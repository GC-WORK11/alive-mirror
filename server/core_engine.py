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
        if r > 12:  # ~2.4 km ceiling — nothing this far is a reverse hit
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
                      "public_transport:platform"),
    ("bus", "stand"): ("bus_station", "bus_stop", "platform", "stop"),
    ("bus", "station"): ("bus_station", "bus_stop", "platform", "stop"),
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


def _compound(q, weak: bool, lat, lon, limit):
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
        return []
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
        out.append({
            "id": e["pid"],
            "display": e["display"],
            "category": e.get("category") or "",
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
            "match": "category", "match_rank": 1,
        })
        if len(out) >= limit:
            break
    return out


def search(q, lat=None, lon=None, limit=8):
    """/v2/search T1 — index.query on whichever impl loaded. Index ids
    are positions (uint32 for the C++ binding); remap to the resolvable
    `pid` (gaz:<idx>/cor:<osm-id>) the gazetteer engine emits."""
    hits = search_index().query(q, lat, lon, limit)
    weak = not hits or (hits[0].get("cov") or 0.0) < 0.9
    comp = _compound(q, weak, lat, lon, limit)
    if comp:
        # intent rows first; name hits append for breadth (deduped on
        # pid — an entry can satisfy both readings, e.g. "Saket City
        # Hospital" for 'hospital saket')
        seen = {r["id"] for r in comp}
        for h in hits:
            if h.get("id") not in seen:
                comp.append(h)
        hits = comp[:limit]
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
