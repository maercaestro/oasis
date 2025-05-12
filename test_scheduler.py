"""
Test script for the updated scheduler.py
"""
import os
import sys
# Add the parent directory to sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.scheduler.scheduler import Scheduler
from backend.scheduler.models import Tank, BlendingRecipe, FeedstockParcel, Vessel, Crude

# Create some test data
tanks = {
    "tank1": Tank(name="tank1", capacity=100.0, content=[{"Arab Light": 50.0}]),
    "tank2": Tank(name="tank2", capacity=150.0, content=[{"Murban": 75.0}])
}

recipes = [
    BlendingRecipe(
        name="Recipe 1",
        primary_grade="Arab Light",
        secondary_grade="Murban",
        max_rate=60.0,
        primary_fraction=0.7
    ),
    BlendingRecipe(
        name="Recipe 2",
        primary_grade="Murban",
        secondary_grade=None,
        max_rate=40.0,
        primary_fraction=1.0
    )
]

vessels = [
    Vessel(
        vessel_id="vessel1",
        arrival_day=3,
        cost=10.0,
        capacity=200.0,
        cargo=[
            FeedstockParcel(
                grade="Arab Light",
                volume=100.0,
                ldr={1: 2},
                origin="Saudi Arabia"
            )
        ]
    )
]

crudes = {
    "Arab Light": Crude(name="Arab Light", margin=10.0, origin="Saudi Arabia"),
    "Murban": Crude(name="Murban", margin=12.0, origin="UAE")
}

# Create and run the scheduler
scheduler = Scheduler(
    tanks=tanks,
    blending_recipes=recipes,
    vessels=vessels,
    crude_data=crudes,
    max_processing_rate=100.0
)

# Run for 5 days and save output
results = scheduler.run(days=5, save_output=True)
print(f"Generated {len(results)} daily plans")

# Check the output directory
output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backend", "output")
print(f"Output files saved to: {output_dir}")
print("Files in output directory:")
for filename in os.listdir(output_dir):
    print(f"- {filename}")

# Check if any JSON files were created
json_files = [f for f in os.listdir(output_dir) if f.endswith('.json')]
print(f"JSON files: {json_files}")
