"""
OASIS Data Service Layer
Centralized business logic for data access, transformation, and persistence.
"""

from typing import Dict, List, Any, Optional
from datetime import datetime
from database.extended_ops import DatabaseManagerExtended
from scheduler.models import Tank, Vessel, Crude, BlendingRecipe, FeedstockParcel
import os
import json

class DataService:
    def __init__(self, db: DatabaseManagerExtended):
        self.db = db

    # Tanks
    def get_all_tanks(self) -> Dict[str, Any]:
        return self.db.get_all_tanks()

    def save_tanks(self, tanks_data: Dict[str, Any]) -> bool:
        return self.db.save_tanks_data(tanks_data)

    def get_tank(self, name: str) -> Optional[Dict[str, Any]]:
        return self.db.get_tank(name=name)

    def update_tank(self, name: str, update_data: Dict[str, Any]) -> bool:
        return self.db.update_tank(name=name, **update_data)

    def delete_tank(self, name: str) -> bool:
        return self.db.delete_tank(name=name)

    # Vessels
    def get_all_vessels(self) -> Dict[str, Any]:
        return self.db.get_all_vessels()

    def save_vessels(self, vessels_data: Dict[str, Any]) -> bool:
        return self.db.save_vessels_data(vessels_data)

    # Crudes
    def get_all_crudes(self) -> List[Dict[str, Any]]:
        return self.db.get_all_crudes()

    def save_crudes(self, crudes_data: Dict[str, Any]) -> bool:
        with self.db.transaction() as conn:
            conn.execute("DELETE FROM crudes")
            for crude_name, crude_info in crudes_data.items():
                self.db.create_crude(
                    name=crude_name,
                    margin=crude_info.get('margin', 15.0),
                    origin=crude_info.get('origin', 'Unknown')
                )
        return True

    # Recipes
    def get_all_recipes(self) -> List[Dict[str, Any]]:
        return self.db.get_all_blending_recipes()

    def save_recipes(self, recipes_data: Dict[str, Any]) -> bool:
        recipes_list = [recipe_info for recipe_info in recipes_data.values()]
        return self.db.save_blending_recipes(recipes_list)

    # Schedule (JSON file)
    def load_schedule(self) -> List[Dict[str, Any]]:
        schedule_path = os.path.join(os.path.dirname(__file__), "../output/schedule_results.json")
        try:
            with open(schedule_path, 'r') as f:
                schedule_json = json.load(f)
                return schedule_json.get('daily_plans', [])
        except (FileNotFoundError, json.JSONDecodeError):
            return []

    def save_schedule(self, schedule: List[Dict[str, Any]]) -> bool:
        output_path = os.path.join(os.path.dirname(__file__), "../output/schedule_results.json")
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        schedule_data = {"daily_plans": schedule}
        with open(output_path, 'w') as f:
            json.dump(schedule_data, f, indent=2)
        return True

    # Vessel Types
    def get_all_vessel_types(self) -> list:
        return self.db.get_all_vessel_types()

    def save_vessel_types(self, vessel_types: list) -> bool:
        return self.db.save_vessel_types(vessel_types)
