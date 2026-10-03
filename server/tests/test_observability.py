"""Tests for observability.py — request-id propagation, Prometheus
/metrics output, privacy guardrails (no tokens/coords in logs), and the
{"error": ..., "detail": ...} envelope.

Run from server/:
    uv run --with 'pytest,h3,boto3,httpx' pytest tests/test_observability.py -v
"""
import json
import logging
import os
import re
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI, Request  # noqa: E402
from fastapi.responses import JSONResponse  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

import observability  # noqa: E402


class _Capture(logging.Handler):
    """In-memory log handler — every emitted line lands in .lines."""
    def __init__(self):
        super().__init__()
        self.lines = []

    def emit(self, record):
        self.lines.append(record.getMessage())


@pytest.fixture()
def rig():
    """Fresh app wired like the integrator note: logging middleware +
    the real /metrics router, writing to a cleared global REGISTRY."""
    observability.REGISTRY.clear()

    logger = logging.getLogger("alive.request.test")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    for h in list(logger.handlers):
        logger.removeHandler(h)
    cap = _Capture()
    logger.addHandler(cap)

    app = FastAPI()

    @app.get("/v2/search")
    async def search(lat: float = 0.0, lon: float = 0.0, q: str = ""):
        return {"results": []}

    @app.post("/v2/trip")
    async def trip(payload: dict):
        return {"stored": True}

    @app.get("/v2/plan")
    async def plan():
        return {"options": []}

    @app.get("/v2/place/{pid}")
    async def place(pid: str):
        return {"pid": pid}

    @app.get("/tiered")
    async def tiered():
        return JSONResponse(
            {"ok": True},
            headers={"Server-Timing": "t1;dur=12.345, t2;dur=48"})

    @app.get("/tiered-state")
    async def tiered_state(request: Request):
        request.state.tier_timings = {"t1": 7.5, "bad key!": 1,
                                      "t2": "not-a-number"}
        return {"ok": True}

    @app.get("/gone")
    async def gone():
        return JSONResponse({"error": "nope"}, status_code=410)

    app.add_middleware(observability.RequestLoggingMiddleware,
                       logger=logger)
    app.include_router(observability.router)

    return TestClient(app), cap, observability.REGISTRY


def _records(cap):
    return [json.loads(line) for line in cap.lines]


# --- request id -------------------------------------------------------------

def test_request_id_propagates_to_response_and_log(rig):
    client, cap, _reg = rig
    r = client.get("/v2/search", headers={"X-Request-ID": "req-fixed-1"})
    assert r.status_code == 200
    assert r.headers["x-request-id"] == "req-fixed-1"
    recs = _records(cap)
    assert recs and recs[-1]["request_id"] == "req-fixed-1"


def test_request_id_generated_when_absent_or_unsafe(rig):
    client, _cap, _reg = rig
    rid = client.get("/v2/search").headers["x-request-id"]
    assert re.fullmatch(r"[0-9a-f]{32}", rid)
    # hostile/oversized ids are replaced, never echoed or logged
    r = client.get("/v2/search",
                   headers={"X-Request-ID": '../../etc "passwd"'})
    assert re.fullmatch(r"[0-9a-f]{32}", r.headers["x-request-id"])


# --- metrics ----------------------------------------------------------------

def test_metrics_text_parses_and_increments_on_traffic(rig):
    client, _cap, reg = rig
    client.get("/v2/search")
    client.get("/v2/search", params={"q": "x"})
    client.get("/v2/plan")
    client.get("/gone")

    r = client.get("/metrics")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/plain")
    assert "# HELP" in r.text and "# TYPE" in r.text

    series = observability.parse_prometheus(r.text)
    k = 'alive_http_requests_total{method="GET",route="/v2/search",status="200"}'
    assert series[k] == 2
    assert series['alive_http_errors_total{class="4xx",route="/gone"}'] == 1
    assert series['alive_request_duration_ms_count{route="/v2/search"}'] == 2
    # route-plan duration histogram fed by the middleware
    assert series['alive_route_plan_duration_ms_count{route="/v2/plan"}'] == 1
    # in-flight gauge counts the /metrics scrape itself while rendering…
    assert series['alive_requests_in_flight'] == 1
    # …and settles back to zero once traffic has drained
    assert reg.gauge_value("alive_requests_in_flight") == 0
    # registry agrees with the rendered text
    assert reg.counter_value("alive_http_requests_total",
                             {"method": "GET", "route": "/v2/search",
                              "status": "200"}) == 2


def test_route_template_labels_not_raw_paths(rig):
    client, cap, _reg = rig
    client.get("/v2/place/amz:X1")
    series = observability.parse_prometheus(
        observability.REGISTRY.render())
    labelled = [k for k in series if "/v2/place" in k]
    assert labelled and all("{pid}" in k or "_count" in k or "_sum" in k
                            or "_bucket" in k or "_total" in k
                            for k in labelled)
    assert not any("amz:X1" in k for k in series)
    rec = _records(cap)[-1]
    assert rec["route"] == "/v2/place/{pid}"
    assert rec["path"] == "/v2/place/amz:X1"


def test_unmatched_paths_collapse_to_one_label(rig):
    client, _cap, _reg = rig
    client.get("/nope/28.6315,77.2167")
    client.get("/different/junk")
    series = observability.parse_prometheus(
        observability.REGISTRY.render())
    unmatched = [k for k in series if 'route="unmatched"' in k]
    assert unmatched and not any("nope" in k or "junk" in k
                                 for k in series)


# --- privacy guardrails -------------------------------------------------------

def test_no_tokens_or_coords_in_emitted_logs(rig):
    client, cap, _reg = rig
    client.post(
        "/v2/trip",
        json={"device_token": "devtok-9988-secret",
              "trajectory": [[77.20901234, 28.61391234],
                             [77.21000000, 28.61400000]]},
        headers={"Authorization": "Bearer supersecret-token-abc123",
                 "X-Device-Token": "devtok-9988-secret"})
    client.get("/v2/search", params={"lat": 28.6315, "lon": 77.2167,
                                     "q": "connaught"})

    blob = "\n".join(cap.lines)
    assert blob, "expected request log lines"
    # NB: don't assert on bare short numbers — epoch `ts` could contain
    # them by chance; the unique secret/coord strings are what matter.
    for bad in ("supersecret", "devtok-9988-secret", "devtok", "Bearer",
                "28.6315", "77.2167", "28.6139", "77.2090",
                "connaught", "trajectory", "device_token"):
        assert bad not in blob, "leaked %r into request log" % bad
    # the query string is never part of the logged path
    assert '"path":"/v2/search"' in blob
    assert '"path":"/v2/trip"' in blob


def test_log_record_fields_are_allowlisted(rig):
    client, cap, _reg = rig
    client.get("/v2/search", params={"lat": 1.23})
    rec = _records(cap)[-1]
    assert set(rec) <= set(observability.LOG_FIELDS)
    assert not (set(rec) & observability.LOG_DENYLIST)


def test_scrub_log_line_redacts_secrets_and_coords():
    line = ('{"lat":28.6315,"device_token":"abc123",'
            '"h":"Bearer xyz789","note":"token=deadbeef42"}')
    out = observability.scrub_log_line(line)
    assert "abc123" not in out and "xyz789" not in out
    assert "deadbeef42" not in out
    assert "28.6315" not in out and "28.63" in out
    assert "REDACTED" in out


# --- tier timings --------------------------------------------------------------

def test_tier_timings_from_server_timing_header(rig):
    client, cap, _reg = rig
    client.get("/tiered")
    rec = _records(cap)[-1]
    assert rec["tier_ms"]["t1"] == pytest.approx(12.345, abs=0.01)
    assert rec["tier_ms"]["t2"] == 48.0


def test_tier_timings_from_request_state_sanitized(rig):
    client, cap, _reg = rig
    client.get("/tiered-state")
    rec = _records(cap)[-1]
    # unsafe key name and non-numeric value are dropped, good ones kept
    assert rec["tier_ms"] == {"t1": 7.5}


# --- error envelope ------------------------------------------------------------

def test_error_envelope_matches_existing_shape():
    body = observability.error_body("unknown_route_id",
                                    "route_ids expire after 1 h")
    assert body == {"error": "unknown_route_id",
                    "detail": "route_ids expire after 1 h"}
    resp = observability.error_response(observability.ERR_NOT_FOUND, 404,
                                        "route_ids expire after 1 h")
    assert resp.status_code == 404
    parsed = json.loads(bytes(resp.body))
    assert parsed["error"] == "not_found" and parsed["detail"]
    # details get the same redaction as log lines — no coords even if a
    # careless caller pastes them in
    leaked = observability.error_body("x", "at 28.6315,77.2167")
    assert "28.6315" not in leaked["detail"]


# --- standalone registry --------------------------------------------------------

def test_registry_histogram_buckets_cumulative():
    reg = observability.MetricsRegistry()
    reg.observe("h_ms", 30.0, labels={"r": "/x"}, buckets=(10, 50, 100))
    reg.observe("h_ms", 5.0, labels={"r": "/x"}, buckets=(10, 50, 100))
    text = reg.render()
    s = observability.parse_prometheus(text)
    assert s['h_ms_bucket{r="/x",le="10"}'] == 1
    assert s['h_ms_bucket{r="/x",le="50"}'] == 2
    assert s['h_ms_bucket{r="/x",le="+Inf"}'] == 2
    assert s['h_ms_count{r="/x"}'] == 2
    assert s['h_ms_sum{r="/x"}'] == 35.0
