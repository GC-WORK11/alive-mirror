"""Offline tests for transit_v2 — tiny hand-built GTFS fixture feeds.

Run from server/:
    .venv/bin/python -m pytest tests/test_transit_v2.py -q
"""
import csv
import datetime as dt
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import transit_v2 as tv  # noqa: E402

IST = tv.IST
MON = dt.date(2026, 10, 5)
SUN = dt.date(2026, 10, 4)


def at(h, m, s=0, day=MON):
    return dt.datetime(day.year, day.month, day.day, h, m, s, tzinfo=IST)


def hms(sec):
    return f"{sec // 3600:02d}:{sec % 3600 // 60:02d}:{sec % 60:02d}"


def write_gtfs(root, stops, lines, calendar=None):
    """stops: {id: (name, lat, lon)}; lines: [(route_id, short, long,
    [stop ids], hop_s, first_dep_s, headway_s, n_trips[, service])]."""
    os.makedirs(root, exist_ok=True)

    def w(name, header, rows):
        with open(os.path.join(root, name), "w", newline="") as fh:
            cw = csv.writer(fh)
            cw.writerow(header)
            cw.writerows(rows)

    w("stops.txt", ["stop_id", "stop_name", "stop_lat", "stop_lon"],
      [(k, n, la, lo) for k, (n, la, lo) in stops.items()])
    w("routes.txt", ["route_id", "route_short_name", "route_long_name", "route_type"],
      [(l[0], l[1], l[2], 1) for l in lines])
    trips, st = [], []
    for l in lines:
        rid, _, _, seq, hop, first, head, n = l[:8]
        svc = l[8] if len(l) > 8 else "all"
        for k in range(n):
            tid = f"{rid}_{k}"
            trips.append((rid, svc, tid, ""))
            t = first + k * head
            for i, s in enumerate(seq):
                st.append((tid, hms(t + i * hop), hms(t + i * hop), s, i))
    w("trips.txt", ["route_id", "service_id", "trip_id", "trip_headsign"], trips)
    w("stop_times.txt", ["trip_id", "arrival_time", "departure_time",
                         "stop_id", "stop_sequence"], st)
    if calendar:
        w("calendar.txt", ["service_id", "monday", "tuesday", "wednesday",
                           "thursday", "friday", "saturday", "sunday",
                           "start_date", "end_date"], calendar)
    return root


SIX = 6 * 3600
METRO_STOPS = {
    "A": ("Alpha", 28.600, 77.150), "B": ("Bravo", 28.600, 77.170),
    "C": ("Charlie", 28.600, 77.190), "D": ("Delta Sec -18", 28.600, 77.210),
    "N": ("North", 28.620, 77.190), "S": ("South", 28.580, 77.190),
    "E": ("Echo", 28.6015, 77.2120), "F": ("Foxtrot", 28.600, 77.240),
}
METRO_LINES = [
    ("blue", "B_AD", "BLUE_Alpha to Delta", ["A", "B", "C", "D"], 120, SIX, 300, 60),
    ("yel", "Y_NS", "YELLOW_North to South", ["N", "C", "S"], 120, SIX, 300, 60),
    ("aqua", "A_EF", "AQUA_Echo to Foxtrot", ["E", "F"], 240, SIX, 300, 60),
]

BUS_STOPS = {f"P{i}": (f"Stop P{i}", 28.65, 77.10 + 0.01 * i) for i in range(6)}
BUS_STOPS.update({"Q1": ("Stop Q1", 28.67, 77.13), "Q2": ("Stop Q2", 28.69, 77.13)})
BUS_LINES = [
    ("r101", "", "101UP", ["P0", "P1", "P2", "P3", "P4", "P5"], 180, SIX, 600, 30),
    ("r202", "", "202DOWN", ["P3", "Q1", "Q2"], 180, SIX + 60, 600, 30),
]


@pytest.fixture
def metro(tmp_path):
    return tv.load_feed(write_gtfs(str(tmp_path / "metro"), METRO_STOPS,
                                   METRO_LINES), "metro")


@pytest.fixture
def bus(tmp_path):
    return tv.load_feed(write_gtfs(str(tmp_path / "bus"), BUS_STOPS,
                                   BUS_LINES), "bus")


def only(opts, mode_prefix):
    hits = [o for o in opts if o["mode"].startswith(mode_prefix)]
    assert len(hits) == 1, opts
    return hits[0]


# --- feed compile ---------------------------------------------------------
def test_load_feed_compiles_sorted_connections(metro):
    assert len(metro.stop_ids) == 8
    assert len(metro.c_dep) == 60 * (3 + 2 + 1)
    assert list(metro.c_dep) == sorted(metro.c_dep)
    assert "Delta Sector 18" in metro.names          # name cleanup
    assert set(metro.trip_line) == {"Blue", "Yellow", "Aqua"}
    d, e = metro.stop_ids.index("D"), metro.stop_ids.index("E")
    assert any(j == e for j, _, _ in metro.footpaths[d])   # ~257 m link
    a = metro.stop_ids.index("A")
    assert metro.footpaths[a] == []


def test_bus_route_names_strip_direction(bus):
    assert set(bus.trip_line) == {"101", "202"}


def test_pickle_cache_roundtrip(tmp_path):
    root = write_gtfs(str(tmp_path / "m"), METRO_STOPS, METRO_LINES)
    f1 = tv.load_feed(root, "metro")
    assert os.path.exists(os.path.join(root, tv.INDEX_NAME))
    f2 = tv.load_feed(root, "metro")
    assert list(f2.c_arr) == list(f1.c_arr)
    assert f2.footpaths == f1.footpaths


def test_unknown_kind_rejected(tmp_path):
    with pytest.raises(ValueError):
        tv.load_feed(str(tmp_path), "tram")


# --- metro ----------------------------------------------------------------
def test_direct_metro_uses_next_scheduled_departure(metro):
    opts = tv.plan_transit(28.6005, 77.150, 28.6005, 77.210,
                           at(8, 1), feeds={"metro": metro})
    o = only(opts, "metro")
    assert o["mode"] == "metro"
    assert o["transfers"] == 0
    assert [l["type"] for l in o["legs"]] == ["walk", "metro", "walk"]
    ride = o["legs"][1]
    assert ride["line"] == "Blue"
    assert ride["from"]["name"] == "Alpha"
    assert ride["to"]["name"] == "Delta Sector 18"
    assert ride["depart_at"] == at(8, 5).isoformat()     # 08:01 + walk + entry
    assert ride["arrive_at"] == at(8, 11).isoformat()
    assert ride["stops"] == 3 and ride["duration_s"] == 360
    assert len(ride["geometry"]["coordinates"]) == 4
    # 08:01 -> 08:11 alight (access walk is inside that window) + exit + egress
    assert o["duration_s"] == pytest.approx(
        10 * 60 + 60 + o["legs"][-1]["duration_s"], abs=1)
    assert o["walk_m"] < 150


def test_depart_at_changes_wait(metro):
    early = only(tv.plan_transit(28.600, 77.150, 28.600, 77.210, at(8, 1, 50),
                                 feeds={"metro": metro}), "metro")
    late = only(tv.plan_transit(28.600, 77.150, 28.600, 77.210, at(8, 2, 30),
                                feeds={"metro": metro}), "metro")
    assert early["legs"][1]["depart_at"] == at(8, 5).isoformat()
    assert late["legs"][1]["depart_at"] == at(8, 10).isoformat()
    assert early["legs"][1]["wait_s"] == 300 - 110 - 180
    assert late["duration_s"] > early["duration_s"]


def test_interchange_same_station(metro):
    o = only(tv.plan_transit(28.600, 77.150, 28.580, 77.190, at(8, 1),
                             feeds={"metro": metro}), "metro")
    assert o["transfers"] == 1
    assert o["lines"] == ["Blue", "Yellow"]
    types = [l["type"] for l in o["legs"]]
    assert types == ["walk", "metro", "metro", "walk"]
    blue, yellow = o["legs"][1], o["legs"][2]
    assert blue["to"]["name"] == yellow["from"]["name"] == "Charlie"
    assert yellow["wait_s"] >= tv.FEEDS["metro"]["change_s"]


def test_walking_transfer_between_distinct_stops(metro):
    o = only(tv.plan_transit(28.600, 77.150, 28.600, 77.240, at(8, 1),
                             feeds={"metro": metro}), "metro")
    types = [l["type"] for l in o["legs"]]
    assert types == ["walk", "metro", "walk", "metro", "walk"]
    xfer = o["legs"][2]
    assert xfer.get("transfer") is True
    assert (xfer["from"]["name"], xfer["to"]["name"]) == ("Delta Sector 18", "Echo")
    assert 200 < xfer["distance_m"] < tv.WALK_LINK_M
    assert o["transfers"] == 1 and o["lines"] == ["Blue", "Aqua"]


def test_long_access_walk_labelled_metro_plus_walk(metro):
    o = only(tv.plan_transit(28.600, 77.140, 28.600, 77.210, at(8, 0),
                             feeds={"metro": metro}), "metro")
    assert o["mode"] == "metro+walk"
    assert o["walk_m"] > tv.METRO_WALK_M


def test_out_of_network_returns_empty(metro):
    assert tv.plan_transit(28.30, 76.90, 28.600, 77.210, at(8, 0),
                           feeds={"metro": metro}) == []


def test_short_hop_walking_wins(metro):
    assert tv.plan_transit(28.600, 77.170, 28.600, 77.173, at(8, 0),
                           feeds={"metro": metro}) == []


def test_no_service_late_night(metro):
    # last Blue trip leaves Alpha 06:00 + 59*5min = 10:55
    assert tv.plan_transit(28.600, 77.150, 28.600, 77.210, at(13, 0),
                           feeds={"metro": metro}) == []


# --- depart_at forms ------------------------------------------------------
@pytest.mark.parametrize("when", [
    at(8, 1),
    at(8, 1).isoformat(),
    at(8, 1).timestamp(),
    dt.datetime(2026, 10, 5, 8, 1),                       # naive = IST
    at(8, 1).astimezone(dt.timezone.utc).isoformat().replace("+00:00", "Z"),
])
def test_depart_at_forms_agree(metro, when):
    o = only(tv.plan_transit(28.600, 77.150, 28.600, 77.210, when,
                             feeds={"metro": metro}), "metro")
    assert o["depart_at"] == at(8, 1).isoformat()
    assert o["legs"][1]["depart_at"] == at(8, 5).isoformat()


# --- bus ------------------------------------------------------------------
def test_bus_with_transfer(bus):
    opts = tv.plan_transit(28.65, 77.10, 28.69, 77.13, at(7, 0),
                           feeds={"bus": bus})
    o = only(opts, "bus")
    assert o["mode"] == "bus"
    assert o["lines"] == ["101", "202"]
    assert o["transfers"] == 1
    r1, r2 = o["legs"][1], o["legs"][2]
    assert r1["from"]["name"] == "Stop P0" and r1["to"]["name"] == "Stop P3"
    assert r2["from"]["name"] == "Stop P3" and r2["to"]["name"] == "Stop Q2"
    assert r1["depart_at"] == at(7, 0).isoformat()
    assert r1["arrive_at"] == at(7, 9).isoformat()
    # 202 leaves P3 at 06:01 + 10k min -> 07:11 is the first after 07:09 + 2 min
    assert r2["depart_at"] == at(7, 11).isoformat()


def test_transfer_penalty_prefers_direct(tmp_path):
    stops = {"O": ("Origin", 28.70, 77.00), "M": ("Mid", 28.70, 77.03),
             "T": ("Target", 28.70, 77.06)}
    lines = [
        ("x", "", "XUP", ["O", "M"], 300, SIX, 900, 10),
        ("y", "", "YUP", ["M", "T"], 300, SIX + 420, 900, 10),   # fast w/ change
        ("z", "", "ZUP", ["O", "M", "T"], 450, SIX, 900, 10),    # direct, +3 min
    ]
    feed = tv.load_feed(write_gtfs(str(tmp_path / "b"), stops, lines), "bus")
    o = only(tv.plan_transit(28.70, 77.00, 28.70, 77.06, at(6, 0),
                             feeds={"bus": feed}), "bus")
    assert o["lines"] == ["Z"] and o["transfers"] == 0

    lines[2] = ("z", "", "ZUP", ["O", "M", "T"], 600, SIX, 900, 10)   # +9 min
    feed = tv.load_feed(write_gtfs(str(tmp_path / "b2"), stops, lines), "bus")
    o = only(tv.plan_transit(28.70, 77.00, 28.70, 77.06, at(6, 0),
                             feeds={"bus": feed}), "bus")
    assert o["lines"] == ["X", "Y"] and o["transfers"] == 1


def test_after_midnight_service_day(tmp_path):
    stops = {"O": ("Origin", 28.70, 77.00), "T": ("Target", 28.70, 77.05)}
    lines = [("n", "", "NIGHTUP", ["O", "T"], 600, 24 * 3600 + 600, 1800, 3)]
    feed = tv.load_feed(write_gtfs(str(tmp_path / "n"), stops, lines), "bus")
    o = only(tv.plan_transit(28.70, 77.00, 28.70, 77.05, at(0, 5),
                             feeds={"bus": feed}), "bus")
    assert o["legs"][1]["depart_at"] == at(0, 10).isoformat()
    assert o["arrive_at"].startswith("2026-10-05T00:2")


def test_calendar_filters_service_days(tmp_path):
    lines = [l + ("wk",) for l in METRO_LINES]
    cal = [("wk", 1, 1, 1, 1, 1, 0, 0, "20260101", "20261231")]
    feed = tv.load_feed(write_gtfs(str(tmp_path / "c"), METRO_STOPS, lines,
                                   calendar=cal), "metro")
    args = (28.600, 77.150, 28.600, 77.210)
    assert tv.plan_transit(*args, at(8, 0, day=MON), feeds={"metro": feed})
    assert tv.plan_transit(*args, at(8, 0, day=SUN), feeds={"metro": feed}) == []


# --- combined / contract --------------------------------------------------
def test_combined_sorted_and_json_contract(metro, bus):
    # both networks overlap this fixture pair only via metro; add a bus
    # trip pair to the same call to check sorting + shape
    opts = tv.plan_transit(28.600, 77.150, 28.600, 77.210, at(8, 1),
                           feeds={"metro": metro, "bus": bus})
    assert [o["mode"] for o in opts] == ["metro"]
    opts += tv.plan_transit(28.65, 77.10, 28.69, 77.13, at(7, 0),
                            feeds={"metro": metro, "bus": bus})
    json.dumps(opts)
    for o in opts:
        assert o["mode"] in ("metro", "bus", "metro+walk")
        for key in ("legs", "duration_s", "walk_m", "transfers"):
            assert key in o
        assert o["legs"][0]["type"] == "walk" and o["legs"][-1]["type"] == "walk"
        assert o["transfers"] == sum(l["type"] != "walk" for l in o["legs"]) - 1
        assert o["walk_m"] == pytest.approx(
            sum(l["distance_m"] for l in o["legs"] if l["type"] == "walk"), abs=2)


def test_plan_sorts_fastest_first(tmp_path, metro):
    stops = {"A2": ("Alpha bus", 28.600, 77.150), "D2": ("Delta bus", 28.600, 77.210)}
    lines = [("s", "", "SLOWUP", ["A2", "D2"], 2400, SIX, 600, 60)]
    slow_bus = tv.load_feed(write_gtfs(str(tmp_path / "sb"), stops, lines), "bus")
    opts = tv.plan_transit(28.600, 77.150, 28.600, 77.210, at(8, 1),
                           feeds={"metro": metro, "bus": slow_bus})
    assert [o["mode"] for o in opts] == ["metro", "bus"]
    assert opts[0]["duration_s"] < opts[1]["duration_s"]


def test_default_feeds_reads_cache_dir(tmp_path, monkeypatch):
    write_gtfs(str(tmp_path / "metro"), METRO_STOPS, METRO_LINES)
    monkeypatch.setattr(tv, "CACHE_DIR", str(tmp_path))
    monkeypatch.setattr(tv, "_FEEDS", {})
    feeds = tv.default_feeds()
    assert set(feeds) == {"metro"}
    assert tv.plan_transit(28.600, 77.150, 28.600, 77.210, at(8, 1))


@pytest.mark.parametrize("raw,expected", [
    # feed-id slug shapes suppress to a boardable 'Bus' — the dotted
    # variant 'AIRPORTEXP.-4' was served on prod as 'Bus AIRPORTEXP.-4'
    ("0AIRPORTEXP-4(NS)", "Bus"), ("0AIRPORTEXP.-4(NS)", "Bus"),
    ("AIRPORTEXP.-4", "Bus"), ("CGOCOMPLEX-2", "Bus"), ("LNWST-1", "Bus"),
    ("EXPRESS-20A", "Bus"),
    # real names and short board names survive
    ("0OMS(-)(NS)", "OMS"), ("0TMS(+)(NS)", "TMS"), ("347ACL", "347ACL"),
    ("347AUP", "347A"), ("101UP", "101"), ("HOHO", "HOHO"),
    ("Airport Express (Night)", "Airport Express (Night)"), ("0334", "0334"),
])
def test_line_name_suppresses_feed_ids(raw, expected):
    assert tv.line_name("bus", raw, "") == expected


def test_line_name_metro_pretty():
    assert tv.line_name("metro", "", "BLUE_Dwarka to Noida") == "Blue"
