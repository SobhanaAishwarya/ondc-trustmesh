"""City-level distance for buyer-seller matching.

ONDC buyers/sellers don't have precise GPS coordinates in this schema (no
maps/geocoding provider is wired up), so location is captured as a city
name chosen from a fixed list of major Indian cities, each mapped to an
approximate lat/lng. That's enough granularity for the paper's vendor-
matchmaking idea (favor nearby, fast-delivering sellers) without needing
an external geocoding API or raw coordinate input.
"""

import math

# Approximate city-centre coordinates (WGS84), not delivery-address precision.
CITY_COORDINATES: dict[str, tuple[float, float]] = {
    "Mumbai": (19.0760, 72.8777),
    "Delhi": (28.7041, 77.1025),
    "Bengaluru": (12.9716, 77.5946),
    "Hyderabad": (17.3850, 78.4867),
    "Chennai": (13.0827, 80.2707),
    "Kolkata": (22.5726, 88.3639),
    "Pune": (18.5204, 73.8567),
    "Ahmedabad": (23.0225, 72.5714),
    "Jaipur": (26.9124, 75.7873),
    "Lucknow": (26.8467, 80.9462),
    "Surat": (21.1702, 72.8311),
    "Kanpur": (26.4499, 80.3319),
    "Nagpur": (21.1458, 79.0882),
    "Indore": (22.7196, 75.8577),
    "Thane": (19.2183, 72.9781),
    "Bhopal": (23.2599, 77.4126),
    "Visakhapatnam": (17.6868, 83.2185),
    "Patna": (25.5941, 85.1376),
    "Vadodara": (22.3072, 73.1812),
    "Ghaziabad": (28.6692, 77.4538),
    "Coimbatore": (11.0168, 76.9558),
    "Kochi": (9.9312, 76.2673),
    "Chandigarh": (30.7333, 76.7794),
    "Guwahati": (26.1445, 91.7362),
}

CITY_NAMES: list[str] = sorted(CITY_COORDINATES)

EARTH_RADIUS_KM = 6371.0


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


def distance_between_cities(city_a: str | None, city_b: str | None) -> float | None:
    """None when either city is unset or not in the known list — callers
    should treat that as "unknown", not "far away"."""
    if not city_a or not city_b:
        return None
    coords_a = CITY_COORDINATES.get(city_a)
    coords_b = CITY_COORDINATES.get(city_b)
    if coords_a is None or coords_b is None:
        return None
    if city_a == city_b:
        return 0.0
    return round(haversine_km(*coords_a, *coords_b), 2)


def estimate_delivery_days(distance_km: float) -> int:
    """Coarse ETA bucket for the UI ("Delivery: 1 day") — not a logistics
    model, just a monotonic function of distance for the demo."""
    if distance_km <= 10:
        return 1
    if distance_km <= 150:
        return 2
    if distance_km <= 800:
        return 3
    return 5
