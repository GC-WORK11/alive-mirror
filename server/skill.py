"""The self-grade — the product publishing its own accuracy.

/v2/archive replays what was RECORDED; /grid?h= serves what is
FORECAST. Since 2026-10-05 every hourly snapshot (archive.py v2 blobs)
also stores the forecast surface the api was serving at capture time —
/grid?h=0..11 over the emit lattice, live anchor included. That makes
the archive a scored record: for every recorded hour, every earlier
snapshot that had already served a forecast for that hour is a real
predicted-vs-recorded pair.

This module joins exactly those pairs and counts the misses:

  pair      = one recorded hour-bucket × one served horizon h
  cells     = the emit-lattice points where both sides carry a value
  mae       = mean |model − recorded| over every cell of every pair
  bias      = mean (model − recorded) — positive = we over-called
  band hit  = share of cells where the served CPCB band equalled the
              recorded band (bands re-derived from the stored µg/m³,
              never assumed)

Honesty rules — the same contract as the rest of the server:
  * pairs key on the forecast's TARGET ist hour vs the recorded ist
    hour (hz.ist_day/ist_hour — the floor of the slot's IST start) —
    never on the hour the forecast happened to be served in.
  * a snapshot never grades its own capture (lead would be ~minutes,
    not the horizon it was filed under) — same rule as
    archive._find_stored_horizon.
  * where several captures served the same h for the same hour, the
    EARLIEST on record is the pair — the longest-standing surface we
    committed to, the same choice the archive flip makes.
  * 'held-run' model blocks are never graded here — they are raw
    model, not the surface anyone was served.
  * a bucket with fewer than MIN_PAIRS hourly realizations reports
    {"status":"thin","n":k} — a handful of hours is one weather
    regime, not a score. Nothing is ever smoothed or extrapolated.
"""
import concurrent.futures
import os
import time
from datetime import datetime

import archive as _archive

IST = _archive.IST
MIN_PAIRS = 5            # see module docstring — the thin floor
_MIN_GRADED_HOURS = 3    # overall 'ok' also needs ≥3 distinct hours
_CACHE_TTL_S = float(os.environ.get("ALIVE_SKILL_TTL_S", "120"))
_CACHE: dict = {"at": 0.0, "fp": None, "doc": None}

# Parsed-snapshot cache — the rescan's real cost is I/O, not the join:
# a miss used to re-read every doc the archive lists (44+ local gzips or
# sequential S3 GETs ≈ seconds; the local mirror only holds what this
# process wrote, so post-deploy nearly every doc is an S3 read). The
# archive is append-only in practice — capture() writes the one
# IST-hour bucket that is current — and every cached entry carries the
# source signature enumeration saw (local mtime / S3 LastModified+Size),
# so even a rewritten or backfilled file misses its sig check and
# reloads. Scoped to (root, bucket); entries the archive no longer
# lists are dropped, and the cache is bounded oldest-key-first — an
# over-cap doc degrades to a fresh read, never a wrong number.
_DOCS: dict = {}             # (day, hh) -> (sig, parsed doc|None)
_DOCS_SRC: tuple = ()        # (root, bucket) the cache is scoped to
_DOCS_MAX = int(os.environ.get("ALIVE_SKILL_DOCS_MAX", "256"))
_LOAD_WORKERS = int(os.environ.get("ALIVE_SKILL_LOAD_WORKERS", "8"))


def _info_sig(info: dict) -> tuple:
    """Freshness fingerprint of one enumerated source — local mtime for
    a mirror file, S3 LastModified+Size for the bucket object. A rewrite
    of the file shows up as a new sig without trusting key order."""
    sig = []
    p = info.get("local")
    if p:
        try:
            sig.append(os.path.getmtime(p))
        except OSError:
            sig.append(None)
    if info.get("s3"):
        sig += [info.get("lms"), info.get("size")]
    return tuple(sig)


def _band(pm25):
    """Recorded cells carry the served CPCB band name; model cells are
    bare µg/m³ — re-derive the band through the same districts table so
    both sides are graded by one convention."""
    import districts
    if pm25 is None:
        return None
    return districts.cpcb_band(districts.cpcb_aqi(pm25))[0]


def _join_cells(rec_cells, mod_cells):
    """(model − recorded) rows + band match per shared lattice point.
    -> list of (diff, model, recorded, band_hit)."""
    rec = {}
    for c in rec_cells or []:
        if c[2] is not None:
            rec[(c[0], c[1])] = (c[2], c[6] if len(c) > 6 else None)
    rows = []
    for c in mod_cells or []:
        rv = rec.get((c[0], c[1]))
        if rv is None or c[2] is None:
            continue
        hit = rv[1] is not None and _band(c[2]) == rv[1]
        rows.append((c[2] - rv[0], c[2], rv[0], hit))
    return rows


def _agg(bucket: dict) -> dict:
    """The per-horizon wire row — honest numbers or honest 'thin'."""
    n = bucket["n_pairs"]
    if n < MIN_PAIRS:
        return {"h": bucket["h"], "status": "thin", "n": n,
                "cells": len(bucket["diffs"])}
    diffs = bucket["diffs"]
    cells = len(diffs)
    mae = round(sum(abs(d) for d in diffs) / cells, 1)
    bias = round(sum(diffs) / cells, 1)
    hit = round(100.0 * bucket["hits"] / cells, 1)
    hour_hit = round(100.0 * bucket["hour_hits"] / n, 1)
    return {"h": bucket["h"], "status": "ok", "n": n, "cells": cells,
            "mae_ug": mae, "bias_ug": bias,
            "band_hit_pct": hit, "hour_band_hit_pct": hour_hit}


def _metrics(diffs, hits, n_pairs, hour_hits):
    cells = len(diffs)
    return {"n": n_pairs, "cells": cells,
            "mae_ug": round(sum(abs(d) for d in diffs) / cells, 1),
            "bias_ug": round(sum(diffs) / cells, 1),
            "band_hit_pct": round(100.0 * hits / cells, 1),
            "hour_band_hit_pct": round(100.0 * hour_hits / n_pairs, 1)}


def skill_payload(*, root=None, s3=None, bucket=None, now=None) -> dict:
    """GET /v2/skill body — the model graded against its own record.

    Scans every snapshot the archive can see (local mirror + bucket —
    same union as archive.day_payload), pairs each recorded hour with
    the served forecast horizons that targeted it, and reports error
    per horizon. An archive with nothing to grade answers
    {"status":"thin","n":0} — never an invented score."""
    now = time.time() if now is None else now
    ist_now = datetime.fromtimestamp(now, IST)

    avail = _archive._enumerate(root=root, s3=s3, bucket=bucket)
    bucket = bucket if bucket is not None \
        else os.environ.get("ALIVE_AIR_BUCKET")
    sigs = {k: _info_sig(info) for k, info in avail.items()}
    fp = (len(avail), max(avail) if avail else None,
          tuple(sorted(sigs.items())),
          _archive._root(root), bucket)
    c = _CACHE
    if c["doc"] is not None and c["fp"] == fp \
            and now - c["at"] < _CACHE_TTL_S:
        return dict(c["doc"])

    # delta-fill the parsed-doc cache: only sources whose signature is
    # new or changed are read — a steady-state miss re-reads nothing.
    global _DOCS_SRC
    src = (_archive._root(root), bucket)
    if _DOCS_SRC != src:
        _DOCS.clear()
        _DOCS_SRC = src
    for k in list(_DOCS):
        if k not in sigs:
            del _DOCS[k]
    need = [k for k in avail
            if not (k in _DOCS and _DOCS[k][0] == sigs[k])]
    if need:
        if len(need) > 4 and _LOAD_WORKERS > 1:
            if s3 is None:
                s3 = _archive._s3_client(bucket)  # boto clients are
            with concurrent.futures.ThreadPoolExecutor(  # thread-safe
                    max_workers=min(_LOAD_WORKERS, len(need)),
                    thread_name_prefix="alive-skill-load") as ex:
                got = list(ex.map(
                    lambda k: _archive._load_doc(
                        avail[k], s3=s3, bucket=bucket)[0], need))
        else:
            got = [_archive._load_doc(avail[k], s3=s3, bucket=bucket)[0]
                   for k in need]
        for k, doc in zip(need, got):
            _DOCS[k] = (sigs[k], doc)
    if len(_DOCS) > _DOCS_MAX:            # bound: oldest keys evict;
        for k in sorted(_DOCS)[:len(_DOCS) - _DOCS_MAX]:
            del _DOCS[k]                  # an evicted listed doc reads
                                          # as unreadable (thin, never
                                          # invented) and re-fills next
    docs = {k: _DOCS.get(k, (None, None))[1] for k in avail}

    # index every stored horizon by the ist bucket it targeted:
    # (target day yyyymmdd, target hour, h) -> issuing captures,
    # earliest first — two captures can serve the same h for the same
    # hour (the :30 ist/utc straddle), we grade the earliest on record
    cover = {}
    n_with_forecast = 0
    for (d, hh), doc in docs.items():
        fc = (doc or {}).get("forecast") or {}
        if fc.get("horizons"):
            n_with_forecast += 1
        cap_epoch = (doc or {}).get("captured_epoch") or 0.0
        for hz in fc.get("horizons") or []:
            td, th, h = hz.get("ist_day"), hz.get("ist_hour"), hz.get("h")
            if td is None or th is None or h is None:
                continue
            k = (td, int(th), int(h))
            cover.setdefault(k, []).append((cap_epoch, (d, hh), hz))
    for k in cover:
        cover[k].sort(key=lambda e: e[0])

    # pair each recorded hour with every horizon that covered it —
    # except the one stored in the hour's own snapshot
    buckets = {h: {"h": h, "n_pairs": 0, "diffs": [], "hits": 0,
                   "hour_hits": 0}
               for h in range(_archive.FORECAST_HORIZON_H)}
    n_pairs = 0
    graded_hours = set()
    pair_first = pair_last = None
    for (d, hh), doc in sorted(docs.items()):
        if doc is None or not doc.get("cells"):
            continue
        rec_key = (d, hh)
        graded = False
        for h in range(_archive.FORECAST_HORIZON_H):
            ents = cover.get((d, hh, h))
            if not ents:
                continue
            # earliest capture that isn't the hour's own snapshot —
            # the longest-standing surface we served for that horizon
            hz = next((e[2] for e in ents if e[1] != (d, hh)), None)
            if hz is None:
                continue                     # never its own comparison
            rows = _join_cells(doc["cells"], hz.get("cells"))
            if not rows:
                continue
            b = buckets[h]
            b["n_pairs"] += 1
            b["diffs"].extend(r[0] for r in rows)
            b["hits"] += sum(1 for r in rows if r[3])
            # the hour-level call: band of the hour's mean model value
            # vs band of its mean recorded value — same convention
            m_mean = sum(r[1] for r in rows) / len(rows)
            r_mean = sum(r[2] for r in rows) / len(rows)
            b["hour_hits"] += 1 if _band(m_mean) == _band(r_mean) else 0
            n_pairs += 1
            graded = True
        if graded:
            graded_hours.add(rec_key)
            t = _archive._ist_dt(d, hh)
            pair_first = t if pair_first is None or t < pair_first \
                else pair_first
            pair_last = t if pair_last is None or t > pair_last \
                else pair_last

    keys = sorted(avail)

    def _iso(d, h):
        return f"{d[:4]}-{d[4:6]}-{d[6:8]}T{h:02d}:00:00+05:30"

    horizons = [_agg(buckets[h]) for h in sorted(buckets)]
    all_diffs = [d for h in buckets for d in buckets[h]["diffs"]]
    all_hits = sum(b["hits"] for b in buckets.values())
    all_hour_hits = sum(b["hour_hits"] for b in buckets.values())
    ok = n_pairs >= MIN_PAIRS and len(graded_hours) >= _MIN_GRADED_HOURS
    overall = dict({"status": "ok" if ok else "thin"},
                   **(_metrics(all_diffs, all_hits, n_pairs, all_hour_hits)
                      if ok else {"n": n_pairs}))
    doc = {
        "status": overall["status"],
        "basis": "self-graded",
        "tz": "ist",
        "generated_ist": ist_now.isoformat(),
        "note": ("the model grading itself — every pair is a real "
                 "forecast surface the api served (/grid?h=, live "
                 "anchor included) vs the field it recorded serving "
                 "for the hour that forecast targeted; bias = model − "
                 "recorded, in µg/m³"),
        "pair_unit": "one recorded ist hour × one served horizon",
        "min_pairs": MIN_PAIRS,
        "pairs": n_pairs,
        "horizons": horizons,
        "overall": overall,
        "coverage": {
            "snapshots": len(keys),
            "snapshots_with_forecast": n_with_forecast,
            "since_ist": _iso(*keys[0]) if keys else None,
            "last_ist": _iso(*keys[-1]) if keys else None,
            "first_pair_ist": pair_first.isoformat()
                              if pair_first else None,
            "last_pair_ist": pair_last.isoformat()
                             if pair_last else None,
            "hours_graded": len(graded_hours),
        },
    }
    c.update({"at": now, "fp": fp, "doc": dict(doc)})
    return doc
