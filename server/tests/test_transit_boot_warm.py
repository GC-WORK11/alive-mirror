"""Boot-warm tests for the GTFS transit layer — all offline.

The cold-start being guarded: an image without data/gtfs used to lazily
download ~120 MB of feeds and parse ~3.3M stop_times inside request
budgets — degraded:["transit"] for ~60 min on a fresh task. The deploy
image now bakes data/gtfs (Dockerfile -> tools/bake_gtfs.py) and boot
warm compiles the indexes before healthy; when feeds are still landing
the retry path compiles them off-request as soon as they appear.

These tests pin the mechanics that make that work — fixture feeds only,
zero network:

  * feeds_on_disk() reports presence/honest absence;
  * ensure_loaded()'s background pipeline loads a fixture feed WITHOUT
    calling _download_feed (fresh cache never re-fetches);
  * default_feeds() picks up a feed that appears AFTER a first call —
    the contract the boot retry loop relies on.

Run from server/:
    .venv/bin/python -m pytest tests/test_transit_boot_warm.py -q
"""
import os
import sys
import time

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import transit_real as tr  # noqa: E402
import transit_v2 as tv    # noqa: E402

from test_transit_v2 import (  # noqa: E402
    write_gtfs, at, METRO_STOPS, METRO_LINES)

BUS_STOPS = {f"P{i}": (f"Stop P{i}", 28.65, 77.10 + 0.01 * i)
             for i in range(6)}
BUS_LINES = [
    ("r1", "764", "764", ["P0", "P1", "P2", "P3", "P4", "P5"],
     180, 6 * 3600, 600, 30),
]


def _state_restore():
    """Snapshot _STATE/_FEEDS so a test can mutate and restore them."""
    saved_state = {k: tr._STATE[k] for k in
                   ("metro", "bus", "loading", "next_retry")}
    saved_errs = list(tr._STATE["errors"])
    saved_feeds = dict(tv._FEEDS)
    return saved_state, saved_errs, saved_feeds


def _state_put(saved):
    saved_state, saved_errs, saved_feeds = saved
    tr._STATE.update(saved_state)
    tr._STATE["errors"][:] = saved_errs
    tv._FEEDS.clear()
    tv._FEEDS.update(saved_feeds)


@pytest.fixture
def fake_cache(tmp_path, monkeypatch):
    """Point both modules' CACHE_DIR at a tmp dir; return its path."""
    monkeypatch.setattr(tr, "CACHE_DIR", str(tmp_path))
    monkeypatch.setattr(tv, "CACHE_DIR", str(tmp_path))
    return tmp_path


def test_feeds_on_disk_honest_about_absence(fake_cache):
    assert tr.feeds_on_disk() is False


def test_feeds_on_disk_true_with_fixture(fake_cache):
    write_gtfs(str(fake_cache / "metro"), METRO_STOPS, METRO_LINES)
    assert tr.feeds_on_disk() is False      # bus still missing — honest
    write_gtfs(str(fake_cache / "bus"), BUS_STOPS, BUS_LINES)
    assert tr.feeds_on_disk() is True


def test_ensure_loaded_loads_fixture_without_download(fake_cache,
                                                      monkeypatch):
    """The warm path: kicked once, the background thread must load the
    on-disk feeds and NOT hit the network (fresh cache is not stale)."""
    write_gtfs(str(fake_cache / "metro"), METRO_STOPS, METRO_LINES)
    write_gtfs(str(fake_cache / "bus"), BUS_STOPS, BUS_LINES)

    downloads = []

    def _no_download(feed):
        downloads.append(feed)
        return None
    monkeypatch.setattr(tr, "_download_feed", _no_download)

    saved = _state_restore()
    try:
        tr._STATE["metro"] = tr._STATE["bus"] = None
        tr._STATE["loading"] = False
        tr._STATE["next_retry"] = 0.0
        tr.ensure_loaded()
        deadline = time.time() + 30
        while time.time() < deadline and \
                (tr._STATE["metro"] is None or tr._STATE["bus"] is None):
            time.sleep(0.1)
        assert tr._STATE["metro"] is not None, "metro feed never loaded"
        assert tr._STATE["bus"] is not None, "bus feed never loaded"
        assert not downloads, \
            f"fresh fixture feeds triggered downloads: {downloads}"
        # and the serving call paths work off what it loaded
        j = tr.metro_journey(28.600, 77.150, 28.600, 77.210)
        assert j is not None and j["board"] == "Alpha"
        h = tr.bus_hint(28.65, 77.10, 28.65, 77.15)
        assert h and "764" in h["direct_routes"]
    finally:
        _state_put(saved)


def test_default_feeds_compiles_late_arriving_feed(fake_cache):
    """The retry-loop contract: a feed dir that appears between calls is
    picked up on the next one — the boot loop never has to restart the
    process to serve it."""
    saved = _state_restore()
    try:
        tv._FEEDS.clear()
        write_gtfs(str(fake_cache / "metro"), METRO_STOPS, METRO_LINES)
        first = tv.default_feeds()
        assert set(first) == {"metro"}

        write_gtfs(str(fake_cache / "bus"), BUS_STOPS, BUS_LINES)
        second = tv.default_feeds()
        assert set(second) == {"metro", "bus"}

        # plan_transit routes off the compiled feeds — a real CSA answer
        # from the fixture, not a stub (fixture trips run 06:00-08:30 IST)
        opts = tv.plan_transit(28.600, 77.150, 28.600, 77.210,
                               depart_at=at(6, 30), feeds=second)
        assert opts and opts[0]["duration_model"] == "gtfs"
    finally:
        _state_put(saved)
