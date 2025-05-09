"""
OASIS API Service
This module provides a Flask API to interact with the OASIS system functionalities.
Exposes endpoints for scheduling, vessel optimization, and schedule optimization.

Copyright (c) by Abu Huzaifah Bidin with help from Github Copilot
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import json
import os
from typing import Dict, List, Any, Optional

from scheduler import (
    Scheduler, VesselOptimizer, SchedulerOptimizer, 
    Tank, Vessel, Crude, Route, FeedstockParcel, FeedstockRequirement
)

from scheduler.models import BlendingRecipe
app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})  # This enables CORS for all /api/ routes

# Data paths
STATIC_DATA_DIR = os.path.join(os.path.dirname(__file__), "static_data")
DYNAMIC_DATA_DIR = os.path.join(os.path.dirname(__file__), "dynamic_data")
TANKS_FILE = os.path.join(DYNAMIC_DATA_DIR, "tanks.json")
RECIPES_FILE = os.path.join(STATIC_DATA_DIR, "recipes.json")
CRUDES_FILE = os.path.join(STATIC_DATA_DIR, "crudes.json")
ROUTES_FILE = os.path.join(STATIC_DATA_DIR, "routes.json")
VESSELS_FILE = os.path.join(DYNAMIC_DATA_DIR, "vessels.json")
VESSEL_TYPES_FILE = os.path.join(STATIC_DATA_DIR, "vessel_types.json")

# Global cache for loaded data
data_cache = {}

# Data loader functions
def load_data_file(file_path: str) -> Any:
    """Load data from a JSON file with caching"""
    if file_path in data_cache:
        return data_cache[file_path]
    
    try:
        with open(file_path, 'r') as f:
            data = json.load(f)
            data_cache[file_path] = data
            return data
    except FileNotFoundError:
        print(f"Warning: Data file not found: {file_path}")
        return {}
    except json.JSONDecodeError:
        print(f"Error: Invalid JSON in file: {file_path}")
        return {}

def load_tanks() -> Dict[str, Tank]:
    """Load tank data and convert to Tank objects"""
    tanks_data = load_data_file(TANKS_FILE)
    tanks = {}
    
    for tank_id, tank_info in tanks_data.items():
        tanks[tank_id] = Tank(
            name=tank_id,
            capacity=tank_info.get("capacity", 0),
            content=tank_info.get("content", [])
        )
    
    return tanks

def load_recipes():
    """Load recipe data and convert to BlendingRecipe objects"""
    recipes_data = load_data_file(RECIPES_FILE)
    recipes = []
    
    for recipe_id, recipe_info in recipes_data.items():
        recipes.append(BlendingRecipe(
            name=recipe_id,
            primary_grade=recipe_info.get("primary_grade", ""),
            secondary_grade=recipe_info.get("secondary_grade", ""),
            primary_fraction=recipe_info.get("primary_fraction", 0),
            max_rate=recipe_info.get("max_rate", 0)
        ))
    
    return recipes

def load_crudes() -> Dict[str, Crude]:
    """Load crude data and convert to Crude objects"""
    crudes_data = load_data_file(CRUDES_FILE)
    crudes = {}
    
    for crude_id, crude_info in crudes_data.items():
        crudes[crude_id] = Crude(
            name=crude_id,
            margin=crude_info.get("margin", 0),
            origin=crude_info.get("origin", "")
        )
    
    return crudes

def load_routes() -> Dict[str, Route]:
    """Load route data and convert to Route objects"""
    routes_data = load_data_file(ROUTES_FILE)
    routes = {}
    
    for route_id, route_info in routes_data.items():
        routes[route_id] = Route(
            origin=route_info.get("origin", ""),
            destination=route_info.get("destination", ""),
            time_travel=route_info.get("time_travel", 0)
        )
    
    return routes

def load_vessels() -> List[Vessel]:
    """Load vessel data and convert to Vessel objects"""
    vessels_data = load_data_file(VESSELS_FILE)
    vessels = []
    
    # Check if data is a dictionary of vessels or a single vessel
    if isinstance(vessels_data, dict) and all(isinstance(value, dict) for value in vessels_data.values()):
        # It's a dictionary of vessels - iterate through each vessel
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
            
            vessels.append(Vessel(
                vessel_id=vessel_id,
                arrival_day=int(vessel_info.get("arrival_day", 0)),
                capacity=float(vessel_info.get("capacity", 0)),
                cost=float(vessel_info.get("cost", 0)),
                cargo=cargo,
                days_held=int(vessel_info.get("days_held", 0))
            ))
    else:
        # Try to handle the file as a list of vessels or a single vessel object
        vessel_list = vessels_data if isinstance(vessels_data, list) else [vessels_data]
        
        for vessel_info in vessel_list:
            vessel_id = vessel_info.get("vessel_id", f"Unknown_Vessel_{len(vessels)}")
            
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
            
            vessels.append(Vessel(
                vessel_id=vessel_id,
                arrival_day=int(vessel_info.get("arrival_day", 0)),
                capacity=float(vessel_info.get("capacity", 0)),
                cost=float(vessel_info.get("cost", 0)),
                cargo=cargo,
                days_held=int(vessel_info.get("days_held", 0))
            ))
    
    return vessels

def load_vessel_types() -> List[Dict]:
    """Load vessel types data"""
    return load_data_file(VESSEL_TYPES_FILE)

def load_feedstock_requirements() -> List[FeedstockRequirement]:
    """Load feedstock requirements data and convert to FeedstockRequirement objects"""
    req_data = load_data_file(os.path.join(DYNAMIC_DATA_DIR, "feedstock_requirements.json"))
    requirements = []
    
    for req_id, req_info in req_data.items():
        requirements.append(FeedstockRequirement(
            grade=req_info.get("grade", ""),
            volume=req_info.get("volume", 0),
            origin=req_info.get("origin", ""),
            allowed_ldr={
                req_info.get("loading_start_day", 0): 
                req_info.get("loading_end_day", 0)
            },
            required_arrival_by=req_info.get("required_arrival_by", 0)
        ))
    
    return requirements

def load_feedstock_parcels() -> List[FeedstockParcel]:
    """Load feedstock parcel data and convert to FeedstockParcel objects"""
    parcel_data = load_data_file(os.path.join(DYNAMIC_DATA_DIR, "feedstock_parcels.json"))
    parcels = []
    
    for parcel_id, parcel_info in parcel_data.items():
        parcels.append(FeedstockParcel(
            grade=parcel_info.get("grade", ""),
            volume=parcel_info.get("volume", 0),
            origin=parcel_info.get("origin", ""),
            ldr={
                parcel_info.get("loading_start_day", 0): 
                parcel_info.get("loading_end_day", 0)
            },
            vessel_id=parcel_info.get("vessel_id")
        ))
    
    return parcels

def load_plant():
    """Load plant configuration data"""
    return load_data_file(os.path.join(STATIC_DATA_DIR, "plant.json"))

# Helper functions for converting objects back to JSON-serializable format
def convert_daily_plans_to_json(daily_plans) -> List[Dict]:
    """Convert daily plans to JSON-serializable format"""
    result = []
    
    for plan in daily_plans:
        # Convert tank objects to serializable format
        tanks_json = {}
        for tank_name, tank in plan.tanks.items():
            content_json = []
            for content in tank.content:
                content_json.append(content)
            
            tanks_json[tank_name] = {
                "name": tank.name,
                "capacity": tank.capacity,
                "content": content_json
            }
        
        # Create serializable plan
        plan_json = {
            "day": plan.day,
            "processing_rates": plan.processing_rates,
            "inventory": plan.inventory,
            "inventory_by_grade": plan.inventory_by_grade,
            "tanks": tanks_json,
            "blending_details": [
                {
                    "name": recipe.name,
                    "primary_grade": recipe.primary_grade,
                    "secondary_grade": recipe.secondary_grade,
                    "primary_fraction": recipe.primary_fraction,
                    "max_rate": recipe.max_rate
                }
                for recipe in plan.blending_details
            ]
        }
        
        result.append(plan_json)
    
    return result

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
            "days_held": vessel.days_held
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

# API routes
@app.route('/api/data', methods=['GET'])
def get_data():
    """Get all configuration data"""
    vessels = load_vessels()
    
    # Convert vessels list to dictionary format for frontend compatibility
    vessels_dict = {}
    for vessel in vessels:
        vessels_dict[vessel.vessel_id] = {
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
            "days_held": vessel.days_held
        }
    
    return jsonify({
        "tanks": load_tanks(),
        "recipes": load_recipes(),
        "crudes": load_crudes(),
        "routes": load_routes(),
        "vessels": vessels_dict,  # Return as dictionary instead of list
        "vessel_types": load_vessel_types(),
        "plants": load_plant(),  # Add this line
        "feedstock_requirements": load_feedstock_requirements(),
        "feedstock_parcels": load_feedstock_parcels()
    })

@app.route('/api/scheduler/run', methods=['POST'])
def run_scheduler():
    """Run the scheduler with provided parameters"""
    try:
        data = request.json
        
        # Get parameters
        days = data.get('days', 30)
        max_processing_rate = data.get('max_processing_rate', 500)
        
        # Load data
        tanks = load_tanks()
        recipes = load_recipes()
        crudes = load_crudes()
        vessels = load_vessels()
        
        # Create and run scheduler
        scheduler = Scheduler(
            tanks=tanks,
            blending_recipes=recipes,
            crude_data=crudes,
            max_processing_rate=max_processing_rate,
            vessels=vessels
        )
        
        schedule = scheduler.run(days)
        
        # Convert schedule to JSON format
        schedule_json = convert_daily_plans_to_json(schedule)
        
        return jsonify({
            "success": True,
            "schedule": schedule_json
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route('/api/optimizer/optimize', methods=['POST'])
def optimize_schedule():
    """Optimize an existing schedule"""
    try:
        data = request.json
        
        # Get parameters
        schedule_data = data.get('schedule', [])
        objective = data.get('objective', 'margin')  # 'margin' or 'throughput'
        max_processing_rate = data.get('max_processing_rate', 500)
        
        # Load data
        recipes = load_recipes()
        crudes = load_crudes()
        vessels = load_vessels()
        
        # Convert JSON schedule back to DailyPlan objects
        # This is a simplified conversion - you'll need more logic to properly reconstruct DailyPlan objects
        from backend.scheduler.models import DailyPlan
        
        existing_schedule = []
        for day_data in schedule_data:
            # Convert tanks from JSON format
            tanks = {}
            for tank_name, tank_data in day_data.get('tanks', {}).items():
                tanks[tank_name] = Tank(
                    name=tank_name,
                    capacity=tank_data.get('capacity', 0),
                    content=tank_data.get('content', [])
                )
            
            # Create DailyPlan
            plan = DailyPlan(
                day=day_data.get('day', 0),
                processing_rates=day_data.get('processing_rates', {}),
                blending_details=recipes,  # Simplified - would need to match the specific recipes used
                inventory=day_data.get('inventory', 0),
                inventory_by_grade=day_data.get('inventory_by_grade', {}),
                tanks=tanks
            )
            existing_schedule.append(plan)
        
        # Create optimizer
        optimizer = SchedulerOptimizer(
            blending_recipes=recipes,
            crude_data=crudes,
            max_processing_rate=max_processing_rate
        )
        
        # Run optimization
        if objective == 'throughput':
            optimized_schedule = optimizer.optimize_throughput(existing_schedule, vessels)
        else:
            optimized_schedule = optimizer.optimize_margin(existing_schedule, vessels)
        
        # Convert optimized schedule to JSON
        schedule_json = convert_daily_plans_to_json(optimized_schedule)
        
        return jsonify({
            "success": True,
            "schedule": schedule_json
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route('/api/vessel-optimizer/generate-requirements', methods=['POST'])
def generate_requirements():
    """
    Generate feedstock requirements based on an existing schedule
    This is a helper endpoint to identify future crude needs from a schedule
    """
    try:
        data = request.json
        
        # Get parameters
        schedule_data = data.get('schedule', [])
        min_inventory_days = data.get('min_inventory_days', 7)
        
        # Convert schedule to a format where we can analyze future needs
        # This is a simplified version - in practice you'd need a more sophisticated function
        
        # In a real implementation, you'd use a feedstock planner like:
        # from backend.scheduler.feedstock_planner import FeedstockPlanner
        # planner = FeedstockPlanner(min_inventory_days=min_inventory_days)
        # requirements = planner.generate_requirements(schedule, origins)
        
        # For now we'll just generate some dummy requirements
        requirements = [
            FeedstockRequirement(
                grade="CrudeA",
                volume=500,
                origin="Terminal1",
                allowed_ldr={15: 25},
                required_arrival_by=30
            ),
            FeedstockRequirement(
                grade="CrudeB",
                volume=300,
                origin="Terminal2",
                allowed_ldr={10: 20},
                required_arrival_by=25
            )
        ]
        
        # Convert requirements to JSON
        requirements_json = convert_requirements_to_json(requirements)
        
        return jsonify({
            "success": True,
            "requirements": requirements_json
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route('/api/vessel-optimizer/optimize', methods=['POST'])
def optimize_vessels():
    """Optimize vessel scheduling based on feedstock requirements"""
    try:
        data = request.json
        
        # Get parameters
        requirements_data = data.get('requirements', [])
        horizon_days = data.get('horizon_days', 60)
        
        # Load data
        routes = load_routes()
        vessel_types = load_vessel_types()
        
        # Convert requirements from JSON
        requirements = []
        for req_data in requirements_data:
            requirements.append(FeedstockRequirement(
                grade=req_data.get('grade', ''),
                volume=req_data.get('volume', 0),
                origin=req_data.get('origin', ''),
                allowed_ldr={
                    req_data.get('loading_start_day', 0): 
                    req_data.get('loading_end_day', 0)
                },
                required_arrival_by=req_data.get('required_arrival_by', 0)
            ))
        
        # Create vessel optimizer
        vessel_optimizer = VesselOptimizer(
            feedstock_requirements=requirements,
            routes=routes,
            vessel_types=vessel_types
        )
        
        # Run optimization
        vessels = vessel_optimizer.optimize(horizon_days=horizon_days)
        
        # Convert vessels to JSON
        vessels_json = convert_vessels_to_json(vessels)
        
        return jsonify({
            "success": True,
            "vessels": vessels_json
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route('/api/save-data', methods=['POST'])
def save_data():
    """Save updated data to JSON files"""
    try:
        data = request.json
        data_type = data.get('type')
        content = data.get('content')
        
        # Determine if static or dynamic data
        if data_type in ['tanks', 'vessels', 'feedstock_parcels', 'feedstock_requirements']:
            # Dynamic data
            if data_type == 'tanks':
                file_path = TANKS_FILE
            elif data_type == 'vessels':
                file_path = VESSELS_FILE
            elif data_type == 'feedstock_parcels':
                file_path = os.path.join(DYNAMIC_DATA_DIR, "feedstock_parcels.json")
            elif data_type == 'feedstock_requirements':
                file_path = os.path.join(DYNAMIC_DATA_DIR, "feedstock_requirements.json")
        else:
            # Static data
            if data_type == 'recipes':
                file_path = RECIPES_FILE
            elif data_type == 'crudes':
                file_path = CRUDES_FILE
            elif data_type == 'routes':
                file_path = ROUTES_FILE
            elif data_type == 'vessel_types':
                file_path = VESSEL_TYPES_FILE
            elif data_type == 'plants' or data_type == 'plant':
                file_path = os.path.join(STATIC_DATA_DIR, "plant.json")
            else:
                return jsonify({"success": False, "error": f"Unknown data type: {data_type}"}), 400
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        # Write to file
        with open(file_path, 'w') as f:
            json.dump(content, f, indent=2)
        
        # Update cache
        data_cache[file_path] = content
        
        return jsonify({"success": True})
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

if __name__ == '__main__':
    # Create data directories if they don't exist
    os.makedirs(STATIC_DATA_DIR, exist_ok=True)
    os.makedirs(DYNAMIC_DATA_DIR, exist_ok=True)
    
    # Run the Flask app
    app.run(debug=True, host='0.0.0.0', port=5001)