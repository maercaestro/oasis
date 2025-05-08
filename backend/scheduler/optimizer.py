"""
OASIS Base Scheduler/optimizer.py
This module refines schedules created by the main scheduler to optimize for margin or throughput.
Copyright (c) by Abu Huzaifah Bidin with help from Github Copilot
"""
import pulp as plp
from typing import List, Dict, Optional, Tuple, Set
from .models import Tank, BlendingRecipe, FeedstockParcel, Vessel, DailyPlan, Crude
from .blending import BlendingEngine

class SchedulerOptimizer:
    """
    Optimizer for refining and improving refinery schedules created by the main scheduler.
    Can optimize for either maximum throughput or maximum margin.
    """

    def __init__(self, blending_recipes: List[BlendingRecipe],
                 crude_data: Dict[str, Crude], max_processing_rate: float):
        """
        Initialize the schedule optimizer.

        args:
        blending_recipes: List[BlendingRecipe] - List of available blending recipes.
        crude_data: Dict[str, Crude] - Dictionary of crude data.
        max_processing_rate: float - Maximum daily processing rate for the refinery.
        """
        self.blending_recipes = blending_recipes
        self.crude_data = crude_data
        self.max_processing_rate = max_processing_rate
        self.blending_engine = BlendingEngine()

    def optimize_throughput(self, existing_schedule: List[DailyPlan], vessels: List[Vessel] = None) -> List[DailyPlan]:
        """
        Optimize an existing schedule for maximum throughput.

        args:
        existing_schedule: List[DailyPlan] - The existing schedule to optimize
        vessels: List[Vessel] - Optional list of vessels arriving during the planning period

        return: List[DailyPlan] - List of optimized daily plans
        """
        return self._optimize(existing_schedule, vessels, objective="throughput")
    
    def optimize_margin(self, existing_schedule: List[DailyPlan], vessels: List[Vessel] = None) -> List[DailyPlan]:
        """
        Optimize an existing schedule for maximum margin.
        
        args:
        existing_schedule: List[DailyPlan] - The existing schedule to optimize
        vessels: List[Vessel] - Optional list of vessels arriving during the planning period
        
        return: List[DailyPlan] - List of optimized daily plans
        """
        return self._optimize(existing_schedule, vessels, objective="margin")
    
    def _optimize(self, existing_schedule: List[DailyPlan], vessels: List[Vessel], objective: str) -> List[DailyPlan]:
        """
        Optimize the refinery schedule using multi-period optimization.

        args:
        existing_schedule: List[DailyPlan] - The existing schedule to optimize
        vessels: List[Vessel] - List of vessels arriving during the planning period
        objective: str - Objective to optimize for. Can be "throughput" or "margin"

        return: List[DailyPlan] - List of optimized daily plans
        """
        # Determine the planning horizon based on the existing schedule
        days = len(existing_schedule)
        
        # Extract initial tank state from the first day of the existing schedule
        initial_tanks = existing_schedule[0].tanks
        
        # Create the optimization model
        model = plp.LpProblem("Schedule_Refinement", plp.LpMaximize)
        
        # Get all unique crude grades in the system
        all_grades = self._get_all_grades(existing_schedule, vessels)
        
        # DECISION VARIABLES
        
        # 1. Processing rate for each recipe on each day
        rates = {}
        for day in range(1, days+1):
            for recipe in self.blending_recipes:
                rates[(day, recipe.name)] = plp.LpVariable(
                    f"Rate_Day{day}_{recipe.name}", 
                    lowBound=0, 
                    upBound=recipe.max_rate
                )
        
        # 2. Inventory tracking variables for each grade on each day
        inventory = {}
        for day in range(0, days+1):  # Day 0 is initial inventory
            for grade in all_grades:
                inventory[(day, grade)] = plp.LpVariable(
                    f"Inventory_Day{day}_{grade}", 
                    lowBound=0
                )
        
        # CONSTRAINTS
        
        # 1. Set initial inventory (day 0) from first day of schedule
        for grade in all_grades:
            initial_amount = existing_schedule[0].inventory_by_grade.get(grade, 0)
            model += inventory[(0, grade)] == initial_amount, f"Initial_{grade}"
        
        # 2. Inventory balance constraints for each day and grade
        for day in range(1, days+1):
            for grade in all_grades:
                # Consumption from recipes
                consumption = plp.lpSum([
                    # Primary grade consumption
                    rates[(day, recipe.name)] * recipe.primary_fraction 
                    for recipe in self.blending_recipes 
                    if recipe.primary_grade == grade
                ]) + plp.lpSum([
                    # Secondary grade consumption
                    rates[(day, recipe.name)] * (1.0 - recipe.primary_fraction) 
                    for recipe in self.blending_recipes 
                    if recipe.secondary_grade == grade
                ])
                
                # Deliveries from vessels arriving today
                delivery = plp.lpSum([
                    parcel.volume
                    for vessel in (vessels or [])
                    if vessel.arrival_day == day
                    for parcel in vessel.cargo
                    if parcel.grade == grade
                ])
                
                # Inventory balance: previous + deliveries - consumption = current
                model += (
                    inventory[(day-1, grade)] + delivery - consumption == inventory[(day, grade)]
                ), f"Balance_Day{day}_{grade}"
        
        # 3. Processing capacity constraint for each day
        for day in range(1, days+1):
            model += plp.lpSum([
                rates[(day, recipe.name)] 
                for recipe in self.blending_recipes
            ]) <= self.max_processing_rate, f"Capacity_Day{day}"
        
        # 4. Inventory must be sufficient for processing
        for day in range(1, days+1):
            for recipe in self.blending_recipes:
                # Primary grade must be available
                if recipe.primary_grade in all_grades:
                    model += rates[(day, recipe.name)] * recipe.primary_fraction <= inventory[(day-1, recipe.primary_grade)], \
                           f"PrimaryAvail_Day{day}_{recipe.name}"
                
                # Secondary grade must be available (if needed)
                if recipe.secondary_grade and recipe.secondary_grade in all_grades:
                    model += rates[(day, recipe.name)] * (1.0 - recipe.primary_fraction) <= inventory[(day-1, recipe.secondary_grade)], \
                           f"SecondaryAvail_Day{day}_{recipe.name}"
        
        # OBJECTIVE FUNCTION
        
        if objective == "throughput":
            # Maximize total throughput across planning horizon
            model += plp.lpSum([
                rates[(day, recipe.name)]
                for day in range(1, days+1)
                for recipe in self.blending_recipes
            ]), "Total_Throughput"
        else:  # margin
            # Maximize total margin across planning horizon
            model += plp.lpSum([
                rates[(day, recipe.name)] * self.blending_engine.blend_margin(recipe, self.crude_data)
                for day in range(1, days+1)
                for recipe in self.blending_recipes
            ]), "Total_Margin"
        
        # Optional: add constraints to limit deviation from original schedule
        # This can be enabled if you want the optimized schedule to stay close to the original
        enable_deviation_limit = False
        if enable_deviation_limit:
            max_deviation = 0.2  # Maximum 20% deviation from original
            for day in range(1, days+1):
                for recipe in self.blending_recipes:
                    # Get original rate from existing schedule
                    original_rate = existing_schedule[day-1].processing_rates.get(recipe.name, 0)
                    if original_rate > 0:
                        # Limit deviation from original rate
                        model += rates[(day, recipe.name)] >= original_rate * (1 - max_deviation), f"MinDev_Day{day}_{recipe.name}"
                        model += rates[(day, recipe.name)] <= original_rate * (1 + max_deviation), f"MaxDev_Day{day}_{recipe.name}"
        
        # Solve the model
        model.solve(plp.PULP_CBC_CMD(msg=False))
        
        if model.status != plp.LpStatusOptimal:
            print(f"Warning: Optimization did not reach optimal status. Status: {model.status}")
            return existing_schedule  # Return original schedule if optimization failed
        
        # Extract solution into daily plans
        optimized_plans = []
        
        for day in range(1, days+1):
            # Get processing rates for this day
            processing_rates = {}
            blending_details = []
            
            for recipe in self.blending_recipes:
                rate_value = rates[(day, recipe.name)].value()
                if rate_value > 0.001:  # Ignore very small rates
                    processing_rates[recipe.name] = rate_value
                    blending_details.append(recipe)
            
            # Get inventory by grade for this day
            inventory_by_grade = {}
            for grade in all_grades:
                inv_value = inventory[(day, grade)].value()
                if inv_value > 0.001:  # Ignore very small inventories
                    inventory_by_grade[grade] = inv_value
            
            # Calculate total inventory
            total_inventory = sum(inventory_by_grade.values())
            
            # Get tanks from original schedule but adjust content to match new inventory
            # This is a simplification - in practice you would need a more sophisticated
            # algorithm to distribute inventory among tanks
            adjusted_tanks = self._adjust_tank_contents(existing_schedule[day-1].tanks, inventory_by_grade)
            
            # Create daily plan
            daily_plan = DailyPlan(
                day=day,
                processing_rates=processing_rates,
                blending_details=blending_details,
                inventory=total_inventory,
                inventory_by_grade=inventory_by_grade,
                tanks=adjusted_tanks
            )
            
            optimized_plans.append(daily_plan)
        
        return optimized_plans
    
    def _get_all_grades(self, existing_schedule: List[DailyPlan], vessels: List[Vessel] = None) -> Set[str]:
        """Get all crude grades used in the system."""
        grades = set()
        
        # Grades from recipes
        for recipe in self.blending_recipes:
            if recipe.primary_grade:
                grades.add(recipe.primary_grade)
            if recipe.secondary_grade:
                grades.add(recipe.secondary_grade)
        
        # Grades in existing schedule
        for plan in existing_schedule:
            for grade in plan.inventory_by_grade:
                grades.add(grade)
        
        # Grades in arriving vessels
        if vessels:
            for vessel in vessels:
                for parcel in vessel.cargo:
                    grades.add(parcel.grade)
        
        return grades
    
    def _adjust_tank_contents(self, original_tanks: Dict[str, Tank], inventory_by_grade: Dict[str, float]) -> Dict[str, Tank]:
        """
        Adjust tank contents to match new inventory levels while preserving tank structure.
        
        args:
        original_tanks: Dict[str, Tank] - Original tank state
        inventory_by_grade: Dict[str, float] - Target inventory by grade
        
        return: Dict[str, Tank] - Adjusted tank contents
        """
        # Copy tank structure
        adjusted_tanks = {}
        for name, tank in original_tanks.items():
            adjusted_tanks[name] = Tank(
                name=name,
                capacity=tank.capacity,
                content=[]
            )
        
        # Make a copy of inventory_by_grade that we'll modify as we allocate
        remaining_inventory = inventory_by_grade.copy()
        
        # First pass: try to maintain existing grade-to-tank assignments
        for name, tank in original_tanks.items():
            for content_dict in tank.content:
                for grade in content_dict:
                    if grade in remaining_inventory and remaining_inventory[grade] > 0:
                        # Calculate how much we can put in this tank
                        available_space = tank.capacity - sum(sum(c.values()) for c in adjusted_tanks[name].content)
                        amount = min(remaining_inventory[grade], available_space)
                        
                        if amount > 0:
                            adjusted_tanks[name].content.append({grade: amount})
                            remaining_inventory[grade] -= amount
        
        # Second pass: allocate any remaining inventory to tanks with space
        for grade, volume in list(remaining_inventory.items()):
            if volume > 0.001:  # If there's still inventory to allocate
                for name, tank in adjusted_tanks.items():
                    available_space = tank.capacity - sum(sum(c.values()) for c in tank.content)
                    if available_space > 0:
                        amount = min(volume, available_space)
                        tank.content.append({grade: amount})
                        remaining_inventory[grade] -= amount
                        volume -= amount
                        
                        if volume < 0.001:
                            break
        
        return adjusted_tanks