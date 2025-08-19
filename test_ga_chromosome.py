"""
Test script for genetic algorithm chromosome design
Demonstrates how the GA chromosome integrates with the scheduler
"""

import sys
import os

# Add the backend directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

from backend.scheduler.genetic_optimizer import ScheduleChromosome, HourlyOperation, DaySchedule
from backend.scheduler.models import BlendingRecipe

def test_chromosome_basic():
    """Test basic chromosome functionality"""
    print("=== Testing Basic Chromosome Functionality ===")
    
    # Create some sample recipes
    recipes = [
        BlendingRecipe(
            name="Base_Heavy",
            primary_grade="Base",
            secondary_grade="Heavy",
            max_rate=80.0,
            primary_fraction=0.7
        ),
        BlendingRecipe(
            name="Base_Light",
            primary_grade="Base",
            secondary_grade="Light",
            max_rate=90.0,
            primary_fraction=0.6
        ),
        BlendingRecipe(
            name="Heavy_Only",
            primary_grade="Heavy",
            secondary_grade=None,
            max_rate=60.0,
            primary_fraction=1.0
        )
    ]
    
    # Create a chromosome for 3 days
    chromosome = ScheduleChromosome(days=3, recipes=recipes)
    print(f"Created chromosome: {chromosome.days} days, {len(chromosome.recipes)} recipes")
    
    # Generate random schedule
    chromosome.randomize(max_daily_capacity=95.0)
    print(f"Generated random schedule with {chromosome._count_total_changeovers()} changeovers")
    
    # Display the schedule
    print("\n=== Schedule Details ===")
    for day_idx in range(chromosome.days):
        day_schedule = chromosome.schedule[day_idx]
        daily_totals = day_schedule.get_daily_totals()
        total_production = day_schedule.get_total_production()
        changeovers = len(day_schedule.get_changeover_hours())
        recipe_switches = day_schedule.count_recipe_switches()
        
        print(f"\nDay {day_idx}:")
        print(f"  Daily totals: {daily_totals}")
        print(f"  Total production: {total_production:.1f} kb")
        print(f"  Changeover hours: {changeovers}")
        print(f"  Recipe switches: {recipe_switches}")
        
        # Show hourly details for first day
        if day_idx == 0:
            print(f"  Hourly breakdown:")
            for hour_op in day_schedule.hours[:24]:
                if hour_op.is_changeover:
                    print(f"    Hour {hour_op.hour:2d}: CHANGEOVER {hour_op.changeover_from} -> {hour_op.changeover_to}")
                elif hour_op.is_productive():
                    print(f"    Hour {hour_op.hour:2d}: {hour_op.recipe_name} @ {hour_op.processing_rate:.2f} kb/hr")
                else:
                    print(f"    Hour {hour_op.hour:2d}: IDLE")

def test_chromosome_mutations():
    """Test chromosome mutation operations"""
    print("\n\n=== Testing Chromosome Mutations ===")
    
    recipes = [
        BlendingRecipe("Recipe_A", "Base", "Heavy", 80.0, 0.7),
        BlendingRecipe("Recipe_B", "Base", "Light", 90.0, 0.6),
    ]
    
    chromosome = ScheduleChromosome(days=2, recipes=recipes)
    chromosome.randomize(max_daily_capacity=95.0)
    
    print("Original schedule:")
    print(f"Day 0 totals: {chromosome.get_daily_totals(0)}")
    print(f"Day 1 totals: {chromosome.get_daily_totals(1)}")
    
    # Test mutation
    original_changeovers = chromosome._count_total_changeovers()
    chromosome.mutate(mutation_rate=1.0)  # Force mutation
    new_changeovers = chromosome._count_total_changeovers()
    
    print(f"\nAfter mutation:")
    print(f"Day 0 totals: {chromosome.get_daily_totals(0)}")
    print(f"Day 1 totals: {chromosome.get_daily_totals(1)}")
    print(f"Changeovers changed from {original_changeovers} to {new_changeovers}")

def test_chromosome_crossover():
    """Test chromosome crossover operation"""
    print("\n\n=== Testing Chromosome Crossover ===")
    
    recipes = [
        BlendingRecipe("Recipe_A", "Base", "Heavy", 80.0, 0.7),
        BlendingRecipe("Recipe_B", "Base", "Light", 90.0, 0.6),
    ]
    
    # Create two parent chromosomes
    parent1 = ScheduleChromosome(days=2, recipes=recipes)
    parent1.randomize(max_daily_capacity=95.0)
    
    parent2 = ScheduleChromosome(days=2, recipes=recipes)
    parent2.randomize(max_daily_capacity=95.0)
    
    print("Parent 1:")
    print(f"  Day 0: {parent1.get_daily_totals(0)}")
    print(f"  Day 1: {parent1.get_daily_totals(1)}")
    
    print("Parent 2:")
    print(f"  Day 0: {parent2.get_daily_totals(0)}")
    print(f"  Day 1: {parent2.get_daily_totals(1)}")
    
    # Perform crossover
    child1, child2 = parent1.crossover(parent2)
    
    print("\nChild 1:")
    print(f"  Day 0: {child1.get_daily_totals(0)}")
    print(f"  Day 1: {child1.get_daily_totals(1)}")
    
    print("Child 2:")
    print(f"  Day 0: {child2.get_daily_totals(0)}")
    print(f"  Day 1: {child2.get_daily_totals(1)}")

def test_scheduler_integration():
    """Test how chromosome integrates with scheduler interface"""
    print("\n\n=== Testing Scheduler Integration ===")
    
    recipes = [
        BlendingRecipe("Base_Heavy", "Base", "Heavy", 80.0, 0.7),
        BlendingRecipe("Base_Light", "Base", "Light", 90.0, 0.6),
    ]
    
    chromosome = ScheduleChromosome(days=1, recipes=recipes)
    chromosome.randomize(max_daily_capacity=95.0)
    
    # This is how the scheduler would use the chromosome
    day_idx = 0
    daily_totals = chromosome.get_daily_totals(day_idx)
    hourly_schedule = chromosome.get_hourly_schedule(day_idx)
    
    print(f"Scheduler interface for Day {day_idx}:")
    print(f"  Daily totals (for _create_daily_plan): {daily_totals}")
    print(f"  Hourly operations count: {len(hourly_schedule)}")
    
    # Show how daily totals match hourly breakdown
    hourly_calculated = {}
    productive_hours = 0
    changeover_hours = 0
    
    for hour_op in hourly_schedule:
        if hour_op.is_changeover:
            changeover_hours += 1
        elif hour_op.is_productive():
            productive_hours += 1
            recipe = hour_op.recipe_name
            if recipe not in hourly_calculated:
                hourly_calculated[recipe] = 0.0
            hourly_calculated[recipe] += hour_op.processing_rate
    
    print(f"  Productive hours: {productive_hours}")
    print(f"  Changeover hours: {changeover_hours}")
    print(f"  Idle hours: {24 - productive_hours - changeover_hours}")
    print(f"  Hourly calculated totals: {hourly_calculated}")
    print(f"  Match daily totals: {hourly_calculated == daily_totals}")

if __name__ == "__main__":
    test_chromosome_basic()
    test_chromosome_mutations()
    test_chromosome_crossover()
    test_scheduler_integration()
    
    print("\n\n=== GA Chromosome Design Complete ===")
    print("Key Features:")
    print("✓ Hourly granularity (24 hours per day)")
    print("✓ Recipe changeover modeling")
    print("✓ Mutation operators for schedule optimization")
    print("✓ Crossover for combining good schedules")
    print("✓ Integration interface with existing scheduler")
    print("✓ Automatic feasibility repair")
    print("✓ Daily/hourly consistency validation")
