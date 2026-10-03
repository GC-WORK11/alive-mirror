"""Deep-health tests for health.collect_health — the /health payload.

Field age is resolved against the on-disk snapshot mirror
(data/field/snapshots/YYYY/MM/DD/HHmm.json.gz — the same tree
ingest_worker writes and rollup.latest_snapshot reads). Everything is
seeded in tmp_path at known timestamps; no network, no AWS.
"""
import gzip
import json
import os
import sys
from datetime import datetime, timezone

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import health  # noqa: E402

# Fixed probe instant: 2026-10-03T03:00:00Z. All ages below are exact.
NOW = datetime(2026, 10, 3, 3, 0, 0, tzinfo=timezone.utc).timestamp()


def _epoch(y, mo, d, h, mi, s=0):
    return datetime(y, mo, d, h, mi, s, tzinfo=timezone.utc).timestamp()


def _seed(root, rel, payload=None, mtime=None, raw=None):
    """Write a snapshot file at root/rel. `payload` is gzip'd JSON;
    `raw` writes bytes verbatim (corrupt-snapshot fixture)."""
    path = os.path.join(str(root), rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if raw is not None:
        with open(path, "wb") as f:
            f.write(raw)
    else:
        blob = gzip.compress(
            json.dumps(payload or {}).encode("utf-8"), mtime=0)
        with open(path, "wb") as f:
            f.write(blob)
    if mtime is not None:
        os.utime(path, (mtime, mtime))
    return path


def _field_payload(built_epoch, prov=None):
    return {"schema": "alive-airindex/1",
            "built_epoch": built_epoch,
            "built_at": datetime.fromtimestamp(
                built_epoch, tz=timezone.utc).isoformat(timespec="seconds"),
            "grid": {"system": "latlon-fallback", "n_cells": 42},
            "provenance": prov or {}}


# ---------------------------------------------------------------- field age

def test_field_age_exact_from_built_epoch(tmp_path):
    """Payload built_epoch wins: exact generated_at, not path-minute."""
    built = _epoch(2026, 10, 3, 2, 2, 20)           # 02:02:20, age 3460s
    _seed(tmp_path, "2026/10/03/0202.json.gz",
          payload=_field_payload(built),
          mtime=NOW - 60)                            # copied in a minute ago
    h = health.collect_health(now=NOW, snapshot_root=str(tmp_path))
    assert h["field_age_s"] == pytest.approx(3460.0)
    assert h["field"]["snapshot"] == "2026/10/03/0202.json.gz"
    assert h["field"]["built_at"] == "2026-10-03T02:02:20+00:00"
    assert h["field"]["cells"] == 42


def test_field_age_path_derived_when_payload_unreadable(tmp_path):
    """Corrupt gzip: age still honest, derived from the path timestamp."""
    gen = _epoch(2026, 10, 3, 2, 30)                 # 02:30, age 1800s
    _seed(tmp_path, "2026/10/03/0230.json.gz", raw=b"\x1f\x8b broken",
          mtime=NOW - 5)
    h = health.collect_health(now=NOW, snapshot_root=str(tmp_path))
    assert h["field_age_s"] == pytest.approx(NOW - gen)
    assert h["field"]["snapshot"] == "2026/10/03/0230.json.gz"


def test_mtime_does_not_fake_freshness(tmp_path):
    """A snapshot backfilled/copied just now still reports its true
    generated_at age — mtime is never a proxy for field freshness."""
    built = _epoch(2026, 10, 3, 0, 30)               # generated 2.5 h ago
    _seed(tmp_path, "2026/10/03/0030.json.gz",
          payload=_field_payload(built), mtime=NOW)  # landed on disk NOW
    assert health._field_age_s(NOW, str(tmp_path)) == pytest.approx(9000.0)


def test_newest_snapshot_wins(tmp_path):
    for hhmm, ep in (("0115", _epoch(2026, 10, 3, 1, 15)),
                     ("0245", _epoch(2026, 10, 3, 2, 45)),
                     ("0130", _epoch(2026, 10, 3, 1, 30))):
        _seed(tmp_path, f"2026/10/03/{hhmm}.json.gz",
              payload=_field_payload(ep))
    h = health.collect_health(now=NOW, snapshot_root=str(tmp_path))
    assert h["field"]["snapshot"] == "2026/10/03/0245.json.gz"
    assert h["field_age_s"] == pytest.approx(900.0)


def test_empty_dir_is_null_not_crash(tmp_path):
    h = health.collect_health(now=NOW, snapshot_root=str(tmp_path))
    assert h["ok"] is True
    assert h["field_age_s"] is None
    assert h["field"]["snapshot"] is None
    assert set(h["sources"]) == {"model", "met", "stations",
                               "fires", "location"}


def test_missing_dir_is_null_not_crash(tmp_path):
    h = health.collect_health(
        now=NOW, snapshot_root=str(tmp_path / "never-made"))
    assert h["field_age_s"] is None


def test_malformed_names_skipped(tmp_path):
    """Every non-convention file is ignored; with nothing valid left the
    answer is null — and a malformed file with a NEWER mtime must never
    shadow the real newest snapshot."""
    valid = _epoch(2026, 10, 3, 1, 0)                # 01:00, age 7200s
    _seed(tmp_path, "2026/10/03/0100.json.gz",
          payload=_field_payload(valid), mtime=NOW - 3600)
    malformed = [
        "2026/10/03/latest.json.gz",      # not HHmm
        "2026/10/03/2561.json.gz",        # hour 25, minute 61 — invalid
        "2026/13/40/1260.json.gz",        # month 13, day 40 — invalid
        "junk/0459.json.gz",              # not under YYYY/MM/DD
        "2026/10/03/0300.txt",            # not a snapshot blob
        "README.md",
    ]
    for i, rel in enumerate(malformed):
        _seed(tmp_path, rel, payload=_field_payload(NOW),
              mtime=NOW - i)              # all newer than the valid file
    h = health.collect_health(now=NOW, snapshot_root=str(tmp_path))
    assert h["field"]["snapshot"] == "2026/10/03/0100.json.gz"
    assert h["field_age_s"] == pytest.approx(7200.0)


def test_only_malformed_is_null(tmp_path):
    _seed(tmp_path, "2026/10/03/latest.json.gz", payload=_field_payload(NOW))
    _seed(tmp_path, "notes.txt", raw=b"hi")
    assert health._field_age_s(NOW, str(tmp_path)) is None


# ---------------------------------------------------------------- deep health

def test_per_source_ages_from_provenance(tmp_path):
    """model/met/stations/fires carry now - fetched_at, recomputed at
    probe time; status is the last build's own verdict."""
    built = _epoch(2026, 10, 3, 2, 45)
    prov = {
        "model": {"status": "ok",
                  "fetched_at": "2026-10-03T02:44:00+00:00",
                  "source": "open-meteo/cams", "n_points": 48},
        "stations": {"status": "unavailable: no key",
                     "fetched_at": "2026-10-03T02:44:30+00:00",
                     "source": "openaq-v3", "n_used": 0},
        "fires": {"status": "ok",
                  "fetched_at": "2026-10-03T02:44:45+00:00",
                  "source": "nasa-firms-public-csv", "n_fires": 72},
        "met": {"status": "ok",
                "fetched_at": "2026-10-03T02:44:10+00:00",
                "source": "open-meteo", "vc_m2s": 3120.15},
    }
    _seed(tmp_path, "2026/10/03/0245.json.gz",
          payload=_field_payload(built, prov))
    h = health.collect_health(now=NOW, snapshot_root=str(tmp_path))
    s = h["sources"]
    assert s["model"]["age_s"] == pytest.approx(960.0)      # 16 min stale
    assert s["model"]["status"] == "ok"
    assert s["met"]["age_s"] == pytest.approx(950.0)
    assert s["stations"]["age_s"] == pytest.approx(930.0)
    assert s["stations"]["status"] == "unavailable: no key"  # honest, not "up"
    assert s["fires"]["age_s"] == pytest.approx(915.0)
    # location has no snapshot provenance — config-presence only
    assert s["location"]["age_s"] is None
    assert s["location"]["status"] is None


def test_source_env_override_still_wins(tmp_path, monkeypatch):
    monkeypatch.setenv("SOURCE_STATIONS_UP", "false")
    built = _epoch(2026, 10, 3, 2, 45)
    _seed(tmp_path, "2026/10/03/0245.json.gz",
          payload=_field_payload(built, {
              "stations": {"status": "ok",
                           "fetched_at": "2026-10-03T02:40:00+00:00"}}))
    h = health.collect_health(now=NOW, snapshot_root=str(tmp_path))
    st = h["sources"]["stations"]
    assert st["up"] is False                       # override honoured
    assert st["age_s"] == pytest.approx(1200.0)    # provenance still shown


def test_disk_signal(tmp_path):
    h = health.collect_health(now=NOW, snapshot_root=str(tmp_path))
    d = h["disk"]
    assert d["total_bytes"] and d["total_bytes"] > 0
    assert d["free_bytes"] is not None and 0 <= d["free_bytes"] <= d["total_bytes"]
    assert 0 <= d["free_pct"] <= 100
    assert isinstance(d["low"], bool)
    assert d["path"] == str(tmp_path)


def test_payload_shape_and_types(tmp_path):
    h = health.collect_health(now=NOW, snapshot_root=str(tmp_path))
    for key in ("ok", "ts", "build_sha", "version", "uptime_s",
                "field_age_s", "field", "disk", "sources"):
        assert key in h
    assert h["ts"] == NOW
    assert isinstance(h["build_sha"], str) and h["build_sha"]
    for src in h["sources"].values():
        assert src["up"] in (True, False, None)
        assert isinstance(src["detail"], str)


def test_real_mirror_tree_matches_writer_convention():
    """The checked-in mirror (data/field/snapshots/**) parses under the
    ingest_worker convention — guards the regex against repo drift."""
    path, rel, ts = health._newest_snapshot(health.SNAPSHOT_DIR)
    assert path is not None, "no convention-named snapshot in the mirror"
    assert rel == "2026/10/03/0202.json.gz"
    assert ts == _epoch(2026, 10, 3, 2, 2)
