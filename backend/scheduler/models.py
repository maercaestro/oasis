"""
OASIS Base Scheduler/ models.py
This is where we define the models for the scheduler, which is 
the tanks, the plants, and the vessel, the blending recipes, and the feedstock parcel
Copyright (c) by Abu Huzaifah Bidin with help from Github Copilot
"""

from dataclasses import dataclass, field
from typing import List,Dict, Optional, Tuple

@dataclass
class Plant:
    """
    A class reprensenting a refinery in the OASIS system.
    """
    name: str
    capacity: float #in kb
    base_crude_capacity: float #capacity of base crude it was designed for
    max_inventory: float #in kb also (maximum inventory of the refinery, accumulatinf all tanks )

@dataclass
class Crude:
    """
    A class representing a crude in the OASIS system.
    """
    name: str
    margin: float #margin of the crude
    origin: str #origin of the crude


@dataclass
class Tank:
    """
    A class representing a tank in the OASIS system.
    """
    name: str
    capacity: float #maximum capacity of the tank, only pumpable
    content:List[Dict[str, float]] # list of dicts with keys as crude name and values as volume in kb

@dataclass
class BlendingRecipe:
    """
    A class representing a blending recipe in the OASIS system.
    """
    name: str
    primary_grade: str
    secondary_grade: Optional[str]
    max_rate: float  #in kb
    primary_fraction: float #fraction of primary grade in the blend

    #secondary_fraction can be calculated as 1 - primary_fraction

@dataclass
class FeedstockRequirement:
    """
    A class representing a feedstock requirement in the OASIS system.
    """
    grade: str
    volume: float
    origin: str
    allowed_ldr: Dict[int, int] #start and end date of the loading at terminal
    required_arrival_by: int #day by which the feedstock should arrive at the refinery


@dataclass
class FeedstockParcel:
    """
    A class representing a feedstock parcel in the OASIS system.
    """
    grade: str
    volume: float
    ldr:Dict[int,int] #start and end date of the loading at terminal
    origin: str #origin of the feedstock parcel
    vessel_id: Optional[str] = None #vessel id, if it is on a vessel

@dataclass
class Vessel:
    """
    A class representing a vessel in the OASIS system.
    """
    vessel_id: str
    arrival_day: int
    cost : float #cost of the vessel per kb
    capacity: float #maximum capacity of the vessel
    cargo: List[FeedstockParcel]
    original_arrival_day: Optional[int] =None
    days_held: int = 0  #days held at the arrival refinery



class Route:
    def __init__(self, origin, destination, time_travel, cost=None):
        self.origin = origin
        self.destination = destination
        self.time_travel = float(time_travel)  # Convert to float for safety
        self.cost = cost if cost is not None else 10000.0


@dataclass
class DailyPlan:
    """
    A class representing a daily plan in the OASIS system.
    """
    day: int
    processing_rates: Dict[str, float] 
    blending_details: List[BlendingRecipe]
    inventory: float
    inventory_by_grade: Dict[str, float]
    tanks: Dict[str, Tank]
    daily_margin: float = 0.0  # Add margin calculation as an optional field with default 0
