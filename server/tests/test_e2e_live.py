"""LIVE end-to-end freshness proof — real app, real network, real upstreams.

Boots the actual FastAPI app as a uvicorn subprocess on a test port with
ALIVE_INGEST_IN_APP=1 (the in-app 15-min ingest thread, main.py
`_start_ingest_loop`), then walks the surface the way a client does:

  /health        — field_age_s must drop under 900 s once the ingest
                   thread's first build lands (and only that can lower
                   it: /health never triggers a request-driven refresh,
                   so a fresh field here IS the ingest loop working)
  /aqi           — real interpolated pm25 plus the live pollutant keys
                   (co / so2 / o3) that only exist on the live-serving
                   path — the snapshot carries pm25 only
  /v2/plan       — POSTed OD pair returns real routes (OSRM) AND the
                   field status block (serving / age_s / stale)
  /v2/strip      — re-samples a stored route_id every ~250 m: real pm25
  /v2/city/moves — aggregate-only mobility view: k>=3 rows or the honest
                   insufficient_data flag — never fabricated counts

Skip-by-default: every upstream hit is REAL (Open-Meteo, NASA FIRMS,
OSRM demo) so this only runs when LIVE=1 is in the environment. CI runs
`pytest tests -q` without it and gets a clean skip.

Run it:
    cd server && LIVE=1 ./.venv/bin/python -m pytest tests/test_e2e_live.py -q
    # or standalone (no pytest needed):
    cd server && LIVE=1 ./.venv/bin/python tests/test_e2e_live.py

Nothing is mocked; the only injections are the uvicorn port, the rate
limiter (off, so the walk can't throttle itself), and
ALIVE_INGEST_IN_APP=1 — the exact env a single-box deployment runs.
"""
import json
import os
import socket
import subprocess
import sys
import tempfile
import time

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_SERVER = os.path.dirname(_HERE)

LIVE = os.environ.get("LIVE") == "1"

pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(not LIVE,
                       reason="live e2e hits real upstreams — set LIVE=1"),
]

# A real OD pair inside the NCR bbox: Connaught Place -> Karol Bagh.
FROM = {"lat": 28.6315, "lon": 77.2167}
TO = {"lat": 28.6519, "lon": 77.1907}
AQI_POINT = {"lat": 28.6139, "lon": 77.2090}   # Delhi centre

# Wall-clock budgets. The first ingest build pulls four multi-MB FIRMS
# CSVs plus two Open-Meteo calls before it can write a snapshot, so the
# freshness wait is generous; request timeouts cover the same upstreams.
BOOT_TIMEOUT_S = 90.0
FRESH_TIMEOUT_S = 540.0
POLL_S = 5.0
REQ_TIMEOUT_S = 240.0

OBSERVED: dict = {}   # filled during the run; printed by the teardown


def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


class LiveServer:
    """The real app as a uvicorn subprocess — same boot path as prod."""

    def __init__(self):
        self.port = _free_port()
        self.base = f"http://127.0.0.1:{self.port}"
        self.proc = None
        self._logf = None

    def start(self) -> None:
        env = dict(os.environ)
        # Explicit, not inherited: tests/conftest.py sets
        # ALIVE_INGEST_IN_APP=0 in the pytest env — the child env must
        # override it or the thread under test never starts.
        env["ALIVE_INGEST_IN_APP"] = "1"
        env["ALIVE_RATE_LIMIT"] = "0"     # the walk must not 429 itself
        env.pop("AIRFIELD_NO_SNAPSHOT", None)  # we WANT the snapshot path
        self._logf = tempfile.NamedTemporaryFile(
            mode="w+b", prefix="alive-e2e-uvicorn-", suffix=".log",
            delete=False)
        self.proc = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "main:app",
             "--host", "127.0.0.1", "--port", str(self.port),
             "--log-level", "info"],
            cwd=_SERVER, env=env,
            stdout=self._logf, stderr=subprocess.STDOUT)

    def log_text(self) -> str:
        try:
            self._logf.flush()
            with open(self._logf.name, "rb") as f:
                return f.read().decode("utf-8", "replace")[-4000:]
        except Exception:
            return "<log unavailable>"

    def stop(self) -> None:
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=15)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait(timeout=10)
        if self._logf:
            self._logf.close()


_CURRENT_SRV: "LiveServer | None" = None


@pytest.fixture(scope="module")
def server():
    import httpx
    global _CURRENT_SRV
    srv = _CURRENT_SRV = LiveServer()
    srv.start()
    try:
        client = httpx.Client(base_url=srv.base,
                              timeout=REQ_TIMEOUT_S,
                              headers={"User-Agent": "alive108-e2e-live/0.1"})
        deadline = time.time() + BOOT_TIMEOUT_S
        while time.time() < deadline:
            if srv.proc.poll() is not None:
                raise RuntimeError(
                    f"uvicorn exited rc={srv.proc.returncode}\n"
                    + srv.log_text())
            try:
                r = client.get("/health", timeout=10.0)
                if r.status_code == 200:
                    break
            except httpx.HTTPError:
                pass
            time.sleep(1.0)
        else:
            raise RuntimeError(
                "server did not answer /health in "
                f"{BOOT_TIMEOUT_S}s\n" + srv.log_text())
        OBSERVED["boot"] = {"base": srv.base, "port": srv.port}
        yield client
    finally:
        srv.stop()
        _CURRENT_SRV = None
        if OBSERVED:
            print("\n=== LIVE OBSERVED ===")
            print(json.dumps(OBSERVED, indent=1, default=str))


def _wait_fresh(client, srv=None) -> dict:
    """Poll /health until the ingest thread's first build lands.

    /health only READS FIELD.status() — nothing here triggers a live
    refresh — so field_age_s can only fall under 900 s because the
    in-app ingest loop wrote a fresh snapshot and FIELD.load_snapshot()
    picked it up. That is the freshness proof itself.
    """
    deadline = time.time() + FRESH_TIMEOUT_S
    last = None
    while time.time() < deadline:
        r = client.get("/health")
        assert r.status_code == 200
        body = r.json()
        last = body
        age = body.get("field_age_s")
        if age is not None and age < 900:
            return body
        time.sleep(POLL_S)
    tail = (srv or _CURRENT_SRV).log_text() \
        if (srv or _CURRENT_SRV) is not None else ""
    raise AssertionError(
        f"field never got fresh within {FRESH_TIMEOUT_S}s "
        f"(last /health: {json.dumps(last, default=str)[:800]})\n"
        f"<uvicorn log tail>\n{tail}")


def test_health_reports_fresh_field_after_ingest(server):
    r = server.get("/health")
    assert r.status_code == 200
    first = r.json()
    OBSERVED["health_at_boot"] = {
        "field_age_s": first.get("field_age_s"),
        "build_sha": first.get("build_sha"),
        "sources": first.get("sources"),
    }
    body = _wait_fresh(server)
    OBSERVED["health_after_ingest"] = {
        "field_age_s": body.get("field_age_s"),
        "sources": body.get("sources"),
        "ts": body.get("ts"),
    }
    assert body["ok"] is True
    assert body.get("build_sha")
    age = body["field_age_s"]
    assert age is not None and age < 900, (
        f"field_age_s={age} — ingest thread did not refresh the field")


def test_aqi_returns_real_pollutants(server):
    r = server.get("/aqi", params=AQI_POINT)
    assert r.status_code == 200
    body = r.json()
    assert body.get("pm25") is not None, f"/aqi gave no pm25: {body}"
    pm25 = float(body["pm25"])
    assert 0.0 < pm25 < 1500.0, f"pm25={pm25} out of plausible range"
    # the widened pollutant coverage (commit 'realtime field'): these
    # keys must exist AND carry real values on the live-serving path —
    # /aqi triggers FIELD.refresh itself, so serving='live' here is
    # expected unless a fresher snapshot is mid-load.
    for key in ("co", "so2", "o3"):
        assert key in body, f"/aqi payload missing '{key}'"
        assert body[key] is not None, (
            f"{key}=None — live field refresh did not land "
            f"(serving={body.get('field', {}).get('serving')})")
        assert float(body[key]) >= 0.0
    for key in ("pm10", "no2", "us_aqi", "conditions", "wind", "fire",
                "field", "smoke_modifier", "grap"):
        assert key in body, f"/aqi payload missing '{key}'"
    f = body["field"]
    assert f.get("serving") in ("live", "snapshot")
    assert f.get("age_s") is not None
    assert "stale" in f
    OBSERVED["aqi"] = {k: body.get(k) for k in
                       ("pm25", "pm25_ambient", "pm10", "no2", "o3",
                        "co", "so2", "nh3", "us_aqi", "smoke_modifier",
                        "nearest_sample_km")}
    OBSERVED["aqi"]["wind"] = body.get("wind")
    OBSERVED["aqi"]["field"] = {k: f.get(k) for k in
                                ("serving", "age_s", "stale", "source",
                                 "samples", "station_readings",
                                 "kriging")}
    OBSERVED["aqi"]["fire"] = body.get("fire")


def test_plan_returns_routes_and_field_status(server):
    body_in = {"from": FROM, "to": TO, "vehicle": "auto"}
    body = None
    for _ in range(3):                      # public OSRM demo can flake
        r = server.post("/v2/plan", json=body_in)
        assert r.status_code == 200
        body = r.json()
        if body.get("options"):
            break
        time.sleep(2.0)
    assert body is not None
    opts = body.get("options") or []
    assert opts, f"/v2/plan returned no routes: {body.get('error')}"
    for o in opts:
        assert (o.get("geometry") or {}).get("type") == "LineString"
        assert o.get("route_id")
        assert o.get("eta_s") and o["eta_s"] > 0
        assert "dose" in o and "emissions" in o
    f = body.get("field") or {}
    assert "serving" in f and "age_s" in f and "stale" in f, (
        f"/v2/plan field status incomplete: {sorted(f)}")
    OBSERVED["plan"] = {
        "n_options": len(opts),
        "modes": [o.get("mode") for o in opts],
        "eta_models": sorted({o.get("eta_model") for o in opts}),
        "recommended": [o["mode"] for o in opts if o.get("recommended")],
        "field": {k: f.get(k) for k in ("serving", "age_s", "stale")},
        "took_ms": body.get("took_ms"),
        "route_id": opts[0]["route_id"],
    }


def test_strip_returns_real_samples(server):
    # strip needs a live route_id — mint one through the real /v2/plan.
    r = server.post("/v2/plan", json={"from": FROM, "to": TO,
                                      "vehicle": "car"})
    assert r.status_code == 200
    opts = r.json().get("options") or []
    assert opts, "no routes to sample — /v2/plan gave empty options"
    route_id = opts[0]["route_id"]

    r = server.get("/v2/strip", params={"route_id": route_id})
    assert r.status_code == 200
    body = r.json()
    samples = body.get("samples") or []
    assert samples, "strip returned no samples for a live route_id"
    measured = [s for s in samples if s.get("pm25") is not None]
    assert measured, "strip sampled points but got no pm25 values"
    for s in samples:
        assert s.get("lat") is not None and s.get("lon") is not None
        assert s.get("dist_m") is not None
        if s.get("pm25") is not None:
            assert 0.0 <= float(s["pm25"]) < 1500.0
    assert body.get("emissions_curve")
    f = body.get("field") or {}
    assert "serving" in f and "age_s" in f
    OBSERVED["strip"] = {
        "route_id": route_id,
        "n_samples": len(samples),
        "n_with_pm25": len(measured),
        "pm25_min": min(s["pm25"] for s in measured),
        "pm25_max": max(s["pm25"] for s in measured),
        "step_m": body.get("step_m"),
        "field_serving": f.get("serving"),
    }


def test_city_moves_is_k3_or_honest_empty(server):
    r = server.get("/v2/city/moves")
    assert r.status_code == 200
    body = r.json()
    assert body.get("min_k") == 3
    assert body.get("n_trips") is not None
    assert (body.get("window") or {}).get("days") == 7
    if body.get("insufficient_data"):
        # the honest empty: no fabricated distributions
        assert body.get("n_trips", 99) < 3
        assert not body.get("mode_share") or all(
            row.get("trips", 0) >= 3 for row in body["mode_share"])
        assert (body.get("corridors") or {}).get("active", 1) == 0
    else:
        # real aggregates: every emitted row cleared k>=3
        for row in body.get("mode_share") or []:
            assert row["trips"] >= 3, f"sub-k mode row leaked: {row}"
        corr = body.get("corridors") or {}
        assert corr.get("window_h") == 72
    OBSERVED["city_moves"] = {
        "n_trips": body.get("n_trips"),
        "n_days": body.get("n_days"),
        "insufficient_data": body.get("insufficient_data"),
        "mode_share": body.get("mode_share"),
        "corridors": body.get("corridors"),
        "min_k": body.get("min_k"),
    }


# --- standalone runner ---------------------------------------------------------
def _run_standalone() -> int:
    """python tests/test_e2e_live.py — same checks without pytest."""
    import httpx

    srv = LiveServer()
    srv.start()
    client = httpx.Client(base_url=srv.base, timeout=REQ_TIMEOUT_S)
    try:
        deadline = time.time() + BOOT_TIMEOUT_S
        while time.time() < deadline:
            try:
                if client.get("/health", timeout=10.0).status_code == 200:
                    break
            except httpx.HTTPError:
                pass
            time.sleep(1.0)
        else:
            print("server never came up\n" + srv.log_text())
            return 2
        checks = [
            ("health freshness", lambda: _check_health(client, srv)),
            ("aqi pollutants", lambda: _check_aqi(client)),
            ("plan routes", lambda: _check_plan(client)),
            ("strip samples", lambda: _check_strip(client)),
            ("city moves k>=3", lambda: _check_moves(client)),
        ]
        rc = 0
        for name, fn in checks:
            try:
                fn()
                print(f"  PASS {name}")
            except AssertionError as e:
                rc = 1
                print(f"  FAIL {name}: {e}")
        print(json.dumps(OBSERVED, indent=1, default=str))
        return rc
    finally:
        srv.stop()


def _check_health(c, srv=None):
    first = c.get("/health").json()
    OBSERVED["health_at_boot"] = {"field_age_s": first.get("field_age_s")}
    body = _wait_fresh(c, srv)
    OBSERVED["health_after_ingest"] = {
        "field_age_s": body.get("field_age_s"),
        "sources": body.get("sources")}
    assert body["field_age_s"] < 900


def _check_aqi(c):
    body = c.get("/aqi", params=AQI_POINT).json()
    assert body.get("pm25") is not None
    for k in ("co", "so2", "o3"):
        assert body.get(k) is not None, f"{k} missing"
    OBSERVED["aqi"] = {k: body.get(k) for k in
                       ("pm25", "pm10", "no2", "o3", "co", "so2")}


def _check_plan(c):
    body = c.post("/v2/plan",
                  json={"from": FROM, "to": TO, "vehicle": "auto"}).json()
    opts = body.get("options") or []
    assert opts, "no options"
    f = body.get("field") or {}
    assert {"serving", "age_s", "stale"} <= set(f)
    OBSERVED["plan"] = {"n_options": len(opts),
                        "route_id": opts[0]["route_id"]}


def _check_strip(c):
    body = c.post("/v2/plan",
                  json={"from": FROM, "to": TO, "vehicle": "car"}).json()
    rid = (body.get("options") or [{}])[0].get("route_id")
    assert rid, "no route_id"
    s = c.get("/v2/strip", params={"route_id": rid}).json()
    samples = s.get("samples") or []
    assert samples and any(x.get("pm25") is not None for x in samples)
    OBSERVED["strip"] = {"n_samples": len(samples)}


def _check_moves(c):
    body = c.get("/v2/city/moves").json()
    assert body.get("min_k") == 3
    if body.get("insufficient_data"):
        assert body.get("n_trips", 9) < 3
    else:
        assert all(r["trips"] >= 3 for r in body.get("mode_share") or [])
    OBSERVED["city_moves"] = {"n_trips": body.get("n_trips"),
                              "insufficient_data": body.get(
                                  "insufficient_data")}


if __name__ == "__main__":
    if not LIVE:
        print("LIVE=1 not set — live e2e hits real upstreams; refusing.")
        sys.exit(0)
    sys.exit(_run_standalone())
