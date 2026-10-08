"""alive_core runtime shim — the C++ engine where the extension loads,
the verified Python reference where it doesn't (docs/plan/08).

`ENGINE` is the serving label: /health reports it, so the API never
claims C++ while answering from Python. Every adapter here reproduces
its counterpart's exact contract — krige.py's sample coercion/merge and
estimate semantics — and the parity suite (tests/test_core_parity.py,
tests/test_parity_field.py) bit-checks C++ vs Python on the same inputs.
"""

import itertools
import math
from typing import Optional

import krige
import alive_core_ref

try:  # compiled extension — needs the eigen build for KrigeField
    import alive_core as _ac

    _CPP_KRIGE = hasattr(_ac, "KrigeField")
except Exception:  # no .so on this interpreter — Python serves
    _ac = None
    _CPP_KRIGE = False

# alive_core when the extension serves ANY hot path (FieldView/search/
# integrators aren't eigen-gated); krige separately reports per-adapter.
ENGINE = "alive_core" if _ac is not None else "python"


def field_view(src, coverage_km: float):
    """Snapshot field view — alive_core.FieldView when the extension
    loads, PyFieldView (identical semantics) otherwise. Wraps
    alive_core_ref.get_field_view; raises only what it raises."""
    return alive_core_ref.get_field_view(src, coverage_km, prefer_cpp=True)


_SEARCH_IDX = None
_SEARCH_PIDS: list = []
_SEARCH_ENTRIES: Optional[list] = None
_REV_CELLS: Optional[dict] = None
_REV_CELL = 0.002  # ~221 m lat / ~196 m lon at Delhi's latitude


def _search_entries() -> list:
    """The T1 entry list — built once, shared by the search index and
    the reverse-lookup grid so /v2/reverse rides the same universe."""
    global _SEARCH_IDX, _SEARCH_PIDS, _SEARCH_ENTRIES
    if _SEARCH_ENTRIES is None:
        _SEARCH_ENTRIES = alive_core_ref.entries_from_gazetteer()
        _SEARCH_PIDS = [e["pid"] for e in _SEARCH_ENTRIES]
        _SEARCH_IDX = alive_core_ref.get_search_index(
            _SEARCH_ENTRIES, prefer_cpp=True)
    return _SEARCH_ENTRIES


def search_index():
    """T1 place index over the gazetteer+corpus universe — the same
    sources v2/gazetteer resolves (first readable file of each wins, so
    an image shipping only data/corpus still builds). alive_core.
    SearchIndex when the extension loads, PySearchIndex (identical
    semantics) otherwise. Built once: ~45k entries, alias-expanded."""
    _search_entries()
    return _SEARCH_IDX


def _rev_grid() -> dict:
    global _REV_CELLS
    if _REV_CELLS is None:
        cells: dict = {}
        for i, e in enumerate(_search_entries()):
            key = (math.floor(e["lat"] / _REV_CELL),
                   math.floor(e["lon"] / _REV_CELL))
            cells.setdefault(key, []).append(i)
        _REV_CELLS = cells
    return _REV_CELLS


def nearest(lat, lon, max_m: float = 150.0, limit: int = 16):
    """Reverse lookup: entry rows within max_m of a point.

    Chebyshev ring scan over a lat/lon grid of the SAME entries T1
    searches — no second index, no second data file. Returns
    [(entry_dict, distance_m)] sorted by distance."""
    ents = _search_entries()
    cells = _rev_grid()
    bi, bj = math.floor(lat / _REV_CELL), math.floor(lon / _REV_CELL)
    found: list = []
    r = 0
    # ring r's points can't sit closer than (r-1) * the cell's short
    # axis (~196 m) — stop once a ring is entirely past max_m.
    while (r - 1) * 196.0 <= max_m:
        for di in range(-r, r + 1):
            for dj in range(-r, r + 1):
                if max(abs(di), abs(dj)) != r:
                    continue
                for i in cells.get((bi + di, bj + dj), ()):
                    e = ents[i]
                    d = 1000.0 * alive_core_ref.haversine_km(
                        lat, lon, e["lat"], e["lon"])
                    if d <= max_m:
                        found.append((d, i))
        r += 1
        if r > 45:  # ~8.8 km failsafe — reverse stays inside its max_m
            break
    found.sort()
    return [(ents[i], d) for d, i in found[:limit]]


# ---------------------------------------------------------------------------
# compound (kind + place) queries — "atm near cp", "school sector 62 noida"
# ---------------------------------------------------------------------------
# A name-token index can't answer "a KIND of thing near a PLACE": every
# token is name-text, so "school sector 62 noida" surfaces the wrong
# sector's schools. The compound layer detects the kind noun, resolves
# the remaining place phrase through the SAME index, and returns
# kind-filtered rows nearest the resolved anchor from the SAME grid that
# serves /v2/reverse. It fires only when the name path is weak (empty or
# partial coverage) — a query that already resolves as a full name
# ("school of planning", "metro station rajiv chowk") stays untouched.

# place-phrase fillers Delhi users actually type around the anchor
_COMPOUND_STOP = frozenset((
    "in", "near", "at", "around", "round", "opp", "opposite", "of",
    "the", "a", "an", "for", "to", "by", "from", "mein", "me", "ke",
    "ki", "ka", "paas", "pas", "wala", "wale", "wali", "se", "par",
    "pe", "andar", "bahar", "nazdeek", "najdeek", "kareeb", "karib",
    "close", "nearby", "side", "samne", "saamne", "peeche", "piche",
    "aage",
))

# "near me" style anchors — resolved to the caller's own lat/lon
_ME_TOKENS = frozenset(("me", "mere", "yahan", "here", "pas", "paas"))

# anchor kinds that mean 'a container place' — locality/sector/area —
# not one named POI. Under a strong name hit a compound may only ride
# a container anchor ('school sector 62 noida' anchors on Sector 62);
# a named-POI anchor means the whole query was a name. A locality also
# covers a wider sweep than a street: a sector's own rows sit at its
# edges, so the kind-scan radius loosens for these.
_AREA_KINDS = frozenset((
    "locality", "macrohood", "neighborhood", "neighbourhood", "suburb",
    "sector", "district", "subdistrict", "administrative", "place",
    "area", "block", "ward", "colony", "village", "hamlet", "town",
    "enclave", "extension", "residential", "quarter", "city",
    "borough", "municipality", "estate", "tehsil", "county",
    "gated_community", "housing",
))
_COMPOUND_AREA_MAX_M = 2600.0

# kind phrase -> cooked category set (entries_from_gazetteer kinds).
# Multi-word forms ("petrol pump", "metro station") win before their
# single tokens, so "bus stand" doesn't read as plain "bus" + leftover.
_KIND_PHRASES = {
    ("petrol", "pump"): ("fuel", "gas_station", "fueling_station"),
    ("gas", "station"): ("fuel", "gas_station", "fueling_station"),
    ("filling", "station"): ("fuel", "gas_station", "fueling_station"),
    ("charging", "station"): ("charging_station", "charge_point",
                             "ev_charging_station"),
    ("metro", "station"): ("metro", "station", "train_station",
                           "subway_entrance", "platform", "stop",
                           "public_transit_facility_or_service"),
    ("railway", "station"): ("train_station", "station",
                             "railway:station", "rail", "halt",
                             "platform", "rail_facility_or_service",
                             "public_transit_facility_or_service"),
    ("train", "station"): ("train_station", "station",
                           "railway:station", "rail", "halt", "platform",
                           "rail_facility_or_service",
                           "public_transit_facility_or_service"),
    ("rail", "station"): ("train_station", "station", "rail", "halt",
                         "rail_facility_or_service"),
    ("police", "station"): ("police", "policeoutpost", "police_station"),
    ("bus", "stop"): ("bus_stop", "platform", "stop", "stop_position",
                      "public_transport:platform", "amenity:bus_station",
                      "public_transit_facility_or_service"),
    ("bus", "stand"): ("bus_station", "bus_stop", "platform", "stop",
                      "amenity:bus_station",
                      "public_transit_facility_or_service",
                      "travel_and_transportation"),
    ("bus", "station"): ("bus_station", "bus_stop", "platform", "stop",
                        "amenity:bus_station",
                        "public_transit_facility_or_service",
                        "travel_and_transportation"),
    ("bus", "depot"): ("bus_station", "bus_depot", "bus_stop",
                      "amenity:bus_station", "depot", "platform", "stop",
                      "public_transit_facility_or_service",
                      "travel_and_transportation"),
    ("bus", "terminal"): ("bus_station", "bus_depot", "bus_stop",
                         "amenity:bus_station", "depot", "platform",
                         "public_transit_facility_or_service",
                         "travel_and_transportation"),
    ("bus", "terminus"): ("bus_station", "bus_depot", "amenity:bus_station",
                         "depot", "platform",
                         "public_transit_facility_or_service",
                         "travel_and_transportation"),
    ("depot",): ("bus_station", "bus_depot", "depot",
                "amenity:bus_station",
                "public_transit_facility_or_service"),
    ("terminus",): ("bus_station", "bus_depot", "depot",
                   "amenity:bus_station", "train_station",
                   "public_transit_facility_or_service"),
    ("isbt",): ("bus_station", "bus_stop", "platform",
               "amenity:bus_station",
               "public_transit_facility_or_service"),
    ("adda",): ("bus_station", "bus_stop", "amenity:bus_station",
               "public_transit_facility_or_service"),
    ("post", "office"): ("post_office", "post_depot", "post_box"),
    ("fire", "station"): ("fire_station",),
    ("guest", "house"): ("guest_house", "tourism:guest_house", "hostel",
                        "lodging", "bed_and_breakfast", "private_lodging"),
    ("ice", "cream"): ("ice_cream",),
    ("swimming", "pool"): ("swimming_pool", "swimming_area"),
    ("community", "centre"): ("community_centre", "social_centre",
                             "community_center", "civic_center"),
    ("community", "center"): ("community_centre", "social_centre",
                             "community_center", "civic_center"),
    ("movie", "theater"): ("cinema", "movie_theater"),
    ("nursing", "home"): ("hospital", "nursing_home",
                         "specialized_health_care",
                         "senior_living_facility"),
    ("medical", "store"): ("pharmacy", "chemist", "medical_supply",
                           "pharmacy_and_drug_store"),
    ("car", "wash"): ("car_wash",),
    ("shopping", "mall"): ("shopping_mall", "mall", "shop:mall",
                           "shopping_centre", "department_store",
                           "warehouse_club_store", "superstore"),
    ("taxi", "stand"): ("taxi",),
    ("petrol",): ("fuel", "gas_station", "fueling_station"),
    ("sports", "complex"): ("stadium_arena", "stadium", "sports_centre",
                           "sport_or_fitness_facility",
                           "sports_and_recreation",
                           "sport_or_recreation_club", "sport_court",
                           "sport_field", "fitness_studio"),
    ("sports", "centre"): ("sports_centre", "stadium_arena",
                          "sport_or_fitness_facility",
                          "sports_and_recreation",
                          "sport_or_recreation_club", "sport_court",
                          "sport_field", "fitness_studio"),
    ("golf", "course"): ("golf_course",),
    ("atm",): ("atm",),
    ("bank",): ("bank", "bank_or_credit_union", "financial_service"),
    ("hospital",): ("hospital", "specialty_hospital", "nursing_home",
                   "amenity:hospital", "specialized_health_care",
                   "health_care", "medical_service",
                   "specialized_medical_facility",
                   "emergency_or_urgent_care_facility",
                   "emergency_department",
                   "primary_care_or_general_clinic", "walk_in_clinic"),
    ("aspatal",): ("hospital",),
    ("clinic",): ("clinic", "dental_clinic", "outpatient_care_facility",
                  "vision_or_eye_care_clinic", "healthcare",
                  "specialized_health_care", "health_care",
                  "medical_service", "primary_care_or_general_clinic",
                  "walk_in_clinic", "pediatric_clinic",
                  "behavioral_or_mental_health_clinic",
                  "physical_medicine_and_rehabilitation",
                  "complementary_and_alternative_medicine",
                  "diagnostics_imaging_or_lab_service",
                  "reproductive_perinatal_and_womens_care", "surgery",
                  "specialized_medical_facility"),
    ("doctor",): ("doctors", "doctor", "clinic",
                  "specialized_health_care", "health_care",
                  "medical_service", "primary_care_or_general_clinic",
                  "complementary_and_alternative_medicine"),
    ("dentist",): ("dentist", "dental_clinic"),
    ("pharmacy",): ("pharmacy", "chemist", "medical_supply",
                    "pharmacy_and_drug_store"),
    ("chemist",): ("pharmacy", "chemist", "pharmacy_and_drug_store"),
    ("school",): ("school", "prep_school", "kindergarten",
                  "educational_institution", "language_school",
                  "music_school", "driving_school", "dancing_school",
                  "specialty_school", "amenity:school",
                  "building:school", "place_of_learning", "preschool",
                  "elementary_school", "middle_school", "high_school",
                  "education", "educational_service",
                  "educational_facility", "tutoring_service",
                  "academy"),
    ("college",): ("college", "college_university",
                   "educational_institution", "amenity:college",
                   "building:college", "place_of_learning",
                   "educational_facility", "academy",
                   "educational_service"),
    ("university",): ("university", "college_university",
                      "educational_institution", "amenity:university",
                      "building:university", "place_of_learning",
                      "educational_facility", "academy"),
    ("metro",): ("metro", "subway", "subway_entrance",
                 "public_transit_facility_or_service"),
    ("station",): ("station", "train_station", "metro",
                   "railway:station", "halt",
                   "rail_facility_or_service",
                   "public_transit_facility_or_service"),
    ("airport",): ("airport", "aerodrome", "terminal", "helipad",
                   "heliport", "air_transport_facility_or_service"),
    ("police",): ("police", "policeoutpost", "police_station"),
    ("thana",): ("police", "policeoutpost"),
    ("parking",): ("parking", "parking_space", "parking_entrance",
                  "motorcycle_parking", "bicycle_parking"),
    ("restaurant",): ("restaurant", "fast_food", "food_court",
                      "canteen", "casual_eatery",
                      "fast_food_restaurant", "food_service",
                      "food_and_drink", "food_truck_stand"),
    ("dhaba",): ("restaurant", "fast_food", "casual_eatery"),
    ("hotel",): ("hotel", "guest_house", "hostel", "motel", "resort",
                 "tourism:hotel", "tourism:guest_house", "lodging",
                 "bed_and_breakfast", "private_lodging", "inn"),
    ("hostel",): ("hostel", "dormitory", "student_accommodation",
                  "student_accomodation", "lodging", "private_lodging"),
    ("dharamshala",): ("guest_house", "hostel", "lodging"),
    ("cafe",): ("cafe", "coffee", "internet_cafe", "coffee_shop",
                "smoothie_juice_bar", "non_alcoholic_beverage_venue"),
    ("cinema",): ("cinema", "theatre", "movie_theater"),
    ("movie",): ("cinema", "theatre", "movie_theater"),
    ("multiplex",): ("cinema", "movie_theater"),
    ("theatre",): ("theatre", "cinema", "arts_centre",
                  "movie_theater", "theatre_venue",
                  "performing_arts_venue"),
    ("park",): ("park", "garden", "playground", "recreation_ground",
                "dog_park", "leisure:park", "national_park",
                "nature_reserve", "sport_field"),
    ("playground",): ("playground", "pitch", "park"),
    ("gym",): ("gym", "fitness_centre", "sports_centre",
               "fitness_station", "leisure:fitness_centre",
               "leisure:sports_centre", "sport_or_fitness_facility",
               "fitness_studio", "sports_and_recreation"),
    ("gymnasium",): ("gym", "fitness_centre", "sport_or_fitness_facility",
                    "fitness_studio"),
    ("stadium",): ("stadium_arena", "stadium", "sports_centre",
                   "leisure:stadium", "sport_or_fitness_facility",
                   "sport_court", "sport_field",
                   "sports_and_recreation"),
    ("library",): ("library", "public_bookcase"),
    ("market",): ("marketplace", "market", "greengrocer",
                  "farmers_market"),
    ("mandi",): ("marketplace", "market", "greengrocer"),
    ("bazaar",): ("marketplace", "market", "convenience",
                  "farmers_market"),
    ("mall",): ("shopping_mall", "mall", "shop:mall", "shopping_centre",
                "department_store", "warehouse_club_store", "superstore"),
    ("shop",): ("shop", "convenience", "supermarket", "store",
                "variety_store", "general", "retail",
                "convenience_store", "specialty_store", "shopping",
                "discount_store", "second_hand_store"),
    ("store",): ("store", "shop", "convenience", "supermarket",
                 "variety_store", "general", "convenience_store",
                 "specialty_store", "shopping", "discount_store"),
    ("grocery",): ("supermarket", "convenience", "grocery",
                   "greengrocer", "shop:supermarket",
                   "shop:convenience", "food_and_beverage_store",
                   "convenience_store", "warehouse_club_store"),
    ("kirana",): ("convenience", "grocery", "general", "supermarket",
                  "convenience_store", "food_and_beverage_store"),
    ("supermarket",): ("supermarket", "shop:supermarket", "convenience",
                      "food_and_beverage_store", "convenience_store",
                      "warehouse_club_store", "superstore"),
    ("gymkhana",): ("club", "sports_centre", "sport_or_recreation_club"),
    ("club",): ("club", "social_club", "sports_centre",
                "sport_or_recreation_club"),
    ("temple",): ("temple", "hindu_place_of_worship", "place_of_worship",
                  "building:temple", "amenity:place_of_worship",
                  "shrine", "wayside_shrine"),
    ("mandir",): ("temple", "hindu_place_of_worship", "place_of_worship",
                  "building:temple", "amenity:place_of_worship",
                  "shrine", "wayside_shrine"),
    ("mosque",): ("mosque", "muslim_place_of_worship",
                  "place_of_worship"),
    ("masjid",): ("mosque", "muslim_place_of_worship",
                  "place_of_worship"),
    ("church",): ("church", "christian_place_of_worship",
                  "place_of_worship"),
    ("gurudwara",): ("place_of_worship", "amenity:place_of_worship"),
    ("gurdwara",): ("place_of_worship", "amenity:place_of_worship"),
    ("bar",): ("bar", "pub", "nightclub", "lounge",
               "alcoholic_beverage_venue", "dance_club",
               "nightlife_venue", "brewery", "distillery", "winery"),
    ("pub",): ("pub", "bar", "nightclub", "alcoholic_beverage_venue",
               "dance_club", "nightlife_venue", "brewery"),
    ("theka",): ("bar", "pub", "alcohol", "wine",
                "alcoholic_beverage_venue"),
    ("bakery",): ("bakery", "pastry", "confectionery"),
    ("sweets",): ("sweets", "confectionery", "pastry", "sweet",
                  "sweets_shop"),
    ("mithai",): ("sweets", "confectionery", "sweet"),
    ("court",): ("courthouse",),
    ("kachahri",): ("courthouse",),
    ("vet",): ("veterinary", "animal_or_pet_service"),
    ("veterinary",): ("veterinary", "animal_or_pet_service"),
    ("taxi",): ("taxi",),
    ("cab",): ("taxi",),
    ("graveyard",): ("grave_yard", "cemetery"),
    ("cemetery",): ("cemetery", "grave_yard"),
    ("smashan",): ("crematorium", "cemetery"),
    ("salon",): ("hairdresser", "beauty", "personal_or_beauty_service",
                 "personal_care_and_beauty_store"),
    ("parlour",): ("beauty", "hairdresser", "personal_or_beauty_service",
                   "personal_care_and_beauty_store"),
    ("parlor",): ("beauty", "hairdresser", "personal_or_beauty_service",
                  "personal_care_and_beauty_store"),
    ("barber",): ("hairdresser", "personal_or_beauty_service"),
    ("tailor",): ("tailor",),
    ("electrician",): ("electrician", "home_service"),
    ("plumber",): ("plumber", "home_service"),
    ("gym", "wear"): ("gym_wear",),
    ("pet", "shop"): ("pet", "animal_and_pet_store",
                     "animal_or_pet_service"),
    ("computer",): ("computer", "electronics", "electronics_repair",
                    "electronics_store", "telecommunications_service"),
    ("mobile", "shop"): ("mobile_phone", "mobile_phone_accessories",
                        "electronics_store",
                        "telecommunications_service"),
}

# kinds compound hits rank by anchor distance within this radius
_COMPOUND_MAX_M = 1500.0

# sub-place designators — "block", "pocket", "sector" mark the query
# as <unit> inside <place>; the anchor is the place, the designator +
# its letter/number become the display-token requirement inside it
_SUBPLACE_STRUCT = frozenset((
    "block", "pocket", "phase", "part", "khand", "sector", "gali",
    "poket", "pkt", "mkt", "mktg",
    # Greater Noida names its sectors after Greek letters — 'beta 2',
    # 'alpha 1', 'delta 3' are unit names, not name+number
    "alpha", "beta", "gamma", "delta", "eta", "zeta", "theta",
    "iota", "kappa", "lambda", "mu", "nu", "omicron", "pi", "rho",
    "sigma", "tau", "upsilon", "phi", "chi", "psi", "omega", "xa",
    "xb", "xc", "xu", "xt", "parthala",
))
# struct words that live inside the place name itself ("Sector 62") —
# usable for tokenizing the anchor, never required of sub-rows
_WANT_DROP = frozenset(("sector", "phase", "part", "extension"))
# address filler that never disambiguates the sub-row
_DESIG_FILLER = frozenset((
    "no", "hno", "house", "number", "num", "unit", "gf", "ff",
    "floor", "kothi", "near", "flat", "plot", "bungalow",
))


def _comp_row(e, d, anchor, match="category", **extra):
    row = {
        "id": e["pid"],
        "display": e["display"],
        "category": e.get("category") or "",
        # '<kind> · <anchor>' — the resolved place stays visible next to
        # the unit row ('address · Defence Colony')
        "subtitle": f"{e.get('category') or 'place'}"
                    f" · {anchor['display']}",
        "lat": e["lat"], "lon": e["lon"],
        # distance to the resolved anchor — the honest semantic for
        # "atm near cp", not distance to the caller
        "distance_m": round(d, 1),
        "anchor": anchor["display"],
        "compound": True,
        # cov=None: these rows aren't token matches; match_rank set
        # so _merge orders them as a real answer tier, not noise
        "score": max(0.0, 3.0 - d / 1000.0),
        "cov": None, "fuzzy": False,
        "match": match, "match_rank": 1,
    }
    row.update(extra)
    return row


def _tok_wanted(etoks, t):
    """does the sub-row's token set satisfy want-token t: exact for
    words/digits; a lone letter also matches letter+digits (H-3, B7)."""
    if t in etoks:
        return True
    if len(t) == 1 and t.isalpha():
        return any(x.startswith(t) and x[1:].isdigit() for x in etoks)
    return False


def _unit_atom(t):
    """letters, digits and designator words — the pieces a unit name
    is built from ('b', '7', 'gali', 'beta'); ordinary words break
    the run."""
    return t.isdigit() or (len(t) == 1 and t.isalpha()) \
        or t in _SUBPLACE_STRUCT


def _unit_pairs(base, want):
    """adjacent atom pairs on the unit side of the query — 'b 7' is
    one unit ('B-7'), not a 'b' from one unit and a '7' from another.
    computed on `base` so a used anchor token between them can never
    fuse a fake pair."""
    wantset = set(want)
    return {(a, b) for a, b in itertools.pairwise(base)
            if a in wantset and b in wantset
            and _unit_atom(a) and _unit_atom(b)}


def _unit_pairs_hold(dseq, etoks, pairs):
    """every query pair must survive in the hit — adjacent in either
    order after the same filler-strip, or fused ('b7', '7b').
    'B-16 Gali Number 7' fails 'b 7': its pairs are (b,16)+(gali,7)."""
    adj = set(itertools.pairwise(dseq))
    for a, b in pairs:
        if ((a, b) in adj or (b, a) in adj
                or f"{a}{b}" in etoks or f"{b}{a}" in etoks):
            continue
        return False
    return True


def _anchor_candidates(toks, lat, lon, k=6):
    """every plausible anchor, not just the top-1 — 'udyog vihar' is a
    Delhi locality AND the Gurgaon phases the user usually means; the
    first candidate whose area actually contains the unit wins."""
    return [h for h in search_index().query(" ".join(toks), lat, lon, k)
            if (h.get("cov") or 0.0) >= 0.75]


def _area_row(anchor):
    """the resolved place itself as the honest area-level answer —
    'E Block' may be missing from OSM, but the locality the user named
    is still the truth, and beats a same-named block in a wrong colony."""
    pid = anchor.get("id")
    if isinstance(pid, int) and 0 <= pid < len(_SEARCH_PIDS):
        pid = _SEARCH_PIDS[pid]
    return {
        "id": pid,
        "display": anchor["display"],
        "category": anchor.get("category") or "",
        "subtitle": anchor.get("category") or "place",
        "lat": anchor["lat"], "lon": anchor["lon"],
        "distance_m": 0.0,
        "anchor": anchor["display"],
        "compound": True,
        "score": 2.2,
        "cov": None, "fuzzy": False,
        "match": "area", "match_rank": 1,
        "subplace": True, "locality": True,
    }


# digits following these tokens name the PLACE ('sector 62',
# 'phase 2') — they anchor the query. Digits after pocket/block/gali/
# a Greek letter name the UNIT ('pocket 4', 'a block', 'beta 2') and
# stay want-side
_UNIT_AFTER = frozenset(("sector", "phase", "part"))

# a name-path hit that already declares the whole unit ('Beta 2',
# 'Pocket 4') is a correct answer when it sits inside the anchor's
# urban area — sectors inside a city can be km from its centroid
_SUBPLACE_HIT_MAX_M = 6000.0

# address-surface vocab — a leftover name built only of these isn't a
# place ('B-12 residential'); a leftover that resolves to another
# locality ('B-12 Sanwal Nagar' on a Lajpat Nagar query) is a unit in
# the WRONG colony, never an answer
_PLACE_NEUTRAL = frozenset((
    "road", "street", "marg", "block", "pocket", "sector", "phase",
    "part", "extension", "enclave", "colony", "nagar", "vihar", "pur",
    "puram", "gunj", "ganj", "bagh", "place", "market", "gali",
    "park", "garden", "gardens", "residential", "new", "old", "west",
    "east", "north", "south", "central", "town", "city", "village",
    "apartment", "apartments", "building", "flat", "flats", "plot",
    "house", "kothi", "no", "number", "near", "opp", "opposite"))

_FOREIGN_Q_CACHE: dict = {}


def _foreign_place(anchor, leftover):
    """do the row's leftover tokens name a different colony? 'B-12
    Sanwal Nagar' — {sanwal, nagar} resolves to Sanwal Nagar, which
    carries none of the anchor's distinctive tokens → wrong
    neighbourhood. 'B-12 Lajpat Nagar IV' keeps {lajpat} → in-area."""
    name_toks = frozenset(t for t in leftover if t.isalpha())
    if not name_toks or name_toks <= _PLACE_NEUTRAL:
        return False
    if len(name_toks) == 1 and len(next(iter(name_toks))) <= 2:
        return False  # a stray letter/suffix isn't a place name
    atoks = set(alive_core_ref.normalize(anchor.get("display") or ""))
    distinctive = {t for t in atoks
                   if t not in _PLACE_NEUTRAL and not t.isdigit()
                   and len(t) > 1}
    if not distinctive:
        return False
    cands = _FOREIGN_Q_CACHE.get(name_toks)
    if cands is None:
        cands = search_index().query(
            " ".join(sorted(name_toks)), None, None, 3)
        if len(_FOREIGN_Q_CACHE) > 512:
            _FOREIGN_Q_CACHE.clear()
        _FOREIGN_Q_CACHE[name_toks] = cands
    return any((c.get("cov") or 0.0) >= 0.75
               and distinctive - set(alive_core_ref.normalize(
                   c.get("display") or ""))
               for c in cands or [])


def _hav_m(lat1, lon1, lat2, lon2):
    return 1000.0 * alive_core_ref.haversine_km(lat1, lon1, lat2, lon2)


def _anchor_extent(anchor):
    """how spread out the anchor's own namesake rows are — 'Greater
    Noida' rows scatter km across the city, 'Sarita Vihar X' rows
    cluster inside one colony. p80 distance of rows whose display
    carries the anchor's whole name."""
    atoks = set(alive_core_ref.normalize(anchor.get("display") or ""))
    if not atoks:
        return 0.0
    ds = sorted(
        d for e, d in nearest(anchor["lat"], anchor["lon"],
                              max_m=_SUBPLACE_HIT_MAX_M, limit=4096)
        if atoks <= set(
            alive_core_ref.normalize(e.get("display") or "")))
    return ds[int(len(ds) * 0.8)] if len(ds) >= 3 else 0.0


def _unit_leading(rows, want):
    """rows whose display LEADS with the asked unit atoms — 'Beta 2'
    counts for 'beta 2 …', 'Sector Beta 2, Greater Noida' does not.
    Under a strong name hit only a unit-leading row may displace it:
    the user typed the unit verbatim, so the answer leads with it."""
    lead = " ".join(want)
    pref = lead + " "
    out = []
    for r in rows:
        dn = " ".join(alive_core_ref.normalize(r.get("display") or ""))
        if dn == lead or dn.startswith(pref):
            out.append(r)
    return out


def _subplace(toks, lat, lon, limit, hits=None, strict=False):
    """'<letter/number> <designator> <place>' — 'pocket b sarita
    vihar', 'h block sector 62 noida', 'a 43 defence colony'. The place
    phrase resolves as the anchor; a row inside its radius whose
    display carries the remaining unit tokens is the sub-place the
    user meant. When the anchor's own display already carries them
    ('Beta 2' for 'beta 2 greater noida') the anchor is the answer.
    When nothing declares them, the locality is the honest answer —
    never a same-numbered unit in a different colony.

    `strict` = the name path already answered strongly; then only a
    unit-LEADING row may displace it ('Beta 2' not 'Sector Beta 2,
    Greater Noida' — a lodging POI that merely contains the atoms) and
    there is no bare area fallback — the name hits stand."""
    base = [t for t in toks
            if t not in _COMPOUND_STOP and t not in _DESIG_FILLER]
    struct = [t for t in base if t in _SUBPLACE_STRUCT]
    letters = [t for t in base if len(t) == 1 and t.isalpha()]
    digits = [t for t in base if t.isdigit()]
    # 'a block janakpuri' — 'a' is filler, but in front of a struct
    # word it IS the block's letter
    for i, t in enumerate(toks[:-1]):
        if t in ("a", "an") and toks[i + 1] in _SUBPLACE_STRUCT:
            letters.append(t)
            break
    if not (struct or letters or digits):
        return []
    # anchor = word tokens + digits that name the place ('sector 62');
    # letters and unit digits ('a 43', 'pocket b') stay want-side
    anchor_digits = set()
    for i, t in enumerate(toks):
        if t.isdigit() and i > 0 and toks[i - 1] in _UNIT_AFTER:
            anchor_digits.add(t)
    anchor_toks = [t for t in base
                   if t not in _SUBPLACE_STRUCT and t not in letters
                   and (not t.isdigit() or t in anchor_digits)]
    anchors, used = None, None
    # full phrase → minus anchor digits → trailing-context shrink:
    # 'ashok nagar shahdara gali 4' anchors on 'ashok nagar', the
    # shahdara token was context the user glued on
    variants = [
        anchor_toks,
        [t for t in anchor_toks if not t.isdigit()],
    ] + [anchor_toks[:c] for c in range(len(anchor_toks) - 1, 1, -1)]
    for qt in variants:
        if not qt:
            continue
        cands = _anchor_candidates(qt, lat, lon)
        if cands:
            anchors, used = cands, set(qt)
            break
    if not anchors:
        return []

    atoks0 = set(
        alive_core_ref.normalize(anchors[0].get("display") or ""))
    used0 = {t for t in used
             if not ((len(t) == 1 and t.isalpha()) or t.isdigit())
             or t in atoks0}
    if not [t for t in base
            if t not in used0 and t not in _WANT_DROP]:
        return []  # pure place query — the name path's hits stand

    def resolve(anchor):
        # a letter/digit counts as consumed only if the anchor's own
        # display carries it — 'beta' in 'HDFC Beta Plaza' doesn't make
        # the bank the answer to 'beta 2'
        atoks = set(
            alive_core_ref.normalize(anchor.get("display") or ""))
        used_a = {t for t in used
                  if not ((len(t) == 1 and t.isalpha()) or t.isdigit())
                  or t in atoks}
        want = [t for t in base
                if t not in used_a and t not in _WANT_DROP]
        if not want:
            return []
        pairs = _unit_pairs(base, want)
        if all(_tok_wanted(atoks, t) for t in want):
            aseq = [t for t in alive_core_ref.normalize(
                anchor.get("display") or "") if t not in _DESIG_FILLER]
            if _unit_pairs_hold(aseq, atoks, pairs):
                return [_area_row(anchor)]  # the anchor IS the sub-place
        # 'inside the named place' — a locality's pockets sit close, a
        # city's sectors sit km out; scale the membership radius to the
        # anchor's measured extent, never beyond the metro ceiling. A
        # locality/area anchor's floor is the wider sweep — a sector's
        # own rows sit at its edges
        floor = (_COMPOUND_AREA_MAX_M
                 if (anchor.get("category") or "") in _AREA_KINDS
                 else _COMPOUND_MAX_M)
        radius = min(_SUBPLACE_HIT_MAX_M,
                     max(floor, _anchor_extent(anchor) * 1.5))
        # a name-path row that already carries the unit and sits inside
        # the anchor's urban area IS the real sub-place — promote it
        # ahead of same-named units elsewhere ('Pocket B' in Jasola
        # fails for 'pocket b sarita vihar'; 'Beta 2' inside Greater
        # Noida passes)
        cand = []
        for h in hits or []:
            hseq = [t for t in alive_core_ref.normalize(
                h.get("display") or "") if t not in _DESIG_FILLER]
            ht = set(hseq)
            if not all(_tok_wanted(ht, t) for t in want):
                continue
            # same unit atoms, same pairing — a scattered cover
            # ('B-16' + 'Gali 7' for 'b 7') is a different unit
            if not _unit_pairs_hold(hseq, ht, pairs):
                continue
            if _foreign_place(
                    anchor,
                    {t for t in ht if t.isalpha() and t not in want}):
                h["_foreign"] = True  # wrong colony at ANY distance
                continue
            if h.get("lat") is None:
                continue
            d = _hav_m(anchor["lat"], anchor["lon"],
                       h["lat"], h["lon"])
            if d > radius:
                continue
            hid = h.get("id")
            pid = (_SEARCH_PIDS[hid]
                   if isinstance(hid, int)
                   and 0 <= hid < len(_SEARCH_PIDS)
                   else hid)
            cand.append(_comp_row(
                {"pid": pid, "display": h["display"],
                 "category": h.get("category"), "lat": h["lat"],
                 "lon": h["lon"]}, d, anchor, match="area",
                subplace=True))
            if len(cand) >= limit:
                break
        if strict:
            cand = _unit_leading(cand, want)
        if cand:
            return cand
        out = []
        for e, d in nearest(anchor["lat"], anchor["lon"],
                            max_m=radius, limit=4096):
            eseq = [t for t in alive_core_ref.normalize(
                e.get("display") or "") if t not in _DESIG_FILLER]
            etoks = set(eseq)
            if not all(_tok_wanted(etoks, t) for t in want):
                continue
            if not _unit_pairs_hold(eseq, etoks, pairs):
                continue
            # a row that declares a DIFFERENT sector number than the
            # anchored one is a wrong answer ('h block sector 62' can't
            # land on 'H Block Market-Sector 22')
            if (anchor_digits and "sector" in etoks
                    and not (anchor_digits & etoks)):
                continue
            if _foreign_place(
                    anchor,
                    {t for t in etoks if t.isalpha() and t not in want}):
                continue
            out.append(_comp_row(e, d, anchor, match="area",
                                 subplace=True))
            if len(out) >= limit:
                break
        if strict:
            out = _unit_leading(out, want)
        return out

    # first anchor whose area actually holds the unit wins; when no
    # candidate does, the top anchor itself is the honest area answer.
    # 3 candidates max — each resolve() is a spatial scan, and deeper
    # ambiguity is a wrong anchor more often than a hidden right one.
    # Under a strong name hit there is no area fallback: the name
    # answer stands ('beta 2' keeps 'Beta 2', not a random sector row)
    rows = []
    for anchor in anchors[:3]:
        rows = resolve(anchor)
        if rows:
            break
    return rows or ([] if strict else [_area_row(anchors[0])])


def _compound(q, weak: bool, lat, lon, limit, hits=None):
    """kind+place compound rows, or [] when nothing honest resolves.

    `weak` = the plain name-match came back empty or partial; then the
    query freely re-reads as kind + anchor. A strong name hit narrows
    the reading: compound still fires, but only when the anchor is a
    CONTAINER (locality/sector/area-kind) or the caller's own position
    — 'school sector 62 noida' anchors on Sector 62 and its schools
    lead; 'school of planning and architecture' anchors on a named
    building, the name answer stands."""
    strict = not weak
    toks = alive_core_ref.normalize(q)
    if len(toks) < 2:
        return []
    kinds = None
    kspan = None
    for n in (2, 1):
        for i in range(len(toks) - n + 1):
            ks = _KIND_PHRASES.get(tuple(toks[i:i + n]))
            if ks:
                kinds, kspan = ks, (i, i + n)
                break
        if kinds:
            break
    if kinds is None:
        # no kind noun — maybe a sub-place unit (block/pocket/house no.)
        # inside a named place
        return _subplace(toks, lat, lon, limit, hits, strict=strict)
    rest = [t for j, t in enumerate(toks)
            if not (kspan[0] <= j < kspan[1])]
    kind_words = set(toks[kspan[0]:kspan[1]])
    anchor = None
    # "atm near me" — every non-kind token is filler or the me-marker
    if (rest and any(t in _ME_TOKENS for t in rest)
            and all(t in _ME_TOKENS or t in _COMPOUND_STOP
                    for t in rest)):
        if lat is None or lon is None:
            return []
        anchor = {"display": "your location", "lat": float(lat),
                  "lon": float(lon)}
    else:
        # the anchor phrase is what follows the LAST near-class marker —
        # a name qualifier on the left ('pawan bakery near …') is part of
        # the ask, not the anchor. Without the split 'pawan' glues to
        # 'hanuman mandir' and coverage dies below the 0.75 floor.
        stop_i = -1
        for i, t in enumerate(rest):
            if t in _COMPOUND_STOP:
                stop_i = i
        right = [t for t in rest[stop_i + 1:] if t not in _COMPOUND_STOP]
        place_toks = right or [t for t in rest
                               if t not in _COMPOUND_STOP]
        if not place_toks:
            return []
        anchor = None
        # shrink from the right — a trailing context token the user
        # glued on ('ashok nagar shahdara …') must not kill the anchor
        for cut in range(len(place_toks), 0, -1):
            qt = place_toks[:cut]
            ah = search_index().query(" ".join(qt), lat, lon, 1)
            if ah and (ah[0].get("cov") or 0.0) >= 0.75:
                anchor = ah[0]
                break
        if anchor is None:
            return []

    # a strong name hit narrows the reading: the compound only rides a
    # container anchor (or the caller's own position) — a named-POI
    # anchor means the whole query was a name, not a kind ask
    if strict and anchor.get("display") != "your location" \
            and (anchor.get("category") or "") not in _AREA_KINDS:
        return []

    out = []
    # scan deep enough that dense localities can't starve a rarer kind —
    # Dwarka alone has ~1k rows inside the radius. A locality anchor
    # sweeps wider than a street — the sector's own rows sit at its
    # edges ('pappu bakery' ~2 km out still answers 'bakery shahdara')
    max_m = (_COMPOUND_AREA_MAX_M
             if (anchor.get("category") or "") in _AREA_KINDS
             else _COMPOUND_MAX_M)
    for e, d in nearest(anchor["lat"], anchor["lon"],
                        max_m=max_m, limit=4096):
        # kind match is corpus-kind OR, for a single-word kind, a display
        # token equal to the kind word — "The indian gym" carries kind
        # 'named', not a gym code, but its own name honestly declares it.
        # multi-word kinds require the whole phrase ("office" alone is
        # not a post office)
        if e.get("category") not in kinds:
            etoks = set(alive_core_ref.normalize(e.get("display") or ""))
            if len(kind_words) > 1:
                ok = kind_words <= etoks
            else:
                ok = bool(kind_words & etoks)
            if not ok:
                continue
        out.append(_comp_row(e, d, anchor))
        if len(out) >= limit:
            break
    if out:
        return out
    # kind path found nothing in the radius — the query may still carry
    # a sub-place shape ("school block h sector 62")
    return _subplace(toks, lat, lon, limit, hits, strict=strict)


# transit accessories named after a landmark ('AIIMS' platform,
# 'Lodhi Garden' bus bay) must not outrank the landmark they serve —
# 'aiims' means the hospital, 'lodhi garden' the park
_ACCESSORY_KINDS = frozenset((
    "platform", "stop", "stop_position", "bus_stop",
    "subway_entrance", "railway:platform", "railway:stop",
    "public_transport:platform", "public_transport:stop_position"))

_MATCH_NAMES = {0: "exact-prefix", 1: "token-prefix"}


_AL_MAP = None


def _alias_map():
    global _AL_MAP
    if _AL_MAP is None:
        _AL_MAP = alive_core_ref.load_aliases()
    return _AL_MAP


def _name_toks(h):
    """display + entry-alias tokens + one-level table expansion ('aiims'
    reaches 'all india institute of medical sciences'),
    singular-collapsed ('lodi gardens' ~ 'lodhi garden')."""
    src = [h.get("display") or ""]
    hid = h.get("id")
    if isinstance(hid, int) and 0 <= hid < len(_SEARCH_ENTRIES):
        src.extend(_SEARCH_ENTRIES[hid].get("aliases") or [])
    toks = set()
    for s in src:
        toks.update(alive_core_ref.normalize(s))
    for t in list(toks):
        for alt in _alias_map().get(t, ()):
            toks.update(alt)
    return {t[:-1] if len(t) > 3 and t.endswith("s") else t
            for t in toks}


def _tok_close(a, b):
    """name sets relate through a one-token transliteration wobble —
    'lodhi' ~ 'lodi' — when the alias table didn't already fold them."""
    xa, xb = a - b, b - a
    if not xa and not xb:
        return True
    if len(xa) > 1 or len(xb) > 1:
        return False
    return all(abs(len(x) - len(y)) <= 2
               and alive_core_ref.dl_distance(x, y, 2) <= 2
               for x in xa for y in xb)


def _demote_accessory(hits, qn=""):
    """accessory rows serving a landmark drop below it — and the
    landmark inherits the accessory's query-match class, because
    'AIIMS' platform's literal-name match is really the hospital's
    intent (the downstream merger re-ranks on match class and would
    otherwise put the platform back on top)."""
    if not hits or not any((h.get("category") or "") in _ACCESSORY_KINDS
                           for h in hits):
        return hits
    land = [(i, _name_toks(h)) for i, h in enumerate(hits)
            if (h.get("category") or "") not in _ACCESSORY_KINDS]
    land = [(i, lt) for i, lt in land if lt]
    keep, acc = [], []
    for h in hits:
        at = _name_toks(h)
        rel = [i for i, lt in land
               if at and (at <= lt or lt <= at or _tok_close(at, lt))]
        if (h.get("category") or "") in _ACCESSORY_KINDS and rel:
            dn = " ".join(
                alive_core_ref.normalize(h.get("display") or ""))
            cls = 0 if (qn and dn.startswith(qn)) else 1
            for i in rel:
                cur = hits[i].get("match_rank")
                if cur is None or cls < cur:  # 0 is a real class — never `or` it
                    hits[i]["match_rank"] = cls
                    hits[i]["match"] = _MATCH_NAMES[cls]
            acc.append(h)
        else:
            keep.append(h)
    return keep + acc


_CITY_SUFFIX = frozenset(("delhi", "new", "india", "ncr"))


def _name_prefix(a, b):
    """one display is the other plus city-suffix filler — 'Lodi
    Gardens' ~ 'Lodi Gardens, Delhi'."""
    at, bt = set(a.split()), set(b.split())
    if at <= bt and at != bt:
        return (bt - at) <= (_PLACE_NEUTRAL | _CITY_SUFFIX)
    if bt <= at and bt != at:
        return (at - bt) <= (_PLACE_NEUTRAL | _CITY_SUFFIX)
    return False


def _dedupe_hits(rows):
    """same-place rows collapse: twin bus bays ('AIIMS'/'AIIMS'
    platforms 72m apart), spelling-variant parks ('Lodi Gardens' /
    'Lodhi Gardens' 16m apart), and city-suffixed names ('Lodi
    Gardens, Delhi') read as duplicates."""
    kept, out = [], []
    for h in rows:
        disp = " ".join(sorted(
            alive_core_ref.normalize(h.get("display") or "")))
        cat = h.get("category") or ""
        if h.get("lat") is not None:
            for k, ph in kept:
                if cat != k[1]:
                    continue
                m = _hav_m(h["lat"], h["lon"],
                           ph["lat"], ph["lon"])
                if m > 350.0:
                    continue
                if ((disp == k[0] or _name_prefix(disp, k[0]))
                        or (m <= 150.0
                            and abs(len(disp) - len(k[0])) <= 2
                            and alive_core_ref.dl_distance(
                                disp, k[0], 2) <= 2)):
                    break
            else:
                kept.append(((disp, cat), h))
                out.append(h)
            continue
        kept.append(((disp, cat), h))
        out.append(h)
    return out


def search(q, lat=None, lon=None, limit=8):
    """/v2/search T1 — index.query on whichever impl loaded. Index ids
    are positions (uint32 for the C++ binding); remap to the resolvable
    `pid` (gaz:<idx>/cor:<osm-id>) the gazetteer engine emits."""
    qtoks = alive_core_ref.normalize(q)
    nums = [t for t in qtoks if t.isdigit()]
    # numeric tokens are load-bearing ('sector 12' is not 'sector 125',
    # '43' is not '4') — when the query carries digits, rows that don't
    # contain them verbatim are wrong answers, not close-enough ones.
    # ask the index wider so honest digit-bearing rows survive the cut
    q_limit = max(limit, limit * 5, 32) if nums else limit
    # address filler ('house', 'h no', 'flat', 'plot') is real vocab —
    # it makes 'house 559 udyog vihar' match 'Gaurd House' across the
    # city. When digits anchor the query, the number leads, not the
    # decoration
    q_use = q
    if nums:
        kept = [t for t in qtoks if t not in _DESIG_FILLER]
        if kept:
            q_use = " ".join(kept)
    hits = search_index().query(q_use, lat, lon, q_limit)
    if nums:
        hits = [h for h in hits
                if all(n in set(alive_core_ref.normalize(
                    h.get("display") or "")) for n in nums)]
    hits = _demote_accessory(hits, " ".join(qtoks))
    weak = not hits or (hits[0].get("cov") or 0.0) < 0.9
    comp = _compound(q, weak, lat, lon, limit, hits)
    if comp:
        # intent rows first; name hits append for breadth (deduped on
        # pid — an entry can satisfy both readings, e.g. "Saket City
        # Hospital" for 'hospital saket')
        seen = {r["id"] for r in comp}
        for h in hits:
            if h.get("id") not in seen and not h.get("_foreign"):
                comp.append(h)
        hits = comp
    hits = _dedupe_hits(hits)[:limit]
    for h in hits:
        i = h.get("id")
        if isinstance(i, int) and 0 <= i < len(_SEARCH_PIDS):
            h["id"] = _SEARCH_PIDS[i]
    return hits


class KrigeField:
    """Drop-in for krige.KrigeField — same fit(samples)/on/estimate.

    C++ KrigeField takes parallel (lat, lon, z) arrays and does no sample
    coercion, so the adapter replicates krige.py's contract around it:
    coerce + finite-check, merge bit-identical (lat, lon) by mean keeping
    first occurrence. Fit/estimate math is then identical by
    test_core_parity.
    """

    def __init__(self):
        self.on = False
        if _CPP_KRIGE:
            self._impl = "cpp"
            self._kf = _ac.KrigeField()
        else:
            self._impl = "py"
            self._kf = krige.KrigeField()

    def fit(self, samples, key="pm2_5"):
        self.on = False
        if self._impl == "py":
            self._kf.fit(samples, key=key)
            self.on = self._kf.on
            return self
        merged = {}  # (lat, lon) -> [z_sum, count]; dicts keep order
        for s in samples:
            try:
                lat, lon, _name, vals = s
                zf = float((vals or {}).get(key))
                latf, lonf = float(lat), float(lon)
            except (TypeError, ValueError, OverflowError, AttributeError):
                continue
            if not (math.isfinite(latf) and math.isfinite(lonf)
                    and math.isfinite(zf)):
                continue
            e = merged.get((latf, lonf))
            if e is None:
                merged[(latf, lonf)] = [latf, lonf, zf, 1.0]
            else:
                e[2] += zf
                e[3] += 1.0
        recs = list(merged.values())
        self.on = bool(self._kf.fit(
            [r[0] for r in recs], [r[1] for r in recs],
            [r[2] / r[3] for r in recs], _ac.KrigeParams()))
        return self

    def estimate(self, lat, lon) -> Optional[tuple]:
        if self._impl == "py":
            return self._kf.estimate(lat, lon)
        if not self.on:
            return None
        try:
            est = self._kf.estimate(float(lat), float(lon))
        except (TypeError, ValueError, OverflowError):
            return None
        if est is None:
            return None
        mu, sd = float(est[0]), float(est[1])
        return (mu, sd) if math.isfinite(mu) and math.isfinite(sd) else None


# airfield.py's module-level field — same role as krige.KF.
KF = KrigeField()
