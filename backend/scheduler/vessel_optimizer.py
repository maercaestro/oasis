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
    
    def optimize(self, horizon_days: int =30) -> List[Vessel]:
        """
        Optimize vessel scheduling to minimize costs
        params horizon_days: int the number of days to optimize for
        return: List[Vessel] the list of scheduled vessels with their cargo
        """
        model = self._build_optimization_model(horizon_days)
        model.solve()

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
        vessels = self._plan_vessel_routes(vessels)
        
        # Convert to JSON format
        vessels_dict = {}
        for vessel in vessels:
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
        
        # Save to vessels.json
        save_path = os.path.join(os.path.dirname(__file__), "..", "dynamic_data", "vessels.json")
        with open(save_path, 'w') as f:
            json.dump(vessels_dict, f, indent=2)
            
        return vessels
    
    def _build_optimization_model(self, horizon_days: int) -> plp.LpProblem:
        """
        Build the optimization model for vessel scheduling.
        params horizon_days: int the number of days to optimize for
        return: plp.LpProblem the optimization model
        """
        # Create a linear programming problem
        model = plp.LpProblem("Vessel_Scheduling_Optimization", plp.LpMinimize)
        
        # Store horizon days for later use
        model.horizon_days = horizon_days  # Add this line

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
                            
        # Store decision variables for solution extraction
        self._y_vars = y
        self._x_vars = x
                
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
        
        Args:
            vessels: List of vessels from the optimizer
            
        Returns:
            Vessels with updated routes and loading days
        """
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
                    route_key = self._get_route_key(origin, "Refinery")
                    
                    if route_key:
                        travel_time = self.routes[route_key].time_travel
                    else:
                        travel_time = 7
                    
                    # Calculate loading days
                    loading_start = int(vessel.arrival_day - travel_time - 1)
                    loading_end = loading_start + 1
                    
                    for cargo in vessel.cargo:
                        cargo.loading_start_day = loading_start
                        cargo.loading_end_day = loading_end
                    
                    vessel.route = [
                        {
                            "from": "Refinery",
                            "to": origin,
                            "day": 0,
                            "travel_days": travel_time
                        },
                        {
                            "from": origin,
                            "to": "Refinery",
                            "day": loading_end + 1,
                            "travel_days": travel_time
                        }
                    ]
        
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
            f"{origin}-{destination}"
        ]
        
        for key in possible_keys:
            if key in self.routes:
                return key
                
        # If no exact match, try case-insensitive matching
        for route_key in self.routes.keys():
            if origin.lower() in route_key.lower() and destination.lower() in route_key.lower():
                return route_key
        
        return None  # No matching route found