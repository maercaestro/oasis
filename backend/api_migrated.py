"""
OASIS API Service (Database Migration)
This module provides a Flask API to interact with the OASIS system functionalities.
Exposes endpoints for scheduling, vessel optimization, and schedule optimization.

MIGRATED TO USE SQLITE DATABASE - All JSON file operations replaced with database operations.

Copyright (c) by Abu Huzaifah Bidin with help from Github Copilot
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import json
import os
from typing import Dict, List, Any, Optional
from datetime import datetime

from scheduler import (
    Scheduler, VesselOptimizer, SchedulerOptimizer, 
    Tank, Vessel, Crude, Route, FeedstockParcel, FeedstockRequirement, DailyPlan
)

from scheduler.models import BlendingRecipe

# Import new database components
from database.extended_ops import DatabaseManagerExtended

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})  # This enables CORS for all /api/ routes

# Initialize database
DB_PATH = os.path.join(os.path.dirname(__file__), "oasis.db")
db = DatabaseManagerExtended(DB_PATH)

# Migration flag file
MIGRATION_FLAG = os.path.join(os.path.dirname(__file__), ".migration_completed")

def ensure_migration():
    """Ensure JSON data has been migrated to database."""
    if not os.path.exists(MIGRATION_FLAG):
        print("⚠️  Database migration not completed. Run migration first.")
        print("To migrate: python -m database.migration")
        return False
    return True

@app.before_first_request
def initialize_app():
    """Initialize application on first request."""
    if not ensure_migration():
        raise RuntimeError("Database migration required before starting API")

# ==============================================================================
# DATABASE-POWERED DATA LOADERS
# ==============================================================================

def load_tanks() -> Dict[str, Tank]:
    """Load tank data from database and convert to Tank objects"""
    tanks_data = db.get_all_tanks()
    tanks = {}
    
    for tank_data in tanks_data:
        tank_name = tank_data.get('name', '')
        
        # Get tank contents
        contents = db.get_tank_contents(tank_name)
        content_list = []
        
        for content in contents:
            content_dict = {content['crude_grade']: content['volume']}
            content_list.append(content_dict)
        
        tanks[tank_name] = Tank(
            name=tank_name,
            capacity=tank_data.get('capacity', 0),
            content=content_list
        )
    
    return tanks

def load_recipes() -> List[BlendingRecipe]:
    """Load recipe data from database and convert to BlendingRecipe objects"""
    recipes_data = db.get_all_blending_recipes()
    recipes = []
    
    for recipe_data in recipes_data:
        recipes.append(BlendingRecipe(
            name=recipe_data.get('name', ''),
            primary_grade=recipe_data.get('primary_grade', ''),
            secondary_grade=recipe_data.get('secondary_grade', ''),
            primary_fraction=recipe_data.get('primary_fraction', 0),
            max_rate=recipe_data.get('max_rate', 0)
        ))
    
    return recipes

def load_crudes() -> Dict[str, Crude]:
    """Load crude data from database and convert to Crude objects"""
    crudes_data = db.get_all_crudes()
    crudes = {}
    
    for crude_data in crudes_data:
        crude_name = crude_data.get('name', '')
        crudes[crude_name] = Crude(
            name=crude_name,
            margin=crude_data.get('margin', 0),
            origin=crude_data.get('origin', '')
        )
    
    return crudes

def load_routes() -> Dict[str, Route]:
    """Load route data from database and convert to Route objects"""
    routes_data = db.get_all_routes()
    routes = {}
    
    for route_data in routes_data:
        route_id = route_data.get('id', '')
        routes[route_id] = Route(
            origin=route_data.get('origin', ''),
            destination=route_data.get('destination', ''),
            time_travel=route_data.get('time_travel', 0)
        )
    
    return routes

def load_vessels() -> List[Vessel]:
    """Load vessel data from database and convert to Vessel objects"""
    vessels_data = db.get_all_vessels()
    vessels = []
    
    for vessel_data in vessels_data:
        vessel_id = vessel_data.get('vessel_id', '')
        
        # Get vessel cargo
        cargo_data = db.get_vessel_cargo(vessel_id)
        cargo = []
        
        for cargo_item in cargo_data:
            cargo.append(FeedstockParcel(
                grade=cargo_item.get('grade', ''),
                volume=cargo_item.get('volume', 0),
                origin=cargo_item.get('origin', ''),
                ldr={
                    cargo_item.get('loading_start_day', 0): 
                    cargo_item.get('loading_end_day', 0)
                },
                vessel_id=vessel_id
            ))
        
        # Create vessel object
        vessel = Vessel(
            vessel_id=vessel_id,
            arrival_day=vessel_data.get('arrival_day', 0),
            capacity=vessel_data.get('capacity', 0),
            cost=vessel_data.get('cost', 0),
            cargo=cargo,
            days_held=vessel_data.get('days_held', 0)
        )
        
        # Add vessel route if exists
        route_data = db.get_vessel_routes(vessel_id)
        if route_data:
            vessel.route = route_data
            
        vessels.append(vessel)
    
    return vessels

def load_feedstock_requirements() -> List[FeedstockRequirement]:
    """Load feedstock requirements from database"""
    req_data = db.get_all_feedstock_requirements()
    requirements = []
    
    for req_info in req_data:
        allowed_ldr = {
            req_info.get('loading_start_day', 1): 
            req_info.get('loading_end_day', 10)
        }
        
        requirements.append(FeedstockRequirement(
            grade=req_info.get('grade', ''),
            volume=req_info.get('volume', 0),
            origin=req_info.get('origin', ''),
            allowed_ldr=allowed_ldr,
            required_arrival_by=req_info.get('required_arrival_by', 30)
        ))
    
    return requirements

def load_plant() -> Dict:
    """Load plant configuration from database"""
    plants_data = db.get_all_plants()
    if plants_data:
        return plants_data[0]  # Return first plant config
    return {}

# ==============================================================================
# HELPER FUNCTIONS FOR JSON CONVERSION
# ==============================================================================

def routes_to_dict(routes):
    """Convert Route objects to dictionaries for JSON serialization"""
    return {
        route_id: {
            "origin": route.origin,
            "destination": route.destination,
            "time_travel": route.time_travel
        }
        for route_id, route in routes.items()
    }

def convert_vessels_to_json(vessels) -> List[Dict]:
    """Convert vessel objects to JSON-serializable format"""
    result = []
    
    for vessel in vessels:
        cargo_json = []
        for parcel in vessel.cargo:
            ldr_start = next(iter(parcel.ldr.keys())) if parcel.ldr else 0
            ldr_end = next(iter(parcel.ldr.values())) if parcel.ldr else 0
            
            cargo_json.append({
                "grade": parcel.grade,
                "volume": parcel.volume,
                "origin": parcel.origin,
                "loading_start_day": ldr_start,
                "loading_end_day": ldr_end
            })
        
        vessel_json = {
            "vessel_id": vessel.vessel_id,
            "arrival_day": vessel.arrival_day,
            "capacity": vessel.capacity,
            "cost": vessel.cost,
            "cargo": cargo_json,
            "days_held": vessel.days_held,
            "route": getattr(vessel, 'route', [])
        }
        
        result.append(vessel_json)
    
    return result

def convert_requirements_to_json(requirements) -> List[Dict]:
    """Convert feedstock requirement objects to JSON-serializable format"""
    result = []
    
    for req in requirements:
        ldr_start = next(iter(req.allowed_ldr.keys())) if req.allowed_ldr else 0
        ldr_end = next(iter(req.allowed_ldr.values())) if req.allowed_ldr else 0
        
        req_json = {
            "grade": req.grade,
            "volume": req.volume,
            "origin": req.origin,
            "loading_start_day": ldr_start,
            "loading_end_day": ldr_end,
            "required_arrival_by": req.required_arrival_by
        }
        
        result.append(req_json)
    
    return result

# ==============================================================================
# API ENDPOINTS
# ==============================================================================

@app.route('/api/data', methods=['GET'])
def get_data():
    """Get all configuration data from database"""
    try:
        tanks = load_tanks()
        recipes = load_recipes()
        crudes = load_crudes()
        routes = load_routes()
        vessels = load_vessels()
        
        # Convert vessels list to dictionary format for frontend compatibility
        vessels_dict = {}
        for vessel in vessels:
            vessel_data = {
                "vessel_id": vessel.vessel_id,
                "arrival_day": vessel.arrival_day,
                "capacity": vessel.capacity,
                "cost": vessel.cost,
                "cargo": [
                    {
                        "grade": parcel.grade,
                        "volume": parcel.volume,
                        "origin": parcel.origin,
                        "loading_start_day": next(iter(parcel.ldr.keys())) if parcel.ldr else 0,
                        "loading_end_day": next(iter(parcel.ldr.values())) if parcel.ldr else 0
                    }
                    for parcel in vessel.cargo
                ],
                "days_held": vessel.days_held,
                "route": getattr(vessel, 'route', [])
            }
            vessels_dict[vessel.vessel_id] = vessel_data
        
        # Load schedule data if available
        schedule_data = []
        schedule_path = os.path.join(os.path.dirname(__file__), "output", "schedule_results.json")
        try:
            with open(schedule_path, 'r') as f:
                schedule_json = json.load(f)
                schedule_data = schedule_json.get('daily_plans', [])
        except (FileNotFoundError, json.JSONDecodeError):
            pass
        
        return jsonify({
            "tanks": {name: {"name": tank.name, "capacity": tank.capacity, "content": tank.content} 
                     for name, tank in tanks.items()},
            "recipes": [{"name": r.name, "primary_grade": r.primary_grade, "secondary_grade": r.secondary_grade,
                        "primary_fraction": r.primary_fraction, "max_rate": r.max_rate} for r in recipes],
            "crudes": {name: {"name": crude.name, "margin": crude.margin, "origin": crude.origin} 
                      for name, crude in crudes.items()},
            "routes": routes_to_dict(routes),
            "vessels": vessels_dict,
            "vessel_routes": [],  # TODO: Load from database
            "vessel_types": [],   # TODO: Load from database
            "plants": load_plant(),
            "feedstock_requirements": convert_requirements_to_json(load_feedstock_requirements()),
            "feedstock_parcels": [],  # Can be derived from vessels
            "schedule": schedule_data,
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/save-data', methods=['POST'])
def save_data():
    """Save updated data to database"""
    try:
        data = request.json
        data_type = data.get('type')
        content = data.get('content')
        
        if data_type == 'tanks':
            tank_name = content.get('name')
            if tank_name:
                # Update or create tank
                tank_data = {
                    'name': tank_name,
                    'capacity': content.get('capacity', 0),
                    'plant_id': content.get('plant_id', 1)  # Default plant
                }
                db.save_tank(tank_data)
                
                # Update tank contents
                db.clear_tank_contents(tank_name)
                for content_item in content.get('content', []):
                    for grade, volume in content_item.items():
                        db.add_tank_content({
                            'tank_name': tank_name,
                            'crude_grade': grade,
                            'volume': volume
                        })
                        
        elif data_type == 'vessels':
            vessel_id = content.get('vessel_id')
            if vessel_id:
                # Save vessel
                vessel_data = {
                    'vessel_id': vessel_id,
                    'capacity': content.get('capacity', 0),
                    'cost': content.get('cost', 0),
                    'arrival_day': content.get('arrival_day', 0),
                    'days_held': content.get('days_held', 0)
                }
                db.save_vessel(vessel_data)
                
                # Save vessel cargo
                db.clear_vessel_cargo(vessel_id)
                for cargo_item in content.get('cargo', []):
                    cargo_data = {
                        'vessel_id': vessel_id,
                        'grade': cargo_item.get('grade', ''),
                        'volume': cargo_item.get('volume', 0),
                        'origin': cargo_item.get('origin', ''),
                        'loading_start_day': cargo_item.get('loading_start_day', 0),
                        'loading_end_day': cargo_item.get('loading_end_day', 0)
                    }
                    db.add_vessel_cargo(cargo_data)
                    
        elif data_type == 'crudes':
            crude_name = content.get('name')
            if crude_name:
                crude_data = {
                    'name': crude_name,
                    'margin': content.get('margin', 0),
                    'origin': content.get('origin', '')
                }
                db.save_crude(crude_data)
                
        elif data_type == 'recipes':
            recipe_name = content.get('name')
            if recipe_name:
                recipe_data = {
                    'name': recipe_name,
                    'primary_grade': content.get('primary_grade', ''),
                    'secondary_grade': content.get('secondary_grade', ''),
                    'primary_fraction': content.get('primary_fraction', 0),
                    'max_rate': content.get('max_rate', 0)
                }
                db.save_blending_recipe(recipe_data)
                
        elif data_type == 'routes':
            route_id = content.get('id')
            if route_id:
                route_data = {
                    'id': route_id,
                    'origin': content.get('origin', ''),
                    'destination': content.get('destination', ''),
                    'time_travel': content.get('time_travel', 0)
                }
                db.save_route(route_data)
        else:
            return jsonify({"success": False, "error": f"Unknown data type: {data_type}"}), 400
        
        return jsonify({"success": True})
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

# ==============================================================================
# SCHEDULER ENDPOINTS
# ==============================================================================

@app.route('/api/scheduler/run', methods=['POST'])
def run_scheduler():
    """Run the scheduling algorithm with database data"""
    try:
        # Parse request data
        data = request.json
        days = data.get('days', 30)
        
        # Load required data from database
        tanks = load_tanks()
        recipes = load_recipes()
        crudes = load_crudes()
        vessels = load_vessels()
        
        # Validate required data
        if not tanks:
            return jsonify({"success": False, "error": "No tanks available"}), 400
        if not recipes:
            return jsonify({"success": False, "error": "No blending recipes available"}), 400
        if not crudes:
            return jsonify({"success": False, "error": "No crude data available"}), 400
        
        # Create and run scheduler
        max_processing_rate = 100
        
        scheduler = Scheduler(
            tanks=tanks,
            blending_recipes=recipes,
            vessels=vessels,
            crude_data=crudes,
            max_processing_rate=max_processing_rate
        )
        
        print(f"Running scheduler for {days} days")
        result = scheduler.run(days, save_output=True)
        
        # Load the standardized JSON file
        json_file = os.path.join(os.path.dirname(__file__), "output", "schedule_results.json")
        
        try:
            with open(json_file, 'r') as f:
                schedule_data = json.load(f)
                
            return jsonify({
                "success": True,
                "days": days,
                "daily_plans": schedule_data.get("daily_plans", [])
            })
            
        except Exception as file_error:
            return jsonify({"success": False, "error": f"Failed to load schedule results: {str(file_error)}"}), 500
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/vessel-optimizer/optimize', methods=['POST'])
def optimize_vessels():
    """Optimize vessel scheduling based on feedstock requirements"""
    try:
        data = request.json
        horizon_days = data.get('horizon_days', 60)
        
        # Load data from database
        requirements = load_feedstock_requirements()
        routes = load_routes()
        
        # For vessel types, we need to load from static data or database
        # This might need to be migrated to database as well
        vessel_types_file = os.path.join(os.path.dirname(__file__), "static_data", "vessel_types.json")
        try:
            with open(vessel_types_file, 'r') as f:
                vessel_types = json.load(f)
        except:
            vessel_types = []
        
        # Create vessel optimizer
        vessel_optimizer = VesselOptimizer(
            feedstock_requirements=requirements,
            routes=routes,
            vessel_types=vessel_types
        )
        
        # Run optimization
        vessels = vessel_optimizer.optimize(horizon_days=horizon_days)
        
        # Save vessels to database
        for vessel in vessels:
            vessel_data = {
                'vessel_id': vessel.vessel_id,
                'capacity': vessel.capacity,
                'cost': vessel.cost,
                'arrival_day': vessel.arrival_day,
                'days_held': vessel.days_held
            }
            db.save_vessel(vessel_data)
            
            # Save cargo
            for cargo in vessel.cargo:
                cargo_data = {
                    'vessel_id': vessel.vessel_id,
                    'grade': cargo.grade,
                    'volume': cargo.volume,
                    'origin': cargo.origin,
                    'loading_start_day': next(iter(cargo.ldr.keys())) if cargo.ldr else 0,
                    'loading_end_day': next(iter(cargo.ldr.values())) if cargo.ldr else 0
                }
                db.add_vessel_cargo(cargo_data)
        
        # Convert vessels to JSON for response
        vessels_json = convert_vessels_to_json(vessels)
        
        return jsonify({
            "success": True,
            "vessels": vessels_json
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/save-schedule', methods=['POST'])
def save_schedule():
    """Save modified schedule data"""
    try:
        data = request.json
        schedule = data.get('schedule', [])
        
        if not schedule:
            return jsonify({"success": False, "error": "No schedule data provided"}), 400
        
        # Save to schedule_results.json (keep file-based for schedule output)
        output_path = os.path.join(os.path.dirname(__file__), "output", "schedule_results.json")
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        with open(output_path, 'w') as f:
            json.dump({"daily_plans": schedule}, f, indent=2)
        
        return jsonify({"success": True})
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

# ==============================================================================
# DATABASE MANAGEMENT ENDPOINTS
# ==============================================================================

@app.route('/api/database/status', methods=['GET'])
def get_database_status():
    """Get database status and migration information"""
    try:
        is_migrated = os.path.exists(MIGRATION_FLAG)
        
        # Get table counts
        table_counts = {}
        if is_migrated:
            table_counts = {
                'tanks': len(db.get_all_tanks()),
                'vessels': len(db.get_all_vessels()),
                'crudes': len(db.get_all_crudes()),
                'recipes': len(db.get_all_blending_recipes()),
                'routes': len(db.get_all_routes()),
                'feedstock_requirements': len(db.get_all_feedstock_requirements()),
            }
        
        return jsonify({
            "success": True,
            "migration_completed": is_migrated,
            "database_path": DB_PATH,
            "database_exists": os.path.exists(DB_PATH),
            "table_counts": table_counts
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route('/api/database/migrate', methods=['POST'])
def migrate_database():
    """Run database migration from JSON files"""
    try:
        # Import and run migration
        from database.migration import DatabaseMigration
        
        migrator = DatabaseMigration(DB_PATH)
        success = migrator.migrate_all_data()
        
        if success:
            # Create migration flag
            with open(MIGRATION_FLAG, 'w') as f:
                f.write(f"Migration completed at {datetime.now()}")
            
            return jsonify({
                "success": True,
                "message": "Database migration completed successfully"
            })
        else:
            return jsonify({
                "success": False,
                "error": "Migration failed"
            }), 500
            
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)
