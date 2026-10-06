"""DPCC (dpccairdata.com) station-ingest adapter — Delhi Pollution Control
Committee's own 5-minute pages, scraped as an opt-in third feed behind
ALIVE_DPCC_INGEST (default OFF; wired alongside WAQI in
airfield._grab_stations).

Why it exists: the 2026-10-06 holdout lane (docs/lanes/
accuracy-holdout-report.md) showed the field is provably blind at 7 DPCC
instrument sites (nearest field sample 1.5-5.8 km away). DPCC publishes
those same instruments' raw readings publicly every ~5 minutes — this
adapter turns them into field samples.

Units — VERIFIED against live pages (Vivek Vihar 2026-10-06 21:40 IST):
particulate rows render as e.g. 'Particulate Matter < 2.5 µg ... 69.0
µg/m3', gases as '31.0 µg/m3', CO as '0.5 mg/m3'. These are RAW
concentrations, not indices — unlike WAQI, whose iaqi is the US-EPA
NowCast sub-index (inverted via breakpoints in ingest_waqi). The field
consumes µg/m³ post-debias either way, but a DPCC value is the
instrument's own instantaneous reading while a WAQI value for the same
instrument is a smoothed sub-index. Parser asserts the expected unit
token per row (µg/m3 / mg/m3); a page that starts serving e.g. AQI
counts as unit_mismatch, never silently reinterpreted.

Source shape:
  GET https://www.dpccairdata.com/dpccairdata/display/
      -> index embeds 'stName=<base64>' links for the ~24 tree stations.
  Each station page's nav bar additionally links the stations the tree
  omits (IGNOU, JNU, CWG Akshardham, NSUT West Campus, Talkatora Garden,
  SBV Delhi Cantt — the 'Supersite (Rouse Avenue)' page is live but its
  data has been stuck at March 2025; staleness drops it). Discovery is
  therefore two-phase: tree links from the index + nav hrefs harvested
  off the first fetched page.
  GET .../AallStationView5MinData.php?stName=<b64>
      -> two tables (gases, particulate+met); rows carry their own
      'Day, Month DD, YYYY' date + 'HH:MM:SS' IST timestamp per cell.

Pages carry NO lat/lon — coords resolve from the committed NCR registry
(data/delhi_climatology.json.gz, same artifact ingest_cpcb uses) via a
static label->coord map for the 30 known sites (each mapped to its
registry id in STATIONS below; DPCC's own misspelling 'Sri Auribindo
Marg' is the label key, the registry spells it 'Sri Aurobindo Marg').
A station not in the map falls back to registry name normalization, else
is counted unresolved_coords — never placed by guessing.

Politeness: this is someone's beta PHP site, not an API. One fetch
bundle is cached module-level for CACHE_TTL_S (900 s — 3x their ~5-min
cadence), every page GET is capped (MAX_PAGES), concurrency bounded
(PAGE_SEM=4), and all failures surface in status/skipped — nothing is
retried past one retry and nothing is invented.

Contract — fetch(client=None, bbox=..., now=...) -> dict:
  status    "ok" | "disabled" | "unavailable: <reason>"
  obs       normalized readings: {station_id (b64 stName), name, lat,
            lon, parameter, value (µg/m³), unit, src_value, src_unit,
            ts, ts_utc}
  stations  airindex station-obs schema for pm25 —
            {lat, lon, name, pm25, ts, station_id}
  skipped   honest counters: no_pm25, bad_value, bad_ts, stale,
            unit_mismatch, unresolved_coords, http_error
grab_async(client) -> list[(lat, lon, name, {field-keyed vals})] is the
airfield variant; returns [] when the flag is off or the source fails —
the modelled field stands alone exactly like the other feeds.
"""
import asyncio
import base64
import concurrent.futures
import gzip
import html as _html
import json
import math
import os
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from typing import Optional

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import httpx  # noqa: E402

INDEX = "https://www.dpccairdata.com/dpccairdata/display/"
PAGE = ("https://www.dpccairdata.com/dpccairdata/display/"
        "AallStationView5MinData.php?stName={}")
ENV_FLAG = "ALIVE_DPCC_INGEST"
SOURCE = "dpcc"

# A browser UA — the site answers plain bots with a ModSecurity 406 and
# index.php 404s; the bare display/ index is the working entry point.
_UA = {"User-Agent":
       "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
       "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 "
       "Safari/537.36"}

CACHE_TTL_S = 900.0        # never re-scrape inside 15 min
MAX_AGE_S = 5400.0         # 90 min — a 5-min cadence page older than
                         # that is stale, not fresh (Supersite is
                         # months-stale and must die here)
MAX_PAGES = 40             # station pages per refresh, worst case
PAGE_SEM = 4               # concurrent page fetches — be gentle
GET_ATTEMPTS = 2
BACKOFF_S = 0.8
MAX_PM25 = 1500.0          # same implausible bound as the other adapters

IST = timezone(timedelta(hours=5, minutes=30))

# DPCC row label -> (param, src_unit, unit_factor->µg/m³, field key,
#                    plausibility range in µg/m³). Rows whose unit token
# is absent from the conc cell are counted unit_mismatch, not parsed —
# protects against the site silently changing what it publishes.
_PARAMS = [
    ("Particulate Matter < 2.5", "pm25", "µg/m3", 1.0, "pm2_5",
     (0.0, 1500.0)),
    ("Particulate Matter < 10", "pm10", "µg/m3", 1.0, "pm10",
     (0.0, 3000.0)),
    ("Nitrogen Dioxide", "no2", "µg/m3", 1.0, "nitrogen_dioxide",
     (0.0, 3000.0)),
    ("Ozone", "o3", "µg/m3", 1.0, "ozone", (0.0, 2000.0)),
    ("Sulphur Dioxide", "so2", "µg/m3", 1.0, "sulphur_dioxide",
     (0.0, 3000.0)),
    ("Carbon Monoxide", "co", "mg/m3", 1000.0, "carbon_monoxide",
     (0.0, 60000.0)),
]

# Station label (exactly as the site links it) -> (lat, lon, registry
# name/id). All verified against server/data/delhi_climatology.json.gz;
# 'canonical' marks the registry's canonical-name row. See module
# docstring for the DPCC 'Auribindo' spelling note.
STATIONS = {
    "Alipur": (28.8153, 77.1530, "DPCC-6932"),
    "Anand Vihar": (28.6468, 77.3162, "canonical"),
    "Ashok Vihar": (28.6927, 77.1754, "canonical"),
    "Dr. Karni Singh Shooting Range": (28.4986, 77.2648, "DPCC-6934"),
    "Dwarka, Sector 8": (28.5710, 77.0640, "canonical Dwarka Sec-8"),
    "Jahangirpuri": (28.7328, 77.1708, "canonical"),
    "Jawaharlal Nehru Stadium": (28.5803, 77.2338, "DPCC-6957"),
    "Major Dhyan Chand National Stadium":
        (28.6113, 77.2377, "DPCC-6929"),
    "Mandir Marg": (28.6364, 77.2015, "canonical"),
    "Mundka": (28.6847, 77.0766, "DPCC-10486"),
    "Najafgarh": (28.5702, 76.9338, "DPCC-10488"),
    "Narela": (28.8522, 77.0929, "canonical"),
    "Nehru Nagar": (28.5686, 77.2515, "canonical"),
    "Okhla Phase-2": (28.5308, 77.2813, "canonical Okhla Ph-2"),
    "Patparganj": (28.6237, 77.3067, "canonical"),
    "Pooth Khurd, Bawana": (28.7936, 77.0326, "canonical Bawana"),
    "Punjabi Bagh": (28.6692, 77.1316, "canonical"),
    "Pusa": (28.6396, 77.1691, "canonical"),
    "R.K. Puram": (28.5640, 77.1868, "canonical RK Puram"),
    "Rohini": (28.7325, 77.1188, "canonical"),
    "Sonia Vihar": (28.7330, 77.2494, "canonical"),
    "Sri Auribindo Marg": (28.5313, 77.1902, "DPCC-10484"),
    "Vivek Vihar": (28.6723, 77.3153, "canonical"),
    "Wazirpur": (28.6999, 77.1658, "canonical"),
    # nav-bar-only stations (absent from the index tree)
    "IGNOU": (28.4936, 77.2012, "DPCC-6224597 IGNOU_Maidan Garhi"),
    "JNU": (28.5407, 77.1685, "DPCC-6224594"),
    "CWG Sports Complex,Akshardham":
        (28.6158, 77.2720, "DPCC-6224596 Commonwealth Sports Complex"),
    "NSUT(West Campus)": (28.5940, 76.9094, "DPCC-6224595 NSUT Jaffarpur"),
    "SPM-SPC Talkatora Garden":
        (28.6218, 77.1945, "DPCC-6224525 Talkatora Garden"),
    "SBV Delhi Cantt": (28.5942, 77.1251, "DPCC-6227749 Cantonment Area"),
}

REGISTRY = os.path.join(_HERE, "data", "delhi_climatology.json.gz")

_cache = {"at": 0.0, "bundle": None}


def enabled() -> bool:
    return os.environ.get(ENV_FLAG) == "1"


def _norm_text(s: str) -> str:
    return _html.unescape(re.sub(r"\s+", " ", s or "")).strip()


def station_links(index_html: str) -> list:
    """Index tree links -> [(b64, label)] in order, deduped."""
    seen, out = set(), []
    for b64, label in re.findall(
            r"stName=([A-Za-z0-9+/=]+)',\s*'\.\./images/tree-[^']*\.png',"
            r"'([^']+)'\]", index_html):
        if b64 not in seen:
            seen.add(b64)
            out.append((b64, _norm_text(label)))
    return out


def nav_links(page_html: str) -> list:
    """Nav-bar hrefs on a station page -> [(b64, label)] — catches the
    stations the index tree omits (IGNOU, JNU, ...)."""
    seen, out = set(), []
    for b64, label in re.findall(
            r"StationView5MinData\.php\?stName=([A-Za-z0-9+/=]+)\"?"
            r"[^>]*>([^<]+)</a>", page_html):
        if b64 not in seen:
            seen.add(b64)
            out.append((b64, _norm_text(label)))
    return out


def parse_station_page(page_html: str, now: Optional[float] = None) -> dict:
    """One station page -> {'ts': epoch|None, 'vals': {param: (value_µg/m³,
    src_unit)}, 'skipped': {...}}. Every row is unit-checked; stale or
    unparseable timestamps are counted, never guessed."""
    now = time.time() if now is None else now
    skipped = {"bad_ts": 0, "bad_value": 0, "unit_mismatch": 0,
               "stale": 0}
    vals = {}
    ts = None
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", page_html, re.S):
        cells = [re.sub(r"<[^>]+>", "", c) for c in
                 re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", row, re.S)]
        cells = [_norm_text(c) for c in cells]
        if len(cells) < 4:
            continue
        name, date_s, time_s, conc = cells[0], cells[1], cells[2], cells[3]
        for label, param, unit, factor, _fkey, rng in _PARAMS:
            if not name.startswith(label):
                continue
            if unit not in conc:
                skipped["unit_mismatch"] += 1
                break
            m = re.search(r"(-?\d+(?:\.\d+)?)", conc.replace(",", ""))
            if not m:
                skipped["bad_value"] += 1
                break
            v = float(m.group(1)) * factor
            if not (rng[0] <= v <= rng[1]):
                skipped["bad_value"] += 1
                break
            row_ts = _row_ts(date_s, time_s)
            if row_ts is None:
                skipped["bad_ts"] += 1
                break
            if now - row_ts > MAX_AGE_S:
                skipped["stale"] += 1
                break
            if ts is None or row_ts > ts:
                ts = row_ts
            # freshest row wins (pages list one snapshot anyway)
            vals[param] = (round(v, 2), unit, float(m.group(1)))
            break
    # PM2.5 is a subset of PM10 — pm25 > pm10 means a swapped or broken
    # row on their end (unit confusion), so the pm25 row is dropped and
    # counted rather than blended in (flatline-style QC like qc_stations
    # is the consumer's job; this is a hard physical constraint only).
    pm25, pm10 = vals.get("pm25"), vals.get("pm10")
    if pm25 is not None and pm10 is not None and pm25[0] > pm10[0] * 1.05:
        vals.pop("pm25")
        skipped["bad_value"] += 1
    return {"ts": ts, "vals": vals, "skipped": skipped}


def _row_ts(date_s: str, time_s: str) -> Optional[float]:
    """'Tuesday, October 06, 2026' + '21:40:00' IST -> epoch, else None."""
    try:
        d = datetime.strptime(date_s.strip(), "%A, %B %d, %Y").date()
        t = datetime.strptime(time_s.strip(), "%H:%M:%S").time()
        return datetime.combine(d, t, tzinfo=IST).timestamp()
    except ValueError:
        return None


def _resolve(label: str, registry: dict) -> Optional[tuple]:
    """DPCC label -> (lat, lon, provenance). Static map first, then
    registry normalization for a station the map predates."""
    hit = STATIONS.get(label)
    if hit:
        return hit[0], hit[1], hit[2]
    if registry:
        import ingest_cpcb  # shared normalizer/registry loader
        reg = registry.get(ingest_cpcb._norm_station(label))
        if reg:
            return reg[1], reg[2], f"registry:{reg[0]}"
    return None


def _registry():
    try:
        import ingest_cpcb
        return ingest_cpcb._registry()
    except Exception:  # noqa: BLE001 — fallback only; static map is primary
        return {}


def _blank_skip():
    return {"no_pm25": 0, "bad_value": 0, "bad_ts": 0, "stale": 0,
            "unit_mismatch": 0, "unresolved_coords": 0, "http_error": 0}


def _bundle_from_pages(pages: dict, now: float) -> dict:
    """{b64: (label, html)} -> stations+obs bundle rows (pre-status)."""
    registry = _registry()
    skipped = _blank_skip()
    stations, obs = [], []
    for b64, (label, page) in pages.items():
        if page is None:
            skipped["http_error"] += 1
            continue
        parsed = parse_station_page(page, now=now)
        for k in skipped:
            if k in parsed["skipped"]:
                skipped[k] += parsed["skipped"][k]
        pm = parsed["vals"].get("pm25")
        if pm is None:
            skipped["no_pm25"] += 1
            continue
        if parsed["ts"] is None:
            continue  # bad_ts/stale already counted
        coord = _resolve(label, registry)
        if coord is None:
            skipped["unresolved_coords"] += 1
            continue
        lat, lon, prov = coord
        ts = parsed["ts"]
        ts_utc = datetime.fromtimestamp(ts, tz=timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ")
        for param, (v, unit, src_v) in parsed["vals"].items():
            obs.append({
                "station_id": b64, "name": label,
                "lat": lat, "lon": lon,
                "parameter": param, "value": v, "unit": "µg/m³",
                "src_value": src_v, "src_unit": unit,
                "ts": ts, "ts_utc": ts_utc, "coord_src": prov,
            })
        stations.append({"lat": lat, "lon": lon, "name": label,
                         "pm25": pm[0], "ts": ts, "station_id": b64})
    return {"stations": stations, "obs": obs, "skipped": skipped}


def _fetch_pages(client, links: list) -> dict:
    """Fetch every linked page (bounded parallel) -> {b64: (label, html)}.
    The nav bar is identical on every page, so nav_links() from ANY page
    completes the station set — one harvest pass, no recursion."""
    pages = {}

    def one(b64_label):
        b64, label = b64_label
        for attempt in range(GET_ATTEMPTS):
            try:
                r = client.get(PAGE.format(b64), timeout=25, headers=_UA)
                if r.status_code == 200:
                    return b64, label, r.text
                if r.status_code < 500:
                    return b64, label, None   # 4xx is not transient
            except httpx.HTTPError:
                pass
            if attempt + 1 < GET_ATTEMPTS:
                time.sleep(BACKOFF_S)
        return b64, label, None

    with concurrent.futures.ThreadPoolExecutor(
            max_workers=PAGE_SEM) as ex:
        for b64, label, text in ex.map(one, links):
            pages[b64] = (label, text)
    return pages


def _all_links(client) -> "tuple[list, str]":
    """(links, error). Tree links from the index; union the nav-bar set
    from the FIRST fetched page so nav-only stations are never missed.
    Index failure returns the verbatim reason."""
    try:
        r = client.get(INDEX, timeout=25, headers=_UA)
        r.raise_for_status()
    except httpx.HTTPError as e:
        return [], f"{type(e).__name__}: {e}"[:160]
    links = station_links(r.text)
    if not links:
        return [], "index fetched but no stName links (page churn?)"
    # one probe page for the nav superset (tree may be a subset of nav)
    try:
        r = client.get(PAGE.format(links[0][0]), timeout=25, headers=_UA)
        if r.status_code == 200:
            extra = [bl for bl in nav_links(r.text)
                     if bl[0] not in {b for b, _ in links}]
            links += extra
            # reuse the already-fetched page — see fetch()
            _prefetched.update({links[0][0]: r.text})
    except httpx.HTTPError:
        pass  # nav superset is a bonus; tree links alone still work
    return links[:MAX_PAGES], ""


_prefetched: dict = {}


def fetch(client=None, now: Optional[float] = None) -> dict:
    """Pull live DPCC station obs into the airindex stations bundle.
    Cached for CACHE_TTL_S — caller may hit this every field refresh."""
    t0 = time.time()
    if not enabled():
        return {"status": "disabled", "source": SOURCE,
                "fetched_at": t0, "stations": [], "obs": [],
                "skipped": _blank_skip()}
    if _cache["bundle"] is not None and t0 - _cache["at"] < CACHE_TTL_S:
        return _cache["bundle"]
    own = client is None
    c = client or httpx.Client(timeout=httpx.Timeout(25.0, connect=8.0),
                               headers=_UA)
    try:
        links, err = _all_links(c)
        if not links:
            return {"status": f"unavailable: {err}", "source": SOURCE,
                    "fetched_at": time.time(), "stations": [], "obs": [],
                    "skipped": _blank_skip()}
        # the nav-probe page is already fetched — fold it in, don't
        # fetch it twice inside _fetch_pages
        pages = {}
        first = links[0][0]
        if first in _prefetched:
            pages[first] = (links[0][1], _prefetched.pop(first))
            rest = links[1:]
        else:
            rest = links
        pages.update(_fetch_pages(c, rest))
        b = _bundle_from_pages(pages, now or t0)
        out = {"status": "ok" if b["stations"] else
               "unavailable: no station rows survived parse",
               "source": SOURCE, "fetched_at": time.time(),
               "stations": b["stations"], "obs": b["obs"],
               "skipped": b["skipped"], "pages": len(pages)}
        if out["status"] == "ok":
            _cache["at"], _cache["bundle"] = time.time(), out
        return out
    finally:
        if own:
            c.close()


async def grab_async(client: httpx.AsyncClient,
                     now: Optional[float] = None) -> list:
    """airfield._grab_stations sibling — live DPCC stations as
    (lat, lon, name, {field-keyed vals}) rows for the IDW/_debias blend.
    pm25+pm10 plus whichever gases the page carries, all µg/m³.

    Shares the fetch() 15-min cache: the async path rides the same
    bundle (pages are fetched via httpx.AsyncClient when uncached).
    Returns [] without the flag or on any upstream failure."""
    if not enabled():
        return []
    if _cache["bundle"] is not None and \
            time.time() - _cache["at"] < CACHE_TTL_S:
        b = _cache["bundle"]
    else:
        try:
            r = await client.get(INDEX, timeout=25.0, headers=_UA)
            r.raise_for_status()
            links = station_links(r.text)
            if links:
                try:
                    r2 = await client.get(PAGE.format(links[0][0]),
                                          timeout=25.0, headers=_UA)
                    if r2.status_code == 200:
                        have = {b for b, _ in links}
                        links += [bl for bl in nav_links(r2.text)
                                  if bl[0] not in have]
                        _prefetched[links[0][0]] = r2.text
                except httpx.HTTPError:
                    pass
            if not links:
                return []
            sem = asyncio.Semaphore(PAGE_SEM)
            pages = {}

            async def one(b64_label):
                b64, label = b64_label
                if b64 in _prefetched:
                    pages[b64] = (label, _prefetched.pop(b64))
                    return
                async with sem:
                    for attempt in range(GET_ATTEMPTS):
                        try:
                            rr = await client.get(PAGE.format(b64),
                                                  timeout=25.0, headers=_UA)
                            if rr.status_code == 200:
                                pages[b64] = (label, rr.text)
                                return
                            if rr.status_code < 500:
                                pages[b64] = (label, None)
                                return  # 4xx is not transient
                        except httpx.HTTPError:
                            pass
                        if attempt + 1 < GET_ATTEMPTS:
                            await asyncio.sleep(BACKOFF_S)
                    pages[b64] = (label, None)

            await asyncio.gather(*(one(bl) for bl in links[:MAX_PAGES]))
            b = _bundle_from_pages(pages, now or time.time())
            if not b["stations"]:
                return []
            _cache["at"] = time.time()
            _cache["bundle"] = {"status": "ok", "source": SOURCE,
                                "fetched_at": time.time(),
                                "stations": b["stations"],
                                "obs": b["obs"],
                                "skipped": b["skipped"],
                                "pages": len(pages)}
            b = _cache["bundle"]
        except (httpx.HTTPError, ValueError):
            return []
    out = []
    by_station = {}
    for o in b["obs"]:
        by_station.setdefault(o["station_id"], {})[o["parameter"]] = \
            o["value"]
    names = {s["station_id"]: s for s in b["stations"]}
    for sid, params in by_station.items():
        st = names.get(sid)
        if st is None:
            continue
        vals = {}
        for pname, v in params.items():
            fkey = next((f for _l, p, _u, _f, f, _r in _PARAMS
                         if p == pname), None)
            if fkey is not None:
                vals[fkey] = round(float(v), 1)
        if vals:
            out.append((st["lat"], st["lon"], st["name"], vals))
    return out


def _reset_cache():  # tests only
    _cache["at"] = 0.0
    _cache["bundle"] = None
    _prefetched.clear()
