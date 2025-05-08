"""
OASIS Base Scheduler / tanks.py
This module handles the tank logic for the OASIS system. 
It handles the withdrawal and addition of crude to the tanks.

Copyright (c) by Abu Huzaifah Bidin with help from Github Copilot
"""

from typing import List, Dict, Optional, Tuple
from .models import Tank, BlendingRecipe, FeedstockParcel, Vessel, DailyPlan

class TankManager:
    """
    Manager responsible for handling the tanks in the OASIS system.
    """
    def __init__(self, tanks: Dict[str, Tank]):
        self.tanks = tanks

    def withdraw(self, tank_name: str, grade: str, volume: float) -> bool:
        """
        Withdraw a volume of a specific crude grade from a tank.
        
        Args:
            tank_name: The name of the tank to withdraw from
            grade: The grade of crude to withdraw
            volume: The volume to withdraw
            
        Returns:
            True if the withdrawal was successful, False otherwise
        """
        if tank_name not in self.tanks:
            return False
        
        tank = self.tanks[tank_name]
        
        # Check if tank has this grade
        grade_available = 0
        for content in tank.content:
            if grade in content:
                grade_available += content[grade]
        
        if grade_available < volume:
            return False
        
        # Withdraw the crude from the tank
        remaining = volume
        for content in tank.content:
            if grade in content and remaining > 0:
                to_withdraw = min(content[grade], remaining)
                content[grade] -= to_withdraw
                remaining -= to_withdraw
                
                # Remove grade if volume is 0
                if content[grade] <= 0:
                    del content[grade]
        
        # Clean up empty dictionaries in content
        tank.content = [content for content in tank.content if content]
        
        return True
    
    def add(self, tank_name: str, parcel: FeedstockParcel) -> bool:
        """
        Add a feedstock parcel to a tank.
        
        Args:
            tank_name: The name of the tank to add to
            parcel: The feedstock parcel to add
            
        Returns:
            True if the addition was successful, False otherwise
        """
        if tank_name not in self.tanks:
            return False
        
        tank = self.tanks[tank_name]
        
        # Check if there is enough space in the tank
        current_volume = sum(sum(volumes.values()) for volumes in tank.content)
        
        if current_volume + parcel.volume > tank.capacity:
            return False
        
        # Look for existing content with the same grade
        for content in tank.content:
            if parcel.grade in content:
                content[parcel.grade] += parcel.volume
                return True
        
        # Add new content entry if grade doesn't exist
        tank.content.append({parcel.grade: parcel.volume})
        return True
    
    def get_available_volume(self, grade: str) -> float:
        """
        Get the total available volume of a specific crude grade across all tanks.
        
        Args:
            grade: The grade to check
            
        Returns:
            Total available volume
        """
        total = 0
        for tank in self.tanks.values():
            for content in tank.content:
                if grade in content:
                    total += content[grade]
        return total