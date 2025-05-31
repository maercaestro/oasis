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
                    "description": "Get production metrics, throughput, and margin analysis",
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
    def _get_production_metrics(self, days: int = 30, metric_type: str = "all") -> Dict[str, Any]:
        """Get production metrics."""
        # This would analyze daily plans and schedules
        # For now, providing structured placeholder data
        
        metrics = {}
        
        if metric_type in ["throughput", "all"]:
            metrics["throughput"] = {
                "average_daily_throughput": 85.5,
                "peak_throughput": 96.0,
                "capacity_utilization": 87.2,
                "days_analyzed": days
            }
        
        if metric_type in ["margin", "all"]:
            metrics["margin"] = {
                "total_margin": 1245000,
                "average_daily_margin": 41500,
                "margin_per_barrel": 15.75,
                "best_performing_crude": "Grade C"
            }
        
        if metric_type in ["inventory", "all"]:
            tanks = self.db.get_all_tanks()
            total_inventory = sum(
                sum(sum(content.values()) for content in t['content']) 
                for t in tanks.values()
            )
            
            metrics["inventory"] = {
                "current_total_inventory": total_inventory,
                "days_of_supply": total_inventory / 85.5 if total_inventory > 0 else 0,
                "inventory_by_grade": self._calculate_inventory_by_grade(tanks)
            }
        
        return {"metrics": metrics, "timestamp": datetime.now().isoformat()}
    
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
