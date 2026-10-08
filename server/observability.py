"""Observability for Alive — request logs, in-process metrics, errors.

Three pieces, all dependency-light:

  * ``RequestLoggingMiddleware`` — pure-ASGI structured request logging:
    one JSON line per request with request_id, method, route template,
    path, status, latency_ms and (when surfaced) per-tier timings.
  * ``MetricsRegistry`` / ``REGISTRY`` — counters, gauges and histograms
    rendered as Prometheus text at ``GET /metrics`` (``router`` below).
  * Error taxonomy — ``error_body`` / ``error_response`` produce the
    ``{"error": <code>, "detail": <human>}`` envelope already used by
    server/v2/places.py and server/v2/strip.py.

────────────────────────────────────────────────────────────────────────
INTEGRATOR MOUNT NOTE (server/main.py is owned by another lane):

    import observability
    observability.install(app)            # middleware + GET /metrics

    # — or mount the pieces by hand —
    app.add_middleware(observability.RequestLoggingMiddleware)
    app.include_router(observability.router)

Handlers surface tier timings either via a standard Server-Timing
response header (``t1;dur=12.3, t2;dur=45.6``) or by setting
``request.state.tier_timings = {"t1": 12.3}`` inside the handler.
The caller's request id is honoured via ``X-Request-ID`` (strict charset,
≤64 chars — anything else is replaced with a fresh uuid4); the id is
always echoed back on the ``x-request-id`` response header.
────────────────────────────────────────────────────────────────────────

PRIVACY — enforced by construction, not by convention:

  1. The request body is never read (``receive`` is passed through
     untouched) and the query string is never logged — so bodies,
     device tokens and lat/lon query params cannot reach a log line.
  2. Request headers are never read except ``x-request-id``, which is
     validated against ``^[A-Za-z0-9._-]{1,64}$`` — auth headers,
     cookies and device tokens are structurally unreachable.
  3. The log record is built field-by-field from a fixed allowlist;
     there is no API to attach arbitrary data.
  4. As a last line of defence, every emitted line passes through
     ``scrub_log_line``: labelled secrets (token/authorization/key/
     secret/password/cookie) are replaced with REDACTED, Bearer values
     are stripped, and any decimal with >2 fractional digits — i.e.
     anything precise enough to be a coordinate — is truncated to 2 dp
     (~1 km at Delhi's latitude), which is the precision floor we allow.
"""
import json
import logging
import re
import threading
import time
import uuid
from typing import Optional

from fastapi import APIRouter
from fastapi.responses import JSONResponse, Response
from starlette.datastructures import MutableHeaders

try:  # the console's mount — same dual-layout rule as middleware.py:
    # /in/<token> carries a credential in the path itself, so the
    # prefix is needed to blank the secret out of the log record below
    from admin_mount import ADMIN_MOUNT as _ADMIN_MOUNT
except ImportError:
    try:
        from server.admin_mount import ADMIN_MOUNT as _ADMIN_MOUNT
    except Exception:
        _ADMIN_MOUNT = None

__all__ = [
    "REGISTRY", "MetricsRegistry", "RequestLoggingMiddleware",
    "install", "router", "metrics_text",
    "error_body", "error_response",
    "set_field_age_s", "observe_route_plan",
    "scrub_log_line", "parse_prometheus",
    "LOG_DENYLIST", "LOG_FIELDS", "DURATION_BUCKETS_MS",
    "ERR_ROUTER_UNAVAILABLE", "ERR_LOCATION_DISABLED", "ERR_NOT_FOUND",
    "ERR_VALIDATION", "ERR_UPSTREAM", "ERR_INTERNAL",
]

_log = logging.getLogger("alive.request")

# ---------------------------------------------------------------------------
# Privacy guardrails
# ---------------------------------------------------------------------------

#: Field names that must never appear in a log record or metric label.
#: A test asserts the emitted record keys are disjoint from this set.
LOG_DENYLIST = frozenset({
    "authorization", "proxy-authorization", "www-authenticate",
    "cookie", "set-cookie",
    "token", "access_token", "refresh_token", "device_token",
    "x-device-token", "api_key", "apikey", "x-api-key",
    "secret", "password", "passwd",
    "lat", "lon", "lng", "latitude", "longitude", "coords",
    "body", "payload", "trajectory", "query", "query_string",
})

#: The only keys a request log record may ever contain (allowlist —
#: the record is built literally from this tuple, nothing else can get in).
LOG_FIELDS = ("ts", "request_id", "method", "route", "path",
              "status", "latency_ms", "tier_ms")

# Any decimal with >2 fractional digits is too precise to log — at this
# latitude 2 dp ≈ 1.1 km, which is the most precision we ever emit.
_COORD_RE = re.compile(r"-?\d{1,3}\.\d{3,}")
_SECRET_KEY_RE = re.compile(
    r'(?i)("?(?:[\w-]*?(?:authorization|token|secret|password|cookie'
    r'|api[_-]?key|device[_-]?token)[\w-]*?)"?\s*[:=]\s*"?)'
    r'[^\s",&}]+')
_BEARER_RE = re.compile(r'(?i)\bbearer\s+[^\s",&}]+')

_REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9._\-]{1,64}$")
_TIER_KEY_RE = re.compile(r"^[A-Za-z0-9_.\-]{1,32}$")
_SERVER_TIMING_RE = re.compile(
    r"(?i)([A-Za-z0-9_.\-]{1,32})\s*;\s*dur\s*=\s*([0-9]+(?:\.[0-9]+)?)")

#: Path prefixes whose remainder is a credential — logged redacted.
#: The magic sign-in link carries the admin token in the path itself;
#: scrub_log_line's labelled-secret pass can't see it (the segment
#: isn't labelled), so the path is rewritten before the record is built.
_SECRET_PATH_PREFIXES = ((_ADMIN_MOUNT or "/v2/admin") + "/in/",)


def scrub_log_line(line: str) -> str:
    """Last-defence redaction applied to every emitted log line.

    1. labelled secrets   ``"device_token":"abc"`` → ``"device_token":"REDACTED"``
    2. bearer values      ``Bearer xyz``           → ``Bearer REDACTED``
    3. >2dp decimals      ``28.6315``              → ``28.63``
    """
    line = _SECRET_KEY_RE.sub(lambda m: m.group(1) + "REDACTED", line)
    line = _BEARER_RE.sub("Bearer REDACTED", line)
    line = _COORD_RE.sub(lambda m: "%.2f" % float(m.group(0)), line)
    return line


def _request_id(scope) -> str:
    """Honour an inbound X-Request-ID only if it is a safe token —
    anything else (injections, 4 kB junk) is replaced, not logged."""
    for k, v in scope.get("headers") or []:
        if k.lower() == b"x-request-id":
            cand = v.decode("latin-1", errors="replace")
            return cand if _REQUEST_ID_RE.match(cand) else uuid.uuid4().hex
    return uuid.uuid4().hex


def _route_label(scope) -> str:
    """Route template (``/v2/place/{pid}``) for metric labels; unmatched
    paths collapse to 'unmatched' so junk URLs can't blow up cardinality."""
    route = scope.get("route")
    path = getattr(route, "path_format", None) or getattr(route, "path", None)
    return path if isinstance(path, str) and path else "unmatched"


def _tier_timings(scope, server_timing_headers) -> dict:
    """Per-tier ms from request.state.tier_timings and/or Server-Timing
    response headers. Only [a-z0-9_.-] keys and numeric values survive."""
    tiers = {}
    state = scope.get("state") or {}
    raw = state.get("tier_timings")
    if isinstance(raw, dict):
        for k, v in raw.items():
            if _TIER_KEY_RE.match(str(k)) and isinstance(v, (int, float)) \
                    and not isinstance(v, bool):
                tiers[str(k)] = float(v)
    for header in server_timing_headers:
        for name, dur in _SERVER_TIMING_RE.findall(header):
            if _TIER_KEY_RE.match(name):
                tiers[name] = float(dur)
    return tiers


# ---------------------------------------------------------------------------
# Metrics registry — counters, gauges, histograms → Prometheus text
# ---------------------------------------------------------------------------

DURATION_BUCKETS_MS = (5.0, 10.0, 25.0, 50.0, 100.0,
                       250.0, 500.0, 1000.0, 2500.0, 5000.0)


def _lkey(labels) -> tuple:
    return tuple(sorted((labels or {}).items()))


def _esc_label(v) -> str:
    return str(v).replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def _fmt_num(x: float) -> str:
    return "%g" % x


class MetricsRegistry:
    """In-process metrics: thread-safe, zero-dependency, Prometheus text.

    Series keys are (metric_name, sorted-label-tuple); created lazily on
    first write. ``render()`` produces the text exposition format that
    Prometheus/CloudWatch agents scrape.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._counters = {}          # (name, lkey) -> float
        self._gauges = {}            # (name, lkey) -> float
        self._histograms = {}        # (name, lkey) -> dict
        self._meta = {}              # name -> (type, help)

    # -- writers ----------------------------------------------------------
    def set_help(self, name: str, mtype: str, help_text: str) -> None:
        self._meta.setdefault(name, (mtype, help_text))

    def inc(self, name: str, labels: Optional[dict] = None,
            amount: float = 1.0, help: str = "") -> None:
        if help:
            self.set_help(name, "counter", help)
        with self._lock:
            key = (name, _lkey(labels))
            self._counters[key] = self._counters.get(key, 0.0) + amount

    def gauge(self, name: str, value: float,
              labels: Optional[dict] = None, help: str = "") -> None:
        if help:
            self.set_help(name, "gauge", help)
        with self._lock:
            self._gauges[(name, _lkey(labels))] = float(value)

    def gauge_add(self, name: str, delta: float,
                  labels: Optional[dict] = None, help: str = "") -> None:
        if help:
            self.set_help(name, "gauge", help)
        with self._lock:
            key = (name, _lkey(labels))
            self._gauges[key] = self._gauges.get(key, 0.0) + delta

    def observe(self, name: str, value: float,
                labels: Optional[dict] = None,
                buckets=DURATION_BUCKETS_MS, help: str = "") -> None:
        if help:
            self.set_help(name, "histogram", help)
        v = float(value)
        with self._lock:
            key = (name, _lkey(labels))
            h = self._histograms.get(key)
            if h is None:
                h = {"buckets": {b: 0 for b in sorted(buckets)},
                     "sum": 0.0, "count": 0}
                self._histograms[key] = h
            for b in h["buckets"]:
                if v <= b:
                    h["buckets"][b] += 1
            h["sum"] += v
            h["count"] += 1

    # -- readers ----------------------------------------------------------
    def counter_value(self, name: str, labels: Optional[dict] = None) -> float:
        return self._counters.get((name, _lkey(labels)), 0.0)

    def gauge_value(self, name: str, labels: Optional[dict] = None):
        return self._gauges.get((name, _lkey(labels)))

    def clear(self) -> None:
        with self._lock:
            self._counters.clear()
            self._gauges.clear()
            self._histograms.clear()
            self._meta.clear()

    # -- exposition -------------------------------------------------------
    def render(self) -> str:
        """Prometheus text exposition format (version 0.0.4)."""
        out = []
        with self._lock:
            counters = dict(self._counters)
            gauges = dict(self._gauges)
            hists = {k: {"buckets": dict(v["buckets"]), "sum": v["sum"],
                         "count": v["count"]}
                     for k, v in self._histograms.items()}
            meta = dict(self._meta)

        emitted = set()

        def header(name, default_type):
            if name in emitted:
                return
            mtype, help_text = meta.get(name, (default_type,
                                             "%s metric" % name))
            out.append("# HELP %s %s" % (name, help_text or name))
            out.append("# TYPE %s %s" % (name, mtype))
            emitted.add(name)

        def labels_str(lkey, extra=None):
            pairs = list(lkey) + (list(extra.items()) if extra else [])
            if not pairs:
                return ""
            return "{" + ",".join('%s="%s"' % (k, _esc_label(v))
                                  for k, v in pairs) + "}"

        for (name, lk), val in sorted(counters.items()):
            header(name, "counter")
            out.append("%s%s %s" % (name, labels_str(lk), _fmt_num(val)))

        for (name, lk), val in sorted(gauges.items()):
            header(name, "gauge")
            out.append("%s%s %s" % (name, labels_str(lk), _fmt_num(val)))

        for (name, lk), h in sorted(hists.items()):
            header(name, "histogram")
            base = dict(lk)
            for le, cnt in sorted(h["buckets"].items()):
                out.append('%s_bucket%s %s' % (
                    name, labels_str(lk, {"le": _fmt_num(le)}),
                    _fmt_num(cnt)))
            out.append('%s_bucket%s %s' % (
                name, labels_str(lk, {"le": "+Inf"}), _fmt_num(h["count"])))
            out.append("%s_sum%s %s" % (name, labels_str(lk),
                                        _fmt_num(h["sum"])))
            out.append("%s_count%s %s" % (name, labels_str(lk),
                                          _fmt_num(h["count"])))
            _ = base  # (labels already rendered via labels_str)
        return "\n".join(out) + ("\n" if out else "")


#: Process-wide registry — middleware and /metrics share this instance.
REGISTRY = MetricsRegistry()


def parse_prometheus(text: str) -> dict:
    """Tiny parser for the exposition format — used by tests and by any
    quick-and-dirty scrape checker. Returns {series_key: value} where
    series_key is 'name{labels}' or 'name' for unlabelled series."""
    series = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        sample, _, val = line.rpartition(" ")
        try:
            series[sample] = float(val)
        except ValueError:
            continue
    return series


# ---------------------------------------------------------------------------
# Convenience writers used by handlers/workers
# ---------------------------------------------------------------------------

def set_field_age_s(age_s: Optional[float]) -> None:
    """Worker/health hook: publish the air-field age as a gauge so the
    'field age > 45 min' alarm has something to read."""
    if isinstance(age_s, (int, float)) and not isinstance(age_s, bool):
        REGISTRY.gauge("alive_field_age_seconds", float(age_s),
                       help="Age of the newest air-quality field snapshot.")


def observe_route_plan(duration_ms: float, route: str = "/v2/plan") -> None:
    """Publish a /v2/plan pipeline duration (callers may time inner
    stages more precisely than end-to-end request latency)."""
    REGISTRY.observe("alive_route_plan_duration_ms", duration_ms,
                     labels={"route": route},
                     help="Route-plan pipeline duration, milliseconds.")


def _auto_field_age() -> None:
    """Best-effort refresh of the field-age gauge from airfield.FIELD —
    guarded so observability stays importable on its own."""
    try:
        from airfield import FIELD  # server/ on sys.path
    except Exception:
        try:
            from server.airfield import FIELD  # package import
        except Exception:
            return
    try:
        set_field_age_s(FIELD.status().get("age_s"))
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Request-logging middleware (pure ASGI — the body is never touched)
# ---------------------------------------------------------------------------

class RequestLoggingMiddleware:
    """One structured JSON line per request + metrics rollups.

    Privacy is structural: ``receive`` is passed through unwrapped (we
    cannot see a body we never read), the query string is never copied
    anywhere, and the only request header read is x-request-id.
    """

    def __init__(self, app, registry: Optional[MetricsRegistry] = None,
                 logger: Optional[logging.Logger] = None):
        self.app = app
        self.registry = registry if registry is not None else REGISTRY
        self.log = logger if logger is not None else _log

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        rid = _request_id(scope)
        scope.setdefault("state", {})["request_id"] = rid
        self.registry.gauge_add("alive_requests_in_flight", 1.0,
                                help="Requests currently being served.")

        start = time.perf_counter()
        status = 500
        timing_headers = []

        async def send_guarded(message):
            nonlocal status
            if message["type"] == "http.response.start":
                status = int(message.get("status") or 500)
                headers = MutableHeaders(
                    raw=message.setdefault("headers", []))
                headers.append("x-request-id", rid)
                for k, v in message["headers"]:
                    if k.lower() == b"server-timing":
                        timing_headers.append(
                            v.decode("latin-1", errors="replace"))
            await send(message)

        try:
            await self.app(scope, receive, send_guarded)
        except Exception:
            status = 500
            raise
        finally:
            latency_ms = (time.perf_counter() - start) * 1000.0
            route = _route_label(scope)
            method = str(scope.get("method", "?"))
            path = str(scope.get("path", ""))
            self.registry.gauge_add("alive_requests_in_flight", -1.0)
            self._record(method, route, status, latency_ms)
            self._emit(rid, method, route, path, status, latency_ms,
                       _tier_timings(scope, timing_headers))

    # -- metrics ----------------------------------------------------------
    def _record(self, method, route, status, latency_ms) -> None:
        r = self.registry
        r.inc("alive_http_requests_total",
              {"method": method, "route": route, "status": str(status)},
              help="HTTP requests served, by method/route/status.")
        r.observe("alive_request_duration_ms", latency_ms,
                  labels={"route": route},
                  help="End-to-end request latency, milliseconds.")
        if status >= 400:
            r.inc("alive_http_errors_total",
                  {"route": route, "class": "%dxx" % (status // 100)},
                  help="HTTP error responses, by route and class.")
        if route.endswith("/plan"):
            observe_route_plan(latency_ms, route=route)

    # -- logging ------------------------------------------------------------
    def _emit(self, rid, method, route, path, status, latency_ms,
              tier_ms) -> None:
        # The magic-link path IS the credential — the concrete secret
        # must never reach a log line, matched route or not (a near-miss
        # guess is still ~47/48 chars of the real token). The route
        # template in `route` is safe: it carries {secret}, not a value.
        for p in _SECRET_PATH_PREFIXES:
            if path.startswith(p):
                path = p + "<redacted>"
                break
        # Built field-by-field from LOG_FIELDS — nothing else can get in.
        record = {
            "ts": round(time.time(), 2),
            "request_id": rid,
            "method": method,
            "route": route,
            "path": path,
            "status": status,
            "latency_ms": round(latency_ms, 2),
        }
        if tier_ms:
            record["tier_ms"] = {k: round(v, 2) for k, v in
                                 sorted(tier_ms.items())}
        if set(record) & LOG_DENYLIST:
            raise RuntimeError("log record violated the privacy denylist")
        self.log.info(scrub_log_line(
            json.dumps(record, sort_keys=True, separators=(",", ":"))))


# ---------------------------------------------------------------------------
# /metrics endpoint + installer
# ---------------------------------------------------------------------------

router = APIRouter()


@router.get("/metrics", include_in_schema=False)
async def metrics():
    """Prometheus scrape target — plain-text exposition format."""
    _auto_field_age()
    return Response(
        content=REGISTRY.render(),
        media_type="text/plain; version=0.0.4; charset=utf-8")


def metrics_text() -> str:
    """Render the global registry — handy for a CloudWatch shipper."""
    _auto_field_age()
    return REGISTRY.render()


def install(app) -> object:
    """One-call mount: request-logging middleware + GET /metrics."""
    app.add_middleware(RequestLoggingMiddleware)
    app.include_router(router)
    return app


# ---------------------------------------------------------------------------
# Error taxonomy — {"error": <code>, "detail": <human>} like v2/places.py
# ---------------------------------------------------------------------------

# Stable machine codes — keep in sync with what handlers already emit.
ERR_ROUTER_UNAVAILABLE = "router_unavailable"     # OSRM/Routes down
ERR_LOCATION_DISABLED = "amazon_location_disabled"  # no ALIVE_LOCATION_KEY
ERR_NOT_FOUND = "not_found"                       # unknown id / no match
ERR_VALIDATION = "invalid_request"                # bad client input
ERR_UPSTREAM = "upstream_error"                   # any 3rd-party failure
ERR_INTERNAL = "internal_error"                   # our bug; detail sanitized


def error_body(code: str, detail: Optional[str] = None, **extra) -> dict:
    """Envelope for handlers that return dicts ({"options": [], ...}):
        {"error": code, "detail": human, ...extra}
    Detail is for humans — never put tokens, coords or stack traces in it."""
    body = {"error": str(code)}
    if detail is not None:
        body["detail"] = scrub_log_line(str(detail))
    body.update(extra)
    return body


def error_response(code: str, http_status: int = 400,
                   detail: Optional[str] = None, **extra) -> JSONResponse:
    """JSONResponse version for handlers that short-circuit:
        return error_response(ERR_NOT_FOUND, 404, "route_id expired")"""
    return JSONResponse(status_code=int(http_status),
                        content=error_body(code, detail, **extra))
