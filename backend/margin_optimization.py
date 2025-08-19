#!/usr/bin/env python3
"""
Margin Optimization Script - Converted from Jupyter Notebook
OASIS Refinery Scheduling and Vessel Routing Optimization using Mathematical Programming

This script implements a Mixed Integer Linear Programming (MILP) approach for:
- Vessel routing and scheduling
- Crude oil pickup and discharge optimization
- Blending and inventory management
- Margin optimization with demurrage minimization
"""

import os
import sys
import json
import ast
import pickle
import pandas as pd
import mlflow
import smtplib
import traceback
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from pyomo.environ import *

# Load environment variables
try:
    from dotenv import load_dotenv
    load_dotenv()
    print("✅ Environment variables loaded from .env file")
except ImportError:
    print("⚠️ python-dotenv not installed. Install with: pip install python-dotenv")
    print("   Using system environment variables only.")

# Configuration parameters - modify these as needed for testing
SCENARIO = "test_data"  # Changed to use direct test_data folder
VESSEL_COUNT = 6
OPTIMIZATION_TYPE = "throughput"  # "margin" or "throughput"
MAX_DEMURRAGE_LIMIT = 10

# Data paths - using local data directory
DATA_BASE_PATH = "."  # Current directory

# Load email configuration
def load_email_config():
    """Load email configuration from file and environment variables"""
    try:
        with open("email_config.json", "r") as f:
            config = json.load(f)
        
        email_config = config["email_config"].copy()
        
        # Override sensitive data with environment variables
        email_config["sender_password"] = os.getenv("EMAIL_PASSWORD", "")
        
        # Optional: Allow overriding other settings via environment variables
        if os.getenv("EMAIL_SENDER"):
            email_config["sender_email"] = os.getenv("EMAIL_SENDER")
        if os.getenv("EMAIL_RECIPIENT"):
            email_config["recipient_email"] = os.getenv("EMAIL_RECIPIENT")
        if os.getenv("SMTP_SERVER"):
            email_config["smtp_server"] = os.getenv("SMTP_SERVER")
        if os.getenv("SMTP_PORT"):
            email_config["smtp_port"] = int(os.getenv("SMTP_PORT"))
        
        # Check if password is available
        if not email_config["sender_password"]:
            print("⚠️ EMAIL_PASSWORD not found in environment variables. Email notifications disabled.")
            email_config["enable_email"] = False
        
        return email_config
        
    except FileNotFoundError:
        print("⚠️ email_config.json not found. Email notifications disabled.")
        return {"enable_email": False}
    except Exception as e:
        print(f"⚠️ Error loading email config: {e}. Email notifications disabled.")
        return {"enable_email": False}

EMAIL_CONFIG = load_email_config()

def install_dependencies():
    """Install required packages - uncomment if needed"""
    # os.system("conda install -c conda-forge scip -y")
    # os.system("pip install PySCIPOpt pyomo highspy mlflow")
    pass

def send_email_notification(subject, body, attachment_paths=None, is_success=True):
    """Send email notification about optimization completion"""
    if not EMAIL_CONFIG.get("enable_email", False):
        print("Email notifications disabled")
        return
    
    try:
        # Create message
        msg = MIMEMultipart()
        msg['From'] = EMAIL_CONFIG["sender_email"]
        msg['To'] = EMAIL_CONFIG["recipient_email"]
        msg['Subject'] = subject
        
        # Add body
        msg.attach(MIMEText(body, 'plain'))
        
        # Add attachments if provided
        if attachment_paths:
            for file_path in attachment_paths:
                if os.path.exists(file_path):
                    with open(file_path, "rb") as attachment:
                        part = MIMEBase('application', 'octet-stream')
                        part.set_payload(attachment.read())
                    
                    encoders.encode_base64(part)
                    part.add_header(
                        'Content-Disposition',
                        f'attachment; filename= {os.path.basename(file_path)}'
                    )
                    msg.attach(part)
        
        # Connect to server and send email
        server = smtplib.SMTP(EMAIL_CONFIG["smtp_server"], EMAIL_CONFIG["smtp_port"])
        server.starttls()
        server.login(EMAIL_CONFIG["sender_email"], EMAIL_CONFIG["sender_password"])
        text = msg.as_string()
        server.sendmail(EMAIL_CONFIG["sender_email"], EMAIL_CONFIG["recipient_email"], text)
        server.quit()
        
        print(f"✅ Email notification sent successfully to {EMAIL_CONFIG['recipient_email']}")
        
    except Exception as e:
        print(f"❌ Failed to send email notification: {str(e)}")

def create_success_email_body(scenario, vessel_count, optimization_type, total_throughput, 
                             total_margin, average_throughput, average_margin, execution_time):
    """Create email body for successful optimization"""
    return f"""
🎉 OASIS Margin Optimization Completed Successfully! 🎉

Optimization Details:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Scenario: {scenario}
Vessels: {vessel_count}
Optimization Type: {optimization_type}
Execution Time: {execution_time:.2f} minutes

Results Summary:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📊 Total Throughput: {total_throughput:,.0f} kb
💰 Total Margin: ${total_margin:,.0f}
📈 Average Daily Throughput: {average_throughput:,.0f} kb
💵 Average Daily Margin: ${average_margin:,.0f}

The optimization has generated:
✅ Vessel routing schedule
✅ Crude blending plan
✅ Inventory management plan

Files have been saved and are attached to this email.

System Information:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Host: {os.uname().nodename if hasattr(os, 'uname') else 'Unknown'}

Best regards,
OASIS Optimization System
"""

def create_failure_email_body(scenario, vessel_count, optimization_type, error_message, execution_time):
    """Create email body for failed optimization"""
    return f"""
❌ OASIS Margin Optimization Failed ❌

Optimization Details:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Scenario: {scenario}
Vessels: {vessel_count}
Optimization Type: {optimization_type}
Execution Time: {execution_time:.2f} minutes

Error Information:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

{error_message}

System Information:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Host: {os.uname().nodename if hasattr(os, 'uname') else 'Unknown'}

Please check the logs and retry the optimization.

Best regards,
OASIS Optimization System
"""

def load_all_scenario_data(scenario, base_data_path=DATA_BASE_PATH):
    """Load all scenario data from CSV files"""
    base_path = f"{base_data_path}/{scenario}/"
    
    with open(f"{base_path}/config.json", "r") as f:
        config = json.load(f)

    crude_availability_df = pd.read_csv(base_path + "crude_availability.csv")
    crude_availability = {}
    for _, row in crude_availability_df.iterrows():
        crude_availability \
            .setdefault(row["date_range"], {}) \
            .setdefault(row["location"], {})[row["crude"]] = {
                "volume": int(row["volume"]),
                "parcel_size": int(row["parcel_size"])
            }
    
    time_of_travel_df = pd.read_csv(base_path + "time_of_travel.csv")
    time_of_travel = {
        (row["from"], row["to"]): int(row["time_in_days"])
        for _, row in time_of_travel_df.iterrows()
    }
    
    products_info = pd.read_csv(base_path + "products_info.csv")
    crudes_info_df = pd.read_csv(base_path + "crudes_info.csv")
    crudes = crudes_info_df["crudes"]
    locations = set(time_of_travel_df["from"]) | set(time_of_travel_df["to"])
    source_location = crudes_info_df["origin"].to_list()
    crude_margins = crudes_info_df['margin'].to_list()

    opening_inventory = crudes_info_df['opening_inventory'].to_list()
    opening_inventory_dict = dict(zip(crudes.to_list(), opening_inventory))

    return config, list(crudes), list(locations), time_of_travel, crude_availability, source_location, products_info, crude_margins, opening_inventory_dict

def extract_window_to_days(crude_availability):
    """Convert date windows to day lists"""
    window_to_days = {}
    for window in crude_availability:
        parts = window.split()[0]  # e.g., "1-3"
        if '-' in parts:
            start_day, end_day = map(int, parts.split('-'))
            days = list(range(start_day, end_day + 1))
        else:
            days = [int(parts)]
        window_to_days[window] = days
    return window_to_days

def extract_products_ratio(df):
    """Convert DataFrame to products ratio dictionary"""
    return {
        (row['product'], crude): ratio
        for _, row in df.iterrows()
        for crude, ratio in zip(ast.literal_eval(row['crudes']), ast.literal_eval(row['ratios']))
    }

def get_enabled_solver(config):
    """Get the first enabled solver from config"""
    for solver_cfg in config.get("solver", []):
        if solver_cfg.get("use", False):
            solver_name = solver_cfg.get("name")
            if not solver_name:
                continue

            solver = SolverFactory(solver_name)
            if not solver.available():
                continue

            print(f"Using solver: {solver_name}")
            if "time_limit" in solver_cfg:
                solver.options["time_limit"] = solver_cfg["time_limit"]

            for key, value in solver_cfg.get("options", {}).items():
                solver.options[key] = value

            print(f"Solver options: {solver.options}")
            return solver

    raise RuntimeError("No enabled solver found in config.")

def create_pyomo_model(config, crudes, locations, source_location, products_info, crude_availability, 
                      time_of_travel, crude_margins, opening_inventory_dict, vessel_count, optimization_type, max_demurrage_limit):
    """Create and configure the Pyomo optimization model"""
    
    # Extract data
    window_to_days = extract_window_to_days(crude_availability)
    products_ratio = extract_products_ratio(products_info)
    
    # Create model
    model = ConcreteModel()
    
    # Parameters
    INVENTORY_MAX_VOLUME = config["INVENTORY_MAX_VOLUME"]
    MaxTransitions = config["MaxTransitions"]
    
    # Sets
    model.CRUDES = Set(initialize=crudes)
    model.LOCATIONS = Set(initialize=locations)
    model.SOURCE_LOCATIONS = Set(initialize=source_location)
    config["VESSELS"] = list(range(1, vessel_count + 1))
    model.VESSELS = Set(initialize=config["VESSELS"])
    model.DAYS = RangeSet(config["DAYS"]["start"], config["DAYS"]["end"])
    model.BLENDS = Set(initialize=products_info['product'].to_list(), dimen=None)
    model.SLOTS = RangeSet(config["DAYS"]["start"], 2 * config["DAYS"]["end"])
    
    # Parameters
    products_capacity = dict(zip(products_info['product'].to_list(), products_info['max_per_day']))
    crude_margins_dict = dict(zip(crudes, crude_margins))
    
    model.BCb = Param(model.BLENDS, initialize=products_capacity)
    model.BRcb = Param(model.BLENDS, model.CRUDES, initialize=products_ratio, default=0)
    model.MRc = Param(model.CRUDES, initialize=crude_margins_dict)
    
    # Parcels
    parcel_set = set()
    for window, loc_data in crude_availability.items():
        for location, crude_dict in loc_data.items():
            for crude_type, info in crude_dict.items():
                parcel_set.add((location, crude_type, window))
    model.PARCELS = Set(initialize=parcel_set, dimen=3)
    
    # Parcel parameters
    parcel_size = {}
    for window, loc_data in crude_availability.items():
        for location, crude_dict in loc_data.items():
            for crude_type, info in crude_dict.items():
                key = (location, crude_type, window)
                parcel_size[key] = info["parcel_size"]
    model.PVp = Param(model.PARCELS, initialize=parcel_size)
    
    def pc_init(model, *p):
        return p[1]
    model.PCp = Param(model.PARCELS, initialize=pc_init, within=Any)
    
    model.Travel_Time = Param(model.LOCATIONS, model.LOCATIONS, initialize=time_of_travel)
    
    def pdp_init(model, *p):
        window = p[2]
        return window_to_days[window]
    model.PDp = Param(model.PARCELS, initialize=pdp_init)
    
    def plp_init(model, *p):
        return p[0]
    model.PLp = Param(model.PARCELS, within=model.SOURCE_LOCATIONS, initialize=plp_init)
    
    # Capacity parameters
    days = list(range(config["DAYS"]["start"], config["DAYS"]["end"] + 1))
    capacity_dict = {}
    for entry in config['Range']:
        cap = entry['capacity']
        start = entry['start_date']
        end = entry['end_date']
        for day in range(start, end + 1):
            capacity_dict[day] = cap
    
    default_capacity = config['default_capacity']
    for day in days:
        capacity_dict.setdefault(day, default_capacity)
    
    model.RCd = Param(model.DAYS, initialize=capacity_dict)
    
    # Decision Variables
    model.AtLocation = Var(model.VESSELS, model.LOCATIONS, model.DAYS, domain=Binary)
    model.Discharge = Var(model.VESSELS, model.DAYS, domain=Binary)
    model.Pickup = Var(model.VESSELS, model.PARCELS, model.DAYS, domain=Binary)
    model.Inventory = Var(model.CRUDES, model.DAYS, domain=NonNegativeReals)
    model.BlendFraction = Var(model.BLENDS, model.SLOTS, domain=NonNegativeReals)
    model.DischargeDay = Var(model.VESSELS, domain=PositiveIntegers)
    model.Ullage = Var(model.DAYS, domain=NonNegativeReals)
    
    # Auxiliary Variables
    model.LocationVisited = Var(model.VESSELS, model.LOCATIONS, domain=Binary)
    model.CrudeInVessel = Var(model.VESSELS, model.CRUDES, domain=Binary)
    model.NumGrades12 = Var(model.VESSELS, domain=Binary)
    model.NumGrades3 = Var(model.VESSELS, domain=Binary)
    model.VolumeDischarged = Var(model.VESSELS, model.CRUDES, model.DAYS, domain=NonNegativeReals)
    model.VolumeOnboard = Var(model.VESSELS, model.CRUDES, domain=NonNegativeReals)
    model.IsBlendConsumed = Var(model.BLENDS, model.SLOTS, domain=Binary)
    model.IsTransition = Var(model.BLENDS, model.SLOTS, domain=Binary)
    model.Departure = Var(model.VESSELS, model.LOCATIONS, model.DAYS, domain=Binary)
    
    # CONSTRAINTS
    
    # 1. Vessel Travel Constraints
    def vessel_single_location_rule(model, v, d):
        return sum(model.AtLocation[v, l, d] for l in model.LOCATIONS) <= 1
    model.VesselSingleLocation = Constraint(model.VESSELS, model.DAYS, rule=vessel_single_location_rule)
    
    def departure_lower_bound_rule(model, v, l, d):
        if d == model.DAYS[-1]:
            return Constraint.Skip
        else:
            return model.Departure[v, l, d] >= model.AtLocation[v, l, d] - model.AtLocation[v, l, d + 1]
    model.DepartureLowerBound = Constraint(model.VESSELS, model.LOCATIONS, model.DAYS, rule=departure_lower_bound_rule)
    
    def departure_upper_bound1_rule(model, v, l, d):
        return model.Departure[v, l, d] <= model.AtLocation[v, l, d]
    model.DepartureUpperBound1 = Constraint(model.VESSELS, model.LOCATIONS, model.DAYS, rule=departure_upper_bound1_rule)
    
    def departure_upper_bound2_rule(model, v, l, d):
        if d == model.DAYS[-1]:
            return Constraint.Skip
        else:
            return model.Departure[v, l, d] <= 1 - model.AtLocation[v, l, d + 1]
    model.DepartureUpperBound2 = Constraint(model.VESSELS, model.LOCATIONS, model.DAYS, rule=departure_upper_bound2_rule)
    
    def single_departure_per_location_rule(model, v, l):
        return sum(model.Departure[v, l, d] for d in model.DAYS) <= 1
    model.SingleDeparturePerLocation = Constraint(model.VESSELS, model.LOCATIONS, rule=single_departure_per_location_rule)
    
    def enforce_travel_time_rule(model, v, l, d):
        valid_destinations = []
        for l2 in model.LOCATIONS:
            if (l, l2) in time_of_travel:
                travel_time = model.Travel_Time[l, l2]
                arrival_day = d + travel_time
                if arrival_day in model.DAYS:
                    valid_destinations.append(model.AtLocation[v, l2, arrival_day])
        if valid_destinations:
            return model.Departure[v, l, d] <= sum(valid_destinations)
        else:
            return Constraint.Skip
    model.EnforceTravelTime = Constraint(model.VESSELS, model.SOURCE_LOCATIONS, model.DAYS, rule=enforce_travel_time_rule)
    
    def no_early_arrival_rule(model, vessel, source_location, destination_location, start_day, end_day):
        if source_location == destination_location:
            return Constraint.Skip
        if (source_location, destination_location) not in time_of_travel:
            return Constraint.Skip
        if end_day - start_day >= model.Travel_Time[source_location, destination_location]:
            return Constraint.Skip
        if end_day <= start_day:
            return Constraint.Skip
        return model.AtLocation[vessel, source_location, start_day] + model.AtLocation[vessel, destination_location, end_day] <= 1
    model.NoEarlyArrival = Constraint(model.VESSELS, model.LOCATIONS, model.LOCATIONS, model.DAYS, model.DAYS, rule=no_early_arrival_rule)
    
    # 2. Vessel Loading Constraints
    def atleast_one_parcel_per_vessel(model, vessel):
        return sum(model.Pickup[vessel, parcel, day] for parcel in model.PARCELS for day in model.DAYS) >= 1
    model.AtleastOneParcelPerVessel = Constraint(model.VESSELS, rule=atleast_one_parcel_per_vessel)
    
    def one_ship_for_one_parcel_pickup(model, *parcel):
        return sum(model.Pickup[vessel, parcel, day] for vessel in model.VESSELS for day in model.DAYS) <= 1
    model.OneVesselParcel = Constraint(model.PARCELS, rule=one_ship_for_one_parcel_pickup)
    
    def one_pickup_per_day(model, v, d):
        return sum(model.Pickup[v, parcel, d] for parcel in model.PARCELS) <= 1
    model.OnePickupDayVessel = Constraint(model.VESSELS, model.DAYS, rule=one_pickup_per_day)
    
    def pickup_day_limit(model, vessel, *parcel):
        return sum(model.Pickup[vessel, parcel, day] for day in model.DAYS if day not in model.PDp[parcel]) == 0
    model.PickupDayLimit = Constraint(model.VESSELS, model.PARCELS, rule=pickup_day_limit)
    
    def parcel_location_bound(model, vessel, day, *parcel):
        return model.Pickup[vessel, parcel, day] <= model.AtLocation[vessel, model.PLp[parcel], day]
    model.ParcelLocationBound = Constraint(model.VESSELS, model.DAYS, model.PARCELS, rule=parcel_location_bound)
    
    # Location visited constraints
    M = 30
    def location_visited_constraint_1(model, vessel, location):
        return sum(model.AtLocation[vessel, location, day] for day in model.DAYS) >= model.LocationVisited[vessel, location]
    model.LocationConstraint1 = Constraint(model.VESSELS, model.SOURCE_LOCATIONS, rule=location_visited_constraint_1)
    
    def location_visited_constraint_2(model, vessel, location):
        return sum(model.AtLocation[vessel, location, day] for day in model.DAYS) <= M * model.LocationVisited[vessel, location]
    model.LocationConstraint2 = Constraint(model.VESSELS, model.SOURCE_LOCATIONS, rule=location_visited_constraint_2)
    
    def location_visited_constraint_3(model, vessel, location):
        return sum(sum(model.Pickup[vessel, parcel, day] for day in model.DAYS) for parcel in model.PARCELS if model.PLp[parcel] == location) >= model.LocationVisited[vessel, location]
    model.LocationConstraint3 = Constraint(model.VESSELS, model.SOURCE_LOCATIONS, rule=location_visited_constraint_3)
    
    # Crude vessel constraints
    def crude_in_vessel_bound_with_pickup(model, vessel, crude):
        return sum(sum(model.Pickup[vessel, parcel, day] for day in model.DAYS) for parcel in model.PARCELS if model.PCp[parcel] == crude) >= model.CrudeInVessel[vessel, crude]
    model.CrudeInVesselBoundWithPickup = Constraint(model.VESSELS, model.CRUDES, rule=crude_in_vessel_bound_with_pickup)
    
    def crude_in_vessel_lower_bound(model, vessel, crude):
        return sum(sum(model.Pickup[vessel, parcel, day] for day in model.DAYS) for parcel in model.PARCELS if model.PCp[parcel] == crude) <= model.CrudeInVessel[vessel, crude] * M
    model.CrudeInVesselLowerBound = Constraint(model.VESSELS, model.CRUDES, rule=crude_in_vessel_lower_bound)
    
    def max_3_crudes_limit(model, vessel):
        return sum(model.CrudeInVessel[vessel, crude] for crude in model.CRUDES) <= 3
    model.Max3CrudesLimit = Constraint(model.VESSELS, rule=max_3_crudes_limit)
    
    def crude_group_limit(model, vessel):
        return model.NumGrades12[vessel] + model.NumGrades3[vessel] == 1
    model.CrudeGroupLimit = Constraint(model.VESSELS, rule=crude_group_limit)
    
    def total_crude_upper_limit(model, vessel, crude):
        return 2 * model.NumGrades12[vessel] + 3 * model.NumGrades3[vessel] >= sum(model.CrudeInVessel[vessel, crude] for crude in model.CRUDES)
    model.TotalCrudeUpperLimit = Constraint(model.VESSELS, model.CRUDES, rule=total_crude_upper_limit)
    
    def total_crude_lower_limit(model, vessel, crude):
        return model.NumGrades12[vessel] + 3 * model.NumGrades3[vessel] <= sum(model.CrudeInVessel[vessel, crude] for crude in model.CRUDES)
    model.TotalCrudeLowerLimit = Constraint(model.VESSELS, model.CRUDES, rule=total_crude_lower_limit)
    
    def crude_count_wise_vessel_volume_limit(model, vessel):
        return sum(model.PVp[parcel] * sum(model.Pickup[vessel, parcel, day] for day in model.DAYS) for parcel in model.PARCELS) <= config['Two_crude'] * model.NumGrades12[vessel] + config['Three_crude'] * model.NumGrades3[vessel]
    model.CrudeCountWiseVesselVolume = Constraint(model.VESSELS, rule=crude_count_wise_vessel_volume_limit)
    
    # 3. Vessel Discharge Constraints
    def unique_vessel_discharge_day(model, v):
        return sum(model.Discharge[v, d] for d in model.DAYS) == 1
    model.UniqueVesselDischargeDay = Constraint(model.VESSELS, rule=unique_vessel_discharge_day)
    
    def discharge_at_melaka_rule(model, v, d):
        if d == model.DAYS[-1]:
            return 2 * model.Discharge[v, d] <= model.AtLocation[v, "Melaka", d]
        else:
            return 2 * model.Discharge[v, d] <= model.AtLocation[v, "Melaka", d] + model.AtLocation[v, "Melaka", d + 1]
    model.DischargeAtMelaka = Constraint(model.VESSELS, model.DAYS, rule=discharge_at_melaka_rule)
    
    def no_two_vessels_discharge_same_or_adjacent_day_rule(model, d):
        if d == model.DAYS[-1]:
            return sum(model.Discharge[v, d] for v in model.VESSELS) <= 1
        else:
            return sum(model.Discharge[v, d] + model.Discharge[v, d + 1] for v in model.VESSELS) <= 1
    model.NoTwoDischargeSameOrAdjacent = Constraint(model.DAYS, rule=no_two_vessels_discharge_same_or_adjacent_day_rule)
    
    def vessel_stops_after_discharge_rule(model, v, l, d1, d2):
        if d2 <= d1 + 1:
            return Constraint.Skip
        return model.AtLocation[v, l, d2] <= 1 - model.Discharge[v, d1]
    model.VesselStopsAfterDischarge = Constraint(model.VESSELS, model.LOCATIONS, model.DAYS, model.DAYS, rule=vessel_stops_after_discharge_rule)
    
    def volume_onboard_rule(model, v, c):
        return model.VolumeOnboard[v, c] == sum(model.PVp[p] * sum(model.Pickup[v, p, d] for d in model.DAYS) for p in model.PARCELS if model.PCp[p] == c)
    model.VolumeOnboardDef = Constraint(model.VESSELS, model.CRUDES, rule=volume_onboard_rule)
    
    def discharge_upper_limit_rule(model, v, c, d):
        return model.VolumeDischarged[v, c, d] <= config['Vessel_max_limit'] * model.Discharge[v, d]
    model.DischargeUpperLimit = Constraint(model.VESSELS, model.CRUDES, model.DAYS, rule=discharge_upper_limit_rule)
    
    def discharge_no_more_than_onboard_rule(model, v, c, d):
        return model.VolumeDischarged[v, c, d] <= model.VolumeOnboard[v, c]
    model.DischargeNoMoreThanOnboard = Constraint(model.VESSELS, model.CRUDES, model.DAYS, rule=discharge_no_more_than_onboard_rule)
    
    def discharge_lower_bound_rule(model, v, c, d):
        return model.VolumeDischarged[v, c, d] >= model.VolumeOnboard[v, c] - config['Vessel_max_limit'] * (1 - model.Discharge[v, d])
    model.DischargeLowerBound = Constraint(model.VESSELS, model.CRUDES, model.DAYS, rule=discharge_lower_bound_rule)
    
    # 4. Crude Blending Constraints
    def is_blend_greater_than_fraction_rule(model, s, *b):
        return model.IsBlendConsumed[b, s] >= model.BlendFraction[b, s]
    model.IsBlendVsFraction = Constraint(model.SLOTS, model.BLENDS, rule=is_blend_greater_than_fraction_rule)
    
    def one_blend_per_slot_rule(model, s):
        return sum(model.IsBlendConsumed[b, s] for b in model.BLENDS) == 1
    model.OneBlendPerSlot = Constraint(model.SLOTS, rule=one_blend_per_slot_rule)
    
    def blend_fraction_daily_upper_bound_rule(model, s):
        if s % 2 == 1 and s + 1 in model.SLOTS:
            return sum(model.BlendFraction[b, s] + model.BlendFraction[b, s + 1] for b in model.BLENDS) <= 1
        else:
            return Constraint.Skip
    model.BlendFractionDailyBound = Constraint(model.SLOTS, rule=blend_fraction_daily_upper_bound_rule)
    
    def transition_lower_bound_rule(model, s, *b):
        if s + 1 in model.SLOTS:
            return model.IsTransition[b, s] >= model.IsBlendConsumed[b, s] - model.IsBlendConsumed[b, s + 1]
        else:
            return Constraint.Skip
    model.TransitionLowerBound = Constraint(model.SLOTS, model.BLENDS, rule=transition_lower_bound_rule)
    
    def transition_upper_bound1_rule(model, s, *b):
        return model.IsTransition[b, s] <= model.IsBlendConsumed[b, s]
    model.TransitionUpperBound1 = Constraint(model.SLOTS, model.BLENDS, rule=transition_upper_bound1_rule)
    
    def transition_upper_bound2_rule(model, s, *b):
        if s + 1 in model.SLOTS:
            return model.IsTransition[b, s] <= 1 - model.IsBlendConsumed[b, s + 1]
        else:
            return Constraint.Skip
    model.TransitionUpperBound2 = Constraint(model.SLOTS, model.BLENDS, rule=transition_upper_bound2_rule)
    
    def max_transitions_rule(model):
        return sum(model.IsTransition[b, s] for b in model.BLENDS for s in model.SLOTS) <= MaxTransitions
    model.MaxTransitionsConstraint = Constraint(rule=max_transitions_rule)
    
    def plant_capacity_rule(model, d):
        return sum(model.BCb[b] * (model.BlendFraction[b, 2*d - 1] + model.BlendFraction[b, 2*d]) for b in model.BLENDS) <= model.RCd[d]
    model.PlantCapacityConstraint = Constraint(model.DAYS, rule=plant_capacity_rule)
    
    # Symmetry constraints
    def discharge_day_rule(model, v):
        return model.DischargeDay[v] == sum(d * model.Discharge[v, d] for d in model.DAYS)
    model.CalcDischargeDay = Constraint(model.VESSELS, rule=discharge_day_rule)
    
    def symmetry_breaking_rule(model, v):
        if v < len(model.VESSELS):
            return model.DischargeDay[v] + 1 <= model.DischargeDay[v + 1]
        return Constraint.Skip
    model.SymmetryBreak = Constraint(model.VESSELS, rule=symmetry_breaking_rule)
    
    # 5. Inventory Constraints
    def inventory_update_rule(model, c, d):
        discharged = 0
        if d <= 5:
            discharged = 0
        else:
            discharged = sum(model.VolumeDischarged[v, c, d-5] for v in model.VESSELS)
        
        consumed = sum(model.BCb[blend]*model.BRcb[blend,c]*(model.BlendFraction[blend, 2*d-1] + model.BlendFraction[blend, 2*d]) for blend in model.BLENDS)
        if d == 1:
            return model.Inventory[c, d] == opening_inventory_dict[c] + discharged - consumed
        else:
            return model.Inventory[c, d] == model.Inventory[c, d-1] + discharged - consumed
    model.InventoryUpdate = Constraint(model.CRUDES, model.DAYS, rule=inventory_update_rule)
    
    def max_inventory_limit(model, day):
        return sum(model.Inventory[crude, day] for crude in model.CRUDES) <= INVENTORY_MAX_VOLUME
    model.MaxInventoryLimit = Constraint(model.DAYS, rule=max_inventory_limit)
    
    def ullage_update_rule(model, d):
        consumed = sum(model.BCb[b] * (model.BlendFraction[b, 2*d - 1] + model.BlendFraction[b, 2*d]) for b in model.BLENDS)
        if d == 1:
            return model.Ullage[d] == INVENTORY_MAX_VOLUME - sum(opening_inventory_dict[c] for c in model.CRUDES) + consumed
        
        discharged = 0
        if (d - 1) in model.DAYS:
            discharged = sum(model.VolumeDischarged[v, c, d - 1] for v in model.VESSELS for c in model.CRUDES)
        
        return model.Ullage[d] == model.Ullage[d - 1] - discharged + consumed
    model.UllageUpdate = Constraint(model.DAYS, rule=ullage_update_rule)
    
    def depart_after_load_rule(model, v, l, d):
        return model.Departure[v,l,d] <= sum(model.Pickup[v, p, d] for p in model.PARCELS if model.PLp[p] == l)
    model.DepartAfterLoad = Constraint(model.VESSELS, model.SOURCE_LOCATIONS, model.DAYS, rule=depart_after_load_rule)
    
    # OBJECTIVE FUNCTION
    def demurrage_at_source_expr(model):
        return config['Demurrage'] * (
            sum(model.AtLocation[vessel,location,day] for vessel in model.VESSELS for location in model.LOCATIONS for day in model.DAYS if location != 'Melaka') - 
            sum(model.Pickup[vessel, parcel, day] for vessel in model.VESSELS for parcel in model.PARCELS for day in model.DAYS)
        )
    model.DeumrrageAtSource = Expression(rule=demurrage_at_source_expr)
    
    def demurrage_at_melaka_expr(model):
        return config['Demurrage'] * (sum(sum(model.AtLocation[vessel,'Melaka', day] for day in model.DAYS) - 2 for vessel in model.VESSELS))
    model.DemurrageAtMelaka = Expression(rule=demurrage_at_melaka_expr)
    
    def total_profit_expr(model):
        return sum(model.MRc[crude]*model.BRcb[blend,crude]*model.BCb[blend]*model.BlendFraction[blend,slot] for crude in model.CRUDES for blend in model.BLENDS for slot in model.SLOTS)
    model.TotalProfit = Expression(rule=total_profit_expr)
    
    def total_throughput_expr(model):
        return sum(model.BCb[blend]*model.BlendFraction[blend,slot] for blend in model.BLENDS for slot in model.SLOTS)
    model.Throughput = Expression(rule=total_throughput_expr)
    
    def net_profit_objective_rule(model):
        return model.TotalProfit - (model.DeumrrageAtSource + model.DemurrageAtMelaka)
    
    def total_throughput_objective_rule(model):
        return model.Throughput
    
    if optimization_type == 'margin':
        model.objective = Objective(rule=net_profit_objective_rule, sense=maximize)
    elif optimization_type == 'throughput':
        model.DemurrageLimitConstraint = Constraint(expr=model.DeumrrageAtSource + model.DemurrageAtMelaka <= max_demurrage_limit*config["Demurrage"])
        model.objective = Objective(rule=total_throughput_objective_rule, sense=maximize)
    else:
        raise NotImplementedError(f"Optimization type '{optimization_type}' not implemented")
    
    return model, parcel_size

def solve_model(model, config, scenario, vessel_count, optimization_type, max_demurrage_limit):
    """Solve the optimization model"""
    solver = get_enabled_solver(config)
    
    # Create output directory
    dir_path = f"{DATA_BASE_PATH}/output/{scenario}/"
    os.makedirs(dir_path, exist_ok=True)
    
    # Set up logging
    if optimization_type == 'throughput':
        model_log_file_path = f'{dir_path}{optimization_type}_Optimization_log_{vessel_count}_vessels_{config["DAYS"]["end"]}_days_{config["MaxTransitions"]}_transitions_{max_demurrage_limit}_demurrages.txt'
    else:
        model_log_file_path = f'{dir_path}{optimization_type}_Optimization_log_{vessel_count}_vessels_{config["DAYS"]["end"]}_days_{config["MaxTransitions"]}_transitions.txt'
    
    print(f"📝 Solver log will be saved to: {model_log_file_path}")
    print(f"🔧 Using solver: {solver}")
    print(f"⏱️ Starting optimization (this may take several hours)...")
    
    # Solve model
    with open(model_log_file_path, "w") as f:
        sys_stdout = sys.stdout
        sys.stdout = f
        
        # Print progress header to console and log
        print(f"=== OASIS Margin Optimization Started ===")
        print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Scenario: {scenario}")
        print(f"Vessels: {vessel_count}")
        print(f"Optimization Type: {optimization_type}")
        print(f"Days: {config['DAYS']['end']}")
        print(f"Max Transitions: {config['MaxTransitions']}")
        print(f"Solver: {solver}")
        print("=" * 50)
        
        result = solver.solve(model, tee=True)
        
        print("=" * 50)
        print(f"=== Optimization Completed ===")
        print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Status: {result.solver.termination_condition}")
        
        sys.stdout = sys_stdout
    
    print(f"✅ Optimization solver completed!")
    print(f"📊 Status: {result.solver.termination_condition}")
    
    return result

def extract_results(model, config, scenario, vessel_count, optimization_type, max_demurrage_limit, parcel_size):
    """Extract and process optimization results"""
    from pyomo.environ import value
    
    print("=" * 50)
    print("OPTIMIZATION RESULTS")
    print("=" * 50)
    print(f"Total Margin: {value(model.TotalProfit)}")
    print(f"Total Demurrage at Melaka: {value(model.DemurrageAtMelaka)}")
    print(f"Total Demurrage at Source: {value(model.DeumrrageAtSource)}")
    print(f"Total Profit: {value(model.objective)}")
    
    # Extract blending results
    days = []
    Final_Product = []
    Quantity_produced = []
    profit_each_slot = []
    slots = []
    inventory = []
    ullage = []
    crude_blended = {c: [] for c in model.CRUDES}
    crude_available = {c: [] for c in model.CRUDES}
    
    for slot in model.SLOTS:
        slots.append(slot)
        if (slot+1) % 2 == 0:
            day = int((slot+1)/2)
        days.append(day)
        total_profit = 0
        
        for blend in model.BLENDS:
            if value(model.IsBlendConsumed[blend, slot]) > 0.5:
                Final_Product.append(blend)
                produced = value(model.BlendFraction[blend,slot]) * value(model.BCb[blend])
                Quantity_produced.append(produced)
                inventory_total = 0
                
                for crude in model.CRUDES:
                    blended_amount = value(model.BCb[blend]) * value(model.BRcb[blend,crude]) * value(model.BlendFraction[blend, slot])
                    profit = model.MRc[crude] * blended_amount
                    crude_blended[crude].append(blended_amount)
                    inv = value(model.Inventory[crude, day])
                    crude_available[crude].append(inv)
                    inventory_total += inv
                    total_profit += profit
                
                inventory.append(inventory_total)
        ullage.append(value(model.Ullage[day]))
        profit_each_slot.append(total_profit)
    
    # Create blending DataFrame
    records = []
    for i in range(len(slots)):
        record = {
            "Date": pd.to_datetime("2024-10-01") + pd.Timedelta(days=days[i]-1),
            "Slot": slots[i],
            "Final Product": Final_Product[i],
            "Quantity Produced": round(Quantity_produced[i]/1000, 1),
            **{f"Crude {c} Available": round(crude_available[c][i]/1000, 1) for c in model.CRUDES},
            **{f"Crude {c} Blended": round(crude_blended[c][i]/1000, 1) for c in model.CRUDES},
            "Inventory Available": round(inventory[i]/1000, 1),
            "Ullage": round(ullage[i]/1000, 1),
            "Profit": profit_each_slot[i],
            "Flag": "Margin_Optimization"
        }
        records.append(record)
    
    df = pd.DataFrame(records)
    
    # Process slot numbers
    slot = []
    for i in df['Slot']:
        if i % 2 == 0:
            slot.append(2)
        else:
            slot.append(1)
    df['Slot'] = slot
    df['Date'] = df['Date'].dt.strftime('%Y-%m-%d')
    
    def reduce_rows(group):
        if (group["Quantity Produced"] == 0).sum() == 1:
            row = group[group["Quantity Produced"] != 0].copy()
            row.loc[:, "Slot"] = 1
            return row
        else:
            return group
    
    combined_df_reduced = df.groupby(["Date","Flag"], group_keys=False).apply(reduce_rows).reset_index(drop=True)
    
    # Extract vessel routing results
    vessel_records = []
    for v in model.VESSELS:
        is_vessel_started = False
        is_vessel_terminated = False
        is_at_melaka = 0
        last_port_location = None
        pending_sailing_records = []
        crude_loaded = {}
        
        for d in model.DAYS:
            at_location = False
            activity_name_list = []
            location_visited = None
            is_loading = 0
            is_unloading = 0
            
            for l in model.LOCATIONS:
                if value(model.AtLocation[v, l, d]) > 0.5:
                    at_location = True
                    location_visited = l
                    last_port_location = l
                    
                    if not is_vessel_started:
                        activity_name_list.append("Arrival T")
                        is_vessel_started = True
                    
                    for p in model.PARCELS:
                        if value(model.Pickup[v, p, d]) > 0.5:
                            crude_type = p[1]
                            crude_volume_carried = parcel_size[p]
                            crude_loaded[f"{crude_type} Volume"] = crude_volume_carried
                            activity_name_list.append("Loading")
                            is_loading = 1
                            break
                    
                    if l == "Melaka" and is_at_melaka == 0:
                        activity_name_list.append("Arrival M")
                        is_at_melaka = 1
                    
                    if value(model.Discharge[v, d]) > 0.5:
                        activity_name_list.append("Discharge")
                        is_unloading = 1
                    
                    if (d > 1) and value(model.Discharge[v, d-1]) > 0.5:
                        activity_name_list.append("Discharge")
                        is_vessel_terminated = True
                        is_unloading = 1
                    
                    if 'Loading' not in activity_name_list and "Discharge" not in activity_name_list:
                        activity_name_list.append("Demurrage")
            
            if is_vessel_started and not is_vessel_terminated and not at_location:
                activity_name_list.append("Sailing")
            
            # Find next port when sailing
            next_port_location = None
            if not at_location:
                for future_d in range(d + 1, max(model.DAYS) + 1):
                    for l_future in model.LOCATIONS:
                        if value(model.AtLocation[v, l_future, future_d]) > 0.5:
                            next_port_location = l_future
                            break
                    if next_port_location:
                        break
            
            # Decide Last Port display
            if at_location:
                last_port_display = location_visited
                for rec in pending_sailing_records:
                    rec["Last Port"] = f"{rec['Last Port'].split('--')[0]}--{location_visited}"
                    vessel_records.append(rec)
                pending_sailing_records.clear()
            elif not at_location and last_port_location and next_port_location:
                last_port_display = f"{last_port_location}--{next_port_location}"
            else:
                last_port_display = "Unknown"
            
            for activity_name in activity_name_list:
                if activity_name == "Demurrage":
                    demurrage_activity = 1
                else:
                    demurrage_activity = 0
                    
                record = {
                    "Activity Date": pd.to_datetime("2024-10-01") + pd.Timedelta(days=d - 1),
                    "Activity Name": activity_name,
                    "Activity End Date": pd.to_datetime("2024-10-01") + pd.Timedelta(days=d),
                    "Vessel ID": v,
                    "Last Port": last_port_display,
                    **crude_loaded,
                    "is_at_Melaka": is_at_melaka,
                    "is Demurrage Day": demurrage_activity,
                    "is_crude_unloading_day": is_unloading,
                    "is_loading": is_loading,
                    "Scenario Id": scenario
                }
                
                if activity_name == "Sailing":
                    pending_sailing_records.append(record)
                else:
                    vessel_records.append(record)
    
    vessel_df = pd.DataFrame(vessel_records)
    
    # Calculate summary metrics
    total_throughput = combined_df_reduced['Quantity Produced'].sum()
    total_margin = combined_df_reduced['Profit'].sum()
    average_throughput = total_throughput / config["DAYS"]["end"]
    average_margin = total_margin / config["DAYS"]["end"]
    
    print(f"\nSUMMARY METRICS:")
    print(f"Total Throughput: {total_throughput}")
    print(f"Total Margin: {total_margin}")
    print(f"Average Throughput: {average_throughput}")
    print(f"Average Margin: {average_margin}")
    
    return combined_df_reduced, vessel_df, total_throughput, total_margin, average_throughput, average_margin

def save_results(model, combined_df_reduced, vessel_df, config, scenario, vessel_count, optimization_type, max_demurrage_limit, 
                total_throughput, total_margin, average_throughput, average_margin):
    """Save results to files"""
    base_path = f"{DATA_BASE_PATH}/output/{scenario}/"
    os.makedirs(base_path, exist_ok=True)
    
    # Generate filenames
    if optimization_type == 'throughput':
        crude_blending_filename = f'crude_blending_{optimization_type}_optimization_{vessel_count}_vessels_{config["DAYS"]["end"]}_days_{config["MaxTransitions"]}_transitions_{max_demurrage_limit}_demurrages.csv'
        vessel_routing_filename = f'vessel_routing_{optimization_type}_optimization_{vessel_count}_vessels_{config["DAYS"]["end"]}_days_{config["MaxTransitions"]}_transitions_{max_demurrage_limit}_demurrages.csv'
        model_file_name = f'{base_path}{optimization_type}_optimization_{vessel_count}_vessels_{config["DAYS"]["end"]}_days_{config["MaxTransitions"]}_transitions_{max_demurrage_limit}_demurrages.pkl'
    else:
        crude_blending_filename = f'crude_blending_{optimization_type}_optimization_{vessel_count}_vessels_{config["DAYS"]["end"]}_days_{config["MaxTransitions"]}_transitions.csv'
        vessel_routing_filename = f'vessel_routing_{optimization_type}_optimization_{vessel_count}_vessels_{config["DAYS"]["end"]}_days_{config["MaxTransitions"]}_transitions.csv'
        model_file_name = f'{base_path}{optimization_type}_optimization_{vessel_count}_vessels_{config["DAYS"]["end"]}_days_{config["MaxTransitions"]}_transitions.pkl'
    
    # Save CSV files
    combined_df_reduced.to_csv(base_path + crude_blending_filename, index=False)
    vessel_df.to_csv(base_path + vessel_routing_filename, index=False)
    
    # Save model to pickle
    with open(model_file_name, 'wb') as fp:
        pickle.dump(model, fp)
    
    print(f"\nResults saved to:")
    print(f"- Blending: {base_path + crude_blending_filename}")
    print(f"- Vessel Routing: {base_path + vessel_routing_filename}")
    print(f"- Model: {model_file_name}")
    
    return base_path + crude_blending_filename, base_path + vessel_routing_filename

def run_mlflow_experiment(scenario, vessel_count, optimization_type, max_demurrage_limit, 
                         total_throughput, total_margin, average_throughput, average_margin,
                         crude_blending_file, vessel_routing_file):
    """Run MLflow experiment tracking"""
    try:
        mlflow.set_experiment(f"vessel_routing_crude_blending_optimization_scenario_{scenario.replace(' ', '')}_experiment")
        mlflow.start_run()
        
        # Log parameters
        mlflow.log_param("vessel_count", vessel_count)
        mlflow.log_param("optimization_type", optimization_type)
        if optimization_type == 'throughput':
            mlflow.log_param("max_demurrage_limit", max_demurrage_limit)
        
        # Log metrics
        mlflow.log_metric("total_throughput", total_throughput)
        mlflow.log_metric("total_margin", total_margin)
        mlflow.log_metric("average_throughput", average_throughput)
        mlflow.log_metric("average_margin", average_margin)
        
        # Log artifacts
        mlflow.log_artifact(crude_blending_file, artifact_path="tables")
        mlflow.log_artifact(vessel_routing_file, artifact_path="tables")
        
        mlflow.end_run()
        print("MLflow experiment completed successfully")
        
    except Exception as e:
        print(f"MLflow logging failed: {e}")

def main():
    """Main execution function with error handling and email notifications"""
    start_time = datetime.now()
    print("Starting Margin Optimization Script")
    print("=" * 50)
    print(f"Start Time: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    try:
        # Load data
        print("Loading scenario data...")
        config, crudes, locations, time_of_travel, crude_availability, source_location, products_info, crude_margins, opening_inventory_dict = load_all_scenario_data(SCENARIO)
        
        # Create model
        print("Creating optimization model...")
        model, parcel_size = create_pyomo_model(
            config, crudes, locations, source_location, products_info, crude_availability,
            time_of_travel, crude_margins, opening_inventory_dict, VESSEL_COUNT, OPTIMIZATION_TYPE, MAX_DEMURRAGE_LIMIT
        )
        
        # Solve model
        print("Solving optimization model...")
        result = solve_model(model, config, SCENARIO, VESSEL_COUNT, OPTIMIZATION_TYPE, MAX_DEMURRAGE_LIMIT)
        
        # Extract results
        print("Extracting results...")
        combined_df_reduced, vessel_df, total_throughput, total_margin, average_throughput, average_margin = extract_results(
            model, config, SCENARIO, VESSEL_COUNT, OPTIMIZATION_TYPE, MAX_DEMURRAGE_LIMIT, parcel_size
        )
        
        # Save results
        print("Saving results...")
        crude_blending_file, vessel_routing_file = save_results(
            model, combined_df_reduced, vessel_df, config, SCENARIO, VESSEL_COUNT, OPTIMIZATION_TYPE, MAX_DEMURRAGE_LIMIT,
            total_throughput, total_margin, average_throughput, average_margin
        )
        
        # MLflow tracking
        print("Running MLflow experiment...")
        run_mlflow_experiment(
            SCENARIO, VESSEL_COUNT, OPTIMIZATION_TYPE, MAX_DEMURRAGE_LIMIT,
            total_throughput, total_margin, average_throughput, average_margin,
            crude_blending_file, vessel_routing_file
        )
        
        # Calculate execution time
        end_time = datetime.now()
        execution_time = (end_time - start_time).total_seconds() / 60  # in minutes
        
        print(f"\n🎉 Optimization completed successfully!")
        print(f"Execution time: {execution_time:.2f} minutes")
        
        # Send success email
        subject = f"✅ OASIS Optimization Completed Successfully - {SCENARIO}"
        body = create_success_email_body(
            SCENARIO, VESSEL_COUNT, OPTIMIZATION_TYPE, total_throughput, 
            total_margin, average_throughput, average_margin, execution_time
        )
        
        # Attach result files
        attachments = [crude_blending_file, vessel_routing_file]
        send_email_notification(subject, body, attachments, is_success=True)
        
        return model, combined_df_reduced, vessel_df
        
    except Exception as e:
        # Calculate execution time for failed run
        end_time = datetime.now()
        execution_time = (end_time - start_time).total_seconds() / 60  # in minutes
        
        # Get full error traceback
        error_traceback = traceback.format_exc()
        error_message = f"Error: {str(e)}\n\nFull Traceback:\n{error_traceback}"
        
        print(f"\n❌ Optimization failed!")
        print(f"Execution time: {execution_time:.2f} minutes")
        print(f"Error: {str(e)}")
        
        # Send failure email
        subject = f"❌ OASIS Optimization Failed - {SCENARIO}"
        body = create_failure_email_body(
            SCENARIO, VESSEL_COUNT, OPTIMIZATION_TYPE, error_message, execution_time
        )
        send_email_notification(subject, body, is_success=False)
        
        # Re-raise the exception so the script exits with error code
        raise

if __name__ == "__main__":
    # You can modify these parameters for testing
    print(f"Configuration:")
    print(f"- Scenario: {SCENARIO}")
    print(f"- Vessel Count: {VESSEL_COUNT}")
    print(f"- Optimization Type: {OPTIMIZATION_TYPE}")
    print(f"- Max Demurrage Limit: {MAX_DEMURRAGE_LIMIT}")
    print()
    
    model, blending_results, vessel_results = main()
