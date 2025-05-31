"""
OASIS Base Scheduler/scheduler.py
The main scheduler module for the OASIS system. This module handles the scheduling logic for the OASIS system.
Copyright (c) by Abu Huzaifah Bidin with help from Github Copilot
"""

from typing import List, Dict, Optional, Tuple, Any
from .models import Tank, BlendingRecipe, FeedstockParcel, Vessel, DailyPlan, Crude
from .blending import BlendingEngine
from .tanks import TankManager
# Add imports for output functionality
from .utils import generate_summary_report, export_schedule_to_excel
import os
import datetime
import json


class Scheduler:
    """
    The main scheduler class for the OASIS system.
    This class is responsible for scheduling the daily operations of the refinery.
    """
    def __init__(self, tanks: Dict[str, Tank], 
                blending_recipes: List[BlendingRecipe], 
                vessels: List[Vessel],
                crude_data: Dict[str, Crude],
                max_processing_rate: float):
        """
        Initialize the scheduler.
        
        Args:
            tanks: Dictionary of tanks
            blending_recipes: List of available blending recipes
            vessels: List of vessels with arrival schedules
            crude_data: Dictionary of crude data (margins, etc.)
            max_processing_rate: Fallback max rate if recipe doesn't specify one
        """
        self.tank_manager = TankManager(tanks)
        self.blending_engine = BlendingEngine()
        
        # Ensure all recipes have a max_rate by using the fallback if needed
        for recipe in blending_recipes:
            if not hasattr(recipe, 'max_rate') or recipe.max_rate is None:
                recipe.max_rate = max_processing_rate
        
        self.blending_recipes = blending_recipes
        self.vessels = vessels
        self.crude_data = crude_data
        self.max_processing_rate = max_processing_rate  # Plant's daily capacity (e.g., 95 kb/day from plant.json)
        self.daily_plans = {}  # Dictionary with day (int) as key and DailyPlan as value
        
        # Track recipe status for transition logic
        self.current_active_recipes = {}  # {recipe_name: days_running}
        self.recipe_transition_threshold = 2  # Allow multi-recipe only if switching recipes within N days
        
    # Enhanced run method with better error handling and automatic output saving
    def run(self, days: int, save_output: bool = True, output_dir: str = None) -> List[Dict]:
        """
        Run the scheduler for a specified number of days.
        
        Args:
            days: Number of days to run the scheduler for
            save_output: Whether to save output files (default: True)
            output_dir: Directory to save output files (default: "../output")
            
        Returns:
            List of daily plans in JSON-serializable format
        """
        try:
            # Validate required data
            if not self.tank_manager.tanks:
                raise ValueError("No tanks available for scheduling")
                
            if not self.blending_recipes:
                raise ValueError("No blending recipes provided for scheduling")
            
            # Check if we have crude data for the recipes
            recipe_grades = {recipe.primary_grade for recipe in self.blending_recipes}
            recipe_grades.update({recipe.secondary_grade for recipe in self.blending_recipes if recipe.secondary_grade})
            missing_grades = recipe_grades - set(self.crude_data.keys())
            if missing_grades:
                raise ValueError(f"Missing crude data for grades: {', '.join(missing_grades)}")
            
            # Create day 0 plan with initial inventory
            self._create_initial_plan()
            
            # Process each day
            for day in range(1, days+1):
                # Check for vessel arrivals and update inventory
                self._update_inventory(day)
                
                # Calculate current inventory levels
                current_inventory = {}
                for tank in self.tank_manager.tanks.values():
                    for content in tank.content:
                        for grade, volume in content.items():
                            if grade in current_inventory:
                                current_inventory[grade] += volume
                            else:
                                current_inventory[grade] = volume

                # Pass both parameters to _select_blends
                selected_recipes = self._select_blends(day, current_inventory)
                if selected_recipes is None:
                    selected_recipes = {}

                # Create daily plan and update tank inventory
                self._create_daily_plan(day, selected_recipes)
                
                # Update active recipes tracking for transition detection
                self.current_active_recipes = {name: rate for name, rate in selected_recipes.items() if rate > 0.1}
                
            # Save output if requested (default is True)
            output_files = {}
            if save_output:
                output_files = self.save_results(output_dir)
                
            # Convert daily_plans from dictionary to list of JSON-serializable objects
            result = []
            for day in sorted(self.daily_plans.keys()):
                plan = self.daily_plans[day]
                
                # Convert tank objects to serializable format
                tanks_json = {}
                for tank_name, tank in plan.tanks.items():
                    content_json = []
                    for content in tank.content:
                        content_json.append(content)
                    
                    tanks_json[tank_name] = {
                        "name": tank.name,
                        "capacity": tank.capacity,
                        "content": content_json
                    }
                
                # Create serializable plan
                plan_json = {
                    "day": plan.day,
                    "processing_rates": plan.processing_rates,
                    "inventory": plan.inventory,
                    "inventory_by_grade": plan.inventory_by_grade,
                    "tanks": tanks_json,
                    "blending_details": plan.blending_details
                }
                
                result.append(plan_json)
            
            return result
            
        except Exception as e:
            print(f"Scheduler error: {e}")
            import traceback
            traceback.print_exc()
            
            # Return partial results if available
            if self.daily_plans:
                # Convert partial daily_plans to JSON format
                partial_results = []
                for day in sorted(self.daily_plans.keys()):
                    plan = self.daily_plans[day]
                    
                    # Create a minimal JSON-serializable plan with error handling
                    try:
                        tanks_json = {}
                        for tank_name, tank in plan.tanks.items():
                            tanks_json[tank_name] = {
                                "name": tank.name,
                                "capacity": tank.capacity,
                                "content": [content for content in tank.content]
                            }
                        
                        plan_json = {
                            "day": plan.day,
                            "processing_rates": plan.processing_rates,
                            "inventory": plan.inventory,
                            "inventory_by_grade": plan.inventory_by_grade,
                            "tanks": tanks_json,
                            "blending_details": getattr(plan, "blending_details", [])
                        }
                        
                        partial_results.append(plan_json)
                    except Exception as conversion_error:
                        print(f"Error converting day {day} plan: {conversion_error}")
                        partial_results.append({"day": day, "error": str(conversion_error)})
                
                return partial_results
                
            return []
    
    def save_results(self, output_dir: str = None) -> Dict[str, str]:
        """
        Save scheduling results to output files.
        
        Args:
            output_dir: Directory to save output files (default: "../output")
            
        Returns:
            Dictionary with paths to the saved files
        """
        # Set default output directory if not provided
        if output_dir is None:
            output_dir = os.path.join(os.path.dirname(__file__), "../output")
        
        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)
        
        # Generate timestamp for text and Excel files (these can have timestamps)
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Dictionary to store output file paths
        output_files = {}
        
        # Generate summary report (text format) - keep timestamp for this
        summary_path = os.path.join(output_dir, f"schedule_summary_{timestamp}.txt")
        with open(summary_path, "w") as f:
            f.write(generate_summary_report(self.daily_plans))
        output_files['summary'] = summary_path
        
        # Try to export to Excel - keep timestamp for this
        try:
            excel_path = os.path.join(output_dir, f"schedule_{timestamp}.xlsx")
            export_schedule_to_excel(self.daily_plans, excel_path)
            output_files['excel'] = excel_path
        except ImportError:
            print("Warning: Excel export skipped - xlsxwriter module not installed")
            print("To enable Excel export, run: pip install xlsxwriter")
        
        # Save as JSON using a FIXED filename (no timestamp) for easier frontend access
        json_path = os.path.join(output_dir, "schedule_results.json")
        self.export_to_json(json_path)
        output_files['json'] = json_path
        
        print(f"Results saved to {output_dir}")
        for output_type, path in output_files.items():
            print(f" - {output_type}: {os.path.basename(path)}")
        
        return output_files
    
    def _update_inventory(self, day: int) -> None:
        """Update inventory based on vessel arrivals for the given day."""
        print(f"------- Updating inventory for Day {day} -------")
        
        # Check for vessel arrivals
        arriving_vessels = [v for v in self.vessels if v.arrival_day == day]
        print(f"Arriving vessels: {len(arriving_vessels)}")
        
        for vessel in arriving_vessels:
            print(f"Processing vessel {vessel.vessel_id} arrival on day {day}")
            
            # Process each cargo item
            for cargo_item in vessel.cargo:
                print(f"Processing cargo item: {cargo_item}")
                
                # Check if cargo_item is a FeedstockParcel object
                if isinstance(cargo_item, FeedstockParcel):
                    grade = cargo_item.grade
                    volume = cargo_item.volume
                    if grade and volume > 0:
                        # Attempt to store the crude in available tanks
                        stored = self.tank_manager.store_crude(grade, volume)
                        print(f"Stored {stored} units of {grade} ({volume} requested)")
                
                # If it's the old format (dict with grade:volume)
                elif isinstance(cargo_item, dict):
                    try:
                        if "grade" in cargo_item and "volume" in cargo_item:
                            # New vessel.json format with grade/volume as separate keys
                            grade = cargo_item.get("grade")
                            volume = cargo_item.get("volume", 0)
                            if grade and volume > 0:
                                stored = self.tank_manager.store_crude(grade, volume)
                                print(f"Stored {stored} units of {grade} ({volume} requested)")
                        else:
                            # Legacy format with grade:volume pairs
                            for grade, volume in cargo_item.items():
                                stored = self.tank_manager.store_crude(grade, volume)
                                print(f"Legacy format: Stored {stored} units of {grade}")
                    except Exception as e:
                        print(f"Error processing cargo: {e}")
        
        # After processing all vessels, print current inventory
        print("Current inventory after vessel processing:")
        current_inventory = {}
        for tank_name, tank in self.tank_manager.tanks.items():
            for content_item in tank.content:
                for grade, amount in content_item.items():
                    if grade in current_inventory:
                        current_inventory[grade] += amount
                    else:
                        current_inventory[grade] = amount
        print(current_inventory)
    
    def _select_blends(self, day_idx: int, available_inventory: Dict[str, float]) -> Dict[str, float]:
        """
        Select optimal blends for the given day based on available inventory.
        Allows multiple recipes only during transition periods between different recipes.
        
        Args:
            day_idx: Current day index
            available_inventory: Available inventory by grade
            
        Returns:
            Dictionary mapping recipe names to processing rates
        """
        try:
            # Find all possible blends
            all_possible_blends = self.blending_engine.find_optimal_blends(
                self.blending_recipes,      
                self.crude_data,            
                self.tank_manager.tanks,    
                float('inf')  # No global limit - we'll use recipe limits
            )
            
            # If no blends found, return empty dict
            if not all_possible_blends:
                print(f"Day {day_idx}: No viable blends found")
                return {}
            
            # Sort by margin (highest first)
            sorted_blends = sorted(all_possible_blends, key=lambda x: x[1], reverse=True)
            
            # Determine best recipe based on margin
            best_recipe, best_margin, proposed_rate = sorted_blends[0]
            
            # Check if we're in a transition period
            is_transition_period = self._is_transition_period(day_idx, best_recipe.name)
            
            if is_transition_period and len(sorted_blends) > 1:
                print(f"Day {day_idx}: Transition period detected - checking for compatible recipes")
                
                # Find compatible recipes that can actually be blended together
                # Recipes are compatible if they share at least one crude grade
                compatible_recipes = self._find_compatible_recipes_for_transition(sorted_blends)
                
                if len(compatible_recipes) > 1:
                    print(f"Day {day_idx}: Found {len(compatible_recipes)} compatible recipes for transition")
                    
                    # During transition, simulate time-sharing within the day
                    selected_recipes = {}
                    
                    # Use plant capacity (95 kb/day) instead of sum of recipe max rates
                    daily_plant_capacity = self.max_processing_rate
                    print(f"Day {day_idx}: Available daily plant capacity: {daily_plant_capacity} kb")
                    
                    # Allocate capacity between compatible recipes based on their relative margins
                    total_margin = sum(recipe[1] for recipe in compatible_recipes)
                    
                    for i, (recipe, margin, max_possible_rate) in enumerate(compatible_recipes):
                        # Calculate time allocation based on margin weight
                        # Higher margin recipes get more time within the day
                        if total_margin > 0:
                            time_fraction = margin / total_margin
                        else:
                            time_fraction = 1.0 / len(compatible_recipes)  # Equal split if no margin data
                        
                        # Calculate allocated capacity for this recipe's time slice
                        allocated_capacity = daily_plant_capacity * time_fraction
                        
                        # Respect recipe's max rate and inventory constraints
                        actual_rate = min(recipe.max_rate, max_possible_rate, allocated_capacity)
                        
                        if actual_rate > 0.1:  # Only include if rate is significant
                            selected_recipes[recipe.name] = actual_rate
                            print(f"Day {day_idx}: Recipe {recipe.name} allocated {time_fraction:.2f} of day ({actual_rate:.1f} kb)")
                    
                    # Verify total doesn't exceed plant capacity
                    total_allocated = sum(selected_recipes.values())
                    if total_allocated > daily_plant_capacity:
                        # Scale down proportionally if we somehow exceeded capacity
                        scale_factor = daily_plant_capacity / total_allocated
                        selected_recipes = {name: rate * scale_factor for name, rate in selected_recipes.items()}
                        print(f"Day {day_idx}: Scaled down by {scale_factor:.3f} to respect plant capacity")
                    
                    print(f"Day {day_idx}: Total processing: {sum(selected_recipes.values()):.1f} kb (Plant capacity: {daily_plant_capacity} kb)")
                    return selected_recipes
                else:
                    print(f"Day {day_idx}: No compatible recipes found for transition - using single best recipe")
                    # Fall through to single recipe selection
                
            else:
                # Normal operation - single recipe only
                # Respect both recipe max rate and plant capacity
                actual_rate = min(proposed_rate, best_recipe.max_rate, self.max_processing_rate)
                print(f"Day {day_idx}: Selected single recipe {best_recipe.name} at rate {actual_rate:.1f} kb")
                print(f"Day {day_idx}: Rate constraints - Recipe max: {best_recipe.max_rate}, Plant capacity: {self.max_processing_rate}, Inventory limit: {proposed_rate:.1f}")
                return {best_recipe.name: actual_rate}
            
        except Exception as e:
            print(f"Error in blend selection: {e}")
            import traceback
            traceback.print_exc()
            return {}
    
    def _is_transition_period(self, day_idx: int, best_recipe_name: str) -> bool:
        """
        Determine if we're in a transition period between recipes.
        
        Args:
            day_idx: Current day index
            best_recipe_name: Name of the best recipe for this day
            
        Returns:
            True if we're in a transition period, False otherwise
        """
        # Check if we have any currently active recipes
        if not self.current_active_recipes:
            # No active recipes - not a transition
            return False
        
        # Check if the best recipe is different from currently active recipes
        active_recipe_names = set(self.current_active_recipes.keys())
        
        if best_recipe_name not in active_recipe_names:
            # New recipe being introduced - this is a transition
            print(f"Day {day_idx}: Recipe transition detected - switching from {active_recipe_names} to {best_recipe_name}")
            return True
        
        # Check if any current recipe is nearing end (low inventory for its grades)
        for active_recipe_name in active_recipe_names:
            active_recipe = next((r for r in self.blending_recipes if r.name == active_recipe_name), None)
            if active_recipe:
                # Check inventory levels for this recipe's grades
                primary_inventory = sum(
                    content.get(active_recipe.primary_grade, 0) 
                    for tank in self.tank_manager.tanks.values() 
                    for content in tank.content
                )
                
                # If primary inventory is low (less than 2 days of operation), consider it a transition
                estimated_days_remaining = primary_inventory / (active_recipe.max_rate * active_recipe.primary_fraction)
                if estimated_days_remaining < self.recipe_transition_threshold:
                    print(f"Day {day_idx}: Recipe {active_recipe_name} running low on inventory - estimated {estimated_days_remaining:.1f} days remaining")
                    return True
        
        return False
    
    def _create_daily_plan(self, day: int, selected_recipes: Dict[str, float]) -> None:
        """
        Create a daily plan for multiple recipes and update tank inventory.
        
        Args:
            day: Current day
            selected_recipes: Dictionary mapping recipe names to processing rates
        """
        if selected_recipes is None:
            print(f"Day {day}: No recipes selected (selected_recipes is None). Skipping daily plan.")
            selected_recipes = {}
        
        processing_rates = {}
        selected_recipe_objects = []
        
        # Process each selected recipe
        for recipe_name, rate in selected_recipes.items():
            # Find the recipe object
            recipe = next((r for r in self.blending_recipes if r.name == recipe_name), None)
            if recipe and rate > 0:
                # Make sure we respect the recipe's max rate
                actual_rate = min(rate, recipe.max_rate)
                processing_rates[recipe.name] = actual_rate
                selected_recipe_objects.append({
                    "name": recipe.name,
                    "primary_grade": recipe.primary_grade,
                    "secondary_grade": recipe.secondary_grade,
                    "primary_fraction": recipe.primary_fraction,
                    "max_rate": recipe.max_rate,
                    "rate": actual_rate
                })
                
                # Withdraw crude from tanks based on recipe
                primary_volume = actual_rate * recipe.primary_fraction
                self._withdraw_crude(recipe.primary_grade, primary_volume)
                
                if recipe.secondary_grade:
                    secondary_volume = actual_rate * (1.0 - recipe.primary_fraction)
                    self._withdraw_crude(recipe.secondary_grade, secondary_volume)
        
        # Calculate current inventory levels (keep this part the same)
        total_inventory = 0
        inventory_by_grade = {}
        
        for tank in self.tank_manager.tanks.values():
            for content in tank.content:
                for grade, volume in content.items():
                    total_inventory += volume
                    if grade in inventory_by_grade:
                        inventory_by_grade[grade] += volume
                    else:
                        inventory_by_grade[grade] = volume
        
        # Create daily plan
        daily_plan = DailyPlan(
            day=day,
            processing_rates=processing_rates,
            blending_details=selected_recipe_objects,
            inventory=total_inventory,
            inventory_by_grade=inventory_by_grade,
            tanks=self.tank_manager.tanks.copy()
        )
        
        self.daily_plans[day] = daily_plan
    
    def _withdraw_crude(self, grade: str, volume: float) -> None:
        """
        Withdraw crude from tanks.
        
        Args:
            grade: Crude grade to withdraw
            volume: Volume to withdraw
        """
        remaining = volume
        
        # Try each tank until we've withdrawn the required amount
        for tank_name in self.tank_manager.tanks:
            if remaining <= 0:
                break
                
            # Check how much of this grade is in the current tank
            tank = self.tank_manager.tanks[tank_name]
            available = sum(content.get(grade, 0) for content in tank.content)
            
            if available > 0:
                # Withdraw as much as possible from this tank
                to_withdraw = min(available, remaining)
                self.tank_manager.withdraw(tank_name, grade, to_withdraw)
                remaining -= to_withdraw

    def export_to_json(self, file_path: str) -> None:
        """
        Export daily plans to JSON format that is compatible with the API.
        
        Args:
            file_path: Path to save the JSON file
        """
        try:
            # Convert daily plans to JSON-serializable format
            daily_plans_json = []
            
            for day in sorted(self.daily_plans.keys()):
                plan = self.daily_plans[day]
                
                # Convert tank objects to serializable format
                tanks_json = {}
                for tank_name, tank in plan.tanks.items():
                    content_json = []
                    for content in tank.content:
                        content_json.append(content)
                    
                    tanks_json[tank_name] = {
                        "name": tank.name,
                        "capacity": tank.capacity,
                        "content": content_json
                    }
                
                # Create serializable plan
                plan_json = {
                    "day": plan.day,
                    "processing_rates": plan.processing_rates,
                    "inventory": plan.inventory,
                    "inventory_by_grade": plan.inventory_by_grade,
                    "tanks": tanks_json,
                    "blending_details": plan.blending_details
                }
                
                daily_plans_json.append(plan_json)
            
            # Write to file with proper formatting
            with open(file_path, 'w') as f:
                json.dump({"daily_plans": daily_plans_json}, f, indent=2)
                
            print(f"JSON export successful: {file_path}")
            
        except Exception as e:
            print(f"Error exporting to JSON: {e}")
            import traceback
            traceback.print_exc()

    def _create_initial_plan(self):
        """Create a day 0 plan with initial inventory"""
        # Calculate current inventory levels
        total_inventory = 0
        inventory_by_grade = {}
        
        for tank in self.tank_manager.tanks.values():
            for content in tank.content:
                for grade, volume in content.items():
                    total_inventory += volume
                    if grade in inventory_by_grade:
                        inventory_by_grade[grade] += volume
                    else:
                        inventory_by_grade[grade] = volume
        
        # Create day 0 plan (no processing)
        daily_plan = DailyPlan(
            day=0,
            processing_rates={},
            blending_details=[],
            inventory=total_inventory,
            inventory_by_grade=inventory_by_grade,
            tanks=self.tank_manager.tanks.copy()
        )
        
        self.daily_plans[0] = daily_plan
        print(f"Initial inventory registered: {total_inventory} total, {inventory_by_grade} by grade")
    
    def _find_compatible_recipes_for_transition(self, sorted_blends: List[Tuple]) -> List[Tuple]:
        """
        Find recipes that are compatible for simultaneous operation during transitions.
        Recipes are compatible if they share at least one crude grade or can reasonably
        operate together without conflicting resource requirements.
        
        Args:
            sorted_blends: List of (recipe, margin, max_rate) tuples sorted by preference
            
        Returns:
            List of compatible recipe tuples for transition operation
        """
        if not sorted_blends:
            return []
        
        # Always include the best recipe
        best_recipe, best_margin, best_rate = sorted_blends[0]
        compatible_recipes = [sorted_blends[0]]
        
        # Get grades used by the best recipe
        best_grades = {best_recipe.primary_grade}
        if best_recipe.secondary_grade:
            best_grades.add(best_recipe.secondary_grade)
        
        print(f"Best recipe {best_recipe.name} uses grades: {best_grades}")
        
        # Check each remaining recipe for compatibility
        for recipe, margin, rate in sorted_blends[1:]:
            recipe_grades = {recipe.primary_grade}
            if recipe.secondary_grade:
                recipe_grades.add(recipe.secondary_grade)
            
            print(f"Checking recipe {recipe.name} with grades: {recipe_grades}")
            
            # Recipes are compatible if they share at least one grade
            # This allows for blending transitions (e.g., Base+A -> Base+B)
            shared_grades = best_grades.intersection(recipe_grades)
            
            if shared_grades:
                print(f"Recipe {recipe.name} is compatible - shared grades: {shared_grades}")
                compatible_recipes.append((recipe, margin, rate))
                # Only allow one additional recipe for transition to keep it simple
                break
            else:
                print(f"Recipe {recipe.name} is NOT compatible - no shared grades with {best_recipe.name}")
        
        return compatible_recipes