"""Transport-layer privacy tests — the audit's URL/log-surface holes.

The device token is the read-key to a person's own trip history. It must
not travel in URL query strings (uvicorn access logs, browser history,
Referer): /v2/ledger accepts X-Device-Token, and /observe — the retired
raw-coords write surface — answers 410 Gone.

Run from server/:
    .venv/bin/python -m pytest tests/test_privacy_transport.py -v
"""
import hashlib
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient  # noqa: E402

from main import app  # noqa: E402
from v2.store import LEDGER  # noqa: E402

c = TestClient(app)

_TOK = "audit-test-device"


@pytest.fixture(autouse=True)
def _clean_ledger():
    if hasattr(LEDGER, "reset"):
        LEDGER.reset()
    yield
    if hasattr(LEDGER, "reset"):
        LEDGER.reset()


def _hash(tok: str) -> str:
    return hashlib.sha256(tok.encode()).hexdigest()[:16]


def _seed():
    LEDGER.record(_hash(_TOK), {"distance_km": 1.2, "dose_ug": 30.0,
                                "mode": "bus"})


# --- retired raw-coords write surface -----------------------------------------
def test_observe_endpoint_gone():
    r = c.post("/observe", json={
        "vehicle": "car", "coords": [[77.21, 28.63], [77.22, 28.64]],
        "duration_s": 600, "dose_ug": 30.0, "contributor": "x"})
    assert r.status_code == 410
    assert "v2/trip" in r.json()["detail"]


# --- device token stays out of URLs -------------------------------------------
def test_ledger_reads_via_header():
    _seed()
    r = c.get("/v2/ledger", headers={"X-Device-Token": _TOK})
    assert r.status_code == 200
    j = r.json()
    assert len(j["trips"]) == 1 and j["totals"]["trips"] == 1


def test_ledger_requires_token():
    r = c.get("/v2/ledger")
    assert r.status_code == 422


def test_ledger_delete_via_header():
    _seed()
    r = c.delete("/v2/ledger", headers={"X-Device-Token": _TOK})
    assert r.status_code == 200 and r.json()["deleted"] == 1
    j = c.get("/v2/ledger", headers={"X-Device-Token": _TOK}).json()
    assert j["trips"] == []


def test_ledger_query_token_still_works_backcompat():
    """Already-shipped clients send ?token= — keep reading it, but new
    clients must use the header (tested above)."""
    _seed()
    r = c.get("/v2/ledger", params={"token": _TOK})
    assert r.status_code == 200 and len(r.json()["trips"]) == 1


def test_ledger_header_wins_over_query():
    _seed()
    r = c.get("/v2/ledger", params={"token": "other-device"},
              headers={"X-Device-Token": _TOK})
    assert len(r.json()["trips"]) == 1
