"""Fixed enums/constants shared across layers. Keep this the single
source of truth for event type names and vehicle types — services,
schemas, and the dataset generator should all import from here rather
than redefining these strings.
"""
from enum import Enum


class EventType(str, Enum):
    NORMAL = "normal"
    CONGESTION = "congestion"
    ROAD_BLOCK = "road_block"
    ROAD_DAMAGE = "road_damage"
    CONSTRUCTION = "construction"
    FLOOD = "flood"
    ACCIDENT = "accident"
    DIVERSION = "diversion"


class VehicleType(str, Enum):
    CAR = "car"
    BIKE = "bike"
    AUTO = "auto"
    BUS = "bus"


class RoadType(str, Enum):
    RESIDENTIAL = "residential"
    COLLECTOR = "collector"
    ARTERIAL = "arterial"
    HIGHWAY_LINK = "highway_link"


class RoadDirection(str, Enum):
    BIDIRECTIONAL = "bidirectional"
    ONE_WAY = "one_way"
