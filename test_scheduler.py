"""
Test script for running the scheduler directly without the API
"""

import os
import json
import sys
from backend.scheduler.scheduler import Scheduler
from backend.scheduler.models import Tank, BlendingRecipe, Crude, Vessel

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
    # For debugging - let's print the signature of the Vessel constructor
    import inspect
    print(f"Vessel constructor parameters: {inspect.signature(Vessel.__init__)}")
    
    vessels_data = load_json_file(os.path.join(DYNAMIC_DATA_DIR, "vessels.json"))
    vessels = []
    
    # Check if data is a dictionary of vessels or a list
    if isinstance(vessels_data, dict):
        for vessel_id, vessel_info in vessels_data.items():
            try:
                # Try with positional arguments first
                vessels.append(Vessel(
                    vessel_id,  # First arg (likely the vessel identifier)
                    vessel_info.get("cargo", []),  # Second arg (likely cargo)
                    vessel_info.get("arrival_day", 0)  # Third arg (likely arrival day)
                ))
            except TypeError as e:
                print(f"Error creating vessel with ID {vessel_id}: {e}")
                # If the first attempt fails, print the error for debugging
                print("Vessel data:", vessel_info)
    elif isinstance(vessels_data, list):
        for vessel_info in vessels_data:
            try:
                # Try with positional arguments for list format
                vessels.append(Vessel(
                    vessel_info.get("name", "Unknown"),
                    vessel_info.get("cargo", []),
                    vessel_info.get("arrival_day", 0)
                ))
            except TypeError as e:
                print(f"Error creating vessel: {e}")
                # If the first attempt fails, print the error for debugging
                print("Vessel data:", vessel_info)
    
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
    
    # Print vessel delivery schedule
    print("\nVessel delivery schedule:")
    for vessel in vessels:
        print(f"  Vessel {vessel.name} arriving on day {vessel.arrival_day}")
        print(f"    Cargo: {vessel.cargo}")
    
    # Set max processing rate
    max_processing_rate = 100  # Adjust as needed
    
    # Create scheduler
    scheduler = Scheduler(tanks, recipes, vessels, crudes, max_processing_rate)
    
    # Run for 7 days
    days_to_schedule = 30
    print(f"\nRunning scheduler for {days_to_schedule} days with max processing rate {max_processing_rate}...")
    
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
