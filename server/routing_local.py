"""Local-first OSRM routing — drop-in replacement for v2/deps.osrm_route.

Same signature, same OSRM route-object shape. Tries the self-hosted
osrm-routed (Delhi NCR extract, ~0 AWS rupees per query) first, falls
back to the public demo server with a loud flag so callers/metrics can
tell the difference.

Env:
  OSRM_URL           base URL of local osrm-routed (default http://127.0.0.1:5001)
  OSRM_URL_DRIVING   per-profile override — a self-hosted osrm-routed serves
  OSRM_URL_CYCLING   ONE profile and ignores the /{profile}/ path segment,
  OSRM_URL_WALKING   so point each mode at the right daemon (scripts/geo/
                     run_stack.sh publishes car=5001 foot=5002 bicycle=5003).
  OSRM_LOCAL_TIMEOUT seconds before failing over to the demo (default 3.0)

INTEGRATOR NOTE — the 3 lines that make /v2 prefer this over the public
demo, in server/v2/deps.py (owner: another lane):

  1.  import:   from routing_local import osrm_route as _geo_route
  2.  inside osrm_route(), replace the `url = (...)` line with:
        return await _geo_route(profile, flon, flat, tlon, tlat)
  3.  delete the now-dead try/except + url construction (or keep the
      whole body as `return await _geo_route(...)`).

`route()`/`osrm_route()` on the module-level LocalRouter behave exactly
like deps.osrm_route: Optional[dict] of the first OSRM route, plus:
  route["source"]            "osrm-local:<url>" | "osrm-public-demo"
  route["demo_rate_limited"] True only on the demo fallback — LOUD
  route["fallback_reason"]   why local was skipped (when applicable)
"""
import os
import sys
from typing import Optional

import httpx

_SERVER_DIR = os.path.dirname(os.path.abspath(__file__))
if _SERVER_DIR not in sys.path:
    sys.path.insert(0, _SERVER_DIR)

PUBLIC_OSRM = "https://router.project-osrm.org"
_PROFILES = ("driving", "cycling", "walking")


class LocalRouter:
    """Local osrm-routed first, public demo as flagged fallback."""

    def __init__(self, base_url: Optional[str] = None,
                 timeout: Optional[float] = None):
        self.base = (base_url or os.environ.get("OSRM_URL")
                     or "http://127.0.0.1:5001").rstrip("/")
        self.timeout = float(
            timeout or os.environ.get("OSRM_LOCAL_TIMEOUT", "3.0"))
        self._client: Optional[httpx.AsyncClient] = None

    def _http(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(8.0, connect=4.0),
                headers={"User-Agent": "alive108-geo/0.1"})
        return self._client

    def _url_for(self, profile: str) -> str:
        """Per-profile daemon override; a self-hosted osrm-routed ignores
        the profile path segment, so the PORT picks the real profile."""
        env = {"driving": "OSRM_URL_DRIVING", "cycling": "OSRM_URL_CYCLING",
               "walking": "OSRM_URL_WALKING"}.get(profile)
        base = (os.environ.get(env) if env else None) or self.base
        return base.rstrip("/")

    async def route(self, profile: str, flon: float, flat: float,
                    tlon: float, tlat: float) -> Optional[dict]:
        if profile not in _PROFILES:
            profile = "driving"
        params = {"overview": "full", "geometries": "geojson",
                  "alternatives": "false", "steps": "false"}
        coords = f"{flon},{flat};{tlon},{tlat}"
        local_base = self._url_for(profile)

        # 1) self-hosted Delhi NCR daemon
        local_err: Optional[str] = None
        try:
            r = await self._http().get(
                f"{local_base}/route/v1/{profile}/{coords}",
                params=params, timeout=self.timeout)
            r.raise_for_status()
            routes = r.json().get("routes", [])
            if routes:
                rt = routes[0]
                rt["source"] = f"osrm-local:{local_base}"
                return rt
            local_err = "no route in local extract"
        except Exception as e:  # daemon down/unreachable — fall through
            local_err = f"{type(e).__name__}: {e}"

        # 2) public demo fallback — loudly flagged, rate-limited by them
        try:
            r = await self._http().get(
                f"{PUBLIC_OSRM}/route/v1/{profile}/{coords}",
                params=params)
            r.raise_for_status()
            routes = r.json().get("routes", [])
            if routes:
                rt = routes[0]
                rt["source"] = "osrm-public-demo"
                rt["demo_rate_limited"] = True
                rt["warning"] = ("DEMO-RATE-LIMITED: public OSRM demo in use "
                                 "— start scripts/geo/run_stack.sh and set OSRM_URL")
                rt["fallback_reason"] = local_err
                return rt
        except Exception:
            return None
        return None


_default = LocalRouter()

# Drop-in for deps.osrm_route — identical signature.
osrm_route = _default.route
