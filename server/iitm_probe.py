"""Probe for IITM's Early Warning System Delhi PM2.5 forecast.

IITM Pune runs a WRF-Chem (400 m) air-quality model whose Delhi EWS
publishes a "hourly air quality forecast for next 72 hours" at
ews.tropmet.res.in (index-2.php) plus forecast-verification plots at
analysis.php. This module is the machine-readable probe for it.

=== PROBE LOG (2026-10-01, this box) ===================================

Host reachability — FAILED:
  - DNS `ews.tropmet.res.in` resolves to 172.25.1.46 — an RFC1918
    *private* address — via the local resolver AND public resolvers
    (dig @8.8.8.8 and @1.1.1.1 agree). The service is currently not
    publicly routable; likely moved inside the IITM/MoES intranet.
  - GET http://ews.tropmet.res.in/        -> curl exit 28 (timeout, code 000)
  - GET https://ews.tropmet.res.in/       -> curl exit 28 (timeout, code 000)
  - GET https://ews.tropmet.res.in:8080/  -> timeout (code 000)

Endpoints referenced by the spec, all unreachable for the same reason:
  - https://ews.tropmet.res.in/?menu_id=291  (EWS bulletin page)
  - https://ews.tropmet.res.in/index-2.php   (WRF-Chem hourly forecast)
  - https://ews.tropmet.res.in/analysis.php  (multi-model verification)

Evidence about what the pages serve (search-engine cache):
  - index-2.php renders "IITM WRF-Chem Model hourly Air Quality forecast
    for Next 72 Hours (Time in IST)" as a CHART/plot (PM2.5 [µg/m³]);
    no JSON/CSV data endpoint was visible in cached markup. The
    underlying data calls (likely ajax/Highcharts feeds) could not be
    inspected because the host is unreachable.
  - Wayback Machine: zero captures of ews.tropmet.res.in.
  - Common Crawl index: no records.

Conclusion: IITM WRF-Chem Delhi forecast exists (72h hourly PM2.5), but
no machine-readable endpoint is consumable from the public internet
today — the host does not route publicly. `iitm_hourly_pm25()` below
still performs a live best-effort probe (short timeouts, strict JSON
shape checks) so it picks the feed up automatically if IITM re-exposes
it; until then it returns None. Documented failure > fake parsing.
======================================================================
"""
import time
from typing import Optional

import httpx

EWS_BASE = "https://ews.tropmet.res.in"

# Candidate data endpoints, in probing order. The PHP pages themselves
# are checked first — if IITM ever serves JSON directly from them (or
# embeds a data block), the parser below finds it. Sibling apps under
# the same vhost (e.g. a /data or /api path) are worth re-checking when
# the host becomes reachable again.
CANDIDATES = [
    f"{EWS_BASE}/index-2.php",
    f"{EWS_BASE}/analysis.php",
    f"{EWS_BASE}/?menu_id=291",
]

_TIMEOUT = httpx.Timeout(4.0, connect=3.0)


def _extract_pm25_series(obj) -> Optional[list]:
    """Recursively hunt for a list of 24-90 numeric values labelled like
    an hourly PM2.5 series inside a decoded JSON object. Strict: the key
    must mention pm2.5/pm25 and every value must be a sane number."""
    keys = ("pm2_5", "pm25", "pm2.5", "pm_25")
    if isinstance(obj, dict):
        for k, v in obj.items():
            if any(t in str(k).lower() for t in keys):
                vals = v[0] if isinstance(v, list) and len(v) == 1 else v
                if isinstance(vals, list) and 24 <= len(vals) <= 96 and all(
                        isinstance(x, (int, float)) and 0 <= x <= 1500 for x in vals):
                    return [float(x) for x in vals]
        for v in obj.values():
            found = _extract_pm25_series(v)
            if found:
                return found
    elif isinstance(obj, list):
        for v in obj:
            found = _extract_pm25_series(v)
            if found:
                return found
    return None


async def iitm_hourly_pm25(client: Optional[httpx.AsyncClient] = None) -> Optional[list]:
    """Next-72h hourly PM2.5 forecast for Delhi from IITM WRF-Chem.

    Returns a list of hourly µg/m³ values when a machine-readable feed
    is reachable, else None. Never fabricates. As of 2026-10-01 the EWS
    host resolves to a private IP and does not respond — see PROBE LOG.
    """
    own = client is None
    if own:
        client = httpx.AsyncClient(timeout=_TIMEOUT,
                                   headers={"User-Agent": "delhi-air-108/0.1 (probe)"})
    try:
        for url in CANDIDATES:
            try:
                r = await client.get(url)
                r.raise_for_status()
            except (httpx.HTTPError, OSError):
                continue
            ctype = r.headers.get("content-type", "")
            if "json" in ctype:
                try:
                    series = _extract_pm25_series(r.json())
                except ValueError:
                    series = None
                if series:
                    return series
            # HTML/plot pages carry no hourly series we can trust —
            # parsing canvas-rendered chart pixels would be fabrication.
        return None
    finally:
        if own:
            await client.aclose()


def probe_sync() -> Optional[list]:
    """Sync wrapper for scripts/tests."""
    import asyncio
    return asyncio.run(iitm_hourly_pm25())


if __name__ == "__main__":
    t0 = time.time()
    out = probe_sync()
    print(f"iitm_hourly_pm25 -> {out}  ({time.time() - t0:.1f}s)")
