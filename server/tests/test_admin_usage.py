"""Tests for the console usage endpoint — the 'usage' tab's rollup.

The endpoint answers "who uses it" inside the privacy spine (doc 07 §3):
aggregate scalars only, honest nulls + basis notes where a store can't
answer, the same _admin_guard as the rest of <mount>/api/*. Covered here: payload
shape on a populated store, the no-identity key scan, the honest-empty
state, degraded-backend honesty (a failing store degrades to null +
note, never a wrong number), the 401/403 gate, and the admin page's
wiring (the section exists and fetches the endpoint through the same
guest short-circuit as the other gated feeds).
"""
import time

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

import admin_agg
from admin_mount import ADMIN_MOUNT as M
from v2.store import LEDGER, TRIPS

app = FastAPI()
app.include_router(admin_agg.usage_router)
client = TestClient(app)

# Same contract as test_admin_agg: no response may carry identity or
# coordinate field names, at any depth.
BANNED_KEYS = {
    "token", "tokens", "token_hash", "device_token",
    "lat", "lon", "latitude", "longitude",
    "coord", "coords", "coordinate", "coordinates",
    "trajectory", "points", "geometry", "route",
    "contributor", "reporter", "identity",
    "user", "users", "uid", "uuid", "device_id", "ip",
}


@pytest.fixture(autouse=True)
def clean_stores():
    TRIPS.reset()
    LEDGER.reset()
    yield
    TRIPS.reset()
    LEDGER.reset()


def _keys(obj):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield str(k)
            yield from _keys(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _keys(v)


def _donate(cells, tokens, summary=None, ts=None):
    summary = summary or {"mode": "metro", "distance_km": 4.0,
                          "dose_ug": 40.0, "switched": False}
    for tok in tokens:
        TRIPS.record_trip(cells, summary, token_hash=tok, ts=ts)
        LEDGER.record(tok, summary, ts=ts)


# --- shape ------------------------------------------------------------------

def test_usage_shape_empty():
    """Fresh stores -> honest empties, no fabricated zeros-as-means."""
    d = client.get(M + "/api/usage").json()
    assert d["k_min"] == 3
    assert d["empty"] is True
    assert d["installs"] is None and d["installs_note"]
    assert d["devices"]["total"] == 0
    t = d["trips"]
    assert t["total"] == 0 and t["today"] is None
    assert t["latest_donation_age_min"] is None
    ds = d["dose"]
    assert ds["mean_ug_per_trip"] is None
    assert ds["median_ug_per_trip"] is None and ds["median_n"] == 0
    assert d["feedback"]["reviews"]["count"] == 0


def test_usage_shape_populated():
    """Real donations -> every block fills from the stores' own rows."""
    _donate(["cX"], ["t1"], {"mode": "metro", "distance_km": 4.0,
                             "dose_ug": 40.0})
    _donate(["cX"], ["t2"], {"mode": "car", "distance_km": 6.0,
                             "dose_ug": 120.0})
    _donate(["cX"], ["t3"], {"mode": "walk", "distance_km": 2.0,
                             "dose_ug": 30.0})
    d = client.get(M + "/api/usage").json()
    assert d["empty"] is False
    dev = d["devices"]
    assert dev["total"] == 3 and dev["seen_24h"] == 3
    t = d["trips"]
    assert t["total"] == 3 and t["km"] == 12.0 and t["dose_ug"] == 190.0
    assert t["today"]["trips"] == 3
    assert t["last_24h"]["devices"] == 3
    assert len(t["per_hour"]) == 24 and sum(t["per_hour"]) == 3
    ds = d["dose"]
    assert ds["mean_ug_per_trip"] == pytest.approx(63.3, abs=0.05)
    assert ds["median_ug_per_trip"] == 40.0 and ds["median_n"] == 3
    assert cor_populated(d)
    assert d["feedback"]["reviews"] is not None


def cor_populated(d):
    return d["corridors"]["tracked"] >= 1 and \
        d["corridors"]["publishable"] >= 1 and d["corridors"]["k_min"] == 3


def test_usage_window_buckets():
    """24h/7d device windows count by each token's newest ledger row."""
    now = time.time()
    _donate(["cX"], ["fresh"], ts=now - 3600)
    _donate(["cX"], ["week"], ts=now - 3 * 86400)
    _donate(["cX"], ["old"], ts=now - 10 * 86400)
    d = client.get(M + "/api/usage").json()
    dev = d["devices"]
    assert dev["total"] == 3
    assert dev["seen_24h"] == 1 and dev["seen_7d"] == 2
    # rolling trip window likewise covers 24h only
    assert d["trips"]["last_24h"]["trips"] == 1


# --- privacy + degradation honesty -------------------------------------------

def test_usage_never_leaks_identity():
    """A populated payload recursively scanned: counts, never people."""
    _donate(["cX"], ["t1", "t2", "t3"])
    d = client.get(M + "/api/usage").json()
    leaked = {k.lower() for k in _keys(d)} & BANNED_KEYS
    assert not leaked, f"usage leaks field(s): {leaked}"
    # nothing dimensional below a city total: no per-device or per-trip
    # rows anywhere in the payload
    assert isinstance(d["devices"], dict)
    assert all(not isinstance(v, list) or k in ("per_hour", "daily")
               for blk in (d["devices"], d["trips"], d["dose"])
               for k, v in blk.items())


def test_usage_degraded_ledger_is_honest():
    """A ledger that can't answer -> nulls + note, never a guess."""
    _donate(["cX"], ["t1", "t2", "t3"])

    class BrokenLedger:
        backend = "broken"

        def device_windows(self, now=None):
            return None

        def dose_values(self, limit=50000):
            return None

        def devices(self):
            return 0

    real = admin_agg.LEDGER
    admin_agg.LEDGER = BrokenLedger()
    try:
        d = client.get(M + "/api/usage").json()
    finally:
        admin_agg.LEDGER = real
    assert d["devices"]["unavailable"] is True
    assert d["devices"]["total"] is None
    assert d["dose"]["median_ug_per_trip"] is None
    # trips block still answers — one failing store must not blank the rest
    assert d["trips"]["total"] == 3


def test_usage_k_guard_is_structural():
    """<k donations still report — usage serves only scalar city totals,
    so there is no sub-k row to suppress (corridor rows elsewhere carry
    the >=3 gate). What must never happen is a scalar turning into a
    person; the payload stays key-clean."""
    _donate(["cX"], ["solo"])
    d = client.get(M + "/api/usage").json()
    assert d["devices"]["total"] == 1          # a count, not a person
    assert d["corridors"]["publishable"] == 0  # k<3 cell suppressed
    assert d["corridors"]["tracked"] == 1
    leaked = {k.lower() for k in _keys(d)} & BANNED_KEYS
    assert not leaked


# --- the operator gate ---------------------------------------------------------

def test_usage_requires_operator_token(monkeypatch):
    """Mounted with the real _admin_guard: 401 without a Bearer, 200
    with it. (Loopback mode — token unset — is covered by main.py's
    own guard tests; here the token path is the contract.)"""
    import main as _m
    monkeypatch.setenv("ALIVE_ADMIN_TOKEN", "test-token-xyz")
    gated_app = FastAPI()
    gated_app.include_router(admin_agg.usage_router,
                             dependencies=[Depends(_m._admin_guard)])
    c = TestClient(gated_app, base_url="http://10.9.8.7")
    assert c.get(M + "/api/usage").status_code == 401
    r = c.get(M + "/api/usage",
              headers={"Authorization": "Bearer test-token-xyz"})
    assert r.status_code == 200
    assert c.get(M + "/api/usage",
                 headers={"Authorization": "Bearer wrong"}).status_code == 401


# --- the tab itself -------------------------------------------------------------

def test_admin_page_renders_usage_section():
    """The served page must carry the section, the fetch, and the guest
    short-circuit — a stale admin.html fails this loudly."""
    import main as _m
    body = TestClient(_m.app).get(M).text
    assert '/api/usage' in body
    assert 'id="usagecards"' in body
    assert 'id="usagefb"' in body
    assert 'isGatedPath' in body
    assert "who's using it" in body
    # guests must never see internals — the locked state is explicit
    assert 'locked — sign in as operator' in body
