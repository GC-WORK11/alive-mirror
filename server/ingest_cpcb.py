"""data.gov.in CPCB live-AQI adapter — station observations for the 15-min
air index (docs/plan/05-backend-architecture.md §2 "CPCB/OpenAQ station
readings"). Full endpoint notes + signup flow: docs/plan/cpcb-source.md.

Source: OGD Platform India datastore API
  GET https://api.data.gov.in/resource/{resource_id}
      ?api-key=$CPCB_API_KEY&format=json&limit=1000&offset=N
      &filters[state]=Delhi&filters[pollutant_id]=PM2.5
resource 3b01bcb8-0b14-4abf-b6f2-c1bfd384ba69 = "Real time Air Quality Index
from various locations" (publisher: Central Pollution Control Board, catalog
a3e7afc6-b799-4ede-b143-8e074b27e062 — verified live on the portal).

Records are one row per (station, pollutant):
  id, country, state, city, station, last_update (IST, "DD-MM-YYYY HH:MM:SS"),
  pollutant_id, pollutant_min, pollutant_max, pollutant_avg, pollutant_unit.
NO lat/lon — coordinates are resolved from the committed NCR station
registry data/delhi_climatology.json.gz (same artifact openaq_archive.py
uses; its names share the CPCB "Name, City - AGENCY" convention). Stations
that don't resolve are skipped and counted, never placed by guessing.

Emits the SAME bundle shape airindex._fetch_stations returns, so it drops
straight into inputs["stations"] of airindex.build_field():
  {"status": "ok"|"unavailable: ...", "source": "data.gov.in-cpcb",
   "fetched_at": epoch, "stations": [{name, lat, lon, pm25, ts, series,
   pollutants}], "report": {...counts...}}

QC stays in airindex.qc_stations (stale >3h on `ts`, flatline, >5-sigma
spike). `series` carries the row's [pollutant_min, pollutant_avg,
pollutant_max]: a fully frozen station (min==avg==max over the window)
trips the flatline rule; partial flatlines are not detectable from one
snapshot — same honest limit as any single-shot source.

api.data.gov.in is TCP-refused from this build box (see cpcb-source.md) —
the adapter is written + fixture-tested so it goes live the moment the
owner drops a key into CPCB_API_KEY from a network that can reach NIC.
"""
import gzip
import json
import math
import os
import re
import sys
import time
from datetime import datetime, timedelta, timezone

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import httpx  # noqa: E402

API_BASE = "https://api.data.gov.in"
RESOURCE_ID = "3b01bcb8-0b14-4abf-b6f2-c1bfd384ba69"   # real-time AQI
CATALOG_UUID = "a3e7afc6-b799-4ede-b143-8e074b27e062"  # CPCB AQI catalog
ENV_KEY = "CPCB_API_KEY"
SOURCE = "data.gov.in-cpcb"

# NCR bbox — mirrors airindex.BBOX (kept local so this module stays a
# standalone adapter; the consumer owns clipping too, we just pre-filter).
BBOX = (76.75, 28.15, 77.95, 28.98)

# state filter values use underscores (OGD convention). Delhi alone misses
# NCR stations in Gurugram/Noida/Ghaziabad/Faridabad that sit inside BBOX.
STATES = ("Delhi", "Haryana", "Uttar_Pradesh", "Rajasthan")
POLLUTANT = "PM2.5"          # the field's pollutant (doc 05 §2)
PAGE_LIMIT = 1000            # OGD datastore page size (default is 10)
MAX_PAGES = 4                # safety cap per state (~4k rows worst case)
MAX_PM25 = 1500.0            # same implausible bound as airindex's OpenAQ path

REGISTRY = os.path.join(_HERE, "data", "delhi_climatology.json.gz")

# agency suffixes seen on CPCB/OpenAQ station names: " - CPCB", " - DPCC
# -5760", " - HSPCB", " - UPPCB", " - IMD", " - IITM", " - MHUA", ...
_AGENCY_TAIL = re.compile(
    r"\s*-\s*([a-z]{0,4}pcb|imd|iitm|mhua|us embassy|us diplomatic"
    r"|dpcb|pcb)\b.*$", re.I)
_NUM_TAIL = re.compile(r"[-\s]+\d+$")
_STOP_TOKENS = {"delhi", "new", "india", "ncr", "nct", "ut"}

IST = timezone(timedelta(hours=5, minutes=30))  # last_update is stamped IST


def _norm_station(name: str) -> str:
    """Canonical station key shared by API names and registry names.
    'Income Tax Office, Delhi - CPCB' and 'Income Tax Office, Delhi -
    CPCB-103' both -> 'income tax office'."""
    s = _AGENCY_TAIL.sub("", (name or "").strip())
    s = _NUM_TAIL.sub("", s)
    toks = [t for t in re.split(r"[^0-9a-zA-Z]+", s.lower()) if t]
    return " ".join(t for t in toks if t not in _STOP_TOKENS)


def _registry() -> dict:
    """normalized-name -> (name, lat, lon) from the NCR station registry.
    First entry wins on normalized-name collisions (duplicates in the
    registry are the same physical site with different OpenAQ ids)."""
    out = {}
    try:
        db = json.load(gzip.open(REGISTRY))
    except OSError:
        return out
    for s in db.get("stations") or []:
        key = _norm_station(s.get("name") or "")
        if key and key not in out:
            out[key] = (s["name"], float(s["lat"]), float(s["lon"]))
    return out


def _parse_ts(raw) -> "float | None":
    """'28-02-2022 09:00:00' (IST) or ISO -> epoch seconds, else None.
    Naive timestamps on this feed are IST (UTC+05:30, no DST)."""
    if not raw or not isinstance(raw, str):
        return None
    s = raw.strip()
    for fmt in ("%d-%m-%Y %H:%M:%S", "%Y-%m-%d %H:%M:%S",
                "%d-%m-%Y %H:%M", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(s, fmt).replace(tzinfo=IST).timestamp()
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def parse_records(records, registry=None) -> tuple:
    """data.gov.in rows -> airindex station-obs list + skip report.

    -> (stations, report). Every skipped row increments a reason counter —
    nothing is silently dropped."""
    registry = _registry() if registry is None else registry
    skipped = {"no_station": 0, "bad_value": 0, "bad_ts": 0,
               "out_of_range": 0, "unresolved_coords": 0}
    unresolved = []
    by_station = {}
    for r in records or []:
        if not isinstance(r, dict):
            skipped["no_station"] += 1
            continue
        st_name = (r.get("station") or "").strip()
        if not st_name:
            skipped["no_station"] += 1
            continue
        pid = (r.get("pollutant_id") or "").strip().upper()
        try:
            avg = float(r.get("pollutant_avg"))
        except (TypeError, ValueError):
            avg = None
        if avg is None or not math.isfinite(avg):
            skipped["bad_value"] += 1
            continue
        ts = _parse_ts(r.get("last_update"))
        if ts is None:
            skipped["bad_ts"] += 1
        st = by_station.setdefault(st_name, {
            "name": st_name, "ts": ts, "pollutants": {},
            "_pm25_row": None})
        if ts is not None and (st["ts"] is None or ts > st["ts"]):
            st["ts"] = ts
        st["pollutants"][pid] = avg
        if pid in ("PM2.5", "PM25"):
            lo, hi = _fnum(r.get("pollutant_min")), _fnum(r.get("pollutant_max"))
            if st["_pm25_row"] is None or (ts or 0) >= \
                    (st["_pm25_row"].get("ts") or 0):
                st["_pm25_row"] = {"v": avg, "min": lo, "max": hi, "ts": ts}

    stations = []
    for st_name, st in by_station.items():
        row = st["_pm25_row"]
        if row is None:
            continue                      # no PM2.5 row — nothing to emit
        v = row["v"]
        if not (0.0 <= v <= MAX_PM25):
            skipped["out_of_range"] += 1
            continue
        reg = registry.get(_norm_station(st_name))
        if reg is None:
            skipped["unresolved_coords"] += 1
            unresolved.append(st_name)
            continue
        reg_name, lat, lon = reg
        series = [x for x in (row["min"], v, row["max"]) if x is not None]
        stations.append({
            "name": reg_name,             # registry name (single spelling)
            "lat": lat, "lon": lon,
            "pm25": float(v),
            "ts": st["ts"],
            "series": series,             # [min, avg, max] — see docstring
            "pollutants": st["pollutants"],
            "raw_station": st_name,       # as-reported name, for debugging
        })
    report = {"rows_in": len(records or []), "stations_out": len(stations),
              "skipped": skipped, "unresolved_names": sorted(unresolved)}
    return stations, report


def _fnum(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def fetch(resource_id: str = RESOURCE_ID, api_key=None, client=None,
          states=STATES, bbox=BBOX, limit: int = PAGE_LIMIT) -> dict:
    """Pull live CPCB station obs into the airindex stations bundle.

    api_key: default env CPCB_API_KEY. Absent -> status 'unavailable: no
    key — owner blocker' + empty stations (explicit, never silent).
    client: injectable httpx-like object (tests pass a fake); created and
    closed internally when not given. Never raises on upstream failure —
    the caller's field still builds on what arrived."""
    t0 = time.time()
    key = api_key or os.environ.get(ENV_KEY)
    if not key:
        out = {"status": "unavailable: no key — owner blocker",
               "source": SOURCE, "fetched_at": t0, "stations": [],
               "report": {"note": f"set ${ENV_KEY}; see docs/plan/"
                                  f"cpcb-source.md for the free signup"}}
        _remember(out)
        return out

    own = client is None
    c = client or httpx.Client(
        timeout=httpx.Timeout(30.0, connect=8.0),
        headers={"User-Agent": "alive108-ingest-cpcb/0.1"})
    records, errors, pages = [], [], 0
    try:
        for state in states:
            offset = 0
            for _ in range(MAX_PAGES):
                try:
                    r = c.get(f"{API_BASE}/resource/{resource_id}", params={
                        "api-key": key, "format": "json",
                        "filters[state]": state,
                        "filters[pollutant_id]": POLLUTANT,
                        "limit": limit, "offset": offset}, timeout=30)
                    r.raise_for_status()
                    j = r.json()
                    pages += 1
                except Exception as e:      # noqa: BLE001 - upstream wobble
                    errors.append(f"{state}@{offset}: {type(e).__name__}")
                    break
                if j.get("status") and str(j.get("status")).lower() != "ok":
                    errors.append(f"{state}@{offset}: "
                                  f"{j.get('message') or j.get('status')}")
                    break
                chunk = j.get("records") or []
                records += chunk
                total = int(j.get("total") or 0)
                offset += len(chunk)
                if not chunk or offset >= total or len(chunk) < limit:
                    break
    finally:
        if own:
            c.close()

    if not records and errors:
        out = {"status": f"unavailable: {errors[0].split(':')[0]}",
               "source": SOURCE, "fetched_at": t0, "stations": [],
               "report": {"errors": errors, "pages": pages}}
        _remember(out)
        return out

    stations, report = parse_records(records)
    if bbox is not None:
        w, s, e, n = bbox
        in_box = [st for st in stations
                  if s <= st["lat"] <= n and w <= st["lon"] <= e]
        report["outside_bbox"] = len(stations) - len(in_box)
        stations = in_box
    report.update({"pages": pages, "errors": errors,
                   "states": list(states), "resource_id": resource_id})
    out = {"status": "ok", "source": SOURCE, "fetched_at": time.time(),
           "stations": stations, "report": report}
    _remember(out)
    return out


_LAST = {}


def _remember(bundle: dict) -> None:
    """Keep the last fetch summary for status() (same-process lifetime —
    the 15-min worker is the only caller that matters)."""
    _LAST.clear()
    _LAST.update({"status": bundle["status"],
                  "fetched_at": bundle.get("fetched_at"),
                  "n_stations": len(bundle.get("stations") or []),
                  "report": bundle.get("report")})


def status(api_key=None) -> dict:
    """Adapter readiness for /health-style reporting. Honest about the
    blocker when the key is absent."""
    key = api_key or os.environ.get(ENV_KEY)
    out = {"source": SOURCE, "resource_id": RESOURCE_ID,
           "endpoint": f"{API_BASE}/resource/{RESOURCE_ID}",
           "key_env": ENV_KEY, "key_present": bool(key)}
    if not key:
        out["status"] = "no key — owner blocker"
        out["note"] = (f"set ${ENV_KEY} (free, data.gov.in account -> "
                       "API key; signup flow in docs/plan/cpcb-source.md)")
    else:
        out["status"] = (_LAST.get("status")
                         if _LAST else "key present — not fetched yet")
        out["last_fetch"] = _LAST or None
    return out


if __name__ == "__main__":
    print(json.dumps(status(), indent=1, default=str))
    res = fetch()
    rep = res.get("report") or {}
    rep.pop("unresolved_names", None)
    print(json.dumps({"status": res["status"],
                      "stations": len(res["stations"]),
                      "report": rep}, indent=1, default=str))
    for st in res["stations"][:8]:
        print(f"  {st['name']:<55} pm25={st['pm25']:<7} "
              f"ts={st['ts']}")
