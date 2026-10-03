"""Offline tests for transit_rt — synthesized GTFS-RT bytes, no network.

Run from server/:
    uv run --with pytest pytest tests/test_transit_rt.py -q
"""
import json
import os
import struct
import sys
import time

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import transit_rt as rt  # noqa: E402


# --- tiny protobuf encoder (mirror of the wire format rt decodes) ----------
def _var(n):
    if n < 0:
        n += 1 << 64
    out = b""
    while True:
        b = n & 0x7F
        n >>= 7
        if n:
            out += bytes([b | 0x80])
        else:
            return out + bytes([b])


def _f(fno, wt, payload):
    return _var((fno << 3) | wt) + payload


def _fvar(fno, n):
    return _f(fno, 0, _var(n))


def _fstr(fno, s):
    b = s.encode()
    return _f(fno, 2, _var(len(b)) + b)


def _fmsg(fno, body):
    return _f(fno, 2, _var(len(body)) + body)


def _ff32(fno, x):
    return _f(fno, 5, struct.pack("<f", x))


def feed(entities, version="2.0", ts=1759492000):
    """Build a FeedMessage: entities = [field 3|4|5 message bodies]."""
    head = _fmsg(1, _fstr(1, version) + _fvar(2, 0) + _fvar(3, ts))
    blob = head
    for fno, body in entities:
        blob += _fmsg(2, _fstr(1, "e%d" % fno) + _fmsg(fno, body))
    return blob


def vp(trip_id=None, route_id=None, veh_id=None, label=None,
       lat=None, lon=None, bearing=None, speed=None, stop_id=None, ts=None):
    t = b""
    if trip_id:
        t += _fstr(1, trip_id)
    if route_id:
        t += _fstr(5, route_id)
    v = b""
    if veh_id:
        v += _fstr(1, veh_id)
    if label:
        v += _fstr(2, label)
    p = b""
    if lat is not None:
        p += _ff32(1, lat)
    if lon is not None:
        p += _ff32(2, lon)
    if bearing is not None:
        p += _ff32(3, bearing)
    if speed is not None:
        p += _ff32(5, speed)
    body = (_fmsg(1, t) if t else b"") + (_fmsg(2, p) if p else b"")
    if ts:
        body += _fvar(5, ts)
    if stop_id:
        body += _fstr(7, stop_id)
    if v:
        body += _fmsg(8, v)
    return body


def tu(trip_id=None, route_id=None, delay=None, ts=None, stops=()):
    t = (_fstr(1, trip_id) if trip_id else b"") + \
        (_fstr(5, route_id) if route_id else b"")
    body = _fmsg(1, t)
    for seq, sid, arr_d, dep_d in stops:
        ev = b""
        if arr_d is not None:
            ev += _fmsg(2, _fvar(1, arr_d))
        if dep_d is not None:
            ev += _fmsg(3, _fvar(1, dep_d))
        body += _fmsg(2, _fvar(1, seq) + ev + _fstr(4, sid))
    if ts:
        body += _fvar(4, ts)
    if delay is not None:
        body += _fvar(5, delay)
    return body


def alert(route_ids=(), start=None, end=None, header=None):
    body = b""
    if start is not None or end is not None:
        body += _fmsg(1, (_fvar(1, start) if start else b"") +
                      (_fvar(2, end) if end else b""))
    for r in route_ids:
        body += _fmsg(5, _fstr(2, r))
    if header:
        body += _fmsg(10, _fmsg(1, _fstr(1, header) + _fstr(2, "en")))
    return body


@pytest.fixture(autouse=True)
def clean_state(monkeypatch):
    """Tests never see leaked _STATE; no network anywhere."""
    monkeypatch.setattr(rt, "_STATE", {
        "vehicles": [], "trip_updates": [], "alerts": [],
        "updated_at": 0.0, "last_poll": {}, "probes": {}, "errors": []})
    yield


# --- parser ----------------------------------------------------------------
def test_parse_vehicle_positions():
    blob = feed([(4, vp(trip_id="T1", route_id="r101", veh_id="DL1PC0001",
                       label="Bus 42", lat=28.6328, lon=77.2197,
                       bearing=90.0, speed=8.5, stop_id="P3",
                       ts=1759491999))])
    p = rt.parse_feed(blob)
    assert p["header"]["version"] == "2.0"
    assert p["header"]["timestamp"] == 1759492000
    assert len(p["vehicles"]) == 1 and not p["trip_updates"]
    v = p["vehicles"][0]
    assert v["trip_id"] == "T1" and v["route_id"] == "r101"
    assert v["vehicle_id"] == "DL1PC0001" and v["vehicle_label"] == "Bus 42"
    assert v["lat"] == pytest.approx(28.6328, abs=1e-4)
    assert v["lon"] == pytest.approx(77.2197, abs=1e-4)
    assert v["speed_mps"] == pytest.approx(8.5, abs=1e-3)
    assert v["stop_id"] == "P3" and v["timestamp"] == 1759491999


def test_parse_trip_updates_with_negative_delay():
    blob = feed([(3, tu(trip_id="T9", route_id="r202", ts=1759491990,
                       stops=[(1, "P3", 300, 305), (2, "Q1", -120, -120)])),
                 (3, tu(trip_id="T10", route_id="r101", delay=45))])
    p = rt.parse_feed(blob)
    assert len(p["trip_updates"]) == 2
    t9 = p["trip_updates"][0]
    assert t9["route_id"] == "r202"
    assert t9["stop_time_updates"][0]["stop_id"] == "P3"
    assert t9["stop_time_updates"][0]["arrival"]["delay_s"] == 300
    # negative delay is encoded as a 64-bit sign-extended varint
    assert t9["stop_time_updates"][1]["arrival"]["delay_s"] == -120
    assert p["trip_updates"][1]["delay_s"] == 45


def test_parse_alert():
    blob = feed([(5, alert(route_ids=["r101"], start=1759490000,
                          header="Route 101 diverted"))])
    p = rt.parse_feed(blob)
    a = p["alerts"][0]
    assert a["route_ids"] == ["r101"]
    assert a["active_period"][0]["start"] == 1759490000
    assert a["header"] == "Route 101 diverted"


def test_parse_rejects_garbage():
    with pytest.raises(ValueError):
        rt.parse_feed(b"")
    with pytest.raises(ValueError):
        rt.parse_feed(b"\xff\xff\xff\xff\xff")
    with pytest.raises(ValueError):
        rt.parse_feed(feed([(4, vp(trip_id="T"))])[:7])   # truncated


def test_unknown_fields_and_wire_types_skipped():
    body = vp(trip_id="T1", lat=28.6, lon=77.2) + _f(20, 1, b"12345678")
    p = rt.parse_feed(feed([(4, body)]))
    assert p["vehicles"][0]["trip_id"] == "T1"


# --- feed_status -----------------------------------------------------------
def test_feed_status_offline_uses_recorded_evidence():
    st = rt.feed_status()
    assert set(st) == {"otd_bus_vehicle_positions", "otd_bus_trip_updates",
                       "community_mirror_nikhilvj", "dmrc_metro"}
    assert st["otd_bus_vehicle_positions"]["status"] == "key-gated"
    assert st["otd_bus_vehicle_positions"]["http_status"] == 401
    assert st["otd_bus_trip_updates"]["status"] == "dead"
    assert st["dmrc_metro"]["status"] == "dead"
    for row in st.values():
        assert row["status"] in ("reachable", "key-gated", "dead", "unknown")
        assert row["evidence"]            # every claim carries its proof
    json.dumps(st)


def test_probe_url_less_source_is_dead():
    rec = rt.probe_source("dmrc_metro")
    assert rec["status"] == "dead"
    rec = rt.probe_source("nonsense")
    assert rec["status"] == "unknown"


# --- honest-empty contract ---------------------------------------------------
def test_delays_empty_and_basis_explains():
    assert rt.delays() == []
    assert rt.delays("r101") == []
    s = rt.status()
    assert s["cached"]["vehicles"] == 0
    assert "no public feed" in s["delays_basis"]
    json.dumps(s)


def test_vehicle_positions_and_alerts_empty():
    assert rt.vehicle_positions() == []
    assert rt.vehicle_positions("r101") == []
    assert rt.alerts() == []


def test_refresh_without_key_never_fetches(monkeypatch):
    monkeypatch.delenv("ALIVE_OTD_API_KEY", raising=False)

    def boom(url, timeout=0):
        raise AssertionError("no network expected: " + url)
    monkeypatch.setattr(rt, "_fetch", boom)
    rep = rt.refresh()
    assert "key-gated" in rep["otd_bus_vehicle_positions"]["skipped"]
    assert "skipped" in rep["otd_bus_trip_updates"]
    assert rep["community_mirror_nikhilvj"]["skipped"].startswith("recorded dead")
    assert rep["dmrc_metro"]["skipped"] == "no public feed URL exists"


def test_refresh_with_key_parses_feed(monkeypatch):
    blob = feed([(4, vp(trip_id="T1", route_id="r101", veh_id="V1",
                        lat=28.61, lon=77.21, ts=int(time.time())))])
    urls = []

    def fake_fetch(url, timeout=0):
        urls.append(url)
        # only the vehicle feed serves entities; every other URL gets a
        # valid header-only feed, like a live-but-empty TripUpdates
        return blob if "VehiclePositions" in url else feed([])
    monkeypatch.setenv("ALIVE_OTD_API_KEY", "TESTKEY")
    monkeypatch.setattr(rt, "_fetch", fake_fetch)
    monkeypatch.setattr(rt, "POLL_MIN_S", 0)
    rep = rt.refresh()
    assert rep["otd_bus_vehicle_positions"]["parsed"]["vehicles"] == 1
    # key rides along as the documented query param
    assert "https://otd.delhi.gov.in/api/realtime/" \
        "VehiclePositions.pb?key=TESTKEY" in urls
    vs = rt.vehicle_positions()
    assert len(vs) == 1 and vs[0]["feed"] == "otd_bus_vehicle_positions"
    assert vs[0]["vehicle_id"] == "V1"
    assert rt.vehicle_positions("nope") == []


def test_refresh_stale_entities_expired(monkeypatch):
    blob = feed([(4, vp(trip_id="T1", veh_id="V1", lat=28.6, lon=77.2))])
    monkeypatch.setenv("ALIVE_OTD_API_KEY", "K")
    monkeypatch.setattr(rt, "_fetch",
                        lambda u, timeout=0: blob
                        if "VehiclePositions" in u else feed([]))
    monkeypatch.setattr(rt, "POLL_MIN_S", 0)
    rt.refresh()
    rt._STATE["updated_at"] = time.time() - rt.ENTITY_TTL_S - 1
    assert rt.vehicle_positions() == []      # stale data dies, not served


def test_delays_flow_through_when_feed_supplies(monkeypatch):
    blob = feed([(3, tu(trip_id="T9", route_id="r202",
                        stops=[(1, "P3", 300, None)])),
                 (3, tu(trip_id="T10", route_id="r101", delay=45))])
    monkeypatch.setenv("ALIVE_OTD_API_KEY", "K")
    monkeypatch.setattr(rt, "_fetch",
                        lambda u, timeout=0: blob
                        if "VehiclePositions" in u else feed([]))
    monkeypatch.setattr(rt, "POLL_MIN_S", 0)
    rt.refresh()
    d = rt.delays()
    assert len(d) == 2
    p3 = [x for x in d if x["stop_id"] == "P3"][0]
    assert p3["delay_s"] == 300 and p3["feed"] == "otd_bus_vehicle_positions"
    only_r202 = rt.delays("r202")
    assert len(only_r202) == 1 and only_r202[0]["trip_id"] == "T9"
    json.dumps(d)


def test_refresh_polls_all_sources_once_keyed(monkeypatch):
    """With a key, the 404'd trip-updates URL still gets one honest try —
    the recorded 404 isn't trusted forever."""
    seen = []
    monkeypatch.setenv("ALIVE_OTD_API_KEY", "K")
    monkeypatch.setattr(rt, "_fetch",
                        lambda u, timeout=0: seen.append(u) or b"\x08\x01")
    monkeypatch.setattr(rt, "POLL_MIN_S", 0)
    rt.refresh()
    assert any("VehiclePositions" in u for u in seen)
    assert any("TripUpdates" in u for u in seen)
