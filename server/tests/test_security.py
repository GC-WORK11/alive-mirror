"""Tests for server/middleware.py — rate limiting, body cap, security
headers, and the input sanitation helpers.

Uses a minimal FastAPI app (not main.py) so the suite stays hermetic:
the middlewares are pure ASGI and behave identically wherever mounted.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI  # noqa: E402
from fastapi.responses import HTMLResponse  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

import middleware  # noqa: E402


def make_app(**kwargs) -> TestClient:
    """A tiny app with the real stack mounted via attach() — the same
    call the integrator's two lines make."""
    app = FastAPI()

    @app.get("/ping")
    async def ping():
        return {"ok": True}

    @app.post("/echo")
    async def echo(body: dict):
        return {"got": body}

    @app.get("/page")
    async def page():
        return HTMLResponse("<html><body>city breathes</body></html>")

    @app.get("/health")
    async def health():
        return {"ok": True}

    middleware.attach(app, **kwargs)
    return TestClient(app)


# --- rate limiting -------------------------------------------------------------
def test_429_after_burst_and_retry_after_header():
    c = make_app(rate_per_s=1.0, burst=3.0, path_overrides={})
    codes = [c.get("/ping").status_code for _ in range(6)]
    assert codes[:3] == [200, 200, 200]
    assert 429 in codes[3:]
    r = c.get("/ping")
    assert r.status_code == 429
    assert r.headers["retry-after"]
    assert int(r.headers["retry-after"]) >= 1
    body = r.json()
    assert body["error"] == "rate_limited"
    assert body["retry_after_s"] >= 1


def test_rate_limit_ignores_self_minted_tokens():
    """x-device-token is a client-chosen anonymous id — rotating it must
    NOT mint fresh buckets or the limiter is a header-length away from
    being bypassed. Buckets key on the socket peer only."""
    c = make_app(rate_per_s=0.5, burst=2.0, path_overrides={})
    for i, tok in enumerate(("tok-A", "tok-B", "tok-C")):
        r = c.get("/ping", headers={"x-device-token": tok})
        assert r.status_code == (200 if i < 2 else 429)


def test_xff_spoof_cannot_mint_buckets():
    """The edge is an L4 NLB — it cannot append X-Forwarded-For, so a
    rotating claimed IP is pure spoofing material: buckets must key on
    the socket peer and every hop of the XFF header is ignored."""
    c = make_app(rate_per_s=0.5, burst=2.0, path_overrides={})
    for i, spoof in enumerate(("10.0.0.1", "10.0.0.2", "10.0.0.3")):
        r = c.get("/ping",
                  headers={"x-forwarded-for": f"{spoof}, 203.0.113.7"})
        assert r.status_code == (200 if i < 2 else 429)


def test_xff_trusted_proxy_opt_in(monkeypatch):
    """ALIVE_TRUSTED_PROXIES re-enables XFF when a real L7 front exists —
    honored only when the socket peer is inside the trusted CIDRs, and
    then only its rightmost hop (the one the front appended)."""
    from starlette.datastructures import Headers
    monkeypatch.setenv("ALIVE_TRUSTED_PROXIES", "10.0.0.0/8")
    hdr = [(b"x-forwarded-for", b"1.1.1.1, 2.2.2.2")]
    # socket peer inside the trusted range → rightmost XFF hop wins
    scope = {"headers": hdr, "client": ("10.1.2.3", 5000)}
    assert middleware._client_ip(Headers(scope=scope), scope) == "2.2.2.2"
    # socket peer outside the trusted range → XFF ignored entirely
    scope = {"headers": hdr, "client": ("192.0.2.1", 5000)}
    assert middleware._client_ip(Headers(scope=scope), scope) == \
        "192.0.2.1"
    # malformed trusted-proxy entry → trust widens to nobody
    monkeypatch.setenv("ALIVE_TRUSTED_PROXIES", "not-a-cidr, ")
    scope = {"headers": hdr, "client": ("10.1.2.3", 5000)}
    assert middleware._client_ip(Headers(scope=scope), scope) == \
        "10.1.2.3"


def test_rate_limit_falls_back_to_socket_peer():
    """No XFF header (or no usable hop in it) → the socket peer keys the
    bucket, consistently."""
    c = make_app(rate_per_s=0.5, burst=1.0, path_overrides={})
    assert c.get("/ping").status_code == 200
    assert c.get("/ping").status_code == 429


def test_health_is_exempt_from_rate_limit():
    c = make_app(rate_per_s=0.5, burst=1.0, path_overrides={})
    codes = [c.get("/health").status_code for _ in range(10)]
    assert codes == [200] * 10


def test_path_override_tighter_on_donation_endpoint():
    app = FastAPI()

    @app.post("/v2/trip")
    async def trip(body: dict):
        return {"stored": True}

    @app.get("/ping")
    async def ping():
        return {"ok": True}

    middleware.attach(app, rate_per_s=100.0, burst=100.0,
                      path_overrides={"/v2/trip": (0.5, 2)})
    c = TestClient(app)
    codes = [c.post("/v2/trip", json={"x": 1}).status_code
             for _ in range(4)]
    assert codes[:2] == [200, 200]
    assert 429 in codes[2:]
    assert c.get("/ping").status_code == 200  # global budget untouched


# --- body size cap --------------------------------------------------------------
def test_oversized_body_rejected_413():
    c = make_app(max_body_bytes=1024)
    big = {"data": "x" * 5000}
    r = c.post("/echo", json=big)
    assert r.status_code == 413
    assert r.json()["error"] == "payload_too_large"
    assert r.json()["max_bytes"] == 1024


def test_body_just_under_cap_passes_intact():
    c = make_app(max_body_bytes=4096)
    payload = {"data": "y" * 2000}
    r = c.post("/echo", json=payload)
    assert r.status_code == 200
    assert r.json()["got"] == payload


# --- security headers ------------------------------------------------------------
EXPECTED_HEADERS = {
    "x-content-type-options": "nosniff",
    "x-frame-options": "DENY",
    "referrer-policy": "no-referrer",
}


def test_security_headers_on_json_and_html():
    c = make_app(rate_per_s=100, burst=100, path_overrides={})
    for path in ("/ping", "/page"):
        r = c.get(path)
        assert r.status_code == 200
        for k, v in EXPECTED_HEADERS.items():
            assert r.headers.get(k) == v, f"{path}: missing {k}"
    # no HSTS on plain-http requests
    assert "strict-transport-security" not in c.get("/ping").headers


def test_security_headers_also_on_429():
    c = make_app(rate_per_s=0.5, burst=1.0, path_overrides={})
    c.get("/ping")
    r = c.get("/ping")
    assert r.status_code == 429
    for k, v in EXPECTED_HEADERS.items():
        assert r.headers.get(k) == v


# --- normal traffic unaffected -----------------------------------------------------
def test_normal_requests_unaffected():
    c = make_app()
    r = c.get("/ping")
    assert r.status_code == 200 and r.json() == {"ok": True}
    r = c.post("/echo", json={"trajectory": [[77.2, 28.6]]})
    assert r.status_code == 200
    assert r.json()["got"]["trajectory"] == [[77.2, 28.6]]
    r = c.get("/page")
    assert r.status_code == 200
    assert "city breathes" in r.text


# --- sanitation helpers ------------------------------------------------------------
def test_bounded_lat_lon():
    assert middleware.bounded_lat("28.6") == 28.6
    assert middleware.bounded_lon(77.2) == 77.2
    for bad in (91, -91, "nan", float("inf"), "abc", None):
        with pytest.raises(ValueError):
            middleware.bounded_lat(bad)
    for bad in (181, -181, float("nan")):
        with pytest.raises(ValueError):
            middleware.bounded_lon(bad)


def test_bounded_str_caps_and_strips():
    assert middleware.bounded_str("connaught\x00\x01 place") == \
        "connaught place"
    assert len(middleware.bounded_str("q" * 500, max_len=200)) == 200
    with pytest.raises(ValueError):
        middleware.bounded_str("   ")
    assert middleware.bounded_str("   ", allow_empty=True) == ""
    with pytest.raises(ValueError):
        middleware.bounded_str({"not": "a string"})


def test_parse_point_shapes_and_bounds():
    assert middleware.parse_point({"lat": 28.6, "lon": 77.2}) == \
        (28.6, 77.2)
    assert middleware.parse_point([77.2, 28.6]) == (28.6, 77.2)
    with pytest.raises(ValueError):
        middleware.parse_point({"lat": 99, "lon": 0})
    with pytest.raises(ValueError):
        middleware.parse_point("delhi")
