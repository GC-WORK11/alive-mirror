"""The archive — Delhi's served field, recorded hourly.

/grid?h=0..11 and the timelapse replay FORECAST slots (basis
"forecast"). This module is the other half of that story: once an hour
the API renders the field it is actually SERVING — the same surface
/grid answers with at h=None, i.e. airfield.FIELD over the shared 22x22
NCR lattice — and appends it to durable storage:

    s3://{ALIVE_AIR_BUCKET}/archive/field-YYYYMMDDHH.json.gz  (preferred —
        store_blob; the task role already carries s3 perms on the bucket)
    server/data/archive/field-YYYYMMDDHH.json.gz              (local
        mirror + offline fallback — the endpoint reads back off this
        task's disk; when AWS is unusable the local file is the copy)

The filename hour is the IST hour-bucket the snapshot belongs to —
"Delhi breathes" is kept in IST, so field-2026100514 is the record for
14:00-15:00 IST on 2026-10-05 regardless of the UTC instant it was
written at. One file per served IST hour, gzip, ~10-30 KB — append-only
(a re-capture of the same bucket replaces the stale first attempt,
never a different hour's).

Honesty contract — same rule as every other layer in this server:
  * snapshots record ONLY the served field: mid via FIELD.value, the
    read band via FIELD.sigma (lo/hi = mid ± 1.96·sigma, the convention
    the built index itself uses), confidence via FIELD.nearest_sample_km
    and the served source counts via FIELD.status. Cells the field
    does not value are dropped — never interpolated into fiction.
  * a field serving nothing writes NO snapshot: the hour stays a gap,
    and /v2/archive reports "gap". Gaps are data too.
  * every blob and every wire payload carries basis:"recorded" — it can
    never be confused with the forecast timelapse.

The recorder is an asyncio task started in main._lifespan
(ALIVE_ARCHIVE=0 disables). Each tick runs the same request-driven
FIELD.refresh a visitor would trigger — the snapshot stays aligned to
the field's own 15-min refresh cadence — then captures whatever is
served. A skipped tick (field empty) retries in ~5 min so a cold boot
still lands its first honest snapshot early.
"""
import asyncio
import glob
import gzip
import json
import math
import os
import re
import time
from datetime import datetime, timedelta, timezone
from typing import Optional

_HERE = os.path.dirname(os.path.abspath(__file__))
ARCHIVE_DIR = os.path.join(_HERE, "data", "archive")
S3_PREFIX = "archive/"
GRID_CELLS = 22            # the same lattice /grid?cells=22 serves
WIRE_STRIDE = 4            # endpoint emits every 4th stored cell (~121)
CELL_FIELDS = ["lon", "lat", "pm25", "lo", "hi", "conf", "band"]
BAND_SIGMA = 1.96          # lo/hi convention — matches airindex cells
TZ_NAME = "ist"
IST = timezone(timedelta(hours=5, minutes=30), "IST")

# cadence: one snapshot per IST hour-bucket, taken just past its start
INITIAL_DELAY_S = float(os.environ.get("ALIVE_ARCHIVE_DELAY_S", "45"))
SKIP_RETRY_S = 300.0       # a skipped tick (no served field) retries sooner
LOCAL_KEEP_DAYS = float(os.environ.get("ALIVE_ARCHIVE_KEEP_DAYS", "8"))
_STATUS_TTL_S = 60.0

_NAME_RE = re.compile(r"field-(\d{8})(\d{2})\.json\.gz$")

# last capture attempt — status() and the admin tile read it; the loop
# is the only writer, so a plain dict is enough
_LAST: dict = {"ok": None, "at": None}
_STATUS_CACHE: dict = {"at": 0.0, "doc": None}


def _enabled() -> bool:
    return os.environ.get("ALIVE_ARCHIVE", "1").strip() \
        not in ("0", "false", "no")


def _root(root=None) -> str:
    return root or os.environ.get("ALIVE_ARCHIVE_DIR") or ARCHIVE_DIR


def _key(ist: datetime) -> str:
    """S3 key for the IST hour-bucket a capture belongs to."""
    return f"{S3_PREFIX}field-{ist:%Y%m%d%H}.json.gz"


def _local_path(ist: datetime, root=None) -> str:
    return os.path.join(_root(root), f"field-{ist:%Y%m%d%H}.json.gz")


def _serialize(doc: dict) -> bytes:
    """Deterministic gzip JSON — same codec as the built index."""
    import airindex
    return airindex.serialize(doc)


def _deserialize(blob: bytes) -> dict:
    import airindex
    return airindex.deserialize(blob)


# ------------------------------------------------------------------ render

def _render_cells(field, cells: int = GRID_CELLS) -> list:
    """The served field on the /grid lattice — mid, honest band, conf,
    CPCB band name per cell. Cells the field does not value are dropped
    (same rule as grid.as_geojson)."""
    import districts
    import grid as _grid
    x0, y0, x1, y1 = _grid.BBOX
    dx, dy = (x1 - x0) / cells, (y1 - y0) / cells
    out = []
    for ix in range(cells):
        for iy in range(cells):
            cx, cy = x0 + (ix + 0.5) * dx, y0 + (iy + 0.5) * dy
            mid = field.value(cy, cx, "pm2_5")
            if mid is None or not math.isfinite(mid):
                continue
            sd = field.sigma(cy, cx)
            lo = hi = None
            if sd is not None and math.isfinite(sd):
                lo = round(max(0.0, mid - BAND_SIGMA * sd), 1)
                hi = round(mid + BAND_SIGMA * sd, 1)
            conf = _grid._conf(field.nearest_sample_km(cy, cx))
            band = districts.cpcb_band(districts.cpcb_aqi(mid))[0]
            out.append([round(cx, 4), round(cy, 4), round(mid, 1),
                        lo, hi, conf, band])
    return out


def _field_meta(field) -> dict:
    """The served field's own provenance at capture time — verbatim
    FIELD.status() subset, no re-derivation."""
    try:
        st = field.status() or {}
    except Exception:  # noqa: BLE001 - meta must never sink a capture
        st = {}
    return {
        "serving": st.get("serving"),
        "source": st.get("source"),
        "samples": st.get("samples"),
        "station_readings": st.get("station_readings"),
        "stations_src": st.get("stations_src"),
        "age_s": st.get("age_s"),
        "kriging": st.get("kriging"),
        "sigma_coverage": st.get("sigma_coverage"),
    }


# ------------------------------------------------------------------ capture

def capture(field=None, *, now: Optional[float] = None, root=None,
            store=None) -> dict:
    """Render the CURRENT served field and append it to the archive.

    `field` defaults to airfield.FIELD — the object /grid, /aqi and the
    dose engine all read. `store` is injectable for tests; the default
    is ingest_worker.store_blob (S3 when ALIVE_AIR_BUCKET + credentials
    resolve, always mirrored locally — the local file is how this task
    serves the endpoint back; on a failed put, local is the only copy).

    Nothing is fabricated: a field that serves no cells writes no
    snapshot — the hour stays an honest gap.
    -> summary {ok, uri|skipped, backend, cells, ist_day, ist_hour, ...}
    """
    if field is None:
        from airfield import FIELD
        field = FIELD
    now = time.time() if now is None else now
    ist = datetime.fromtimestamp(now, IST)
    cells = _render_cells(field)
    meta = _field_meta(field)
    base = {"ist_day": str(ist.date()), "ist_hour": ist.hour,
            "serving": meta.get("serving")}
    if not cells:
        res = dict(base, ok=False,
                   skipped=("served field has no cells — the hour stays "
                            "an honest gap"))
        _LAST.update(dict(res, at=now))
        return res
    doc = {
        "v": 1,
        "basis": "recorded",
        "captured_at": datetime.fromtimestamp(
            now, timezone.utc).isoformat(),
        "captured_epoch": now,
        "ist_day": base["ist_day"],
        "ist_hour": base["ist_hour"],
        "grid": {"cells": GRID_CELLS, "bbox": list(_bbox())},
        "cell_fields": CELL_FIELDS,
        "band_convention": f"lo/hi = pm25 +/- {BAND_SIGMA}*sigma "
                           "(the built index's own ±1.96 convention)",
        "field": meta,
        "n_cells": len(cells),
        "cells": cells,
    }
    blob = _serialize(doc)
    if store is None:
        import ingest_worker
        store = ingest_worker.store_blob
    uri, backend, note = store(_key(ist), blob, _local_path(ist, root),
                               mirror_local=True)
    res = dict(base, ok=True, uri=uri, backend=backend, note=note,
               cells=len(cells), bytes=len(blob),
               captured_ist=ist.isoformat(),
               field_age_s=meta.get("age_s"))
    _LAST.update(dict(res, at=now))
    try:
        _prune_local(root)
    except Exception:  # noqa: BLE001 - retention must never sink a write
        pass
    return res


def _bbox():
    import grid as _grid
    return _grid.BBOX


def _prune_local(root=None, keep_days: float = None) -> int:
    """Local mirror retention — files older than keep_days are deleted.
    S3 is the durable shelf; the local copy exists to serve reads, not
    to be the record."""
    root = _root(root)
    keep_days = LOCAL_KEEP_DAYS if keep_days is None else keep_days
    cutoff = time.time() - keep_days * 86400
    n = 0
    for p in glob.glob(os.path.join(root, "field-*.json.gz")):
        try:
            if os.path.getmtime(p) < cutoff:
                os.remove(p)
                n += 1
        except OSError:
            pass
    return n


# ------------------------------------------------------------------ storage

def _s3_client(bucket):
    """boto3 s3 client when AWS resolves, else None — same readiness rule
    as the rest of the server (ingest_worker._aws_ready)."""
    if not bucket:
        return None
    try:
        import ingest_worker
        b3, _why = ingest_worker._aws_ready()
        if b3 is None:
            return None
        return b3.client("s3")
    except Exception:  # noqa: BLE001
        return None


def _parse_name(path) -> Optional[tuple]:
    """'field-YYYYMMDDHH.json.gz' -> (yyyymmdd_str, hour_int)."""
    m = _NAME_RE.search(os.path.basename(path))
    if not m:
        return None
    return m.group(1), int(m.group(2))


def _enum_local(root=None) -> dict:
    out = {}
    for p in glob.glob(os.path.join(_root(root), "field-*.json.gz")):
        k = _parse_name(p)
        if k is not None:
            out[k] = {"local": p}
    return out


def _enum_s3(s3, bucket) -> dict:
    out = {}
    token = None
    while True:
        kw = {"Bucket": bucket, "Prefix": S3_PREFIX + "field-"}
        if token:
            kw["ContinuationToken"] = token
        r = s3.list_objects_v2(**kw)
        for o in r.get("Contents", []):
            k = _parse_name(o["Key"])
            if k is not None:
                out[k] = {"s3": o["Key"]}
        if not r.get("IsTruncated"):
            return out
        token = r.get("NextContinuationToken")


def _enumerate(*, root=None, s3=None, bucket=None) -> dict:
    """{(yyyymmdd, hour): {"local": path?, "s3": key?}} — the union of
    the local mirror and the bucket; either side alone is honestly
    partial, never treated as authoritative."""
    out = _enum_local(root)
    bucket = bucket if bucket is not None \
        else os.environ.get("ALIVE_AIR_BUCKET")
    if s3 is None:
        s3 = _s3_client(bucket)
    if s3 is not None and bucket:
        try:
            for k, info in _enum_s3(s3, bucket).items():
                out.setdefault(k, {}).update(info)
        except Exception:  # noqa: BLE001 - S3 down: local view stands,
            pass               # honestly partial
    return out


def _load_doc(info: dict, *, s3=None, bucket=None):
    """-> (doc|None, err|None). Local mirror first, the bucket second."""
    p = info.get("local")
    if p:
        try:
            with open(p, "rb") as fh:
                return _deserialize(fh.read()), None
        except Exception as e:  # noqa: BLE001
            return None, f"{type(e).__name__}: {e}"
    key = info.get("s3")
    if key:
        if s3 is None:
            bucket = bucket if bucket is not None \
                else os.environ.get("ALIVE_AIR_BUCKET")
            s3 = _s3_client(bucket)
        if s3 is not None and bucket:
            try:
                body = s3.get_object(Bucket=bucket, Key=key)["Body"].read()
                return _deserialize(body), None
            except Exception as e:  # noqa: BLE001
                return None, f"{type(e).__name__}: {e}"
    return None, "no readable copy"


# ------------------------------------------------------------------ payloads

def _hour_entry(h: int, doc: dict) -> dict:
    """One recorded hour on the wire — the stored field downsampled to
    every 4th cell (~121 of 484), meta verbatim."""
    cells = doc.get("cells") or []
    wire = cells[::WIRE_STRIDE]
    meta = doc.get("field") or {}
    return {
        "hour_ist": h,
        "ist_label": f"{h:02d}:00",
        "status": "recorded",
        "basis": "recorded",
        "captured_at": doc.get("captured_at"),
        "field_age_s": meta.get("age_s"),
        "serving": meta.get("serving"),
        "source": meta.get("source"),
        "samples": meta.get("samples"),
        "station_readings": meta.get("station_readings"),
        "stations_src": meta.get("stations_src"),
        "kriging": meta.get("kriging"),
        "sigma_coverage": meta.get("sigma_coverage"),
        "n_cells": len(cells),
        "cell_fields": CELL_FIELDS,
        "band_convention": doc.get("band_convention"),
        "downsample": {"stride": WIRE_STRIDE, "emitted": len(wire),
                       "of": len(cells)},
        "cells": wire,
    }


def day_payload(day=None, *, root=None, s3=None, bucket=None,
                now=None) -> dict:
    """GET /v2/archive body — one IST day's recorded hours + honest
    coverage. `day` is a date; None = today (IST). The archive being
    wholly empty (no snapshot anywhere) yields hours:[] — the honest
    'nothing recorded yet' — while a day inside a non-empty archive
    shows each missing hour as an explicit gap."""
    now = time.time() if now is None else now
    ist_now = datetime.fromtimestamp(now, IST)
    day = day or ist_now.date()
    day_s = str(day)
    day_key = day.strftime("%Y%m%d")

    avail = _enumerate(root=root, s3=s3, bucket=bucket)
    total_all = len(avail)
    today_map = {h: info for (d, h), info in avail.items()
                 if d == day_key}
    bucket = bucket if bucket is not None \
        else os.environ.get("ALIVE_AIR_BUCKET")

    hours = []
    for h in range(24):
        label = f"{h:02d}:00"
        info = today_map.get(h)
        if info is None:
            # a future slot on today's card is 'pending', not a gap —
            # the recorder simply hasn't reached it yet
            if day == ist_now.date() and h > ist_now.hour:
                st, note = "pending", "hour hasn't started yet"
            else:
                st, note = "gap", "no snapshot recorded"
            hours.append({"hour_ist": h, "ist_label": label,
                          "status": st, "note": note})
            continue
        doc, err = _load_doc(info, s3=s3, bucket=bucket)
        if doc is None:
            hours.append({"hour_ist": h, "ist_label": label,
                          "status": "unreadable",
                          "note": "snapshot exists but failed to read — "
                                  f"{err}"})
            continue
        hours.append(_hour_entry(h, doc))

    recorded = [e["hour_ist"] for e in hours if e["status"] == "recorded"]
    gaps = [e["hour_ist"] for e in hours if e["status"] == "gap"]
    pending = [e["hour_ist"] for e in hours if e["status"] == "pending"]
    unread = [e["hour_ist"] for e in hours if e["status"] == "unreadable"]
    if total_all == 0:
        # mandate: an empty archive answers hours:[] — honestly empty,
        # not 24 invented gaps over a recording that never started
        hours = []
    keys = sorted(avail)
    since_ist = last_ist = None
    if keys:
        d0, h0 = keys[0]
        d1, h1 = keys[-1]
        since_ist = f"{d0[:4]}-{d0[4:6]}-{d0[6:8]}T{h0:02d}:00:00+05:30"
        last_ist = f"{d1[:4]}-{d1[4:6]}-{d1[6:8]}T{h1:02d}:00:00+05:30"
    return {
        "day": day_s,
        "tz": TZ_NAME,
        "basis": "recorded",
        "note": ("the served pm2.5 field, snapshotted hourly — what "
                 "delhi actually breathed; /grid?h=… stays the forecast"),
        "generated_ist": ist_now.isoformat(),
        "window_hours": 24,
        "hours": hours,
        "coverage": {
            "recorded": recorded,
            "gaps": gaps,
            "pending": pending,
            "unreadable": unread,
            "recorded_count": len(recorded),
            "gap_count": len(gaps),
        },
        "archive": {
            "total_snapshots": total_all,
            "since_ist": since_ist,
            "last_ist": last_ist,
        },
        "storage": {
            "dir": _root(root),
            "bucket": bucket,
            "s3_prefix": S3_PREFIX if bucket else None,
        },
    }


def status(*, root=None, s3=None, bucket=None, now=None,
           ttl_s: float = _STATUS_TTL_S) -> dict:
    """The admin tile's numbers — every count comes from real files/keys
    (union of the local mirror and the bucket). Cached ttl_s; a busted
    enumeration degrades to the last good answer, never a fake 0."""
    now = time.time() if now is None else now
    c = _STATUS_CACHE
    if c["doc"] is not None and now - c["at"] < ttl_s:
        return dict(c["doc"])
    try:
        avail = _enumerate(root=root, s3=s3, bucket=bucket)
    except Exception as e:  # noqa: BLE001
        if c["doc"] is not None:
            return dict(c["doc"])
        return {"enabled": _enabled(), "snapshots_total": None,
                "error": f"{type(e).__name__}: {e}"}
    ist_now = datetime.fromtimestamp(now, IST)
    today_key = ist_now.strftime("%Y%m%d")
    today_hours = sorted(h for (d, h) in avail if d == today_key)
    keys = sorted(avail)

    def _iso(d, h):
        return f"{d[:4]}-{d[4:6]}-{d[6:8]}T{h:02d}:00:00+05:30"

    doc = {
        "enabled": _enabled(),
        "snapshots_total": len(keys),
        "since_ist": _iso(*keys[0]) if keys else None,
        "last_ist": _iso(*keys[-1]) if keys else None,
        "today": {
            "day": str(ist_now.date()),
            "hours_recorded": len(today_hours),
            "hours_elapsed": ist_now.hour + 1,
            "gaps": [h for h in range(ist_now.hour + 1)
                     if h not in today_hours],
        },
        "storage": {
            "dir": _root(root),
            "bucket": bucket if bucket is not None
            else os.environ.get("ALIVE_AIR_BUCKET"),
            "last_backend": _LAST.get("backend"),
        },
        "last": {k: v for k, v in _LAST.items() if v is not None},
    }
    c.update({"at": now, "doc": dict(doc)})
    return doc


# ------------------------------------------------------------------ loop

def _sleep_to_next_ist_hour(now=None) -> float:
    """Seconds until the next IST hour boundary — snapshots key on the
    bucket they belong to, so the cadence is IST, not UTC."""
    now = time.time() if now is None else now
    ist = datetime.fromtimestamp(now, IST)
    nxt = (ist.replace(minute=0, second=0, microsecond=0)
           + timedelta(hours=1))
    return max(1.0, nxt.timestamp() - now)


async def run_forever(field=None, client_factory=None) -> None:
    """The hourly recorder. Each tick runs the same request-driven
    FIELD.refresh a visitor would trigger — the snapshot stays aligned
    to the field's own 15-min cadence — then captures whatever is
    served. A field serving nothing writes nothing and retries in ~5
    min; every other failure is reported in status() and the loop
    sleeps to the next IST hour."""
    if not _enabled():
        return
    if field is None:
        from airfield import FIELD
        field = FIELD
    await asyncio.sleep(INITIAL_DELAY_S)
    while True:
        try:
            if client_factory is not None:
                await field.refresh(client_factory())
        except Exception:  # noqa: BLE001 - refresh must never sink the
            pass               # recorder; the snapshot says what it saw
        try:
            res = await asyncio.to_thread(capture, field)
        except Exception as e:  # noqa: BLE001
            res = {"ok": False,
                   "error": f"{type(e).__name__}: {e}"}
            _LAST.update(dict(res, at=time.time()))
        wait = SKIP_RETRY_S if not res.get("ok") \
            else _sleep_to_next_ist_hour()
        await asyncio.sleep(wait)
