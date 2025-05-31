"""
OASIS Base Scheduler/optimizer.py
This module refines schedules created by the main scheduler to optimize for margin or throughput.
Copyright (c) by Abu Huzaifah Bidin with help from Github Copilot
"""
from typing import List, Dict, Optional, Tuple, Set
from .models import Tank, BlendingRecipe, FeedstockParcel, Vessel, DailyPlan, Crude
from .blending import BlendingEngine
import pulp as plp
import logging
import sys

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("optimizer_debug.log"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("scheduler.optimizer")

class SchedulerOptimizer:
    """
    Optimizer for refining and improving refinery schedules created by the main scheduler.
    Can optimize for either maximum throughput or maximum margin.
    """
    # Add constant for numerical stability
    EPSILON = 1e-6

    def __init__(self, blending_recipes: List[BlendingRecipe],
                 crude_data: Dict[str, Crude], max_processing_rate: float):
        """
        Initialize the optimizer with recipes and crude data
        """
        self.blending_recipes = blending_recipes
        self.crude_data = crude_data
        self.max_processing_rate = max_processing_rate
        self.blending_engine = BlendingEngine()
        
        logger.info(f"Initialized SchedulerOptimizer with {len(blending_recipes)} recipes")
        logger.info(f"Available crude grades: {list(crude_data.keys())}")
        logger.info(f"Max processing rate: {max_processing_rate}")
        
        # Log recipe details
        for recipe in blending_recipes:
            logger.info(f"Recipe: {recipe.name}, Primary: {recipe.primary_grade} ({recipe.primary_fraction}), "
                      f"Secondary: {recipe.secondary_grade}, Max rate: {recipe.max_rate}")

    def optimize_throughput(self, existing_schedule: List[DailyPlan], vessels: List[Vessel] = None) -> List[DailyPlan]:
        """Optimize the schedule to maximize throughput"""
        logger.info(f"Starting throughput optimization with {len(existing_schedule)} days of schedule")
        if vessels:
            logger.info(f"Using {len(vessels)} provided vessels")
            
        return self._optimize(existing_schedule, vessels, objective="throughput")
    
    def optimize_margin(self, existing_schedule: List[DailyPlan], vessels: List[Vessel] = None) -> List[DailyPlan]:
        """Optimize the schedule to maximize margin"""
        logger.info(f"Starting margin optimization with {len(existing_schedule)} days of schedule")
        if vessels:
            logger.info(f"Using {len(vessels)} provided vessels")
            
        return self._optimize(existing_schedule, vessels, objective="margin")
    
    def _optimize(self, existing_schedule: List[DailyPlan], vessels: List[Vessel] = None, 
                 objective: str = "margin") -> List[DailyPlan]:
        """
        Core optimization function used by both throughput and margin optimization.
        
        Args:
            existing_schedule: List of DailyPlan objects representing the current schedule
            vessels: List of vessels with arrival schedules (optional)
            objective: Either 'margin' or 'throughput' to determine optimization goal
            
        Returns:
            List of optimized DailyPlan objects
        """
        # Check if we have data to optimize
        if not existing_schedule:
            logger.error("No schedule data provided for optimization")
            raise ValueError("No schedule provided for optimization")
        
        logger.info(f"Starting {objective} optimization with {len(existing_schedule)} days")
        logger.info("==== BEGIN OPTIMIZER TRACE ====")
        # Log schedule inventory
        for i, day in enumerate(existing_schedule):
            logger.info(f"Day {day.day}: Inventory = {day.inventory}, Grades = {day.inventory_by_grade}")
            logger.debug(f"Day {day.day}: Tanks = {getattr(day, 'tanks', None)}")
        # Extract initial tanks from first day
        try:
            initial_tanks = existing_schedule[0].tanks
            logger.info(f"Initial tanks: {len(initial_tanks)}")
            for tank_name, tank in initial_tanks.items():
                total = sum(sum(content.values()) for content in tank.content)
                logger.info(f"  Tank {tank_name}: {total} units")
                for content in tank.content:
                    for grade, volume in content.items():
                        logger.info(f"    - {grade}: {volume} units")
        except (IndexError, AttributeError) as e:
            logger.error(f"Failed to extract initial tanks: {e}")
            logger.error(f"Schedule first day: {existing_schedule[0] if existing_schedule else 'No schedule'}")
            raise ValueError(f"Invalid schedule format: {e}")
        # Get all unique crude grades used in the schedule
        all_grades = self._get_all_grades(existing_schedule)
        logger.info(f"Unique grades in schedule: {all_grades}")
        days = len(existing_schedule)
        # Create optimization model
        model = plp.LpProblem(name="refinery_schedule_optimization", sense=plp.LpMaximize)
        logger.info("Created optimization model")
        # Define decision variables:
        rates = {}
        for day in range(1, days+1):
            for recipe in self.blending_recipes:
                var_name = f"rate_{day}_{recipe.name}"
                rates[(day, recipe.name)] = plp.LpVariable(var_name, lowBound=0, upBound=recipe.max_rate)
                logger.debug(f"Created variable: {var_name}, bounds: [0, {recipe.max_rate}]")
        recipe_used = {}
        for day in range(1, days+1):
            for recipe in self.blending_recipes:
                var_name = f"use_{day}_{recipe.name}"
                recipe_used[(day, recipe.name)] = plp.LpVariable(var_name, cat=plp.LpBinary)
                logger.debug(f"Created binary variable: {var_name} for recipe selection")
        inventory = {}
        for day in range(days+1):
            for grade in all_grades:
                var_name = f"inventory_{day}_{grade}"
                inventory[(day, grade)] = plp.LpVariable(var_name, lowBound=0)
                logger.debug(f"Created variable: {var_name}, bounds: [0, None]")
        # Set initial inventory from first day of existing schedule
        for grade in all_grades:
            initial_amount = existing_schedule[0].inventory_by_grade.get(grade, 0)
            model += inventory[(0, grade)] == initial_amount
            logger.info(f"Initial inventory for {grade}: {initial_amount}")
        logger.info("Adding constraints to the model...")
        # Add constraint to ensure only one recipe is used per day
        for day in range(1, days+1):
            one_recipe_constraint = plp.lpSum([recipe_used[(day, recipe.name)] for recipe in self.blending_recipes]) == 1
            model += one_recipe_constraint
            logger.info(f"Day {day}: Added constraint to use exactly one recipe")
        # Link binary variables to processing rates
        M = self.max_processing_rate
        for day in range(1, days+1):
            for recipe in self.blending_recipes:
                model += rates[(day, recipe.name)] <= M * recipe_used[(day, recipe.name)]
                model += rates[(day, recipe.name)] <= recipe.max_rate
                logger.debug(f"Day {day}, {recipe.name}: Linked binary selection to processing rate")
        # Maximum processing rate per day
        for day in range(1, days+1):
            constraint = plp.lpSum([rates[(day, recipe.name)] for recipe in self.blending_recipes]) <= self.max_processing_rate
            model += constraint
            logger.debug(f"Day {day} max processing: <= {self.max_processing_rate}")
        # Inventory balance constraints
        for day in range(1, days+1):
            for grade in all_grades:
                consumption = 0
                for recipe in self.blending_recipes:
                    if recipe.primary_grade == grade:
                        consumption += rates[(day, recipe.name)] * recipe.primary_fraction
                    if recipe.secondary_grade == grade:
                        consumption += rates[(day, recipe.name)] * (1 - recipe.primary_fraction)
                arrivals = 0
                if vessels:
                    for vessel in vessels:
                        if vessel.arrival_day == day:
                            for cargo in vessel.cargo:
                                if cargo.grade == grade:
                                    arrivals += cargo.volume
                                    logger.info(f"Day {day}: {cargo.volume} units of {grade} arriving")
                constraint = inventory[(day, grade)] == inventory[(day-1, grade)] - consumption + arrivals
                model += constraint
                logger.debug(f"Day {day}, {grade} balance: today = yesterday - {consumption} + {arrivals}")
        # Recipe feasibility constraints
        for day in range(1, days+1):
            for recipe in self.blending_recipes:
                primary_constraint = rates[(day, recipe.name)] * recipe.primary_fraction <= inventory[(day-1, recipe.primary_grade)]
                model += primary_constraint
                logger.debug(f"Day {day}, {recipe.name} primary limit: <= {recipe.primary_grade} inventory")
                if recipe.secondary_grade:
                    secondary_constraint = rates[(day, recipe.name)] * (1 - recipe.primary_fraction) <= inventory[(day-1, recipe.secondary_grade)]
                    model += secondary_constraint
                    logger.debug(f"Day {day}, {recipe.name} secondary limit: <= {recipe.secondary_grade} inventory")
        # Set objective function based on parameter
        logger.info(f"Setting objective function for {objective} optimization")
        if objective == "throughput":
            model += plp.lpSum([rates[(day, recipe.name)] for day in range(1, days+1) 
                               for recipe in self.blending_recipes])
            logger.info("Objective: Maximize total processing volume")
        else:
            objective_expr = 0
            for day in range(1, days+1):
                for recipe in self.blending_recipes:
                    margin = self.blending_engine.blend_margin(recipe, self.crude_data)
                    objective_expr += rates[(day, recipe.name)] * margin
                    logger.debug(f"Recipe {recipe.name} margin: {margin}")
            model += objective_expr
            logger.info("Objective: Maximize total margin")
        logger.info("Solving optimization model...")
        time_limit = 1200
        solver = plp.PULP_CBC_CMD(
            msg=True,
            gapRel=0.05,
            timeLimit=time_limit,
            options=['log=2']
        )
        logger.info(f"Using solver with MIP gap=0.05 and time limit={time_limit} seconds")
        model.solve(solver)

        # Check solution status
        status = plp.LpStatus[model.status]
        logger.info(f"Optimization status: {status}")
        
        # --- BEGIN: Extra logging for debugging ---
        # Log all variable values after solving
        logger.info("--- Variable values after solving ---")
        for v in model.variables():
            logger.info(f"{v.name} = {v.varValue}")
        logger.info("--- End variable values ---")

        # Log constraint slacks for key constraints
        logger.info("--- Constraint slacks (key constraints) ---")
        for name, constraint in model.constraints.items():
            slack = constraint.slack if hasattr(constraint, 'slack') else None
            logger.info(f"Constraint {name}: slack={slack}, value={constraint.value() if hasattr(constraint, 'value') else None}")
        logger.info("--- End constraint slacks ---")
        # --- END: Extra logging for debugging ---

        if status != 'Optimal':
            logger.warning(f"Optimization did not complete successfully: {status}")
            if status == 'Infeasible':
                logger.error("The problem has no feasible solution - check constraints")
                # Try to identify which constraints might be causing infeasibility
                self._debug_infeasible_model(model)
            return existing_schedule  # Return the original schedule if optimization fails
        
        # Log objective value
        logger.info(f"Objective value: {plp.value(model.objective)}")
        
        # Create optimized schedule
        logger.info("Creating optimized schedule...")
        optimized_schedule = []
        
        for day_idx in range(days):
            day = day_idx + 1  # Day 1-indexed in the model
            
            # Extract processing rates for this day
            processing_rates = {}
            blend_details = []
            total_processing = 0
            zero_processing = True
            
            for recipe in self.blending_recipes:
                rate_value = rates[(day, recipe.name)].value()
                if rate_value > self.EPSILON:  # Only include non-zero rates
                    processing_rates[recipe.name] = rate_value
                    blend_details.append(recipe)
                    total_processing += rate_value
                    zero_processing = False
                    logger.info(f"Day {day}: Processing {rate_value} units of {recipe.name}")
            if zero_processing:
                logger.warning(f"Day {day}: ZERO processing! Check inventory, constraints, and recipe selection.")
                # Log inventory for this day
                for grade in all_grades:
                    logger.warning(f"Day {day}: Inventory of {grade} = {inventory[(day-1, grade)].value()}")
                # Log recipe_used variables
                for recipe in self.blending_recipes:
                    used_val = recipe_used[(day, recipe.name)].value()
                    logger.warning(f"Day {day}: Recipe {recipe.name} used? {used_val}")
            
            # Calculate inventory for this day
            inventory_by_grade = {}
            total_inventory = 0
            
            for grade in all_grades:
                grade_inventory = inventory[(day, grade)].value()
                if grade_inventory > self.EPSILON:
                    inventory_by_grade[grade] = grade_inventory
                    total_inventory += grade_inventory
                    logger.debug(f"Day {day}: {grade} inventory = {grade_inventory}")

            # Calculate daily margin and update blend_details with margin info
            daily_margin = 0.0
            for recipe_name, rate in processing_rates.items():
                recipe_obj = next((r for r in self.blending_recipes if r.name == recipe_name), None)
                if recipe_obj:
                    recipe_margin = self.blending_engine.blend_margin(recipe_obj, self.crude_data)
                    recipe_total = rate * recipe_margin
                    daily_margin += recipe_total
                    for i, recipe_detail in enumerate(blend_details):
                        if recipe_detail.name == recipe_name:
                            blend_details[i] = BlendingRecipe(
                                name=recipe_detail.name,
                                primary_grade=recipe_detail.primary_grade,
                                secondary_grade=recipe_detail.secondary_grade,
                                max_rate=recipe_detail.max_rate,
                                primary_fraction=recipe_detail.primary_fraction
                            )
                            setattr(blend_details[i], 'margin', recipe_margin)
                            setattr(blend_details[i], 'total_margin', recipe_total)
                            break
            logger.info(f"Day {day}: Total margin = {daily_margin}")
            logger.info(f"Day {day}: Total inventory = {total_inventory}, Processing = {total_processing}")
            if not processing_rates:
                logger.warning(f"Day {day}: No processing occurred (all rates zero)")
            if len(processing_rates) == 1:
                logger.info(f"Day {day}: Only one recipe used")
            if len(processing_rates) > 1:
                logger.info(f"Day {day}: Multiple recipes used (unexpected under current constraints)")
            new_plan = DailyPlan(
                day=day,
                processing_rates=processing_rates,
                blending_details=blend_details,
                inventory=total_inventory,
                inventory_by_grade=inventory_by_grade,
                daily_margin=daily_margin,
                tanks=existing_schedule[day_idx].tanks if day_idx < len(existing_schedule) else {}
            )
            optimized_schedule.append(new_plan)
        logger.info(f"Optimization complete! Created {len(optimized_schedule)} days of schedule")
        logger.info("==== END OPTIMIZER TRACE ====")
        return optimized_schedule
    
    def _get_all_grades(self, schedule: List[DailyPlan]) -> Set[str]:
        """Extract all unique crude grades used in the schedule"""
        grades = set()
        for day in schedule:
            if hasattr(day, 'inventory_by_grade'):
                grades.update(day.inventory_by_grade.keys())
        
        # Also add grades from recipes
        for recipe in self.blending_recipes:
            grades.add(recipe.primary_grade)
            if recipe.secondary_grade:
                grades.add(recipe.secondary_grade)
                
        return grades
    
    def _debug_infeasible_model(self, model):
        """
        Try to identify why a model is infeasible by checking constraints
        """
        logger.info("Debugging infeasible model...")
        
        # Check initial inventory values
        initial_inventory = {}
        for var in model.variables():
            if var.name.startswith("inventory_0_"):
                grade = var.name.replace("inventory_0_", "")
                initial_inventory[grade] = var.value()
                
        logger.info(f"Initial inventory values: {initial_inventory}")
        
        # Check for zero inventory grades that are needed by recipes
        for recipe in self.blending_recipes:
            primary_inv = initial_inventory.get(recipe.primary_grade, 0)
            if primary_inv <= self.EPSILON:
                logger.warning(f"Recipe {recipe.name} needs {recipe.primary_grade} but initial inventory is {primary_inv}")
                
            if recipe.secondary_grade:
                secondary_inv = initial_inventory.get(recipe.secondary_grade, 0)
                if secondary_inv <= self.EPSILON:
                    logger.warning(f"Recipe {recipe.name} needs {recipe.secondary_grade} but initial inventory is {secondary_inv}")
        
        # Check for other potential issues
        if not self.blending_recipes:
            logger.error("No blending recipes provided")
        
        if sum(initial_inventory.values()) <= self.EPSILON:
            logger.error("No initial inventory available")
            
        logger.info("Debug complete - see warnings above for potential causes")