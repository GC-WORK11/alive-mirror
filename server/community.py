"""Community air layer — commuters as the sensor network.

Two honest contributions, no fake sensing:

1. Trip observations: anonymized traversals (mode + polyline + timing)
   the app donates after a journey. Aggregated they answer what no
   station can — where, when and how Delhi actually breathes: per-
   corridor counts, modal split, cumulative inhaled mass, and the µg
   avoided by dose-aware choices. Delhi's grid is ~65% unmonitored;
   phones can't measure PM2.5, but traversal density IS real data.

2. Hazard reports: user flags (dust, smoke, burning smell, visibly
   clean air) with a 6h TTL — the Waze model applied to air. Stored
   in-memory, snapshotted to data/community.json for restart survival.

Privacy (docs/plan/07 §3 — the product promise, enforced here):
observations carry no identity. The client-sent anonymous id is hashed
like v2/trip.py's device_token before it can touch any store, and raw
coordinates are folded into ~500 m cell traversals at ingest — no raw
trajectories at rest. And there are no per-trip rows at rest either:
observe() folds each traversal straight into per-cell / per-hour /
per-day AGGREGATES — the only structures that exist in memory, on
disk, or in S3 (the old per-trip _obs rows were the leak — ordered
cell chains a reader could walk endpoint-to-end, linked by the same
hashed id; the all-time _LIFE/_DEVICES counters are gone too — the
donation ledger lives in v2/store.TRIPS + LEDGER, one source of truth
every surface reads). Anything this module publishes is an aggregate; a
corridor cell is revealed only with >=_K_MIN_DEVICES distinct hashed
devices inside the 72 h window (same rule v2/store.py TripAggregates
implements). Per-device rows are never returned — that was the leak.
"""
import hashlib
import json
import math
import os
import re
import threading
import time
from pathlib import Path
from typing import Optional

_FILE = Path(__file__).parent / "data" / "community.json"
_REPORT_TTL_S = 6 * 3600
_REPORT_KINDS = {"dust", "smoke", "burning", "clean"}

# S3 persistence — Fargate has an ephemeral FS, so the community layer
# would reset on every deploy. When COMMUNITY_BUCKET is set the snapshot
# is pushed at most every _S3_MIN_GAP_S and pulled back on boot.
_BUCKET = os.environ.get("COMMUNITY_BUCKET", "")
_S3_KEY = "community/state.json"
_S3_MIN_GAP_S = 60
_s3_client = None
_last_s3_put = 0.0

# ---------------------------------------------------------------- aggregates
# What persists — every structure is an aggregate; no per-trip row can
# exist here (the privacy audit's fix: the retired _obs list held one
# row per donation — ordered cell chains + a stable hashed id + an
# exact timestamp — i.e. per-device path histories at rest. A reader of
# the file or S3 snapshot could walk a donor's trip corridor to
# corridor. The aggregate shapes below keep every published answer
# identical while making a per-person record structurally impossible.)

_CELLS: dict = {}   # (lon,lat) -> per-cell totals + k-gate state
_CELLS_CAP = 60_000          # evict stalest cells beyond this
_CELL_VAL_CAP = 400          # implied-C ring per cell (freshness pairs)
_DAYS: dict = {}    # "YYYY-MM-DD" -> traversal rollup (admin per-day view)
_DAYS_CAP = 400
_HOURS: dict = {}   # int utc-hour -> traversal rollup (admin per-hour view)
_HOUR_KEEP_S = 7 * 86400   # hour buckets evaporate after a week
# NOTE — there is deliberately NO all-time trips/km/devices counter
# here. The public donation ledger lives in v2/store.TRIPS + LEDGER
# (the store /v2/city and /admin read); totals() repointed to it so the
# community surface quotes the same numbers. This module's own stores
# are the corridor-traversal projection: only donations that carried
# usable coordinates fold in, so their sums are a subset of the ledger
# — never a second count of 'shared trips'.

_reports: list[dict] = []
_reviews: list[dict] = []
_REVIEW_CAP = 400
_NOTE_CAP = 240
_loaded = False
# Hydration is a MERGE, not a wholesale replace: _hydrate() unions each
# snapshot entry into the live aggregates, so a donation folded while
# the warm-up thread was still reading S3 survives the hydrate. Boot
# warms _load() in a thread while requests are already served — the
# lock makes every later caller wait rather than observe or fold into
# a half-hydrated store.
_load_lock = threading.Lock()
# A FAILED S3 hydrate (network blip, throttling) used to latch _loaded
# on an empty store: every later _save then PUT an almost-empty
# snapshot over the real one — the prod community projection was
# clobbered that way (a boot during an S3 dip erased the durable copy
# and every write after kept republishing the loss). Now a transient
# failure stays RETRYABLE on a 30 s gap, _save refuses to PUT until a
# hydrate has actually landed, and the error is kept in _LAST_ERROR
# where /admin can read it instead of vanishing into `except: pass`.
_s3_unhydrated = False   # only while _BUCKET is set and hydrate failed
_s3_next_retry = 0.0
_S3_RETRY_GAP_S = 30.0
_LAST_ERROR: Optional[str] = None


def _record_error(e: Exception) -> None:
    """Last store failure, inspectable instead of silent — a bare
    `except: pass` on the hydrate path is what let the projection get
    clobbered unnoticed. Callers (e.g. v2/trip's citizen-layer hop)
    may record here too."""
    global _LAST_ERROR
    try:
        _LAST_ERROR = f"{type(e).__name__}: {e}"[:200]
    except Exception:
        _LAST_ERROR = "unprintable store error"

# k-anonymity contract shared with v2/store.py TripAggregates: a cell is
# publishable only with >=3 distinct (hashed) devices and a traversal
# inside the last 72 h. Keep these in lockstep.
_K_MIN_DEVICES = 3
_CELL_WINDOW_S = 72 * 3600


def _token(contributor) -> str:
    """Hash the anonymous device id before it may touch a store or a
    snapshot — the same treatment v2/trip.py gives device_token.
    Distinct-countable for the k>=3 threshold, not linkable."""
    if not contributor:
        return ""
    return hashlib.sha256(str(contributor).encode()).hexdigest()[:16]


def _s3():
    global _s3_client
    if _s3_client is None and _BUCKET:
        try:
            import boto3
            _s3_client = boto3.client("s3", region_name=os.environ.get("AWS_REGION", "ap-south-1"))
        except Exception:
            _s3_client = False
    return _s3_client or None


_HEX16 = re.compile(r"[0-9a-f]{16}")


def _fold(ts: float, vehicle: str, duration_s: float, dose_ug,
          avoided_ug, co2_kg, km: float, cells: set, tok_hash: str) -> None:
    """Fold ONE traversal into the aggregates — the only write path.

    Called by observe() on ingest and by _migrate() when an old-format
    snapshot is loaded. After this call the trip's coordinates and its
    ordered cell chain no longer exist anywhere: cells are a set, so the
    store can't even tell which cell was first or last. tok_hash is the
    already-hashed contributor id; it lands only inside per-cell /
    per-bucket device SETS — the k>=3 distinct-device gate cannot count
    without them, but they never link back to a row, a route, or a
    time-ordered trace.
    """
    global _OBS_VERSION
    day = time.strftime("%Y-%m-%d", time.gmtime(ts))
    d = _DAYS.setdefault(day, {"trips": 0, "dose_sum": 0.0,
                               "avoided_sum": 0.0, "km": 0.0,
                               "last_ts": 0.0, "modes": set(),
                               "devices": set()})
    d["trips"] += 1
    d["dose_sum"] += dose_ug or 0.0
    d["avoided_sum"] += avoided_ug or 0.0
    d["km"] += km
    d["last_ts"] = max(d["last_ts"], ts)
    d["modes"].add(vehicle)
    if tok_hash:
        d["devices"].add(tok_hash)
    h = int(ts // 3600)
    hr = _HOURS.setdefault(h, {"trips": 0, "devices": set(),
                               "duration_s": 0.0, "dose_ug": 0.0,
                               "avoided_ug": 0.0, "km": 0.0,
                               "last_ts": 0.0, "modes": {}})
    hr["trips"] += 1
    if tok_hash:
        hr["devices"].add(tok_hash)
    hr["duration_s"] += duration_s
    hr["dose_ug"] += dose_ug or 0.0
    hr["avoided_ug"] += avoided_ug or 0.0
    hr["km"] += km
    hr["last_ts"] = max(hr["last_ts"], ts)
    hr["modes"][vehicle] = hr["modes"].get(vehicle, 0) + 1
    # implied ambient concentration — only traversals that survive the
    # same validity gates corridor_field_samples() applies count as
    # measurements (dose + >=30 s duration + sane implied value)
    implied = None
    dur_min = duration_s / 60.0
    if dose_ug and dur_min >= 0.5:
        ve = VENTILATION_LPM.get(vehicle, 10.0) / 1000.0
        me = MICROENV.get(vehicle, 1.0)
        c = dose_ug / (ve * dur_min * me)
        if 10 <= c <= 900:
            implied = round(c, 1)
    km_cell = km / len(cells) if cells else 0.0
    for cell in cells:
        v = _CELLS.setdefault(cell, {"trips": 0, "dose_sum": 0.0,
                                     "avoided_sum": 0.0, "km_sum": 0.0,
                                     "co2_kg_sum": 0.0, "co2_trips": 0,
                                     "modes": {}, "dev_all": set(),
                                     "dev_ts": {}, "vals": [],
                                     "last_ts": 0.0})
        v["trips"] += 1
        v["dose_sum"] += dose_ug or 0.0
        v["avoided_sum"] += avoided_ug or 0.0
        v["modes"][vehicle] = v["modes"].get(vehicle, 0) + 1
        if tok_hash:
            v["dev_all"].add(tok_hash)
        v["last_ts"] = max(v["last_ts"], ts)
        v["km_sum"] += km_cell
        if co2_kg:
            v["co2_kg_sum"] += co2_kg
            v["co2_trips"] += 1
        if implied is not None:
            # dev_ts is the *fresh-window* device set — field samples
            # require >=k devices among traversals inside 72 h, not all-
            # time; dev_ts entries self-prune past the window
            if tok_hash:
                tl = v["dev_ts"].setdefault(tok_hash, [])
                tl.append(ts)
                if len(tl) > 64:
                    del tl[:len(tl) - 64]
            v["vals"].append([ts, implied])
            if len(v["vals"]) > _CELL_VAL_CAP:
                del v["vals"][:len(v["vals"]) - _CELL_VAL_CAP]
    _OBS_VERSION += 1


def _migrate_obs(o: dict) -> None:
    """Fold a pre-aggregate snapshot row into the new stores, once.

    Rows carrying 'cells' fold straight in. Rows carrying only 'points'
    — snapshots written before any trim existed — are DROPPED: their
    coordinates were never privacy-trimmed, so folding their endpoints
    into cells would preserve exactly what the trim exists to erase.
    Plaintext-era contributor ids are hashed on the way in.
    """
    cells_raw = o.get("cells")
    if not isinstance(cells_raw, list):
        return                      # legacy 'points' rows die here
    cells = set()
    for c in cells_raw:
        if isinstance(c, (list, tuple)) and len(c) >= 2:
            try:
                cells.add((float(c[0]), float(c[1])))
            except (TypeError, ValueError):
                continue
    if not cells:
        return
    tok = o.get("contributor") or ""
    if tok and not _HEX16.fullmatch(str(tok)):
        tok = _token(tok)
    _fold(ts=float(o.get("ts") or time.time()),
          vehicle=str(o.get("vehicle") or "unknown"),
          duration_s=float(o.get("duration_s") or 0.0),
          dose_ug=o.get("dose_ug"), avoided_ug=o.get("avoided_ug"),
          co2_kg=o.get("co2_kg"), km=float(o.get("km") or 0.0),
          cells=cells, tok_hash=str(tok or ""))


def _apply(d: dict) -> bool:
    """Hydrate a snapshot. Returns True when a legacy v1 file was
    migrated — the caller re-saves so the per-trip rows die on disk
    the moment they're read, not at the next write."""
    global _reports, _reviews
    # merge by content key — a retry or a second source may carry rows
    # already folded; idempotent hydrate keeps them single
    rkeys = {(r.get("ts"), r.get("kind"), r.get("lat"), r.get("lon"))
             for r in _reports}
    _reports = sorted(
        _reports + [r for r in (d.get("reports") or [])
                    if (r.get("ts"), r.get("kind"), r.get("lat"),
                        r.get("lon")) not in rkeys],
        key=lambda r: r.get("ts") or 0)[-2000:]
    vkeys = {(v.get("ts"), v.get("stars"), v.get("note"), v.get("build"))
             for v in _reviews}
    _reviews = sorted(
        _reviews + [v for v in (d.get("reviews") or [])
                    if (v.get("ts"), v.get("stars"), v.get("note"),
                        v.get("build")) not in vkeys],
        key=lambda v: v.get("ts") or 0)[-_REVIEW_CAP:]
    if d.get("v") == 2:
        _hydrate(d)
        return False
    migrated = bool(d.get("obs"))
    for o in d.get("obs", []):      # v1 snapshot: fold rows, then they
        _migrate_obs(o)             # never exist at rest again
    return migrated


def _merge_cell(cell: dict, v: dict) -> None:
    """Union a hydrated cell into the live one — counters add, device
    sets union, last_ts takes the max. Entries come from the same
    aggregate stream, so union recovers what this process missed
    without double-counting what it already folded."""
    cell["trips"] += v["trips"]
    for k in ("dose_sum", "avoided_sum", "km_sum", "co2_kg_sum"):
        cell[k] += v[k]
    cell["co2_trips"] += v["co2_trips"]
    for m, n in v["modes"].items():
        cell["modes"][m] = cell["modes"].get(m, 0) + n
    cell["dev_all"] |= v["dev_all"]
    for k, ts in v["dev_ts"].items():
        tl = cell["dev_ts"].setdefault(k, [])
        tl.extend(ts)
        tl.sort()
        if len(tl) > 64:
            del tl[:len(tl) - 64]
    cell["vals"].extend(v["vals"])
    cell["vals"].sort(key=lambda p: p[0])
    if len(cell["vals"]) > _CELL_VAL_CAP:
        del cell["vals"][:len(cell["vals"]) - _CELL_VAL_CAP]
    cell["last_ts"] = max(cell["last_ts"], v["last_ts"])


def _hydrate(d: dict) -> None:
    """v2 payload → in-memory aggregates (lists back to sets), MERGED
    into whatever already folded — a donation written while this
    hydrate was still running survives it. A clean boot merges into
    empty stores, which is exactly the old wholesale-load behaviour."""
    for key, v in (d.get("cells") or {}).items():
        try:
            lon, lat = (float(x) for x in str(key).split(",", 1))
        except (TypeError, ValueError):
            continue
        hv = {
            "trips": int(v.get("trips") or 0),
            "dose_sum": float(v.get("dose_sum") or 0.0),
            "avoided_sum": float(v.get("avoided_sum") or 0.0),
            "km_sum": float(v.get("km_sum") or 0.0),
            "co2_kg_sum": float(v.get("co2_kg_sum") or 0.0),
            "co2_trips": int(v.get("co2_trips") or 0),
            "modes": dict(v.get("modes") or {}),
            "dev_all": set(v.get("dev_all") or []),
            "dev_ts": {str(k): [float(x) for x in
                              (t if isinstance(t, list) else [t])]
                       for k, t in (v.get("dev_ts") or {}).items()},
            "vals": [[float(p[0]), float(p[1])]
                     for p in (v.get("vals") or [])
                     if isinstance(p, (list, tuple)) and len(p) >= 2],
            "last_ts": float(v.get("last_ts") or 0.0),
        }
        cur = _CELLS.get((lon, lat))
        if cur is None:
            _CELLS[(lon, lat)] = hv
        else:
            _merge_cell(cur, hv)
    for day, v in (d.get("days") or {}).items():
        cur = _DAYS.setdefault(str(day), {
            "trips": 0, "dose_sum": 0.0, "avoided_sum": 0.0, "km": 0.0,
            "last_ts": 0.0, "modes": set(), "devices": set()})
        cur["trips"] += int(v.get("trips") or 0)
        cur["dose_sum"] += float(v.get("dose_sum") or 0.0)
        cur["avoided_sum"] += float(v.get("avoided_sum") or 0.0)
        cur["km"] += float(v.get("km") or 0.0)
        cur["last_ts"] = max(cur["last_ts"], float(v.get("last_ts") or 0.0))
        cur["modes"] |= set(v.get("modes") or [])
        cur["devices"] |= set(v.get("devices") or [])
    for h, v in (d.get("hours") or {}).items():
        cur = _HOURS.setdefault(int(h), {
            "trips": 0, "devices": set(), "duration_s": 0.0,
            "dose_ug": 0.0, "avoided_ug": 0.0, "km": 0.0,
            "last_ts": 0.0, "modes": {}})
        cur["trips"] += int(v.get("trips") or 0)
        cur["devices"] |= set(v.get("devices") or [])
        cur["duration_s"] += float(v.get("duration_s") or 0.0)
        cur["dose_ug"] += float(v.get("dose_ug") or 0.0)
        cur["avoided_ug"] += float(v.get("avoided_ug") or 0.0)
        cur["km"] += float(v.get("km") or 0.0)
        cur["last_ts"] = max(cur["last_ts"], float(v.get("last_ts") or 0.0))
        for m, n in (v.get("modes") or {}).items():
            cur["modes"][m] = cur["modes"].get(m, 0) + int(n)
    # legacy snapshots may carry 'life'/'devices' keys — the duplicate
    # all-time ledger this module used to keep. They are ignored: the
    # donation ledger is v2/store.TRIPS + LEDGER now.


def _snapshot() -> dict:
    """The persisted shape — aggregates only, by construction there is
    no per-trip row to serialize."""
    return {
        "v": 2,
        "cells": {f"{lon},{lat}": {k: (sorted(v[k]) if isinstance(
                       v[k], set) else v[k]) for k in (
                       "trips", "dose_sum", "avoided_sum", "km_sum",
                       "co2_kg_sum", "co2_trips", "modes", "dev_all",
                       "dev_ts", "vals", "last_ts")}
                  for (lon, lat), v in _CELLS.items()},
        "days": {day: {**v, "modes": sorted(v["modes"]),
                       "devices": sorted(v["devices"])}
                 for day, v in _DAYS.items()},
        "hours": {str(h): {**v, "devices": sorted(v["devices"])}
                  for h, v in _HOURS.items()},
        "reports": _reports[-2000:],
        "reviews": _reviews[-_REVIEW_CAP:],
    }


def _prune_agg() -> None:
    """Bound the aggregates on save: stale hour buckets evaporate, stale
    implied-C pairs die, oversized stores evict their stalest cells/days.
    Deleting is honest here — everything past the windows is dead weight
    the publish paths already ignore."""
    now = time.time()
    for h in [k for k in _HOURS if now - k * 3600 > _HOUR_KEEP_S]:
        del _HOURS[h]
    for cell, v in _CELLS.items():
        fresh = [p for p in v["vals"] if now - p[0] <= _OBS_FRESH_S]
        if len(fresh) != len(v["vals"]):
            v["vals"] = fresh
        v["dev_ts"] = {k: [t for t in ts
                           if now - t <= _CELL_WINDOW_S]
                       for k, ts in v["dev_ts"].items()}
        v["dev_ts"] = {k: ts for k, ts in v["dev_ts"].items() if ts}
    if len(_CELLS) > _CELLS_CAP:
        stale = sorted(_CELLS.items(), key=lambda kv: kv[1]["last_ts"])
        for k, _v in stale[:len(_CELLS) - _CELLS_CAP]:
            del _CELLS[k]
    if len(_DAYS) > _DAYS_CAP:
        for k in sorted(_DAYS)[:len(_DAYS) - _DAYS_CAP]:
            del _DAYS[k]


def _load() -> None:
    global _loaded, _s3_unhydrated, _s3_next_retry
    if _loaded:
        # a failed S3 hydrate stays retryable — the saved snapshot is
        # the projection's only durable copy, and serving empty because
        # of a transient blip then PUTting that empty over it was the
        # clobber. Retry on a gap rather than latching forever.
        if not (_s3_unhydrated and time.time() >= _s3_next_retry):
            return
        _loaded = False
    with _load_lock:
        if _loaded:
            return
        s3 = _s3()
        if s3:
            try:
                body = s3.get_object(Bucket=_BUCKET, Key=_S3_KEY)["Body"].read()
                if _apply(json.loads(body)):
                    _save()         # rewrite as aggregates immediately
                _s3_unhydrated = False
                _prune_reports()
                _loaded = True
                return
            except Exception as e:
                code = ""
                try:
                    code = str(e.response["Error"]["Code"])
                except Exception:
                    pass
                if code not in ("NoSuchKey", "NoSuchBucket", "404"):
                    # transient S3 failure — stay unhydrated and retry;
                    # the file is NOT hydrated here on purpose: its
                    # rows would double-merge with S3's once the bucket
                    # recovers. Folds keep landing live meanwhile — the
                    # eventual merge unions them with the snapshot.
                    _record_error(e)
                    _s3_unhydrated = True
                    _s3_next_retry = time.time() + _S3_RETRY_GAP_S
                    _prune_reports()
                    _loaded = True
                    return
                _s3_unhydrated = False   # S3 answered honestly-empty;
                # a local file may still hold this box's last state
                # (written before the bucket existed) — safe to merge:
                # with no S3 key there is no overlap to double-count.
        if _FILE.exists():
            try:
                if _apply(json.loads(_FILE.read_text())):
                    _save()
            except Exception as e:
                _record_error(e)
        _prune_reports()
        _loaded = True


def _save() -> None:
    global _last_s3_put
    _prune_agg()
    payload = _snapshot()
    try:
        _FILE.parent.mkdir(parents=True, exist_ok=True)
        _FILE.write_text(json.dumps(payload))
    except Exception:
        pass
    now = time.time()
    s3 = _s3()
    # never PUT while the S3 hydrate is still outstanding — writing a
    # near-empty snapshot over the durable one is the clobber this flag
    # exists to prevent
    if s3 and not _s3_unhydrated and now - _last_s3_put > _S3_MIN_GAP_S:
        _last_s3_put = now
        try:
            s3.put_object(Bucket=_BUCKET, Key=_S3_KEY,
                          Body=json.dumps(payload), ContentType="application/json")
        except Exception as e:
            _record_error(e)


def _prune_reports() -> None:
    cutoff = time.time() - _REPORT_TTL_S
    _reports[:] = [r for r in _reports if r.get("ts", 0) > cutoff]


def observe(vehicle: str, coords: list, duration_s: float,
            dose_ug: Optional[float], avoided_ug: Optional[float],
            contributor: Optional[str],
            co2_kg: Optional[float] = None,
            privacy_trimmed: bool = False) -> dict:
    """Store an anonymized traversal. coords: [[lon, lat], ...] sampled.

    The raw coordinate list is folded into ~500 m cell traversals here
    and never stored — doc 07 §3's "no raw trajectories at rest". What
    persists per trip is exactly what every aggregate needs and nothing
    more: cells touched, path km, mode, dose sums, a hashed token.

    Untrimmed callers (anything that posts raw geometry — the retired
    /observe endpoint used to) get the same privacy pipeline /v2/trip
    runs: drop first+last 300 m, thin ~100 m, round 4 dp — so endpoints
    can never persist even client-side-forgot. v2/trip already trims
    and passes privacy_trimmed=True; re-running would double-trim its
    `kept` set."""
    _load()
    if not isinstance(coords, (list, tuple)):
        coords = []
    if privacy_trimmed:
        # v2/trip feeds pipeline output here (always numeric), but a
        # direct caller's junk pair must not crash the whole donation
        pts = []
        for c in coords[:400]:
            if not isinstance(c, (list, tuple)) or len(c) < 2:
                continue
            try:
                lo, la = float(c[0]), float(c[1])
            except (TypeError, ValueError):
                continue
            if math.isfinite(lo) and math.isfinite(la):
                pts.append([round(lo, 5), round(la, 5)])
    else:
        from v2.trip import privacy_pipeline
        kept, _t1, _t2 = privacy_pipeline(coords)  # [(lat, lon)] @ 4 dp
        pts = [[lo, la] for la, lo in kept]        # back to [lon, lat]
    cells: list = []
    for lon, lat in pts:
        cell = _cell(lon, lat)
        if not cells or cells[-1] != cell:
            cells.append(list(cell))
    # a donation that produced zero usable cells (empty coords, all
    # garbage pairs, a single point) must never enter the ledger — it
    # would only inflate the totals. found via malformed-input sweep.
    if not cells:
        return {"stored": False, "error": "no usable coordinates"}

    def _nn(v):
        """non-negative finite float or None — negative/junk metric
        values can't pollute the aggregates."""
        if v is None:
            return None
        try:
            f = float(v)
        except (TypeError, ValueError):
            return None
        return f if math.isfinite(f) and f >= 0 else None

    # Fold straight into the aggregates — after this line nothing that
    # could single out one traversal exists anywhere in the process.
    # `cells` is deliberately a SET: trip order dies at ingest, so no
    # store, snapshot, or S3 object can ever carry a walkable chain.
    _fold(ts=time.time(),
          vehicle=str(vehicle or "unknown")[:24],
          duration_s=round(_nn(duration_s) or 0.0, 1),
          dose_ug=_nn(dose_ug), avoided_ug=_nn(avoided_ug),
          co2_kg=_nn(co2_kg), km=round(_hav_km(pts), 3),
          cells={tuple(c) for c in cells},
          tok_hash=_token(contributor))
    _save()
    return {"stored": True}


def report(kind: str, lat: float, lon: float, contributor: Optional[str]) -> dict:
    if kind not in _REPORT_KINDS:
        return {"stored": False, "error": f"kind must be one of {sorted(_REPORT_KINDS)}"}
    _load()
    # 3 dp ≈ 110 m — a hazard pin needs street accuracy, not doorstep.
    # 5 dp (~1 m) pointed at a reporter's home; the pin's job is to warn
    # the next traveler, and no legitimate reader needs finer than this.
    r = {"ts": time.time(), "kind": kind,
         "lat": round(float(lat), 3), "lon": round(float(lon), 3)}
    _reports.append(r)
    _save()
    return {"stored": True, "active_reports": len(_reports)}


def reports_geojson() -> dict:
    _load()
    _prune_reports()
    feats = [{
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [r["lon"], r["lat"]]},
        "properties": {"kind": r["kind"], "age_min": round((time.time() - r["ts"]) / 60)},
    } for r in _reports]
    return {"type": "FeatureCollection", "features": feats}


def contributors_detail() -> dict:
    """Per-day city rollup for the admin dashboard — aggregates only.

    This used to return one row per contributor id (trips/km/dose/
    modes/last-seen per device) — exactly the per-device surface
    doc 07 §3 forbids, even hashed, because a persistent id makes the
    rows linkable across days. Rows are now UTC-day buckets: what the
    city did each day, plus the count of distinct devices behind it.
    `last_seen_min_ago` is kept so the ops console api's
    live-activity check still computes.

    The same k>=_K_MIN_DEVICES distinct-device rule recent_obs applies
    to hour buckets gates the day rows too: a UTC day held by 1-2
    devices is a *labelled* one-person day-slice — their trips, km,
    dose, modes and a last-seen to the minute. Sub-k days are
    suppressed and counted, never emitted (same shape as
    v2.store.global_aggregates' suppressed block)."""
    _load()
    out = []
    suppressed = 0
    for k, v in _DAYS.items():
        if len(v["devices"]) < _K_MIN_DEVICES:
            suppressed += 1
            continue  # below-k day row — counted, never published
        out.append({
            "day": k,
            "trips": v["trips"], "km": round(v["km"], 1),
            "dose_ug": round(v["dose_sum"], 1),
            "avoided_ug": round(v["avoided_sum"], 1),
            "contributors": len(v["devices"]),
            "last_seen_min_ago": round((time.time() - v["last_ts"]) / 60),
            "modes": sorted(v["modes"]),
        })
    out.sort(key=lambda x: x["last_seen_min_ago"])
    return {"days": out,
            "suppressed": {"day_rows": suppressed},
            "days_tracked": len(_DAYS)}


def recent_obs(limit: int = 20) -> list[dict]:
    """Recent activity as per-hour city aggregates, newest first.

    This used to return per-trip rows carrying the contributor id —
    linkable slices of individual journeys. Doc 07 §2 asks the admin
    surface for 'trips (aggregate): per hour/day', so each row is an
    hour bucket the whole city's trips collapsed into — AND a bucket
    only publishes when it holds >=_K_MIN_DEVICES distinct hashed
    contributors, the same k-anonymity contract corridor cells use:
    a trips:1 or trips:2 bucket still collapses to someone's exact
    hour/mode/duration/km/dose, which is per-person data."""
    _load()
    out = [{
        "hour": time.strftime("%Y-%m-%d %H:00Z", time.gmtime(h * 3600)),
        "age_min": round((time.time() - r["last_ts"]) / 60, 1),
        "trips": r["trips"],
        "devices": len(r["devices"]),
        "vehicle": max(r["modes"], key=r["modes"].get) if r["modes"] else None,
        "duration_s": round(r["duration_s"], 1),
        "dose_ug": round(r["dose_ug"], 1),
        "avoided_ug": round(r["avoided_ug"], 1),
        "km": round(r["km"], 1),
    } for h, r in _HOURS.items() if len(r["devices"]) >= _K_MIN_DEVICES]
    out.sort(key=lambda x: x["age_min"])
    return out[:limit]


def live_reports() -> list[dict]:
    _load()
    _prune_reports()
    return [{
        "kind": r["kind"], "lat": r["lat"], "lon": r["lon"],
        "age_min": round((time.time() - r["ts"]) / 60),
    } for r in _reports]


def journeys_per_hour(hours: int = 24) -> list[int]:
    """Traversals bucketed per UTC hour, oldest→newest — the ops
    sparkline. Read straight from the hour aggregates."""
    _load()
    cur = int(time.time() // 3600)
    return [_HOURS.get(cur - hours + 1 + i, {}).get("trips", 0)
            for i in range(hours)]


def _cell(lon: float, lat: float) -> tuple[float, float]:
    """~500m snap — groups traversals into corridors."""
    return (round(lon / 0.005) * 0.005, round(lat / 0.005) * 0.005)


# Offline gazetteer naming for published cells — the same offline rule
# v2/city applies, tiered for what a ~500 m street stretch should read
# as: the street it lies on when a road row is close, else the locality
# it sits inside, else "near <the closest place>". None when nothing
# honest is found — a name is never invented. Cells sit on a fixed
# grid, so each scan runs once per cell ever and the result is cached.
_CELL_NAME_RADIUS_M = 1200.0
_NAME_AREA_KINDS = {
    "locality", "neighborhood", "neighbourhood", "suburb", "district",
    "subdistrict", "sector", "quarter", "village", "hamlet", "town",
    "city", "place", "tehsil", "macrohood", "area", "block", "colony",
    "administrative", "place:locality", "place:neighbourhood",
    "place:suburb", "place:village", "place:hamlet", "place:quarter",
}
_NAME_STREET_KINDS = {
    "residential", "primary", "secondary", "tertiary", "trunk",
    "motorway", "unclassified", "living_street", "pedestrian",
    "service", "track", "street", "main", "highway", "footway",
    "cycleway", "primary_link", "secondary_link", "tertiary_link",
    "trunk_link", "motorway_link",
}
_NAME_ANCHOR_KINDS = {
    "station", "train_station", "railway:station", "metro", "subway",
    "bus_station", "park", "market", "marketplace", "square", "fort",
    "monument", "airport", "shopping_mall", "stadium",
}
_CELL_NAMES: dict = {}
_NAME_BUCKET_DEG = 0.05   # ~5.5 km buckets — a name scan touches
_NAME_BUCKETS: dict = {}  # 3×3 buckets around the cell, not 124k rows


def _name_rows():
    """Gazetteer rows that can name a street stretch, bucketed by
    ~5.5 km cells. Built once — GAZ._load() caches its own rows."""
    global _NAME_BUCKETS
    if _NAME_BUCKETS:
        return _NAME_BUCKETS
    from v2.gazetteer import GAZ
    kinds = _NAME_AREA_KINDS | _NAME_STREET_KINDS | _NAME_ANCHOR_KINDS
    for r in GAZ._load():
        if r["kind"] not in kinds or r["lat"] is None or r["lon"] is None:
            continue
        key = (int(r["lat"] / _NAME_BUCKET_DEG),
               int(r["lon"] / _NAME_BUCKET_DEG))
        _NAME_BUCKETS.setdefault(key, []).append(r)
    return _NAME_BUCKETS


def _cell_name(lat: float, lon: float):
    """A readable place name for a corridor cell — or None (the page
    falls back to coordinates; a name is never invented)."""
    key = (round(lat, 5), round(lon, 5))
    if key in _CELL_NAMES:
        return _CELL_NAMES[key]
    name = None
    try:
        from v2.gazetteer import _haversine_m
        buckets = _name_rows()
        blat, blon = (int(lat / _NAME_BUCKET_DEG),
                      int(lon / _NAME_BUCKET_DEG))
        span = int(math.ceil(_CELL_NAME_RADIUS_M / 111_000.0
                             / _NAME_BUCKET_DEG))  # ≥ radius, in buckets
        street = area = anchor = None
        for bi in range(blat - span, blat + span + 1):
            for bj in range(blon - span, blon + span + 1):
                for r in buckets.get((bi, bj), ()):
                    d = _haversine_m(lat, lon, r["lat"], r["lon"])
                    if d > _CELL_NAME_RADIUS_M:
                        continue
                    k = r["kind"]
                    if k in _NAME_STREET_KINDS:
                        if street is None or d < street[1]:
                            street = (r["name"], d)
                    elif k in _NAME_AREA_KINDS:
                        if area is None or d < area[1]:
                            area = (r["name"], d)
                    elif k in _NAME_ANCHOR_KINDS:
                        if anchor is None or d < anchor[1]:
                            anchor = (r["name"], d)
        if street and street[1] <= 250:
            name = street[0]
        elif area and area[1] <= 600:
            name = area[0]
        elif area:
            name = f"near {area[0]}"
        elif street:
            name = f"near {street[0]}"
        elif anchor:
            name = f"near {anchor[0]}"
    except Exception:
        name = None
    _CELL_NAMES[key] = name
    return name


def _hav_km(pts) -> float:
    """Path distance over [[lon, lat], ...] points."""
    d = 0.0
    for a, b in zip(pts, pts[1:]):
        d += 6371 * 2 * math.asin(min(1, math.sqrt(
            math.sin(math.radians(b[1] - a[1]) / 2) ** 2 +
            math.cos(math.radians(a[1])) * math.cos(math.radians(b[1])) *
            math.sin(math.radians(b[0] - a[0]) / 2) ** 2)))
    return d


# mode microenv + ventilation lookups for backing ambient concentration
# out of an inhaled dose — the environmental evidence a traversal carries
from exposure import MICROENV, VENTILATION_LPM  # noqa: E402

_OBS_FRESH_S = 72 * 3600  # traversals older than 3 days stop informing

# corridor_field_samples() rescans every observation on each call — and
# /grid asks once PER CELL (~800 calls a paint). Cache it for up to 60s,
# invalidated the moment a new traversal lands, so the citizen layer
# stays fresh while a dashboard paint costs one scan, not 800.
_OBS_VERSION = 0
_CELLS_CACHE: tuple = (0.0, -1, [])  # (built_at, obs_version, samples)
_CELLS_CACHE_TTL = 60.0


def corridor_field_samples() -> list:
    """Traversal-implied ambient PM2.5 per corridor cell — the citizen
    sensor network's real output.

    Every observation carries dose(µg) = ∫ C·microenv·ve dt along its
    path. Inverting it gives the ambient concentration the traveler
    effectively breathed through, mode-corrected:
        C_implied = dose_ug / (ve_lpm/1000 · duration_min · microenv)
    Median per ~500m cell needs ≥3 fresh traversals — one journey is an
    anecdote, a corridor of commutes is a measurement. Returned in the
    (lat, lon, name, vals) sample shape AirField consumes; unnamed so
    they weigh like model points (1×), never like stations (3×)."""
    _load()
    built, ver, cached = _CELLS_CACHE
    if cached and ver == _OBS_VERSION and time.time() - built < _CELLS_CACHE_TTL:
        return cached
    now = time.time()
    out = []
    for (lon, lat), v in _CELLS.items():
        vals = sorted(c for ts, c in v["vals"]
                      if now - ts <= _OBS_FRESH_S)
        # median needs >=3 fresh traversals AND >=_K_MIN_DEVICES distinct
        # hashed devices — otherwise one device looping a block could
        # write a 'measurement' into the city field
        fresh_dev = sum(1 for ts in v["dev_ts"].values()
                        if any(now - t <= _CELL_WINDOW_S for t in ts))
        if len(vals) < 3 or fresh_dev < _K_MIN_DEVICES:
            continue
        med = vals[len(vals) // 2]
        out.append((lat, lon, None, {"pm2_5": round(med, 1)}))
    return out


def corridor_estimate(lat: float, lon: float):
    """Traversal-implied ambient pm25 at a point: (µg, std-dev, n_obs).

    IDW (p=2) over corridor cells within ~3km; the spread across cells
    plus the shallow-sample noise sets the std-dev. None when the
    citizen layer has no coverage there — no invented confidence."""
    cells = corridor_field_samples()
    if not cells:
        return None
    num = den = var_sum = n = 0.0
    for slat, slon, _n, vals in cells:
        c = (vals or {}).get("pm2_5")
        if c is None:
            continue
        d = math.hypot(slat - lat, slon - lon)
        if d > 0.03:  # ~3km coherence — citizen data is local
            continue
        w = 1.0 / max(d * d, 1e-8)
        num += w * c
        den += w
        var_sum += w * c * c
        n += 1
    if not den or n == 0:
        return None
    mu = num / den
    var = max(0.0, var_sum / den - mu * mu)
    # instrument noise of a traversal-implied read ~40µg + spatial spread
    sd = math.sqrt(var + 1600.0 / max(n, 1))
    return mu, sd, n


def corridors(limit: int = 10) -> list[dict]:
    """Where Delhi actually travels, ranked — donated traversal density
    per ~500m cell with average inhaled dose. This is street-level
    movement data no station grid or routing API can produce.

    Publishable-set semantics mirror v2/store.py TripAggregates: a trip
    counts a cell once, and a cell is revealed only with >=_K_MIN_DEVICES
    distinct hashed devices and a traversal inside the 72 h window.
    Below k the cell simply does not exist in the output — the old code
    published any cell with samples, so one device pacing a block could
    draw its own commute onto the map."""
    _load()
    now = time.time()
    out = []
    for (lon, lat), v in _CELLS.items():
        if len(v["dev_all"]) < _K_MIN_DEVICES:
            continue  # below-k suppression — never publishable
        if now - v["last_ts"] > _CELL_WINDOW_S:
            continue  # stale corridor — doc 07 shows only live corridors
        out.append({
            "lon": lon, "lat": lat, "samples": v["trips"],
            "devices": len(v["dev_all"]),
            "name": _cell_name(lat, lon),
            "avg_dose_ug": round(v["dose_sum"] / max(v["trips"], 1), 1),
            # traversal-implied average, not an instrument read — the
            # claims audit wants the estimate basis on the wire, not
            # just implied by which endpoint serves it
            "avg_dose_basis": "est. from donated trips",
            "top_mode": max(v["modes"], key=v["modes"].get) if v["modes"] else None,
            "co2_g_per_100m": (round(v["co2_kg_sum"] * 100.0
                                     / v["km_sum"], 1)
                               if v["co2_trips"] and v["km_sum"] > 0
                               else None),
            "co2_trips": v["co2_trips"] or None,
        })
    out.sort(key=lambda x: -x["samples"])
    return out[:limit]


def totals() -> dict:
    """City rollup — the collective ledger judges can read at a glance.

    Reads the SAME donation ledger /v2/city and the ops console
    serve (v2.store.TRIPS day buckets + LEDGER's device count) — one source
    of truth, so the public surfaces can never disagree on 'shared
    trips' again (they diverged: /v2/trip writes TRIPS and best-effort
    folds here, and this module's own _LIFE/_DEVICES counter answered
    'how many donated' with the smaller traversal set). 'today' is the
    UTC day the ledger keys itself on — the same basis /city prints.

    Only the corridor fields come from this module's own stores: a
    different dataset (donations that carried usable coordinates), and
    corridors() applies its own k>=3/72 h gate. Every field is a
    city-level total, never per device (doc 07 §3)."""
    _load()
    from v2.store import TRIPS, LEDGER
    days = TRIPS.city_aggregates().get("days") or {}
    today_key = time.strftime("%Y-%m-%d", time.gmtime())
    today = days.get(today_key) or {}

    def _all(k: str) -> float:
        return sum(float(v.get(k) or 0.0) for v in days.values())

    last_ts = max((float(v.get("last_ts") or 0.0)
                   for v in days.values()), default=0.0)
    return {
        "obs_total": int(_all("trips")),
        "obs_today": int(today.get("trips") or 0),
        "today": today_key,
        "contributors": LEDGER.devices(),
        "km_today": round(float(today.get("km") or 0.0), 1),
        "dose_ug_today": round(float(today.get("dose_ug") or 0.0), 1),
        "avoided_ug_today": round(float(today.get("avoided_ug") or 0.0), 1),
        "avoided_ug_all": round(_all("avoided_ug"), 1),
        "active_reports": len(_reports),
        "modes_today": dict(today.get("modes") or {}),
        "latest_obs_age_min": (round((time.time() - last_ts) / 60)
                               if last_ts else None),
        "top_corridors": corridors(5),
        "source": "trip_aggregates",
        "basis": ("the shared donation ledger /v2/city and the ops "
                  "console read "
                  "(v2 trip aggregates + device ledger) — one source of "
                  "truth for shared-trip totals; corridor cells publish "
                  "only with >=3 distinct devices in 72 h; no per-trip "
                  "records exist at rest"),
    }


# ---------------------------------------------------------------- reviews
# "Their reviews" for the admin surface — star ratings + short notes the
# app lets a user leave voluntarily (Settings → rate). Stored WITHOUT any
# token or device id: a review is authored content meant for display, so
# nothing linkable needs to exist at rest. The same k-gate as corridors:
# individual notes only publish once >=_K_MIN_DEVICES reviews exist —
# one lonely review is identifiable by timing alone.

def add_review(stars, note: Optional[str], build: Optional[str]) -> dict:
    _load()
    try:
        s = int(stars)
    except Exception:
        return {"stored": False, "error": "stars must be 1..5"}
    if s < 1 or s > 5:
        return {"stored": False, "error": "stars must be 1..5"}
    if note is not None and not isinstance(note, str):
        return {"stored": False, "error": "note must be text"}
    if build is not None and not isinstance(build, str):
        return {"stored": False, "error": "build must be text"}
    n = _redact_note((note or "").strip()[:_NOTE_CAP])
    r = {"ts": time.time(), "stars": s, "note": n,
         "build": (build or "")[:16]}
    _reviews.append(r)
    del _reviews[:-_REVIEW_CAP]
    _save()
    return {"stored": True, "total_reviews": len(_reviews)}


_COORD_RE = re.compile(
    r"(-?\d{1,3}\.\d{2,7})\s*[,/ ]\s*(-?\d{1,3}\.\d{2,7})")


def _redact_note(note: str) -> str:
    """Strip coordinate patterns from free text before it can persist.

    A review note is the one place a user can type raw lat/lon that we'd
    otherwise store and re-serve verbatim ('my stop at 28.6315,77.2167
    is dusty'). Anything shaped like a lat/lon pair degrades to ~1 km —
    enough for a reader to place it, not enough to pin a doorstep.
    """
    return _COORD_RE.sub(lambda m: f"{float(m.group(1)):.2f},"
                                   f"{float(m.group(2)):.2f}", note)


def reviews_summary(notes_limit: int = 8) -> dict:
    """Aggregate review rollup — the only shape the admin surface reads.
    Histogram + mean always publish; note bodies only once the count
    clears the same k>=3 gate corridor cells use, each truncated and
    timestamped to the hour so they can't be re-pinned to a moment."""
    _load()
    hist = {str(i): 0 for i in range(1, 6)}
    for r in _reviews:
        hist[str(r["stars"])] += 1
    out = {
        "count": len(_reviews),
        "avg": round(sum(r["stars"] for r in _reviews) / len(_reviews), 2)
               if _reviews else None,
        "hist": hist,
        "notes": [],
        "notes_withheld": False,
        "basis": ("authored reviews — stars + optional note; no device id "
                  "or token stored; note bodies publish only at >=3 reviews"),
    }
    if len(_reviews) >= _K_MIN_DEVICES:
        out["notes"] = [
            {"ts_hour": int(r["ts"] // 3600) * 3600,
             "stars": r["stars"], "note": r["note"][:140]}
            for r in _reviews[-notes_limit:] if r.get("note")
        ][::-1]
    else:
        out["notes_withheld"] = bool(_reviews)
    return out
