"""
Test script for running the scheduler directly without the API
"""

import os
import json
import sys
from backend.scheduler.scheduler import Scheduler
from backend.scheduler.models import Tank, BlendingRecipe, Crude, Vessel, FeedstockParcel

# Define paths to data files
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DATA_DIR = os.path.join(BASE_DIR, "backend", "static_data")
DYNAMIC_DATA_DIR = os.path.join(BASE_DIR, "backend", "dynamic_data")
OUTPUT_DIR = os.path.join(BASE_DIR, "backend", "output")

def load_json_file(file_path):
    """Load a JSON file and return its contents"""
    try:
        with open(file_path, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Error: File not found: {file_path}")
        return {}
    except json.JSONDecodeError:
        print(f"Error: Invalid JSON in file: {file_path}")
        return {}

def load_tanks():
    """Load tank data from JSON file and convert to Tank objects"""
    tanks_data = load_json_file(os.path.join(DYNAMIC_DATA_DIR, "tanks.json"))
    tanks = {}
    
    for tank_id, tank_info in tanks_data.items():
        tanks[tank_id] = Tank(
            name=tank_id,
            capacity=tank_info.get("capacity", 0),
            content=tank_info.get("content", [])
        )
    
    return tanks

def load_recipes():
    """Load recipe data from JSON file and convert to BlendingRecipe objects"""
    recipes_data = load_json_file(os.path.join(STATIC_DATA_DIR, "recipes.json"))
    recipes = []
    
    for recipe_id, recipe_info in recipes_data.items():
        recipes.append(BlendingRecipe(
            name=recipe_id,
            primary_grade=recipe_info.get("primary_grade", ""),
            secondary_grade=recipe_info.get("secondary_grade", "") or "",  # Convert None to empty string
            primary_fraction=recipe_info.get("primary_fraction", 0),
            max_rate=recipe_info.get("max_rate", 0)
        ))
    
    return recipes

def load_crudes():
    """Load crude data from JSON file and convert to Crude objects"""
    crudes_data = load_json_file(os.path.join(STATIC_DATA_DIR, "crudes.json"))
    crudes = {}
    
    for crude_id, crude_info in crudes_data.items():
        crudes[crude_id] = Crude(
            name=crude_id,
            margin=crude_info.get("margin", 0),
            origin=crude_info.get("origin", "")
        )
    
    return crudes

def load_vessels():
    """Load vessel data from JSON file and convert to Vessel objects"""
    vessels_data = load_json_file(os.path.join(DYNAMIC_DATA_DIR, "vessels.json"))
    vessels = []
    
    if isinstance(vessels_data, dict):
        for vessel_id, vessel_info in vessels_data.items():
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
            
            # Now create the vessel with the correct parameters
            vessels.append(Vessel(
                vessel_id=vessel_id,
                arrival_day=vessel_info.get("arrival_day", 0),
                cost=vessel_info.get("cost", 0),
                capacity=vessel_info.get("capacity", 0),
                cargo=cargo_objects,
                days_held=vessel_info.get("days_held", 0)
            ))
    
    return vessels

def main():
    """Main test function to run the scheduler"""
    # Load necessary data
    tanks = load_tanks()
    recipes = load_recipes()
    crudes = load_crudes()
    vessels = load_vessels()
    
    # Debugging information
    print(f"Loaded {len(tanks)} tanks")
    print(f"Loaded {len(recipes)} recipes")
    print(f"Loaded {len(crudes)} crudes")
    print(f"Loaded {len(vessels)} vessels")
    
    # Print detailed recipe information for debugging
    print("\nRecipes:")
    for recipe in recipes:
        print(f"  Recipe {recipe.name}: {recipe.primary_grade} ({recipe.primary_fraction*100:.1f}%) + {recipe.secondary_grade} ({(1-recipe.primary_fraction)*100:.1f}%), Max rate: {recipe.max_rate}")
    
    # Print tank contents
    print("\nTank contents:")
    for name, tank in tanks.items():
        print(f"  {name}: {tank.content}")
    
    # Fix in Vessel delivery schedule section
    print("\nVessel delivery schedule:")
    for vessel in vessels:
        print(f"  Vessel {vessel.vessel_id} arriving on day {vessel.arrival_day}")
        print(f"    Cargo: {vessel.cargo}")
    
    # Fix in Vessel cargo details section
    print("\nVessel cargo details:")
    for vessel in vessels:
        print(f"  Vessel {vessel.vessel_id} arriving on day {vessel.arrival_day}")
        for cargo_item in vessel.cargo:
            if isinstance(cargo_item, FeedstockParcel):
                print(f"    {cargo_item.grade}: {cargo_item.volume} units")
            else:
                print(f"    Unexpected cargo format: {cargo_item}")
    
    # Set max processing rate
    max_processing_rate = 100  # Adjust as needed
    
    # Create scheduler
    scheduler = Scheduler(tanks, recipes, vessels, crudes, max_processing_rate)
    
    # Run for 7 days
    days_to_schedule = 30
    print(f"\nRunning scheduler for {days_to_schedule} days with max processing rate {max_processing_rate}...")
    
    # IMPORTANT: Check which vessel grades are in the crudes data
    print("\nVessel cargo grades vs available crude data:")
    all_vessel_grades = set()
    for vessel in vessels:
        for cargo_item in vessel.cargo:
            if isinstance(cargo_item, dict) and "grade" in cargo_item:
                grade = cargo_item["grade"]
                all_vessel_grades.add(grade)
                if grade in crudes:
                    print(f"  ✅ Grade {grade} (in vessel cargo) IS in crudes data")
                else:
                    print(f"  ❌ Grade {grade} (in vessel cargo) is NOT in crudes data")
    
    # Check which recipes can use the available grades
    print("\nCompatible recipes for vessel cargo:")
    for recipe in recipes:
        primary_in_crudes = recipe.primary_grade in crudes
        secondary_in_crudes = not recipe.secondary_grade or recipe.secondary_grade in crudes
        
        primary_in_cargo = recipe.primary_grade in all_vessel_grades
        secondary_in_cargo = not recipe.secondary_grade or recipe.secondary_grade in all_vessel_grades
        
        if primary_in_crudes and secondary_in_crudes and primary_in_cargo and secondary_in_cargo:
            print(f"  ✅ Recipe {recipe.name} ({recipe.primary_grade}/{recipe.secondary_grade}) is compatible with vessel cargo and crudes")
        else:
            print(f"  ❌ Recipe {recipe.name} ({recipe.primary_grade}/{recipe.secondary_grade}) is NOT compatible")
    
    try:
        result = scheduler.run(days_to_schedule, save_output=True, output_dir=OUTPUT_DIR)
        
        # Print daily summary
        print("\nSchedule Summary:")
        for day_plan in result:
            day = day_plan.get("day")
            processing = day_plan.get("processing_rates", {})
            inventory = day_plan.get("inventory", 0)
            
            print(f"\nDay {day}:")
            print(f"  Inventory: {inventory}")
            print(f"  Processing rates: {processing}")
            
            blending_details = day_plan.get("blending_details", [])
            if blending_details:
                print(f"  Blending details:")
                for blend in blending_details:
                    print(f"    {blend}")
    
    except Exception as e:
        print(f"Error running scheduler: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
