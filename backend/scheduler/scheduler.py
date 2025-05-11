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
            max_processing_rate: Maximum daily processing rate
        """
        self.tank_manager = TankManager(tanks)
        self.blending_engine = BlendingEngine()
        self.blending_recipes = blending_recipes
        self.vessels = vessels
        self.crude_data = crude_data
        self.max_processing_rate = max_processing_rate
        self.daily_plans = {}
        
    def run(self, days: int, save_output: bool = False, output_dir: str = None) -> Dict[int, DailyPlan]:
        """
        Run the scheduler for a specified number of days.
        
        Args:
            days: Number of days to schedule
            save_output: Whether to save results to output files
            output_dir: Directory to save output files (default: "../output")
            
        Returns:
            Dictionary of daily plans indexed by day
        """
        for day in range(1, days+1):
            # Check for vessel arrivals and update inventory
            self._update_inventory(day)
            
            # Pick optimal blending recipes for the day
            optimal_blends = self._select_blends(day)
            
            # Create daily plan and update tank inventory
            self._create_daily_plan(day, optimal_blends)
            
        # Save output if requested
        if save_output:
            self.save_results(output_dir)
            
        return self.daily_plans
    
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
        
        # Generate timestamp for filenames
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Save results to files
        output_files = {}
        
        # Generate and save summary report
        report_path = os.path.join(output_dir, f"schedule_summary_{timestamp}.txt")
        generate_summary_report(self.daily_plans, report_path)
        output_files['summary'] = report_path
        
        # Export to Excel
        excel_path = os.path.join(output_dir, f"schedule_results_{timestamp}.xlsx")
        export_schedule_to_excel(self.daily_plans, excel_path)
        output_files['excel'] = excel_path
        
        print(f"Results saved to {output_dir}")
        print(f"- Summary report: {os.path.basename(report_path)}")
        print(f"- Excel file: {os.path.basename(excel_path)}")
        
        return output_files
    
    def _update_inventory(self, day: int) -> None:
        """
        Check for vessel arrivals and update tank inventory.
        
        Args:
            day: Current day
        """
        # Find vessels arriving on this day
        arriving_vessels = [v for v in self.vessels if v.arrival_day == day]
        
        for vessel in arriving_vessels:
            # Process each cargo parcel
            for parcel in vessel.cargo:
                # Find a suitable tank with enough capacity
                for tank_name, tank in self.tank_manager.tanks.items():
                    # Calculate current tank volume
                    current_volume = sum(sum(content.values()) for content in tank.content)
                    
                    # Check if there's enough space
                    if current_volume + parcel.volume <= tank.capacity:
                        # Add parcel to tank
                        success = self.tank_manager.add(tank_name, parcel)
                        if success:
                            break
                else:
                    # If we couldn't find a tank with enough space, delay the vessel
                    vessel.days_held += 1
                    vessel.arrival_day = day + 1
    
    def _select_blends(self, day: int) -> List[Tuple[BlendingRecipe, float, float]]:
        """
        Select optimal blending recipes for the current day.
        
        Args:
            day: Current day
            
        Returns:
            List of tuples (recipe, margin, actual_rate)
        """
        # Get current tanks from tank manager
        current_tanks = self.tank_manager.tanks
        
        # Use blending engine to find optimal blends
        optimal_blends = self.blending_engine.find_optimal_blends(
            self.blending_recipes,
            self.crude_data,
            current_tanks,
            self.max_processing_rate
        )
        
        return optimal_blends
    
    def _create_daily_plan(self, day: int, optimal_blends: List[Tuple[BlendingRecipe, float, float]]) -> None:
        """
        Create a daily plan and update tank inventory.
        
        Args:
            day: Current day
            optimal_blends: List of selected blends with rates
        """
        # Extract recipes and rates
        processing_rates = {}
        selected_recipes = []
        
        for recipe, margin, rate in optimal_blends:
            processing_rates[recipe.name] = rate
            selected_recipes.append(recipe)
            
            # Withdraw crude from tanks based on recipe
            primary_volume = rate * recipe.primary_fraction
            self._withdraw_crude(recipe.primary_grade, primary_volume)
            
            if recipe.secondary_grade:
                secondary_volume = rate * (1.0 - recipe.primary_fraction)
                self._withdraw_crude(recipe.secondary_grade, secondary_volume)
        
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
        
        # Create daily plan
        daily_plan = DailyPlan(
            day=day,
            processing_rates=processing_rates,
            blending_details=selected_recipes,
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