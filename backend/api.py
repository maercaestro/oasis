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
    Tank, Vessel, Crude, Route, FeedstockParcel, FeedstockRequirement, DailyPlan
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
VESSEL_ROUTES_FILE = os.path.join(DYNAMIC_DATA_DIR, "vessel_routes.json")

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

def load_routes():
    """Load route data and convert to Route objects"""
    routes_data = load_data_file(ROUTES_FILE)
    routes = {}
    
    for route_id, route_info in routes_data.items():
        routes[route_id] = Route(
            origin=route_info.get("from", ""),
            destination=route_info.get("to", ""),
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
            
            # Create vessel object without route parameter
            vessel = Vessel(
                vessel_id=vessel_id,
                arrival_day=int(vessel_info.get("arrival_day", 0)),
                capacity=float(vessel_info.get("capacity", 0)),
                cost=float(vessel_info.get("cost", 0)),
                cargo=cargo,
                days_held=int(vessel_info.get("days_held", 0))
            )
            
            # Set route attribute separately
            if "route" in vessel_info:
                vessel.route = vessel_info["route"]
                
            vessels.append(vessel)
            
    # ...handle the else case if needed...
    
    return vessels

def load_vessel_types() -> List[Dict]:
    """Load vessel types data"""
    return load_data_file(VESSEL_TYPES_FILE)

def load_feedstock_requirements() -> List[FeedstockRequirement]:
    """Load feedstock requirements data and convert to FeedstockRequirement objects"""
    req_data = load_data_file(os.path.join(DYNAMIC_DATA_DIR, "feedstock_requirements.json"))
    requirements = []
    
    # Handle both array and object formats
    if isinstance(req_data, list):
        # It's an array format
        for req_info in req_data:
            # Skip entries with missing required fields
            if not all(k in req_info for k in ["grade", "volume", "origin"]):
                print(f"Warning: Skipping incomplete requirement: {req_info}")
                continue
                
            # Extract allowed_ldr
            allowed_ldr = {}
            if "allowed_ldr" in req_info and isinstance(req_info["allowed_ldr"], dict):
                allowed_ldr = {
                    int(k) if isinstance(k, str) else k: 
                    int(v) if isinstance(v, str) else v 
                    for k, v in req_info["allowed_ldr"].items()
                }
            elif not allowed_ldr:  # Provide default if missing
                allowed_ldr = {1: 10}  # Default loading window
            
            requirements.append(FeedstockRequirement(
                grade=req_info.get("grade", ""),
                volume=float(req_info.get("volume", 0)),
                origin=req_info.get("origin", ""),
                allowed_ldr=allowed_ldr,
                required_arrival_by=int(req_info.get("required_arrival_by", 30))
            ))
    else:
        # Original dictionary format handling (keep as is)
        for req_id, req_info in req_data.items():
            # Similar validation and handling...
            pass  # Placeholder for actual logic

    return requirements

def load_feedstock_parcels():
    """Load feedstock parcels from vessels.json"""
    vessels_data = load_data_file(VESSELS_FILE)
    parcels = []
    
    # Add at the beginning of load_feedstock_parcels function
    print("DEBUG: Vessel data keys:", list(vessels_data.keys()))
    for vessel_id, vessel_info in vessels_data.items():
        if not isinstance(vessel_info, dict):
            print(f"DEBUG: Invalid vessel format: {vessel_id} = {vessel_info} (type: {type(vessel_info)})")
            
        # Add this safety check
        if not isinstance(vessel_info, dict):
            print(f"Warning: Vessel {vessel_id} has invalid format: {type(vessel_info)}. Skipping.")
            continue
            
        for cargo in vessel_info.get("cargo", []):
            # Rest of your code remains the same
            parcel_id = f"{vessel_id}_{cargo.get('grade', '')}_{cargo.get('volume', 0)}"
            parcels.append(FeedstockParcel(
                grade=cargo.get("grade", ""),
                volume=cargo.get("volume", 0),
                origin=cargo.get("origin", ""),
                ldr={
                    int(cargo.get("loading_start_day", 0)): 
                    int(cargo.get("loading_end_day", 0))
                },
                vessel_id=vessel_id
            ))
    
    return parcels

def load_plant():
    """Load plant configuration data"""
    return load_data_file(os.path.join(STATIC_DATA_DIR, "plant.json"))

def load_routes_as_objects() -> Dict[str, Route]:
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

def load_vessel_routes():
    """Load vessel routes data tracking day-by-day vessel locations"""
    return load_data_file(VESSEL_ROUTES_FILE)

# Helper function for converting Route objects to dictionaries
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

# Helper functions for converting objects back to JSON-serializable format
def convert_daily_plans_to_json(daily_plans) -> List[Dict]:
    """Convert daily plans to JSON-serializable format"""
    result = []
    
    # Validate input type
    if not daily_plans:
        print("Warning: No daily plans to convert")
        return []
    
    # Handle different formats of daily_plans
    if isinstance(daily_plans, int):
        print(f"Error: Expected daily plans object but got integer: {daily_plans}")
        return [{"error": f"Invalid data format: {daily_plans}"}]
        
    # If it's a dictionary (keyed by day), convert to list
    if isinstance(daily_plans, dict):
        print(f"Converting daily_plans from dict to list format")
        plans_list = []
        for day in sorted(daily_plans.keys()):
            plans_list.append(daily_plans[day])
        daily_plans = plans_list
    
    # Process each plan
    for plan_index, plan in enumerate(daily_plans):
        try:
            # Check if plan is valid
            if not hasattr(plan, 'tanks'):
                print(f"Error: Plan at index {plan_index} is not a valid DailyPlan object: {type(plan)}")
                result.append({
                    "day": plan_index,
                    "error": f"Invalid plan format: {type(plan).__name__}",
                    "data": str(plan)[:100]  # Include truncated data for debugging
                })
                continue
            
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
        except Exception as e:
            print(f"Error converting plan at index {plan_index}: {e}")
            # Add error info to result instead of failing
            result.append({
                "day": plan_index,
                "error": f"Conversion error: {str(e)}",
                "type": str(type(plan))
            })
    
    return result

# Alias for backward compatibility
convert_plans_to_json = convert_daily_plans_to_json

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
        
        # Handle vessel route - check if it's a list of dictionaries or Route objects
        route_json = []
        if hasattr(vessel, "route"):
            if vessel.route and len(vessel.route) > 0:  # Make sure route has items
                try:
                    # First item is a dict with expected keys
                    if isinstance(vessel.route[0], dict):
                        # Check if it has standard route keys
                        if all(key in vessel.route[0] for key in ['from', 'to']):
                            route_json = vessel.route  # Already in the right format
                        # It's a different dictionary format, convert it
                        else:
                            for route in vessel.route:
                                route_dict = {}
                                # Copy all keys to ensure we don't miss anything
                                for key, value in route.items():
                                    route_dict[key] = value
                                route_json.append(route_dict)
                    
                    # It might be a Route object
                    elif hasattr(vessel.route[0], 'origin'):
                        for route in vessel.route:
                            route_json.append({
                                "from": route.origin,
                                "to": route.destination,
                                "day": getattr(route, "day", 0),
                                "travel_days": route.time_travel
                            })
                    # Unknown format - create empty route to avoid errors
                    else:
                        print(f"Warning: Unknown route format in vessel {vessel.vessel_id}")
                except Exception as e:
                    print(f"Error processing route for vessel {vessel.vessel_id}: {e}")
                    # In case of error, return empty route
        
        vessel_json = {
            "vessel_id": vessel.vessel_id,
            "arrival_day": vessel.arrival_day,
            "capacity": vessel.capacity,
            "cost": vessel.cost,
            "cargo": cargo_json,
            "days_held": vessel.days_held,
            "route": route_json
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
# Update the get_data function to use routes_to_dict
@app.route('/api/data', methods=['GET'])
def get_data():
    """Get all configuration data"""
    vessels = load_vessels()
    
    # Load routes and convert to dictionaries for JSON serialization
    routes = load_routes()
    routes_dict = routes_to_dict(routes)
    
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
        }
        
        # Add route if it exists
        if hasattr(vessel, 'route'):
            vessel_data["route"] = vessel.route
        else:
            vessel_data["route"] = []
            
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
        "tanks": load_tanks(),
        "recipes": load_recipes(),
        "crudes": load_crudes(),
        "routes": routes_dict,  # Use dictionaries instead of Route objects
        "vessels": vessels_dict,
        "vessel_routes": load_vessel_routes(),
        "vessel_types": load_vessel_types(),
        "plants": load_plant(),
        "feedstock_requirements": load_feedstock_requirements(),
        "feedstock_parcels": load_feedstock_parcels(),
        "schedule": schedule_data,
    })

@app.route('/api/scheduler/run', methods=['POST'])
def run_scheduler():
    try:
        # Parse request data
        data = request.json
        days = data.get('days', 30)
        
        # Load required data
        tanks = load_tanks()
        recipes = load_recipes()
        crudes = load_crudes()
        
        # Load vessels with proper conversion to FeedstockParcel objects
        vessels_data = load_data_file(VESSELS_FILE)
        vessels = []

        if isinstance(vessels_data, dict):
            for vessel_id, vessel_info in vessels_data.items():
                # Add this safety check
                if not isinstance(vessel_info, dict):
                    print(f"Warning: Vessel {vessel_id} has invalid format: {type(vessel_info)}. Skipping.")
                    continue
                    
                # Process each cargo item into FeedstockParcel objects
                cargo_objects = []
                for cargo_item in vessel_info.get("cargo", []):
                    if isinstance(cargo_item, dict) and "grade" in cargo_item and "volume" in cargo_item:
                        # Convert loading days to ldr dict format expected by FeedstockParcel
                        start_day = cargo_item.get("loading_start_day", 0)
                        end_day = cargo_item.get("loading_end_day", 0)
                        ldr = {start_day: end_day} if start_day and end_day else {0: 0}
                        
                        cargo_objects.append(FeedstockParcel(
                            grade=cargo_item["grade"],
                            volume=cargo_item["volume"],
                            origin=cargo_item.get("origin", "Unknown"),
                            ldr=ldr,
                            vessel_id=vessel_id
                        ))
                
                # Create the vessel with the correct parameters
                vessels.append(Vessel(
                    vessel_id=vessel_id,
                    arrival_day=vessel_info.get("arrival_day", 0),
                    cost=vessel_info.get("cost", 0),
                    capacity=vessel_info.get("capacity", 0),
                    cargo=cargo_objects,
                    days_held=vessel_info.get("days_held", 0)
                ))
        
        # Validate required data
        if not tanks:
            return jsonify({"success": False, "error": "No tanks available"}), 400
        if not recipes:
            return jsonify({"success": False, "error": "No blending recipes available"}), 400
        if not crudes:
            return jsonify({"success": False, "error": "No crude data available"}), 400
        
        # Add compatibility checks for vessel grades and crudes
        print("Available crude grades in crude data:", list(crudes.keys()))
        
        vessel_grades = set()
        for vessel in vessels:
            for cargo in vessel.cargo:
                vessel_grades.add(cargo.grade)
        
        print(f"Grades from vessels: {vessel_grades}")
        print(f"Crude data grades: {set(crudes.keys())}")
        missing = vessel_grades - set(crudes.keys())
        if missing:
            print(f"WARNING: Vessels contain grades that are not in crudes.json: {missing}")
        
        # Check which recipes can use the available grades
        print("\nCompatible recipes for vessel cargo:")
        for recipe in recipes:
            primary_in_crudes = recipe.primary_grade in crudes
            secondary_in_crudes = not recipe.secondary_grade or recipe.secondary_grade in crudes
            
            primary_in_cargo = recipe.primary_grade in vessel_grades
            secondary_in_cargo = not recipe.secondary_grade or recipe.secondary_grade in vessel_grades
            
            if primary_in_crudes and secondary_in_crudes and primary_in_cargo and secondary_in_cargo:
                print(f"  ✅ Recipe {recipe.name} ({recipe.primary_grade}/{recipe.secondary_grade}) is compatible")
            else:
                print(f"  ❌ Recipe {recipe.name} ({recipe.primary_grade}/{recipe.secondary_grade}) is NOT compatible")
        
        # Add this section before creating the scheduler
        print("\nInitial inventory from tanks:")
        initial_inventory = {}
        total_initial = 0
        for tank_name, tank in tanks.items():
            for content_item in tank.content:
                for grade, amount in content_item.items():
                    if grade in initial_inventory:
                        initial_inventory[grade] += amount
                    else:
                        initial_inventory[grade] = amount
                    total_initial += amount
        
        print(f"Total initial inventory: {total_initial}")
        print(f"By grade: {initial_inventory}")
        
        # Create and run scheduler
        max_processing_rate = 100  # Use the same value as in test_scheduler.py
        
        scheduler = Scheduler(
            tanks=tanks,
            blending_recipes=recipes,
            vessels=vessels,
            crude_data=crudes,
            max_processing_rate=max_processing_rate
        )
        
        # Run scheduler with save_output=True
        print(f"Running scheduler for {days} days")
        result = scheduler.run(days, save_output=True)
        
        # Load the standardized JSON file
        json_file = os.path.join(os.path.dirname(__file__), "output", "schedule_results.json")
        print(f"Loading schedule data from {json_file}")
        
        try:
            with open(json_file, 'r') as f:
                schedule_data = json.load(f)
                
            return jsonify({
                "success": True,
                "days": days,
                "daily_plans": schedule_data.get("daily_plans", [])
            })
            
        except Exception as file_error:
            print(f"Error loading JSON file: {file_error}")
            return jsonify({"success": False, "error": f"Failed to load schedule results: {str(file_error)}"}), 500
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/optimizer/optimize', methods=['POST'])
def optimize_schedule():
    """
    Optimize a schedule using the SchedulerOptimizer.
    Accepts a schedule and returns an optimized version based on objective.
    """
    try:
        # Parse request data
        data = request.json
        days = data.get('days', 30)
        schedule_data = data.get('schedule', [])
        objective = data.get('objective', 'margin')
        
        print(f"Optimizer Request: days={days}, objective={objective}")
        print(f"Schedule data: {len(schedule_data)} days")
        
        # Check if we have schedule data
        if not schedule_data:
            return jsonify({
                'success': False,
                'error': 'No schedule data provided. Run the scheduler first.'
            }, 400)
        
        # Load required data
        recipes = load_recipes()
        crudes = load_crudes()
        
        # Import the DailyPlan class explicitly here if needed
        from scheduler.models import DailyPlan
        
        # Convert JSON schedule data to DailyPlan objects
        daily_plans = []
        for day_data in schedule_data:
            try:
                # Create a simplified DailyPlan from the JSON data
                daily_plan = DailyPlan(
                    day=day_data.get('day', 0),
                    processing_rates=day_data.get('processing_rates', {}),
                    blending_details=day_data.get('blending_details', []),
                    inventory=day_data.get('inventory', 0),
                    inventory_by_grade=day_data.get('inventory_by_grade', {}),
                    tanks={}  # We may not need full tank objects for optimization
                )
                daily_plans.append(daily_plan)
            except Exception as e:
                print(f"Error converting day {day_data.get('day', 'unknown')}: {str(e)}")
        
        # Ensure we have daily plans
        if not daily_plans:
            return jsonify({
                'success': False,
                'error': 'Failed to convert schedule data to daily plans'
            }, 400)
        
        # Load vessels (required for optimization)
        vessels_data = load_data_file(VESSELS_FILE)
        vessels = []

        if isinstance(vessels_data, dict):
            for vessel_id, vessel_info in vessels_data.items():
                try:
                    # Process each cargo item into FeedstockParcel objects
                    cargo_objects = []
                    for cargo_item in vessel_info.get("cargo", []):
                        if isinstance(cargo_item, dict) and "grade" in cargo_item and "volume" in cargo_item:
                            # Convert loading days to ldr dict format expected by FeedstockParcel
                            start_day = cargo_item.get("loading_start_day", 0)
                            end_day = cargo_item.get("loading_end_day", 0)
                            ldr = {start_day: end_day} if start_day and end_day else {0: 0}
                            
                            cargo_objects.append(FeedstockParcel(
                                grade=cargo_item["grade"],
                                volume=cargo_item["volume"],
                                origin=cargo_item.get("origin", "Unknown"),
                                ldr=ldr,
                                vessel_id=vessel_id
                            ))
                    
                    # Create the vessel with the correct parameters
                    vessels.append(Vessel(
                        vessel_id=vessel_id,
                        arrival_day=vessel_info.get("arrival_day", 0),
                        cost=vessel_info.get("cost", 0),
                        capacity=vessel_info.get("capacity", 0),
                        cargo=cargo_objects,
                        days_held=vessel_info.get("days_held", 0)
                    ))
                except Exception as e:
                    print(f"Error converting vessel {vessel_id}: {str(e)}")
        
        # Initialize optimizer
        optimizer = SchedulerOptimizer(
            blending_recipes=recipes,
            crude_data=crudes,
            max_processing_rate=1000  # Use an appropriate default or get from data
        )
        
        # Run optimization based on objective
        try:
            if objective == 'throughput':
                print("Running throughput optimization")
                optimized_schedule = optimizer.optimize_throughput(daily_plans, vessels)
            else:
                print("Running margin optimization")
                optimized_schedule = optimizer.optimize_margin(daily_plans, vessels)
                
            # Convert the optimized schedule back to JSON
            optimized_json = []
            for plan in optimized_schedule:
                plan_dict = {
                    'day': plan.day,
                    'processing_rates': plan.processing_rates,
                    'blending_details': plan.blending_details,
                    'inventory': plan.inventory,
                    'inventory_by_grade': plan.inventory_by_grade
                }
                optimized_json.append(plan_dict)
                
            # Calculate total margin improvement
            total_margin = sum(day.daily_margin for day in optimized_schedule)
            original_margin = sum(day.daily_margin for day in daily_plans if hasattr(day, 'daily_margin'))

            # Add to response
            return jsonify({
                'success': True,
                'schedule': optimized_json,
                'message': f'Optimized schedule for {objective}',
                'days_processed': len(optimized_json),
                'metrics': {
                    'total_margin': total_margin,
                    'original_margin': original_margin,
                    'margin_improvement_percent': ((total_margin - original_margin) / original_margin * 100) if original_margin > 0 else 0
                }
            })
            
        except Exception as e:
            error_message = f"Optimization error: {str(e)}"
            print(error_message)
            import traceback
            print(traceback.format_exc())
            return jsonify({
                'success': False,
                'error': error_message
            }, 500)
            
    except Exception as e:
        error_message = f"API error: {str(e)}"
        print(error_message)
        import traceback
        print(traceback.format_exc())
        return jsonify({
            'success': False, 
            'error': error_message
        }, 500)

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
                origin="Sabah",
                allowed_ldr={15: 25},
                required_arrival_by=30
            ),
            FeedstockRequirement(
                grade="CrudeB",
                volume=300,
                origin="Sarawak",
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
        print(f"Received vessel optimization request: {data}")
        
        # Get parameters
        requirements_data = data.get('requirements', [])
        horizon_days = data.get('horizon_days', 60)
        use_file_requirements = data.get('use_file_requirements', False)
        
        print(f"Optimizing vessels with horizon: {horizon_days}, use_file_requirements: {use_file_requirements}")
        
        # Load data
        routes = load_routes()
        vessel_types = load_vessel_types()
        
        print(f"Loaded {len(routes)} routes and {len(vessel_types)} vessel types")
        
        # Either use requirements from request or load from file
        if use_file_requirements:
            requirements = load_feedstock_requirements()
            print(f"Loaded {len(requirements)} requirements from file")
            
            # DEBUG: Print detailed requirements info
            print("\n=== DETAILED REQUIREMENTS DATA ===")
            for i, req in enumerate(requirements):
                print(f"Req {i}: {req.grade} from {req.origin}, volume: {req.volume}")
                print(f"  - allowed_ldr: {req.allowed_ldr}")
                print(f"  - required_arrival_by: {req.required_arrival_by}")
        else:
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
            print(f"Created {len(requirements)} requirements from request")
        
        # DEBUG: Validate vessel type capacities
        print("\n=== VESSEL TYPE CAPACITIES ===")
        for i, vtype in enumerate(vessel_types):
            print(f"Vessel type {i}: {vtype.get('name', 'Unknown')} - Capacity: {vtype.get('capacity', 0)}")
        
        # Check requirement volumes vs vessel capacities
        max_capacity = max(v.get('capacity', 0) for v in vessel_types) if vessel_types else 0
        print(f"\nMax vessel capacity: {max_capacity}")
        
        oversize_reqs = [r for r in requirements if r.volume > max_capacity]
        if oversize_reqs:
            print(f"WARNING: {len(oversize_reqs)} requirements have volumes larger than max vessel capacity:")
            for r in oversize_reqs:
                print(f"  - {r.grade}: {r.volume} (max capacity: {max_capacity})")
        
        # Create vessel optimizer
        vessel_optimizer = VesselOptimizer(
            feedstock_requirements=requirements,
            routes=routes,
            vessel_types=vessel_types
        )
        
        print(f"Starting vessel optimization with {len(requirements)} requirements...")
        print(f"Network will include {len(vessel_optimizer.locations)} locations: {vessel_optimizer.locations}")
        
        # Run optimization with debug info
        try:
            vessels = vessel_optimizer.optimize(horizon_days=horizon_days)
            print(f"Optimization complete. Created {len(vessels)} vessels")
            
            # Summarize vessel plan
            total_volume = sum(sum(c.volume for c in v.cargo) for v in vessels)
            total_req_volume = sum(req.volume for req in requirements)
            print(f"Total scheduled volume: {total_volume} of {total_req_volume} required ({total_volume/total_req_volume*100:.1f}% fulfilled)")
            
            # Save results
            vessels = vessel_optimizer.optimize_and_save(horizon_days=horizon_days)
        except Exception as e:
            print(f"Error during vessel optimization: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({
                "success": False, 
                "error": f"Optimization failed: {str(e)}"
            }), 500
    except Exception as e:
        print(f"Optimization error: {str(e)}")
        raise
    
    # Convert vessels to JSON
    vessels_json = convert_vessels_to_json(vessels)
    
    # Save to vessels.json
    vessels_dict = {}
    for i, vessel in enumerate(vessels):
        vessel_id = vessel.vessel_id if vessel.vessel_id else f"Vessel_{i:03d}"
        print(f"Processing vessel {vessel_id} for JSON...")
        
        # Process vessel cargo
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
        
        # Process vessel routes - properly serialize to dict
        route_json = []
        if hasattr(vessel, "route") and vessel.route:
            print(f"Vessel {vessel_id} has route data, serializing...")
            for segment in vessel.route:
                if isinstance(segment, dict):
                    # It's already a dictionary
                    route_json.append(segment)
                elif hasattr(segment, 'origin') and hasattr(segment, 'destination'):
                    # It's a Route object
                    route_json.append({
                        "from": segment.origin,
                        "to": segment.destination,
                        "day": getattr(segment, "day", vessel.arrival_day),
                        "travel_days": segment.time_travel
                    })
                else:
                    print(f"Warning: Unknown route segment format in vessel {vessel.vessel_id}: {type(segment)}")
                    
            print(f"Successfully serialized {len(route_json)} route segments")
        
        # Create the vessel dictionary with properly serialized routes
        vessels_dict[vessel_id] = {
            "vessel_id": vessel_id,
            "arrival_day": vessel.arrival_day,
            "capacity": vessel.capacity,
            "cost": vessel.cost,
            "days_held": vessel.days_held,
            "cargo": cargo_json,
            # Use the properly serialized route_json
            "route": route_json
        }
    
    # Save to file
    print(f"Saving {len(vessels_dict)} vessels to {VESSELS_FILE}")
    with open(VESSELS_FILE, 'w') as f:
        json.dump(vessels_dict, f, indent=2)
        
    # Update the cache
    data_cache[VESSELS_FILE] = vessels_dict
    
    print("Vessel optimization completed successfully")
    return jsonify({
        "success": True,
        "vessels": vessels_json
    })
        


@app.route('/api/save-data', methods=['POST'])
def save_data():
    """Save updated data to JSON files"""
    try:
        data = request.json
        data_type = data.get('type')
        content = data.get('content')
        
        # Determine if static or dynamic data
        if data_type in ['tanks', 'vessels', 'vessel_routes', 'feedstock_parcels', 'feedstock_requirements']:
            # Dynamic data
            if data_type == 'tanks':
                file_path = TANKS_FILE
                tank_name = content.get('name')
                if tank_name:
                    current_tanks = load_tanks()
                    current_tanks[tank_name] = content
            elif data_type == 'vessels':
                file_path = VESSELS_FILE
                vessel_id = content.get('vessel_id')
            elif data_type == 'vessel_routes':
                file_path = VESSEL_ROUTES_FILE
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

@app.route('/api/save-schedule', methods=['POST'])
def save_schedule():
    """Save modified schedule data"""
    try:
        data = request.json
        schedule = data.get('schedule', [])
        
        if not schedule:
            return jsonify({"success": False, "error": "No schedule data provided"}), 400
        
        # Save to schedule_results.json
        output_path = os.path.join(os.path.dirname(__file__), "output", "schedule_results.json")
        
        with open(output_path, 'w') as f:
            json.dump({"daily_plans": schedule}, f, indent=2)
        
        return jsonify({"success": True, "message": "Schedule saved successfully"})
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

if __name__ == '__main__':
    # Create data directories if they don't exist
    os.makedirs(STATIC_DATA_DIR, exist_ok=True)
    os.makedirs(DYNAMIC_DATA_DIR, exist_ok=True)
    
    # Run the Flask app
    app.run(debug=True, host='0.0.0.0', port=5001)