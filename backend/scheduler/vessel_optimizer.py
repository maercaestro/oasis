"""
Vessel Optimizer class for OASIS sytem. The auxiliary optimizer that will work
with main scheduling optimizer to optimize the operating rates by optimizing the vessel
delivery and volume. Target: right volume at the right time.

Copyright (c) by Abu Huzaifah Bidin with help from Github Copilot

"""

import json
import os
from typing import List, Dict, Optional, Tuple, Set
import pulp as plp
from .models import Vessel, FeedstockParcel, FeedstockRequirement, Route

class VesselOptimizer:
    """
    Optimizer for vessel scheduling and feedstock delivery.
    Minimizes total vessel cost while ensuring all feedstock requirements are met.
    """
    
    def __init__(self, feedstock_requirements: List[FeedstockRequirement], 
                 routes: Dict[str, Route],  # <-- Fixed: Dict instead of List
                 vessel_types: List[Dict]):
        """
        Initialize the vessel optimizer.
        
        Args:
            feedstock_requirements: List of feedstock requirements to be fulfilled
            routes: Dictionary of routes (key format: "{origin}_{destination}")
            vessel_types: List of available vessel types with their capacities and costs
        """
        self.requirements = feedstock_requirements
        self.routes = routes
        self.vessel_types = vessel_types
    
    def optimize(self, horizon_days: int =30, time_limit_seconds: int = 300) -> List[Vessel]:
        """
        Optimize vessel scheduling to minimize costs
        
        Args:
            horizon_days: Number of days to optimize for
            time_limit_seconds: Maximum solving time in seconds
            
        Returns:
            List of scheduled vessels with cargo
        """
        model = self._build_optimization_model(horizon_days)
        
        # Set time limit for solver
        solver = plp.PULP_CBC_CMD(timeLimit=time_limit_seconds)
        model.solve(solver)
        
        # Even if not optimal, extract the best solution found
        print(f"Optimization status: {plp.LpStatus[model.status]}")
        if model.status == plp.LpStatusOptimal:
            print("Found optimal solution")
        else:
            print(f"Best solution found within {time_limit_seconds} seconds")

        vessels = self._extract_solution(model)
        return vessels
    
    def optimize_and_save(self, horizon_days: int = 30) -> List[Vessel]:
        """
        Optimize vessel scheduling and save results to vessels.json
        
        Args:
            horizon_days: Planning horizon in days
            
        Returns:
            List of scheduled vessels
        """
        vessels = self.optimize(horizon_days)
        
        # Plan optimal routes for multi-cargo vessels
        print(f"Planning routes for {len(vessels)} vessels...")
        vessels = self._plan_vessel_routes(vessels)
        
        # Check if routes were created
        vessels_with_routes = sum(1 for v in vessels if hasattr(v, "route") and v.route)
        print(f"Routes created for {vessels_with_routes} out of {len(vessels)} vessels")
        
        # Convert to JSON format
        vessels_dict = {}
        
        # Initialize vessel_routes dictionary - all vessels start from PM
        vessel_routes = {}
        
        for vessel in vessels:
            # Ensure vessel has a route property
            if not hasattr(vessel, "route") or not vessel.route:
                # Find the cargo origin(s)
                origins = set(cargo.origin for cargo in vessel.cargo)
                if origins:
                    route = []
                    # Create a simple direct route for each origin
                    for origin in origins:
                        route_key = self._get_route_key(origin, "Refinery")
                        travel_days = self.routes[route_key].time_travel if route_key and route_key in self.routes else 3
                        
                        # Add refinery to origin leg
                        route.append({
                            "from": "Refinery",
                            "to": origin,
                            "day": vessel.arrival_day - travel_days - 1,
                            "travel_days": travel_days
                        })
                        
                        # Add origin to refinery leg
                        route.append({
                            "from": origin,
                            "to": "Refinery",
                            "day": vessel.arrival_day,
                            "travel_days": travel_days
                        })
                    
                    vessel.route = route
                    print(f"Created fallback route for {vessel.vessel_id}")
            
            # Convert to JSON format with route data
            vessels_dict[vessel.vessel_id] = {
                "vessel_id": vessel.vessel_id,
                "arrival_day": vessel.arrival_day,
                "capacity": vessel.capacity,
                "cost": vessel.cost,
                "days_held": vessel.days_held,
                "cargo": [
                    {
                        "grade": cargo_item.grade,
                        "volume": cargo_item.volume,
                        "origin": cargo_item.origin,
                        "loading_start_day": cargo_item.loading_start_day,
                        "loading_end_day": cargo_item.loading_end_day
                    }
                    for cargo_item in vessel.cargo
                ],
                "route": vessel.route if hasattr(vessel, "route") else []
            }
            
            # Generate day-by-day vessel routes
            days_dict = {}
            current_location = "Peninsular Malaysia"  # All vessels start at PM
            max_day = max(segment["day"] for segment in vessel.route) if vessel.route else vessel.arrival_day
            
            # Initialize vessel_routes entry
            vessel_routes[vessel.vessel_id] = {
                "start_location": "Peninsular Malaysia",
                "days": {}
            }
            
            # For each day, determine where the vessel is
            for day in range(int(max_day + 1)):
                # Check if we're at the beginning of a route segment
                location_found = False
                
                if vessel.route:
                    for segment in vessel.route:
                        # If this is the start day of a route segment
                        start_day = segment["day"] - segment["travel_days"]
                        end_day = segment["day"]
                        
                        # If we're at exactly the start day - vessel is at "from" location
                        if day == start_day:
                            current_location = segment["from"]
                            location_found = True
                            break
                        
                        # If we're at exactly the end day - vessel is at "to" location
                        elif day == end_day:
                            current_location = segment["to"]
                            location_found = True
                            break
                            
                        # If we're in transit between locations
                        elif start_day < day < end_day:
                            current_location = f"en_route_to_{segment['to']}"
                            location_found = True
                            break
                
                # If no segment matched this day, vessel stays in the last known location
                days_dict[str(day)] = current_location
            
            # Add days dictionary to vessel_routes
            vessel_routes[vessel.vessel_id]["days"] = days_dict
        
        # Log route data to help debug
        for vessel_id, vessel_data in vessels_dict.items():
            route_count = len(vessel_data.get("route", []))
            print(f"Vessel {vessel_id}: {route_count} route segments")
            if route_count > 0:
                for i, segment in enumerate(vessel_data["route"]):
                    print(f"  Segment {i}: {segment['from']} to {segment['to']} (Day {segment['day']} - travel: {segment['travel_days']})")
        
        # Save to vessels.json
        save_path = os.path.join(os.path.dirname(__file__), "..", "dynamic_data", "vessels.json")
        print(f"Saving vessels data to {save_path}")
        with open(save_path, 'w') as f:
            json.dump(vessels_dict, f, indent=2)
        
        # Save to vessel_routes.json
        routes_save_path = os.path.join(os.path.dirname(__file__), "..", "dynamic_data", "vessel_routes.json")
        print(f"Saving vessel routes data to {routes_save_path}")
        with open(routes_save_path, 'w') as f:
            json.dump(vessel_routes, f, indent=2)
        
        return vessels
    
    def _build_optimization_model(self, horizon_days: int) -> plp.LpProblem:
        """
        Build the optimization model for vessel scheduling.
        """
        # Create a linear programming problem
        model = plp.LpProblem("Vessel_Scheduling_Optimization", plp.LpMinimize)
        
        # Store horizon days for later use
        model.horizon_days = horizon_days

        # Create decision variables for vessel type selection and loading
        # y[v_type, day] = 1 if vessel of type v_type is scheduled on day
        y = {}
        for v_idx, vessel_type in enumerate(self.vessel_types):
            for day in range(1, horizon_days+1):
                y[(v_idx, day)] = plp.LpVariable(f"Use_Vessel_{v_idx}_Day_{day}", 
                                                cat='Binary')
        
        # x[v_idx, day, req_idx] = volume of requirement req_idx loaded on vessel v_idx on day
        x = {}
        for v_idx, _ in enumerate(self.vessel_types):
            for day in range(1, horizon_days+1):
                for req_idx, req in enumerate(self.requirements):
                    x[(v_idx, day, req_idx)] = plp.LpVariable(
                        f"Load_Vessel_{v_idx}_Day_{day}_Req_{req_idx}", 
                        lowBound=0, 
                        cat='Continuous')
        
        # NEW: Preprocess to avoid unnecessary variables - MOVED UP
        # Group requirements by grade for faster lookup
        requirements_by_grade = {}
        for req_idx, req in enumerate(self.requirements):
            if req.grade not in requirements_by_grade:
                requirements_by_grade[req.grade] = []
            requirements_by_grade[req.grade].append((req_idx, req))
        
        # Get all unique grades
        all_grades = set(req.grade for req in self.requirements)
        
        # Only add relevant grade variables and constraints
        relevant_grades_by_vessel = {}
        for v_idx, vessel_type in enumerate(self.vessel_types):
            relevant_grades_by_vessel[v_idx] = set()
            
            for grade, reqs in requirements_by_grade.items():
                # Check if this vessel type could practically carry this grade
                if any(req.volume <= vessel_type["capacity"] for _, req in reqs):
                    relevant_grades_by_vessel[v_idx].add(grade)
        
        # NEW: Create binary variables to track which grades are loaded - COMBINED
        z = {}
        for v_idx, vessel_type in enumerate(self.vessel_types):
            relevant_grades = relevant_grades_by_vessel[v_idx]
            for day in range(1, horizon_days+1):
                for grade in relevant_grades:  # Only relevant grades!
                    z[(v_idx, day, grade)] = plp.LpVariable(
                        f"Grade_{grade}_on_Vessel_{v_idx}_Day_{day}", 
                        cat='Binary')
        
        # Objective function: Minimize total cost of vessels
        model += plp.lpSum([self.vessel_types[v_idx]["cost"] * y[(v_idx, day)] 
                           for v_idx in range(len(self.vessel_types))
                           for day in range(1, horizon_days+1)]), "Total_Cost"
        
        # Constraints: Ensure all feedstock requirements are met
        for req_idx, req in enumerate(self.requirements):
            model += plp.lpSum([x[(v_idx, day, req_idx)] 
                               for v_idx in range(len(self.vessel_types))
                               for day in range(1, horizon_days+1)]) >= req.volume, \
                    f"Feedstock_Requirement_{req_idx}"
        
        # Constraints: Ensure vessels do not exceed their capacity
        for v_idx in range(len(self.vessel_types)):
            for day in range(1, horizon_days+1):
                model += plp.lpSum([x[(v_idx, day, req_idx)] 
                                   for req_idx in range(len(self.requirements))]) <= \
                        self.vessel_types[v_idx]["capacity"] * y[(v_idx, day)], \
                        f"Vessel_Capacity_{v_idx}_{day}"
        
        # Constraints: Only load if vessel is used
        for v_idx in range(len(self.vessel_types)):
            for day in range(1, horizon_days+1):
                for req_idx in range(len(self.requirements)):
                    model += x[(v_idx, day, req_idx)] <= \
                            self.vessel_types[v_idx]["capacity"] * y[(v_idx, day)], \
                            f"Load_If_Used_{v_idx}_{day}_{req_idx}"
        
        # NEW: Link binary grade variables to loading variables
        for v_idx in range(len(self.vessel_types)):
            relevant_grades = relevant_grades_by_vessel[v_idx]
            for day in range(1, horizon_days+1):
                for grade in relevant_grades:
                    # Find all requirements with this grade
                    req_indices = [idx for idx, req in enumerate(self.requirements) if req.grade == grade]
                    
                    # If any requirement with this grade is loaded, set z = 1
                    for req_idx in req_indices:
                        model += x[(v_idx, day, req_idx)] <= \
                                self.vessel_types[v_idx]["capacity"] * z[(v_idx, day, grade)], \
                                f"Grade_Used_{v_idx}_{day}_{grade}_{req_idx}"
                    
                    # Only set z = 1 if there's actual volume loaded
                    model += plp.lpSum([x[(v_idx, day, req_idx)] for req_idx in req_indices]) >= \
                            0.001 * z[(v_idx, day, grade)], \
                            f"Grade_Not_Used_{v_idx}_{day}_{grade}"
        
        # NEW: Constraint - maximum 3 grades per vessel (with unique constraint names)
        for v_idx in range(len(self.vessel_types)):
            capacity = self.vessel_types[v_idx]["capacity"]
            for day in range(1, horizon_days+1):
                # Limit number of binary z variables that can be 1 based on capacity
                model += plp.lpSum([z[(v_idx, day, grade)] for grade in relevant_grades_by_vessel[v_idx]]) <= 3, \
                        f"Max_Three_Grades_v{v_idx}_d{day}"
                
                # Add a valid inequality: if no vessel is used, no grades can be assigned
                model += plp.lpSum([z[(v_idx, day, grade)] for grade in relevant_grades_by_vessel[v_idx]]) <= 3 * y[(v_idx, day)], \
                        f"No_Grades_If_No_Vessel_v{v_idx}_d{day}"
        
        # Store decision variables for solution extraction
        self._y_vars = y
        self._x_vars = x
        self._z_vars = z  # Store new variables
            
        return model

    def _extract_solution(self, model: plp.LpProblem) -> List[Vessel]:
        """
        Extract the solution from the optimization model.
        params model: plp.LpProblem the optimization model
        return: List[Vessel] the list of scheduled vessels with their cargo
        """
        vessels = []
        
        # Check if model was solved successfully
        if model.status != plp.LpStatusOptimal:
            print(f"Warning: Optimization did not reach optimal status. Status: {model.status}")
            return vessels
            
        # For each vessel type and day
        for v_idx, vessel_type in enumerate(self.vessel_types):
            for day in range(1, model.horizon_days+1 if hasattr(model, 'horizon_days') else 60):
                # Check if this vessel is used
                var_name = f"Use_Vessel_{v_idx}_Day_{day}"
                if var_name in model.variablesDict() and model.variablesDict()[var_name].varValue > 0.5:
                    # Create cargo for this vessel
                    cargo = []
                    
                    # Check what requirements are loaded on this vessel
                    for req_idx, req in enumerate(self.requirements):
                        var_name = f"Load_Vessel_{v_idx}_Day_{day}_Req_{req_idx}"
                        if var_name in model.variablesDict():
                            volume = model.variablesDict()[var_name].varValue
                            if volume > 0.001:  # Small tolerance for numerical issues
                                # Calculate arrival day based on route travel time
                                route_key = self._get_route_key(req.origin, "Refinery")
                                travel_time = 7.0  # Default fallback
                                if route_key and route_key in self.routes:
                                    travel_time = self.routes[route_key].time_travel
                                
                                # Create feedstock parcel
                                cargo.append(FeedstockParcel(
                                    grade=req.grade,
                                    volume=volume,
                                    ldr={day: day+1},  # Simple loading window
                                    origin=req.origin,
                                    vessel_id=f"Vessel_{v_idx}_{day}"
                                ))
                    
                    # If this vessel has cargo, add it to the list
                    if cargo:
                        # Calculate arrival day (use earliest arrival from all routes)
                        arrival_times = []
                        for parcel in cargo:
                            route_key = self._get_route_key(parcel.origin, "Refinery")
                            if route_key:
                                arrival_times.append(day + int(self.routes[route_key].time_travel))
                        
                        arrival_day = min(arrival_times) if arrival_times else day + 7
                        
                        vessels.append(Vessel(
                            vessel_id=f"Vessel_{v_idx}_{day}",
                            arrival_day=arrival_day,
                            cost=vessel_type["cost"],
                            capacity=vessel_type["capacity"],
                            cargo=cargo,
                            days_held=0
                        ))
        
        return vessels
    
    def _plan_vessel_routes(self, vessels: List[Vessel]) -> List[Vessel]:
        """
        Plan optimal routes for vessels with multiple cargo items
        """
        # Add debug code to understand the structure of routes dictionary
        print("\n=== ROUTE PLANNING DEBUG ===")
        print(f"Available routes: {list(self.routes.keys())}")
        
        # Check for missing origins in routes
        all_origins = set()
        for vessel in vessels:
            for cargo in vessel.cargo:
                all_origins.add(cargo.origin)
        
        print(f"All cargo origins: {all_origins}")
        
        # Check which routes are missing
        missing_routes = []
        for origin in all_origins:
            route_key = self._get_route_key(origin, "Refinery") 
            if not route_key:
                missing_routes.append(f"{origin}-Refinery")
        
        if missing_routes:
            print(f"WARNING: Missing routes: {missing_routes}")
            print("Will use default travel times for these routes")

        for vessel in vessels:
            # If vessel has multiple cargo items from different origins
            if len(set(cargo.origin for cargo in vessel.cargo)) > 1:
                # Start at refinery (day 0)
                current_location = "Refinery"
                current_day = 0
                
                # Collect all origins needed
                origins_to_visit = set(cargo.origin for cargo in vessel.cargo)
                route_plan = []
                
                # Keep track of where we've been
                visited = set()
                
                # While we still have places to visit
                while origins_to_visit:
                    best_next = None
                    best_time = float('inf')
                    
                    # Find closest unvisited origin
                    for origin in origins_to_visit:
                        route_key = self._get_route_key(current_location, origin)
                        
                        if route_key:
                            travel_time = self.routes[route_key].time_travel
                            if travel_time < best_time:
                                best_time = travel_time
                                best_next = origin
                    
                    if best_next:
                        # Update current location and day
                        current_day += best_time
                        route_plan.append({
                            "from": current_location,
                            "to": best_next,
                            "day": current_day,
                            "travel_days": best_time
                        })
                        
                        # Update cargo loading days for this origin
                        for cargo in vessel.cargo:
                            if cargo.origin == best_next:
                                cargo.loading_start_day = int(current_day)
                                cargo.loading_end_day = int(current_day) + 1  # 1 day for loading
                        
                        # Spend a day loading
                        current_day += 1
                        
                        current_location = best_next
                        origins_to_visit.remove(best_next)
                        visited.add(best_next)
                    else:
                        # No route found, break the loop
                        break
                
                # Finally, return to refinery
                route_key = self._get_route_key(current_location, "Refinery")
                
                if route_key:
                    travel_time = self.routes[route_key].time_travel
                else:
                    # Default if no route found
                    travel_time = 7
                
                current_day += travel_time
                route_plan.append({
                    "from": current_location,
                    "to": "Refinery",
                    "day": current_day,
                    "travel_days": travel_time
                })
                
                # Update vessel arrival day and route
                vessel.arrival_day = int(current_day)
                vessel.route = route_plan
            else:
                # Single origin - simpler route calculation
                origin = vessel.cargo[0].origin if vessel.cargo else None
                if origin:
                    # Calculate route from refinery to origin
                    refinery_to_origin_key = self._get_route_key("Refinery", origin)
                    origin_to_refinery_key = self._get_route_key(origin, "Refinery")
                    
                    # Calculate travel times (now always have valid keys)
                    to_origin_time = self.routes[refinery_to_origin_key].time_travel 
                    from_origin_time = self.routes[origin_to_refinery_key].time_travel
                    
                    # Calculate loading days
                    loading_start = max(0, vessel.arrival_day - from_origin_time - 1)
                    loading_end = loading_start + 1
                    
                    # Update cargo loading days
                    for cargo in vessel.cargo:
                        cargo.loading_start_day = loading_start
                        cargo.loading_end_day = loading_end
                    
                    # Create full route
                    vessel.route = [
                        {
                            "from": "Refinery",
                            "to": origin,
                            "day": loading_start - to_origin_time,
                            "travel_days": to_origin_time
                        },
                        {
                            "from": origin,
                            "to": "Refinery",
                            "day": vessel.arrival_day,
                            "travel_days": from_origin_time
                        }
                    ]
                    
                    # Fix negative days if they occur
                    if vessel.route[0]["day"] < 0:
                        vessel.route[0]["day"] = 0
        
        return vessels
    
    def visualize_schedule(self, vessels: List[Vessel]) -> None:
        """
        Visualize the optimized vessel schedule.
        args:
        vessels: List of scheduled vessels
        """
        # Visualization logic goes here
        try:
            import matplotlib.pyplot as plt
            import pandas as pd

            # Create a DataFrame for visualization
            data = []
            for vessel in vessels:
                for parcel in vessel.cargo:
                    data.append({
                        'Vessel': vessel.vessel_id,
                        'Grade': parcel.grade,
                        'Volume': parcel.volume,
                        'Arrival Day': vessel.arrival_day
                    })
            df = pd.DataFrame(data)

            # Plot the schedule
            plt.figure(figsize=(10, 6))
            for grade in df['Grade'].unique():
                subset = df[df['Grade'] == grade]
                plt.bar(subset['Vessel'], subset['Volume'], label=grade)

            plt.xlabel('Vessel')
            plt.ylabel('Volume')
            plt.title('Optimized Vessel Schedule')
            plt.legend()
            plt.show()
        except ImportError:
            print("Matplotlib is not installed. Cannot visualize schedule.")

    # Add this helper method to VesselOptimizer class
    def _get_route_key(self, origin, destination):
        """Find the appropriate route key format that exists in the routes dictionary"""
        # Try various formats
        possible_keys = [
            f"{origin}_{destination}",
            f"{origin} to {destination}",
            f"{origin}-{destination}",
            # Add case variations
            f"{origin.lower()} to {destination.lower()}",
            f"{origin} to {destination.lower()}",
            f"{origin.lower()} to {destination}"
        ]
        
        # Debug info
        print(f"Looking for route: {origin} to {destination}")
        print(f"Available routes: {list(self.routes.keys())}")
        
        for key in possible_keys:
            if key in self.routes:
                print(f"Found exact match: {key}")
                return key
        
        # Check common abbreviations (like PM -> Peninsular Malaysia)        
        if origin == "PM":
            alt_origin = "Peninsular Malaysia"
            for route_key in self.routes.keys():
                if alt_origin.lower() in route_key.lower() and destination.lower() in route_key.lower():
                    print(f"Found match with PM expansion: {route_key}")
                    return route_key
                    
        # If no exact match, try case-insensitive matching
        for route_key in self.routes.keys():
            # Try more flexible matching
            orig_part = origin.lower().replace(" ", "")
            dest_part = destination.lower().replace(" ", "")
            route_key_simple = route_key.lower().replace(" ", "")
            
            if orig_part in route_key_simple and dest_part in route_key_simple:
                print(f"Found fuzzy match: {route_key}")
                return route_key
        
        # For legacy or custom locations that might not be in routes.json
        if origin not in ["Sabah", "Sarawak", "Peninsular Malaysia", "Refinery"] or destination not in ["Sabah", "Sarawak", "Peninsular Malaysia", "Refinery"]:
            print(f"Creating dummy route for custom location: {origin} to {destination}")
            default_travel_time = 5  # Longer default for custom locations
        else:
            print(f"Creating dummy route: {origin} to {destination}")
            default_travel_time = 3
        
        # Create a new key and add it to routes
        new_key = f"{origin} to {destination}"
        try:
            self.routes[new_key] = Route(
                origin=origin,
                destination=destination,
                time_travel=default_travel_time,
                cost=10000  # Default cost
            )
            print(f"Created new route: {new_key}")
            return new_key
        except Exception as e:
            print(f"ERROR creating route: {e}")
            # Fall back to creating a dictionary route if Route object fails
            self.routes[new_key] = {
                "origin": origin,
                "destination": destination,
                "time_travel": default_travel_time
            }
            # Last resort fallback - return a key to avoid crashes
            # even if the route doesn't exist
            return list(self.routes.keys())[0] if self.routes else "fallback_route"