"""Offline tests for agg_ddb.DDBDeviceLedger — a fake DynamoDB client
stands in for AWS (same pattern as test_agg_ddb: real call semantics,
no boto3, no credentials, no network).

Covers: record -> item layout, trips/totals reads via query, devices()
via the ledger_meta index, TTL attr, empty-token skip, failure
surfacing via last_error, and the store selector's memory fallback.
"""
import os
import sys
import time

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import agg_ddb           # noqa: E402
from v2 import store as memstore  # noqa: E402


class FakeDDB:
    """update_item/put_item/query/scan/delete_item — the calls the
    ledger path actually makes."""

    def __init__(self, fail_on=()):
        self.items = {}
        self.calls = []
        self.fail_on = set(fail_on)

    def put_item(self, TableName, Item, **kw):
        self.calls.append(("put_item", TableName, Item["pk"]["S"]))
        if "put_item" in self.fail_on:
            raise RuntimeError("injected put failure")
        self.items[(Item["pk"]["S"], Item["sk"]["S"])] = dict(Item)
        return {}

    def update_item(self, TableName, Key, UpdateExpression,
                    ExpressionAttributeNames=None,
                    ExpressionAttributeValues=None, **kw):
        self.calls.append(("update_item", TableName, Key["sk"]["S"]))
        if "update_item" in self.fail_on:
            raise RuntimeError("injected update failure")
        pk, sk = Key["pk"]["S"], Key["sk"]["S"]
        item = self.items.setdefault((pk, sk), dict(Key))
        # the ledger's only expression: SET last_ts = :ts ADD trips :one
        vals = ExpressionAttributeValues or {}
        item["last_ts"] = dict(vals[":ts"])
        cur = item.get("trips")
        n = float(vals[":one"]["N"])
        item["trips"] = {"N": str(n + float(cur["N"]))} if cur \
            else dict(vals[":one"])
        return {}

    def query(self, TableName, KeyConditionExpression,
              ExpressionAttributeValues, ScanIndexForward=None,
              Limit=None, ExclusiveStartKey=None, **kw):
        if "query" in self.fail_on:
            raise RuntimeError("injected query failure")
        pk = ExpressionAttributeValues[":pk"]["S"]
        rows = sorted(
            (v for (ipk, _isk), v in self.items.items() if ipk == pk),
            key=lambda it: it["sk"]["S"],
            reverse=not ScanIndexForward)
        return {"Items": rows[:Limit] if Limit else rows}

    def scan(self, TableName, ProjectionExpression=None, **kw):
        self.calls.append(("scan", TableName, kw.get("ExclusiveStartKey")))
        return {"Items": [dict(v) for v in self.items.values()]}

    def delete_item(self, TableName, Key, **kw):
        self.items.pop((Key["pk"]["S"], Key["sk"]["S"]), None)
        return {}


@pytest.fixture
def fake():
    return FakeDDB()


@pytest.fixture
def led(fake):
    return agg_ddb.DDBDeviceLedger(client=fake, table_name="test-agg")


def test_record_lays_out_trip_and_meta_items(fake, led):
    led.record("hashabc", {"mode": "car", "distance_km": 3.4,
                           "dose_ug": 52.1, "switched": False},
               ts=1700000000.0)
    assert ("ledger#hashabc", "trip#1700000000.000") in fake.items
    row = fake.items[("ledger#hashabc", "trip#1700000000.000")]
    assert row["mode"]["S"] == "car"
    assert float(row["dose_ug"]["N"]) == 52.1
    assert row["switched"]["BOOL"] is False
    assert float(row["ttl"]["N"]) > 1700000000.0   # 90 d expiry set
    meta = fake.items[("ledger_meta", "device#hashabc")]
    assert float(meta["trips"]["N"]) == 1


def test_trips_newest_first_and_totals(led):
    for i, dose in enumerate((10.0, 20.0, 30.0)):
        led.record("h1", {"dose_ug": dose, "distance_km": 1.0},
                   ts=1700000000.0 + i)
    rows = led.trips("h1")
    assert [r["dose_ug"] for r in rows] == [30.0, 20.0, 10.0]
    tot = led.totals("h1")
    assert tot["trips"] == 3 and tot["dose_ug"] == 60.0
    assert tot["km"] == 3.0


def test_devices_counts_meta_index(led):
    led.record("a", {"dose_ug": 1.0})
    led.record("a", {"dose_ug": 2.0})
    led.record("b", {"dose_ug": 3.0})
    assert led.devices() == 2


def test_no_coordinates_no_cells_anywhere(led):
    led.record("t1", {"mode": "metro", "dose_ug": 7.0})
    dump = str(list(led._items("t1", 10)))
    assert "lat" not in dump and "cell" not in dump and "trajectory" not in dump


def test_empty_token_is_a_noop(fake, led):
    led.record("", {"dose_ug": 1.0})
    assert not fake.items


def test_write_failure_surfaces_last_error(led):
    led_fail = agg_ddb.DDBDeviceLedger(
        client=FakeDDB(fail_on={"put_item"}), table_name="t")
    with pytest.raises(RuntimeError):
        led_fail.record("x", {"dose_ug": 1.0})
    assert led_fail.last_error


def test_read_failure_is_honest_empty():
    led = agg_ddb.DDBDeviceLedger(
        client=FakeDDB(fail_on={"query"}), table_name="t")
    assert led.trips("x") == []
    assert led.last_error


def test_selector_falls_back_to_memory_without_table(monkeypatch):
    monkeypatch.delenv("AGG_TABLE", raising=False)
    monkeypatch.delenv("ALIVE_DDB_TABLE", raising=False)
    store = memstore._select_ledger()
    assert isinstance(store, memstore.DeviceLedger)
    assert store.backend == "memory"
