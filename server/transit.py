"""DMRC metro leg for the /compare mode set — the biggest dose lever.

Leaving the road entirely beats every road-mode microenv: measured
breathing-zone PM2.5 on the metro is ~34.2 µg/m³ vs 113.2 in an
auto-rickshaw on the same corridor (exposure.py [2]), and MICROENV +
VENTILATION make a metro minute inhale ~4x less than a walking minute.

Station registry: REAL coordinates fetched from OpenStreetMap via the
Overpass API (lz4.overpass-api.de mirror):

    [out:json][timeout:20];
    node["railway"="station"](28.20,76.80,28.95,77.90);
    out;

filtered to network in (Delhi Metro, Noida Metro, Rapid Metro Gurgaon),
then collapsed to the 62 busiest interchange + terminal + high-footfall
stations across the 12 DMRC lines. Interchange complexes mapped as one
node per line (e.g. "Hauz Khas (Yellow Line)" + "(Magenta Line)") were
merged into a single entry with averaged coordinates.

Honesty envelope: this is a station-to-station model, not a transit
router. Leg geometries are straight lines; the metro leg is inflated by
METRO_DETOUR for network circuity. Walk legs follow the same
straight-line convention the app already uses for OSRM fallbacks.
"""
from typing import Callable, Optional

import exposure

try:
    import transit_real  # GTFS-backed real metro/bus network when cached
except Exception:
    transit_real = None

# --- Stated assumptions (see docs/09-transit.md) ---------------------------
METRO_DETOUR = 1.35       # network circuity: straight-line x 1.35 approximates
                          # track distance for station-to-station trips
METRO_SPEED_KMH = 32.0    # DMRC average commercial speed incl. dwell time
ACCESS_WAIT_MIN = 5.0     # station entry + average headway wait + interchange
WALK_SPEED_KMH = 5.0      # matches MODE_SPEED_KMH["walking"] in main.py
MAX_ACCESS_KM = 2.5       # farther than this, "metro + walk" is not credible

# --- Station registry (embedded real OSM coordinates) ----------------------
STATIONS = [
    {"name": "Rajiv Chowk", "lat": 28.632742, "lon": 77.219505, "lines": ['Yellow', 'Blue']},
    {"name": "Kashmere Gate", "lat": 28.667449, "lon": 77.228249, "lines": ['Red', 'Yellow', 'Violet']},
    {"name": "Hauz Khas", "lat": 28.543813, "lon": 77.205876, "lines": ['Yellow', 'Magenta']},
    {"name": "Central Secretariat", "lat": 28.615879, "lon": 77.212282, "lines": ['Yellow', 'Violet']},
    {"name": "Mandi House", "lat": 28.625564, "lon": 77.234195, "lines": ['Blue', 'Violet']},
    {"name": "ITO", "lat": 28.628191, "lon": 77.241044, "lines": ['Blue', 'Violet']},
    {"name": "New Delhi", "lat": 28.642981, "lon": 77.222927, "lines": ['Yellow', 'Orange']},
    {"name": "Ashok Park Main", "lat": 28.671605, "lon": 77.155291, "lines": ['Green']},
    {"name": "Kirti Nagar", "lat": 28.655143, "lon": 77.151012, "lines": ['Blue', 'Green']},
    {"name": "Inderlok", "lat": 28.673148, "lon": 77.169767, "lines": ['Red', 'Green']},
    {"name": "Welcome", "lat": 28.672096, "lon": 77.277436, "lines": ['Red', 'Pink']},
    {"name": "Yamuna Bank", "lat": 28.623312, "lon": 77.268013, "lines": ['Blue']},
    {"name": "Anand Vihar", "lat": 28.646725, "lon": 77.315703, "lines": ['Blue', 'Pink']},
    {"name": "Azadpur", "lat": 28.706413, "lon": 77.181161, "lines": ['Yellow', 'Pink']},
    {"name": "Netaji Subhash Place", "lat": 28.695382, "lon": 77.153373, "lines": ['Red', 'Pink']},
    {"name": "Rajouri Garden", "lat": 28.650123, "lon": 77.12349, "lines": ['Blue', 'Pink']},
    {"name": "Lajpat Nagar", "lat": 28.570088, "lon": 77.237453, "lines": ['Violet', 'Pink']},
    {"name": "Kalkaji Mandir", "lat": 28.549915, "lon": 77.258017, "lines": ['Violet', 'Magenta']},
    {"name": "Janakpuri West", "lat": 28.629266, "lon": 77.078017, "lines": ['Blue', 'Magenta']},
    {"name": "Botanical Garden", "lat": 28.563924, "lon": 77.334118, "lines": ['Blue', 'Magenta']},
    {"name": "Mayur Vihar-I", "lat": 28.603853, "lon": 77.290236, "lines": ['Blue', 'Pink']},
    {"name": "Karkarduma", "lat": 28.64883, "lon": 77.305793, "lines": ['Blue', 'Pink']},
    {"name": "Dilli Haat - INA", "lat": 28.573915, "lon": 77.208444, "lines": ['Yellow', 'Pink']},
    {"name": "Sikanderpur", "lat": 28.481272, "lon": 77.093002, "lines": ['Yellow', 'Rapid']},
    {"name": "Dwarka Sector 21", "lat": 28.551922, "lon": 77.05856, "lines": ['Blue', 'Orange']},
    {"name": "Noida Sector 51", "lat": 28.585719, "lon": 77.375259, "lines": ['Aqua']},
    {"name": "Noida Sector 52", "lat": 28.586874, "lon": 77.373024, "lines": ['Blue']},
    {"name": "Samaypur Badli", "lat": 28.744641, "lon": 77.13827, "lines": ['Yellow']},
    {"name": "Millennium City Centre Gurugram", "lat": 28.459343, "lon": 77.072657, "lines": ['Yellow']},
    {"name": "Shaheed Sthal", "lat": 28.670645, "lon": 77.415474, "lines": ['Red']},
    {"name": "Rithala", "lat": 28.720806, "lon": 77.107181, "lines": ['Red']},
    {"name": "Noida Electronic City", "lat": 28.628263, "lon": 77.375003, "lines": ['Blue']},
    {"name": "Vaishali", "lat": 28.64967, "lon": 77.339575, "lines": ['Blue']},
    {"name": "Raja Nahar Singh", "lat": 28.340002, "lon": 77.316451, "lines": ['Violet']},
    {"name": "Maujpur-Babarpur", "lat": 28.692078, "lon": 77.279697, "lines": ['Pink']},
    {"name": "Majlis Park", "lat": 28.724403, "lon": 77.181841, "lines": ['Pink']},
    {"name": "Krishna Park Extension", "lat": 28.647792, "lon": 77.084343, "lines": ['Magenta']},
    {"name": "Dhansa Bus Stand", "lat": 28.611909, "lon": 76.978526, "lines": ['Grey']},
    {"name": "Brigadier Hoshiyar Singh", "lat": 28.69746, "lon": 76.919203, "lines": ['Green']},
    {"name": "Depot Station", "lat": 28.489014, "lon": 77.544009, "lines": ['Aqua']},
    {"name": "Sector 55-56", "lat": 28.423356, "lon": 77.105133, "lines": ['Rapid']},
    {"name": "Chandni Chowk", "lat": 28.658423, "lon": 77.230338, "lines": ['Yellow']},
    {"name": "Vishwa Vidyalaya", "lat": 28.695077, "lon": 77.214746, "lines": ['Yellow']},
    {"name": "Jahangirpuri", "lat": 28.725972, "lon": 77.162658, "lines": ['Yellow']},
    {"name": "Patel Chowk", "lat": 28.622966, "lon": 77.214031, "lines": ['Yellow']},
    {"name": "AIIMS", "lat": 28.56686, "lon": 77.207806, "lines": ['Yellow']},
    {"name": "Saket", "lat": 28.521168, "lon": 77.202224, "lines": ['Yellow']},
    {"name": "IFFCO Chowk", "lat": 28.472328, "lon": 77.072422, "lines": ['Yellow']},
    {"name": "Karol Bagh", "lat": 28.644012, "lon": 77.188524, "lines": ['Blue']},
    {"name": "Barakhamba Road", "lat": 28.629768, "lon": 77.225005, "lines": ['Blue']},
    {"name": "Laxmi Nagar", "lat": 28.630597, "lon": 77.277523, "lines": ['Blue']},
    {"name": "Noida Sector 18", "lat": 28.570758, "lon": 77.326076, "lines": ['Blue']},
    {"name": "Noida City Centre", "lat": 28.574733, "lon": 77.356164, "lines": ['Blue']},
    {"name": "Shahdara", "lat": 28.67343, "lon": 77.289886, "lines": ['Red']},
    {"name": "Govind Puri", "lat": 28.544552, "lon": 77.264276, "lines": ['Violet']},
    {"name": "Nehru Place", "lat": 28.551417, "lon": 77.251739, "lines": ['Violet']},
    {"name": "Sarai Kale Khan - Nizamuddin", "lat": 28.588749, "lon": 77.257249, "lines": ['Pink']},
    {"name": "South Extension", "lat": 28.568566, "lon": 77.220568, "lines": ['Pink']},
    {"name": "Delhi Cantt", "lat": 28.60862, "lon": 77.140419, "lines": ['Pink']},
    {"name": "IGI Airport", "lat": 28.556463, "lon": 77.086699, "lines": ['Orange']},
    {"name": "Munirka", "lat": 28.556897, "lon": 77.175059, "lines": ['Magenta']},
    {"name": "Cyber City", "lat": 28.49807, "lon": 77.089257, "lines": ['Rapid']},
]


def _km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Haversine km (same formula as exposure._haversine_m)."""
    return exposure._haversine_m((lon1, lat1), (lon2, lat2)) / 1000.0


def _line(lon1: float, lat1: float, lon2: float, lat2: float) -> dict:
    return {"type": "LineString", "coordinates": [[lon1, lat1], [lon2, lat2]]}


def nearest_station(lat: float, lon: float) -> tuple:
    """(name, lat, lon, dist_km) of the closest registry station."""
    best = min(STATIONS, key=lambda s: _km(lat, lon, s["lat"], s["lon"]))
    return (best["name"], best["lat"], best["lon"],
            round(_km(lat, lon, best["lat"], best["lon"]), 3))


def _walk_leg(flat: float, flon: float, tlat: float, tlon: float,
              field_value) -> dict:
    dist_km = _km(flat, flon, tlat, tlon)
    dur_s = dist_km / WALK_SPEED_KMH * 3600.0
    e = exposure.dose(_line(flon, flat, tlon, tlat), dur_s, "walking", field_value)
    return {"type": "walk", "from": [flat, flon], "to": [tlat, tlon],
            "distance_km": round(dist_km, 2),
            "duration_min": round(dur_s / 60, 1), "duration_s": round(dur_s),
            "dose_ug": e["dose_ug"], "exposure": e}


def _metro_leg(a: dict, b: dict, field_value) -> dict:
    crow_km = _km(a["lat"], a["lon"], b["lat"], b["lon"])
    route_km = crow_km * METRO_DETOUR
    ride_s = route_km / METRO_SPEED_KMH * 3600.0
    dur_s = ride_s + ACCESS_WAIT_MIN * 60.0
    e = exposure.dose(_line(a["lon"], a["lat"], b["lon"], b["lat"]),
                      dur_s, "metro", field_value)
    return {"type": "metro",
            "from": [a["lat"], a["lon"]], "to": [b["lat"], b["lon"]],
            "from_station": a["name"], "to_station": b["name"],
            "distance_km": round(route_km, 2),
            "duration_min": round(dur_s / 60, 1), "duration_s": round(dur_s),
            "dose_ug": e["dose_ug"], "exposure": e}


def metro_option(from_lat: float, from_lon: float, to_lat: float,
                 to_lon: float, field_value: Callable[[float, float], Optional[float]]
                 ) -> Optional[dict]:
    """One /compare-shaped option: walk -> metro -> walk.

    Returns None when either endpoint sits > MAX_ACCESS_KM from the
    nearest station — at that distance the honest answer is "the metro
    isn't for this trip", not a fake estimate.
    """
    if transit_real is not None:
        j = transit_real.metro_journey(from_lat, from_lon, to_lat, to_lon)
        if j is not None:
            return _option_from_gtfs(j, from_lat, from_lon,
                                     to_lat, to_lon, field_value)

    sa = nearest_station(from_lat, from_lon)
    sb = nearest_station(to_lat, to_lon)
    if sa[3] > MAX_ACCESS_KM or sb[3] > MAX_ACCESS_KM:
        return None

    sta = {"name": sa[0], "lat": sa[1], "lon": sa[2]}
    stb = {"name": sb[0], "lat": sb[1], "lon": sb[2]}

    walk_in = _walk_leg(from_lat, from_lon, sta["lat"], sta["lon"], field_value)
    ride = _metro_leg(sta, stb, field_value)
    walk_out = _walk_leg(stb["lat"], stb["lon"], to_lat, to_lon, field_value)
    legs = [walk_in, ride, walk_out]

    dose_parts = [l["dose_ug"] for l in legs]
    dose_ug = round(sum(d for d in dose_parts if d is not None), 1) \
        if any(d is not None for d in dose_parts) else None
    duration_s = sum(l["duration_s"] for l in legs)
    distance_km = round(sum(l["distance_km"] for l in legs), 1)

    coords = [[from_lon, from_lat]]
    for l in legs:
        coords.append([l["to"][1], l["to"][0]])

    confs = [l["exposure"]["confidence"] for l in legs]
    return {
        "vehicle": "metro",
        "label": "Metro + walk",
        "mode": "metro",
        "distance_km": distance_km,
        "duration_min": round(duration_s / 60),
        "duration_s": round(duration_s),
        "duration_model": "estimated",
        "geometry": {"type": "LineString", "coordinates": coords},
        "legs": legs,
        "stations": {"board": sta["name"], "alight": stb["name"],
                     "access_km": sa[3], "egress_km": sb[3]},
        "assumptions": {
            "metro_detour_factor": METRO_DETOUR,
            "metro_speed_kmh": METRO_SPEED_KMH,
            "access_wait_min": ACCESS_WAIT_MIN,
            "walk_speed_kmh": WALK_SPEED_KMH,
            "max_access_km": MAX_ACCESS_KM,
        },
        "exposure": {
            "dose_ug": dose_ug,
            "confidence": "low" if "low" in confs else
                          ("medium" if "medium" in confs else
                           ("high" if "high" in confs else "none")),
            "factors": {"microenv": "walk 1.3 / metro 0.45",
                        "ventilation_lpm": "walk 14 / metro 10",
                        "road_uplift": 1.0},
        },
    }


def _option_from_gtfs(j: dict, from_lat: float, from_lon: float,
                      to_lat: float, to_lon: float, field_value) -> dict:
    """Same option shape as the synthetic path, built on the real feed:
    GTFS station names/lines, real track geometry, stop_times-median
    ride minutes. `duration_model: "gtfs"` marks the upgrade."""
    walk_in = _walk_leg(from_lat, from_lon, j["board_lat"], j["board_lon"],
                        field_value)
    ride = {"type": "metro",
            "from": [j["board_lat"], j["board_lon"]],
            "to": [j["alight_lat"], j["alight_lon"]],
            "from_station": j["board"], "to_station": j["alight"],
            "lines": j["lines"], "transfers": j["transfers"],
            "via": j["via"], "stops": j["stops_ridden"],
            "distance_km": j["distance_km"],
            "duration_min": round(j["duration_s"] / 60, 1),
            "duration_s": round(j["duration_s"]),
            "geometry": j["geometry"]}
    ride["exposure"] = exposure.dose(j["geometry"], j["duration_s"],
                                   "metro", field_value)
    ride["dose_ug"] = ride["exposure"]["dose_ug"]
    walk_out = _walk_leg(j["alight_lat"], j["alight_lon"],
                         to_lat, to_lon, field_value)
    legs = [walk_in, ride, walk_out]

    dose_parts = [l["dose_ug"] for l in legs]
    dose_ug = round(sum(d for d in dose_parts if d is not None), 1) \
        if any(d is not None for d in dose_parts) else None
    duration_s = sum(l["duration_s"] for l in legs)
    distance_km = round(sum(l["distance_km"] for l in legs), 1)

    coords = [[from_lon, from_lat]]
    coords += [list(c) for c in ride["geometry"]["coordinates"]]
    coords.append([to_lon, to_lat])

    confs = [l["exposure"]["confidence"] for l in legs]
    return {
        "vehicle": "metro",
        "label": "Metro + walk",
        "mode": "metro",
        "distance_km": distance_km,
        "duration_min": round(duration_s / 60),
        "duration_s": round(duration_s),
        "duration_model": "gtfs",
        "geometry": {"type": "LineString", "coordinates": coords},
        "legs": legs,
        "stations": {"board": j["board"], "alight": j["alight"],
                     "access_km": j["access_km"], "egress_km": j["egress_km"],
                     "lines": j["lines"], "via": j["via"],
                     "transfers": j["transfers"],
                     "stops_ridden": j["stops_ridden"]},
        "assumptions": {
            "schedule_source": j["time_source"],
            "transfer_min": 6.0,
            "access_wait_min": 5.0,
            "walk_speed_kmh": WALK_SPEED_KMH,
            "max_access_km": MAX_ACCESS_KM,
        },
        "exposure": {
            "dose_ug": dose_ug,
            "confidence": "low" if "low" in confs else
                          ("medium" if "medium" in confs else
                           ("high" if "high" in confs else "none")),
            "factors": {"microenv": "walk 1.3 / metro 0.45",
                        "ventilation_lpm": "walk 14 / metro 10",
                        "road_uplift": 1.0},
        },
    }


def annotate_bus_hints(options: list, from_lat: float, from_lon: float,
                       to_lat: float, to_lon: float) -> None:
    """Attach real DTC/cluster bus-stop context to bus options — additive
    `transit` key, nothing existing changes."""
    if transit_real is None:
        return
    hint = transit_real.bus_hint(from_lat, from_lon, to_lat, to_lon)
    if not hint:
        return
    for o in options:
        if o.get("vehicle") == "bus":
            o["transit"] = hint
