"""Pull the most recent ~48h of Delhi NCR station observations from the
OpenAQ public S3 archive into a refreshable CSV cache.

Why this exists: the live OpenAQ v3 API needs an API key, and when the key
is unavailable the air field runs on the CAMS model grid alone. The S3
archive needs NO key and keeps every CAAQMS/CPCB measurement ever taken —
it lags real time by ~1-2 days, so this is a VALIDATION source (ground
truth for "did the field say the right thing yesterday"), not a live feed.

Archive layout (anonymous HTTPS, same as history_builder.py):
  https://openaq-data-archive.s3.amazonaws.com/
  records/csv.gz/locationid=<id>/year=<yyyy>/month=<mm>/location-<id>-<yyyymmdd>.csv.gz
  gzip CSV: location_id,sensors_id,location,datetime,lat,lon,parameter,units,value
  (datetime carries the +05:30 offset already for Delhi stations)

Station registry: server/data/delhi_climatology.json.gz was built by
history_builder.discover() — 125 NCR stations, each carrying the OpenAQ
location ids ("openaq_ids") that ever reported from that site. We reuse it
instead of re-enumerating ~56k archive prefixes; dead ids simply return no
recent files.

Output:
  data/openaq_recent.csv       one row per measurement (freshest days only)
  data/openaq_recent_meta.json pull timestamp, coverage, freshest hour seen

Usage:
    python openaq_archive.py pull [days]      # refresh the cache (default 3 days)
    python openaq_archive.py status           # summarize the cache
    from openaq_archive import load_recent    # hourly pm25 per station, last N h
"""
import argparse
import concurrent.futures as cf
import csv
import gzip
import io
import json
import os
import re
import sys
import time
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from history_builder import (  # noqa: E402 - shared archive machinery
    BASE, GOOD_UNITS, IST, LIST_PREFIX, _get, _list,
)

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
OUT_CSV = os.path.join(DATA, "openaq_recent.csv")
OUT_META = os.path.join(DATA, "openaq_recent_meta.json")
CLIMATOLOGY = os.path.join(DATA, "delhi_climatology.json.gz")

PARAMS = {"pm25", "pm10"}   # pm25 is the field's pollutant; pm10 rides along
CSV_FIELDS = ["openaq_id", "station", "lat", "lon", "datetime", "parameter",
              "units", "value"]


def _registry():
    """NCR stations + their OpenAQ location ids from the committed
    climatology artifact (built from this same archive — see
    history_builder.py)."""
    db = json.load(gzip.open(CLIMATOLOGY))
    out = []
    for s in db["stations"]:
        out.append({"station": s["name"], "lat": s["lat"], "lon": s["lon"],
                    "openaq_ids": list(s.get("openaq_ids") or [])})
    return out


def _recent_keys(lid, days):
    """Day-file keys for the freshest `days` dates present in the archive.

    The archive lags real time ~1-2 days, so we list the current month and
    the previous one (covers a window spanning a month boundary) and keep
    the newest `days` dates that actually have files — dead stations yield
    nothing, stale stations yield their last data."""
    now = datetime.now(timezone.utc)
    prev = (now.replace(day=1) - timedelta(days=1))
    keys = []
    for y, m in {(now.year, now.month), (prev.year, prev.month)}:
        ks, _, _ = _list(LIST_PREFIX.format(lid=lid) +
                         f"year={y}/month={m:02d}/", max_keys=1000)
        keys += ks
    dated = {}
    for k in keys:
        m = re.search(r"location-\d+-(\d{8})\.csv\.gz$", k)
        if m:
            dated.setdefault(m.group(1), []).append(k)
    freshest = sorted(dated)[-days:]
    return [k for d in freshest for k in dated[d]]


def _parse(key, meta):
    """Rows of one day-file as CSV dicts for OUT_CSV."""
    text = gzip.decompress(_get(BASE + key, timeout=40)).decode(errors="replace")
    rows = []
    for row in csv.DictReader(io.StringIO(text)):
        p = row.get("parameter")
        if p not in PARAMS or (row.get("units") or "").strip() not in GOOD_UNITS:
            continue
        try:
            v = float(row["value"])
        except (TypeError, ValueError):
            continue
        if not (0.0 <= v < 2000.0):
            continue
        rows.append({"openaq_id": meta["openaq_id"], "station": meta["station"],
                     "lat": meta["lat"], "lon": meta["lon"],
                     "datetime": row.get("datetime"), "parameter": p,
                     "units": (row.get("units") or "").strip(),
                     "value": v})
    return rows


def _pull_station(stn, days):
    """All recent day-files across every openaq_id of one station."""
    rows, files = [], 0
    for lid in stn["openaq_ids"]:
        try:
            keys = _recent_keys(lid, days)
        except Exception:                       # noqa: BLE001 - offline tool
            continue
        for k in keys:
            try:
                meta = {"openaq_id": lid, "station": stn["station"],
                        "lat": stn["lat"], "lon": stn["lon"]}
                rows += _parse(k, meta)
                files += 1
            except Exception:                   # noqa: BLE001
                continue
    return stn["station"], rows, files


def pull(days=3, workers=32):
    """Refresh data/openaq_recent.csv with the freshest `days` of archive
    days per station. `days` defaults to 3 so the trailing-48h window stays
    covered even when a station's newest day is partial."""
    os.makedirs(DATA, exist_ok=True)
    stations = _registry()
    t = time.time()
    all_rows, live, files = [], 0, 0
    with cf.ThreadPoolExecutor(workers) as ex:
        for name, rows, nfiles in ex.map(lambda s: _pull_station(s, days),
                                       stations):
            files += nfiles
            if rows:
                live += 1
                all_rows += rows
    all_rows.sort(key=lambda r: (r["station"], r["datetime"] or ""))
    with open(OUT_CSV, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        w.writeheader()
        w.writerows(all_rows)

    dts = sorted(r["datetime"] for r in all_rows if r["datetime"])
    meta = {
        "pulled_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": "s3://openaq-data-archive/records/csv.gz (anonymous HTTPS)",
        "note": "archive lags ~1-2 days — validation source, not a live feed",
        "stations_with_data": live,
        "stations_registry": len(stations),
        "day_files": files,
        "rows": len(all_rows),
        "freshest": dts[-1] if dts else None,
        "oldest": dts[0] if dts else None,
        "elapsed_s": round(time.time() - t, 1),
    }
    json.dump(meta, open(OUT_META, "w"), indent=1)
    print(json.dumps(meta, indent=1))
    return meta


def _hour(dt_str):
    """'2026-09-30T14:45:00+05:30' -> naive IST hour '2026-09-30T14'."""
    try:
        dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return dt.astimezone(IST).replace(minute=0, second=0, microsecond=0)


def load_recent(parameter="pm25", hours=48):
    """{station: {lat, lon, series: {ist_hour_naive: median value}}}.

    The window is the trailing `hours` ending at the freshest timestamp in
    the cache — anchored to the data, not the wall clock, because the
    archive lags real time."""
    if not os.path.exists(OUT_CSV):
        return {}
    buckets = {}
    freshest = None
    for row in csv.DictReader(open(OUT_CSV)):
        if row["parameter"] != parameter:
            continue
        h = _hour(row["datetime"])
        if h is None:
            continue
        freshest = h if freshest is None or h > freshest else freshest
        st = buckets.setdefault(row["station"], {
            "lat": float(row["lat"]), "lon": float(row["lon"]),
            "series": {}})
        st["series"].setdefault(h, []).append(float(row["value"]))
    if freshest is None:
        return {}
    cutoff = freshest - timedelta(hours=hours - 1)
    out = {}
    for name, st in buckets.items():
        ser = {h: sorted(v)[len(v) // 2] for h, v in st["series"].items()
               if h >= cutoff}
        if ser:
            out[name] = {"lat": st["lat"], "lon": st["lon"], "series": ser}
    return out


def status():
    meta = json.load(open(OUT_META)) if os.path.exists(OUT_META) else None
    recent = load_recent()
    print(json.dumps({"meta": meta,
                      "stations_48h": len(recent)}, indent=1, default=str))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["pull", "status"], nargs="?", default="pull")
    ap.add_argument("days", nargs="?", type=int, default=3)
    a = ap.parse_args()
    if a.cmd == "pull":
        pull(days=a.days)
    else:
        status()
