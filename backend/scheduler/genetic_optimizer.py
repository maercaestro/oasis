"""
OASIS Genetic Algorithm Optimizer
This module implements genetic algorithm optimization for refinery scheduling with hourly granularity.
Copyright (c) by Abu Huzaifah Bidin with help from Github Copilot
"""

import random
import copy
from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass, field
import numpy as np
from .models import BlendingRecipe, Crude, Tank
from .blending import BlendingEngine
import logging

logger = logging.getLogger("scheduler.genetic_optimizer")

@dataclass
class HourlyOperation:
    """Represents one hour of refinery operation"""
    hour: int  # 0-23
    recipe_name: Optional[str] = None
    processing_rate: float = 0.0
    is_changeover: bool = False
    changeover_from: Optional[str] = None
    changeover_to: Optional[str] = None
    changeover_progress: float = 0.0  # 0.0 to 1.0 for multi-hour changeovers

    def is_productive(self) -> bool:
        """Returns True if this hour produces output (not changeover)"""
        return not self.is_changeover and self.recipe_name is not None

    def get_hourly_rate(self) -> float:
        """Get the effective processing rate for this hour"""
        if self.is_productive():
            return self.processing_rate
        return 0.0

@dataclass  
class DaySchedule:
    """Represents 24 hours of refinery operations for one day"""
    day: int
    hours: List[HourlyOperation] = field(default_factory=lambda: [HourlyOperation(hour=h) for h in range(24)])
    
    def get_daily_totals(self) -> Dict[str, float]:
        """Convert hourly schedule to daily recipe totals"""
        daily_rates = {}
        for hour_op in self.hours:
            if hour_op.is_productive():
                recipe = hour_op.recipe_name
                if recipe not in daily_rates:
                    daily_rates[recipe] = 0.0
                daily_rates[recipe] += hour_op.processing_rate
        return daily_rates
    
    def get_total_production(self) -> float:
        """Get total daily production volume"""
        return sum(hour_op.get_hourly_rate() for hour_op in self.hours)
    
    def get_active_hours(self, recipe_name: str) -> List[int]:
        """Get list of hours when a specific recipe is active"""
        return [h.hour for h in self.hours if h.recipe_name == recipe_name and h.is_productive()]
    
    def get_changeover_hours(self) -> List[int]:
        """Get list of hours with changeovers"""
        return [h.hour for h in self.hours if h.is_changeover]
    
    def count_recipe_switches(self) -> int:
        """Count number of recipe changes in this day"""
        switches = 0
        prev_recipe = None
        for hour_op in self.hours:
            if hour_op.is_productive():
                if prev_recipe is not None and prev_recipe != hour_op.recipe_name:
                    switches += 1
                prev_recipe = hour_op.recipe_name
        return switches

class ScheduleChromosome:
    """
    Represents a complete schedule as a genetic algorithm chromosome.
    Each chromosome represents multiple days of hourly refinery operations.
    """
    
    def __init__(self, days: int = 7, recipes: List[BlendingRecipe] = None):
        """
        Initialize a chromosome for multi-day scheduling.
        
        Args:
            days: Number of days to schedule
            recipes: Available blending recipes
        """
        self.days = days
        self.recipes = recipes or []
        self.recipe_names = [r.name for r in self.recipes]
        self.schedule: List[DaySchedule] = []
        
        # Initialize empty schedule
        for day in range(days):
            self.schedule.append(DaySchedule(day=day))
        
        # Configuration parameters
        self.min_recipe_run_hours = 4  # Minimum hours to run a recipe
        self.changeover_duration_hours = 2  # Hours needed for recipe changeover
        self.max_daily_capacity = 95.0  # kb/day (will be set from scheduler)
        
        logger.debug(f"Created chromosome for {days} days with {len(self.recipes)} recipes")

    def randomize(self, max_daily_capacity: float = 95.0) -> None:
        """
        Generate a random but feasible schedule.
        
        Args:
            max_daily_capacity: Maximum daily processing capacity in kb/day
        """
        self.max_daily_capacity = max_daily_capacity
        max_hourly_rate = max_daily_capacity / 24  # Rough hourly capacity
        
        for day_idx in range(self.days):
            day_schedule = self.schedule[day_idx]
            
            # Randomly choose 1-2 recipes for this day
            num_recipes = random.choice([1, 2])  # Most days single recipe, some transitions
            selected_recipes = random.sample(self.recipe_names, min(num_recipes, len(self.recipe_names)))
            
            if len(selected_recipes) == 1:
                # Single recipe for the whole day
                recipe_name = selected_recipes[0]
                recipe = self._get_recipe(recipe_name)
                
                # Calculate reasonable hourly rate
                hourly_rate = min(
                    max_hourly_rate,
                    recipe.max_rate / 24 if recipe else max_hourly_rate
                )
                
                for hour in range(24):
                    day_schedule.hours[hour] = HourlyOperation(
                        hour=hour,
                        recipe_name=recipe_name,
                        processing_rate=hourly_rate
                    )
            
            else:
                # Multiple recipes - create a transition
                recipe1, recipe2 = selected_recipes[:2]
                
                # Randomly choose changeover time (avoid very early/late hours)
                changeover_start = random.randint(6, 18)
                changeover_end = changeover_start + self.changeover_duration_hours
                
                # Fill hours before changeover
                recipe1_obj = self._get_recipe(recipe1)
                hourly_rate1 = min(max_hourly_rate, recipe1_obj.max_rate / 24 if recipe1_obj else max_hourly_rate)
                
                for hour in range(changeover_start):
                    day_schedule.hours[hour] = HourlyOperation(
                        hour=hour,
                        recipe_name=recipe1,
                        processing_rate=hourly_rate1
                    )
                
                # Fill changeover hours
                for hour in range(changeover_start, min(changeover_end, 24)):
                    day_schedule.hours[hour] = HourlyOperation(
                        hour=hour,
                        is_changeover=True,
                        changeover_from=recipe1,
                        changeover_to=recipe2,
                        changeover_progress=(hour - changeover_start + 1) / self.changeover_duration_hours
                    )
                
                # Fill hours after changeover
                if changeover_end < 24:
                    recipe2_obj = self._get_recipe(recipe2)
                    hourly_rate2 = min(max_hourly_rate, recipe2_obj.max_rate / 24 if recipe2_obj else max_hourly_rate)
                    
                    for hour in range(changeover_end, 24):
                        day_schedule.hours[hour] = HourlyOperation(
                            hour=hour,
                            recipe_name=recipe2,
                            processing_rate=hourly_rate2
                        )
        
        logger.debug(f"Randomized chromosome with {self._count_total_changeovers()} total changeovers")

    def mutate(self, mutation_rate: float = 0.1) -> None:
        """
        Mutate the chromosome with various types of mutations.
        
        Args:
            mutation_rate: Probability of mutation occurring
        """
        if random.random() > mutation_rate:
            return
        
        # Choose mutation type
        mutation_types = [
            self._mutate_recipe_change,
            self._mutate_changeover_timing,
            self._mutate_processing_rates,
            self._mutate_recipe_duration
        ]
        
        mutation_func = random.choice(mutation_types)
        mutation_func()
        
        # Ensure feasibility after mutation
        self._repair_schedule()
        
        logger.debug(f"Applied mutation: {mutation_func.__name__}")

    def _mutate_recipe_change(self) -> None:
        """Randomly change recipe for a portion of a day"""
        day_idx = random.randint(0, self.days - 1)
        day_schedule = self.schedule[day_idx]
        
        # Find productive hours
        productive_hours = [h for h in range(24) if day_schedule.hours[h].is_productive()]
        if not productive_hours:
            return
        
        # Choose a random span of hours to change
        start_hour = random.choice(productive_hours)
        end_hour = min(24, start_hour + random.randint(2, 8))
        
        # Choose new recipe
        new_recipe = random.choice(self.recipe_names)
        new_rate = self._calculate_reasonable_rate(new_recipe)
        
        for hour in range(start_hour, end_hour):
            if hour < 24:
                day_schedule.hours[hour].recipe_name = new_recipe
                day_schedule.hours[hour].processing_rate = new_rate
                day_schedule.hours[hour].is_changeover = False

    def _mutate_changeover_timing(self) -> None:
        """Shift changeover timing"""
        day_idx = random.randint(0, self.days - 1)
        day_schedule = self.schedule[day_idx]
        
        changeover_hours = day_schedule.get_changeover_hours()
        if not changeover_hours:
            return
        
        # Shift changeover by 1-3 hours
        shift = random.randint(-3, 3)
        for hour_idx in changeover_hours:
            new_hour = hour_idx + shift
            if 0 <= new_hour < 24:
                # Move changeover operation
                old_op = day_schedule.hours[hour_idx]
                day_schedule.hours[new_hour] = copy.deepcopy(old_op)
                day_schedule.hours[new_hour].hour = new_hour
                
                # Clear old hour
                day_schedule.hours[hour_idx] = HourlyOperation(hour=hour_idx)

    def _mutate_processing_rates(self) -> None:
        """Adjust processing rates slightly"""
        day_idx = random.randint(0, self.days - 1)
        day_schedule = self.schedule[day_idx]
        
        for hour_op in day_schedule.hours:
            if hour_op.is_productive():
                # Adjust rate by ±10%
                adjustment = random.uniform(0.9, 1.1)
                hour_op.processing_rate *= adjustment
                
                # Ensure within recipe limits
                recipe = self._get_recipe(hour_op.recipe_name)
                if recipe:
                    max_hourly = recipe.max_rate / 24
                    hour_op.processing_rate = min(hour_op.processing_rate, max_hourly)

    def _mutate_recipe_duration(self) -> None:
        """Change how long a recipe runs"""
        day_idx = random.randint(0, self.days - 1)
        day_schedule = self.schedule[day_idx]
        
        # Find recipe runs
        current_recipe = None
        run_start = 0
        
        for hour in range(24):
            hour_op = day_schedule.hours[hour]
            if hour_op.is_productive():
                if current_recipe != hour_op.recipe_name:
                    # New recipe run
                    if current_recipe is not None:
                        # Modify previous run
                        self._adjust_recipe_run(day_schedule, run_start, hour - 1, current_recipe)
                    current_recipe = hour_op.recipe_name
                    run_start = hour
        
        # Handle last run
        if current_recipe is not None:
            self._adjust_recipe_run(day_schedule, run_start, 23, current_recipe)

    def _adjust_recipe_run(self, day_schedule: DaySchedule, start: int, end: int, recipe_name: str) -> None:
        """Randomly extend or shorten a recipe run"""
        if end - start < 2:  # Too short to modify
            return
        
        # Randomly extend or shorten by 1-2 hours
        change = random.randint(-2, 2)
        new_end = min(23, max(start + 1, end + change))
        
        rate = self._calculate_reasonable_rate(recipe_name)
        
        # Apply new duration
        for hour in range(start, new_end + 1):
            if hour < 24:
                day_schedule.hours[hour].recipe_name = recipe_name
                day_schedule.hours[hour].processing_rate = rate
                day_schedule.hours[hour].is_changeover = False

    def crossover(self, other: 'ScheduleChromosome') -> Tuple['ScheduleChromosome', 'ScheduleChromosome']:
        """
        Create two offspring through crossover with another chromosome.
        
        Args:
            other: Another chromosome to crossover with
            
        Returns:
            Tuple of two offspring chromosomes
        """
        child1 = ScheduleChromosome(self.days, self.recipes)
        child2 = ScheduleChromosome(self.days, self.recipes)
        
        child1.max_daily_capacity = self.max_daily_capacity
        child2.max_daily_capacity = self.max_daily_capacity
        
        # Day-wise crossover: randomly choose which parent contributes each day
        for day_idx in range(self.days):
            if random.random() < 0.5:
                child1.schedule[day_idx] = copy.deepcopy(self.schedule[day_idx])
                child2.schedule[day_idx] = copy.deepcopy(other.schedule[day_idx])
            else:
                child1.schedule[day_idx] = copy.deepcopy(other.schedule[day_idx])
                child2.schedule[day_idx] = copy.deepcopy(self.schedule[day_idx])
        
        # Repair any infeasibilities
        child1._repair_schedule()
        child2._repair_schedule()
        
        logger.debug("Performed crossover operation")
        return child1, child2

    def _repair_schedule(self) -> None:
        """Repair schedule to ensure feasibility"""
        for day_schedule in self.schedule:
            self._repair_day_schedule(day_schedule)

    def _repair_day_schedule(self, day_schedule: DaySchedule) -> None:
        """Repair a single day's schedule"""
        # Ensure recipe runs meet minimum duration
        current_recipe = None
        run_start = 0
        
        for hour in range(24):
            hour_op = day_schedule.hours[hour]
            if hour_op.is_productive():
                if current_recipe != hour_op.recipe_name:
                    # Check if previous run was too short
                    if current_recipe is not None and (hour - run_start) < self.min_recipe_run_hours:
                        # Extend previous recipe
                        for extend_hour in range(run_start, min(24, run_start + self.min_recipe_run_hours)):
                            day_schedule.hours[extend_hour].recipe_name = current_recipe
                            day_schedule.hours[extend_hour].is_changeover = False
                    
                    current_recipe = hour_op.recipe_name
                    run_start = hour
        
        # Ensure daily capacity limits
        total_production = day_schedule.get_total_production()
        if total_production > self.max_daily_capacity:
            # Scale down all rates proportionally
            scale_factor = self.max_daily_capacity / total_production
            for hour_op in day_schedule.hours:
                if hour_op.is_productive():
                    hour_op.processing_rate *= scale_factor

    def _get_recipe(self, recipe_name: str) -> Optional[BlendingRecipe]:
        """Get recipe object by name"""
        for recipe in self.recipes:
            if recipe.name == recipe_name:
                return recipe
        return None

    def _calculate_reasonable_rate(self, recipe_name: str) -> float:
        """Calculate a reasonable hourly processing rate for a recipe"""
        recipe = self._get_recipe(recipe_name)
        if recipe:
            # Use recipe max rate as guideline, but adapt to hourly operation
            max_hourly = recipe.max_rate / 24
            return min(max_hourly, self.max_daily_capacity / 24)
        return self.max_daily_capacity / 24

    def _count_total_changeovers(self) -> int:
        """Count total number of changeovers in the schedule"""
        total = 0
        for day_schedule in self.schedule:
            total += len(day_schedule.get_changeover_hours())
        return total

    def get_daily_totals(self, day_idx: int) -> Dict[str, float]:
        """Get daily recipe totals for a specific day (interface for scheduler)"""
        if 0 <= day_idx < len(self.schedule):
            return self.schedule[day_idx].get_daily_totals()
        return {}

    def get_hourly_schedule(self, day_idx: int) -> List[HourlyOperation]:
        """Get hourly schedule for a specific day"""
        if 0 <= day_idx < len(self.schedule):
            return self.schedule[day_idx].hours
        return []

    def __str__(self) -> str:
        """String representation for debugging"""
        summary = f"ScheduleChromosome({self.days} days)\n"
        for day_idx, day_schedule in enumerate(self.schedule):
            daily_totals = day_schedule.get_daily_totals()
            changeovers = len(day_schedule.get_changeover_hours())
            summary += f"  Day {day_idx}: {daily_totals}, {changeovers} changeovers\n"
        return summary

class FitnessEvaluator:
    """
    Evaluates fitness of schedule chromosomes based on multiple objectives:
    - Margin maximization
    - Throughput maximization  
    - Operational efficiency (minimize changeovers)
    - Inventory management
    """
    
    def __init__(self, blending_engine: BlendingEngine, crude_data: Dict[str, Crude],
                 weights: Dict[str, float] = None):
        """
        Initialize fitness evaluator.
        
        Args:
            blending_engine: For calculating recipe margins
            crude_data: Crude pricing and margin data
            weights: Weights for different objectives
        """
        self.blending_engine = blending_engine
        self.crude_data = crude_data
        
        # Default weights for multi-objective optimization
        self.weights = weights or {
            'margin': 0.5,      # 50% weight on margin
            'throughput': 0.3,  # 30% weight on throughput
            'operational': 0.2  # 20% weight on operational efficiency
        }
        
        logger.info(f"Initialized FitnessEvaluator with weights: {self.weights}")

    def evaluate_fitness(self, chromosome: ScheduleChromosome, 
                        initial_inventory: Dict[str, float],
                        vessel_arrivals: Dict[int, Dict[str, float]] = None) -> Dict[str, float]:
        """
        Evaluate fitness of a chromosome across multiple objectives.
        
        Args:
            chromosome: Schedule chromosome to evaluate
            initial_inventory: Starting inventory by grade
            vessel_arrivals: Dict of {day: {grade: volume}} for vessel arrivals
            
        Returns:
            Dict with fitness scores and total weighted fitness
        """
        try:
            # Simulate the schedule to check feasibility
            simulation_result = self._simulate_schedule(chromosome, initial_inventory, vessel_arrivals)
            
            if not simulation_result['feasible']:
                # Heavy penalty for infeasible schedules
                return {
                    'margin_score': 0.0,
                    'throughput_score': 0.0,
                    'operational_score': 0.0,
                    'total_fitness': -1000.0,
                    'feasible': False,
                    'penalty_reason': simulation_result.get('penalty_reason', 'Unknown infeasibility')
                }
            
            # Calculate individual fitness components
            margin_score = self._calculate_margin_fitness(chromosome)
            throughput_score = self._calculate_throughput_fitness(chromosome)
            operational_score = self._calculate_operational_fitness(chromosome)
            
            # Calculate weighted total fitness
            total_fitness = (
                self.weights['margin'] * margin_score +
                self.weights['throughput'] * throughput_score +
                self.weights['operational'] * operational_score
            )
            
            return {
                'margin_score': margin_score,
                'throughput_score': throughput_score,
                'operational_score': operational_score,
                'total_fitness': total_fitness,
                'feasible': True,
                'inventory_levels': simulation_result['final_inventory']
            }
            
        except Exception as e:
            logger.error(f"Error evaluating fitness: {e}")
            return {
                'margin_score': 0.0,
                'throughput_score': 0.0,
                'operational_score': 0.0,
                'total_fitness': -500.0,
                'feasible': False,
                'penalty_reason': f'Evaluation error: {str(e)}'
            }

    def _simulate_schedule(self, chromosome: ScheduleChromosome, 
                          initial_inventory: Dict[str, float],
                          vessel_arrivals: Dict[int, Dict[str, float]] = None) -> Dict[str, Any]:
        """
        Simulate the schedule to check inventory feasibility.
        
        Returns:
            Dict with feasibility status and final inventory levels
        """
        current_inventory = initial_inventory.copy()
        vessel_arrivals = vessel_arrivals or {}
        
        for day_idx in range(chromosome.days):
            # Add vessel arrivals for this day
            if day_idx in vessel_arrivals:
                for grade, volume in vessel_arrivals[day_idx].items():
                    current_inventory[grade] = current_inventory.get(grade, 0) + volume
            
            # Process hourly operations
            day_schedule = chromosome.schedule[day_idx]
            for hour_op in day_schedule.hours:
                if hour_op.is_productive():
                    # Get recipe and calculate consumption
                    recipe = chromosome._get_recipe(hour_op.recipe_name)
                    if recipe:
                        primary_consumption = hour_op.processing_rate * recipe.primary_fraction
                        
                        # Check primary grade availability
                        if current_inventory.get(recipe.primary_grade, 0) < primary_consumption:
                            return {
                                'feasible': False,
                                'penalty_reason': f'Day {day_idx} Hour {hour_op.hour}: Insufficient {recipe.primary_grade} inventory',
                                'final_inventory': current_inventory
                            }
                        
                        # Consume primary grade
                        current_inventory[recipe.primary_grade] -= primary_consumption
                        
                        # Handle secondary grade if exists
                        if recipe.secondary_grade:
                            secondary_consumption = hour_op.processing_rate * (1 - recipe.primary_fraction)
                            
                            if current_inventory.get(recipe.secondary_grade, 0) < secondary_consumption:
                                return {
                                    'feasible': False,
                                    'penalty_reason': f'Day {day_idx} Hour {hour_op.hour}: Insufficient {recipe.secondary_grade} inventory',
                                    'final_inventory': current_inventory
                                }
                            
                            current_inventory[recipe.secondary_grade] -= secondary_consumption
        
        return {
            'feasible': True,
            'final_inventory': current_inventory
        }

    def _calculate_margin_fitness(self, chromosome: ScheduleChromosome) -> float:
        """Calculate fitness based on total margin generated"""
        total_margin = 0.0
        
        for day_schedule in chromosome.schedule:
            for hour_op in day_schedule.hours:
                if hour_op.is_productive():
                    recipe = chromosome._get_recipe(hour_op.recipe_name)
                    if recipe:
                        recipe_margin = self.blending_engine.blend_margin(recipe, self.crude_data)
                        hour_margin = hour_op.processing_rate * recipe_margin
                        total_margin += hour_margin
        
        # Normalize margin score (assuming typical margin range 0-50 $/kb)
        normalized_margin = min(total_margin / 1000.0, 100.0)  # Scale to 0-100
        return max(0.0, normalized_margin)

    def _calculate_throughput_fitness(self, chromosome: ScheduleChromosome) -> float:
        """Calculate fitness based on total production volume"""
        total_production = 0.0
        max_possible_production = chromosome.max_daily_capacity * chromosome.days
        
        for day_schedule in chromosome.schedule:
            daily_production = day_schedule.get_total_production()
            total_production += daily_production
        
        # Normalize throughput score (0-100 scale)
        if max_possible_production > 0:
            throughput_ratio = total_production / max_possible_production
            return min(throughput_ratio * 100.0, 100.0)
        
        return 0.0

    def _calculate_operational_fitness(self, chromosome: ScheduleChromosome) -> float:
        """Calculate fitness based on operational efficiency"""
        total_changeovers = 0
        total_recipe_switches = 0
        total_idle_hours = 0
        
        for day_schedule in chromosome.schedule:
            # Count changeovers and switches
            total_changeovers += len(day_schedule.get_changeover_hours())
            total_recipe_switches += day_schedule.count_recipe_switches()
            
            # Count idle hours
            for hour_op in day_schedule.hours:
                if not hour_op.is_productive() and not hour_op.is_changeover:
                    total_idle_hours += 1
        
        # Calculate penalties
        changeover_penalty = total_changeovers * 2.0  # 2 points per changeover hour
        switch_penalty = total_recipe_switches * 5.0  # 5 points per recipe switch
        idle_penalty = total_idle_hours * 1.0  # 1 point per idle hour
        
        total_penalty = changeover_penalty + switch_penalty + idle_penalty
        
        # Start with base score and subtract penalties
        base_score = 100.0
        operational_score = max(0.0, base_score - total_penalty)
        
        return operational_score


class GeneticAlgorithmPopulation:
    """
    Manages a population of schedule chromosomes and evolves them using genetic algorithms.
    """
    
    def __init__(self, population_size: int = 50, elite_size: int = 10, 
                 mutation_rate: float = 0.1, crossover_rate: float = 0.8):
        """
        Initialize GA population manager.
        
        Args:
            population_size: Number of chromosomes in population
            elite_size: Number of best chromosomes to preserve each generation
            mutation_rate: Probability of mutation
            crossover_rate: Probability of crossover
        """
        self.population_size = population_size
        self.elite_size = elite_size
        self.mutation_rate = mutation_rate
        self.crossover_rate = crossover_rate
        
        self.population: List[ScheduleChromosome] = []
        self.fitness_scores: List[Dict[str, float]] = []
        self.generation = 0
        self.best_fitness_history: List[float] = []
        
        logger.info(f"Initialized GA Population: size={population_size}, elite={elite_size}, "
                   f"mutation_rate={mutation_rate}, crossover_rate={crossover_rate}")

    def initialize_population(self, days: int, recipes: List[BlendingRecipe], 
                            max_daily_capacity: float) -> None:
        """
        Create initial random population.
        
        Args:
            days: Number of days to schedule
            recipes: Available blending recipes
            max_daily_capacity: Maximum daily processing capacity
        """
        self.population = []
        
        for i in range(self.population_size):
            chromosome = ScheduleChromosome(days=days, recipes=recipes)
            chromosome.randomize(max_daily_capacity=max_daily_capacity)
            self.population.append(chromosome)
        
        self.fitness_scores = [None] * self.population_size
        logger.info(f"Initialized population with {len(self.population)} chromosomes")

    def evaluate_population(self, fitness_evaluator: FitnessEvaluator,
                          initial_inventory: Dict[str, float],
                          vessel_arrivals: Dict[int, Dict[str, float]] = None) -> None:
        """
        Evaluate fitness for all chromosomes in the population.
        """
        logger.info(f"Evaluating generation {self.generation} population fitness...")
        
        for i, chromosome in enumerate(self.population):
            self.fitness_scores[i] = fitness_evaluator.evaluate_fitness(
                chromosome, initial_inventory, vessel_arrivals
            )
        
        # Track best fitness
        feasible_fitness = [score['total_fitness'] for score in self.fitness_scores 
                           if score.get('feasible', False)]
        
        if feasible_fitness:
            best_fitness = max(feasible_fitness)
            self.best_fitness_history.append(best_fitness)
            logger.info(f"Generation {self.generation}: Best fitness = {best_fitness:.2f}")
        else:
            self.best_fitness_history.append(-1000.0)
            logger.warning(f"Generation {self.generation}: No feasible solutions found!")

    def evolve_generation(self) -> None:
        """
        Evolve the population for one generation using selection, crossover, and mutation.
        """
        logger.debug(f"Evolving generation {self.generation}...")
        
        # Selection: keep elite chromosomes
        elite_population = self._select_elite()
        
        # Generate offspring through crossover and mutation
        offspring = self._generate_offspring()
        
        # Create new population: elite + offspring
        self.population = elite_population + offspring
        
        # Ensure population size is maintained
        if len(self.population) > self.population_size:
            self.population = self.population[:self.population_size]
        
        # Reset fitness scores for new population
        self.fitness_scores = [None] * len(self.population)
        self.generation += 1
        
        logger.debug(f"Generation {self.generation} created with {len(self.population)} chromosomes")

    def _select_elite(self) -> List[ScheduleChromosome]:
        """Select the best chromosomes for the next generation"""
        # Sort by fitness (highest first)
        fitness_chromosome_pairs = list(zip(self.fitness_scores, self.population))
        
        # Prioritize feasible solutions
        feasible_pairs = [(f, c) for f, c in fitness_chromosome_pairs if f.get('feasible', False)]
        infeasible_pairs = [(f, c) for f, c in fitness_chromosome_pairs if not f.get('feasible', False)]
        
        # Sort feasible by fitness, infeasible by least negative fitness
        feasible_pairs.sort(key=lambda x: x[0]['total_fitness'], reverse=True)
        infeasible_pairs.sort(key=lambda x: x[0]['total_fitness'], reverse=True)
        
        # Select elite from feasible first, then infeasible if needed
        all_sorted_pairs = feasible_pairs + infeasible_pairs
        elite_pairs = all_sorted_pairs[:self.elite_size]
        
        return [copy.deepcopy(chromosome) for _, chromosome in elite_pairs]

    def _generate_offspring(self) -> List[ScheduleChromosome]:
        """Generate offspring through crossover and mutation"""
        offspring = []
        needed_offspring = self.population_size - self.elite_size
        
        while len(offspring) < needed_offspring:
            # Tournament selection for parents
            parent1 = self._tournament_selection()
            parent2 = self._tournament_selection()
            
            # Crossover
            if random.random() < self.crossover_rate:
                child1, child2 = parent1.crossover(parent2)
            else:
                child1, child2 = copy.deepcopy(parent1), copy.deepcopy(parent2)
            
            # Mutation
            child1.mutate(self.mutation_rate)
            child2.mutate(self.mutation_rate)
            
            offspring.extend([child1, child2])
        
        return offspring[:needed_offspring]

    def _tournament_selection(self, tournament_size: int = 3) -> ScheduleChromosome:
        """Select a chromosome using tournament selection"""
        tournament_indices = random.sample(range(len(self.population)), 
                                          min(tournament_size, len(self.population)))
        
        # Find best chromosome in tournament
        best_idx = tournament_indices[0]
        best_fitness = self.fitness_scores[best_idx]['total_fitness']
        
        for idx in tournament_indices[1:]:
            fitness = self.fitness_scores[idx]['total_fitness']
            if fitness > best_fitness:
                best_fitness = fitness
                best_idx = idx
        
        return copy.deepcopy(self.population[best_idx])

    def get_best_chromosome(self) -> Tuple[ScheduleChromosome, Dict[str, float]]:
        """Get the best chromosome and its fitness from current population"""
        if not self.fitness_scores:
            raise ValueError("Population has not been evaluated yet")
        
        # Find best feasible solution
        best_idx = 0
        best_fitness = self.fitness_scores[0]['total_fitness']
        best_is_feasible = self.fitness_scores[0].get('feasible', False)
        
        for i, fitness in enumerate(self.fitness_scores[1:], 1):
            is_feasible = fitness.get('feasible', False)
            current_fitness = fitness['total_fitness']
            
            # Prefer feasible solutions, then higher fitness
            if (is_feasible and not best_is_feasible) or \
               (is_feasible == best_is_feasible and current_fitness > best_fitness):
                best_fitness = current_fitness
                best_idx = i
                best_is_feasible = is_feasible
        
        return copy.deepcopy(self.population[best_idx]), self.fitness_scores[best_idx]

    def get_population_stats(self) -> Dict[str, Any]:
        """Get statistics about current population"""
        if not self.fitness_scores:
            return {"error": "Population not evaluated"}
        
        fitness_values = [score['total_fitness'] for score in self.fitness_scores]
        feasible_count = sum(1 for score in self.fitness_scores if score.get('feasible', False))
        
        return {
            'generation': self.generation,
            'population_size': len(self.population),
            'feasible_solutions': feasible_count,
            'feasible_percentage': (feasible_count / len(self.population)) * 100,
            'best_fitness': max(fitness_values),
            'average_fitness': sum(fitness_values) / len(fitness_values),
            'worst_fitness': min(fitness_values),
            'fitness_std': np.std(fitness_values)
        }

class GeneticSchedulerOptimizer:
    """
    Main genetic algorithm optimizer for refinery scheduling.
    Coordinates population management, fitness evaluation, and evolution.
    """
    
    def __init__(self, recipes: List[BlendingRecipe], crude_data: Dict[str, Crude],
                 max_processing_rate: float, population_size: int = 50,
                 generations: int = 100, mutation_rate: float = 0.1):
        """
        Initialize the genetic scheduler optimizer.
        
        Args:
            recipes: Available blending recipes
            crude_data: Crude pricing and margin data
            max_processing_rate: Maximum daily processing capacity
            population_size: Size of GA population
            generations: Number of generations to evolve
            mutation_rate: Probability of mutation
        """
        self.recipes = recipes
        self.crude_data = crude_data
        self.max_processing_rate = max_processing_rate
        self.generations = generations
        
        # Initialize GA components
        self.blending_engine = BlendingEngine()
        self.fitness_evaluator = FitnessEvaluator(self.blending_engine, crude_data)
        self.population = GeneticAlgorithmPopulation(
            population_size=population_size,
            elite_size=max(5, population_size // 10),  # 10% elite
            mutation_rate=mutation_rate,
            crossover_rate=0.8
        )
        
        # Optimization history
        self.optimization_history = []
        
        logger.info(f"Initialized GeneticSchedulerOptimizer with {len(recipes)} recipes, "
                   f"population_size={population_size}, generations={generations}")

    def optimize_schedule(self, days: int, initial_inventory: Dict[str, float],
                         vessel_arrivals: Dict[int, Dict[str, float]] = None,
                         target_generations: int = None) -> Dict[str, Any]:
        """
        Optimize refinery schedule using genetic algorithm.
        
        Args:
            days: Number of days to schedule
            initial_inventory: Starting inventory by grade
            vessel_arrivals: Dict of {day: {grade: volume}} for vessel arrivals
            target_generations: Override default generations if specified
            
        Returns:
            Dict containing best schedule and optimization results
        """
        generations_to_run = target_generations or self.generations
        
        logger.info(f"Starting GA optimization for {days} days, {generations_to_run} generations")
        logger.info(f"Initial inventory: {initial_inventory}")
        if vessel_arrivals:
            logger.info(f"Vessel arrivals scheduled for {len(vessel_arrivals)} days")
        
        # Initialize population
        self.population.initialize_population(days, self.recipes, self.max_processing_rate)
        
        # Evolution loop
        for generation in range(generations_to_run):
            # Evaluate population
            self.population.evaluate_population(
                self.fitness_evaluator, initial_inventory, vessel_arrivals
            )
            
            # Log progress
            stats = self.population.get_population_stats()
            self.optimization_history.append(stats)
            
            if generation % 10 == 0 or generation == generations_to_run - 1:
                logger.info(f"Generation {generation}: "
                           f"Best={stats['best_fitness']:.2f}, "
                           f"Avg={stats['average_fitness']:.2f}, "
                           f"Feasible={stats['feasible_percentage']:.1f}%")
            
            # Check for early convergence
            if generation > 20 and self._check_convergence():
                logger.info(f"Early convergence detected at generation {generation}")
                break
            
            # Evolve to next generation (except last)
            if generation < generations_to_run - 1:
                self.population.evolve_generation()
        
        # Get best solution
        best_chromosome, best_fitness = self.population.get_best_chromosome()
        
        # Prepare results
        results = {
            'best_chromosome': best_chromosome,
            'best_fitness': best_fitness,
            'optimization_stats': self.optimization_history[-1],
            'convergence_history': [h['best_fitness'] for h in self.optimization_history],
            'total_generations': len(self.optimization_history),
            'success': best_fitness.get('feasible', False)
        }
        
        logger.info(f"GA optimization complete: "
                   f"Best fitness={best_fitness['total_fitness']:.2f}, "
                   f"Feasible={best_fitness.get('feasible', False)}")
        
        return results

    def optimize_for_scheduler(self, days: int, initial_inventory: Dict[str, float],
                             starting_day: int = 1, 
                             vessel_arrivals: Dict[int, Dict[str, float]] = None) -> ScheduleChromosome:
        """
        Optimize schedule specifically for scheduler integration.
        Uses shorter optimization suitable for real-time scheduling.
        
        Args:
            days: Number of days to schedule (typically 7 for rolling window)
            initial_inventory: Starting inventory by grade
            starting_day: Starting day number for the schedule
            vessel_arrivals: Vessel arrivals during the period
            
        Returns:
            Best schedule chromosome optimized for the period
        """
        # Use shorter optimization for real-time performance
        quick_generations = min(50, self.generations)
        
        logger.info(f"Quick GA optimization for scheduler: {days} days, {quick_generations} generations")
        
        results = self.optimize_schedule(
            days=days,
            initial_inventory=initial_inventory,
            vessel_arrivals=vessel_arrivals,
            target_generations=quick_generations
        )
        
        if results['success']:
            chromosome = results['best_chromosome']
            logger.info(f"Scheduler optimization successful: "
                       f"fitness={results['best_fitness']['total_fitness']:.2f}")
            return chromosome
        else:
            # Return a simple feasible schedule if optimization fails
            logger.warning("GA optimization failed, creating simple fallback schedule")
            return self._create_fallback_schedule(days, initial_inventory)

    def _check_convergence(self, window_size: int = 10, threshold: float = 0.1) -> bool:
        """
        Check if the population has converged (fitness improvement stagnated).
        
        Args:
            window_size: Number of generations to look back
            threshold: Minimum improvement required to avoid convergence
            
        Returns:
            True if converged, False otherwise
        """
        if len(self.optimization_history) < window_size:
            return False
        
        recent_fitness = [h['best_fitness'] for h in self.optimization_history[-window_size:]]
        
        # Check if improvement is below threshold
        if len(recent_fitness) >= 2:
            max_fitness = max(recent_fitness)
            min_fitness = min(recent_fitness)
            improvement = max_fitness - min_fitness
            
            return improvement < threshold
        
        return False

    def _create_fallback_schedule(self, days: int, 
                                initial_inventory: Dict[str, float]) -> ScheduleChromosome:
        """
        Create a simple, feasible fallback schedule when GA optimization fails.
        
        Args:
            days: Number of days to schedule
            initial_inventory: Available inventory
            
        Returns:
            Simple feasible chromosome
        """
        logger.info("Creating fallback schedule with single best recipe")
        
        # Find recipe with best margin that's feasible with current inventory
        best_recipe = None
        best_margin = -float('inf')
        
        for recipe in self.recipes:
            margin = self.blending_engine.blend_margin(recipe, self.crude_data)
            
            # Check if we have enough inventory for at least one day
            primary_needed = (self.max_processing_rate / 24) * recipe.primary_fraction
            primary_available = initial_inventory.get(recipe.primary_grade, 0)
            
            secondary_needed = 0
            secondary_available = float('inf')
            if recipe.secondary_grade:
                secondary_needed = (self.max_processing_rate / 24) * (1 - recipe.primary_fraction)
                secondary_available = initial_inventory.get(recipe.secondary_grade, 0)
            
            if (primary_available >= primary_needed and 
                secondary_available >= secondary_needed and 
                margin > best_margin):
                best_recipe = recipe
                best_margin = margin
        
        # Create simple schedule with best recipe
        fallback_chromosome = ScheduleChromosome(days=days, recipes=self.recipes)
        fallback_chromosome.max_daily_capacity = self.max_processing_rate
        
        if best_recipe:
            # Fill all days with the best recipe
            hourly_rate = min(
                self.max_processing_rate / 24,
                best_recipe.max_rate / 24
            )
            
            for day_idx in range(days):
                day_schedule = fallback_chromosome.schedule[day_idx]
                for hour in range(24):
                    day_schedule.hours[hour] = HourlyOperation(
                        hour=hour,
                        recipe_name=best_recipe.name,
                        processing_rate=hourly_rate
                    )
        
        logger.info(f"Created fallback schedule using recipe: {best_recipe.name if best_recipe else 'None'}")
        return fallback_chromosome

    def get_optimization_summary(self) -> Dict[str, Any]:
        """
        Get summary of the optimization process.
        
        Returns:
            Dict with optimization summary statistics
        """
        if not self.optimization_history:
            return {"error": "No optimization history available"}
        
        final_stats = self.optimization_history[-1]
        convergence_history = [h['best_fitness'] for h in self.optimization_history]
        
        return {
            'total_generations': len(self.optimization_history),
            'final_best_fitness': final_stats['best_fitness'],
            'final_feasible_percentage': final_stats['feasible_percentage'],
            'fitness_improvement': convergence_history[-1] - convergence_history[0] if len(convergence_history) > 1 else 0,
            'convergence_history': convergence_history,
            'population_size': final_stats['population_size'],
            'recipes_available': len(self.recipes),
            'optimization_successful': final_stats['feasible_solutions'] > 0
        }
