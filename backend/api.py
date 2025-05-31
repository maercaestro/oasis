"""
OASIS Database-Powered API
New API layer using SQLite database instead of JSON files.
Provides atomic operations, concurrent access, and data consistency.

Copyright (c) by Abu Huzaifah Bidin with help from Github Copilot
"""

from flask import Flask, request, jsonify, Response
from flask_cors import CORS
import os
import json
from typing import Dict, List, Any, Optional
from datetime import datetime

# Import existing scheduler components
from scheduler import (
    Scheduler, VesselOptimizer, SchedulerOptimizer, 
    Tank, Vessel, Crude, Route, FeedstockParcel, FeedstockRequirement, DailyPlan
)
from scheduler.models import BlendingRecipe

# Import new database components
from database.extended_ops import DatabaseManagerExtended

# Import OpenAI function calling system
from llm_functions import OASISLLMFunctions

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})

# Initialize database
DB_PATH = os.path.join(os.path.dirname(__file__), "oasis.db")
db = DatabaseManagerExtended(DB_PATH)

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

# ==============================================================================
# DATABASE-POWERED DATA ENDPOINTS
# ==============================================================================

@app.route('/api/data', methods=['GET'])
def get_all_data():
    """Get all system data from database."""
    try:
        # Get all data from database
        tanks_data = db.get_all_tanks()
        vessels_data = db.get_all_vessels()
        crudes_data = {crude['name']: crude for crude in db.get_all_crudes()}
        recipes_data = db.get_all_blending_recipes()
        
        # Convert recipes to dictionary format for compatibility
        recipes_dict = {}
        for idx, recipe in enumerate(recipes_data):
            recipes_dict[str(idx)] = recipe
        
        return jsonify({
            'tanks': tanks_data,
            'vessels': vessels_data,
            'crudes': crudes_data,
            'recipes': recipes_dict,
            'timestamp': datetime.now().isoformat(),
            'source': 'database'
        })
        
    except Exception as e:
        return jsonify({'error': f'Failed to load data: {str(e)}'}), 500

@app.route('/api/data/tanks', methods=['GET'])
def get_tanks():
    """Get tanks data from database."""
    try:
        tanks_data = db.get_all_tanks()
        return jsonify(tanks_data)
    except Exception as e:
        return jsonify({'error': f'Failed to load tanks: {str(e)}'}), 500

@app.route('/api/data/tanks', methods=['POST'])
def save_tanks():
    """Save tanks data to database with atomic transaction."""
    try:
        tanks_data = request.get_json()
        if not tanks_data:
            return jsonify({'error': 'No tanks data provided'}), 400
        
        success = db.save_tanks_data(tanks_data)
        
        if success:
            return jsonify({
                'message': 'Tanks saved successfully',
                'timestamp': datetime.now().isoformat(),
                'tanks_count': len(tanks_data)
            })
        else:
            return jsonify({'error': 'Failed to save tanks'}), 500
            
    except Exception as e:
        return jsonify({'error': f'Failed to save tanks: {str(e)}'}), 500

@app.route('/api/data/tanks/<tank_name>', methods=['GET'])
def get_tank(tank_name):
    """Get specific tank data."""
    try:
        tank_data = db.get_tank(name=tank_name)
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
        
        success = db.update_tank(name=tank_name, **update_data)
        
        if success:
            return jsonify({
                'message': f'Tank {tank_name} updated successfully',
                'timestamp': datetime.now().isoformat()
            })
        else:
            return jsonify({'error': 'Tank not found or update failed'}), 404
            
    except Exception as e:
        return jsonify({'error': f'Failed to update tank: {str(e)}'}), 500

@app.route('/api/data/tanks/<tank_name>', methods=['DELETE'])
def delete_tank(tank_name):
    """Delete specific tank."""
    try:
        success = db.delete_tank(name=tank_name)
        
        if success:
            return jsonify({
                'message': f'Tank {tank_name} deleted successfully',
                'timestamp': datetime.now().isoformat()
            })
        else:
            return jsonify({'error': 'Tank not found'}), 404
            
    except Exception as e:
        return jsonify({'error': f'Failed to delete tank: {str(e)}'}), 500

@app.route('/api/data/vessels', methods=['GET'])
def get_vessels():
    """Get vessels data from database."""
    try:
        vessels_data = db.get_all_vessels()
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
        
        success = db.save_vessels_data(vessels_data)
        
        if success:
            return jsonify({
                'message': 'Vessels saved successfully',
                'timestamp': datetime.now().isoformat(),
                'vessels_count': len(vessels_data)
            })
        else:
            return jsonify({'error': 'Failed to save vessels'}), 500
            
    except Exception as e:
        return jsonify({'error': f'Failed to save vessels: {str(e)}'}), 500

@app.route('/api/data/crudes', methods=['GET'])
def get_crudes():
    """Get crudes data from database."""
    try:
        crudes_list = db.get_all_crudes()
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
        
        # Clear existing crudes and add new ones
        with db.transaction() as conn:
            conn.execute("DELETE FROM crudes")
            
            for crude_name, crude_info in crudes_data.items():
                db.create_crude(
                    name=crude_name,
                    margin=crude_info.get('margin', 15.0),
                    origin=crude_info.get('origin', 'Unknown')
                )
        
        return jsonify({
            'message': 'Crudes saved successfully',
            'timestamp': datetime.now().isoformat(),
            'crudes_count': len(crudes_data)
        })
        
    except Exception as e:
        return jsonify({'error': f'Failed to save crudes: {str(e)}'}), 500

@app.route('/api/data/recipes', methods=['GET'])
def get_recipes():
    """Get recipes data from database."""
    try:
        recipes_list = db.get_all_blending_recipes()
        # Convert to dictionary format for compatibility
        recipes_data = {}
        for idx, recipe in enumerate(recipes_list):
            recipes_data[str(idx)] = recipe
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
        
        # Convert to list format
        recipes_list = []
        for recipe_id, recipe_info in recipes_data.items():
            recipes_list.append(recipe_info)
        
        success = db.save_blending_recipes(recipes_list)
        
        if success:
            return jsonify({
                'message': 'Recipes saved successfully',
                'timestamp': datetime.now().isoformat(),
                'recipes_count': len(recipes_list)
            })
        else:
            return jsonify({'error': 'Failed to save recipes'}), 500
            
    except Exception as e:
        return jsonify({'error': f'Failed to save recipes: {str(e)}'}), 500

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
        data = request.get_json() or {}
        horizon_days = data.get('days', 30)
        objective = data.get('objective', 'margin')  # 'margin' or 'throughput'
        
        print(f"Starting schedule optimization for {horizon_days} days with objective: {objective}")
        
        # Load data from database
        crudes = load_crudes_from_db()
        recipes = load_recipes_from_db()
        
        # Check if we have an existing schedule to optimize
        current_schedule = data.get('schedule', [])
        if not current_schedule:
            # If no schedule provided, we need to generate one first using the scheduler
            print("No existing schedule provided, running scheduler first...")
            tanks = load_tanks_from_db()
            vessels = load_vessels_from_db()
            
            scheduler = Scheduler(
                tanks=tanks,
                blending_recipes=recipes,
                vessels=vessels,
                crude_data=crudes,
                max_processing_rate=100
            )
            
            # Generate initial schedule
            initial_schedule_json = scheduler.run(horizon_days, save_output=False)
            
            # Convert JSON schedule to DailyPlan objects for optimization
            from scheduler.models import DailyPlan
            schedule_objects = []
            for day_data in initial_schedule_json:
                plan = DailyPlan(
                    day=day_data['day'],
                    processing_rates=day_data.get('processing_rates', {}),
                    blending_details=recipes, # Use all available recipes
                    inventory=day_data.get('inventory', 0),
                    inventory_by_grade=day_data.get('inventory_by_grade', {}),
                    tanks={}  # Simplified for optimization
                )
                schedule_objects.append(plan)
            
            current_schedule = schedule_objects
        else:
            # Convert provided schedule from JSON to DailyPlan objects
            from scheduler.models import DailyPlan
            schedule_objects = []
            for day_data in current_schedule:
                plan = DailyPlan(
                    day=day_data['day'],
                    processing_rates=day_data.get('processing_rates', {}),
                    blending_details=recipes,
                    inventory=day_data.get('inventory', 0),
                    inventory_by_grade=day_data.get('inventory_by_grade', {}),
                    tanks=day_data.get('tanks', {})
                )
                schedule_objects.append(plan)
            
            current_schedule = schedule_objects
        
        # Create optimizer
        optimizer = SchedulerOptimizer(
            blending_recipes=recipes,
            crude_data=crudes,
            max_processing_rate=100
        )
        
        # Run optimization based on objective
        if objective == 'throughput':
            optimized_schedule = optimizer.optimize_throughput(current_schedule)
        else:
            optimized_schedule = optimizer.optimize_margin(current_schedule)
        
        # Convert optimized schedule back to JSON format
        result = []
        for plan in optimized_schedule:
            plan_json = {
                "day": plan.day,
                "processing_rates": plan.processing_rates,
                "inventory": plan.inventory,
                "inventory_by_grade": plan.inventory_by_grade,
                "blending_details": [
                    {
                        "name": recipe.name,
                        "primary_grade": recipe.primary_grade,
                        "secondary_grade": recipe.secondary_grade,
                        "max_rate": recipe.max_rate,
                        "primary_fraction": recipe.primary_fraction,
                        "margin": getattr(recipe, 'margin', 0)
                    }
                    for recipe in plan.blending_details
                ],
                "tanks": {}  # Simplified
            }
            result.append(plan_json)
        
        return jsonify({
            'success': True,
            'schedule': result,
            'objective': objective,
            'horizon_days': horizon_days,
            'timestamp': datetime.now().isoformat(),
            'source': 'database_optimizer'
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Schedule optimization failed: {str(e)}'}), 500

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

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)
