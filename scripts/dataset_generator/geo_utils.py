"""
geo_utils.py
------------
Correct-enough-for-a-city-block geospatial helpers.

THE CORE FACT THIS FILE ENCODES (this is what you flagged):
  Latitude  (y) : 1 degree is ALWAYS ~111,320 m, everywhere on Earth.
  Longitude(x) : 1 degree is 111,320 * cos(latitude) m — it SHRINKS as you
                  move away from the equator, because meridians converge
                  at the poles.

  So: if you displace a point by a fixed 10 m EAST, the change in the
  longitude (x) *value* is LARGER in degrees at higher latitudes than the
  same 10 m NORTH is in latitude (y) degrees, because you're dividing by a
  smaller number (fewer meters per degree of longitude).
  Concretely at Hyderabad (~17.4N): cos(17.4) = 0.954, so 1 deg longitude
  there is only ~106,200 m instead of 111,320 m -> a given east-west meter
  offset maps to a bigger degree-jump than the same offset north-south.

  If you use ONE flat epsilon for both lat and lon jitter (a common bug),
  your synthetic points drift off the real road line east-west more than
  they should, and the error gets worse the further from the equator you
  simulate. This module fixes that by always converting meters -> degrees
  through the correct per-axis constant.
"""

import numpy as np

METERS_PER_DEG_LAT = 111_320.0  # ~constant everywhere


def meters_per_deg_lon(lat_deg: float) -> float:
    """How many meters 1 degree of longitude covers AT THIS LATITUDE."""
    return METERS_PER_DEG_LAT * np.cos(np.radians(lat_deg))


def offset_latlon(lat: float, lon: float, dx_east_m: float, dy_north_m: float):
    """Move a (lat, lon) point by dx_east_m / dy_north_m meters and return
    the new (lat, lon). This is the function to use for ALL synthetic
    point placement — never add a flat +/-0.0001 to both lat and lon."""
    dlat = dy_north_m / METERS_PER_DEG_LAT
    dlon = dx_east_m / meters_per_deg_lon(lat)
    return lat + dlat, lon + dlon


def haversine_m(lat1, lon1, lat2, lon2) -> float:
    """Real-world distance in meters between two lat/lon points."""
    R = 6_371_000.0
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dphi = np.radians(lat2 - lat1)
    dlmb = np.radians(lon2 - lon1)
    a = np.sin(dphi / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dlmb / 2) ** 2
    return 2 * R * np.arcsin(np.sqrt(a))


def interpolate_latlon(lat1, lon1, lat2, lon2, frac: float):
    """Point at fraction `frac` (0..1) along the straight line from
    (lat1,lon1) to (lat2,lon2). Fine over short (<1km) road-segment
    distances — no great-circle correction needed at this scale."""
    return lat1 + (lat2 - lat1) * frac, lon1 + (lon2 - lon1) * frac


def bearing_deg(lat1, lon1, lat2, lon2) -> float:
    """Compass heading (0=N, 90=E, 180=S, 270=W) from point 1 to point 2."""
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dlmb = np.radians(lon2 - lon1)
    x = np.sin(dlmb) * np.cos(p2)
    y = np.cos(p1) * np.sin(p2) - np.sin(p1) * np.cos(p2) * np.cos(dlmb)
    return (np.degrees(np.arctan2(x, y)) + 360) % 360
