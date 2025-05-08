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
    
    def find_optimal_blends(self, available_recipes: List[BlendingRecipe], crude_data: Dict[str, Crude],
                    tanks: Dict[str, Tank], max_processing: float) -> List[Tuple[BlendingRecipe, float, float]]:
        """
        Determine the optimal set of blends to run based on margins and available inventory
        
        Args:
            available_recipes: List of possible blending recipes
            crude_data: Dictionary of crude information including margins
            tanks: Dict of available tanks
            max_processing: Maximum daily processing capacity
        
        Returns:
            List of tuples containing (recipe, margin, actual_rate)
        """
        # Calculate margin for each recipe and check compatibility
        viable_recipes = []
        for recipe in available_recipes:
            # Calculate the maximum possible rate from inventory
            max_rate_from_inventory = self.calculate_max_rate(recipe, tanks)
            
            # Only consider recipes with enough inventory to run
            if max_rate_from_inventory > 0:
                margin = self.blend_margin(recipe, crude_data)
                viable_recipes.append((recipe, margin, max_rate_from_inventory))
        
        # Sort by margin (highest first)
        viable_recipes.sort(key=lambda x: x[1], reverse=True)
        
        # Select recipes up to max processing capacity
        selected_recipes = []
        remaining_capacity = max_processing
        remaining_tanks = tanks.copy()
        
        for recipe, margin, max_possible_rate in viable_recipes:
            if remaining_capacity <= 0:
                break
                
            # Determine actual rate: min of recipe max_rate, inventory-based rate, and remaining capacity
            actual_rate = min(recipe.max_rate, max_possible_rate, remaining_capacity)
            
            if actual_rate > 0:
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




