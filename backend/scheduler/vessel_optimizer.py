"""
Vessel Optimizer class for OASIS sytem. The auxiliary optimizer that will work
with main scheduling optimizer to optimize the operating rates by optimizing the vessel
delivery and volume. Target: right volume at the right time.

Copyright (c) by Abu Huzaifah Bidin with help from Github Copilot

"""

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
    
    def _build_optimization_model(self, horizon_days: int) -> plp.LpProblem:
        """
        Build the optimization model for vessel scheduling.
        params horizon_days: int the number of days to optimize for
        return: plp.LpProblem the optimization model
        """
        # Create a linear programming problem
        model = plp.LpProblem("Vessel_Scheduling_Optimization", plp.LpMinimize)

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
                                route_key = f"{req.origin}_Refinery"
                                travel_time = self.routes[route_key].time_travel if route_key in self.routes else 7.0
                                
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
                            route_key = f"{parcel.origin}_Refinery"
                            if route_key in self.routes:
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