"""Correct meters<->degrees conversion. Latitude degrees are ~constant
everywhere (~111,320m); longitude degrees shrink by cos(latitude) as you
move away from the equator. Every module that places or jitters a
lat/lon point MUST go through offset_latlon() below — never add a flat
epsilon to both lat and lon, it introduces a systematic east-west drift
that gets worse the further from the equator you deploy."""
import math

METERS_PER_DEG_LAT = 111_320.0


def meters_per_deg_lon(lat_deg: float) -> float:
    return METERS_PER_DEG_LAT * math.cos(math.radians(lat_deg))


def offset_latlon(lat: float, lon: float, dx_east_m: float, dy_north_m: float) -> tuple[float, float]:
    dlat = dy_north_m / METERS_PER_DEG_LAT
    dlon = dx_east_m / meters_per_deg_lon(lat)
    return lat + dlat, lon + dlon


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6_371_000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def bearing_deg(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dlmb = math.radians(lon2 - lon1)
    x = math.sin(dlmb) * math.cos(p2)
    y = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dlmb)
    return (math.degrees(math.atan2(x, y)) + 360) % 360
