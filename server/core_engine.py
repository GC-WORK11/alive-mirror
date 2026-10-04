"""alive_core runtime shim — the C++ engine where the extension loads,
the verified Python reference where it doesn't (docs/plan/08).

`ENGINE` is the serving label: /health reports it, so the API never
claims C++ while answering from Python. Every adapter here reproduces
its counterpart's exact contract — krige.py's sample coercion/merge and
estimate semantics — and the parity suite (tests/test_core_parity.py,
tests/test_parity_field.py) bit-checks C++ vs Python on the same inputs.
"""

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

# kind phrase -> cooked category set (entries_from_gazetteer kinds).
# Multi-word forms ("petrol pump", "metro station") win before their
# single tokens, so "bus stand" doesn't read as plain "bus" + leftover.
_KIND_PHRASES = {
    ("petrol", "pump"): ("fuel",), ("gas", "station"): ("fuel",),
    ("filling", "station"): ("fuel",), ("charging", "station"):
    ("charging_station", "charge_point"),
    ("metro", "station"): ("metro", "station", "train_station",
                           "subway_entrance", "platform", "stop"),
    ("railway", "station"): ("train_station", "station",
                             "railway:station", "rail", "halt",
                             "platform"),
    ("train", "station"): ("train_station", "station",
                           "railway:station", "rail", "halt", "platform"),
    ("rail", "station"): ("train_station", "station", "rail", "halt"),
    ("police", "station"): ("police", "policeoutpost"),
    ("bus", "stop"): ("bus_stop", "platform", "stop", "stop_position",
                      "public_transport:platform", "amenity:bus_station"),
    ("bus", "stand"): ("bus_station", "bus_stop", "platform", "stop",
                      "amenity:bus_station"),
    ("bus", "station"): ("bus_station", "bus_stop", "platform", "stop",
                        "amenity:bus_station"),
    ("bus", "depot"): ("bus_station", "bus_depot", "bus_stop",
                      "amenity:bus_station", "depot", "platform", "stop"),
    ("bus", "terminal"): ("bus_station", "bus_depot", "bus_stop",
                         "amenity:bus_station", "depot", "platform"),
    ("bus", "terminus"): ("bus_station", "bus_depot", "amenity:bus_station",
                         "depot", "platform"),
    ("depot",): ("bus_station", "bus_depot", "depot",
                "amenity:bus_station"),
    ("terminus",): ("bus_station", "bus_depot", "depot",
                   "amenity:bus_station", "train_station"),
    ("isbt",): ("bus_station", "bus_stop", "platform",
               "amenity:bus_station"),
    ("adda",): ("bus_station", "bus_stop", "amenity:bus_station"),
    ("post", "office"): ("post_office", "post_depot", "post_box"),
    ("fire", "station"): ("fire_station",),
    ("guest", "house"): ("guest_house", "tourism:guest_house", "hostel"),
    ("ice", "cream"): ("ice_cream",),
    ("swimming", "pool"): ("swimming_pool", "swimming_area"),
    ("community", "centre"): ("community_centre", "social_centre"),
    ("community", "center"): ("community_centre", "social_centre"),
    ("movie", "theater"): ("cinema",),
    ("nursing", "home"): ("hospital", "nursing_home"),
    ("medical", "store"): ("pharmacy", "chemist", "medical_supply"),
    ("car", "wash"): ("car_wash",),
    ("shopping", "mall"): ("shopping_mall", "mall", "shop:mall",
                           "shopping_centre", "department_store"),
    ("taxi", "stand"): ("taxi",),
    ("petrol",): ("fuel",),
    ("sports", "complex"): ("stadium_arena", "stadium", "sports_centre"),
    ("sports", "centre"): ("sports_centre", "stadium_arena"),
    ("golf", "course"): ("golf_course",),
    ("atm",): ("atm",),
    ("bank",): ("bank",),
    ("hospital",): ("hospital", "specialty_hospital", "nursing_home",
                   "amenity:hospital"),
    ("aspatal",): ("hospital",),
    ("clinic",): ("clinic", "dental_clinic", "outpatient_care_facility",
                  "vision_or_eye_care_clinic", "healthcare"),
    ("doctor",): ("doctors", "doctor", "clinic"),
    ("dentist",): ("dentist", "dental_clinic"),
    ("pharmacy",): ("pharmacy", "chemist", "medical_supply"),
    ("chemist",): ("pharmacy", "chemist"),
    ("school",): ("school", "prep_school", "kindergarten",
                  "educational_institution", "language_school",
                  "music_school", "driving_school", "dancing_school",
                  "specialty_school", "amenity:school",
                  "building:school"),
    ("college",): ("college", "college_university",
                   "educational_institution", "amenity:college",
                   "building:college"),
    ("university",): ("university", "college_university",
                      "educational_institution", "amenity:university",
                      "building:university"),
    ("metro",): ("metro", "subway", "subway_entrance"),
    ("station",): ("station", "train_station", "metro",
                   "railway:station", "halt"),
    ("airport",): ("airport", "aerodrome", "terminal", "helipad",
                   "heliport"),
    ("police",): ("police", "policeoutpost"),
    ("thana",): ("police", "policeoutpost"),
    ("parking",): ("parking", "parking_space", "parking_entrance",
                  "motorcycle_parking", "bicycle_parking"),
    ("restaurant",): ("restaurant", "fast_food", "food_court",
                      "canteen"),
    ("dhaba",): ("restaurant", "fast_food"),
    ("hotel",): ("hotel", "guest_house", "hostel", "motel", "resort",
                 "tourism:hotel", "tourism:guest_house"),
    ("hostel",): ("hostel", "dormitory", "student_accommodation",
                  "student_accomodation"),
    ("dharamshala",): ("guest_house", "hostel"),
    ("cafe",): ("cafe", "coffee", "internet_cafe"),
    ("cinema",): ("cinema", "theatre"),
    ("movie",): ("cinema", "theatre"),
    ("multiplex",): ("cinema",),
    ("theatre",): ("theatre", "cinema", "arts_centre"),
    ("park",): ("park", "garden", "playground", "recreation_ground",
                "dog_park", "leisure:park", "national_park"),
    ("playground",): ("playground", "pitch", "park"),
    ("gym",): ("gym", "fitness_centre", "sports_centre",
               "fitness_station", "leisure:fitness_centre",
               "leisure:sports_centre"),
    ("gymnasium",): ("gym", "fitness_centre"),
    ("stadium",): ("stadium_arena", "stadium", "sports_centre",
                   "leisure:stadium"),
    ("library",): ("library", "public_bookcase"),
    ("market",): ("marketplace", "market", "greengrocer"),
    ("mandi",): ("marketplace", "market", "greengrocer"),
    ("bazaar",): ("marketplace", "market", "convenience"),
    ("mall",): ("shopping_mall", "mall", "shop:mall", "shopping_centre",
                "department_store"),
    ("shop",): ("shop", "convenience", "supermarket", "store",
                "variety_store", "general", "retail"),
    ("store",): ("store", "shop", "convenience", "supermarket",
                 "variety_store", "general"),
    ("grocery",): ("supermarket", "convenience", "grocery",
                   "greengrocer", "shop:supermarket",
                   "shop:convenience"),
    ("kirana",): ("convenience", "grocery", "general", "supermarket"),
    ("supermarket",): ("supermarket", "shop:supermarket", "convenience"),
    ("gymkhana",): ("club", "sports_centre"),
    ("club",): ("club", "social_club", "sports_centre"),
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
    ("bar",): ("bar", "pub", "nightclub", "lounge"),
    ("pub",): ("pub", "bar", "nightclub"),
    ("theka",): ("bar", "pub", "alcohol", "wine"),
    ("bakery",): ("bakery", "pastry", "confectionery"),
    ("sweets",): ("sweets", "confectionery", "pastry", "sweet",
                  "sweets_shop"),
    ("mithai",): ("sweets", "confectionery", "sweet"),
    ("court",): ("courthouse",),
    ("kachahri",): ("courthouse",),
    ("vet",): ("veterinary",),
    ("veterinary",): ("veterinary",),
    ("taxi",): ("taxi",),
    ("cab",): ("taxi",),
    ("graveyard",): ("grave_yard", "cemetery"),
    ("cemetery",): ("cemetery", "grave_yard"),
    ("smashan",): ("crematorium", "cemetery"),
    ("salon",): ("hairdresser", "beauty"),
    ("parlour",): ("beauty", "hairdresser"),
    ("parlor",): ("beauty", "hairdresser"),
    ("barber",): ("hairdresser",),
    ("tailor",): ("tailor",),
    ("electrician",): ("electrician",),
    ("plumber",): ("plumber",),
    ("gym", "wear"): ("gym_wear",),
    ("pet", "shop"): ("pet",),
    ("computer",): ("computer", "electronics", "electronics_repair"),
    ("mobile", "shop"): ("mobile_phone", "mobile_phone_accessories"),
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


def _anchor_row(toks, lat, lon):
    ah = search_index().query(" ".join(toks), lat, lon, 1)
    if ah and (ah[0].get("cov") or 0.0) >= 0.75:
        return ah[0]
    return None


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


def _subplace(toks, lat, lon, limit, hits=None):
    """'<letter/number> <designator> <place>' — 'pocket b sarita
    vihar', 'h block sector 62 noida', 'a 43 defence colony'. The place
    phrase resolves as the anchor; a row inside its radius whose
    display carries the remaining unit tokens is the sub-place the
    user meant. When the anchor's own display already carries them
    ('Beta 2' for 'beta 2 greater noida') the anchor is the answer.
    When nothing declares them, the locality is the honest answer —
    never a same-numbered unit in a different colony."""
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
    for drop in (0, 1):  # full phrase, then minus anchor digits
        qt = [t for t in anchor_toks if not (drop and t.isdigit())]
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
        if all(_tok_wanted(atoks, t) for t in want):
            return [_area_row(anchor)]  # the anchor IS the sub-place
        # 'inside the named place' — a locality's pockets sit close, a
        # city's sectors sit km out; scale the membership radius to the
        # anchor's measured extent, never beyond the metro ceiling
        radius = min(_SUBPLACE_HIT_MAX_M,
                     max(_COMPOUND_MAX_M, _anchor_extent(anchor) * 1.5))
        # a name-path row that already carries the unit and sits inside
        # the anchor's urban area IS the real sub-place — promote it
        # ahead of same-named units elsewhere ('Pocket B' in Jasola
        # fails for 'pocket b sarita vihar'; 'Beta 2' inside Greater
        # Noida passes)
        cand = []
        for h in hits or []:
            ht = set(alive_core_ref.normalize(h.get("display") or ""))
            if not all(_tok_wanted(ht, t) for t in want):
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
        if cand:
            return cand
        out = []
        for e, d in nearest(anchor["lat"], anchor["lon"],
                            max_m=radius, limit=4096):
            etoks = set(
                alive_core_ref.normalize(e.get("display") or ""))
            if not all(_tok_wanted(etoks, t) for t in want):
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
        return out

    # first anchor whose area actually holds the unit wins; when no
    # candidate does, the top anchor itself is the honest area answer.
    # 3 candidates max — each resolve() is a spatial scan, and deeper
    # ambiguity is a wrong anchor more often than a hidden right one
    rows = []
    for anchor in anchors[:3]:
        rows = resolve(anchor)
        if rows:
            break
    return rows or [_area_row(anchors[0])]


def _compound(q, weak: bool, lat, lon, limit, hits=None):
    """kind+place compound rows, or [] when nothing honest resolves.

    `weak` = the plain name-match came back empty or partial; only then
    do we reinterpret the query as kind + anchor."""
    if not weak:
        return []
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
        return _subplace(toks, lat, lon, limit, hits)
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
        place_toks = [t for t in rest if t not in _COMPOUND_STOP]
        if not place_toks:
            return []
        ah = search_index().query(" ".join(place_toks), lat, lon, 1)
        if not ah or (ah[0].get("cov") or 0.0) < 0.75:
            return []
        anchor = ah[0]

    out = []
    # scan deep enough that dense localities can't starve a rarer kind —
    # Dwarka alone has ~1k rows inside the radius
    for e, d in nearest(anchor["lat"], anchor["lon"],
                        max_m=_COMPOUND_MAX_M, limit=4096):
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
    return _subplace(toks, lat, lon, limit, hits)


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
