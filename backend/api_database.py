"""
OASIS Database-Powered API
New API layer using SQLite database instead of JSON files.
Provides atomic operations, concurrent access, and data consistency.

Copyright (c) by Abu Huzaifah Bidin with help from Github Copilot
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import json
from typing import Dict, List, Any, Optional
from datetime import datetime

# Import existing scheduler components
from scheduler import (
    Scheduler, VesselOptimizer, SchedulerOptimizer, 
    Tank, Vessel, Crude, Route, FeedstockParcel, FeedstockRequirement, DailyPlan
)
from scheduler.models import BlendingRecipe

# Import new database components
from database.extended_ops import DatabaseManagerExtended

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})

# Initialize database
DB_PATH = os.path.join(os.path.dirname(__file__), "oasis.db")
db = DatabaseManagerExtended(DB_PATH)

# Migration flag file
MIGRATION_FLAG = os.path.join(os.path.dirname(__file__), ".migration_completed")

def ensure_migration():
    """Ensure JSON data has been migrated to database."""
    if not os.path.exists(MIGRATION_FLAG):
        print("⚠️  Database migration not completed. Run migration first.")
        print("To migrate: python -m database.migration")
        return False
    return True

@app.before_first_request
def initialize_app():
    """Initialize application on first request."""
    if not ensure_migration():
        raise RuntimeError("Database migration required before starting API")

# ==============================================================================
# DATABASE-POWERED DATA ENDPOINTS
# ==============================================================================

@app.route('/api/data', methods=['GET'])
def get_all_data():
    """Get all system data from database."""
    try:
        # Get all data from database
        tanks_data = db.get_all_tanks()
        vessels_data = db.get_all_vessels()
        crudes_data = {crude['name']: crude for crude in db.get_all_crudes()}
        recipes_data = db.get_all_blending_recipes()
        
        # Convert recipes to dictionary format for compatibility
        recipes_dict = {}
        for idx, recipe in enumerate(recipes_data):
            recipes_dict[str(idx)] = recipe
        
        return jsonify({
            'tanks': tanks_data,
            'vessels': vessels_data,
            'crudes': crudes_data,
            'recipes': recipes_dict,
            'timestamp': datetime.now().isoformat(),
            'source': 'database'
        })
        
    except Exception as e:
        return jsonify({'error': f'Failed to load data: {str(e)}'}), 500

@app.route('/api/data/tanks', methods=['GET'])
def get_tanks():
    """Get tanks data from database."""
    try:
        tanks_data = db.get_all_tanks()
        return jsonify(tanks_data)
    except Exception as e:
        return jsonify({'error': f'Failed to load tanks: {str(e)}'}), 500

@app.route('/api/data/tanks', methods=['POST'])
def save_tanks():
    """Save tanks data to database with atomic transaction."""
    try:
        tanks_data = request.get_json()
        if not tanks_data:
            return jsonify({'error': 'No tanks data provided'}), 400
        
        success = db.save_tanks_data(tanks_data)
        
        if success:
            return jsonify({
                'message': 'Tanks saved successfully',
                'timestamp': datetime.now().isoformat(),
                'tanks_count': len(tanks_data)
            })
        else:
            return jsonify({'error': 'Failed to save tanks'}), 500
            
    except Exception as e:
        return jsonify({'error': f'Failed to save tanks: {str(e)}'}), 500

@app.route('/api/data/tanks/<tank_name>', methods=['GET'])
def get_tank(tank_name):
    """Get specific tank data."""
    try:
        tank_data = db.get_tank(name=tank_name)
        if tank_data:
            return jsonify(tank_data)
        else:
            return jsonify({'error': 'Tank not found'}), 404
    except Exception as e:
        return jsonify({'error': f'Failed to get tank: {str(e)}'}), 500

@app.route('/api/data/tanks/<tank_name>', methods=['PUT'])
def update_tank(tank_name):
    """Update specific tank."""
    try:
        update_data = request.get_json()
        if not update_data:
            return jsonify({'error': 'No update data provided'}), 400
        
        success = db.update_tank(name=tank_name, **update_data)
        
        if success:
            return jsonify({
                'message': f'Tank {tank_name} updated successfully',
                'timestamp': datetime.now().isoformat()
            })
        else:
            return jsonify({'error': 'Tank not found or update failed'}), 404
            
    except Exception as e:
        return jsonify({'error': f'Failed to update tank: {str(e)}'}), 500

@app.route('/api/data/tanks/<tank_name>', methods=['DELETE'])
def delete_tank(tank_name):
    """Delete specific tank."""
    try:
        success = db.delete_tank(name=tank_name)
        
        if success:
            return jsonify({
                'message': f'Tank {tank_name} deleted successfully',
                'timestamp': datetime.now().isoformat()
            })
        else:
            return jsonify({'error': 'Tank not found'}), 404
            
    except Exception as e:
        return jsonify({'error': f'Failed to delete tank: {str(e)}'}), 500

@app.route('/api/data/vessels', methods=['GET'])
def get_vessels():
    """Get vessels data from database."""
    try:
        vessels_data = db.get_all_vessels()
        return jsonify(vessels_data)
    except Exception as e:
        return jsonify({'error': f'Failed to load vessels: {str(e)}'}), 500

@app.route('/api/data/vessels', methods=['POST'])
def save_vessels():
    """Save vessels data to database with atomic transaction."""
    try:
        vessels_data = request.get_json()
        if not vessels_data:
            return jsonify({'error': 'No vessels data provided'}), 400
        
        success = db.save_vessels_data(vessels_data)
        
        if success:
            return jsonify({
                'message': 'Vessels saved successfully',
                'timestamp': datetime.now().isoformat(),
                'vessels_count': len(vessels_data)
            })
        else:
            return jsonify({'error': 'Failed to save vessels'}), 500
            
    except Exception as e:
        return jsonify({'error': f'Failed to save vessels: {str(e)}'}), 500

@app.route('/api/data/crudes', methods=['GET'])
def get_crudes():
    """Get crudes data from database."""
    try:
        crudes_list = db.get_all_crudes()
        # Convert to dictionary format for compatibility
        crudes_data = {crude['name']: crude for crude in crudes_list}
        return jsonify(crudes_data)
    except Exception as e:
        return jsonify({'error': f'Failed to load crudes: {str(e)}'}), 500

@app.route('/api/data/crudes', methods=['POST'])
def save_crudes():
    """Save crudes data to database."""
    try:
        crudes_data = request.get_json()
        if not crudes_data:
            return jsonify({'error': 'No crudes data provided'}), 400
        
        # Clear existing crudes and add new ones
        with db.transaction() as conn:
            conn.execute("DELETE FROM crudes")
            
            for crude_name, crude_info in crudes_data.items():
                db.create_crude(
                    name=crude_name,
                    margin=crude_info.get('margin', 15.0),
                    origin=crude_info.get('origin', 'Unknown')
                )
        
        return jsonify({
            'message': 'Crudes saved successfully',
            'timestamp': datetime.now().isoformat(),
            'crudes_count': len(crudes_data)
        })
        
    except Exception as e:
        return jsonify({'error': f'Failed to save crudes: {str(e)}'}), 500

@app.route('/api/data/recipes', methods=['GET'])
def get_recipes():
    """Get recipes data from database."""
    try:
        recipes_list = db.get_all_blending_recipes()
        # Convert to dictionary format for compatibility
        recipes_data = {}
        for idx, recipe in enumerate(recipes_list):
            recipes_data[str(idx)] = recipe
        return jsonify(recipes_data)
    except Exception as e:
        return jsonify({'error': f'Failed to load recipes: {str(e)}'}), 500

@app.route('/api/data/recipes', methods=['POST'])
def save_recipes():
    """Save recipes data to database."""
    try:
        recipes_data = request.get_json()
        if not recipes_data:
            return jsonify({'error': 'No recipes data provided'}), 400
        
        # Convert to list format
        recipes_list = []
        for recipe_id, recipe_info in recipes_data.items():
            recipes_list.append(recipe_info)
        
        success = db.save_blending_recipes(recipes_list)
        
        if success:
            return jsonify({
                'message': 'Recipes saved successfully',
                'timestamp': datetime.now().isoformat(),
                'recipes_count': len(recipes_list)
            })
        else:
            return jsonify({'error': 'Failed to save recipes'}), 500
            
    except Exception as e:
        return jsonify({'error': f'Failed to save recipes: {str(e)}'}), 500

# ==============================================================================
# DATABASE-AWARE SCHEDULER ENDPOINTS
# ==============================================================================

def load_tanks_from_db() -> Dict[str, Tank]:
    """Load tanks from database and convert to Tank objects."""
    tanks_data = db.get_all_tanks()
    tanks = {}
    
    for tank_name, tank_info in tanks_data.items():
        tank = Tank(
            name=tank_name,
            capacity=tank_info['capacity'],
            content=tank_info['content']
        )
        tanks[tank_name] = tank
    
    return tanks

def load_vessels_from_db() -> List[Vessel]:
    """Load vessels from database and convert to Vessel objects."""
    vessels_data = db.get_all_vessels()
    vessels = []
    
    for vessel_id, vessel_info in vessels_data.items():
        # Process cargo data
        cargo = []
        for parcel_info in vessel_info.get("cargo", []):
            cargo.append(FeedstockParcel(
                grade=parcel_info.get("grade", ""),
                volume=parcel_info.get("volume", 0),
                origin=parcel_info.get("origin", ""),
                ldr={
                    int(parcel_info.get("loading_start_day", 0)): 
                    int(parcel_info.get("loading_end_day", 0))
                },
                vessel_id=vessel_id
            ))
        
        # Create vessel object
        vessel = Vessel(
            vessel_id=vessel_id,
            arrival_day=int(vessel_info.get("arrival_day", 0)),
            capacity=float(vessel_info.get("capacity", 0)),
            cost=float(vessel_info.get("cost", 0)),
            cargo=cargo,
            days_held=int(vessel_info.get("days_held", 0))
        )
        
        # Set route attribute
        if "route" in vessel_info:
            vessel.route = vessel_info["route"]
        
        vessels.append(vessel)
    
    return vessels

def load_crudes_from_db() -> Dict[str, Crude]:
    """Load crudes from database and convert to Crude objects."""
    crudes_list = db.get_all_crudes()
    crudes = {}
    
    for crude_info in crudes_list:
        crude = Crude(
            name=crude_info['name'],
            margin=crude_info['margin'],
            origin=crude_info['origin']
        )
        crudes[crude_info['name']] = crude
    
    return crudes

def load_recipes_from_db() -> List[BlendingRecipe]:
    """Load recipes from database and convert to BlendingRecipe objects."""
    recipes_list = db.get_all_blending_recipes()
    recipes = []
    
    for recipe_info in recipes_list:
        recipe = BlendingRecipe(
            name=recipe_info['name'],
            primary_grade=recipe_info['primary_grade'],
            secondary_grade=recipe_info.get('secondary_grade'),
            max_rate=recipe_info['max_rate'],
            primary_fraction=recipe_info['primary_fraction']
        )
        recipes.append(recipe)
    
    return recipes

@app.route('/api/scheduler/run', methods=['POST'])
def run_scheduler():
    """Run scheduler with database data."""
    try:
        data = request.get_json() or {}
        horizon_days = data.get('horizon_days', 30)
        
        print(f"Starting scheduler for {horizon_days} days with database data...")
        
        # Load data from database
        tanks = load_tanks_from_db()
        vessels = load_vessels_from_db()
        crudes = load_crudes_from_db()
        recipes = load_recipes_from_db()
        
        print(f"Loaded from database: {len(tanks)} tanks, {len(vessels)} vessels, {len(crudes)} crudes, {len(recipes)} recipes")
        
        # Create scheduler
        scheduler = Scheduler(
            tanks=tanks,
            blending_recipes=recipes,
            vessels=vessels,
            crude_data=crudes,
            max_processing_rate=100  # Default max processing rate
        )
        
        # Run scheduling
        schedule = scheduler.schedule(horizon_days)
        
        # Convert schedule to JSON-serializable format
        schedule_json = []
        for day, daily_plan in schedule.items():
            plan_dict = {
                'day': day,
                'processing_rates': daily_plan.processing_rates,
                'inventory': daily_plan.inventory,
                'inventory_by_grade': daily_plan.inventory_by_grade,
                'daily_margin': daily_plan.daily_margin,
                'tanks': {}
            }
            
            # Convert tanks to dict
            for tank_name, tank in daily_plan.tanks.items():
                plan_dict['tanks'][tank_name] = {
                    'name': tank.name,
                    'capacity': tank.capacity,
                    'content': tank.content
                }
            
            schedule_json.append(plan_dict)
        
        # Sort by day
        schedule_json.sort(key=lambda x: x['day'])
        
        return jsonify({
            'schedule': schedule_json,
            'horizon_days': horizon_days,
            'total_days': len(schedule_json),
            'timestamp': datetime.now().isoformat(),
            'source': 'database'
        })
        
    except Exception as e:
        return jsonify({'error': f'Scheduler failed: {str(e)}'}), 500

@app.route('/api/vessel-optimizer/optimize', methods=['POST'])
def optimize_vessels():
    """Run vessel optimizer with database data."""
    try:
        data = request.get_json() or {}
        horizon_days = data.get('horizon_days', 30)
        
        print(f"Starting vessel optimization for {horizon_days} days...")
        
        # Load data from database
        crudes = load_crudes_from_db()
        
        # Create vessel optimizer
        vessel_optimizer = VesselOptimizer(crude_data=crudes)
        
        # Run optimization
        optimized_vessels = vessel_optimizer.optimize_and_save(horizon_days=horizon_days)
        
        # Save optimized vessels back to database
        vessels_dict = {}
        for vessel in optimized_vessels:
            # Convert vessel to dictionary format
            cargo_json = []
            for cargo in vessel.cargo:
                ldr_start = next(iter(cargo.ldr.keys())) if cargo.ldr else 0
                ldr_end = next(iter(cargo.ldr.values())) if cargo.ldr else 0
                cargo_json.append({
                    "grade": cargo.grade,
                    "volume": cargo.volume,
                    "origin": cargo.origin,
                    "loading_start_day": ldr_start,
                    "loading_end_day": ldr_end
                })
            
            vessels_dict[vessel.vessel_id] = {
                "vessel_id": vessel.vessel_id,
                "arrival_day": vessel.arrival_day,
                "capacity": vessel.capacity,
                "cost": vessel.cost,
                "days_held": vessel.days_held,
                "cargo": cargo_json,
                "route": getattr(vessel, 'route', [])
            }
        
        # Save to database
        db.save_vessels_data(vessels_dict)
        
        return jsonify({
            'message': 'Vessel optimization completed',
            'optimized_vessels': len(optimized_vessels),
            'horizon_days': horizon_days,
            'timestamp': datetime.now().isoformat(),
            'source': 'database'
        })
        
    except Exception as e:
        return jsonify({'error': f'Vessel optimization failed: {str(e)}'}), 500

# ==============================================================================
# DATABASE MANAGEMENT ENDPOINTS
# ==============================================================================

@app.route('/api/database/status', methods=['GET'])
def database_status():
    """Get database status and statistics."""
    try:
        conn = db._get_connection()
        
        # Get table counts
        tables = [
            'plants', 'crudes', 'tanks', 'tank_contents', 'blending_recipes',
            'vessels', 'vessel_cargo', 'vessel_routes', 'routes',
            'feedstock_requirements', 'vessel_daily_locations'
        ]
        
        counts = {}
        for table in tables:
            cursor = conn.execute(f"SELECT COUNT(*) as count FROM {table}")
            counts[table] = cursor.fetchone()['count']
        
        # Check migration status
        migration_completed = os.path.exists(MIGRATION_FLAG)
        
        return jsonify({
            'status': 'operational',
            'migration_completed': migration_completed,
            'database_path': DB_PATH,
            'table_counts': counts,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({'error': f'Database status check failed: {str(e)}'}), 500

@app.route('/api/database/backup', methods=['POST'])
def backup_database():
    """Create database backup."""
    try:
        backup_name = f"oasis_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
        backup_path = os.path.join(os.path.dirname(DB_PATH), backup_name)
        
        # Copy database file
        import shutil
        shutil.copy2(DB_PATH, backup_path)
        
        return jsonify({
            'message': 'Database backup created successfully',
            'backup_path': backup_path,
            'backup_name': backup_name,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({'error': f'Database backup failed: {str(e)}'}), 500

# ==============================================================================
# MIGRATION ENDPOINT
# ==============================================================================

@app.route('/api/database/migrate', methods=['POST'])
def migrate_database():
    """Run database migration from JSON files."""
    try:
        from database.migration import migrate_from_json
        
        # Get paths from request or use defaults
        data = request.get_json() or {}
        static_dir = data.get('static_data_dir', 'static_data')
        dynamic_dir = data.get('dynamic_data_dir', 'dynamic_data')
        
        # Run migration
        results = migrate_from_json(
            db_path=DB_PATH,
            static_data_dir=static_dir,
            dynamic_data_dir=dynamic_dir
        )
        
        # Create migration flag if successful
        if results['status'] == 'completed':
            with open(MIGRATION_FLAG, 'w') as f:
                f.write(datetime.now().isoformat())
        
        return jsonify(results)
        
    except Exception as e:
        return jsonify({'error': f'Migration failed: {str(e)}'}), 500

# ==============================================================================
# ERROR HANDLERS
# ==============================================================================

@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Endpoint not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({'error': 'Internal server error'}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
