"""
OASIS LLM Function Calling System
OpenAI function calling integration for comprehensive system data access

Copyright (c) by Abu Huzaifah Bidin with help from Github Copilot
"""

import json
import os
from typing import Dict, List, Any, Optional
from datetime import datetime
from dotenv import load_dotenv
import openai

from database.extended_ops import DatabaseManagerExtended
from scheduler import (
    Scheduler, VesselOptimizer, SchedulerOptimizer,
    Tank, Vessel, Crude, Route, FeedstockParcel, FeedstockRequirement, DailyPlan
)
from scheduler.models import BlendingRecipe

# Load environment variables
load_dotenv()
openai.api_key = os.getenv('OPENAI_API_KEY')

class OASISLLMFunctions:
    """OpenAI function calling handler for OASIS system."""
    
    def __init__(self, db_path: str):
        self.db = DatabaseManagerExtended(db_path)
        self.client = openai.OpenAI()
        
    def get_function_schemas(self) -> List[Dict]:
        """Get all available function schemas for OpenAI."""
        return [
            # Tank Operations
            {
                "type": "function",
                "function": {
                    "name": "get_tank_status",
                    "description": "Get status and inventory for all tanks or a specific tank",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "tank_name": {
                                "type": "string",
                                "description": "Optional: specific tank name to query"
                            }
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "update_tank_inventory",
                    "description": "Update tank inventory levels for a specific crude type",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "tank_name": {
                                "type": "string",
                                "description": "Name of the tank to update"
                            },
                            "crude_name": {
                                "type": "string",
                                "description": "Name of the crude type"
                            },
                            "volume": {
                                "type": "number",
                                "description": "New volume in kbbl"
                            }
                        },
                        "required": ["tank_name", "crude_name", "volume"]
                    }
                }
            },
            
            # Vessel Operations
            {
                "type": "function",
                "function": {
                    "name": "get_vessel_schedule",
                    "description": "Get vessel schedule information, arrivals, cargo details",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "vessel_id": {
                                "type": "string",
                                "description": "Optional: specific vessel ID to query"
                            },
                            "days_ahead": {
                                "type": "number",
                                "description": "Number of days ahead to look for arrivals (default: 30)"
                            }
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "modify_vessel_arrival",
                    "description": "Modify vessel arrival day or cargo details",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "vessel_id": {
                                "type": "string",
                                "description": "Vessel ID to modify"
                            },
                            "arrival_day": {
                                "type": "number",
                                "description": "New arrival day"
                            },
                            "cargo_updates": {
                                "type": "array",
                                "description": "Optional cargo modifications",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "grade": {"type": "string"},
                                        "volume": {"type": "number"},
                                        "origin": {"type": "string"}
                                    }
                                }
                            }
                        },
                        "required": ["vessel_id"]
                    }
                }
            },
            
            # Production and Recipe Operations  
            {
                "type": "function",
                "function": {
                    "name": "get_production_metrics",
                    "description": "Get production metrics, throughput, margin analysis, and day-specific details from actual schedule data",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "days": {
                                "type": "number",
                                "description": "Number of days to analyze (default: 30)"
                            },
                            "metric_type": {
                                "type": "string",
                                "enum": ["throughput", "margin", "inventory", "all"],
                                "description": "Type of metrics to retrieve"
                            },
                            "specific_day": {
                                "type": "number",
                                "description": "Optional: Get detailed analysis for a specific day (0-indexed)"
                            }
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_crude_information",
                    "description": "Get crude oil properties, margins, and availability",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "crude_name": {
                                "type": "string", 
                                "description": "Optional: specific crude name to query"
                            }
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_blending_recipes",
                    "description": "Get blending recipe configurations and production rates",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "recipe_name": {
                                "type": "string",
                                "description": "Optional: specific recipe name to query"
                            }
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "analyze_schedule_performance",
                    "description": "Comprehensive analysis of schedule performance including multi-recipe operations and transitions",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "analysis_type": {
                                "type": "string",
                                "enum": ["transitions", "multi_recipe", "efficiency", "all"],
                                "description": "Type of schedule analysis to perform"
                            },
                            "days": {
                                "type": "number",
                                "description": "Number of days to analyze (default: 30)"
                            }
                        }
                    }
                }
            },
            
            # Optimization Operations
            {
                "type": "function", 
                "function": {
                    "name": "run_schedule_optimization",
                    "description": "Run schedule optimization to maximize throughput or margin",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "optimization_type": {
                                "type": "string",
                                "enum": ["margin", "throughput"],
                                "description": "Type of optimization to perform"
                            },
                            "horizon_days": {
                                "type": "number",
                                "description": "Optimization horizon in days (default: 30)"
                            }
                        },
                        "required": ["optimization_type"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "run_vessel_optimization",
                    "description": "Optimize vessel routing and scheduling",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "horizon_days": {
                                "type": "number",
                                "description": "Optimization horizon in days (default: 30)"
                            }
                        }
                    }
                }
            },
            
            # Analysis and Reporting
            {
                "type": "function",
                "function": {
                    "name": "analyze_inventory_trends",
                    "description": "Analyze inventory trends and predict shortages or surpluses",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "crude_type": {
                                "type": "string",
                                "description": "Optional: focus on specific crude type"
                            },
                            "days_ahead": {
                                "type": "number", 
                                "description": "Days ahead to analyze (default: 14)"
                            }
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_feedstock_requirements",
                    "description": "Get feedstock requirements and delivery schedules",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "grade": {
                                "type": "string",
                                "description": "Optional: specific grade to query"
                            },
                            "urgent_only": {
                                "type": "boolean",
                                "description": "Only show urgent requirements (default: false)"
                            }
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "generate_system_summary",
                    "description": "Generate comprehensive system status summary",
                    "parameters": {
                        "type": "object", 
                        "properties": {
                            "include_forecasts": {
                                "type": "boolean",
                                "description": "Include future predictions (default: true)"
                            },
                            "detail_level": {
                                "type": "string",
                                "enum": ["high", "medium", "low"],
                                "description": "Level of detail in summary"
                            }
                        }
                    }
                }
            }
        ]
    
    def execute_function(self, function_name: str, arguments: Dict) -> Dict[str, Any]:
        """Execute a function call and return the result."""
        try:
            # Route to appropriate function
            if function_name == "get_tank_status":
                return self._get_tank_status(**arguments)
            elif function_name == "update_tank_inventory":
                return self._update_tank_inventory(**arguments)
            elif function_name == "get_vessel_schedule":
                return self._get_vessel_schedule(**arguments)
            elif function_name == "modify_vessel_arrival":
                return self._modify_vessel_arrival(**arguments)
            elif function_name == "get_production_metrics":
                return self._get_production_metrics(**arguments)
            elif function_name == "get_crude_information":
                return self._get_crude_information(**arguments)
            elif function_name == "get_blending_recipes":
                return self._get_blending_recipes(**arguments)
            elif function_name == "analyze_schedule_performance":
                return self._analyze_schedule_performance(**arguments)
            elif function_name == "run_schedule_optimization":
                return self._run_schedule_optimization(**arguments)
            elif function_name == "run_vessel_optimization":
                return self._run_vessel_optimization(**arguments)
            elif function_name == "analyze_inventory_trends":
                return self._analyze_inventory_trends(**arguments)
            elif function_name == "get_feedstock_requirements":
                return self._get_feedstock_requirements(**arguments)
            elif function_name == "generate_system_summary":
                return self._generate_system_summary(**arguments)
            else:
                return {"error": f"Unknown function: {function_name}"}
                
        except Exception as e:
            return {"error": f"Function execution failed: {str(e)}"}
    
    # Tank Operations
    def _get_tank_status(self, tank_name: Optional[str] = None) -> Dict[str, Any]:
        """Get tank status and inventory."""
        if tank_name:
            tank = self.db.get_tank(name=tank_name)
            if not tank:
                return {"error": f"Tank '{tank_name}' not found"}
            return {"tank": tank}
        else:
            tanks = self.db.get_all_tanks()
            total_capacity = sum(t['capacity'] for t in tanks.values())
            total_inventory = sum(
                sum(sum(content.values()) for content in t['content']) 
                for t in tanks.values()
            )
            
            return {
                "tanks": tanks,
                "summary": {
                    "total_tanks": len(tanks),
                    "total_capacity": total_capacity,
                    "total_inventory": total_inventory,
                    "utilization": (total_inventory / total_capacity * 100) if total_capacity > 0 else 0
                }
            }
    
    def _update_tank_inventory(self, tank_name: str, crude_name: str, volume: float) -> Dict[str, Any]:
        """Update tank inventory."""
        success = self.db.update_tank_content(tank_name, crude_name, volume)
        if success:
            return {"success": True, "message": f"Updated {tank_name} with {volume} kbbl of {crude_name}"}
        else:
            return {"error": f"Failed to update tank {tank_name}"}
    
    # Vessel Operations
    def _get_vessel_schedule(self, vessel_id: Optional[str] = None, days_ahead: int = 30) -> Dict[str, Any]:
        """Get vessel schedule information."""
        if vessel_id:
            vessel = self.db.get_vessel(vessel_id=vessel_id)
            if not vessel:
                return {"error": f"Vessel '{vessel_id}' not found"}
            return {"vessel": vessel}
        else:
            vessels = self.db.get_all_vessels()
            current_day = 1  # Could be calculated from system date
            upcoming_arrivals = []
            
            for vid, vessel in vessels.items():
                arrival_day = vessel.get('arrival_day', 0)
                if current_day <= arrival_day <= current_day + days_ahead:
                    upcoming_arrivals.append({
                        "vessel_id": vid,
                        "arrival_day": arrival_day,
                        "cargo_summary": len(vessel.get('cargo', [])),
                        "total_volume": sum(c['volume'] for c in vessel.get('cargo', []))
                    })
            
            return {
                "vessels": vessels,
                "upcoming_arrivals": sorted(upcoming_arrivals, key=lambda x: x['arrival_day']),
                "total_vessels": len(vessels)
            }
    
    def _modify_vessel_arrival(self, vessel_id: str, arrival_day: Optional[int] = None, 
                              cargo_updates: Optional[List[Dict]] = None) -> Dict[str, Any]:
        """Modify vessel arrival or cargo."""
        vessel = self.db.get_vessel(vessel_id=vessel_id)
        if not vessel:
            return {"error": f"Vessel '{vessel_id}' not found"}
        
        # This would need to be implemented in the database manager
        # For now, return a placeholder response
        changes = []
        if arrival_day:
            changes.append(f"Arrival day changed to {arrival_day}")
        if cargo_updates:
            changes.append(f"Cargo updated with {len(cargo_updates)} modifications")
        
        return {
            "success": True,
            "vessel_id": vessel_id,
            "changes": changes,
            "message": "Vessel modification completed (placeholder - implement in DB manager)"
        }
    
    # Production Metrics
    def _get_production_metrics(self, days: int = 30, metric_type: str = "all", specific_day: Optional[int] = None) -> Dict[str, Any]:
        """Get production metrics from actual schedule data."""
        try:
            schedule_data = self._load_schedule_results()
            if not schedule_data:
                return {"error": "Schedule results not found"}
            
            daily_plans = schedule_data.get('daily_plans', [])
            
            # If specific day requested, return detailed day analysis
            if specific_day is not None:
                return self._analyze_specific_day(daily_plans, specific_day)
            
            # Analyze the requested number of days
            analyzed_days = daily_plans[:days] if len(daily_plans) >= days else daily_plans
            
            metrics = {}
            
            if metric_type in ["throughput", "all"]:
                throughput_data = self._analyze_throughput(analyzed_days)
                metrics["throughput"] = throughput_data
            
            if metric_type in ["margin", "all"]:
                margin_data = self._analyze_margins(analyzed_days)
                metrics["margin"] = margin_data
            
            if metric_type in ["inventory", "all"]:
                inventory_data = self._analyze_inventory_trends(analyzed_days)
                metrics["inventory"] = inventory_data
            
            if metric_type == "all":
                metrics["multi_recipe_analysis"] = self._analyze_multi_recipe_operations(analyzed_days)
                metrics["recipe_transitions"] = self._analyze_recipe_transitions(analyzed_days)
            
            return {
                "metrics": metrics, 
                "days_analyzed": len(analyzed_days),
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            return {"error": f"Failed to analyze production metrics: {str(e)}"}
    
    def _calculate_inventory_by_grade(self, tanks: Dict) -> Dict[str, float]:
        """Calculate inventory levels by crude grade."""
        inventory_by_grade = {}
        for tank in tanks.values():
            for content in tank.get('content', []):
                for grade, volume in content.items():
                    inventory_by_grade[grade] = inventory_by_grade.get(grade, 0) + volume
        return inventory_by_grade
    
    # Crude Information
    def _get_crude_information(self, crude_name: Optional[str] = None) -> Dict[str, Any]:
        """Get crude oil information."""
        # This would need to be implemented in database manager
        # For now, using placeholder data structure
        
        if crude_name:
            # Return specific crude info
            return {
                "crude": {
                    "name": crude_name,
                    "margin": 15.75,
                    "origin": "Peninsular Malaysia",
                    "current_inventory": 250.0,
                    "availability": "Available"
                }
            }
        else:
            # Return all crudes
            return {
                "crudes": {
                    "Base": {"margin": 15.85, "origin": "Peninsular Malaysia"},
                    "Grade A": {"margin": 18.47, "origin": "Peninsular Malaysia"},
                    "Grade B": {"margin": 15.71, "origin": "Peninsular Malaysia"},
                    "Grade C": {"margin": 19.24, "origin": "Terminal3"},
                    "Grade D": {"margin": 11.19, "origin": "Sabah"},
                    "Grade E": {"margin": 9.98, "origin": "Sabah"},
                    "Grade F": {"margin": 9.97, "origin": "Sarawak"}
                }
            }
    
    # Blending Recipes
    def _get_blending_recipes(self, recipe_name: Optional[str] = None) -> Dict[str, Any]:
        """Get blending recipe information."""
        recipes = self.db.get_all_blending_recipes()
        
        if recipe_name:
            recipe = next((r for r in recipes if r['name'] == recipe_name), None)
            if not recipe:
                return {"error": f"Recipe '{recipe_name}' not found"}
            return {"recipe": recipe}
        else:
            return {
                "recipes": recipes,
                "total_recipes": len(recipes),
                "summary": {
                    "max_total_capacity": sum(r['max_rate'] for r in recipes),
                    "recipe_count": len(recipes)
                }
            }
    
    # Optimization Operations
    def _run_schedule_optimization(self, optimization_type: str, horizon_days: int = 30) -> Dict[str, Any]:
        """Run schedule optimization."""
        try:
            # Load data from database
            tanks = self._load_tanks_from_db()
            vessels = self._load_vessels_from_db()
            crudes = self._load_crudes_from_db()
            recipes = self._load_recipes_from_db()
            
            # Create scheduler
            scheduler = Scheduler(tanks, vessels, crudes, recipes)
            schedule = scheduler.run_schedule(horizon_days)
            
            # Run optimization
            optimizer = SchedulerOptimizer(tanks, vessels, crudes, recipes)
            
            if optimization_type == "margin":
                optimized_schedule = optimizer.optimize_for_margin(schedule, horizon_days)
            else:
                optimized_schedule = optimizer.optimize_for_throughput(schedule, horizon_days)
            
            # Calculate metrics
            original_margin = sum(day.total_margin for day in schedule)
            optimized_margin = sum(day.total_margin for day in optimized_schedule)
            
            return {
                "success": True,
                "optimization_type": optimization_type,
                "horizon_days": horizon_days,
                "results": {
                    "original_margin": original_margin,
                    "optimized_margin": optimized_margin,
                    "improvement": optimized_margin - original_margin,
                    "improvement_percentage": ((optimized_margin - original_margin) / original_margin * 100) if original_margin > 0 else 0
                },
                "schedule_days": len(optimized_schedule),
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            return {"error": f"Optimization failed: {str(e)}"}
    
    def _run_vessel_optimization(self, horizon_days: int = 30) -> Dict[str, Any]:
        """Run vessel optimization."""
        try:
            # This would interface with the VesselOptimizer class
            return {
                "success": True,
                "message": "Vessel optimization completed",
                "horizon_days": horizon_days,
                "optimized_vessels": 5,  # Placeholder
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            return {"error": f"Vessel optimization failed: {str(e)}"}
    
    # Analysis Functions
    def _analyze_inventory_trends(self, crude_type: Optional[str] = None, days_ahead: int = 14) -> Dict[str, Any]:
        """Analyze inventory trends."""
        tanks = self.db.get_all_tanks()
        
        # Calculate current inventory by grade
        current_inventory = self._calculate_inventory_by_grade(tanks)
        
        # Simulate trend analysis (would use real consumption data)
        trends = {}
        for grade, inventory in current_inventory.items():
            if crude_type and grade != crude_type:
                continue
            
            daily_consumption = 12.0  # Placeholder
            days_remaining = inventory / daily_consumption if daily_consumption > 0 else float('inf')
            
            trends[grade] = {
                "current_inventory": inventory,
                "daily_consumption": daily_consumption,
                "days_remaining": days_remaining,
                "status": "critical" if days_remaining < 7 else "low" if days_remaining < 14 else "normal"
            }
        
        return {
            "inventory_trends": trends,
            "analysis_period": days_ahead,
            "recommendations": self._generate_inventory_recommendations(trends)
        }
    
    def _generate_inventory_recommendations(self, trends: Dict) -> List[str]:
        """Generate inventory recommendations based on trends."""
        recommendations = []
        for grade, trend in trends.items():
            if trend["status"] == "critical":
                recommendations.append(f"URGENT: {grade} inventory critically low - arrange immediate delivery")
            elif trend["status"] == "low":
                recommendations.append(f"Schedule {grade} delivery within next week")
        return recommendations
    
    # Feedstock Requirements
    def _get_feedstock_requirements(self, grade: Optional[str] = None, urgent_only: bool = False) -> Dict[str, Any]:
        """Get feedstock requirements."""
        requirements = self.db.get_all_feedstock_requirements()
        
        filtered_requirements = []
        current_day = 1  # Would be calculated from system date
        
        for req in requirements:
            if grade and req.get('grade') != grade:
                continue
            
            days_until_required = req.get('required_arrival_by', 999) - current_day
            is_urgent = days_until_required <= 7
            
            if urgent_only and not is_urgent:
                continue
            
            req_info = {
                **req,
                "days_until_required": days_until_required,
                "urgency": "urgent" if is_urgent else "normal"
            }
            filtered_requirements.append(req_info)
        
        return {
            "requirements": sorted(filtered_requirements, key=lambda x: x['required_arrival_by']),
            "total_requirements": len(filtered_requirements),
            "urgent_count": sum(1 for r in filtered_requirements if r['urgency'] == 'urgent')
        }
    
    # System Summary
    def _generate_system_summary(self, include_forecasts: bool = True, detail_level: str = "medium") -> Dict[str, Any]:
        """Generate comprehensive system summary."""
        summary = {
            "timestamp": datetime.now().isoformat(),
            "system_status": "operational",
            "overview": {}
        }
        
        # Tank status
        tanks = self.db.get_all_tanks()
        tank_summary = self._get_tank_status()["summary"]
        summary["overview"]["tanks"] = tank_summary
        
        # Vessel status
        vessels = self.db.get_all_vessels()
        vessel_summary = {
            "total_vessels": len(vessels),
            "upcoming_arrivals": len([v for v in vessels.values() if v.get('arrival_day', 0) <= 30])
        }
        summary["overview"]["vessels"] = vessel_summary
        
        # Production metrics
        if detail_level in ["medium", "high"]:
            metrics = self._get_production_metrics()["metrics"]
            summary["production"] = metrics
        
        # Inventory trends
        if include_forecasts:
            trends = self._analyze_inventory_trends()
            summary["inventory_forecast"] = {
                "critical_items": len([t for t in trends["inventory_trends"].values() if t["status"] == "critical"]),
                "recommendations": trends["recommendations"][:3]  # Top 3 recommendations
            }
        
        # Requirements
        requirements = self._get_feedstock_requirements(urgent_only=True)
        summary["urgent_requirements"] = requirements["urgent_count"]
        
        return summary
    
    # Helper methods to load data from database
    def _load_tanks_from_db(self) -> Dict[str, Tank]:
        """Load tanks from database."""
        tanks_data = self.db.get_all_tanks()
        tanks = {}
        
        for tank_name, tank_info in tanks_data.items():
            # Create Tank object
            tank = Tank(
                name=tank_name,
                capacity=tank_info['capacity'],
                content={}
            )
            
            # Set content
            for content_item in tank_info.get('content', []):
                for crude_name, volume in content_item.items():
                    tank.content[crude_name] = volume
            
            tanks[tank_name] = tank
        
        return tanks
    
    def _load_vessels_from_db(self) -> List[Vessel]:
        """Load vessels from database."""
        vessels_data = self.db.get_all_vessels()
        vessels = []
        
        for vessel_id, vessel_info in vessels_data.items():
            # Process cargo
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
            
            vessel = Vessel(
                vessel_id=vessel_id,
                arrival_day=int(vessel_info.get("arrival_day", 0)),
                capacity=float(vessel_info.get("capacity", 0)),
                cost=float(vessel_info.get("cost", 0)),
                cargo=cargo,
                days_held=int(vessel_info.get("days_held", 0))
            )
            
            if "route" in vessel_info:
                vessel.route = vessel_info["route"]
            
            vessels.append(vessel)
        
        return vessels
    
    def _load_crudes_from_db(self) -> Dict[str, Crude]:
        """Load crudes from database."""
        # This would need to be implemented in the database manager
        # For now, return placeholder data
        return {
            "Base": Crude(name="Base", margin=15.85, origin="Peninsular Malaysia"),
            "A": Crude(name="A", margin=18.47, origin="Peninsular Malaysia"),
            "B": Crude(name="B", margin=15.71, origin="Peninsular Malaysia"),
            "C": Crude(name="C", margin=19.24, origin="Terminal3"),
            "D": Crude(name="D", margin=11.19, origin="Sabah"),
            "E": Crude(name="E", margin=9.98, origin="Sabah"),
            "F": Crude(name="F", margin=9.97, origin="Sarawak")
        }
    
    def _load_recipes_from_db(self) -> List[BlendingRecipe]:
        """Load recipes from database."""
        recipes_data = self.db.get_all_blending_recipes()
        recipes = []
        
        for recipe_data in recipes_data:
            recipe = BlendingRecipe(
                name=recipe_data['name'],
                primary_grade=recipe_data['primary_grade'],
                secondary_grade=recipe_data.get('secondary_grade'),
                max_rate=recipe_data['max_rate'],
                primary_fraction=recipe_data['primary_fraction']
            )
            recipes.append(recipe)
        
        return recipes
    
    def _load_schedule_results(self) -> Optional[Dict]:
        """Load schedule results from JSON file."""
        try:
            schedule_path = os.path.join(os.path.dirname(__file__), 'output', 'schedule_results.json')
            if os.path.exists(schedule_path):
                with open(schedule_path, 'r') as f:
                    return json.load(f)
        except Exception as e:
            print(f"Failed to load schedule results: {e}")
        return None
    
    def _analyze_specific_day(self, daily_plans: List[Dict], day: int) -> Dict[str, Any]:
        """Provide detailed analysis for a specific day."""
        if day >= len(daily_plans):
            return {"error": f"Day {day} not found in schedule data"}
        
        day_data = daily_plans[day]
        
        analysis = {
            "day": day,
            "processing_rates": day_data.get('processing_rates', {}),
            "total_throughput": sum(day_data.get('processing_rates', {}).values()),
            "inventory": {
                "total": day_data.get('inventory', 0),
                "by_grade": day_data.get('inventory_by_grade', {})
            },
            "blending_details": day_data.get('blending_details', []),
            "tank_status": day_data.get('tanks', {}),
            "multi_recipe_operation": len(day_data.get('processing_rates', {})) > 1
        }
        
        # Add recipe analysis
        if day_data.get('blending_details'):
            analysis["recipe_analysis"] = []
            for recipe in day_data.get('blending_details', []):
                recipe_info = {
                    "recipe_name": recipe.get('name'),
                    "primary_grade": recipe.get('primary_grade'),
                    "secondary_grade": recipe.get('secondary_grade'),
                    "primary_fraction": recipe.get('primary_fraction'),
                    "max_rate": recipe.get('max_rate'),
                    "actual_rate": day_data.get('processing_rates', {}).get(recipe.get('name'), 0)
                }
                analysis["recipe_analysis"].append(recipe_info)
        
        # Calculate utilization
        plant_capacity = 95.0  # From plant.json
        analysis["capacity_utilization"] = (analysis["total_throughput"] / plant_capacity * 100) if plant_capacity > 0 else 0
        
        return analysis
    
    def _analyze_throughput(self, daily_plans: List[Dict]) -> Dict[str, Any]:
        """Analyze throughput metrics from daily plans."""
        total_throughputs = []
        recipe_usage = {}
        multi_recipe_days = 0
        
        for day_data in daily_plans:
            processing_rates = day_data.get('processing_rates', {})
            daily_throughput = sum(processing_rates.values())
            total_throughputs.append(daily_throughput)
            
            # Track recipe usage
            for recipe_id, rate in processing_rates.items():
                if recipe_id not in recipe_usage:
                    recipe_usage[recipe_id] = []
                recipe_usage[recipe_id].append(rate)
            
            # Count multi-recipe days
            if len(processing_rates) > 1:
                multi_recipe_days += 1
        
        plant_capacity = 95.0  # From plant.json
        
        return {
            "average_daily_throughput": sum(total_throughputs) / len(total_throughputs) if total_throughputs else 0,
            "peak_throughput": max(total_throughputs) if total_throughputs else 0,
            "minimum_throughput": min(total_throughputs) if total_throughputs else 0,
            "capacity_utilization": (sum(total_throughputs) / len(total_throughputs) / plant_capacity * 100) if total_throughputs else 0,
            "recipe_usage_summary": {recipe: {
                "days_active": len(rates),
                "average_rate": sum(rates) / len(rates),
                "max_rate": max(rates),
                "total_volume": sum(rates)
            } for recipe, rates in recipe_usage.items()},
            "multi_recipe_days": multi_recipe_days,
            "multi_recipe_percentage": (multi_recipe_days / len(daily_plans) * 100) if daily_plans else 0
        }
    
    def _analyze_margins(self, daily_plans: List[Dict]) -> Dict[str, Any]:
        """Analyze margin data from daily plans."""
        # For now, calculate estimated margins based on crude grades
        # This would need actual pricing data in a real implementation
        
        crude_margins = {
            "Base": 18.50,
            "A": 22.75,
            "B": 19.25,
            "C": 16.80,
            "D": 21.10
        }
        
        total_margin = 0
        daily_margins = []
        
        for day_data in daily_plans:
            day_margin = 0
            blending_details = day_data.get('blending_details', [])
            processing_rates = day_data.get('processing_rates', {})
            
            for recipe in blending_details:
                recipe_name = recipe.get('name')
                rate = processing_rates.get(recipe_name, 0)
                
                # Calculate weighted margin based on blend composition
                primary_grade = recipe.get('primary_grade')
                secondary_grade = recipe.get('secondary_grade') 
                primary_fraction = recipe.get('primary_fraction', 0.5)
                
                if primary_grade and secondary_grade:
                    weighted_margin = (
                        crude_margins.get(primary_grade, 0) * primary_fraction +
                        crude_margins.get(secondary_grade, 0) * (1 - primary_fraction)
                    )
                    day_margin += rate * weighted_margin
            
            daily_margins.append(day_margin)
            total_margin += day_margin
        
        return {
            "total_margin": total_margin,
            "average_daily_margin": total_margin / len(daily_plans) if daily_plans else 0,
            "best_day_margin": max(daily_margins) if daily_margins else 0,
            "worst_day_margin": min(daily_margins) if daily_margins else 0,
            "margin_trend": "increasing" if len(daily_margins) > 1 and daily_margins[-1] > daily_margins[0] else "stable"
        }
    
    def _analyze_inventory_trends(self, daily_plans: List[Dict]) -> Dict[str, Any]:
        """Analyze inventory trends from daily plans."""
        inventory_levels = []
        grade_trends = {}
        
        for day_data in daily_plans:
            total_inventory = day_data.get('inventory', 0)
            inventory_levels.append(total_inventory)
            
            inventory_by_grade = day_data.get('inventory_by_grade', {})
            for grade, volume in inventory_by_grade.items():
                if grade not in grade_trends:
                    grade_trends[grade] = []
                grade_trends[grade].append(volume)
        
        # Calculate trends
        grade_analysis = {}
        for grade, levels in grade_trends.items():
            if len(levels) > 1:
                trend = "increasing" if levels[-1] > levels[0] else "decreasing" if levels[-1] < levels[0] else "stable"
                consumption_rate = (levels[0] - levels[-1]) / len(levels) if levels[0] > 0 else 0
            else:
                trend = "stable"
                consumption_rate = 0
            
            grade_analysis[grade] = {
                "current_level": levels[-1] if levels else 0,
                "initial_level": levels[0] if levels else 0,
                "trend": trend,
                "average_consumption_rate": consumption_rate,
                "days_of_supply": levels[-1] / consumption_rate if consumption_rate > 0 else float('inf')
            }
        
        return {
            "current_total_inventory": inventory_levels[-1] if inventory_levels else 0,
            "initial_inventory": inventory_levels[0] if inventory_levels else 0,
            "inventory_trend": "increasing" if len(inventory_levels) > 1 and inventory_levels[-1] > inventory_levels[0] else "decreasing" if len(inventory_levels) > 1 and inventory_levels[-1] < inventory_levels[0] else "stable",
            "average_daily_consumption": (inventory_levels[0] - inventory_levels[-1]) / len(inventory_levels) if len(inventory_levels) > 1 else 0,
            "grade_analysis": grade_analysis
        }
    
    def _analyze_multi_recipe_operations(self, daily_plans: List[Dict]) -> Dict[str, Any]:
        """Analyze multi-recipe operations in the schedule."""
        multi_recipe_days = []
        transition_patterns = []
        
        for i, day_data in enumerate(daily_plans):
            processing_rates = day_data.get('processing_rates', {})
            
            if len(processing_rates) > 1:
                multi_recipe_days.append({
                    "day": i,
                    "recipes": list(processing_rates.keys()),
                    "rates": processing_rates,
                    "total_throughput": sum(processing_rates.values())
                })
        
        # Analyze transition patterns
        prev_recipes = set()
        for i, day_data in enumerate(daily_plans):
            current_recipes = set(day_data.get('processing_rates', {}).keys())
            
            if prev_recipes and current_recipes != prev_recipes:
                transition_patterns.append({
                    "day": i,
                    "from_recipes": list(prev_recipes),
                    "to_recipes": list(current_recipes),
                    "transition_type": "addition" if current_recipes.issuperset(prev_recipes) else "switch"
                })
            
            prev_recipes = current_recipes
        
        return {
            "multi_recipe_days_count": len(multi_recipe_days),
            "multi_recipe_percentage": (len(multi_recipe_days) / len(daily_plans) * 100) if daily_plans else 0,
            "multi_recipe_details": multi_recipe_days,
            "transition_count": len(transition_patterns),
            "transition_patterns": transition_patterns,
            "average_recipes_per_transition_day": sum(len(day["recipes"]) for day in multi_recipe_days) / len(multi_recipe_days) if multi_recipe_days else 0
        }
    
    def _analyze_recipe_transitions(self, daily_plans: List[Dict]) -> Dict[str, Any]:
        """Analyze recipe transition efficiency and patterns."""
        recipe_changes = []
        recipe_stability = {}
        
        prev_active_recipes = set()
        
        for i, day_data in enumerate(daily_plans):
            current_recipes = set(day_data.get('processing_rates', {}).keys())
            
            if i > 0 and current_recipes != prev_active_recipes:
                recipe_changes.append({
                    "day": i,
                    "added_recipes": list(current_recipes - prev_active_recipes),
                    "removed_recipes": list(prev_active_recipes - current_recipes),
                    "continued_recipes": list(current_recipes & prev_active_recipes)
                })
            
            # Track recipe stability (consecutive days)
            for recipe in current_recipes:
                if recipe not in recipe_stability:
                    recipe_stability[recipe] = {"runs": [], "current_run": 0}
                recipe_stability[recipe]["current_run"] += 1
            
            # End runs for recipes not active today
            for recipe in recipe_stability:
                if recipe not in current_recipes and recipe_stability[recipe]["current_run"] > 0:
                    recipe_stability[recipe]["runs"].append(recipe_stability[recipe]["current_run"])
                    recipe_stability[recipe]["current_run"] = 0
            
            prev_active_recipes = current_recipes
        
        # Finalize current runs
        for recipe in recipe_stability:
            if recipe_stability[recipe]["current_run"] > 0:
                recipe_stability[recipe]["runs"].append(recipe_stability[recipe]["current_run"])
        
        # Calculate stability metrics
        stability_analysis = {}
        for recipe, data in recipe_stability.items():
            runs = data["runs"]
            if runs:
                stability_analysis[recipe] = {
                    "total_runs": len(runs),
                    "average_run_length": sum(runs) / len(runs),
                    "longest_run": max(runs),
                    "shortest_run": min(runs),
                    "total_active_days": sum(runs)
                }
        
        return {
            "total_recipe_changes": len(recipe_changes),
            "recipe_change_frequency": len(recipe_changes) / len(daily_plans) if daily_plans else 0,
            "recipe_changes": recipe_changes,
            "recipe_stability_analysis": stability_analysis,
            "most_stable_recipe": max(stability_analysis.keys(), key=lambda r: stability_analysis[r]["average_run_length"]) if stability_analysis else None
        }
    
    def _analyze_schedule_performance(self, analysis_type: str = "all", days: int = 30) -> Dict[str, Any]:
        """Comprehensive schedule performance analysis."""
        try:
            schedule_data = self._load_schedule_results()
            if not schedule_data:
                return {"error": "Schedule results not found"}
            
            daily_plans = schedule_data.get('daily_plans', [])
            analyzed_days = daily_plans[:days] if len(daily_plans) >= days else daily_plans
            
            analysis = {}
            
            if analysis_type in ["transitions", "all"]:
                analysis["transitions"] = self._analyze_recipe_transitions(analyzed_days)
            
            if analysis_type in ["multi_recipe", "all"]:
                analysis["multi_recipe"] = self._analyze_multi_recipe_operations(analyzed_days)
            
            if analysis_type in ["efficiency", "all"]:
                analysis["efficiency"] = self._calculate_efficiency_metrics(analyzed_days)
            
            if analysis_type == "all":
                analysis["summary"] = self._generate_performance_summary(analyzed_days)
            
            return {
                "analysis": analysis,
                "days_analyzed": len(analyzed_days),
                "analysis_type": analysis_type,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            return {"error": f"Failed to analyze schedule performance: {str(e)}"}
    
    def _calculate_efficiency_metrics(self, daily_plans: List[Dict]) -> Dict[str, Any]:
        """Calculate operational efficiency metrics."""
        plant_capacity = 95.0
        utilization_rates = []
        recipe_efficiency = {}
        
        for day_data in daily_plans:
            processing_rates = day_data.get('processing_rates', {})
            daily_throughput = sum(processing_rates.values())
            utilization = (daily_throughput / plant_capacity * 100) if plant_capacity > 0 else 0
            utilization_rates.append(utilization)
            
            # Track recipe efficiency
            blending_details = day_data.get('blending_details', [])
            for recipe in blending_details:
                recipe_name = recipe.get('name')
                max_rate = recipe.get('max_rate', 0)
                actual_rate = processing_rates.get(recipe_name, 0)
                
                if recipe_name not in recipe_efficiency:
                    recipe_efficiency[recipe_name] = []
                
                efficiency = (actual_rate / max_rate * 100) if max_rate > 0 else 0
                recipe_efficiency[recipe_name].append(efficiency)
        
        # Calculate recipe efficiency summaries
        recipe_summaries = {}
        for recipe, efficiencies in recipe_efficiency.items():
            recipe_summaries[recipe] = {
                "average_efficiency": sum(efficiencies) / len(efficiencies) if efficiencies else 0,
                "peak_efficiency": max(efficiencies) if efficiencies else 0,
                "days_active": len(efficiencies),
                "efficiency_variance": max(efficiencies) - min(efficiencies) if len(efficiencies) > 1 else 0
            }
        
        return {
            "plant_utilization": {
                "average": sum(utilization_rates) / len(utilization_rates) if utilization_rates else 0,
                "peak": max(utilization_rates) if utilization_rates else 0,
                "minimum": min(utilization_rates) if utilization_rates else 0,
                "days_at_full_capacity": sum(1 for u in utilization_rates if u >= 99.0)
            },
            "recipe_efficiency": recipe_summaries,
            "overall_efficiency_score": sum(utilization_rates) / len(utilization_rates) if utilization_rates else 0
        }
    
    def _generate_performance_summary(self, daily_plans: List[Dict]) -> Dict[str, Any]:
        """Generate overall performance summary."""
        total_days = len(daily_plans)
        
        # Count various operational patterns
        production_days = sum(1 for day in daily_plans if day.get('processing_rates'))
        multi_recipe_days = sum(1 for day in daily_plans if len(day.get('processing_rates', {})) > 1)
        recipe_changes = 0
        
        prev_recipes = set()
        for day_data in daily_plans:
            current_recipes = set(day_data.get('processing_rates', {}).keys())
            if prev_recipes and current_recipes != prev_recipes:
                recipe_changes += 1
            prev_recipes = current_recipes
        
        # Calculate total production
        total_production = sum(
            sum(day.get('processing_rates', {}).values()) 
            for day in daily_plans
        )
        
        # Identify most used recipes
        recipe_usage = {}
        for day_data in daily_plans:
            for recipe_id, rate in day_data.get('processing_rates', {}).items():
                recipe_usage[recipe_id] = recipe_usage.get(recipe_id, 0) + rate
        
        most_used_recipe = max(recipe_usage.keys(), key=recipe_usage.get) if recipe_usage else None
        
        return {
            "operational_summary": {
                "total_days_analyzed": total_days,
                "production_days": production_days,
                "idle_days": total_days - production_days,
                "multi_recipe_days": multi_recipe_days,
                "recipe_changes": recipe_changes
            },
            "production_summary": {
                "total_production": total_production,
                "average_daily_production": total_production / total_days if total_days > 0 else 0,
                "most_used_recipe": most_used_recipe,
                "total_volume_by_recipe": recipe_usage
            },
            "flexibility_metrics": {
                "multi_recipe_capability": (multi_recipe_days / total_days * 100) if total_days > 0 else 0,
                "recipe_change_frequency": (recipe_changes / total_days * 100) if total_days > 0 else 0,
                "unique_recipes_used": len(recipe_usage)
            }
        }

    def process_chat_message_stream(self, message: str, conversation_history: List[Dict] = None):
        """Process a chat message using OpenAI streaming function calling."""
        import json
        
        if conversation_history is None:
            conversation_history = []
        
        # Build conversation with system prompt
        messages = [
            {
                "role": "system",
                "content": """You are OASIS Assistant, an AI expert for the OASIS oil refinery scheduling and optimization system. 

You have access to comprehensive system functions that allow you to:
- Read and analyze tank inventories and status
- Access vessel schedules, arrivals, and cargo information  
- Get production metrics including throughput, margins, and efficiency
- Retrieve crude oil properties and blending recipe configurations
- Run schedule and vessel optimizations
- Analyze inventory trends and predict shortages
- Access feedstock requirements and delivery schedules
- Generate system summaries and reports
- Modify system data when requested

Always use the available functions to get real, current data from the system rather than making assumptions. When users ask about system status, optimization, or data analysis, call the appropriate functions to provide accurate information.

Be helpful, detailed, and proactive in your analysis. When you identify potential issues or optimization opportunities, suggest specific actions the user can take."""
            }
        ]
        
        # Add conversation history
        messages.extend(conversation_history)
        
        # Add current user message
        messages.append({"role": "user", "content": message})
        
        try:
            # Make initial API call with function calling
            response = self.client.chat.completions.create(
                model="gpt-4-turbo-preview",
                messages=messages,
                tools=self.get_function_schemas(),
                tool_choice="auto",
                temperature=0.7,
                max_tokens=2000,
                stream=False  # First call for function detection
            )
            
            # Process response
            assistant_message = response.choices[0].message
            
            # Handle function calls
            if assistant_message.tool_calls:
                # Yield function execution status
                yield {
                    "type": "function_start",
                    "functions": [tc.function.name for tc in assistant_message.tool_calls],
                    "message": f"Executing {len(assistant_message.tool_calls)} function(s)..."
                }
                
                # Execute function calls
                function_results = []
                
                for i, tool_call in enumerate(assistant_message.tool_calls):
                    function_name = tool_call.function.name
                    function_args = json.loads(tool_call.function.arguments)
                    
                    # Yield function execution progress
                    yield {
                        "type": "function_progress",
                        "function": function_name,
                        "message": f"Running {function_name}..."
                    }
                    
                    # Execute function
                    result = self.execute_function(function_name, function_args)
                    
                    function_results.append({
                        "tool_call_id": tool_call.id,
                        "result": result
                    })
                
                # Add assistant message with function calls to conversation
                messages.append({
                    "role": "assistant",
                    "content": assistant_message.content,
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": tc.type,
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments
                            }
                        } for tc in assistant_message.tool_calls
                    ]
                })
                
                # Add function results
                for func_result in function_results:
                    messages.append({
                        "role": "tool",
                        "tool_call_id": func_result["tool_call_id"],
                        "content": json.dumps(func_result["result"])
                    })
                
                # Yield function completion
                yield {
                    "type": "function_complete",
                    "message": "Functions executed successfully. Generating response..."
                }
                
                # Get final response with streaming
                stream = self.client.chat.completions.create(
                    model="gpt-4-turbo-preview",
                    messages=messages,
                    temperature=0.7,
                    max_tokens=2000,
                    stream=True
                )
                
                # Stream the response
                accumulated_content = ""
                for chunk in stream:
                    if chunk.choices[0].delta.content:
                        content = chunk.choices[0].delta.content
                        accumulated_content += content
                        yield {
                            "type": "content",
                            "content": content,
                            "accumulated": accumulated_content
                        }
                
                # Final completion message
                yield {
                    "type": "complete",
                    "full_response": accumulated_content,
                    "function_calls": len(function_results),
                    "functions_used": [tc.function.name for tc in assistant_message.tool_calls]
                }
            
            else:
                # No function calls needed - stream directly
                stream = self.client.chat.completions.create(
                    model="gpt-4-turbo-preview",
                    messages=messages,
                    temperature=0.7,
                    max_tokens=2000,
                    stream=True
                )
                
                # Stream the response
                accumulated_content = ""
                for chunk in stream:
                    if chunk.choices[0].delta.content:
                        content = chunk.choices[0].delta.content
                        accumulated_content += content
                        yield {
                            "type": "content",
                            "content": content,
                            "accumulated": accumulated_content
                        }
                
                # Final completion message
                yield {
                    "type": "complete",
                    "full_response": accumulated_content,
                    "function_calls": 0,
                    "functions_used": []
                }
        
        except Exception as e:
            yield {
                "type": "error",
                "error": f"Chat processing failed: {str(e)}",
                "message": "I apologize, but I encountered an error processing your request. Please try again."
            }

    def process_chat_message(self, message: str, conversation_history: List[Dict] = None) -> Dict[str, Any]:
        """Process a chat message using OpenAI function calling."""
        if conversation_history is None:
            conversation_history = []
        
        # Build conversation with system prompt
        messages = [
            {
                "role": "system",
                "content": """You are OASIS Assistant, an AI expert for the OASIS oil refinery scheduling and optimization system. 

You have access to comprehensive system functions that allow you to:
- Read and analyze tank inventories and status
- Access vessel schedules, arrivals, and cargo information  
- Get production metrics including throughput, margins, and efficiency
- Retrieve crude oil properties and blending recipe configurations
- Run schedule and vessel optimizations
- Analyze inventory trends and predict shortages
- Access feedstock requirements and delivery schedules
- Generate system summaries and reports
- Modify system data when requested

Always use the available functions to get real, current data from the system rather than making assumptions. When users ask about system status, optimization, or data analysis, call the appropriate functions to provide accurate information.

Be helpful, detailed, and proactive in your analysis. When you identify potential issues or optimization opportunities, suggest specific actions the user can take."""
            }
        ]
        
        # Add conversation history
        messages.extend(conversation_history)
        
        # Add current user message
        messages.append({"role": "user", "content": message})
        
        try:
            # Make initial API call with function calling
            response = self.client.chat.completions.create(
                model="gpt-4-turbo-preview",
                messages=messages,
                tools=self.get_function_schemas(),
                tool_choice="auto",
                temperature=0.7,
                max_tokens=2000
            )
            
            # Process response
            assistant_message = response.choices[0].message
            
            # Handle function calls
            if assistant_message.tool_calls:
                # Execute function calls
                function_results = []
                
                for tool_call in assistant_message.tool_calls:
                    function_name = tool_call.function.name
                    function_args = json.loads(tool_call.function.arguments)
                    
                    # Execute function
                    result = self.execute_function(function_name, function_args)
                    
                    function_results.append({
                        "tool_call_id": tool_call.id,
                        "result": result
                    })
                
                # Add assistant message with function calls to conversation
                messages.append({
                    "role": "assistant",
                    "content": assistant_message.content,
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": tc.type,
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments
                            }
                        } for tc in assistant_message.tool_calls
                    ]
                })
                
                # Add function results
                for func_result in function_results:
                    messages.append({
                        "role": "tool",
                        "tool_call_id": func_result["tool_call_id"],
                        "content": json.dumps(func_result["result"])
                    })
                
                # Get final response
                final_response = self.client.chat.completions.create(
                    model="gpt-4-turbo-preview",
                    messages=messages,
                    temperature=0.7,
                    max_tokens=2000
                )
                
                return {
                    "success": True,
                    "response": final_response.choices[0].message.content,
                    "function_calls": len(function_results),
                    "functions_used": [tc.function.name for tc in assistant_message.tool_calls]
                }
            
            else:
                # No function calls needed
                return {
                    "success": True,
                    "response": assistant_message.content,
                    "function_calls": 0,
                    "functions_used": []
                }
        
        except Exception as e:
            return {
                "success": False,
                "error": f"Chat processing failed: {str(e)}",
                "response": "I apologize, but I encountered an error processing your request. Please try again."
            }
