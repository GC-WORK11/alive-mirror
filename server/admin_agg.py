"""Aggregate-only admin API — /admin/api/* (docs/plan/07 §2, §3).

MOUNT NOTE — the integrator wires this router into server/main.py with
exactly two lines, next to the /v2 mount at the bottom of the file:

    from admin_agg import router as _admin_agg_router   # or: server.admin_agg
    app.include_router(_admin_agg_router)

(/admin itself — the HTML page — is already served by main.py; this file
is only the data layer behind the rebuilt dashboard.)

PRIVACY — this module is architecturally incapable of showing a person:
  * It reads ONLY TripAggregates (v2/store.py), which holds day counters
    and per-cell counts/dose/token-SETS. Raw trajectories are discarded in
    v2/trip.py before anything reaches the store; raw device tokens are
    hashed before record_trip() sees them.
  * k >= 3 is enforced BY THE STORE — TripAggregates._publishable_cells
    filters len(tokens) >= 3 inside the lock, before a row can exist.
    /corridors re-asserts the invariant on every response and fails loud
    (AssertionError -> 500) rather than ever publishing a k < 3 row.
  * There is no global device registry, so /donations cannot answer
    "how many devices" — it reports that as null + reason, not a guess.
  * No endpoint emits tokens, user ids, or coordinates. Corridor rows are
    H3 cell keys — the documented public aggregate unit (doc 07 §2).
    Daily-rollup `cells` maps (keys embed grid coords) are never passed
    through; only the city summary block is surfaced.

Everything degrades honestly: an empty store or a missing rollup file
returns a shaped "empty"/"unavailable" payload, never a fabricated zero
presented as measured truth.
"""
import glob
import json
import os
import sys
import time

from fastapi import APIRouter

# flat layout (uvicorn from server/) and package layout (repo root) both work
_SERVER_DIR = os.path.dirname(os.path.abspath(__file__))
if _SERVER_DIR not in sys.path:
    sys.path.insert(0, _SERVER_DIR)

import health as _health  # noqa: E402

try:  # noqa: E402
    from v2.store import LEDGER, TRIPS
except ImportError:  # imported as server.admin_agg from the repo root
    from server.v2.store import LEDGER, TRIPS  # type: ignore

router = APIRouter(prefix="/admin/api", tags=["admin-aggregates"])

K_MIN = 3                      # doc 07 §3 display threshold (store-enforced)
CORRIDOR_WINDOW_S = 72 * 3600  # corridor freshness window (same constant)

_DATA_DIR = os.path.join(_SERVER_DIR, "data")


# --- live status helpers (all local, no network — same rule as /health) ------

def _field_status() -> dict:
    try:
        from airfield import FIELD
        return FIELD.status() or {}
    except Exception:
        return {}


def _snapshot_prov() -> dict:
    """Per-source provenance block of the newest on-disk field snapshot
    (status/fetched_at/age_s + build rows like n_used, wind_ms, vc_m2s).
    Empty dict when nothing readable exists — callers report nulls, not
    guesses. Disk-only, same rule as health.collect_health."""
    try:
        probe = _health._field_probe(time.time())
        return ((probe.get("payload") or {}).get("provenance") or {})
    except Exception:
        return {}


def _fires_status() -> dict:
    try:
        from fires import FIRES
        return FIRES.status() or {}
    except Exception:
        return {}


def _location_enabled():
    try:
        from v2 import deps
        return deps.location_enabled()
    except Exception:
        try:
            from server.v2 import deps
            return deps.location_enabled()
        except Exception:
            return None  # unknown, not "down"


# --- corridor labels ---------------------------------------------------------
# A corridor row is already a public k>=3 aggregate; naming the nearest
# gazetteer place makes the table readable without revealing anything finer
# than the cell itself. Best-effort: no h3 / no gazetteer -> name is null.

def _cell_center(cell: str):
    """H3 index or 'll:<lat>,<lon>' key -> (lat, lon) used only internally."""
    if isinstance(cell, str) and cell.startswith("ll:"):
        try:
            la, lo = cell[3:].split(",")
            return float(la), float(lo)
        except (ValueError, TypeError):
            return None
    try:
        import h3
        la, lo = h3.cell_to_latlng(cell)
        return float(la), float(lo)
    except Exception:
        return None


_GAZ_ROWS = None


def _nearest_place_name(lat: float, lon: float, max_km: float = 2.0):
    """Nearest gazetteer place to a cell centre -> name or None."""
    global _GAZ_ROWS
    if _GAZ_ROWS is None:
        _GAZ_ROWS = []
        try:
            from v2.gazetteer import GAZ
            _GAZ_ROWS = GAZ._load() or []
        except Exception:
            try:
                from server.v2.gazetteer import GAZ  # type: ignore
                _GAZ_ROWS = GAZ._load() or []
            except Exception:
                _GAZ_ROWS = []
    best, best_d = None, max_km * 1000.0
    for r in _GAZ_ROWS:
        rlat, rlon = r.get("lat"), r.get("lon")
        if rlat is None or rlon is None:
            continue
        d = ((rlat - lat) ** 2 + (rlon - lon) ** 2) ** 0.5 * 111000.0
        if d < best_d:
            best, best_d = r.get("name"), d
    return best


def _routing_status():
    """Last observed OSRM call — real route traffic, not a probe."""
    try:
        from v2 import deps as _d
    except Exception:
        try:
            from server.v2 import deps as _d
        except Exception:
            _d = None
    last = getattr(_d, "OSRM_LAST", None) or {}
    at = last.get("at")
    return {
        "detail": ("self-hosted Delhi daemon first, public OSRM demo "
                   "fallback — driving/cycling/walking profiles"),
        "up": last.get("ok"),
        "ms": last.get("ms"),
        "backend": last.get("backend"),
        "age_s": (round(time.time() - at, 1) if at else None),
        "err": last.get("err"),
        "note": ("observed from real route calls — null until the first "
                 "request, never a synthetic ping"),
    }


def _corridor_label(cell: str):
    c = _cell_center(cell)
    if not c:
        return None
    try:
        return _nearest_place_name(c[0], c[1])
    except Exception:
        return None


# --- rollup readers (disk-only, honest when absent) ---------------------------

def _latest_json(pattern: str):
    """(path, dict) for the newest readable file matching `pattern`."""
    for path in sorted(glob.glob(pattern), reverse=True):
        try:
            with open(path, "r", encoding="utf-8") as fh:
                return path, json.load(fh)
        except (OSError, ValueError):
            continue
    return None, None


def _latest_validation():
    path, doc = _latest_json(
        os.path.join(_DATA_DIR, "field", "validation", "*.json"))
    if not doc:
        return None
    return {
        "week": doc.get("week"),
        "generated": doc.get("generated"),
        "snapshot": doc.get("snapshot"),
        "loso": doc.get("loso") or {"status": "missing"},
        "archive_replay": doc.get("archive_replay") or {"status": "missing"},
        "file": os.path.basename(path) if path else None,
    }


def _latest_daily():
    path, doc = _latest_json(
        os.path.join(_DATA_DIR, "field", "daily", "*.json"))
    if not doc:
        return None
    city = doc.get("city") or {}
    # NOTE: doc["cells"] (grid-coord keys) is deliberately NOT passed through.
    return {
        "date": doc.get("date"),
        "n_snapshots": doc.get("n_snapshots"),
        "n_cells": doc.get("n_cells"),
        "median_pm25": city.get("median_pm25"),
        "pct_cells_gt15_who": city.get("pct_cells_gt15_who"),
        "pct_cells_gt60_cpcb": city.get("pct_cells_gt60_cpcb"),
        "thresholds": doc.get("thresholds"),
        "file": os.path.basename(path) if path else None,
    }


# --- endpoints ---------------------------------------------------------------

@router.get("")
async def index():
    """Surface map + the privacy contract, for humans and scrapers."""
    return {
        "service": "alive108 admin aggregates",
        "ts": time.time(),
        "privacy": ("aggregate-only — k>=3 enforced by the trip store; "
                    "no per-device data exists server-side to serve"),
        "endpoints": [
            "/admin/api/status",
            "/admin/api/sources",
            "/admin/api/corridors",
            "/admin/api/donations",
            "/admin/api/validation",
            "/admin/api/model",
            "/admin/api/timing",
            "/admin/api/global",
        ],
    }


@router.get("/timing")
async def timing():
    """Measured request latencies — the API's own stopwatch, not a
    claim. Histograms are in-process since boot (or the registry's
    last clear); p50/p90 are reported as the smallest bucket edge that
    covers the share — 'p90_le_ms: 500' honestly reads 'at least 90% of
    requests finished within 500 ms'.
    """
    import observability as _obs
    out = {"ts": time.time(), "window": "since process start",
           "routes": [], "pipeline": {}, "gauges": {}}
    reg = _obs.REGISTRY
    with reg._lock:
        hists = {k: {"buckets": dict(v["buckets"]),
                     "sum": v["sum"], "count": v["count"]}
                 for k, v in reg._histograms.items()}
        gauges = dict(reg._gauges)
    def _pct_le(h, share):
        if not h["count"]:
            return None
        need = h["count"] * share
        cum = 0
        for le in sorted(h["buckets"]):
            cum += h["buckets"][le]
            if cum >= need:
                return round(le, 1)
        return None                      # slower than every bucket edge
    for (name, lk), h in sorted(hists.items()):
        labels = dict(lk)
        row = {"n": h["count"],
               "mean_ms": round(h["sum"] / h["count"], 1) if h["count"] else None,
               "p50_le_ms": _pct_le(h, 0.5),
               "p90_le_ms": _pct_le(h, 0.9)}
        if name == "alive_request_duration_ms":
            out["routes"].append({"path": labels.get("route", "?"), **row})
        else:
            lbl = {("path" if k == "route" else k): v
                   for k, v in labels.items()}
            out["pipeline"][name] = {**lbl, **row}
    for (name, lk), v in sorted(gauges.items()):
        out["gauges"][name] = v
    out["routes"].sort(key=lambda r: -r["n"])
    return out


@router.get("/status")
async def status():
    """Service + air-field status, age and provenance (health.py paths)."""
    h = _health.collect_health()
    f = _field_status()
    species = {}
    try:
        from airfield import FIELD
        from v2.city import _species
        species = _species(FIELD)
    except Exception:
        species = {}
    forecast = {}
    try:
        from forecast import FORECAST
        forecast = FORECAST.status() or {}
    except Exception:
        forecast = {}
    routing = {"loaded": False}
    try:
        import routegraph
        eng = getattr(routegraph, "_ENGINE", None)
        if eng is not None:
            def _n(name):
                v = getattr(eng, name, None)
                if v is None:
                    v = getattr(getattr(eng, "g", None), name, None)
                return v() if callable(v) else v
            from v2 import plan as _v2plan
            meta = {}
            try:
                mp = routegraph.GRAPH_FILE.replace(".bin.gz", ".meta.json")
                meta = json.loads(open(mp).read())
            except Exception:
                pass
            eng_t = getattr(_v2plan, "_ENG_T", 0)
            routing = {
                "loaded": True,
                "engine": type(eng).__name__,
                "edges": _n("n_edges"),
                "nodes": _n("n_nodes"),
                "edges_priced": _n("edges_priced"),
                "field_mean": _n("field_mean"),
                "reweight_age_s": round(time.time() - eng_t) if eng_t else None,
                "reweight_ttl_s": getattr(_v2plan,
                                          "ENGINE_REWEIGHT_TTL_S", None),
                "graph_pbfs": meta.get("pbfs"),
                "graph_sha": meta.get("pbf_sha256"),
            }
    except Exception as e:
        routing = {"loaded": False, "error": repr(e)}
    return {
        "ts": time.time(),
        "ok": h.get("ok", True),
        "build_sha": h.get("build_sha"),
        "version": h.get("version"),
        "uptime_s": h.get("uptime_s"),
        "field": {
            "source": f.get("source"),
            # serving honesty (airfield.status): which field answers
            # queries right now, and whether it is past the alarm rule
            "serving": f.get("serving"),            # snapshot | live | none
            "samples": f.get("samples"),
            "station_readings": f.get("station_readings"),
            "age_s": f.get("age_s"),
            "stale": f.get("stale"),              # True past stale_after_s
            "stale_after_s": f.get("stale_after_s"),
            "kriging": f.get("kriging"),
            "engine": f.get("engine"),  # alive_core | python serving label
            "sigma_coverage": f.get("sigma_coverage"),
            "coverage": f.get("coverage"),
            "wind": f.get("wind") or {},
            "snapshot_age_s": h.get("field_age_s"),
        },
        # the other real species the field serves — city-mean lattice
        # stats; absent entirely when the serving field is pm25-only
        "species": species,
        # the forecast horizon's own health — grid points, hour span,
        # fetch age, and whether reads are anchored to the live field
        "forecast": forecast,
        # the least-inhalation path engine — graph size, how many edges
        # are priced off the live field right now, and reprice age.
        # loaded:false until the boot-warm or first plan builds it.
        "routing": routing,
        "trips_backend": h.get("trips_backend"),
        "ledger": {
            "backend": getattr(LEDGER, "backend", "memory"),
            "devices_tracked": LEDGER.devices(),
            "error": getattr(LEDGER, "last_error", None),
        },
        "disk": h.get("disk") or {},
        "provenance": {
            "field": ("Open-Meteo/CAMS grid + CPCB/OpenAQ/WAQI station blend, "
                      "kriged; snapshots under data/field/snapshots"),
            "corridors": "donated traversals, H3 cells, k>=3 devices/72h",
            "validation": "weekly LOSO + OpenAQ archive replay on disk",
        },
        "empty": not bool(f),
    }


@router.get("/sources")
async def sources():
    """Per-ingest-source health for all four field inputs + location.

    `up` is tri-state from health.py — True/False only when explicitly
    probed/overridden, else null ('configured, not probed'). `age_s` is
    the live figure: the in-memory fetch when the module has one, else
    the newest snapshot's provenance — never a fabricated green, and a
    live null never erases the last build's observed age. `stale` flags
    age past the field alarm rule (doc 05 §6) — null when no age exists
    (a never-fetched source is 'no data', not 'late data')."""
    h = _health.collect_health()
    f = _field_status()
    fires = _fires_status()
    loc_up = _location_enabled()
    src = h.get("sources") or {}
    prov = _snapshot_prov()
    stale_after = f.get("stale_after_s") or 45 * 60

    def merged(name, extra):
        s = dict(src.get(name) or {})
        for k, v in extra.items():
            # a live null must not erase the last build's observed value
            if v is None and k in s:
                continue
            s[k] = v
        return s

    out = {
        "model": merged("model", {
            "n_points": (prov.get("model") or {}).get("n_points"),
            "samples": f.get("samples"),
            "field_age_s": f.get("age_s")}),
        "met": merged("met", {
            "wind_ms": (prov.get("met") or {}).get("wind_ms"),
            "wind_deg": (prov.get("met") or {}).get("wind_deg"),
            "blh_m": (prov.get("met") or {}).get("blh_m"),
            "vc_m2s": (prov.get("met") or {}).get("vc_m2s"),
            # live serving wind from FIELD.status() — covers tasks whose
            # newest disk snapshot predates met provenance (met serves
            # wind on /aqi but the build record has nothing to show)
            "wind_kmh": (f.get("wind") or {}).get("speed_kmh"),
            "wind_from_deg": (f.get("wind") or {}).get("from_deg")}),
        "stations": merged("stations", {
            "readings": f.get("station_readings"),
            "n_raw": (prov.get("stations") or {}).get("n_raw"),
            "n_used": (prov.get("stations") or {}).get("n_used"),
            "field_age_s": f.get("age_s")}),
        "fires": merged("fires", {
            "fires": fires.get("fires"),
            "belt_fires": fires.get("belt_fires"),
            "status": fires.get("status"),
            "age_s": fires.get("age_s"),
            "modifier": (prov.get("fires") or {}).get("modifier")}),
        "location": merged("location", {"enabled": loc_up}),
        # the routing engine — observed from real /v2/plan calls, never
        # probed synthetically; nulls mean 'no route requested yet'
        "routing": _routing_status(),
    }
    for s in out.values():
        a = s.get("age_s")
        s["stale"] = (a > stale_after) if isinstance(a, (int, float)) else None

    return {
        "ts": time.time(),
        "stale_after_s": stale_after,
        "sources": out,
        "note": ("up=null means 'configured, not probed' — probes are "
                 "explicit env overrides; we report, we do not guess"),
    }


@router.get("/corridors")
async def corridors(limit: int = 25):
    """k>=3 corridor aggregates straight from TripAggregates.

    The k>=3 + 72h-window rule is enforced INSIDE the store
    (_publishable_cells, under lock). The assert below is a tripwire,
    not the mechanism: if a k<3 row ever reaches this layer it is a
    store bug, and the correct behaviour is to fail loud — never to
    render a row that shouldn't exist.
    """
    lim = max(1, min(int(limit or 25), 200))
    raw = TRIPS.corridors(limit=lim) or []
    assert all(int(r.get("devices") or 0) >= K_MIN for r in raw), \
        "k>=3 invariant violated upstream — refusing to publish"
    field = None
    try:
        from airfield import FIELD
        field = FIELD
    except Exception:
        try:
            from server.airfield import FIELD as _F  # type: ignore
            field = _F
        except Exception:
            field = None

    def _field_at(cell):
        """Live pm2.5 under this corridor's centre — the merge an admin
        reads as 'people travel this street through air this dirty'.
        None when the field or the cell key is unavailable — never a
        guess."""
        c = _cell_center(cell)
        if not c or field is None:
            return None
        try:
            return field.value(c[0], c[1], "pm2_5")
        except Exception:
            return None

    rows = [{
        "cell": r.get("cell"),
        "near": _corridor_label(r.get("cell")),
        "trips": r.get("trips"),
        "devices": r.get("devices"),
        "avg_dose_ug": r.get("avg_dose_ug"),
        "co2_g_per_100m": r.get("co2_g_per_100m"),
        "co2_trips": r.get("co2_trips"),
        "field_pm25": _field_at(r.get("cell")),
    } for r in raw]
    agg = TRIPS.city_aggregates() or {}
    return {
        "ts": time.time(),
        "k_min": K_MIN,
        "window_s": CORRIDOR_WINDOW_S,
        "rule": ("a cell is publishable only with >=3 distinct devices "
                 "in 72h — enforced by the store, re-asserted here"),
        "rows": rows,
        "shown": len(rows),
        "publishable_cells": agg.get("corridors_publishable", 0),
        "cells_tracked": agg.get("cells_tracked", 0),
        "empty": not rows,
    }


@router.get("/model")
async def model_card():
    """The dose/emission model's own constants — served from the code
    so the panel can never drift from what the engine computes.
    Descriptive only: every number here is a published model constant
    or a citation, never a live-data estimate."""
    try:
        import exposure as _ex
    except Exception:
        try:
            from server import exposure as _ex
        except Exception:
            _ex = None
    canon = ["metro", "driving_car_ac", "driving_car_open", "bus",
             "driving_two_wheeler", "auto_rickshaw", "cycling", "walking"]
    if _ex is None:
        return {"ts": time.time(), "available": False,
                "note": "exposure model not importable on this task"}
    return {
        "ts": time.time(),
        "available": True,
        "sample_every_m": 250.0,
        "dose_formula": ("µg = Σ over the route's ~250 m segments: "
                          "field-C(lat,lon) × microenv(mode) × "
                          "ventilation(L/min) × minutes"),
        "microenv": {m: _ex.MICROENV[m] for m in canon
                     if m in _ex.MICROENV},
        "ventilation_lpm": {m: _ex.VENTILATION_LPM[m] for m in canon
                            if m in _ex.VENTILATION_LPM},
        "road_uplift": {k: v for k, v in _ex.ROAD_UPLIFT.items()
                        if k != "arterial"},
        "plausible_max_kmh": _ex.PLAUSIBLE_MAX_KMH,
        "citations": {
            "microenv": "measured Delhi microenvironment ratios, doc 06 §1",
            "ventilation": ("Zuurbier 2009 — cyclists ≈2.1× in-vehicle VE; "
                            "activity-adjusted tiers"),
            "uplift": ("near-road PM increment decays within ~500 m of "
                       "the curb, doc 06 §1"),
        },
    }


@router.get("/donations")
async def donations():
    """Donation totals — trips/km/dose/switched over all recorded days.

    `distinct_devices` is null BY DESIGN: hashed tokens exist only inside
    per-cell k-sets, so a city-wide device count is not computable and is
    never estimated (docs/plan/07 §3).
    """
    agg = TRIPS.city_aggregates() or {}
    days = agg.get("days") or {}
    tot = {"trips": 0, "km": 0.0, "dose_ug": 0.0, "co2_kg_mid": 0.0,
           "pm25_g_mid": 0.0, "switched": 0, "modes": {},
           "co2_moving_g": 0.0, "co2_idle_g": 0.0, "co2_cold_g": 0.0,
           "co2_split_trips": 0}
    for d in days.values():
        tot["trips"] += int(d.get("trips") or 0)
        for k in ("km", "dose_ug", "co2_kg_mid", "pm25_g_mid",
                  "co2_moving_g", "co2_idle_g", "co2_cold_g"):
            tot[k] += float(d.get(k) or 0.0)
        tot["co2_split_trips"] += int(d.get("co2_split_trips") or 0)
        tot["switched"] += int(d.get("switched") or 0)
        for m, n in (d.get("modes") or {}).items():
            tot["modes"][m] = tot["modes"].get(m, 0) + int(n)
    totals = {
        "trips": tot["trips"],
        "km": round(tot["km"], 1),
        "dose_ug": round(tot["dose_ug"], 1),
        "co2_kg_mid": round(tot["co2_kg_mid"], 2),
        "pm25_g_mid": round(tot["pm25_g_mid"], 3),
        "switched": tot["switched"],
        "modes": tot["modes"],
        # derived per-trip means — null (not 0) while trips==0, so the
        # dashboard can show 'no data' instead of a fake-zero average
        "avg_dose_per_trip_ug": (round(tot["dose_ug"] / tot["trips"], 1)
                                 if tot["trips"] else None),
        "avg_km_per_trip": (round(tot["km"] / tot["trips"], 2)
                            if tot["trips"] else None),
        "dose_ug_per_km": (round(tot["dose_ug"] / tot["km"], 1)
                           if tot["km"] else None),
    }
    # where the donated rides' CO2 comes from — summed ONLY over trips
    # whose receipts carried a real phase split (older builds donate
    # totals but no split; they count in co2_kg_mid, not here)
    _ssum = tot["co2_moving_g"] + tot["co2_idle_g"] + tot["co2_cold_g"]
    totals["co2_split"] = (None if not tot["co2_split_trips"] else {
        "trips": tot["co2_split_trips"],
        "moving_g": round(tot["co2_moving_g"], 1),
        "idle_g": round(tot["co2_idle_g"], 1),
        "cold_g": round(tot["co2_cold_g"], 1),
        "pct": ({"moving": round(100.0 * tot["co2_moving_g"] / _ssum, 1),
                 "idle": round(100.0 * tot["co2_idle_g"] / _ssum, 1),
                 "cold": round(100.0 * tot["co2_cold_g"] / _ssum, 1)}
                if _ssum > 0 else None),
        "note": "of trips whose receipts carried the phase split — "
                "moving vs idling vs cold-start",
    })
    # mode share across all donated trips (day counters — not per-cell,
    # so this is every recorded trip, not only the k>=3 corridor set)
    mode_share = sorted(
        ({"mode": m, "trips": n,
          "pct": round(100.0 * n / tot["trips"], 1) if tot["trips"] else None}
         for m, n in tot["modes"].items()),
        key=lambda r: -(r["trips"] or 0))
    # the live feed — UTC-hour aggregates, newest first. A row only
    # appears when its hour holds >=3 distinct hashed devices (the
    # corridor k-anonymity contract); per-trip rows would collapse to
    # a single person's journey — that was the feed's leak.
    try:
        recent = TRIPS.recent(20)
    except Exception:  # noqa: BLE001 - a store without the ring degrades
        recent = []
    return {
        "ts": time.time(),
        "window_s": CORRIDOR_WINDOW_S,
        "totals": totals,
        "mode_share": mode_share,
        "recent": recent,
        "days": days,
        "n_days": len(days),
        "cells_tracked": agg.get("cells_tracked", 0),
        "corridors_publishable": agg.get("corridors_publishable", 0),
        "distinct_devices": None,
        "devices_note": ("no global device registry exists by design — "
                         "hashed tokens live only inside per-cell k-sets "
                         "(docs/plan/07 §3)"),
        "empty": tot["trips"] == 0,
    }


def _reviews() -> dict:
    """'Their reviews' rides the shared-picture feed — authored stars+notes,
    nothing linkable stored; bodies publish only at k>=3 (community.py)."""
    try:
        import community
        return community.reviews_summary()
    except Exception:  # noqa: BLE001
        return {"count": 0, "avg": None, "hist": {}, "notes": [],
                "notes_withheld": False,
                "basis": "reviews store unavailable"}


@router.get("/global")
async def global_view():
    """Global movement + savings view for the judges' dashboard.

    Answers three questions over the donated-trip aggregates:
      * users from which area — distinct hashed devices whose trip
        origins snapped to each district/sub-district (k>=3, else the
        row is suppressed and counted, never shown)
      * journeys from-to — origin-dest area pairs, same k>=3 device rule
      * impact — lifetime sums of reported savings only: avoided_ug
        counts just the trips whose app computed router-fastest minus
        taken dose; co2_avoided_kg counts only PUC-calibrated receipts.
        A null block means no trip ever reported that figure — honest
        absence, not a fake zero.

    Everything comes from TripAggregates.global_aggregates(); this layer
    re-asserts the invariant rather than re-checking the math."""
    try:
        g = TRIPS.global_aggregates() or {}
    except AttributeError:
        g = {}
    except Exception:  # noqa: BLE001 - degrade, dashboard must live
        g = {}
    areas = g.get("areas") or []
    od = g.get("od_pairs") or []
    assert all(int(r.get("devices") or 0) >= K_MIN for r in areas + od), \
        "k>=3 invariant violated upstream — refusing to publish"
    return {
        "ts": time.time(),
        "k_min": K_MIN,
        "window": "all recorded days",
        "areas": areas,
        "od_pairs": od,
        "suppressed": g.get("suppressed") or {"areas": 0, "od_pairs": 0},
        "areas_tracked": g.get("areas_tracked", 0),
        "od_pairs_tracked": g.get("od_pairs_tracked", 0),
        "dose_avoided": g.get("avoided"),
        "co2_avoided": g.get("co2_avoided"),
        "reviews": _reviews(),
        "note": ("areas are district names resolved from the trimmed "
                 "endpoint — a granularity coarser than the corridor "
                 "cells; suppressed rows are counted, never shown; "
                 "savings blocks are null when no donated trip ever "
                 "reported them"),
        "empty": not (areas or od or g.get("avoided")
                      or g.get("co2_avoided")),
    }


@router.get("/validation")
async def validation():
    """Latest rollup outputs on disk — weekly LOSO/archive-replay and the
    newest daily city summary. Absent files -> nulls + a status string,
    not a fabricated scorecard."""
    weekly = _latest_validation()
    daily = _latest_daily()
    report_md = os.path.exists(
        os.path.join(_DATA_DIR, "field_validation.md"))
    return {
        "ts": time.time(),
        "status": ("ok" if (weekly or daily)
                   else "no rollup outputs on disk yet"),
        "weekly": weekly,
        "daily": daily,
        "report_md": report_md,
    }
