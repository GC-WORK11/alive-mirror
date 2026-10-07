"""Security middleware + input sanitation for the ALive-108 API.

Pure-ASGI (Starlette-style) middlewares — no BaseHTTPMiddleware, so
request bodies are never silently buffered and 429/413 rejections go
out before the endpoint or its dependencies run.

MOUNT — the integrator adds exactly two lines to server/main.py,
right after `app = FastAPI(...)` (before or after the CORS line —
ordering vs CORS only decides whether OPTIONS preflights count
against the rate bucket; either is safe):

    import middleware
    middleware.attach(app)

`attach()` wires the full stack with env-tunable defaults:

    SecurityHeadersMiddleware   (outermost — headers land on EVERY
                                 response, including our own 429/413s)
    RateLimitMiddleware         (token/IP token-bucket, honest 429s)
    BodySizeLimitMiddleware     (413 before a big body is read)

    ALIVE_RATE_RPS        sustained requests/s per client   (default 10)
    ALIVE_RATE_BURST      burst allowance per client        (default 30)
    ALIVE_MAX_BODY_BYTES  POST/PUT/PATCH body cap           (default 2 MiB)
    ALIVE_SEC_HSTS        "0" disables the HSTS header      (default on,
                                                            https only)

SLOW-LORIS / HEADER-TIMEOUT NOTE — an ASGI middleware only sees a
request AFTER the HTTP layer has parsed its headers, so a header-read
deadline cannot live here. It must live at the edge: we run behind the
NLB (docs/plan/05 §1), whose idle/connect timeout bounds dribbled
headers, and uvicorn's --timeout-keep-alive bounds idle keep-alives.
Set both deliberately; do not rely on this module for it.

Input sanitation helpers (bounded_lat, bounded_lon, bounded_float,
bounded_str, parse_point) are exported for endpoint modules — they
are pure functions with no middleware wiring.
"""
import hashlib
import math
import os
import time
from typing import Optional

from starlette.datastructures import Headers, MutableHeaders

# ---------------------------------------------------------------------------
# helpers: tiny JSON responder that works at raw ASGI level
# ---------------------------------------------------------------------------


async def _json_reply(send, status: int, payload: dict,
                      extra_headers: Optional[list] = None) -> None:
    import json
    body = json.dumps(payload).encode()
    hdrs = [(b"content-type", b"application/json"),
            (b"content-length", str(len(body)).encode())]
    if extra_headers:
        hdrs.extend(extra_headers)
    await send({"type": "http.response.start", "status": status,
                "headers": hdrs})
    await send({"type": "http.response.body", "body": body})


# ---------------------------------------------------------------------------
# 1. Rate limiting — in-memory token bucket per client token / IP
# ---------------------------------------------------------------------------


def _client_key(scope) -> str:
    """Anonymous device token when the client sends one, else the
    source IP. Key material is sha256-truncated before it keys the
    bucket map — the same treatment /v2/trip gives tokens before the
    store, so the limiter can't become a place raw tokens sit around."""
    headers = Headers(scope=scope)
    token = headers.get("x-device-token") or headers.get("authorization")
    if token:
        raw = f"tok:{token.strip()[:128]}"
    else:
        raw = f"ip:{_client_ip(headers, scope)}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _client_ip(headers: Headers, scope) -> str:
    """Source IP for rate bucketing.

    Behind an appending balancer (the NLB) each proxy appends the peer
    it actually saw, so the RIGHTMOST X-Forwarded-For hop is the one
    the balancer wrote — everything left of it is client-supplied and
    can rotate per request, which would defeat per-IP budgets. Fall
    back to the socket peer when XFF is absent or carries no usable
    hop."""
    fwd = headers.get("x-forwarded-for")
    if fwd:
        for hop in reversed(fwd.split(",")):
            ip = hop.strip()
            if ip:
                return ip
    return (scope.get("client") or ("?",))[0]


class _Bucket:
    __slots__ = ("tokens", "ts")

    def __init__(self, tokens: float):
        self.tokens = tokens
        self.ts = time.monotonic()


class RateLimitMiddleware:
    """Token bucket per client (device-token or IP).

    rate_per_s : sustained refill rate, requests/second.
    burst      : bucket capacity — how big a burst is allowed.
    path_overrides : {path_prefix: (rate_per_s, burst)} for endpoints
        that deserve a tighter budget (POST /v2/plan fans out to paid
        upstreams; POST /v2/trip + /observe + /report are donations).
        Each limit class gets its own bucket per client, so a burst on
        /v2/trip drains the trip budget only — never the global one.
    exempt_prefixes : paths that skip limiting (default /health —
        monitoring must not 429).
    max_keys   : bound on tracked clients; stalest buckets are evicted.

    A limited request gets 429 + `Retry-After` (whole seconds until one
    token refills) + a JSON body that says the same — honest headers,
    no silent drops.
    """

    def __init__(self, app, rate_per_s: float = 10.0, burst: float = 30.0,
                 path_overrides: Optional[dict] = None,
                 exempt_prefixes: tuple = ("/health",),
                 max_keys: int = 20000):
        self.app = app
        self.rate = float(rate_per_s)
        self.burst = float(burst)
        self.overrides = {p: (float(r), float(b))
                          for p, (r, b) in (path_overrides or {}).items()}
        self.exempt = tuple(exempt_prefixes or ())
        self.max_keys = int(max_keys)
        self._buckets: dict = {}

    def _limits_for(self, path: str) -> tuple:
        for pref, lim in self.overrides.items():
            if path.startswith(pref):
                return pref, lim[0], lim[1]
        return "*", self.rate, self.burst

    def _evict(self, now: float) -> None:
        if len(self._buckets) <= self.max_keys:
            return
        stale = [k for k, b in self._buckets.items() if now - b.ts > 600]
        for k in stale:
            self._buckets.pop(k, None)
        if len(self._buckets) > self.max_keys:
            for k, _ in sorted(self._buckets.items(),
                               key=lambda kv: kv[1].ts)[:self.max_keys // 10]:
                self._buckets.pop(k, None)

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        path = scope.get("path", "")
        if any(path.startswith(p) for p in self.exempt):
            await self.app(scope, receive, send)
            return

        cls, rate, cap = self._limits_for(path)
        key = f"{_client_key(scope)}|{cls}"  # one bucket per client+class
        now = time.monotonic()
        b = self._buckets.get(key)
        if b is None:
            b = self._buckets[key] = _Bucket(cap)
            self._evict(now)
        else:
            b.tokens = min(cap, b.tokens + (now - b.ts) * rate)
            b.ts = now

        if b.tokens >= 1.0:
            b.tokens -= 1.0
            await self.app(scope, receive, send)
            return

        retry = max(1, math.ceil((1.0 - b.tokens) / rate))
        await _json_reply(send, 429, {
            "error": "rate_limited",
            "detail": "too many requests from this client",
            "retry_after_s": retry,
            "limit": {"rate_per_s": rate, "burst": cap},
        }, extra_headers=[(b"retry-after", str(retry).encode())])


# ---------------------------------------------------------------------------
# 2. Request body cap — 413 before a large POST body is read
# ---------------------------------------------------------------------------

_BODY_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


class BodySizeLimitMiddleware:
    """Reject request bodies over max_bytes (default 2 MiB — trip
    traces are the biggest upload and thin to <=5000 points at ~40 B
    each, so 2 MiB is generous, not tight).

    Fast path: a declared Content-Length over the cap is refused
    immediately, without reading a byte. No Content-Length (chunked):
    the body is drained up to cap+1 and rejected the moment it crosses;
    an under-cap body is replayed to the endpoint intact, so chunked
    uploads keep working.
    """

    def __init__(self, app, max_bytes: int = 2 * 1024 * 1024):
        self.app = app
        self.max_bytes = int(max_bytes)

    async def __call__(self, scope, receive, send):
        if (scope["type"] != "http"
                or scope.get("method", "") not in _BODY_METHODS):
            await self.app(scope, receive, send)
            return

        cl = Headers(scope=scope).get("content-length")
        if cl is not None:
            try:
                declared = int(cl)
            except ValueError:
                declared = -1
            if declared < 0:
                await _json_reply(send, 400, {
                    "error": "bad_content_length",
                    "detail": "unparseable Content-Length header"})
                return
            if declared > self.max_bytes:
                await _json_reply(send, 413, {
                    "error": "payload_too_large",
                    "detail": "request body exceeds the server cap",
                    "max_bytes": self.max_bytes})
                return
            await self.app(scope, receive, send)
            return

        # chunked / unknown length: drain up to the cap, then decide
        body = bytearray()
        while True:
            msg = await receive()
            if msg["type"] == "http.disconnect":
                return  # client went away mid-upload — nothing to serve
            body.extend(msg.get("body", b""))
            if len(body) > self.max_bytes:
                await _json_reply(send, 413, {
                    "error": "payload_too_large",
                    "detail": "request body exceeds the server cap",
                    "max_bytes": self.max_bytes})
                return
            if not msg.get("more_body"):
                break

        replayed = False

        async def replay():
            nonlocal replayed
            if not replayed:
                replayed = True
                return {"type": "http.request", "body": bytes(body),
                        "more_body": False}
            return await receive()

        await self.app(scope, replay, send)


# ---------------------------------------------------------------------------
# 3. Security headers — measured set, safe for /admin and /city pages
# ---------------------------------------------------------------------------

_DEFAULT_HEADERS = {
    "x-content-type-options": "nosniff",
    "x-frame-options": "DENY",
    # both HTML pages fetch same-origin only — no-referrer breaks nothing
    "referrer-policy": "no-referrer",
    "x-xss-protection": "0",  # disable the legacy auditor (OWASP guidance)
}


class SecurityHeadersMiddleware:
    """Set the defensive header set on every response, ours included.

    X-Content-Type-Options nosniff, X-Frame-Options DENY, Referrer-Policy
    no-referrer, X-XSS-Protection 0. HSTS only when the request arrived
    over TLS (scheme https or X-Forwarded-Proto from the NLB) — sending
    it on plain HTTP is a no-op anyway. No CSP: the admin/city pages
    use inline <script>/<style>, and a wrong CSP is worse than none —
    noted, not silently half-done.
    """

    def __init__(self, app, hsts: bool = True,
                 hsts_max_age: int = 31_536_000,
                 headers: Optional[dict] = None):
        self.app = app
        self.hsts = hsts
        self.hsts_max_age = int(hsts_max_age)
        self.headers = dict(_DEFAULT_HEADERS if headers is None else headers)

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        secure = (scope.get("scheme") == "https"
                  or Headers(scope=scope).get("x-forwarded-proto") == "https")

        async def send_with_headers(message):
            if message["type"] == "http.response.start":
                h = MutableHeaders(raw=message.setdefault("headers", []))
                for k, v in self.headers.items():
                    h.setdefault(k, v)
                if self.hsts and secure:
                    h.setdefault("strict-transport-security",
                                 f"max-age={self.hsts_max_age}")
            await send(message)

        await self.app(scope, receive, send_with_headers)


# ---------------------------------------------------------------------------
# 4. Input sanitation helpers — for endpoint modules to use explicitly
# ---------------------------------------------------------------------------

LAT_MIN, LAT_MAX = -90.0, 90.0
LON_MIN, LON_MAX = -180.0, 180.0
# NCR bbox (lon_min, lat_min, lon_max, lat_max) — same as deps.NCR_BBOX
NCR_BBOX = (76.80, 28.20, 77.90, 28.95)


def bounded_float(v, lo: float, hi: float, name: str = "value") -> float:
    """Coerce to float; reject NaN/inf and out-of-range. Raises
    ValueError naming the field — callers map that to a 4xx."""
    try:
        x = float(v)
    except (TypeError, ValueError):
        raise ValueError(f"{name}: not a number")
    if math.isnan(x) or math.isinf(x):
        raise ValueError(f"{name}: not finite")
    if not (lo <= x <= hi):
        raise ValueError(f"{name}: {x} outside [{lo}, {hi}]")
    return x


def bounded_lat(v, name: str = "lat") -> float:
    return bounded_float(v, LAT_MIN, LAT_MAX, name)


def bounded_lon(v, name: str = "lon") -> float:
    return bounded_float(v, LON_MIN, LON_MAX, name)


def in_ncr(lat: float, lon: float) -> bool:
    return (NCR_BBOX[1] <= lat <= NCR_BBOX[3]
            and NCR_BBOX[0] <= lon <= NCR_BBOX[2])


def bounded_str(v, max_len: int = 200, name: str = "q",
                allow_empty: bool = False) -> str:
    """Coerce to str, strip ASCII control characters, cap length.
    Raises ValueError on non-string input or empty-after-strip
    (unless allow_empty)."""
    if not isinstance(v, (str, int, float)):
        raise ValueError(f"{name}: not a string")
    s = "".join(ch for ch in str(v)
                if ch >= " " or ch in "\t\n\r")[:max_len].strip()
    if not s and not allow_empty:
        raise ValueError(f"{name}: empty")
    return s


def parse_point(v, name: str = "point") -> tuple:
    """{lat,lon} or [lon,lat] (GeoJSON order) → validated (lat, lon).
    Same shapes v2/plan._pt accepts, plus range/finiteness checks."""
    if isinstance(v, dict):
        return bounded_lat(v["lat"], f"{name}.lat"), \
            bounded_lon(v["lon"], f"{name}.lon")
    if isinstance(v, (list, tuple)) and len(v) >= 2:
        return bounded_lat(v[1], f"{name}[1]"), \
            bounded_lon(v[0], f"{name}[0]")
    raise ValueError(f"{name}: need {{lat,lon}} or [lon,lat]")


# ---------------------------------------------------------------------------
# attach() — the 2-line mount for main.py
# ---------------------------------------------------------------------------

# tighter budgets for endpoints that hit paid upstreams or accept uploads
_DEFAULT_PATH_LIMITS = {
    "/v2/plan": (2.0, 6),
    "/v2/reroute": (2.0, 6),
    "/v2/trip": (1.0, 5),
    "/observe": (1.0, 5),
    "/report": (1.0, 5),
}


def attach(app, rate_per_s: Optional[float] = None,
           burst: Optional[float] = None,
           max_body_bytes: Optional[int] = None,
           path_overrides: Optional[dict] = None,
           hsts: Optional[bool] = None) -> None:
    """Mount the full stack. add_middleware wraps, so the LAST added is
    outermost — added in reverse so SecurityHeaders stays outermost and
    its headers land on our own 429/413s too; the rate limiter rejects
    before the body cap ever reads."""
    rate = float(os.environ.get("ALIVE_RATE_RPS",
                                rate_per_s if rate_per_s is not None else 10.0))
    bst = float(os.environ.get("ALIVE_RATE_BURST",
                               burst if burst is not None else 30.0))
    cap = int(os.environ.get("ALIVE_MAX_BODY_BYTES",
                             max_body_bytes
                             if max_body_bytes is not None
                             else 2 * 1024 * 1024))
    use_hsts = (os.environ.get("ALIVE_SEC_HSTS", "1") != "0"
                if hsts is None else hsts)

    app.add_middleware(BodySizeLimitMiddleware, max_bytes=cap)
    # ALIVE_RATE_LIMIT=0 disables throttling entirely — for tests and
    # local dev only. Explicit kwargs always mount (a caller that tuned
    # the numbers means it); the path overrides don't read the global
    # rate knobs, so a kill-switch beats env-scaling.
    explicit = (rate_per_s is not None or burst is not None
                or path_overrides is not None)
    if explicit or os.environ.get("ALIVE_RATE_LIMIT", "1") != "0":
        app.add_middleware(RateLimitMiddleware, rate_per_s=rate, burst=bst,
                           path_overrides=(path_overrides
                                           if path_overrides is not None
                                           else _DEFAULT_PATH_LIMITS))
    app.add_middleware(SecurityHeadersMiddleware, hsts=use_hsts)


__all__ = [
    "RateLimitMiddleware", "BodySizeLimitMiddleware",
    "SecurityHeadersMiddleware", "attach",
    "bounded_float", "bounded_lat", "bounded_lon", "in_ncr",
    "bounded_str", "parse_point", "NCR_BBOX",
]
