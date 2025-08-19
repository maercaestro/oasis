#!/usr/bin/env python3
"""
OASIS Margin Optimization - 5 Tanks Version
Mathematical Programming Approach using Pyomo with 5 separate tanks

Tank Configuration:
- Tank 1-4: 250,000 barrels each
- Tank 5: 180,000 barrels
- Total: 1,180,000 barrels (same as single tank version)

This script compares performance against the single tank approach.
"""

import pandas as pd
import numpy as np
from pyomo.environ import *
import json
import os
import sys
import time
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime
from dotenv import load_dotenv

def load_data():
    """Load all required data files"""
    print("📂 Loading data files...")
    
    # Load CSV files
    crudes_info = pd.read_csv('test_data/crudes_info.csv')
    products_info = pd.read_csv('test_data/products_info.csv')
    crude_availability = pd.read_csv('test_data/crude_availability.csv')
    time_of_travel = pd.read_csv('test_data/time_of_travel.csv')
    
    # Load configuration
    with open('test_data/config.json', 'r') as f:
        config = json.load(f)
    
    print(f"✅ Loaded {len(crudes_info)} crudes, {len(products_info)} products")
    print(f"✅ Loaded {len(crude_availability)} crude availability entries")
    print(f"✅ Loaded {len(time_of_travel)} vessel travel times")
    
    return crudes_info, products_info, crude_availability, time_of_travel, config

def extract_vessels_capacity_data(crude_availability):
    """Extract vessel capacity data from crude availability"""
    vessels_data = []
    
    for _, row in crude_availability.iterrows():
        vessel_info = {
            "name": row["vessel"],
            "crude": row["crude"],
            "volume": int(row["volume"]),
            "arrival_day": int(row["arrival_day"]),
            "cost": float(row["cost"])
        }
        vessels_data.append(vessel_info)
    
    return vessels_data

def extract_crudes_data(crudes_info):
    """Extract crude oil properties and opening inventory"""
    crudes_data = {}
    
    for _, row in crudes_info.iterrows():
        crude_name = row["crudes"]  # Note: CSV has 'crudes' not 'crude'
        crudes_data[crude_name] = {
            "api": float(row.get("api", 30.0)),  # Default API if missing
            "sulfur": float(row.get("sulfur", 0.5)),  # Default sulfur if missing
            "price": float(row.get("price", 50.0)),  # Default price if missing
            "opening_inventory": float(row.get("opening_inventory", 0))
        }
    
    return crudes_data

def extract_products_data(products_info):
    """Extract product specifications and pricing"""
    products_data = {}
    
    for _, row in products_info.iterrows():
        product_name = row["product"]
        products_data[product_name] = {
            "min_api": float(row["min_api"]),
            "max_api": float(row["max_api"]),
            "min_sulfur": float(row["min_sulfur"]),
            "max_sulfur": float(row["max_sulfur"]),
            "price": float(row["price"]),
            "max_per_day": float(row["max_per_day"])
        }
    
    return products_data

def extract_products_ratio(products_info):
    """Extract product ratio constraints"""
    products_ratio = {}
    
    for _, row in products_info.iterrows():
        product_name = row["product"]
        if 'ratio_min' in row and 'ratio_max' in row:
            products_ratio[product_name] = {
                "min_ratio": float(row["ratio_min"]) if pd.notna(row["ratio_min"]) else 0,
                "max_ratio": float(row["ratio_max"]) if pd.notna(row["ratio_max"]) else 1
            }
    
    return products_ratio

def create_5tank_model(crudes_info, products_info, crude_availability, time_of_travel, config):
    """
    Create the 5-tank optimization model
    
    Tank Configuration:
    - Tank 1-4: 250,000 barrels each
    - Tank 5: 180,000 barrels
    """
    print("🏗️ Creating 5-tank optimization model...")
    
    # Extract data
    vessels_data = extract_vessels_capacity_data(crude_availability)
    crudes_data = extract_crudes_data(crudes_info)
    products_data = extract_products_data(products_info)
    products_ratio = extract_products_ratio(products_info)
    
    # Create model
    model = ConcreteModel()
    
    # Tank Configuration - 5 separate tanks
    TANK_CAPACITIES = {
        'T1': 250000,  # Tank 1: 250k barrels
        'T2': 250000,  # Tank 2: 250k barrels
        'T3': 250000,  # Tank 3: 250k barrels
        'T4': 250000,  # Tank 4: 250k barrels
        'T5': 180000   # Tank 5: 180k barrels
    }
    
    # Parameters
    MaxTransitions = config["MaxTransitions"]
    
    # Sets
    model.CRUDES = Set(initialize=list(crudes_data.keys()))
    model.VESSELS = Set(initialize=list(set([v["name"] for v in vessels_data])))
    model.BLENDS = Set(initialize=list(products_data.keys()))
    model.TANKS = Set(initialize=list(TANK_CAPACITIES.keys()))  # 5 tanks
    
    # Time horizon
    start_day = config["DAYS"]["start"]
    end_day = config["DAYS"]["end"]
    model.DAYS = Set(initialize=range(start_day, end_day + 1))
    
    # Crude properties
    api_dict = {c: crudes_data[c]["api"] for c in model.CRUDES}
    sulfur_dict = {c: crudes_data[c]["sulfur"] for c in model.CRUDES}
    crude_price_dict = {c: crudes_data[c]["price"] for c in model.CRUDES}
    
    model.API = Param(model.CRUDES, initialize=api_dict)
    model.Sulfur = Param(model.CRUDES, initialize=sulfur_dict)
    model.CrudePrice = Param(model.CRUDES, initialize=crude_price_dict)
    
    # Product specifications
    min_api_dict = {p: products_data[p]["min_api"] for p in model.BLENDS}
    max_api_dict = {p: products_data[p]["max_api"] for p in model.BLENDS}
    min_sulfur_dict = {p: products_data[p]["min_sulfur"] for p in model.BLENDS}
    max_sulfur_dict = {p: products_data[p]["max_sulfur"] for p in model.BLENDS}
    blend_price_dict = {p: products_data[p]["price"] for p in model.BLENDS}
    
    model.MinAPI = Param(model.BLENDS, initialize=min_api_dict)
    model.MaxAPI = Param(model.BLENDS, initialize=max_api_dict)
    model.MinSulfur = Param(model.BLENDS, initialize=min_sulfur_dict)
    model.MaxSulfur = Param(model.BLENDS, initialize=max_sulfur_dict)
    model.BlendPrice = Param(model.BLENDS, initialize=blend_price_dict)
    
    # Product capacity constraints
    products_capacity = dict(zip(products_info['product'].to_list(), products_info['max_per_day']))
    model.BCb = Param(model.BLENDS, initialize=products_capacity)
    
    # Tank capacities
    model.TankCapacity = Param(model.TANKS, initialize=TANK_CAPACITIES)
    
    # Opening inventory distribution across tanks
    # Strategy: Smart distribution - fill tanks efficiently
    opening_inventory_distribution = {}
    
    print(f"\n📦 Distributing Opening Inventory Across 5 Tanks...")
    
    # Initialize all to zero
    for tank in model.TANKS:
        for crude in model.CRUDES:
            opening_inventory_distribution[(tank, crude)] = 0
    
    # Distribute each crude type across tanks
    for crude in model.CRUDES:
        crude_opening = crudes_data[crude]["opening_inventory"]
        if crude_opening > 0:
            print(f"   Distributing {crude}: {crude_opening:,} barrels")
            
            # Strategy: Fill tanks sequentially, but keep some space for operations
            remaining_volume = crude_opening
            tank_list = list(model.TANKS)
            
            for i, tank in enumerate(tank_list):
                if remaining_volume <= 0:
                    break
                
                tank_capacity = TANK_CAPACITIES[tank]
                # Don't fill tank completely - leave 20% space for operational flexibility
                max_fill = tank_capacity * 0.8
                
                if remaining_volume <= max_fill:
                    # Put remaining volume in this tank
                    opening_inventory_distribution[(tank, crude)] = remaining_volume
                    print(f"      {tank}: {remaining_volume:,.0f} barrels ({remaining_volume/tank_capacity*100:.1f}% of capacity)")
                    remaining_volume = 0
                else:
                    # Fill this tank to 80% and continue
                    opening_inventory_distribution[(tank, crude)] = max_fill
                    print(f"      {tank}: {max_fill:,.0f} barrels (80.0% of capacity)")
                    remaining_volume -= max_fill
            
            # If there's still remaining volume, distribute proportionally
            if remaining_volume > 0:
                print(f"      Remaining {remaining_volume:,.0f} barrels distributed proportionally")
                total_capacity = sum(TANK_CAPACITIES.values())
                for tank in model.TANKS:
                    additional = remaining_volume * (TANK_CAPACITIES[tank] / total_capacity)
                    opening_inventory_distribution[(tank, crude)] += additional
    
    model.OpeningInventory = Param(model.TANKS, model.CRUDES, 
                                  initialize=opening_inventory_distribution, default=0)
    
    # Print opening inventory distribution for transparency
    print(f"\n📦 Opening Inventory Distribution:")
    total_opening = 0
    for crude in model.CRUDES:
        crude_total = crudes_data[crude]["opening_inventory"]
        total_opening += crude_total
        if crude_total > 0:
            print(f"   {crude}: {crude_total:,} barrels total")
            for tank in model.TANKS:
                tank_amount = opening_inventory_distribution[(tank, crude)]
                if tank_amount > 0:
                    print(f"      {tank}: {tank_amount:,.0f} barrels")
    print(f"   Total Opening Inventory: {total_opening:,} barrels")
    
    # Vessel data parameters
    vessel_crude_volume = {}
    vessel_arrival = {}
    vessel_cost = {}
    
    for vessel_info in vessels_data:
        vessel = vessel_info["name"]
        crude = vessel_info["crude"]
        vessel_crude_volume[(vessel, crude)] = vessel_info["volume"]
        vessel_arrival[vessel] = vessel_info["arrival_day"]
        vessel_cost[vessel] = vessel_info["cost"]
    
    model.VesselCrudeVolume = Param(model.VESSELS, model.CRUDES, 
                                   initialize=vessel_crude_volume, default=0)
    model.VesselArrival = Param(model.VESSELS, initialize=vessel_arrival)
    model.VesselCost = Param(model.VESSELS, initialize=vessel_cost)
    
    # Refinery capacity parameters
    capacity_dict = {}
    for entry in config.get('Range', []):
        cap = entry['capacity']
        start_date = entry['start_date']
        end_date = entry['end_date']
        
        for day in range(start_date, end_date + 1):
            capacity_dict[day] = cap
    
    default_capacity = config['default_capacity']
    for day in model.DAYS:
        capacity_dict.setdefault(day, default_capacity)
    
    model.RCd = Param(model.DAYS, initialize=capacity_dict)
    
    # Decision Variables
    
    # Vessel decisions
    model.SelectVessel = Var(model.VESSELS, domain=Binary)
    model.VesselArrivalDay = Var(model.VESSELS, model.DAYS, domain=Binary)
    model.VesselDepartureDay = Var(model.VESSELS, model.DAYS, domain=Binary)
    
    # Volume variables
    model.VolumeDischarged = Var(model.VESSELS, model.CRUDES, model.DAYS, domain=NonNegativeReals)
    model.VolumeOnboard = Var(model.VESSELS, model.CRUDES, domain=NonNegativeReals)
    
    # Tank inventory for each tank and crude type
    model.TankInventory = Var(model.TANKS, model.CRUDES, model.DAYS, domain=NonNegativeReals)
    
    # Blending variables from each tank
    model.BlendFromTank = Var(model.TANKS, model.CRUDES, model.BLENDS, model.DAYS, domain=NonNegativeReals)
    
    # Total blend production
    model.BlendProduction = Var(model.BLENDS, model.DAYS, domain=NonNegativeReals)
    
    # Tank allocation decisions - which crude goes to which tank
    model.CrudeToTank = Var(model.VESSELS, model.CRUDES, model.TANKS, model.DAYS, domain=NonNegativeReals)
    
    # Constraints
    
    # 1. Tank capacity constraints - each tank has its own capacity limit
    def tank_capacity_rule(model, tank, day):
        return sum(model.TankInventory[tank, c, day] for c in model.CRUDES) <= model.TankCapacity[tank]
    model.TankCapacityConstraint = Constraint(model.TANKS, model.DAYS, rule=tank_capacity_rule)
    
    # 2. Tank inventory balance for each tank
    def tank_inventory_balance_rule(model, tank, crude, day):
        if day == min(model.DAYS):
            # First day: start with opening inventory
            opening_inv = model.OpeningInventory[tank, crude]
            inflow = sum(model.CrudeToTank[v, crude, tank, day] for v in model.VESSELS)
            outflow = sum(model.BlendFromTank[tank, crude, blend, day] for blend in model.BLENDS)
            return model.TankInventory[tank, crude, day] == opening_inv + inflow - outflow
        else:
            # Subsequent days: balance from previous day
            prev_day = day - 1
            inflow = sum(model.CrudeToTank[v, crude, tank, day] for v in model.VESSELS)
            outflow = sum(model.BlendFromTank[tank, crude, blend, day] for blend in model.BLENDS)
            return model.TankInventory[tank, crude, day] == model.TankInventory[tank, crude, prev_day] + inflow - outflow
    model.TankInventoryBalance = Constraint(model.TANKS, model.CRUDES, model.DAYS, rule=tank_inventory_balance_rule)
    
    # 3. Vessel volume discharge constraint
    def volume_discharge_rule(model, vessel, crude, day):
        return model.VolumeDischarged[vessel, crude, day] == sum(model.CrudeToTank[vessel, crude, tank, day] for tank in model.TANKS)
    model.VolumeDischargeRule = Constraint(model.VESSELS, model.CRUDES, model.DAYS, rule=volume_discharge_rule)
    
    # 4. Vessel selection constraint
    def vessel_selection_rule(model, vessel):
        return sum(model.VesselArrivalDay[vessel, day] for day in model.DAYS) == model.SelectVessel[vessel]
    model.VesselSelection = Constraint(model.VESSELS, rule=vessel_selection_rule)
    
    # 5. Vessel arrival timing
    def vessel_arrival_timing_rule(model, vessel, day):
        return model.VesselArrivalDay[vessel, day] <= 1 if day >= model.VesselArrival[vessel] else model.VesselArrivalDay[vessel, day] == 0
    model.VesselArrivalTiming = Constraint(model.VESSELS, model.DAYS, rule=vessel_arrival_timing_rule)
    
    # 6. Vessel discharge timing
    def vessel_discharge_timing_rule(model, vessel, crude, day):
        return model.VolumeDischarged[vessel, crude, day] <= model.VesselCrudeVolume[vessel, crude] * model.VesselArrivalDay[vessel, day]
    model.VesselDischargeTiming = Constraint(model.VESSELS, model.CRUDES, model.DAYS, rule=vessel_discharge_timing_rule)
    
    # 7. Volume onboard constraint
    def volume_onboard_rule(model, v, c):
        return model.VolumeOnboard[v, c] == sum(model.VolumeDischarged[v, c, d] for d in model.DAYS)
    model.VolumeOnboard_con = Constraint(model.VESSELS, model.CRUDES, rule=volume_onboard_rule)
    
    # 8. Blend production constraint
    def blend_production_rule(model, blend, day):
        return model.BlendProduction[blend, day] == sum(model.BlendFromTank[tank, crude, blend, day] 
                                                       for tank in model.TANKS for crude in model.CRUDES)
    model.BlendProductionRule = Constraint(model.BLENDS, model.DAYS, rule=blend_production_rule)
    
    # 9. Blend capacity constraint
    def blend_capacity_rule(model, blend, day):
        return model.BlendProduction[blend, day] <= model.BCb[blend]
    model.BlendCapacityRule = Constraint(model.BLENDS, model.DAYS, rule=blend_capacity_rule)
    
    # 10. API quality constraints
    def api_min_rule(model, blend, day):
        if model.BlendProduction[blend, day].value == 0:
            return Constraint.Skip
        total_api = sum(model.API[crude] * model.BlendFromTank[tank, crude, blend, day] 
                       for tank in model.TANKS for crude in model.CRUDES)
        return total_api >= model.MinAPI[blend] * model.BlendProduction[blend, day]
    model.APIMinRule = Constraint(model.BLENDS, model.DAYS, rule=api_min_rule)
    
    def api_max_rule(model, blend, day):
        if model.BlendProduction[blend, day].value == 0:
            return Constraint.Skip
        total_api = sum(model.API[crude] * model.BlendFromTank[tank, crude, blend, day] 
                       for tank in model.TANKS for crude in model.CRUDES)
        return total_api <= model.MaxAPI[blend] * model.BlendProduction[blend, day]
    model.APIMaxRule = Constraint(model.BLENDS, model.DAYS, rule=api_max_rule)
    
    # 11. Sulfur quality constraints
    def sulfur_min_rule(model, blend, day):
        if model.BlendProduction[blend, day].value == 0:
            return Constraint.Skip
        total_sulfur = sum(model.Sulfur[crude] * model.BlendFromTank[tank, crude, blend, day] 
                          for tank in model.TANKS for crude in model.CRUDES)
        return total_sulfur >= model.MinSulfur[blend] * model.BlendProduction[blend, day]
    model.SulfurMinRule = Constraint(model.BLENDS, model.DAYS, rule=sulfur_min_rule)
    
    def sulfur_max_rule(model, blend, day):
        if model.BlendProduction[blend, day].value == 0:
            return Constraint.Skip
        total_sulfur = sum(model.Sulfur[crude] * model.BlendFromTank[tank, crude, blend, day] 
                          for tank in model.TANKS for crude in model.CRUDES)
        return total_sulfur <= model.MaxSulfur[blend] * model.BlendProduction[blend, day]
    model.SulfurMaxRule = Constraint(model.BLENDS, model.DAYS, rule=sulfur_max_rule)
    
    # 12. Refinery capacity constraint
    def refinery_capacity_rule(model, day):
        total_production = sum(model.BlendProduction[blend, day] for blend in model.BLENDS)
        return total_production <= model.RCd[day]
    model.RefineryCapacityRule = Constraint(model.DAYS, rule=refinery_capacity_rule)
    
    # Objective Function: Maximize profit
    def objective_rule(model):
        # Revenue from product sales
        revenue = sum(model.BlendPrice[blend] * model.BlendProduction[blend, day] 
                     for blend in model.BLENDS for day in model.DAYS)
        
        # Cost of crude oil
        crude_cost = sum(model.CrudePrice[crude] * model.VolumeOnboard[vessel, crude] 
                        for vessel in model.VESSELS for crude in model.CRUDES)
        
        # Vessel costs
        vessel_cost = sum(model.VesselCost[vessel] * model.SelectVessel[vessel] 
                         for vessel in model.VESSELS)
        
        return revenue - crude_cost - vessel_cost
    
    model.Profit = Objective(rule=objective_rule, sense=maximize)
    
    print(f"✅ 5-tank model created with {len(TANK_CAPACITIES)} tanks")
    print(f"   Tank capacities: {TANK_CAPACITIES}")
    print(f"   Total capacity: {sum(TANK_CAPACITIES.values()):,} barrels")
    
    return model

def solve_model(model, config):
    """Solve the optimization model"""
    print("🔧 Solving optimization model...")
    
    # Get solver configuration
    solver_configs = config.get("solver", [])
    active_solver = None
    
    for solver_config in solver_configs:
        if solver_config.get("use", False):
            active_solver = solver_config
            break
    
    if not active_solver:
        raise Exception("No active solver found in configuration")
    
    solver_name = active_solver["name"]
    time_limit = active_solver.get("time_limit", 3600)
    solver_options = active_solver.get("options", {})
    
    print(f"🔧 Using solver: {solver_name} (time limit: {time_limit}s)")
    
    # Create solver
    solver = SolverFactory(solver_name)
    
    # Set solver options
    for option, value in solver_options.items():
        solver.options[option] = value
    
    # Add time limit
    if solver_name.lower() == 'scip':
        solver.options['limits/time'] = time_limit
    elif solver_name.lower() == 'highs':
        solver.options['time_limit'] = time_limit
    
    # Solve
    start_time = time.time()
    result = solver.solve(model, tee=True)
    solve_time = time.time() - start_time
    
    print(f"⏱️ Solve time: {solve_time:.2f} seconds")
    print(f"📊 Solution status: {result.solver.termination_condition}")
    
    return result, solve_time

def extract_results(model):
    """Extract and format optimization results"""
    print("📊 Extracting results...")
    
    results = {
        "objective_value": value(model.Profit),
        "vessels_selected": [],
        "tank_utilization": {},
        "blend_production": {},
        "tank_inventory": {},
        "opening_inventory": {},
        "summary": {}
    }
    
    # Opening inventory
    for tank in model.TANKS:
        results["opening_inventory"][tank] = {}
        for crude in model.CRUDES:
            opening_amount = value(model.OpeningInventory[tank, crude])
            if opening_amount > 0:
                results["opening_inventory"][tank][crude] = opening_amount
    
    # Selected vessels
    for vessel in model.VESSELS:
        if value(model.SelectVessel[vessel]) > 0.5:
            vessel_info = {
                "vessel": vessel,
                "cost": value(model.VesselCost[vessel]),
                "arrival_days": []
            }
            
            for day in model.DAYS:
                if value(model.VesselArrivalDay[vessel, day]) > 0.5:
                    vessel_info["arrival_days"].append(day)
            
            results["vessels_selected"].append(vessel_info)
    
    # Tank utilization by day
    for day in model.DAYS:
        results["tank_utilization"][day] = {}
        for tank in model.TANKS:
            tank_total = sum(value(model.TankInventory[tank, crude, day]) for crude in model.CRUDES)
            tank_capacity = value(model.TankCapacity[tank])
            utilization = (tank_total / tank_capacity) * 100 if tank_capacity > 0 else 0
            
            results["tank_utilization"][day][tank] = {
                "inventory": tank_total,
                "capacity": tank_capacity,
                "utilization_percent": utilization
            }
    
    # Tank inventory details
    for tank in model.TANKS:
        results["tank_inventory"][tank] = {}
        for crude in model.CRUDES:
            results["tank_inventory"][tank][crude] = {}
            for day in model.DAYS:
                results["tank_inventory"][tank][crude][day] = value(model.TankInventory[tank, crude, day])
    
    # Blend production
    for blend in model.BLENDS:
        results["blend_production"][blend] = {}
        for day in model.DAYS:
            results["blend_production"][blend][day] = value(model.BlendProduction[blend, day])
    
    # Summary statistics
    total_revenue = sum(value(model.BlendPrice[blend] * model.BlendProduction[blend, day]) 
                       for blend in model.BLENDS for day in model.DAYS)
    total_crude_cost = sum(value(model.CrudePrice[crude] * model.VolumeOnboard[vessel, crude]) 
                          for vessel in model.VESSELS for crude in model.CRUDES)
    total_vessel_cost = sum(value(model.VesselCost[vessel] * model.SelectVessel[vessel]) 
                           for vessel in model.VESSELS)
    
    results["summary"] = {
        "total_profit": results["objective_value"],
        "total_revenue": total_revenue,
        "total_crude_cost": total_crude_cost,
        "total_vessel_cost": total_vessel_cost,
        "vessels_used": len(results["vessels_selected"]),
        "tanks_configuration": "5 tanks (T1-T4: 250k, T5: 180k)"
    }
    
    print(f"✅ Results extracted - Profit: ${results['objective_value']:,.2f}")
    
    return results

def save_results(results, filename="5tank_optimization_results.json"):
    """Save results to JSON file"""
    print(f"💾 Saving results to {filename}...")
    
    with open(filename, 'w') as f:
        json.dump(results, f, indent=2, default=str)
    
    print(f"✅ Results saved to {filename}")
    return filename

def send_email_notification(results, solve_time, output_file):
    """Send email notification with results"""
    try:
        # Load environment variables
        load_dotenv()
        
        # Load email configuration
        with open('email_config.json', 'r') as f:
            email_config = json.load(f)['email_config']
        
        # Get email settings (environment variables override config)
        smtp_server = os.getenv('SMTP_SERVER', email_config.get('smtp_server'))
        smtp_port = int(os.getenv('SMTP_PORT', email_config.get('smtp_port', 587)))
        sender_email = os.getenv('EMAIL_SENDER', email_config.get('sender_email'))
        recipient_email = os.getenv('EMAIL_RECIPIENT', email_config.get('recipient_email'))
        sender_password = os.getenv('EMAIL_PASSWORD')
        
        if not sender_password:
            print("⚠️ No email password found in environment variables")
            return False
        
        # Create message
        msg = MIMEMultipart()
        msg['From'] = sender_email
        msg['To'] = recipient_email
        msg['Subject'] = "🏗️ OASIS 5-Tank Optimization Complete"
        
        # Email body
        body = f"""
🏗️ OASIS 5-Tank Margin Optimization Results

📊 OPTIMIZATION SUMMARY:
• Configuration: 5 separate tanks (T1-T4: 250k, T5: 180k barrels)
• Total Profit: ${results['summary']['total_profit']:,.2f}
• Solve Time: {solve_time:.2f} seconds
• Vessels Used: {results['summary']['vessels_used']}

💰 FINANCIAL BREAKDOWN:
• Total Revenue: ${results['summary']['total_revenue']:,.2f}
• Crude Oil Cost: ${results['summary']['total_crude_cost']:,.2f}
• Vessel Cost: ${results['summary']['total_vessel_cost']:,.2f}

📈 COMPARISON NOTES:
This is the 5-tank version for comparison with the single tank approach.
Results file attached for detailed analysis.

🕒 Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        """
        
        msg.attach(MIMEText(body, 'plain'))
        
        # Attach results file
        if os.path.exists(output_file):
            with open(output_file, "rb") as attachment:
                part = MIMEBase('application', 'octet-stream')
                part.set_payload(attachment.read())
            
            encoders.encode_base64(part)
            part.add_header(
                'Content-Disposition',
                f'attachment; filename= {os.path.basename(output_file)}'
            )
            msg.attach(part)
        
        # Send email
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(sender_email, sender_password)
        text = msg.as_string()
        server.sendmail(sender_email, recipient_email, text)
        server.quit()
        
        print(f"✅ Email notification sent to {recipient_email}")
        return True
        
    except Exception as e:
        print(f"❌ Failed to send email notification: {e}")
        return False

def main():
    """Main optimization routine"""
    print("🚀 Starting OASIS 5-Tank Margin Optimization")
    print("=" * 60)
    
    try:
        # Load data
        crudes_info, products_info, crude_availability, time_of_travel, config = load_data()
        
        # Create model
        model = create_5tank_model(crudes_info, products_info, crude_availability, time_of_travel, config)
        
        # Solve model
        result, solve_time = solve_model(model, config)
        
        if result.solver.termination_condition == TerminationCondition.optimal:
            print("🎉 Optimal solution found!")
            
            # Extract results
            results = extract_results(model)
            
            # Save results
            output_file = save_results(results)
            
            # Send email notification
            send_email_notification(results, solve_time, output_file)
            
            print("\n🏆 5-TANK OPTIMIZATION COMPLETE!")
            print(f"📊 Total Profit: ${results['summary']['total_profit']:,.2f}")
            print(f"⏱️ Solve Time: {solve_time:.2f} seconds")
            print(f"🏗️ Tank Configuration: 5 tanks (T1-T4: 250k, T5: 180k)")
            
        else:
            print("❌ Optimization failed or suboptimal solution")
            print(f"Status: {result.solver.termination_condition}")
            
    except Exception as e:
        print(f"❌ Error during optimization: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
