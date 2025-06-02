"""
OASIS Database-Powered API
New API layer using SQLite database instead of JSON files.
Provides atomic operations, concurrent access, and data consistency.

Copyright (c) by Abu Huzaifah Bidin with help from Github Copilot
"""

from flask import Flask, request, jsonify, Response, stream_with_context
from flask_cors import CORS
import os
import json
from typing import Dict, List, Any, Optional
from datetime import datetime
import logging
import traceback
import queue
import threading
import time

# Import existing scheduler components
from scheduler.scheduler import Scheduler
from scheduler.vessel_optimizer import VesselOptimizer
from scheduler.optimizer import SchedulerOptimizer
from scheduler.models import Tank, Vessel, Crude, Route, FeedstockParcel, FeedstockRequirement, DailyPlan, BlendingRecipe

# Import new database components
from database.extended_ops import DatabaseManagerExtended

# Import OpenAI function calling system
from llm_functions import OASISLLMFunctions
from data_services import DataService

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})

# Configure logging for API
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
)
api_logger = logging.getLogger("api")

# Initialize database
DB_PATH = os.path.join(os.path.dirname(__file__), "oasis.db")
db = DatabaseManagerExtended(DB_PATH)
data_service = DataService(db)

# Initialize LLM functions with database
llm_functions = OASISLLMFunctions(DB_PATH)

# Migration flag file
MIGRATION_FLAG = os.path.join(os.path.dirname(__file__), ".migration_completed")

def ensure_migration():
    """Ensure JSON data has been migrated to database."""
    if not os.path.exists(MIGRATION_FLAG):
        print("⚠️  Database migration not completed. Run migration first.")
        print("To migrate: python -m database.migration")
        return False
    return True

# Initialize migration check at module level
if not ensure_migration():
    print("Warning: Database migration not completed. Some features may not work.")

# Global event queue for SSE notifications
data_change_queue = queue.Queue()
sse_connections = []

# Data change notification system
def notify_data_change(change_type: str, data_type: str = None, details: dict = None):
    """Notify all connected clients about data changes."""
    event_data = {
        'type': change_type,
        'data_type': data_type,
        'timestamp': datetime.now().isoformat(),
        'details': details or {}
    }
    
    # Add to queue for SSE connections
    try:
        data_change_queue.put(event_data, block=False)
        print(f"📡 Data change notification: {change_type} - {data_type}")
    except queue.Full:
        print("⚠️  SSE queue is full, dropping notification")

@app.route('/api/data-stream')
def data_stream():
    """Server-Sent Events endpoint for real-time data updates."""
    def event_generator():
        # Send initial connection event
        yield f"data: {json.dumps({'type': 'connected', 'timestamp': datetime.now().isoformat()})}\n\n"
        
        last_heartbeat = time.time()
        
        while True:
            try:
                # Send heartbeat every 30 seconds
                current_time = time.time()
                if current_time - last_heartbeat > 30:
                    yield f"data: {json.dumps({'type': 'heartbeat', 'timestamp': datetime.now().isoformat()})}\n\n"
                    last_heartbeat = current_time
                
                # Check for data change notifications
                try:
                    event_data = data_change_queue.get(timeout=1)
                    yield f"data: {json.dumps(event_data)}\n\n"
                except queue.Empty:
                    continue
                    
            except GeneratorExit:
                print("[SSE] Client disconnected from data stream.")
                break
            except Exception as e:
                print(f"[SSE] Exception in event_generator: {e}")
                break
    
    response = Response(event_generator(), mimetype='text/event-stream')
    response.headers['Cache-Control'] = 'no-cache'
    response.headers['Connection'] = 'keep-alive'
    response.headers['Access-Control-Allow-Origin'] = '*'
    return response

# ==============================================================================
# DATABASE-POWERED DATA ENDPOINTS
# ==============================================================================

@app.route('/api/data', methods=['GET'])
def get_all_data():
    """Get all system data from database."""
    try:
        print("[get_all_data] Starting to load all system data...")
        
        # Get all data from database
        tanks_data = db.get_all_tanks()
        print(f"[get_all_data] Loaded {len(tanks_data)} tanks")
        
        vessels_data = db.get_all_vessels()
        print(f"[get_all_data] Loaded {len(vessels_data)} vessels")
        
        crudes_data = {crude['name']: crude for crude in db.get_all_crudes()}
        print(f"[get_all_data] Loaded {len(crudes_data)} crudes")
        
        recipes_data = db.get_all_blending_recipes()
        print(f"[get_all_data] Loaded {len(recipes_data)} recipes")
        
        # Convert recipes to dictionary format for compatibility
        recipes_dict = {}
        for idx, recipe in enumerate(recipes_data):
            recipes_dict[str(idx)] = recipe
        
        # Get feedstock requirements
        feedstock_requirements = db.get_all_feedstock_requirements()
        print(f"[get_all_data] Loaded {len(feedstock_requirements)} feedstock requirements")
        
        # Get routes
        routes_data = db.get_all_routes()
        print(f"[get_all_data] Loaded {len(routes_data)} routes")
        
        # Get plants
        plants_data = db.get_all_plants()
        print(f"[get_all_data] Loaded {len(plants_data)} plants")
        
        # Get vessel types from database
        vessel_types = db.get_all_vessel_types()
        if not vessel_types:
            # Fallback to default if DB is empty
            vessel_types = [
                {"name": "Large Vessel", "capacity": 700, "cost": 80000},
                {"name": "Medium Vessel", "capacity": 500, "cost": 60000},
                {"name": "Small Vessel", "capacity": 300, "cost": 40000}
            ]
        print(f"[get_all_data] Loaded {len(vessel_types)} vessel types")
        
        # Extract feedstock parcels from vessel cargo
        feedstock_parcels = []
        for vessel_id, vessel_info in vessels_data.items():
            for cargo_item in vessel_info.get('cargo', []):
                feedstock_parcels.append({
                    'grade': cargo_item.get('grade', ''),
                    'volume': cargo_item.get('volume', 0),
                    'origin': cargo_item.get('origin', ''),
                    'available_from': cargo_item.get('loading_start_day', 0),
                    'expiry': cargo_item.get('loading_end_day', 30),
                    'vessel_id': vessel_id
                })
        print(f"[get_all_data] Extracted {len(feedstock_parcels)} feedstock parcels from vessels")
        
        # Load schedule data if available
        schedule_data = []
        schedule_path = os.path.join(os.path.dirname(__file__), "output", "schedule_results.json")
        try:
            with open(schedule_path, 'r') as f:
                schedule_json = json.load(f)
                # Extract the daily_plans array from the nested structure
                schedule_data = schedule_json.get('daily_plans', [])
                print(f"[get_all_data] Loaded schedule data with {len(schedule_data)} daily plans")
        except (FileNotFoundError, json.JSONDecodeError):
            print(f"[get_all_data] No schedule data found at {schedule_path}")
            pass
        
        response_data = {
            'tanks': tanks_data,
            'vessels': vessels_data,
            'crudes': crudes_data,
            'recipes': recipes_dict,
            'feedstock_requirements': feedstock_requirements,
            'feedstock_parcels': feedstock_parcels,
            'routes': routes_data,
            'plants': plants_data,
            'vessel_types': vessel_types,
            'schedule': schedule_data,
            'timestamp': datetime.now().isoformat(),
            'source': 'database'
        }
        
        print(f"[get_all_data] Successfully loaded all data types: {list(response_data.keys())}")
        return jsonify(response_data)
        
    except Exception as e:
        print(f"[get_all_data] Error loading data: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Failed to load data: {str(e)}'}), 500

@app.route('/api/data/tanks', methods=['GET'])
def get_tanks():
    """Get tanks data from database."""
    try:
        tanks_data = data_service.get_all_tanks()
        return jsonify(tanks_data)
    except Exception as e:
        return jsonify({'error': f'Failed to load tanks: {str(e)}'}), 500

@app.route('/api/data/tanks', methods=['POST'])
def save_tanks():
    """Save tanks data to database with atomic transaction."""
    try:
        tanks_data = request.get_json()
        print(f"[save_tanks] Received tanks_data: {tanks_data}")  # Log incoming data
        if not tanks_data:
            print("[save_tanks] No tanks data provided!")
            return jsonify({'error': 'No tanks data provided'}), 400
        success = data_service.save_tanks(tanks_data)
        print(f"[save_tanks] Save result: {success}")
        if success:
            # Notify about tank data change
            notify_data_change('update', 'tanks', {'count': len(tanks_data)})
            return jsonify({'message': 'Tanks saved successfully', 'timestamp': datetime.now().isoformat(), 'tanks_count': len(tanks_data)})
        else:
            print("[save_tanks] Failed to save tanks (service returned False)")
            return jsonify({'error': 'Failed to save tanks'}), 500
    except Exception as e:
        import traceback
        print(f"[save_tanks] Exception: {e}")
        traceback.print_exc()
        return jsonify({'error': f'Failed to save tanks: {str(e)}'}), 500

@app.route('/api/data/tanks/<tank_name>', methods=['GET'])
def get_tank(tank_name):
    """Get specific tank data."""
    try:
        tank_data = data_service.get_tank(tank_name)
        if tank_data:
            return jsonify(tank_data)
        else:
            return jsonify({'error': 'Tank not found'}), 404
    except Exception as e:
        return jsonify({'error': f'Failed to get tank: {str(e)}'}), 500

@app.route('/api/data/tanks/<tank_name>', methods=['PUT'])
def update_tank(tank_name):
    """Update specific tank."""
    try:
        update_data = request.get_json()
        if not update_data:
            return jsonify({'error': 'No update data provided'}), 400
        success = data_service.update_tank(tank_name, update_data)
        if success:
            # Notify about tank data change
            notify_data_change('update', 'tanks', {'name': tank_name})
            return jsonify({'message': f'Tank {tank_name} updated successfully', 'timestamp': datetime.now().isoformat()})
        else:
            return jsonify({'error': 'Tank not found or update failed'}), 404
    except Exception as e:
        return jsonify({'error': f'Failed to update tank: {str(e)}'}), 500

@app.route('/api/data/tanks/<tank_name>', methods=['DELETE'])
def delete_tank(tank_name):
    """Delete specific tank."""
    try:
        success = data_service.delete_tank(tank_name)
        if success:
            # Notify about tank data change
            notify_data_change('delete', 'tanks', {'name': tank_name})
            return jsonify({'message': f'Tank {tank_name} deleted successfully', 'timestamp': datetime.now().isoformat()})
        else:
            return jsonify({'error': 'Tank not found'}), 404
    except Exception as e:
        return jsonify({'error': f'Failed to delete tank: {str(e)}'}), 500

@app.route('/api/data/vessels', methods=['GET'])
def get_vessels():
    """Get vessels data from database."""
    try:
        vessels_data = data_service.get_all_vessels()
        return jsonify(vessels_data)
    except Exception as e:
        return jsonify({'error': f'Failed to load vessels: {str(e)}'}), 500

@app.route('/api/data/vessels', methods=['POST'])
def save_vessels():
    """Save vessels data to database with atomic transaction."""
    try:
        vessels_data = request.get_json()
        if not vessels_data:
            return jsonify({'error': 'No vessels data provided'}), 400
        success = data_service.save_vessels(vessels_data)
        if success:
            # Notify about vessel data change
            notify_data_change('update', 'vessels', {'count': len(vessels_data)})
            return jsonify({'message': 'Vessels saved successfully', 'timestamp': datetime.now().isoformat(), 'vessels_count': len(vessels_data)})
        else:
            return jsonify({'error': 'Failed to save vessels'}), 500
    except Exception as e:
        return jsonify({'error': f'Failed to save vessels: {str(e)}'}), 500

@app.route('/api/data/crudes', methods=['GET'])
def get_crudes():
    """Get crudes data from database."""
    try:
        crudes_list = data_service.get_all_crudes()
        # Convert to dictionary format for compatibility
        crudes_data = {crude['name']: crude for crude in crudes_list}
        return jsonify(crudes_data)
    except Exception as e:
        return jsonify({'error': f'Failed to load crudes: {str(e)}'}), 500

@app.route('/api/data/crudes', methods=['POST'])
def save_crudes():
    """Save crudes data to database."""
    try:
        crudes_data = request.get_json()
        if not crudes_data:
            return jsonify({'error': 'No crudes data provided'}), 400
        data_service.save_crudes(crudes_data)
        # Notify about crude data change
        notify_data_change('update', 'crudes', {'count': len(crudes_data)})
        return jsonify({'message': 'Crudes saved successfully', 'timestamp': datetime.now().isoformat(), 'crudes_count': len(crudes_data)})
    except Exception as e:
        return jsonify({'error': f'Failed to save crudes: {str(e)}'}), 500

@app.route('/api/data/recipes', methods=['GET'])
def get_recipes():
    """Get recipes data from database."""
    try:
        recipes_list = data_service.get_all_recipes()
        # Convert to dictionary format for compatibility
        recipes_data = {str(idx): recipe for idx, recipe in enumerate(recipes_list)}
        return jsonify(recipes_data)
    except Exception as e:
        return jsonify({'error': f'Failed to load recipes: {str(e)}'}), 500

@app.route('/api/data/recipes', methods=['POST'])
def save_recipes():
    """Save recipes data to database."""
    try:
        recipes_data = request.get_json()
        if not recipes_data:
            return jsonify({'error': 'No recipes data provided'}), 400
        success = data_service.save_recipes(recipes_data)
        if success:
            # Notify about recipe data change
            notify_data_change('update', 'recipes', {'count': len(recipes_data)})
            return jsonify({'message': 'Recipes saved successfully', 'timestamp': datetime.now().isoformat(), 'recipes_count': len(recipes_data)})
        else:
            return jsonify({'error': 'Failed to save recipes'}), 500
    except Exception as e:
        return jsonify({'error': f'Failed to save recipes: {str(e)}'}), 500

@app.route('/api/data/feedstock_parcels', methods=['GET'])
def get_feedstock_parcels():
    """Get feedstock parcels data extracted from vessel cargo."""
    try:
        print("[get_feedstock_parcels] Loading feedstock parcels from vessel cargo...")
        vessels_data = db.get_all_vessels()
        
        feedstock_parcels = []
        for vessel_id, vessel_info in vessels_data.items():
            for cargo_item in vessel_info.get('cargo', []):
                feedstock_parcels.append({
                    'grade': cargo_item.get('grade', ''),
                    'volume': cargo_item.get('volume', 0),
                    'origin': cargo_item.get('origin', ''),
                    'available_from': cargo_item.get('loading_start_day', 0),
                    'expiry': cargo_item.get('loading_end_day', 30),
                    'vessel_id': vessel_id
                })
        
        print(f"[get_feedstock_parcels] Extracted {len(feedstock_parcels)} feedstock parcels")
        return jsonify(feedstock_parcels)
    except Exception as e:
        print(f"[get_feedstock_parcels] Error: {str(e)}")
        return jsonify({'error': f'Failed to load feedstock parcels: {str(e)}'}), 500

@app.route('/api/data/feedstock_parcels', methods=['POST'])
def save_feedstock_parcels():
    """Save feedstock parcels data (updates vessel cargo)."""
    try:
        parcels_data = request.get_json()
        if not parcels_data:
            return jsonify({'error': 'No feedstock parcels data provided'}), 400
        
        print(f"[save_feedstock_parcels] Received {len(parcels_data)} feedstock parcels")
        
        # For now, just acknowledge the save - implementing vessel cargo update would require more complex logic
        # Notify about parcel data change
        notify_data_change('update', 'feedstock_parcels', {'count': len(parcels_data)})
        return jsonify({
            'message': 'Feedstock parcels received successfully', 
            'timestamp': datetime.now().isoformat(), 
            'parcels_count': len(parcels_data),
            'note': 'Feedstock parcels are derived from vessel cargo. Use vessel endpoints to modify cargo.'
        })
    except Exception as e:
        print(f"[save_feedstock_parcels] Error: {str(e)}")
        return jsonify({'error': f'Failed to save feedstock parcels: {str(e)}'}), 500

@app.route('/api/data/feedstock_requirements', methods=['GET'])
def get_feedstock_requirements():
    """Get feedstock requirements data from database."""
    try:
        print("[get_feedstock_requirements] Loading feedstock requirements...")
        requirements = db.get_all_feedstock_requirements()
        print(f"[get_feedstock_requirements] Loaded {len(requirements)} requirements")
        return jsonify(requirements)
    except Exception as e:
        print(f"[get_feedstock_requirements] Error: {str(e)}")
        return jsonify({'error': f'Failed to load feedstock requirements: {str(e)}'}), 500

@app.route('/api/data/routes', methods=['GET'])
def get_routes():
    """Get routes data from database."""
    try:
        print("[get_routes] Loading routes...")
        routes = db.get_all_routes()
        print(f"[get_routes] Loaded {len(routes)} routes")
        return jsonify(routes)
    except Exception as e:
        print(f"[get_routes] Error: {str(e)}")
        return jsonify({'error': f'Failed to load routes: {str(e)}'}), 500

@app.route('/api/data/plants', methods=['GET'])
def get_plants():
    """Get plants data from database."""
    try:
        print("[get_plants] Loading plants...")
        plants = db.get_all_plants()
        print(f"[get_plants] Loaded {len(plants)} plants")
        return jsonify(plants)
    except Exception as e:
        print(f"[get_plants] Error: {str(e)}")
        return jsonify({'error': f'Failed to load plants: {str(e)}'}), 500

@app.route('/api/data/vessel_types', methods=['GET'])
def get_vessel_types():
    """Get vessel types data from database."""
    try:
        print("[get_vessel_types] Loading vessel types from DB...")
        vessel_types = db.get_all_vessel_types()
        if not vessel_types:
            # Fallback to default if DB is empty
            vessel_types = [
                {"name": "Large Vessel", "capacity": 700, "cost": 80000},
                {"name": "Medium Vessel", "capacity": 500, "cost": 60000},
                {"name": "Small Vessel", "capacity": 300, "cost": 40000}
            ]
        print(f"[get_vessel_types] Loaded {len(vessel_types)} vessel types")
        return jsonify(vessel_types)
    except Exception as e:
        print(f"[get_vessel_types] Error: {str(e)}")
        return jsonify({'error': f'Failed to load vessel types: {str(e)}'}), 500

@app.route('/api/data/vessel_types', methods=['POST'])
def save_vessel_types():
    """Save vessel types data to database."""
    try:
        vessel_types = request.get_json()
        if not vessel_types:
            return jsonify({'error': 'No vessel types data provided'}), 400
        db.save_vessel_types(vessel_types)
        print(f"[save_vessel_types] Saved {len(vessel_types)} vessel types to DB")
        notify_data_change('update', 'vessel_types', {'count': len(vessel_types)})
        return jsonify({
            'message': 'Vessel types saved successfully',
            'timestamp': datetime.now().isoformat(),
            'vessel_types_count': len(vessel_types)
        })
    except Exception as e:
        print(f"[save_vessel_types] Error: {str(e)}")
        return jsonify({'error': f'Failed to save vessel types: {str(e)}'}), 500

@app.route('/api/save-schedule', methods=['POST'])
def save_schedule():
    """Save modified schedule data to JSON file."""
    try:
        data = request.get_json()
        schedule = data.get('schedule', [])
        if not schedule:
            return jsonify({"success": False, "error": "No schedule data provided"}), 400
        data_service.save_schedule(schedule)
        # Notify about schedule data change
        notify_data_change('update', 'schedule', {'saved_days': len(schedule)})
        return jsonify({"success": True, "message": "Schedule saved successfully", "days_saved": len(schedule)})
    except Exception as e:
        return jsonify({"success": False, "error": f"Failed to save schedule: {str(e)}"}), 500

# ==============================================================================
# DATABASE-AWARE SCHEDULER ENDPOINTS
# ==============================================================================

def load_tanks_from_db() -> Dict[str, Tank]:
    """Load tanks from database and convert to Tank objects."""
    tanks_data = db.get_all_tanks()
    tanks = {}
    
    for tank_name, tank_info in tanks_data.items():
        tank = Tank(
            name=tank_name,
            capacity=tank_info['capacity'],
            content=tank_info['content']
        )
        tanks[tank_name] = tank
    
    return tanks

def load_vessels_from_db() -> List[Vessel]:
    """Load vessels from database and convert to Vessel objects."""
    vessels_data = db.get_all_vessels()
    vessels = []
    
    for vessel_id, vessel_info in vessels_data.items():
        # Process cargo data
        cargo = []
        for parcel_info in vessel_info.get("cargo", []):
            cargo.append(FeedstockParcel(
                grade=parcel_info.get("grade", ""),
                volume=parcel_info.get("volume", 0),
                origin=parcel_info.get("origin", ""),
                ldr={
                    int(parcel_info.get("loading_start_day", 0)): 
                    int(parcel_info.get("loading_end_day", 0))
                },
                vessel_id=vessel_id
            ))
        
        # Create vessel object
        vessel = Vessel(
            vessel_id=vessel_id,
            arrival_day=int(vessel_info.get("arrival_day", 0)),
            capacity=float(vessel_info.get("capacity", 0)),
            cost=float(vessel_info.get("cost", 0)),
            cargo=cargo,
            days_held=int(vessel_info.get("days_held", 0))
        )
        
        # Set route attribute
        if "route" in vessel_info:
            vessel.route = vessel_info["route"]
        
        vessels.append(vessel)
    
    return vessels

def load_crudes_from_db() -> Dict[str, Crude]:
    """Load crudes from database and convert to Crude objects."""
    crudes_list = db.get_all_crudes()
    crudes = {}
    
    for crude_info in crudes_list:
        crude = Crude(
            name=crude_info['name'],
            margin=crude_info['margin'],
            origin=crude_info['origin']
        )
        crudes[crude_info['name']] = crude
    
    return crudes

def load_recipes_from_db() -> List[BlendingRecipe]:
    """Load recipes from database and convert to BlendingRecipe objects."""
    recipes_list = db.get_all_blending_recipes()
    recipes = []
    
    for recipe_info in recipes_list:
        recipe = BlendingRecipe(
            name=recipe_info['name'],
            primary_grade=recipe_info['primary_grade'],
            secondary_grade=recipe_info.get('secondary_grade'),
            max_rate=recipe_info['max_rate'],
            primary_fraction=recipe_info['primary_fraction']
        )
        recipes.append(recipe)
    
    return recipes

@app.route('/api/scheduler/run', methods=['POST'])
def run_scheduler():
    """Run scheduler with database data."""
    try:
        data = request.get_json() or {}
        horizon_days = data.get('horizon_days', 30)
        
        print(f"Starting scheduler for {horizon_days} days with database data...")
        
        # Load data from database
        tanks = load_tanks_from_db()
        vessels = load_vessels_from_db()
        crudes = load_crudes_from_db()
        recipes = load_recipes_from_db()
        
        print(f"Loaded from database: {len(tanks)} tanks, {len(vessels)} vessels, {len(crudes)} crudes, {len(recipes)} recipes")
        
        # Create scheduler
        scheduler = Scheduler(
            tanks=tanks,
            blending_recipes=recipes,
            vessels=vessels,
            crude_data=crudes,
            max_processing_rate=100  # Default max processing rate
        )
        
        # Run scheduling
        result = scheduler.run(horizon_days, save_output=True)
        
        # Notify about schedule data change
        notify_data_change('update', 'schedule', {'days': len(result), 'horizon': horizon_days})
        
        # The run method returns a list of daily plans in JSON format
        return jsonify({
            'success': True,
            'schedule': result,
            'horizon_days': horizon_days,
            'timestamp': datetime.now().isoformat(),
            'source': 'database'
        })
        
    except Exception as e:
        return jsonify({'error': f'Scheduler failed: {str(e)}'}), 500

@app.route('/api/optimizer/optimize', methods=['POST'])
def optimize_schedule():
    """Run schedule optimizer with database data."""
    try:
        api_logger.info("/api/optimizer/optimize endpoint called")
        data = request.get_json() or {}
        horizon_days = data.get('days', 30)
        objective = data.get('objective', 'margin')  # 'margin' or 'throughput'
        api_logger.info(f"Optimization request: days={horizon_days}, objective={objective}")
        # Load data from database
        crudes = load_crudes_from_db()
        recipes = load_recipes_from_db()
        # Check if we have an existing schedule to optimize
        current_schedule = data.get('schedule', [])
        from scheduler.models import DailyPlan
        schedule_objects = []
        tanks_db = load_tanks_from_db()
        # Load vessels from database for inventory arrivals
        vessels = load_vessels_from_db()
        if not current_schedule:
            api_logger.warning("No schedule provided in request payload")
            return jsonify({'error': 'No schedule provided'}), 400
        else:
            # Convert JSON schedule to DailyPlan objects, reconstructing Tank objects
            for day in current_schedule:
                tanks_dict = {}
                for tank_name, tank_info in day.get('tanks', {}).items():
                    if isinstance(tank_info, Tank):
                        tanks_dict[tank_name] = tank_info
                    else:
                        tanks_dict[tank_name] = Tank(
                            name=tank_info.get('name', tank_name),
                            capacity=tank_info.get('capacity', 0),
                            content=tank_info.get('content', [])
                        )
                schedule_objects.append(DailyPlan(
                    day=day.get('day'),
                    processing_rates=day.get('processing_rates', {}),
                    blending_details=day.get('blending_details', []),
                    inventory=day.get('inventory', 0),
                    inventory_by_grade=day.get('inventory_by_grade', {}),
                    daily_margin=day.get('daily_margin', 0),
                    tanks=tanks_dict
                ))
        # Create optimizer
        optimizer = SchedulerOptimizer(
            blending_recipes=recipes,
            crude_data=crudes,
            max_processing_rate=100
        )
        api_logger.info(f"Starting optimization: {objective} for {len(schedule_objects)} days (with vessels)")
        # Run optimization based on objective, now passing vessels
        if objective == 'throughput':
            optimized_schedule = optimizer.optimize_throughput(schedule_objects, vessels=vessels)
        else:
            optimized_schedule = optimizer.optimize_margin(schedule_objects, vessels=vessels)
        api_logger.info(f"Optimization complete. Days in optimized schedule: {len(optimized_schedule)}")
        # Convert optimized schedule back to JSON format
        result = []
        for plan in optimized_schedule:
            plan_dict = plan.to_dict() if hasattr(plan, 'to_dict') else dict(plan.__dict__)
            # Always include margin as a float, fallback to 0.0 if missing
            plan_dict['margin'] = float(getattr(plan, 'daily_margin', plan_dict.get('margin', 0.0)))
            # --- SERIALIZE blending_details to dicts if needed ---
            if 'blending_details' in plan_dict and plan_dict['blending_details']:
                plan_dict['blending_details'] = [
                    bd if isinstance(bd, dict) else {
                        'name': bd.name,
                        'primary_grade': bd.primary_grade,
                        'secondary_grade': bd.secondary_grade,
                        'primary_fraction': bd.primary_fraction,
                        'max_rate': bd.max_rate
                    } for bd in plan_dict['blending_details']
                ]
            # --- SERIALIZE tanks to dicts if needed ---
            if 'tanks' in plan_dict and plan_dict['tanks']:
                tanks_json = {}
                for tank_name, tank in plan_dict['tanks'].items():
                    if isinstance(tank, dict):
                        tanks_json[tank_name] = tank
                    else:
                        tanks_json[tank_name] = {
                            'name': tank.name,
                            'capacity': tank.capacity,
                            'content': tank.content
                        }
                plan_dict['tanks'] = tanks_json
            result.append(plan_dict)
        # --- AUTO-SAVE optimized schedule to schedule_results.json ---
        try:
            output_path = os.path.join(os.path.dirname(__file__), "output", "schedule_results.json")
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with open(output_path, 'w') as f:
                json.dump({"daily_plans": result}, f, indent=2)
            api_logger.info(f"Auto-saved optimized schedule to {output_path} ({len(result)} days)")
        except Exception as save_exc:
            api_logger.error(f"Failed to auto-save optimized schedule: {save_exc}")
        # --- END AUTO-SAVE ---
        
        # Notify about schedule optimization completion
        notify_data_change('update', 'schedule', {'optimized_days': len(result), 'objective': objective})
        
        return jsonify({
            'success': True,
            'schedule': result,
            'objective': objective,
            'horizon_days': horizon_days,
            'timestamp': datetime.now().isoformat(),
            'source': 'database_optimizer'
        })
    except Exception as e:
        api_logger.error(f"Exception in /api/optimizer/optimize: {str(e)}")
        api_logger.error(traceback.format_exc())
        return jsonify({'error': f'Exception during optimization: {str(e)}'}), 500

@app.route('/api/vessel-optimizer/optimize', methods=['POST'])
def optimize_vessels():
    """Run vessel optimizer with database data."""
    try:
        data = request.get_json() or {}
        horizon_days = data.get('horizon_days', 30)
        
        print(f"Starting vessel optimization for {horizon_days} days...")
        
        # Load data from database
        feedstock_requirements = db.get_all_feedstock_requirements()
        routes_data = db.get_all_routes()
        
        # Convert routes to expected format
        routes = {}
        for route in routes_data:
            key = f"{route['origin']}_{route['destination']}"
            routes[key] = type('Route', (), {
                'origin': route['origin'],
                'destination': route['destination'],
                'time_travel': route['time_travel']
            })()
        
        # Load vessel types (default types for now)
        vessel_types = [
            {"capacity": 700, "cost": 80000},
            {"capacity": 500, "cost": 60000},
            {"capacity": 300, "cost": 40000}
        ]
        
        # Convert feedstock requirements to expected format
        from scheduler.models import FeedstockRequirement
        requirements = []
        for req_data in feedstock_requirements:
            # Convert allowed_ldr from start/end integers to dict format
            allowed_ldr = {}
            if 'allowed_ldr_start' in req_data and 'allowed_ldr_end' in req_data:
                allowed_ldr = {req_data['allowed_ldr_start']: req_data['allowed_ldr_end']}
            elif 'allowed_ldr' in req_data and req_data['allowed_ldr']:
                allowed_ldr = req_data['allowed_ldr']
            
            req = FeedstockRequirement(
                grade=req_data['grade'],
                volume=req_data['volume'],
                origin=req_data['origin'],
                allowed_ldr=allowed_ldr,
                required_arrival_by=req_data.get('required_arrival_by', 30)  # Default to 30 days
            )
            requirements.append(req)
        
        # Create vessel optimizer
        vessel_optimizer = VesselOptimizer(
            feedstock_requirements=requirements,
            routes=routes,
            vessel_types=vessel_types
        )
        
        # Run optimization
        optimized_vessels = vessel_optimizer.optimize_and_save(horizon_days=horizon_days)
        
        # Save optimized vessels back to database
        vessels_dict = {}
        for vessel in optimized_vessels:
            # Convert vessel to dictionary format
            cargo_json = []
            for cargo in vessel.cargo:
                ldr_start = next(iter(cargo.ldr.keys())) if cargo.ldr else 0
                ldr_end = next(iter(cargo.ldr.values())) if cargo.ldr else 0
                cargo_json.append({
                    "grade": cargo.grade,
                    "volume": cargo.volume,
                    "origin": cargo.origin,
                    "loading_start_day": ldr_start,
                    "loading_end_day": ldr_end
                })
            
            vessels_dict[vessel.vessel_id] = {
                "vessel_id": vessel.vessel_id,
                "arrival_day": vessel.arrival_day,
                "capacity": vessel.capacity,
                "cost": vessel.cost,
                "days_held": vessel.days_held,
                "cargo": cargo_json,
                "route": getattr(vessel, 'route', [])
            }
        
        # Save to database
        db.save_vessels_data(vessels_dict)
        
        # Notify about vessel optimization completion
        notify_data_change('update', 'vessels', {'optimized_count': len(optimized_vessels), 'horizon': horizon_days})
        
        return jsonify({
            'message': 'Vessel optimization completed',
            'optimized_vessels': len(optimized_vessels),
            'horizon_days': horizon_days,
            'timestamp': datetime.now().isoformat(),
            'source': 'database'
        })
        
    except Exception as e:
        return jsonify({'error': f'Vessel optimization failed: {str(e)}'}), 500

# ==============================================================================
# DATABASE MANAGEMENT ENDPOINTS
# ==============================================================================

@app.route('/api/database/status', methods=['GET'])
def database_status():
    """Get database status and statistics."""
    try:
        conn = db._get_connection()
        
        # Get table counts
        tables = [
            'plants', 'crudes', 'tanks', 'tank_contents', 'blending_recipes',
            'vessels', 'vessel_cargo', 'vessel_routes', 'routes',
            'feedstock_requirements', 'vessel_daily_locations'
        ]
        
        counts = {}
        for table in tables:
            cursor = conn.execute(f"SELECT COUNT(*) as count FROM {table}")
            counts[table] = cursor.fetchone()['count']
        
        # Check migration status
        migration_completed = os.path.exists(MIGRATION_FLAG)
        
        return jsonify({
            'status': 'operational',
            'migration_completed': migration_completed,
            'database_path': DB_PATH,
            'table_counts': counts,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({'error': f'Database status check failed: {str(e)}'}), 500

@app.route('/api/database/backup', methods=['POST'])
def backup_database():
    """Create database backup."""
    try:
        backup_name = f"oasis_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
        backup_path = os.path.join(os.path.dirname(DB_PATH), backup_name)
        
        # Copy database file
        import shutil
        shutil.copy2(DB_PATH, backup_path)
        
        return jsonify({
            'message': 'Database backup created successfully',
            'backup_path': backup_path,
            'backup_name': backup_name,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({'error': f'Database backup failed: {str(e)}'}), 500

# ==============================================================================
# MIGRATION ENDPOINT
# ==============================================================================

@app.route('/api/database/migrate', methods=['POST'])
def migrate_database():
    """Run database migration from JSON files."""
    try:
        from database.migration import migrate_from_json
        
        # Get paths from request or use defaults
        data = request.get_json() or {}
        static_dir = data.get('static_data_dir', 'static_data')
        dynamic_dir = data.get('dynamic_data_dir', 'dynamic_data')
        
        # Run migration
        results = migrate_from_json(
            db_path=DB_PATH,
            static_data_dir=static_dir,
            dynamic_data_dir=dynamic_dir
        )
        
        # Create migration flag if successful
        if results['status'] == 'completed':
            with open(MIGRATION_FLAG, 'w') as f:
                f.write(datetime.now().isoformat())
        
        return jsonify(results)
        
    except Exception as e:
        return jsonify({'error': f'Migration failed: {str(e)}'}), 500

# ==============================================================================
# CHAT/LLM ENDPOINTS
# ==============================================================================

@app.route('/api/chat/message', methods=['POST'])
def process_chat_message():
    """Process a chat message through OpenAI function calling."""
    try:
        data = request.get_json()
        if not data or 'message' not in data:
            return jsonify({'error': 'Message is required'}), 400
        
        message = data['message']
        conversation_history = data.get('conversation_history', [])
        
        # Process the message through the LLM
        result = llm_functions.process_chat_message(message, conversation_history)
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({
            'error': f'Failed to process chat message: {str(e)}',
            'response': 'I apologize, but I encountered an error while processing your request. Please try again.',
            'function_calls': [],
            'conversation_history': []
        }), 500

@app.route('/api/chat/stream', methods=['POST'])
def process_chat_message_stream():
    """Process a chat message with streaming response."""
    try:
        data = request.get_json()
        if not data or 'message' not in data:
            return jsonify({'error': 'Message is required'}), 400
        
        message = data['message']
        conversation_history = data.get('conversation_history', [])
        
        def generate():
            """Generator function for streaming response."""
            try:
                for chunk in llm_functions.process_chat_message_stream(message, conversation_history):
                    # Send each chunk as Server-Sent Events format
                    yield f"data: {json.dumps(chunk)}\n\n"
            except Exception as e:
                error_chunk = {
                    "type": "error",
                    "error": str(e),
                    "message": "An error occurred while processing your request."
                }
                yield f"data: {json.dumps(error_chunk)}\n\n"
        
        return Response(
            generate(),
            mimetype='text/event-stream',
            headers={
                'Cache-Control': 'no-cache',
                'Connection': 'keep-alive',
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Headers': 'Content-Type',
                'Access-Control-Allow-Methods': 'POST'
            }
        )
        
    except Exception as e:
        return jsonify({
            'error': f'Failed to process streaming chat message: {str(e)}'
        }), 500

@app.route('/api/chat/functions', methods=['GET'])
def get_available_functions():
    """Get list of available LLM functions."""
    try:
        functions = [
            {
                'name': 'get_tank_status',
                'description': 'Get current status of all tanks including inventory levels',
                'category': 'inventory'
            },
            {
                'name': 'update_tank_inventory',
                'description': 'Update inventory levels for specific tanks',
                'category': 'inventory'
            },
            {
                'name': 'get_vessel_schedule',
                'description': 'Get vessel arrival schedules and cargo information',
                'category': 'vessels'
            },
            {
                'name': 'modify_vessel_arrival',
                'description': 'Modify vessel arrival dates and cargo details',
                'category': 'vessels'
            },
            {
                'name': 'get_production_metrics',
                'description': 'Get production rates and efficiency metrics',
                'category': 'production'
            },
            {
                'name': 'get_crude_information',
                'description': 'Get information about crude oil types and properties',
                'category': 'crude'
            },
            {
                'name': 'get_blending_recipes',
                'description': 'Get blending recipes and component ratios',
                'category': 'blending'
            },
            {
                'name': 'run_schedule_optimization',
                'description': 'Run schedule optimization for maximum throughput or margin',
                'category': 'optimization'
            },
            {
                'name': 'run_vessel_optimization',
                'description': 'Optimize vessel arrival schedules',
                'category': 'optimization'
            },
            {
                'name': 'analyze_inventory_trends',
                'description': 'Analyze inventory trends and predict future levels',
                'category': 'analysis'
            },
            {
                'name': 'get_feedstock_requirements',
                'description': 'Get feedstock requirements for production planning',
                'category': 'feedstock'
            },
            {
                'name': 'generate_system_summary',
                'description': 'Generate comprehensive system status summary',
                'category': 'reporting'
            }
        ]
        
        return jsonify({
            'functions': functions,
            'total_count': len(functions),
            'categories': ['inventory', 'vessels', 'production', 'crude', 'blending', 'optimization', 'analysis', 'feedstock', 'reporting']
        })
        
    except Exception as e:
        return jsonify({'error': f'Failed to get functions: {str(e)}'}), 500

@app.route('/api/chat/health', methods=['GET'])
def chat_health_check():
    """Health check for chat/LLM functionality."""
    try:
        # Test database connection
        db_status = db.get_all_tanks() is not None
        
        # Test OpenAI API key
        import openai
        openai_status = bool(os.getenv('OPENAI_API_KEY'))
        
        return jsonify({
            'status': 'healthy' if db_status and openai_status else 'unhealthy',
            'database_connected': db_status,
            'openai_configured': openai_status,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

# ==============================================================================
# ERROR HANDLERS
# ==============================================================================

@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Endpoint not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({'error': 'Internal server error'}), 500

# ==============================================================================
# MAIN
# ==============================================================================

if __name__ == '__main__':
    print("Starting OASIS Database-Powered API Server...")
    print("Database initialized and API server ready")
    app.run(debug=True, host='0.0.0.0', port=5001)
