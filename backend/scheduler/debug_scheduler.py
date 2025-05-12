"""
Debug script added directly to the scheduler module
"""

if __name__ == "__main__":
    import os
    import json
    from typing import Dict
    from .models import Tank, BlendingRecipe, Vessel, Crude
    from scheduler import Scheduler
    
    # Create test data
    test_tanks = {
        "tank1": Tank(name="tank1", capacity=100.0, content=[{"Arab Light": 50.0}]),
        "tank2": Tank(name="tank2", capacity=150.0, content=[{"Murban": 75.0}])
    }
    
    test_recipes = [
        BlendingRecipe(
            name="Recipe 1",
            primary_grade="Arab Light",
            secondary_grade="Murban",
            max_rate=60.0,
            primary_fraction=0.7
        )
    ]
    
    test_vessels = []  # No vessels for simplicity
    
    test_crudes = {
        "Arab Light": Crude(name="Arab Light", margin=10.0, origin="Saudi Arabia"),
        "Murban": Crude(name="Murban", margin=12.0, origin="UAE")
    }
    
    # Create the scheduler
    scheduler = Scheduler(
        tanks=test_tanks,
        blending_recipes=test_recipes,
        vessels=test_vessels,
        crude_data=test_crudes,
        max_processing_rate=100.0
    )
    
    # Run for 3 days
    print("Running test scheduler...")
    results = scheduler.run(days=3, save_output=True)
    
    print(f"Generated {len(results)} daily plans")
    
    # Output directory
    output_dir = os.path.join(os.path.dirname(__file__), "../output")
    print(f"Output directory: {output_dir}")
    
    # Check for files
    try:
        files = os.listdir(output_dir)
        print(f"Files in output directory: {len(files)}")
        for f in files:
            print(f"- {f}")
    except Exception as e:
        print(f"Error listing output directory: {e}")
