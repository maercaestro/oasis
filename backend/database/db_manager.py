"""
OASIS Database Manager
Core SQLite database operations for the OASIS system.
Provides ACID transactions and thread-safe operations.

Copyright (c) by Abu Huzaifah Bidin with help from Github Copilot
"""

import sqlite3
import json
import threading
from typing import Dict, List, Any, Optional, Union
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path


class DatabaseManager:
    """
    Main database manager for OASIS system.
    Provides thread-safe ACID transactions for all data operations.
    """
    
    def __init__(self, db_path: str = "oasis.db"):
        """
        Initialize database manager.
        
        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self._local = threading.local()
        self._init_database()
    
    def _get_connection(self) -> sqlite3.Connection:
        """Get thread-local database connection."""
        if not hasattr(self._local, 'connection'):
            self._local.connection = sqlite3.connect(
                self.db_path,
                check_same_thread=False,
                isolation_level=None  # Autocommit mode
            )
            self._local.connection.row_factory = sqlite3.Row
            # Enable foreign keys
            self._local.connection.execute("PRAGMA foreign_keys = ON")
        return self._local.connection
    
    @contextmanager
    def transaction(self):
        """Context manager for database transactions."""
        conn = self._get_connection()
        try:
            conn.execute("BEGIN")
            yield conn
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
    
    def _init_database(self):
        """Initialize database schema."""
        conn = self._get_connection()
        
        # Create tables with proper relationships
        conn.executescript("""
        -- Plants table
        CREATE TABLE IF NOT EXISTS plants (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            capacity REAL NOT NULL,
            base_crude_capacity REAL NOT NULL,
            max_inventory REAL NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        
        -- Crudes table
        CREATE TABLE IF NOT EXISTS crudes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            margin REAL NOT NULL,
            origin TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        
        -- Tanks table
        CREATE TABLE IF NOT EXISTS tanks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            capacity REAL NOT NULL,
            plant_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (plant_id) REFERENCES plants(id)
        );
        
        -- Tank contents table (normalized storage)
        CREATE TABLE IF NOT EXISTS tank_contents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tank_id INTEGER NOT NULL,
            crude_id INTEGER NOT NULL,
            volume REAL NOT NULL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (tank_id) REFERENCES tanks(id) ON DELETE CASCADE,
            FOREIGN KEY (crude_id) REFERENCES crudes(id),
            UNIQUE(tank_id, crude_id)
        );
        
        -- Routes table
        CREATE TABLE IF NOT EXISTS routes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            origin TEXT NOT NULL,
            destination TEXT NOT NULL,
            time_travel REAL NOT NULL,
            cost REAL DEFAULT 10000.0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(origin, destination)
        );
        
        -- Blending recipes table
        CREATE TABLE IF NOT EXISTS blending_recipes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            primary_grade_id INTEGER NOT NULL,
            secondary_grade_id INTEGER,
            max_rate REAL NOT NULL,
            primary_fraction REAL NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (primary_grade_id) REFERENCES crudes(id),
            FOREIGN KEY (secondary_grade_id) REFERENCES crudes(id)
        );
        
        -- Vessels table
        CREATE TABLE IF NOT EXISTS vessels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vessel_id TEXT UNIQUE NOT NULL,
            arrival_day INTEGER NOT NULL,
            capacity REAL NOT NULL,
            cost REAL NOT NULL,
            days_held INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        
        -- Vessel cargo table (many-to-many with crudes)
        CREATE TABLE IF NOT EXISTS vessel_cargo (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vessel_id INTEGER NOT NULL,
            crude_id INTEGER NOT NULL,
            volume REAL NOT NULL,
            origin TEXT NOT NULL,
            loading_start_day INTEGER DEFAULT 0,
            loading_end_day INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (vessel_id) REFERENCES vessels(id) ON DELETE CASCADE,
            FOREIGN KEY (crude_id) REFERENCES crudes(id)
        );
        
        -- Vessel routes table (normalized route segments)
        CREATE TABLE IF NOT EXISTS vessel_routes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vessel_id INTEGER NOT NULL,
            route_id INTEGER NOT NULL,
            day_start_travel INTEGER,
            day_end_travel INTEGER,
            day_start_wait INTEGER,
            day_end_wait INTEGER,
            action TEXT,
            segment_order INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (vessel_id) REFERENCES vessels(id) ON DELETE CASCADE,
            FOREIGN KEY (route_id) REFERENCES routes(id)
        );
        
        -- Daily vessel locations (tracking table)
        CREATE TABLE IF NOT EXISTS vessel_daily_locations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vessel_id INTEGER NOT NULL,
            day INTEGER NOT NULL,
            location TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (vessel_id) REFERENCES vessels(id) ON DELETE CASCADE,
            UNIQUE(vessel_id, day)
        );
        
        -- Feedstock requirements table
        CREATE TABLE IF NOT EXISTS feedstock_requirements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            crude_id INTEGER NOT NULL,
            volume REAL NOT NULL,
            origin TEXT NOT NULL,
            allowed_ldr_start INTEGER NOT NULL,
            allowed_ldr_end INTEGER NOT NULL,
            required_arrival_by INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (crude_id) REFERENCES crudes(id)
        );
        
        -- Daily plans table
        CREATE TABLE IF NOT EXISTS daily_plans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            day INTEGER UNIQUE NOT NULL,
            total_processing_rate REAL DEFAULT 0,
            inventory REAL DEFAULT 0,
            daily_margin REAL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        
        -- Daily plan processing rates (many-to-many with recipes)
        CREATE TABLE IF NOT EXISTS daily_plan_processing (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            daily_plan_id INTEGER NOT NULL,
            recipe_id INTEGER NOT NULL,
            processing_rate REAL NOT NULL,
            FOREIGN KEY (daily_plan_id) REFERENCES daily_plans(id) ON DELETE CASCADE,
            FOREIGN KEY (recipe_id) REFERENCES blending_recipes(id),
            UNIQUE(daily_plan_id, recipe_id)
        );
        
        -- Daily inventory by grade
        CREATE TABLE IF NOT EXISTS daily_inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            daily_plan_id INTEGER NOT NULL,
            crude_id INTEGER NOT NULL,
            volume REAL NOT NULL,
            FOREIGN KEY (daily_plan_id) REFERENCES daily_plans(id) ON DELETE CASCADE,
            FOREIGN KEY (crude_id) REFERENCES crudes(id),
            UNIQUE(daily_plan_id, crude_id)
        );
        
        -- Create indexes for performance
        CREATE INDEX IF NOT EXISTS idx_tank_contents_tank_id ON tank_contents(tank_id);
        CREATE INDEX IF NOT EXISTS idx_tank_contents_crude_id ON tank_contents(crude_id);
        CREATE INDEX IF NOT EXISTS idx_vessel_cargo_vessel_id ON vessel_cargo(vessel_id);
        CREATE INDEX IF NOT EXISTS idx_vessel_cargo_crude_id ON vessel_cargo(crude_id);
        CREATE INDEX IF NOT EXISTS idx_vessel_routes_vessel_id ON vessel_routes(vessel_id);
        CREATE INDEX IF NOT EXISTS idx_vessel_daily_locations_vessel_day ON vessel_daily_locations(vessel_id, day);
        CREATE INDEX IF NOT EXISTS idx_daily_plans_day ON daily_plans(day);
        CREATE INDEX IF NOT EXISTS idx_daily_plan_processing_plan_id ON daily_plan_processing(daily_plan_id);
        CREATE INDEX IF NOT EXISTS idx_daily_inventory_plan_id ON daily_inventory(daily_plan_id);
        
        -- Create triggers for updated_at timestamps
        CREATE TRIGGER IF NOT EXISTS update_plants_timestamp 
        AFTER UPDATE ON plants FOR EACH ROW
        BEGIN
            UPDATE plants SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
        END;
        
        CREATE TRIGGER IF NOT EXISTS update_crudes_timestamp 
        AFTER UPDATE ON crudes FOR EACH ROW
        BEGIN
            UPDATE crudes SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
        END;
        
        CREATE TRIGGER IF NOT EXISTS update_tanks_timestamp 
        AFTER UPDATE ON tanks FOR EACH ROW
        BEGIN
            UPDATE tanks SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
        END;
        
        CREATE TRIGGER IF NOT EXISTS update_tank_contents_timestamp 
        AFTER UPDATE ON tank_contents FOR EACH ROW
        BEGIN
            UPDATE tank_contents SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
        END;
        
        CREATE TRIGGER IF NOT EXISTS update_blending_recipes_timestamp 
        AFTER UPDATE ON blending_recipes FOR EACH ROW
        BEGIN
            UPDATE blending_recipes SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
        END;
        
        CREATE TRIGGER IF NOT EXISTS update_vessels_timestamp 
        AFTER UPDATE ON vessels FOR EACH ROW
        BEGIN
            UPDATE vessels SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
        END;
        
        CREATE TRIGGER IF NOT EXISTS update_feedstock_requirements_timestamp 
        AFTER UPDATE ON feedstock_requirements FOR EACH ROW
        BEGIN
            UPDATE feedstock_requirements SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
        END;
        
        CREATE TRIGGER IF NOT EXISTS update_daily_plans_timestamp 
        AFTER UPDATE ON daily_plans FOR EACH ROW
        BEGIN
            UPDATE daily_plans SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
        END;
        """)
    
    # CRUD Operations for Plants
    def create_plant(self, name: str, capacity: float, base_crude_capacity: float, max_inventory: float) -> int:
        """Create a new plant."""
        with self.transaction() as conn:
            cursor = conn.execute(
                "INSERT INTO plants (name, capacity, base_crude_capacity, max_inventory) VALUES (?, ?, ?, ?)",
                (name, capacity, base_crude_capacity, max_inventory)
            )
            return cursor.lastrowid
    
    def get_plant(self, plant_id: int = None, name: str = None) -> Optional[Dict[str, Any]]:
        """Get plant by ID or name."""
        conn = self._get_connection()
        if plant_id:
            cursor = conn.execute("SELECT * FROM plants WHERE id = ?", (plant_id,))
        elif name:
            cursor = conn.execute("SELECT * FROM plants WHERE name = ?", (name,))
        else:
            raise ValueError("Either plant_id or name must be provided")
        
        row = cursor.fetchone()
        return dict(row) if row else None
    
    def get_all_plants(self) -> List[Dict[str, Any]]:
        """Get all plants."""
        conn = self._get_connection()
        cursor = conn.execute("SELECT * FROM plants ORDER BY name")
        return [dict(row) for row in cursor.fetchall()]
    
    def update_plant(self, plant_id: int, **kwargs) -> bool:
        """Update plant fields."""
        if not kwargs:
            return False
        
        fields = []
        values = []
        for key, value in kwargs.items():
            if key in ['name', 'capacity', 'base_crude_capacity', 'max_inventory']:
                fields.append(f"{key} = ?")
                values.append(value)
        
        if not fields:
            return False
        
        values.append(plant_id)
        with self.transaction() as conn:
            cursor = conn.execute(
                f"UPDATE plants SET {', '.join(fields)} WHERE id = ?",
                values
            )
            return cursor.rowcount > 0
    
    def delete_plant(self, plant_id: int) -> bool:
        """Delete a plant."""
        with self.transaction() as conn:
            cursor = conn.execute("DELETE FROM plants WHERE id = ?", (plant_id,))
            return cursor.rowcount > 0
    
    # CRUD Operations for Crudes
    def create_crude(self, name: str, margin: float, origin: str) -> int:
        """Create a new crude."""
        with self.transaction() as conn:
            cursor = conn.execute(
                "INSERT INTO crudes (name, margin, origin) VALUES (?, ?, ?)",
                (name, margin, origin)
            )
            return cursor.lastrowid
    
    def get_crude(self, crude_id: int = None, name: str = None) -> Optional[Dict[str, Any]]:
        """Get crude by ID or name."""
        conn = self._get_connection()
        if crude_id:
            cursor = conn.execute("SELECT * FROM crudes WHERE id = ?", (crude_id,))
        elif name:
            cursor = conn.execute("SELECT * FROM crudes WHERE name = ?", (name,))
        else:
            raise ValueError("Either crude_id or name must be provided")
        
        row = cursor.fetchone()
        return dict(row) if row else None
    
    def get_all_crudes(self) -> List[Dict[str, Any]]:
        """Get all crudes."""
        conn = self._get_connection()
        cursor = conn.execute("SELECT * FROM crudes ORDER BY name")
        return [dict(row) for row in cursor.fetchall()]
    
    def update_crude(self, crude_id: int, **kwargs) -> bool:
        """Update crude fields."""
        if not kwargs:
            return False
        
        fields = []
        values = []
        for key, value in kwargs.items():
            if key in ['name', 'margin', 'origin']:
                fields.append(f"{key} = ?")
                values.append(value)
        
        if not fields:
            return False
        
        values.append(crude_id)
        with self.transaction() as conn:
            cursor = conn.execute(
                f"UPDATE crudes SET {', '.join(fields)} WHERE id = ?",
                values
            )
            return cursor.rowcount > 0
    
    def delete_crude(self, crude_id: int) -> bool:
        """Delete a crude."""
        with self.transaction() as conn:
            cursor = conn.execute("DELETE FROM crudes WHERE id = ?", (crude_id,))
            return cursor.rowcount > 0
    
    # Continue with other CRUD operations...
    # This is getting quite long, so I'll add the remaining methods in subsequent files
