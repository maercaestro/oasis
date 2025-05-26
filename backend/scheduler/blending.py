"""
OASIS Base Scheduler/ blending.py
This module handles the bleding logic for the OASIS system. We just keep it simple as to identify which blend to run
Copyright (c) by Abu Huzaifah Bidin with help from Github Copilot

"""

from typing import List, Dict, Optional, Tuple
from .models import Tank, BlendingRecipe, FeedstockParcel, Vessel, DailyPlan, Crude

class BlendingEngine:
    """
    Engine responsible for findings the best blending recipe for the day based on the available inventory inside the tanks
    and the blending recipes available in the system.
    """
    def blend_margin(self, recipe: BlendingRecipe, crude_data: Dict[str, Crude]) -> float:
        """
        Calculate the margin of the blending recipe based on the crude data
        param recipe: BlendingRecipe the blending recipe to be used
        param crude_data: Dict[str, Crude] the crude data to be used for calculating the margin
        return: List[BlendingRecipe] the list of blending recipes with the margin calculated
        """
        # Calculate the margin of the blending recipe based on the crude data
        margin = 0.0
        if recipe.primary_grade in crude_data:
            margin += crude_data[recipe.primary_grade].margin * recipe.primary_fraction
        if recipe.secondary_grade and recipe.secondary_grade in crude_data:
            margin += crude_data[recipe.secondary_grade].margin * (1.0 - recipe.primary_fraction)
        return margin
    
    def blend_compatibility(self, recipe: BlendingRecipe, tanks: Dict[str, Tank]) -> bool:
        """
        Check if the blending recipe is compatible with the available tanks
        param recipe: BlendingRecipe the blending recipe to be used
        param tanks: Dict[str, Tank] the tanks to be used for blending
        return: bool True if the blending recipe is compatible with the available tanks, False otherwise
        """
        # Calculate needed volumes
        primary_volume_needed = recipe.max_rate * recipe.primary_fraction
        secondary_volume_needed = recipe.max_rate * (1.0 - recipe.primary_fraction) if recipe.secondary_grade else 0
        
        # Check if we have enough of each grade across all tanks
        primary_available = sum(
            content.get(recipe.primary_grade, 0) 
            for tank in tanks.values() 
            for content in tank.content
        )
        
        if primary_available < primary_volume_needed:
            return False
            
        if recipe.secondary_grade:
            secondary_available = sum(
                content.get(recipe.secondary_grade, 0) 
                for tank in tanks.values() 
                for content in tank.content
            )
            
            if secondary_available < secondary_volume_needed:
                return False
                
        return True
    
    def find_optimal_blends(self, available_recipes, crude_data, tanks, max_processing):
        """
        Determine the optimal set of blends to run based on available inventory.
        For scheduler use - prioritizes inventory utilization over margin.
        """
        # Add practical zero threshold
        EPSILON = 1e-6
        
        # Add debug information
        print("\n--- Debugging BlendingEngine.find_optimal_blends (INVENTORY-BASED) ---")
        print(f"Available recipes: {[r.name for r in available_recipes]}")
        print(f"Available grades in crude_data: {list(crude_data.keys())}")
        
        # Calculate available inventory for debugging
        inventory_by_grade = {}
        for tank in tanks.values():
            for content in tank.content:
                for grade, volume in content.items():
                    if grade in inventory_by_grade:
                        inventory_by_grade[grade] += volume
                    else:
                        inventory_by_grade[grade] = volume
        print(f"Available inventory by grade: {inventory_by_grade}")
        
        # Calculate margin for each recipe and check compatibility
        viable_recipes = []
        for recipe in available_recipes:
            # Calculate the maximum possible rate from inventory
            max_rate_from_inventory = self.calculate_max_rate(recipe, tanks)
            
            # Add debugging for each recipe evaluation
            print(f"\nEvaluating recipe: {recipe.name}")
            print(f"  Primary grade: {recipe.primary_grade}, fraction: {recipe.primary_fraction}")
            print(f"  Secondary grade: {recipe.secondary_grade or 'None'}")
            print(f"  Max rate from recipe: {recipe.max_rate}")
            print(f"  Max rate from inventory: {max_rate_from_inventory}")
            
            # Print why a recipe was rejected if applicable
            if max_rate_from_inventory <= EPSILON:  # Using EPSILON instead of 0
                print(f"  REJECTED: Insufficient inventory to run this recipe")
                primary_available = sum(content.get(recipe.primary_grade, 0) for tank in tanks.values() for content in tank.content)
                print(f"    Primary grade {recipe.primary_grade}: {primary_available} available")
                if recipe.secondary_grade:
                    secondary_available = sum(content.get(recipe.secondary_grade, 0) for tank in tanks.values() for content in tank.content)
                    print(f"    Secondary grade {recipe.secondary_grade}: {secondary_available} available")
                continue
                
            margin = self.blend_margin(recipe, crude_data)
            print(f"  Recipe margin: {margin}")
            viable_recipes.append((recipe, margin, max_rate_from_inventory))
        
        print(f"\nFound {len(viable_recipes)} viable recipes")
        
        # CHANGED: Sort by inventory availability (highest first) instead of margin
        print("Using INVENTORY-BASED sorting for scheduler")
        viable_recipes.sort(key=lambda x: x[2], reverse=True)
        
        # Select recipes up to max processing capacity
        selected_recipes = []
        remaining_capacity = max_processing
        
        for recipe, margin, max_possible_rate in viable_recipes:
            if remaining_capacity <= EPSILON:  # Using EPSILON instead of 0
                break
                
            # Determine actual rate: min of recipe max_rate, inventory-based rate, and remaining capacity
            actual_rate = min(recipe.max_rate, max_possible_rate, remaining_capacity)
            
            if actual_rate > EPSILON:  # Using EPSILON instead of 0
                selected_recipes.append((recipe, margin, actual_rate))
                remaining_capacity -= actual_rate
        
        return selected_recipes

    def calculate_max_rate(self, recipe: BlendingRecipe, tanks: Dict[str, Tank]) -> float:
        """
        Calculate maximum possible blend rate based on available inventory
        
        Args:
            recipe: BlendingRecipe to check
            tanks: Available tanks
            
        Returns:
            Maximum possible rate in kb/day
        """
        # Check primary grade availability
        primary_available = sum(
            content.get(recipe.primary_grade, 0) 
            for tank in tanks.values() 
            for content in tank.content
        )
        
        # Max rate based on primary grade
        max_rate_primary = primary_available / recipe.primary_fraction if recipe.primary_fraction > 0 else float('inf')
        
        # If there's a secondary grade, calculate its constraint
        if recipe.secondary_grade:
            secondary_available = sum(
                content.get(recipe.secondary_grade, 0) 
                for tank in tanks.values() 
                for content in tank.content
            )
            
            secondary_fraction = 1.0 - recipe.primary_fraction
            max_rate_secondary = secondary_available / secondary_fraction if secondary_fraction > 0 else float('inf')
            
            # Use the limiting factor
            return min(max_rate_primary, max_rate_secondary)
        else:
            return max_rate_primary




