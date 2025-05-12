"""
Test script for the updated scheduler.py using existing API functions
"""
import os
import sys
import json
import datetime

# Change to the project directory
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# Import the api module from backend
sys.path.append(os.path.abspath('.'))
from backend.api import (
    load_tanks, load_recipes, load_vessels, load_crudes, 
    convert_daily_plans_to_json
)
from backend.scheduler.scheduler import Scheduler

# Load data using existing API functions
tanks = load_tanks()
recipes = load_recipes()
vessels = load_vessels()
crudes = load_crudes()

print("Loaded data:")
print(f"- Tanks: {len(tanks)}")
print(f"- Recipes: {len(recipes)}")
print(f"- Vessels: {len(vessels)}")
print(f"- Crudes: {len(crudes)}")

# Create scheduler
scheduler = Scheduler(
    tanks=tanks,
    blending_recipes=recipes,
    vessels=vessels,
    crude_data=crudes,
    max_processing_rate=350.0
)

# Run for 10 days with output saving enabled (default)
print("\nRunning scheduler for 10 days...")
results = scheduler.run(days=10)

print(f"\nScheduler produced {len(results)} daily plans")

# Output directory location
output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backend", "output")
print(f"\nOutput files saved to: {output_dir}")

try:
    # List files in the output directory
    files = os.listdir(output_dir)
    json_files = [f for f in files if f.endswith('.json')]
    excel_files = [f for f in files if f.endswith('.xlsx')]
    
    print(f"\nFiles in output directory: {len(files)}")
    for filename in files[-5:]:  # Show latest 5 files
        file_path = os.path.join(output_dir, filename)
        file_size = os.path.getsize(file_path)
        file_time = datetime.datetime.fromtimestamp(os.path.getmtime(file_path))
        print(f"- {filename} ({file_size} bytes, {file_time})")
    
    # Load the most recent JSON file to validate
    if json_files:
        latest_json = max([os.path.join(output_dir, f) for f in json_files], key=os.path.getmtime)
        print(f"\nChecking latest JSON file: {os.path.basename(latest_json)}")
        
        with open(latest_json, 'r') as f:
            json_data = json.load(f)
            
        if "daily_plans" in json_data:
            print(f"JSON file contains {len(json_data['daily_plans'])} daily plans")
            print("Format looks valid!")
        else:
            print("ERROR: JSON file does not contain 'daily_plans' key")
    else:
        print("\nNo JSON files found in output directory.")

except Exception as e:
    print(f"Error checking output files: {e}")
