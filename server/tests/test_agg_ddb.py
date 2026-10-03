"""Offline tests for agg_ddb — a fake DynamoDB client stands in for AWS.

No boto3, no credentials, no network. The fake parses the UpdateExpression
shapes agg_ddb emits (SET/ADD over N and SS attributes) so the assertions
run against real call semantics, not mocks that always succeed.
Run from server/:  .venv/bin/python -m pytest tests/test_agg_ddb.py -v
"""
import os
import sys
import time

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import agg_ddb           # noqa: E402
from v2 import store as memstore  # noqa: E402


class FakeDDB:
    """Minimal DynamoDB: update_item (SET/ADD on N/SS), scan, delete_item."""

    def __init__(self, fail_on=()):
        self.items = {}
        self.calls = []
        self.fail_on = set(fail_on)

    # -- expression handling --------------------------------------------
    @staticmethod
    def _resolve(name, names):
        return (names or {}).get(name, name)

    def _apply(self, item, expr, names, values):
        rest = expr.strip()
        if rest.startswith("SET "):
            rest = rest[4:]
            if " ADD " in rest:
                set_part, add_part = rest.split(" ADD ", 1)
            else:
                set_part, add_part = rest, ""
        elif rest.startswith("ADD "):
            set_part, add_part = "", rest[4:]
        else:
            raise AssertionError(f"unhandled expression: {expr}")
        for assign in set_part.split(","):
            assign = assign.strip()
            if not assign:
                continue
            attr, ref = [x.strip() for x in assign.split("=")]
            item[self._resolve(attr, names)] = dict(values[ref])
        for pair in add_part.split(","):
            pair = pair.strip()
            if not pair:
                continue
            attr, ref = pair.split()
            attr = self._resolve(attr, names)
            v = values[ref]
            cur = item.get(attr)
            if cur is None:
                item[attr] = dict(v)
            elif "N" in cur:
                item[attr] = {"N": str(float(cur["N"]) + float(v["N"]))}
            elif "SS" in cur:
                item[attr] = {"SS": sorted(set(cur["SS"]) | set(v["SS"]))}
            else:
                raise AssertionError(f"ADD on non-additive attr {attr}")

    # -- API surface used by agg_ddb -------------------------------------
    def update_item(self, TableName, Key, UpdateExpression,
                    ExpressionAttributeNames=None,
                    ExpressionAttributeValues=None, **kw):
        self.calls.append(("update_item", TableName, Key))
        if "update_item" in self.fail_on:
            raise RuntimeError("injected update failure")
        pk, sk = Key["pk"]["S"], Key["sk"]["S"]
        item = self.items.setdefault((pk, sk), dict(Key))
        self._apply(item, UpdateExpression, ExpressionAttributeNames,
                    ExpressionAttributeValues)
        return {}

    def put_item(self, TableName, Item, **kw):
        self.calls.append(("put_item", TableName, Item))
        if "put_item" in self.fail_on:
            raise RuntimeError("injected put failure")
        self.items[(Item["pk"]["S"], Item["sk"]["S"])] = dict(Item)
        return {}

    def scan(self, TableName, **kw):
        self.calls.append(("scan", TableName, kw.get("ExclusiveStartKey")))
        if "scan" in self.fail_on:
            raise RuntimeError("injected scan failure")
        return {"Items": [dict(v) for v in self.items.values()]}

    def delete_item(self, TableName, Key, **kw):
        self.items.pop((Key["pk"]["S"], Key["sk"]["S"]), None)
        return {}


def _trip(store, cells, dose=10.0, mode="car", token="hash1",
          ts=None, km=2.0, switched=False):
    store.record_trip(
        cells,
        {"mode": mode, "distance_km": km, "dose_ug": dose,
         "co2_kg_mid": 1.0, "pm25_g_mid": 0.5, "switched": switched},
        token, ts=ts)


@pytest.fixture
def fake():
    return FakeDDB()


@pytest.fixture
def ddb(fake):
    return agg_ddb.DDBTripAggregates(client=fake, table_name="test-agg")


# ------------------------------------------------------------------ shape

def test_item_layout_matches_doc05(fake, ddb):
    ts = 1759600000.0
    _trip(ddb, ["cellA"], mode="metro", ts=ts)
    keys = set(fake.items)
    day = time.strftime("%Y-%m-%d", time.gmtime(ts))
    assert (f"day#{day}", "sum") in keys
    assert (f"day#{day}", "mode#metro") in keys
    assert ("cell#cellA", "cell") in keys
    item = fake.items[(f"day#{day}", "mode#metro")]
    for attr in ("trips", "km", "dose_ug", "co2_kg_mid", "pm25_g_mid",
                 "switched"):
        assert attr in item
    # doc 05: TTL only on corridor cells
    assert "ttl" not in item
    cell = fake.items[("cell#cellA", "cell")]
    assert abs(float(cell["ttl"]["N"]) - (ts + 30 * 86400)) < 2


def test_parity_with_memory_store(fake, ddb):
    mem = memstore.TripAggregates()
    ts = time.time()
    for tok, mode, dose in (("a", "car", 10.0), ("b", "car", 20.0),
                            ("c", "metro", 5.0)):
        for s in (ddb, mem):
            _trip(s, ["c1", "c2"], dose=dose, mode=mode, token=tok, ts=ts)
    dc, mc = ddb.city_aggregates(), mem.city_aggregates()
    assert dc["days"] == mc["days"]
    assert dc["cells_tracked"] == mc["cells_tracked"]
    assert dc["corridors_publishable"] == mc["corridors_publishable"]
    assert ddb.corridors(now=ts) == mem.corridors(now=ts)


# ----------------------------------------------------------------- k >= 3

def test_corridors_k_threshold(ddb):
    now = time.time()
    _trip(ddb, ["cellA"], token="h1", ts=now)
    _trip(ddb, ["cellA"], token="h2", ts=now)
    assert ddb.corridors(now=now) == []
    _trip(ddb, ["cellA"], dose=40.0, token="h3", ts=now)
    cor = ddb.corridors(now=now)
    assert len(cor) == 1
    assert cor[0]["cell"] == "cellA"
    assert cor[0]["trips"] == 3
    assert cor[0]["devices"] == 3
    assert cor[0]["avg_dose_ug"] == round((10 + 10 + 40) / 3, 1)


def test_corridors_72h_window(ddb):
    old = time.time() - 73 * 3600
    for i in range(3):
        _trip(ddb, ["cellA"], token=f"h{i}", ts=old)
    assert ddb.corridors(now=time.time()) == []


def test_no_raw_tokens_at_rest(fake, ddb):
    # what reaches record_trip is already a truncated sha (v2/trip.py);
    # assert that's the only thing in the table and only counts leave it
    _trip(ddb, ["cellA"], token="deadbeefcafe1234", ts=time.time())
    cell = fake.items[("cell#cellA", "cell")]
    assert cell["tokens"] == {"SS": ["deadbeefcafe1234"]}
    snap = ddb.snapshot_cells()
    assert snap == {"cellA": {"count": 1, "dose_sum": 10.0, "devices": 1}}


def test_cell_deduped_per_trip(fake, ddb):
    _trip(ddb, ["cellA", "cellA", "cellA"], token="h1", ts=time.time())
    assert fake.items[("cell#cellA", "cell")]["count"] == {"N": "1"}


def test_modes_and_switched(fake, ddb):
    ts = time.time()
    _trip(ddb, ["c1"], mode="car", switched=True, ts=ts)
    _trip(ddb, ["c1"], mode="car", ts=ts)
    _trip(ddb, ["c1"], mode="walk", ts=ts)
    day = time.strftime("%Y-%m-%d", time.gmtime(ts))
    agg = ddb.city_aggregates()["days"][day]
    assert agg["trips"] == 3
    assert agg["switched"] == 1
    assert agg["modes"] == {"car": 2, "walk": 1}
    assert float(fake.items[(f"day#{day}", "mode#car")]["trips"]["N"]) == 2


def test_co2_split_accumulates(fake, ddb):
    ts = time.time()
    day = time.strftime("%Y-%m-%d", time.gmtime(ts))
    ddb.record_trip(
        ["c1"],
        {"mode": "car", "distance_km": 9.0, "dose_ug": 5.0,
         "co2_kg_mid": 1.9, "co2_moving_g": 1724.0,
         "co2_idle_g": 140.2, "co2_cold_g": 69.7},
        "hash1", ts=ts)
    # a trip with no split (old build / metro / walk) — totals yes, split no
    _trip(ddb, ["c1"], token="hash2", ts=ts)
    agg = ddb.city_aggregates()["days"][day]
    assert agg["co2_split_trips"] == 1
    assert agg["co2_moving_g"] == 1724.0
    assert agg["co2_idle_g"] == 140.2
    assert agg["co2_cold_g"] == 69.7
    assert agg["trips"] == 2


def test_reset(ddb, fake):
    _trip(ddb, ["cellA"], ts=time.time())
    ddb.reset()
    assert fake.items == {}
    assert ddb.city_aggregates()["days"] == {}


# ----------------------------------------------------------------- factory

def test_fallback_when_no_boto3(monkeypatch):
    monkeypatch.setattr(agg_ddb, "_aws_ready", lambda: (None, "no boto3"))
    s = agg_ddb.get_trip_store()
    assert isinstance(s, memstore.TripAggregates)


def test_fallback_when_no_credentials(monkeypatch):
    monkeypatch.setattr(agg_ddb, "_aws_ready",
                        lambda: (None, "no credentials"))
    s = agg_ddb.get_trip_store()
    assert isinstance(s, memstore.TripAggregates)


def test_ddb_selected_when_aws_ready(monkeypatch, fake):
    class FakeB3:
        def client(self, service, **kw):
            assert service == "dynamodb"
            return fake
    monkeypatch.setattr(agg_ddb, "_aws_ready", lambda: (FakeB3(), "ok"))
    s = agg_ddb.get_trip_store()
    assert isinstance(s, agg_ddb.DDBTripAggregates)
    assert s._client is fake


def test_table_name_env_and_default(fake, monkeypatch):
    monkeypatch.delenv("ALIVE_DDB_TABLE", raising=False)
    assert agg_ddb.DDBTripAggregates(client=fake).table_name \
        == "alive108-agg"
    monkeypatch.setenv("ALIVE_DDB_TABLE", "custom-tbl")
    assert agg_ddb.DDBTripAggregates(client=fake).table_name == "custom-tbl"
    # explicit arg beats env
    assert agg_ddb.DDBTripAggregates(
        client=fake, table_name="x").table_name == "x"


# --------------------------------------------------------------- degrade

def test_reads_degrade_never_crash():
    s = agg_ddb.DDBTripAggregates(client=FakeDDB(fail_on={"scan"}))
    assert s.corridors() == []
    assert "injected scan failure" in s.last_error
    agg = s.city_aggregates()
    assert agg["days"] == {} and agg["cells_tracked"] == 0
    assert s.snapshot_cells() == {}


def test_write_error_surfaces():
    s = agg_ddb.DDBTripAggregates(client=FakeDDB(fail_on={"update_item"}))
    with pytest.raises(RuntimeError):
        _trip(s, ["cellA"], ts=time.time())
    assert "injected update failure" in s.last_error
