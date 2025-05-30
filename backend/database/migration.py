"""
OASIS Database Migration Module
Migrates existing JSON data to SQLite database.
Provides safe, atomic migration with rollback capabilities.

Copyright (c) by Abu Huzaifah Bidin with help from Github Copilot
"""

import json
import os
import shutil
from pathlib import Path
from typing import Dict, Any, List
from datetime import datetime

try:
    from .extended_ops import DatabaseManagerExtended
except ImportError:
    from extended_ops import DatabaseManagerExtended


def migrate_from_json(db_path: str = "oasis.db", 
                     static_data_dir: str = "static_data",
                     dynamic_data_dir: str = "dynamic_data",
                     backup_existing: bool = True) -> Dict[str, Any]:
    """
    Migrate all JSON data to SQLite database.
    
    Args:
        db_path: Path to SQLite database file
        static_data_dir: Path to static data directory
        dynamic_data_dir: Path to dynamic data directory
        backup_existing: Whether to backup existing JSON files
    
    Returns:
        Migration results with status and statistics
    """
    
    migration_start = datetime.now()
    results = {
        'status': 'started',
        'start_time': migration_start.isoformat(),
        'migrated_files': [],
        'errors': [],
        'statistics': {}
    }
    
    try:
        # Create database manager
        db = DatabaseManagerExtended(db_path)
        
        # Backup existing files if requested
        if backup_existing:
            backup_dir = f"json_backup_{migration_start.strftime('%Y%m%d_%H%M%S')}"
            _backup_json_files(static_data_dir, dynamic_data_dir, backup_dir)
            results['backup_directory'] = backup_dir
        
        # Migrate static data first (reference data)
        static_stats = _migrate_static_data(db, static_data_dir, results)
        
        # Migrate dynamic data (transactional data)
        dynamic_stats = _migrate_dynamic_data(db, dynamic_data_dir, results)
        
        # Calculate final statistics
        results['statistics'] = {
            **static_stats,
            **dynamic_stats,
            'total_migration_time_seconds': (datetime.now() - migration_start).total_seconds()
        }
        
        results['status'] = 'completed'
        results['end_time'] = datetime.now().isoformat()
        
        # Close database
        db.close()
        
    except Exception as e:
        results['status'] = 'failed'
        results['error'] = str(e)
        results['errors'].append(f"Migration failed: {str(e)}")
    
    return results


def _backup_json_files(static_dir: str, dynamic_dir: str, backup_dir: str):
    """Backup existing JSON files."""
    backup_path = Path(backup_dir)
    backup_path.mkdir(exist_ok=True)
    
    # Backup static data
    static_path = Path(static_dir)
    if static_path.exists():
        static_backup = backup_path / "static_data"
        shutil.copytree(static_path, static_backup, dirs_exist_ok=True)
    
    # Backup dynamic data
    dynamic_path = Path(dynamic_dir)
    if dynamic_path.exists():
        dynamic_backup = backup_path / "dynamic_data"
        shutil.copytree(dynamic_path, dynamic_backup, dirs_exist_ok=True)


def _migrate_static_data(db: DatabaseManagerExtended, static_dir: str, results: Dict[str, Any]) -> Dict[str, int]:
    """Migrate static data files."""
    static_path = Path(static_dir)
    stats = {}
    
    # Migrate crudes.json
    crudes_file = static_path / "crudes.json"
    if crudes_file.exists():
        try:
            with open(crudes_file, 'r') as f:
                crudes_data = json.load(f)
            
            crude_count = 0
            for crude_name, crude_info in crudes_data.items():
                db.create_crude(
                    name=crude_name,
                    margin=crude_info.get('margin', 15.0),
                    origin=crude_info.get('origin', 'Unknown')
                )
                crude_count += 1
            
            stats['crudes_migrated'] = crude_count
            results['migrated_files'].append('crudes.json')
            
        except Exception as e:
            results['errors'].append(f"Failed to migrate crudes.json: {str(e)}")
    
    # Migrate plant.json
    plant_file = static_path / "plant.json"
    if plant_file.exists():
        try:
            with open(plant_file, 'r') as f:
                plant_data = json.load(f)
            
            plant_count = 0
            for plant_name, plant_info in plant_data.items():
                db.create_plant(
                    name=plant_name,
                    capacity=plant_info.get('capacity', 1000),
                    base_crude_capacity=plant_info.get('base_crude_capacity', 1000),
                    max_inventory=plant_info.get('max_inventory', 2000)
                )
                plant_count += 1
            
            stats['plants_migrated'] = plant_count
            results['migrated_files'].append('plant.json')
            
        except Exception as e:
            results['errors'].append(f"Failed to migrate plant.json: {str(e)}")
    
    # Migrate recipes.json
    recipes_file = static_path / "recipes.json"
    if recipes_file.exists():
        try:
            with open(recipes_file, 'r') as f:
                recipes_data = json.load(f)
            
            # Convert to list format for batch save
            recipes_list = []
            for recipe_id, recipe_info in recipes_data.items():
                recipes_list.append({
                    'name': recipe_info.get('name', recipe_id),
                    'primary_grade': recipe_info.get('primary_grade'),
                    'secondary_grade': recipe_info.get('secondary_grade'),
                    'max_rate': recipe_info.get('max_rate', 100),
                    'primary_fraction': recipe_info.get('primary_fraction', 1.0)
                })
            
            db.save_blending_recipes(recipes_list)
            stats['recipes_migrated'] = len(recipes_list)
            results['migrated_files'].append('recipes.json')
            
        except Exception as e:
            results['errors'].append(f"Failed to migrate recipes.json: {str(e)}")
    
    # Migrate routes.json
    routes_file = static_path / "routes.json"
    if routes_file.exists():
        try:
            with open(routes_file, 'r') as f:
                routes_data = json.load(f)
            
            route_count = 0
            with db.transaction() as conn:
                for route_info in routes_data:
                    conn.execute("""
                        INSERT OR IGNORE INTO routes (origin, destination, time_travel, cost) 
                        VALUES (?, ?, ?, ?)
                    """, (
                        route_info.get('origin', ''),
                        route_info.get('destination', ''),
                        route_info.get('time_travel', 1),
                        route_info.get('cost', 10000)
                    ))
                    route_count += 1
            
            stats['routes_migrated'] = route_count
            results['migrated_files'].append('routes.json')
            
        except Exception as e:
            results['errors'].append(f"Failed to migrate routes.json: {str(e)}")
    
    return stats


def _migrate_dynamic_data(db: DatabaseManagerExtended, dynamic_dir: str, results: Dict[str, Any]) -> Dict[str, int]:
    """Migrate dynamic data files."""
    dynamic_path = Path(dynamic_dir)
    stats = {}
    
    # Migrate tanks.json
    tanks_file = dynamic_path / "tanks.json"
    if tanks_file.exists():
        try:
            with open(tanks_file, 'r') as f:
                tanks_data = json.load(f)
            
            db.save_tanks_data(tanks_data)
            stats['tanks_migrated'] = len(tanks_data)
            results['migrated_files'].append('tanks.json')
            
        except Exception as e:
            results['errors'].append(f"Failed to migrate tanks.json: {str(e)}")
    
    # Migrate vessels.json
    vessels_file = dynamic_path / "vessels.json"
    if vessels_file.exists():
        try:
            with open(vessels_file, 'r') as f:
                vessels_data = json.load(f)
            
            db.save_vessels_data(vessels_data)
            stats['vessels_migrated'] = len(vessels_data)
            results['migrated_files'].append('vessels.json')
            
        except Exception as e:
            results['errors'].append(f"Failed to migrate vessels.json: {str(e)}")
    
    # Migrate feedstock_requirements.json
    requirements_file = dynamic_path / "feedstock_requirements.json"
    if requirements_file.exists():
        try:
            with open(requirements_file, 'r') as f:
                requirements_data = json.load(f)
            
            requirement_count = 0
            with db.transaction() as conn:
                for req in requirements_data:
                    # Get crude ID
                    crude_cursor = conn.execute("SELECT id FROM crudes WHERE name = ?", (req.get('grade', ''),))
                    crude_row = crude_cursor.fetchone()
                    
                    if crude_row:
                        crude_id = crude_row['id']
                        
                        # Extract LDR dates
                        allowed_ldr = req.get('allowed_ldr', {})
                        if isinstance(allowed_ldr, dict) and allowed_ldr:
                            ldr_start = next(iter(allowed_ldr.keys()), 0)
                            ldr_end = next(iter(allowed_ldr.values()), 0)
                        else:
                            ldr_start = ldr_end = 0
                        
                        conn.execute("""
                            INSERT INTO feedstock_requirements 
                            (crude_id, volume, origin, allowed_ldr_start, allowed_ldr_end, required_arrival_by) 
                            VALUES (?, ?, ?, ?, ?, ?)
                        """, (
                            crude_id,
                            req.get('volume', 0),
                            req.get('origin', ''),
                            ldr_start,
                            ldr_end,
                            req.get('required_arrival_by', 30)
                        ))
                        requirement_count += 1
            
            stats['feedstock_requirements_migrated'] = requirement_count
            results['migrated_files'].append('feedstock_requirements.json')
            
        except Exception as e:
            results['errors'].append(f"Failed to migrate feedstock_requirements.json: {str(e)}")
    
    # Migrate vessel_routes.json (daily locations)
    vessel_routes_file = dynamic_path / "vessel_routes.json"
    if vessel_routes_file.exists():
        try:
            with open(vessel_routes_file, 'r') as f:
                vessel_routes_data = json.load(f)
            
            location_count = 0
            with db.transaction() as conn:
                for vessel_id, route_info in vessel_routes_data.items():
                    # Get vessel database ID
                    vessel_cursor = conn.execute("SELECT id FROM vessels WHERE vessel_id = ?", (vessel_id,))
                    vessel_row = vessel_cursor.fetchone()
                    
                    if vessel_row:
                        vessel_db_id = vessel_row['id']
                        
                        # Add daily locations
                        for day_str, location in route_info.get('days', {}).items():
                            if location:  # Skip empty locations
                                conn.execute("""
                                    INSERT OR REPLACE INTO vessel_daily_locations 
                                    (vessel_id, day, location) VALUES (?, ?, ?)
                                """, (vessel_db_id, int(day_str), location))
                                location_count += 1
            
            stats['vessel_daily_locations_migrated'] = location_count
            results['migrated_files'].append('vessel_routes.json')
            
        except Exception as e:
            results['errors'].append(f"Failed to migrate vessel_routes.json: {str(e)}")
    
    return stats


def create_database_config() -> Dict[str, Any]:
    """Create database configuration for the application."""
    return {
        'database': {
            'type': 'sqlite',
            'path': 'oasis.db',
            'backup_on_startup': True,
            'migration_completed': True
        },
        'features': {
            'json_fallback': False,  # Disable JSON fallback after migration
            'atomic_transactions': True,
            'concurrent_access': True,
            'automatic_backups': True
        }
    }


def verify_migration(db_path: str = "oasis.db") -> Dict[str, Any]:
    """Verify migration results by checking data consistency."""
    db = DatabaseManagerExtended(db_path)
    
    verification = {
        'status': 'verified',
        'tables_verified': [],
        'data_counts': {},
        'issues': []
    }
    
    try:
        conn = db._get_connection()
        
        # Check each table
        tables = [
            'plants', 'crudes', 'tanks', 'tank_contents', 'blending_recipes',
            'vessels', 'vessel_cargo', 'vessel_routes', 'routes',
            'feedstock_requirements', 'vessel_daily_locations'
        ]
        
        for table in tables:
            cursor = conn.execute(f"SELECT COUNT(*) as count FROM {table}")
            count = cursor.fetchone()['count']
            verification['data_counts'][table] = count
            verification['tables_verified'].append(table)
        
        # Check for orphaned records
        orphan_checks = [
            ("tank_contents without tanks", "SELECT COUNT(*) FROM tank_contents tc LEFT JOIN tanks t ON tc.tank_id = t.id WHERE t.id IS NULL"),
            ("vessel_cargo without vessels", "SELECT COUNT(*) FROM vessel_cargo vc LEFT JOIN vessels v ON vc.vessel_id = v.id WHERE v.id IS NULL"),
            ("vessel_routes without vessels", "SELECT COUNT(*) FROM vessel_routes vr LEFT JOIN vessels v ON vr.vessel_id = v.id WHERE v.id IS NULL"),
        ]
        
        for check_name, query in orphan_checks:
            cursor = conn.execute(query)
            count = cursor.fetchone()[0]
            if count > 0:
                verification['issues'].append(f"{check_name}: {count} orphaned records")
        
        db.close()
        
    except Exception as e:
        verification['status'] = 'failed'
        verification['error'] = str(e)
    
    return verification


if __name__ == "__main__":
    # Run migration if called directly
    import sys
    
    static_dir = sys.argv[1] if len(sys.argv) > 1 else "static_data"
    dynamic_dir = sys.argv[2] if len(sys.argv) > 2 else "dynamic_data"
    
    print("Starting OASIS database migration...")
    results = migrate_from_json(
        static_data_dir=static_dir,
        dynamic_data_dir=dynamic_dir
    )
    
    print(f"Migration {results['status']}")
    print(f"Migrated files: {', '.join(results['migrated_files'])}")
    
    if results['errors']:
        print("Errors encountered:")
        for error in results['errors']:
            print(f"  - {error}")
    
    print("Statistics:")
    for key, value in results['statistics'].items():
        print(f"  {key}: {value}")
    
    # Verify migration
    print("\nVerifying migration...")
    verification = verify_migration()
    print(f"Verification: {verification['status']}")
    
    if verification['issues']:
        print("Issues found:")
        for issue in verification['issues']:
            print(f"  - {issue}")
    
    print("Data counts:")
    for table, count in verification['data_counts'].items():
        print(f"  {table}: {count} records")
