"""
Vessel Optimizer class for OASIS sytem. The auxiliary optimizer that will work
with main scheduling optimizer to optimize the operating rates by optimizing the vessel
delivery and volume. Target: right volume at the right time.

Copyright (c) by Abu Huzaifah Bidin with help from Github Copilot

"""

from typing import List, Dict, Optional, Tuple
import pulp as plt
from .models import Vessel, FeedstockParcel, FeedstockRequirement, Route

class VesselOptimizer:
    """
    Optimizer for vessel scheduling and feedstock delivery.
    Minimized total vessel cost while ensuring  all feedstock requirements are met.

    """

    def __init__(self, feedstock_requirements: List[FeedstockRequirement], 
                 vessels: List[Vessel], 
                 routes: List[str,Route]):
        """
        Initialize the optimizer with feedstock requirements, vessels, and routes.

        Args:
            feedstock_requirements: List of feedstock requirements
            vessels: List of vessels available for scheduling
            routes: List of routes available for scheduling
        """
        self.feedstock_requirements = feedstock_requirements
        self.vessels = vessels
        self.routes = routes
    
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
    
    def _build_optimization_model(self, horizon_days: int) -> plt.LpProblem:
        """
        Build the optimization model for vessel scheduling.
        params horizon_days: int the number of days to optimize for
        return: plt.LpProblem the optimization model
        """
        # Create a linear programming problem
        model = plt.LpProblem("Vessel_Scheduling_Optimization", plt.LpMinimize)

        # Create decision variables for each vessel and feedstock requirement
        x = plt.LpVariable.dicts("x", 
                                  ((vessel.name, req.grade) for vessel in self.vessels for req in self.feedstock_requirements), 
                                  lowBound=0, 
                                  cat='Continuous')

        # Objective function: Minimize total cost of vessels
        model += plt.lpSum([vessel.cost * x[(vessel.name, req.grade)] for vessel in self.vessels for req in self.feedstock_requirements]), "Total_Cost"

        # Constraints: Ensure all feedstock requirements are met
        for req in self.feedstock_requirements:
            model += plt.lpSum([x[(vessel.name, req.grade)] for vessel in self.vessels]) >= req.volume, f"Feedstock_Requirement_{req.grade}"

        # Constraints: Ensure vessels do not exceed their capacity
        for vessel in self.vessels:
            model += plt.lpSum([x[(vessel.name, req.grade)] for req in self.feedstock_requirements]) <= vessel.capacity, f"Vessel_Capacity_{vessel.name}"

        return model
    def _extract_solution(self, model: plt.LpProblem) -> List[Vessel]:
        """
        Extract the solution from the optimization model.
        params model: plt.LpProblem the optimization model
        return: List[Vessel] the list of scheduled vessels with their cargo
        """
        vessels = []
        for vessel in self.vessels:
            cargo = []
            for req in self.feedstock_requirements:
                volume = model.variablesDict()[f"x_{vessel.name}_{req.grade}"].varValue
                if volume > 0:
                    cargo.append(FeedstockParcel(grade=req.grade, volume=volume, ldr=req.ldr, origin=req.origin))
            vessels.append(Vessel(vessel_id=vessel.vessel_id, arrival_day=vessel.arrival_day, cost=vessel.cost, capacity=vessel.capacity, cargo=cargo))
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