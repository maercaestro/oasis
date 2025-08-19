#!/usr/bin/env python3
"""
Data Preparation Script for Margin Optimization
Converts OASIS JSON data to CSV format required by the margin optimization script
"""

import json
import pandas as pd
import os
from datetime import datetime, timedelta

def load_oasis_data():
    """Load existing OASIS data from JSON files"""
    print("Loading OASIS data...")
    
    # Load crudes data
    with open('./static_data/crudes.json', 'r') as f:
        crudes_data = json.load(f)
    
    # Load recipes data
    with open('./static_data/recipes.json', 'r') as f:
        recipes_data = json.load(f)
    
    # Load feedstock parcels (crude availability)
    with open('./dynamic_data/feedstock_parcels.json', 'r') as f:
        parcels_data = json.load(f)
    
    return crudes_data, recipes_data, parcels_data

def create_crudes_info_csv(crudes_data, output_dir):
    """Create crudes_info.csv from OASIS crudes data"""
    crudes_list = []
    
    for crude_name, crude_info in crudes_data.items():
        crudes_list.append({
            'crudes': crude_name,
            'margin': crude_info['margin'],
            'origin': crude_info['origin'],
            'opening_inventory': 100000  # Default opening inventory - adjust as needed
        })
    
    df = pd.DataFrame(crudes_list)
    filepath = os.path.join(output_dir, 'crudes_info.csv')
    df.to_csv(filepath, index=False)
    print(f"Created: {filepath}")
    return df

def create_products_info_csv(recipes_data, output_dir):
    """Create products_info.csv from OASIS recipes data"""
    products_list = []
    
    for recipe_id, recipe_info in recipes_data.items():
        # Create crudes list and ratios
        crudes = []
        ratios = []
        
        # Primary crude
        crudes.append(recipe_info['primary_grade'])
        ratios.append(recipe_info['primary_fraction'])
        
        # Secondary crude if exists
        if recipe_info['secondary_grade']:
            crudes.append(recipe_info['secondary_grade'])
            ratios.append(1.0 - recipe_info['primary_fraction'])
        
        products_list.append({
            'product': f"F{int(recipe_id) + 1}",  # F1, F2, etc.
            'max_per_day': recipe_info['max_rate'] * 1000,  # Convert to appropriate units
            'crudes': str(crudes),
            'ratios': str(ratios)
        })
    
    df = pd.DataFrame(products_list)
    filepath = os.path.join(output_dir, 'products_info.csv')
    df.to_csv(filepath, index=False)
    print(f"Created: {filepath}")
    return df

def create_crude_availability_csv(parcels_data, output_dir):
    """Create crude_availability.csv from OASIS feedstock parcels"""
    availability_list = []
    
    for parcel_id, parcel_info in parcels_data.items():
        # Extract LDR (Loading Date Range)
        ldr = parcel_info['ldr']
        for start_day, end_day in ldr.items():
            date_range = f"{start_day}-{end_day} Jan"  # Format as expected
            
            availability_list.append({
                'date_range': date_range,
                'location': parcel_info['origin'],
                'crude': parcel_info['grade'],
                'volume': int(parcel_info['volume'] * 1000),  # Convert to appropriate units
                'parcel_size': int(parcel_info['volume'] * 1000)  # Same as volume for now
            })
    
    df = pd.DataFrame(availability_list)
    filepath = os.path.join(output_dir, 'crude_availability.csv')
    df.to_csv(filepath, index=False)
    print(f"Created: {filepath}")
    return df

def create_time_of_travel_csv(output_dir):
    """Create time_of_travel.csv with sample travel times"""
    # Sample travel time data - adjust based on your actual locations
    travel_data = [
        {'from': 'Peninsular Malaysia', 'to': 'Melaka', 'time_in_days': 1},
        {'from': 'Terminal3', 'to': 'Melaka', 'time_in_days': 2},
        {'from': 'Sabah', 'to': 'Melaka', 'time_in_days': 3},
        {'from': 'Sarawak', 'to': 'Melaka', 'time_in_days': 3},
        # Add more routes as needed
    ]
    
    df = pd.DataFrame(travel_data)
    filepath = os.path.join(output_dir, 'time_of_travel.csv')
    df.to_csv(filepath, index=False)
    print(f"Created: {filepath}")
    return df

def create_config_json(output_dir):
    """Create config.json with optimization parameters"""
    config = {
        "INVENTORY_MAX_VOLUME": 1000000,
        "MaxTransitions": 8,
        "DAYS": {
            "start": 1,
            "end": 30
        },
        "Range": [
            {
                "capacity": 80000,
                "start_date": 18,
                "end_date": 27
            }
        ],
        "default_capacity": 960000,
        "Two_crude": 700000,
        "Three_crude": 650000,
        "Vessel_max_limit": 1000000,
        "Demurrage": 50000,
        "solver": [
            {
                "name": "scip",
                "use": True,
                "time_limit": 3600,
                "options": {
                    "limits/time": 3600,
                    "presolving/maxrounds": 0
                }
            },
            {
                "name": "highs",
                "use": False,
                "time_limit": 1800,
                "options": {}
            }
        ]
    }
    
    filepath = os.path.join(output_dir, 'config.json')
    with open(filepath, 'w') as f:
        json.dump(config, f, indent=2)
    print(f"Created: {filepath}")
    return config

def create_test_data():
    """Main function to create test data for margin optimization"""
    print("Creating test data for margin optimization...")
    
    # Create output directory
    scenario_name = "Scenario Abu"
    output_dir = f"./test_data/{scenario_name}"
    os.makedirs(output_dir, exist_ok=True)
    
    # Load OASIS data
    crudes_data, recipes_data, parcels_data = load_oasis_data()
    
    # Create CSV files
    crudes_df = create_crudes_info_csv(crudes_data, output_dir)
    products_df = create_products_info_csv(recipes_data, output_dir)
    availability_df = create_crude_availability_csv(parcels_data, output_dir)
    travel_df = create_time_of_travel_csv(output_dir)
    
    # Create config
    config = create_config_json(output_dir)
    
    print(f"\nTest data created successfully in: {output_dir}")
    print("\nFiles created:")
    print("- config.json")
    print("- crudes_info.csv")
    print("- products_info.csv") 
    print("- crude_availability.csv")
    print("- time_of_travel.csv")
    
    print(f"\nData summary:")
    print(f"- Crudes: {len(crudes_df)} types")
    print(f"- Products: {len(products_df)} recipes")
    print(f"- Crude parcels: {len(availability_df)} availability windows")
    print(f"- Travel routes: {len(travel_df)} routes")
    
    return output_dir

if __name__ == "__main__":
    # Change to backend directory if running from different location
    if not os.path.exists('./static_data'):
        print("Error: Run this script from the backend directory where static_data folder exists")
        exit(1)
    
    create_test_data()
