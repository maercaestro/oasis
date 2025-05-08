"""
OASIS Base Scheduler / utils.py
This module contains utility functions for the OASIS system.
Copyright (c) by Abu Huzaifah Bidin with help from Github Copilot
"""

import logging
import os
import json
import pandas as pd
from typing import Dict, List, Any, Optional
from datetime import datetime
from pathlib import Path
from .models import Tank, DailyPlan, Vessel, BlendingRecipe, Crude

# Configure logging
def setup_logging(log_file: str = None, level: str = "INFO") -> logging.Logger:
    """
    Set up logging for the OASIS system.
    
    Args:
        log_file: Path to the log file (default: logs/oasis_{timestamp}.log)
        level: Logging level (default: INFO)
        
    Returns:
        Logger object
    """
    # Create logs directory if it doesn't exist
    log_dir = os.path.join(os.path.dirname(__file__), "../logs")
    os.makedirs(log_dir, exist_ok=True)
    
    # Create default log filename with timestamp if none provided
    if not log_file:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = os.path.join(log_dir, f"oasis_{timestamp}.log")
    
    # Set up logger
    level_map = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL
    }
    
    logging.basicConfig(
        filename=log_file,
        level=level_map.get(level.upper(), logging.INFO),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Add console handler
    console = logging.StreamHandler()
    console.setLevel(level_map.get(level.upper(), logging.INFO))
    formatter = logging.Formatter('%(name)s - %(levelname)s - %(message)s')
    console.setFormatter(formatter)
    
    logger = logging.getLogger("OASIS")
    logger.addHandler(console)
    
    return logger

# DataFrame conversion functions
def daily_plans_to_df(daily_plans: Dict[int, DailyPlan]) -> pd.DataFrame:
    """
    Convert daily plans to a pandas DataFrame.
    
    Args:
        daily_plans: Dictionary of daily plans indexed by day
        
    Returns:
        DataFrame containing daily plan information
    """
    data = []
    
    for day, plan in daily_plans.items():
        # Basic day info
        day_data = {
            "day": day,
            "total_inventory": plan.inventory
        }
        
        # Add inventory by grade
        for grade, volume in plan.inventory_by_grade.items():
            day_data[f"inventory_{grade}"] = volume
        
        # Add processing rates
        for recipe, rate in plan.processing_rates.items():
            day_data[f"rate_{recipe}"] = rate
        
        data.append(day_data)
    
    return pd.DataFrame(data)

def tanks_to_df(tanks: Dict[str, Tank]) -> pd.DataFrame:
    """
    Convert tank data to a pandas DataFrame.
    
    Args:
        tanks: Dictionary of tanks
        
    Returns:
        DataFrame containing tank information
    """
    data = []
    
    for tank_name, tank in tanks.items():
        # Get total volume in tank
        total_volume = sum(sum(content.values()) for content in tank.content)
        
        # Get volume by grade
        grade_volumes = {}
        for content in tank.content:
            for grade, volume in content.items():
                grade_volumes[grade] = grade_volumes.get(grade, 0) + volume
        
        # Build row
        tank_data = {
            "name": tank_name,
            "capacity": tank.capacity,
            "total_volume": total_volume,
            "utilization": total_volume / tank.capacity if tank.capacity > 0 else 0
        }
        
        # Add grade volumes
        for grade, volume in grade_volumes.items():
            tank_data[f"volume_{grade}"] = volume
            
        data.append(tank_data)
    
    return pd.DataFrame(data)

def vessels_to_df(vessels: List[Vessel]) -> pd.DataFrame:
    """
    Convert vessel data to a pandas DataFrame.
    
    Args:
        vessels: List of vessels
        
    Returns:
        DataFrame containing vessel information
    """
    data = []
    
    for i, vessel in enumerate(vessels):
        # Basic vessel info
        vessel_id = f"vessel_{i+1}"
        
        vessel_data = {
            "vessel_id": vessel_id,
            "arrival_day": vessel.arrival_day,
            "original_arrival_day": vessel.original_arrival_day or vessel.arrival_day,
            "days_held": vessel.days_held,
            "total_cargo": sum(parcel.volume for parcel in vessel.cargo)
        }
        
        # Add cargo details
        cargo_by_grade = {}
        for parcel in vessel.cargo:
            cargo_by_grade[parcel.grade] = cargo_by_grade.get(parcel.grade, 0) + parcel.volume
        
        for grade, volume in cargo_by_grade.items():
            vessel_data[f"cargo_{grade}"] = volume
            
        data.append(vessel_data)
    
    return pd.DataFrame(data)

# Reporting functions
def generate_summary_report(daily_plans: Dict[int, DailyPlan], output_file: str = None) -> str:
    """
    Generate a summary report of the scheduling results.
    
    Args:
        daily_plans: Dictionary of daily plans indexed by day
        output_file: Optional file to write the report to
        
    Returns:
        Report text
    """
    report = []
    report.append("=== OASIS SCHEDULER SUMMARY REPORT ===")
    report.append(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append(f"Schedule duration: {len(daily_plans)} days")
    report.append("")
    
    # Overall statistics
    total_processed = 0
    grades_processed = {}
    
    for day, plan in daily_plans.items():
        for recipe_name, rate in plan.processing_rates.items():
            total_processed += rate
            
    report.append(f"Total volume processed: {total_processed:.2f} kb")
    report.append(f"Average daily throughput: {total_processed/len(daily_plans):.2f} kb/day")
    report.append("")
    
    # Daily summary
    report.append("=== DAILY SUMMARY ===")
    for day, plan in sorted(daily_plans.items()):
        report.append(f"Day {day}:")
        report.append(f"  Total inventory: {plan.inventory:.2f} kb")
        
        # Inventory by grade
        report.append("  Inventory by grade:")
        for grade, volume in plan.inventory_by_grade.items():
            report.append(f"    {grade}: {volume:.2f} kb")
        
        # Processing rates
        daily_total = sum(plan.processing_rates.values())
        report.append(f"  Total processing: {daily_total:.2f} kb/day")
        report.append("  Processing rates:")
        for recipe_name, rate in plan.processing_rates.items():
            report.append(f"    {recipe_name}: {rate:.2f} kb/day")
        report.append("")
    
    report_text = "\n".join(report)
    
    # Write to file if specified
    if output_file:
        with open(output_file, "w") as f:
            f.write(report_text)
    
    return report_text

def export_schedule_to_excel(daily_plans: Dict[int, DailyPlan], filename: str) -> None:
    """
    Export scheduling results to an Excel file.
    
    Args:
        daily_plans: Dictionary of daily plans indexed by day
        filename: Path to the Excel file
    """
    # Create a writer to save multiple sheets
    writer = pd.ExcelWriter(filename, engine='xlsxwriter')
    
    # Convert daily plans to DataFrame and save
    daily_df = daily_plans_to_df(daily_plans)
    daily_df.to_excel(writer, sheet_name='Daily Plans', index=False)
    
    # Extract and save tank data from the last day
    if daily_plans:
        last_day = max(daily_plans.keys())
        last_tanks = daily_plans[last_day].tanks
        tanks_df = tanks_to_df(last_tanks)
        tanks_df.to_excel(writer, sheet_name='Final Tank Status', index=False)
    
    writer.save()

# Validation functions
def validate_data_consistency(tanks: Dict[str, Tank], 
                             recipes: List[BlendingRecipe], 
                             vessels: List[Vessel],
                             crude_data: Dict[str, Crude]) -> Dict[str, List[str]]:
    """
    Validate data consistency across different components.
    
    Args:
        tanks: Dictionary of tanks
        recipes: List of blending recipes
        vessels: List of vessels
        crude_data: Dictionary of crude data
        
    Returns:
        Dictionary of issues by category
    """
    issues = {
        "tanks": [],
        "recipes": [],
        "vessels": [],
        "crude_data": []
    }
    
    # Check that all grades in recipes exist in crude_data
    all_recipe_grades = set()
    for recipe in recipes:
        all_recipe_grades.add(recipe.primary_grade)
        if recipe.secondary_grade:
            all_recipe_grades.add(recipe.secondary_grade)
    
    for grade in all_recipe_grades:
        if grade not in crude_data:
            issues["recipes"].append(f"Recipe uses grade '{grade}' which is not in crude data")
    
    # Check vessel cargo grades
    all_cargo_grades = set()
    for vessel in vessels:
        for parcel in vessel.cargo:
            all_cargo_grades.add(parcel.grade)
    
    for grade in all_cargo_grades:
        if grade not in crude_data:
            issues["vessels"].append(f"Vessel cargo contains grade '{grade}' which is not in crude data")
    
    # Check tank content grades
    for tank_name, tank in tanks.items():
        for content in tank.content:
            for grade in content:
                if grade not in crude_data:
                    issues["tanks"].append(f"Tank '{tank_name}' contains grade '{grade}' which is not in crude data")
    
    return issues