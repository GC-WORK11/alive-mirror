"""Build server/data/delhi_climatology.json.gz from the OpenAQ public archive.

Data source — S3 open data bucket, PUBLIC-READ, no AWS account needed:
  base   https://openaq-data-archive.s3.amazonaws.com/
  layout records/csv.gz/locationid=<id>/year=<yyyy>/month=<mm>/location-<id>-<yyyymmdd>.csv.gz
  file   gzip CSV: location_id,sensors_id,location,datetime,lat,lon,parameter,units,value
         (datetime carries a timezone offset; Delhi rows are +05:30 already)
Verified 2026-10-01 against https://docs.openaq.org/aws/about and live listing.

This module uses plain HTTPS + XML listing (urllib) so it runs with zero
credentials. Equivalent boto3 usage (build-time only dependency):
    boto3.client("s3", config=Config(signature_version=UNSIGNED))
    requirements.txt therefore includes: boto3

Pipeline (each phase resumable; intermediates land in server/data/_cache/):
  discover  enumerate every `locationid=` prefix (~56k), range-read the first
            day-file of each for lat/lon, keep points inside the NCR bbox
            (76.80-77.90 lon, 28.20-28.95 lat) or within ~30 km of an
            airfield.STATIONS coordinate.
  pull      list all day-file keys per kept location, download each (stride >
            1 subsamples days evenly), parse rows, pool values per
            (station, pollutant, month, hour_IST).
  aggregate p25/median/p75 per bucket (buckets with < MIN_N samples are
            dropped), plus a city-wide curve pooled across all stations.

Stations: every OpenAQ location inside NCR is a climatology station. OpenAQ
locations whose token set contains a canonical station's tokens AND sit
within 10 km of an airfield.STATIONS point are merged into that station (OpenAQ has issued several location ids per physical
site over the years — pooling them fills coverage gaps). Everything else
stays as its own station under its OpenAQ id.

Usage:
    python3.12 history_builder.py all                       # full pipeline
    python3.12 history_builder.py discover                  # discovery only
    python3.12 history_builder.py pull --years 2019-2024 --stride 1
    python3.12 history_builder.py aggregate

Runtime is dominated by HTTP: discovery ~55k small requests (~20 min),
pull ~1 request per station-day (100k files ~= 45-60 min). All numbers in
the emitted artifact come from real archived measurements — nothing is
synthesized.
"""
import argparse
import csv
import gzip
import io
import json
import math
import os
import re
import statistics
import sys
import time
import urllib.parse
import urllib.request
import zlib
import concurrent.futures as cf
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from airfield import STATIONS  # canonical NCR station registry (do not duplicate)

BASE = "https://openaq-data-archive.s3.amazonaws.com/"
LIST_PREFIX = "records/csv.gz/locationid={lid}/"

NCR_BBOX = (76.80, 28.20, 77.90, 28.95)   # lon_min, lat_min, lon_max, lat_max
NEAR_KM = 30.0                            # station proximity radius for discovery
IST = timezone(timedelta(hours=5, minutes=30))
POLLUTANTS = ("pm25", "pm10", "no2")      # archive names; pm25 = PM2.5
GOOD_UNITS = {"µg/m³", "µg/m3", "ug/m3", "μg/m³", "µg/m%C2%B3"}  # seen spellings
MIN_N = 8                                 # min samples to emit a bucket

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "data", "_cache")        # intermediates, not committed
OUT = os.path.join(HERE, "data", "delhi_climatology.json.gz")

PROBE_CACHE = os.path.join(CACHE, "probe_results.jsonl")
IDS_CACHE = os.path.join(CACHE, "all_ids.json")
LOC_CACHE = os.path.join(CACHE, "ncr_locations.json")
KEYS_CACHE = os.path.join(CACHE, "ncr_keys.json")
RAW_DIR = os.path.join(CACHE, "values")             # per-station value dumps


def _get(url, timeout=30, retries=3):
    last = None
    for i in range(retries):
        try:
            return urllib.request.urlopen(url, timeout=timeout).read()
        except Exception as e:                      # noqa: BLE001 - offline tool
            last = e
            time.sleep(0.6 * (i + 1))
    raise last


def _list(prefix, delimiter=False, max_keys=1000, token=None):
    url = (f"{BASE}?list-type=2&prefix={urllib.parse.quote(prefix)}"
           f"&max-keys={max_keys}")
    if delimiter:
        url += "&delimiter=/"
    if token:
        url += "&continuation-token=" + urllib.parse.quote(token)
    xml = _get(url).decode()
    keys = re.findall(r"<Key>([^<]+)</Key>", xml)
    prefs = re.findall(r"<Prefix>([^<]+)</Prefix>", xml)
    nxt = re.search(r"<NextContinuationToken>([^<]+)", xml)
    return keys, prefs, (nxt.group(1) if nxt else None)


def _in_ncr(lat, lon):
    if NCR_BBOX[0] <= lon <= NCR_BBOX[2] and NCR_BBOX[1] <= lat <= NCR_BBOX[3]:
        return True
    return any(math.hypot((s["lat"] - lat) * 111.0,
                          (s["lon"] - lon) * 111.0 * math.cos(math.radians(lat)))
               <= NEAR_KM for s in STATIONS)


# ---------------------------------------------------------------- discover
def _enum_ids():
    """All locationid= prefixes in the archive (~56k)."""
    ids, token = [], None
    while True:
        _, prefs, token = _list("records/csv.gz/", delimiter=True, token=token)
        ids += [int(m.group(1)) for p in prefs
                if (m := re.search(r"locationid=(\d+)/", p))]
        if not token:
            break
    return sorted(set(ids))


def _probe(lid):
    """Return {id,lat,lon,name,first_key} or {id,err}."""
    try:
        keys, _, _ = _list(LIST_PREFIX.format(lid=lid), max_keys=1)
        if not keys:
            return {"id": lid, "err": "no-key"}
        req = urllib.request.Request(BASE + keys[0],
                                     headers={"Range": "bytes=0-8191"})
        raw = urllib.request.urlopen(req, timeout=25).read()
        d = zlib.decompressobj(zlib.MAX_WBITS | 16)
        text = d.decompress(raw).decode(errors="replace")
        for row in csv.DictReader(io.StringIO(text)):
            if row.get("lat") and row.get("lon"):
                return {"id": lid, "lat": float(row["lat"]),
                        "lon": float(row["lon"]), "name": row.get("location"),
                        "first_key": keys[0], "first_dt": row.get("datetime")}
        return {"id": lid, "err": "no-coords", "key": keys[0]}
    except Exception as e:                          # noqa: BLE001
        return {"id": lid, "err": f"{type(e).__name__}:{str(e)[:80]}"}


def _probe_wide(lid):
    """Second-chance probe for no-coords ids: read 256KB of the first file
    and of the newest file (scan year prefixes newest-first)."""
    def try_key(key, nbytes):
        req = urllib.request.Request(BASE + key,
                                     headers={"Range": f"bytes=0-{nbytes - 1}"})
        d = zlib.decompressobj(zlib.MAX_WBITS | 16)
        text = d.decompress(urllib.request.urlopen(req, timeout=30).read())
        for row in csv.DictReader(io.StringIO(text.decode(errors="replace"))):
            if row.get("lat") and row.get("lon"):
                return float(row["lat"]), float(row["lon"]), row.get("location")
        return None
    try:
        keys, _, _ = _list(LIST_PREFIX.format(lid=lid), max_keys=200)
        if not keys:
            return None
        for key in (keys[0], keys[-1]):
            try:
                got = try_key(key, 262144)
            except Exception:                       # noqa: BLE001
                got = None
            if got:
                return {"id": lid, "lat": got[0], "lon": got[1],
                        "name": got[2], "first_key": keys[0]}
        return None
    except Exception:                               # noqa: BLE001
        return None


def discover(workers=64):
    os.makedirs(CACHE, exist_ok=True)
    if os.path.exists(IDS_CACHE):
        ids = json.load(open(IDS_CACHE))
    else:
        print("enumerating location prefixes…")
        ids = _enum_ids()
        json.dump(ids, open(IDS_CACHE, "w"))
    print(f"{len(ids)} location ids")

    seen = set()
    if os.path.exists(PROBE_CACHE):
        with open(PROBE_CACHE) as f:
            for line in f:
                seen.add(json.loads(line)["id"])
    todo = [i for i in ids if i not in seen]
    print(f"probing {len(todo)} locations ({len(seen)} cached)")
    out = open(PROBE_CACHE, "a")
    done = ncr = err = 0
    t = time.time()
    with cf.ThreadPoolExecutor(workers) as ex:
        for r in ex.map(_probe, todo):
            done += 1
            out.write(json.dumps(r) + "\n")
            if "err" not in r and _in_ncr(r["lat"], r["lon"]):
                ncr += 1
                print("  NCR:", r["id"], r["name"])
            if "err" in r:
                err += 1
            if done % 2000 == 0:
                print(f"  {done}/{len(todo)} {done/(time.time()-t):.0f}/s "
                      f"ncr={ncr} err={err}", flush=True)
    out.close()

    # second pass: no-coords ids get a wider read
    rows = [json.loads(l) for l in open(PROBE_CACHE)]
    retry = [r["id"] for r in rows if r.get("err") == "no-coords"]
    if retry:
        print(f"wide re-probe on {len(retry)} no-coords locations")
        fixed = {}
        with cf.ThreadPoolExecutor(workers) as ex:
            for r in ex.map(_probe_wide, retry):
                if r:
                    fixed[r["id"]] = r
        if fixed:
            with open(PROBE_CACHE, "a") as f:
                for r in fixed.values():
                    f.write(json.dumps(r) + "\n")
            print(f"  recovered {len(fixed)} (ncr: "
                  f"{sum(1 for r in fixed.values() if _in_ncr(r['lat'], r['lon']))})")
    rows = [json.loads(l) for l in open(PROBE_CACHE)]
    best = {}
    for r in rows:                      # later entries (wide probe) override
        best[r["id"]] = r
    ncr_locs = [r for r in best.values() if "lat" in r and _in_ncr(r["lat"], r["lon"])]
    json.dump(ncr_locs, open(LOC_CACHE, "w"), indent=1)
    print(f"discover done: {len(ncr_locs)} NCR locations")
    return ncr_locs


# ---------------------------------------------------------------- pull
_AGENCY_CITY_TOKENS = {"cpcb", "dpcc", "imd", "hspcb", "uppcb", "iitm",
                       "mhua", "rspcb", "new", "delhi", "ncr", "uttar",
                       "pradesh", "india"}

# sorted-alpha-token joins -> canonical token set (abbreviations/splits)
_NAME_ALIAS = {
    "k puram r": "rk puram",                     # "R K Puram, Delhi - DPCC"
    "technological university": "dtu",           # "Delhi Technological Univ."
    "fort siri": "sirifort",                     # "Siri Fort" spelling
}


def _tokens(name):
    """Word tokens of a station name, lower-cased, minus agencies/cities."""
    out = set()
    for t in re.findall(r"[a-z]+|\d+", (name or "").lower()):
        if t in _AGENCY_CITY_TOKENS:
            continue
        if t == "sec":
            t = "sector"
        elif t == "ph":
            t = "phase"
        out.add(t)
    joined = " ".join(sorted(t for t in out if not t.isdigit()))
    if joined in _NAME_ALIAS:
        out = set(_NAME_ALIAS[joined].split())
    return out


_CANON_TOKENS = [(s, _tokens(s["name"])) for s in STATIONS]


def _station_key(loc):
    """Cluster an OpenAQ location to a canonical STATIONS entry.

    A canonical station claims the location when its token set is a subset
    of the location's (the OpenAQ name may carry agency suffixes/id digits)
    AND the coordinates are within 10 km — guards against same-named sites
    elsewhere (e.g. "Anand Vihar, Hapur" ~40 km away) and stops unrelated
    low-cost sensors from diluting a canonical station's climatology.
    Everything else stays its own station under its OpenAQ name."""
    lt = _tokens(loc["name"])
    if lt:
        for s, ct in _CANON_TOKENS:
            if ct and ct <= lt:
                d = math.hypot((s["lat"] - loc["lat"]) * 111.0,
                               (s["lon"] - loc["lon"]) * 111.0
                               * math.cos(math.radians(loc["lat"])))
                if d <= 10.0:
                    return ("stn", s["name"], s["lat"], s["lon"])
    return ("loc", loc["name"] or f"openaq-{loc['id']}", loc["lat"], loc["lon"])


def _all_keys(lid):
    keys, token = [], None
    while True:
        ks, _, token = _list(LIST_PREFIX.format(lid=lid), token=token)
        keys += ks
        if not token:
            return keys


def _key_year(key):
    m = re.search(r"year=(\d{4})", key)
    return int(m.group(1)) if m else 0


def _iter_values(key):
    """Yield (param, month_ist, hour_ist, value) from one day file."""
    raw = _get(BASE + key, timeout=40)
    text = gzip.decompress(raw).decode(errors="replace")
    for row in csv.DictReader(io.StringIO(text)):
        p = row.get("parameter")
        u = (row.get("units") or "").strip()
        if p not in POLLUTANTS or u not in GOOD_UNITS:
            continue
        try:
            v = float(row["value"])
        except (TypeError, ValueError):
            continue
        if not (0.0 <= v < 2000.0):
            continue
        try:
            dt = datetime.fromisoformat(row["datetime"].replace("Z", "+00:00"))
        except (TypeError, ValueError):
            continue
        dt = dt.astimezone(IST)
        yield p, dt.month, dt.hour, v


def pull(year_lo=2016, year_hi=2100, stride=1, workers=48):
    """Download files and dump per-station value rows into RAW_DIR.

    Each output line: {"s": station_key, "loc": openaq_id, "file": key,
                      "v": [[param_idx, month, hour, value], ...]}
    """
    locs = json.load(open(LOC_CACHE))
    os.makedirs(RAW_DIR, exist_ok=True)

    # per-location key lists (cached — re-runs don't re-list)
    if os.path.exists(KEYS_CACHE):
        allk = {int(k): v for k, v in json.load(open(KEYS_CACHE)).items()}
    else:
        allk = {}
    for loc in locs:
        if loc["id"] not in allk:
            allk[loc["id"]] = _all_keys(loc["id"])
            json.dump(allk, open(KEYS_CACHE, "w"))
    print("key listing complete")

    # choose files: year window + stride subsample, canonical stations stride 1
    jobs = []          # (loc, key)
    for loc in locs:
        stn = _station_key(loc)
        ks = [k for k in allk[loc["id"]] if year_lo <= _key_year(k) <= year_hi]
        eff_stride = 1 if stn[0] == "stn" else stride
        ks = ks[::eff_stride]
        for k in ks:
            jobs.append((loc, k))
    print(f"{len(jobs)} files to pull from {len(locs)} locations")

    sink = open(os.path.join(RAW_DIR, "values.jsonl"), "a+")
    sink.seek(0)
    done_files = set()
    for line in sink:
        try:
            done_files.add(json.loads(line)["file"])
        except Exception:                           # noqa: BLE001
            pass
    todo = [(l, k) for l, k in jobs if k not in done_files]
    print(f"{len(todo)} new ({len(done_files)} already pulled)")

    def one(job):
        loc, key = job
        try:
            rows = [[POLLUTANTS.index(p), mo, h, v]
                    for p, mo, h, v in _iter_values(key)]
            return {"s": list(_station_key(loc)), "loc": loc["id"],
                    "file": key, "v": rows}
        except Exception as e:                      # noqa: BLE001
            return {"file": key, "err": str(e)[:100]}

    n = 0
    t = time.time()
    with cf.ThreadPoolExecutor(workers) as ex:
        for r in ex.map(one, todo):
            sink.write(json.dumps(r) + "\n")
            n += 1
            if n % 2000 == 0:
                sink.flush()
                print(f"  {n}/{len(todo)} {n/(time.time()-t):.0f}/s",
                      flush=True)
    sink.close()
    print("pull done")


# ---------------------------------------------------------------- aggregate
def _q(vals):
    """[p25, median, p75] rounded to 2 decimals."""
    vs = sorted(vals)
    n = len(vs)
    med = statistics.median(vs)
    if n < 4:
        return [round(vs[0], 2), round(med, 2), round(vs[-1], 2)]
    q1, _, q3 = statistics.quantiles(vs, n=4, method="inclusive")
    return [round(q1, 2), round(med, 2), round(q3, 2)]


def aggregate():
    # station_key -> {meta}, station_key -> param -> month -> hour -> [values]
    from collections import defaultdict
    vals = defaultdict(lambda: defaultdict(
        lambda: defaultdict(lambda: defaultdict(list))))
    smeta = {}
    city = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    nfiles = nrows = 0

    def stn_info(sk):
        kind, name, lat, lon = sk
        return {"kind": kind, "name": name, "lat": lat, "lon": lon,
                "lids": set(), "first": None, "last": None, "years": set()}

    loc_by_id = {l["id"]: l for l in json.load(open(LOC_CACHE))}

    for line in open(os.path.join(RAW_DIR, "values.jsonl")):
        r = json.loads(line)
        if "err" in r:
            continue
        nfiles += 1
        loc = loc_by_id.get(r["loc"])
        sk = _station_key(loc) if loc else tuple(r["s"])
        meta = smeta.setdefault(sk, stn_info(sk))
        meta["lids"].add(r["loc"])
        d = re.search(r"location-\d+-(\d{8})\.csv\.gz", r["file"])
        if d:
            ds = d.group(1)
            meta["first"] = min(meta["first"] or ds, ds)
            meta["last"] = max(meta["last"] or ds, ds)
            meta["years"].add(int(ds[:4]))
        for pidx, mo, h, v in r["v"]:
            p = POLLUTANTS[pidx]
            vals[sk][p][str(mo)][str(h)].append(v)
            city[p][str(mo)][str(h)].append(v)
            nrows += 1
    print(f"{nfiles} files, {nrows} measurements, {len(smeta)} stations")

    stations = []
    for sk, meta in smeta.items():
        m = {}
        for p, months in vals[sk].items():
            for mo, hours in months.items():
                cell = m.setdefault(mo, {})
                for h, vs in hours.items():
                    if len(vs) >= MIN_N:
                        cell.setdefault(h, {})[p] = _q(vs)
        kind, name, lat, lon = sk
        stations.append({
            "id": "/".join(str(x) for x in sorted(meta["lids"])),
            "name": name, "lat": lat, "lon": lon,
            "kind": "canonical" if kind == "stn" else "extra",
            "openaq_ids": sorted(meta["lids"]),
            "first_seen": meta["first"], "last_seen": meta["last"],
            "years": sorted(meta["years"]),
            "buckets": sum(len(hs) for hs in m.values()),
            "m": m,
        })
    stations.sort(key=lambda s: (s["kind"] != "canonical", s["name"]))

    citym = {}
    for p, months in city.items():
        for mo, hours in months.items():
            cell = citym.setdefault(mo, {})
            for h, vs in hours.items():
                if len(vs) >= MIN_N:
                    cell.setdefault(h, {})[p] = _q(vs)

    out = {
        "source": "openaq-data-archive s3://openaq-data-archive/records/csv.gz "
                  "(public, measurements only)",
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "pollutants": list(POLLUTANTS),
        "units": "µg/m³",
        "bucket": "month x hour-of-day IST -> [p25, median, p75]",
        "stations": stations,
        "city": citym,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with gzip.open(OUT, "wt", encoding="utf-8") as f:
        json.dump(out, f, separators=(",", ":"))
    size = os.path.getsize(OUT)
    print(f"wrote {OUT} ({size/1024:.0f} KiB gz)")

    print("\ncoverage (stations, year range):")
    for s in stations:
        print(f"  {s['name']:<46} ids={s['id']:<18} "
              f"{str(s['years'][0]) if s['years'] else '?'}-"
              f"{s['years'][-1] if s['years'] else '?'} "
              f"buckets={s['buckets']}")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("phase", choices=["discover", "pull", "aggregate", "all"])
    ap.add_argument("--years", default="2016-2100",
                    help="year window, e.g. 2019-2024")
    ap.add_argument("--stride", type=int, default=1,
                    help="keep every Nth day file (non-canonical stations)")
    ap.add_argument("--workers", type=int, default=48)
    a = ap.parse_args()
    y0, y1 = (int(x) for x in a.years.split("-"))
    if a.phase in ("discover", "all"):
        discover(workers=a.workers)
    if a.phase in ("pull", "all"):
        pull(y0, y1, stride=a.stride, workers=a.workers)
    if a.phase in ("aggregate", "all"):
        aggregate()


if __name__ == "__main__":
    main()
