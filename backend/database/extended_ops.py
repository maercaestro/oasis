"""
OASIS Database Manager - Extended CRUD Operations
Continuation of database operations for tanks, vessels, recipes, etc.

Copyright (c) by Abu Huzaifah Bidin with help from Github Copilot
"""

from typing import Dict, List, Any, Optional, Tuple
try:
    from .db_manager import DatabaseManager
except ImportError:
    from db_manager import DatabaseManager


class DatabaseManagerExtended(DatabaseManager):
    """Extended database operations for all OASIS entities."""
    
    # CRUD Operations for Tanks
    def create_tank(self, name: str, capacity: float, plant_id: int = None) -> int:
        """Create a new tank."""
        with self.transaction() as conn:
            cursor = conn.execute(
                "INSERT INTO tanks (name, capacity, plant_id) VALUES (?, ?, ?)",
                (name, capacity, plant_id)
            )
            return cursor.lastrowid
    
    def get_tank(self, tank_id: int = None, name: str = None) -> Optional[Dict[str, Any]]:
        """Get tank by ID or name with contents."""
        conn = self._get_connection()
        
        if tank_id:
            tank_query = "SELECT * FROM tanks WHERE id = ?"
            param = (tank_id,)
        elif name:
            tank_query = "SELECT * FROM tanks WHERE name = ?"
            param = (name,)
        else:
            raise ValueError("Either tank_id or name must be provided")
        
        cursor = conn.execute(tank_query, param)
        tank_row = cursor.fetchone()
        
        if not tank_row:
            return None
        
        tank = dict(tank_row)
        
        # Get tank contents
        cursor = conn.execute("""
            SELECT c.name as crude_name, tc.volume 
            FROM tank_contents tc 
            JOIN crudes c ON tc.crude_id = c.id 
            WHERE tc.tank_id = ?
        """, (tank['id'],))
        
        contents = []
        for content_row in cursor.fetchall():
            contents.append({content_row['crude_name']: content_row['volume']})
        
        tank['content'] = contents
        return tank
    
    def get_all_tanks(self) -> Dict[str, Dict[str, Any]]:
        """Get all tanks with contents in JSON-compatible format."""
        conn = self._get_connection()
        
        # Get all tanks
        cursor = conn.execute("SELECT * FROM tanks ORDER BY name")
        tanks = {}
        
        for tank_row in cursor.fetchall():
            tank = dict(tank_row)
            tank_name = tank['name']
            
            # Get contents for this tank
            content_cursor = conn.execute("""
                SELECT c.name as crude_name, tc.volume 
                FROM tank_contents tc 
                JOIN crudes c ON tc.crude_id = c.id 
                WHERE tc.tank_id = ?
            """, (tank['id'],))
            
            contents = []
            for content_row in content_cursor.fetchall():
                contents.append({content_row['crude_name']: content_row['volume']})
            
            tanks[tank_name] = {
                'name': tank_name,
                'capacity': tank['capacity'],
                'content': contents
            }
        
        return tanks
    
    def update_tank(self, tank_id: int = None, name: str = None, **kwargs) -> bool:
        """Update tank fields."""
        if not kwargs:
            return False
        
        # Get tank ID if name provided
        if name and not tank_id:
            tank = self.get_tank(name=name)
            if not tank:
                return False
            tank_id = tank['id']
        
        fields = []
        values = []
        for key, value in kwargs.items():
            if key in ['name', 'capacity', 'plant_id']:
                fields.append(f"{key} = ?")
                values.append(value)
        
        if not fields:
            return False
        
        values.append(tank_id)
        with self.transaction() as conn:
            cursor = conn.execute(
                f"UPDATE tanks SET {', '.join(fields)} WHERE id = ?",
                values
            )
            return cursor.rowcount > 0
    
    def delete_tank(self, tank_id: int = None, name: str = None) -> bool:
        """Delete a tank and its contents."""
        if name and not tank_id:
            tank = self.get_tank(name=name)
            if not tank:
                return False
            tank_id = tank['id']
        
        with self.transaction() as conn:
            cursor = conn.execute("DELETE FROM tanks WHERE id = ?", (tank_id,))
            return cursor.rowcount > 0
    
    def update_tank_content(self, tank_name: str, crude_name: str, volume: float) -> bool:
        """Update tank content for a specific crude."""
        with self.transaction() as conn:
            # Get tank and crude IDs
            tank_cursor = conn.execute("SELECT id FROM tanks WHERE name = ?", (tank_name,))
            tank_row = tank_cursor.fetchone()
            if not tank_row:
                return False
            
            crude_cursor = conn.execute("SELECT id FROM crudes WHERE name = ?", (crude_name,))
            crude_row = crude_cursor.fetchone()
            if not crude_row:
                return False
            
            tank_id = tank_row['id']
            crude_id = crude_row['id']
            
            if volume <= 0:
                # Remove content if volume is 0 or negative
                cursor = conn.execute(
                    "DELETE FROM tank_contents WHERE tank_id = ? AND crude_id = ?",
                    (tank_id, crude_id)
                )
            else:
                # Insert or update content
                cursor = conn.execute("""
                    INSERT INTO tank_contents (tank_id, crude_id, volume) 
                    VALUES (?, ?, ?)
                    ON CONFLICT(tank_id, crude_id) 
                    DO UPDATE SET volume = excluded.volume
                """, (tank_id, crude_id, volume))
            
            return True
    
    def save_tanks_data(self, tanks_data: Dict[str, Dict[str, Any]]) -> bool:
        """Save complete tanks data (replaces all tank data)."""
        with self.transaction() as conn:
            # Clear existing tank contents
            conn.execute("DELETE FROM tank_contents")
            conn.execute("DELETE FROM tanks")
            
            for tank_name, tank_info in tanks_data.items():
                # Create tank
                cursor = conn.execute(
                    "INSERT INTO tanks (name, capacity) VALUES (?, ?)",
                    (tank_name, tank_info.get('capacity', 0))
                )
                tank_id = cursor.lastrowid
                
                # Add contents
                for content_item in tank_info.get('content', []):
                    for crude_name, volume in content_item.items():
                        if crude_name:  # Skip empty crude names
                            # Get or create crude
                            crude_cursor = conn.execute("SELECT id FROM crudes WHERE name = ?", (crude_name,))
                            crude_row = crude_cursor.fetchone()
                            
                            if crude_row:
                                crude_id = crude_row['id']
                            else:
                                # Create crude with default values if it doesn't exist
                                create_cursor = conn.execute(
                                    "INSERT INTO crudes (name, margin, origin) VALUES (?, ?, ?)",
                                    (crude_name, 15.0, "Unknown")
                                )
                                crude_id = create_cursor.lastrowid
                            
                            # Add tank content
                            if volume > 0:
                                conn.execute(
                                    "INSERT INTO tank_contents (tank_id, crude_id, volume) VALUES (?, ?, ?)",
                                    (tank_id, crude_id, volume)
                                )
            
            return True
    
    # CRUD Operations for Blending Recipes
    def create_blending_recipe(self, name: str, primary_grade: str, secondary_grade: Optional[str], 
                              max_rate: float, primary_fraction: float) -> int:
        """Create a new blending recipe."""
        with self.transaction() as conn:
            # Get primary grade ID
            cursor = conn.execute("SELECT id FROM crudes WHERE name = ?", (primary_grade,))
            primary_row = cursor.fetchone()
            if not primary_row:
                raise ValueError(f"Primary grade '{primary_grade}' not found")
            primary_grade_id = primary_row['id']
            
            # Get secondary grade ID if provided
            secondary_grade_id = None
            if secondary_grade:
                cursor = conn.execute("SELECT id FROM crudes WHERE name = ?", (secondary_grade,))
                secondary_row = cursor.fetchone()
                if not secondary_row:
                    raise ValueError(f"Secondary grade '{secondary_grade}' not found")
                secondary_grade_id = secondary_row['id']
            
            cursor = conn.execute("""
                INSERT INTO blending_recipes 
                (name, primary_grade_id, secondary_grade_id, max_rate, primary_fraction) 
                VALUES (?, ?, ?, ?, ?)
            """, (name, primary_grade_id, secondary_grade_id, max_rate, primary_fraction))
            
            return cursor.lastrowid
    
    def get_all_blending_recipes(self) -> List[Dict[str, Any]]:
        """Get all blending recipes with grade names."""
        conn = self._get_connection()
        cursor = conn.execute("""
            SELECT br.*, 
                   p.name as primary_grade, 
                   s.name as secondary_grade
            FROM blending_recipes br
            JOIN crudes p ON br.primary_grade_id = p.id
            LEFT JOIN crudes s ON br.secondary_grade_id = s.id
            ORDER BY br.name
        """)
        
        recipes = []
        for row in cursor.fetchall():
            recipe = dict(row)
            # Convert to match existing JSON format
            recipes.append({
                'name': recipe['name'],
                'primary_grade': recipe['primary_grade'],
                'secondary_grade': recipe['secondary_grade'],
                'max_rate': recipe['max_rate'],
                'primary_fraction': recipe['primary_fraction']
            })
        
        return recipes
    
    def save_blending_recipes(self, recipes: List[Dict[str, Any]]) -> bool:
        """Save complete blending recipes data."""
        with self.transaction() as conn:
            # Clear existing recipes
            conn.execute("DELETE FROM blending_recipes")
            
            for recipe in recipes:
                self.create_blending_recipe(
                    name=recipe['name'],
                    primary_grade=recipe['primary_grade'],
                    secondary_grade=recipe.get('secondary_grade'),
                    max_rate=recipe['max_rate'],
                    primary_fraction=recipe['primary_fraction']
                )
            
            return True
    
    # CRUD Operations for Vessels
    def create_vessel(self, vessel_id: str, arrival_day: int, capacity: float, 
                     cost: float, days_held: int = 0) -> int:
        """Create a new vessel."""
        with self.transaction() as conn:
            cursor = conn.execute("""
                INSERT INTO vessels (vessel_id, arrival_day, capacity, cost, days_held) 
                VALUES (?, ?, ?, ?, ?)
            """, (vessel_id, arrival_day, capacity, cost, days_held))
            
            return cursor.lastrowid
    
    def get_vessel(self, vessel_id: str = None, db_id: int = None) -> Optional[Dict[str, Any]]:
        """Get vessel with cargo and route data."""
        conn = self._get_connection()
        
        if vessel_id:
            cursor = conn.execute("SELECT * FROM vessels WHERE vessel_id = ?", (vessel_id,))
        elif db_id:
            cursor = conn.execute("SELECT * FROM vessels WHERE id = ?", (db_id,))
        else:
            raise ValueError("Either vessel_id or db_id must be provided")
        
        vessel_row = cursor.fetchone()
        if not vessel_row:
            return None
        
        vessel = dict(vessel_row)
        vessel_db_id = vessel['id']
        
        # Get cargo
        cargo_cursor = conn.execute("""
            SELECT c.name as grade, vc.volume, vc.origin, 
                   vc.loading_start_day, vc.loading_end_day
            FROM vessel_cargo vc
            JOIN crudes c ON vc.crude_id = c.id
            WHERE vc.vessel_id = ?
        """, (vessel_db_id,))
        
        cargo = []
        for cargo_row in cargo_cursor.fetchall():
            cargo.append({
                'grade': cargo_row['grade'],
                'volume': cargo_row['volume'],
                'origin': cargo_row['origin'],
                'loading_start_day': cargo_row['loading_start_day'],
                'loading_end_day': cargo_row['loading_end_day']
            })
        
        vessel['cargo'] = cargo
        
        # Get route segments
        route_cursor = conn.execute("""
            SELECT r.origin as from_location, r.destination as to_location,
                   vr.day_start_travel, vr.day_end_travel, 
                   vr.day_start_wait, vr.day_end_wait,
                   r.time_travel as travel_days, vr.action
            FROM vessel_routes vr
            JOIN routes r ON vr.route_id = r.id
            WHERE vr.vessel_id = ?
            ORDER BY vr.segment_order
        """, (vessel_db_id,))
        
        route = []
        for route_row in route_cursor.fetchall():
            segment = {
                'from': route_row['from_location'],
                'to': route_row['to_location'],
                'travel_days': route_row['travel_days']
            }
            
            if route_row['day_start_travel'] is not None:
                segment['day_start_travel'] = route_row['day_start_travel']
            if route_row['day_end_travel'] is not None:
                segment['day_end_travel'] = route_row['day_end_travel']
            if route_row['day_start_wait'] is not None:
                segment['day_start_wait'] = route_row['day_start_wait']
            if route_row['day_end_wait'] is not None:
                segment['day_end_wait'] = route_row['day_end_wait']
            if route_row['action']:
                segment['action'] = route_row['action']
            
            route.append(segment)
        
        vessel['route'] = route
        
        # Remove internal database ID from response
        vessel.pop('id', None)
        
        return vessel
    
    def get_all_vessels(self) -> Dict[str, Dict[str, Any]]:
        """Get all vessels in JSON-compatible format."""
        conn = self._get_connection()
        cursor = conn.execute("SELECT vessel_id FROM vessels ORDER BY vessel_id")
        
        vessels = {}
        for row in cursor.fetchall():
            vessel_id = row['vessel_id']
            vessel_data = self.get_vessel(vessel_id=vessel_id)
            if vessel_data:
                vessels[vessel_id] = vessel_data
        
        return vessels
    
    def save_vessels_data(self, vessels_data: Dict[str, Dict[str, Any]]) -> bool:
        """Save complete vessels data."""
        with self.transaction() as conn:
            # Clear existing vessel data
            conn.execute("DELETE FROM vessel_daily_locations")
            conn.execute("DELETE FROM vessel_routes")
            conn.execute("DELETE FROM vessel_cargo")
            conn.execute("DELETE FROM vessels")
            
            for vessel_id, vessel_info in vessels_data.items():
                # Create vessel
                cursor = conn.execute("""
                    INSERT INTO vessels (vessel_id, arrival_day, capacity, cost, days_held) 
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    vessel_id,
                    vessel_info.get('arrival_day', 0),
                    vessel_info.get('capacity', 0),
                    vessel_info.get('cost', 0),
                    vessel_info.get('days_held', 0)
                ))
                
                vessel_db_id = cursor.lastrowid
                
                # Add cargo
                for cargo_item in vessel_info.get('cargo', []):
                    # Get or create crude
                    crude_cursor = conn.execute("SELECT id FROM crudes WHERE name = ?", (cargo_item.get('grade', ''),))
                    crude_row = crude_cursor.fetchone()
                    
                    if crude_row:
                        crude_id = crude_row['id']
                    else:
                        # Create crude with default values
                        create_cursor = conn.execute(
                            "INSERT INTO crudes (name, margin, origin) VALUES (?, ?, ?)",
                            (cargo_item.get('grade', ''), 15.0, cargo_item.get('origin', 'Unknown'))
                        )
                        crude_id = create_cursor.lastrowid
                    
                    conn.execute("""
                        INSERT INTO vessel_cargo 
                        (vessel_id, crude_id, volume, origin, loading_start_day, loading_end_day) 
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (
                        vessel_db_id,
                        crude_id,
                        cargo_item.get('volume', 0),
                        cargo_item.get('origin', ''),
                        cargo_item.get('loading_start_day', 0),
                        cargo_item.get('loading_end_day', 0)
                    ))
                
                # Add route segments
                for idx, route_segment in enumerate(vessel_info.get('route', [])):
                    # Get or create route
                    route_cursor = conn.execute(
                        "SELECT id FROM routes WHERE origin = ? AND destination = ?",
                        (route_segment.get('from', ''), route_segment.get('to', ''))
                    )
                    route_row = route_cursor.fetchone()
                    
                    if route_row:
                        route_id = route_row['id']
                    else:
                        # Create route
                        create_cursor = conn.execute("""
                            INSERT INTO routes (origin, destination, time_travel) 
                            VALUES (?, ?, ?)
                        """, (
                            route_segment.get('from', ''),
                            route_segment.get('to', ''),
                            route_segment.get('travel_days', 1)
                        ))
                        route_id = create_cursor.lastrowid
                    
                    conn.execute("""
                        INSERT INTO vessel_routes 
                        (vessel_id, route_id, day_start_travel, day_end_travel, 
                         day_start_wait, day_end_wait, action, segment_order) 
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        vessel_db_id,
                        route_id,
                        route_segment.get('day_start_travel'),
                        route_segment.get('day_end_travel'),
                        route_segment.get('day_start_wait'),
                        route_segment.get('day_end_wait'),
                        route_segment.get('action'),
                        idx
                    ))
            
            return True
    
    def get_all_feedstock_requirements(self) -> List[Dict[str, Any]]:
        """Get all feedstock requirements with crude names (grades)."""
        import json
        conn = self._get_connection()
        cursor = conn.execute("""
            SELECT fr.*, c.name as grade 
            FROM feedstock_requirements fr
            JOIN crudes c ON fr.crude_id = c.id
            ORDER BY fr.id
        """)
        requirements = []
        for row in cursor.fetchall():
            req_dict = dict(row)
            # Parse allowed_ldr JSON if it exists
            if req_dict.get('allowed_ldr'):
                try:
                    req_dict['allowed_ldr'] = json.loads(req_dict['allowed_ldr'])
                except (json.JSONDecodeError, TypeError):
                    req_dict['allowed_ldr'] = {}
            requirements.append(req_dict)
        return requirements

    def get_all_routes(self) -> List[Dict[str, Any]]:
        """Get all routes."""
        conn = self._get_connection()
        cursor = conn.execute("SELECT * FROM routes ORDER BY origin, destination")
        return [dict(row) for row in cursor.fetchall()]

    def close(self):
        """Close database connections."""
        if hasattr(self._local, 'connection'):
            self._local.connection.close()
