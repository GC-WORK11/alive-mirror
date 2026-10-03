"""Live concentration field for Delhi NCR.

Grid of sample points across NCR (Delhi + Noida + Gurugram + Ghaziabad +
Faridabad) fetched from the Open-Meteo air-quality API (CAMS model — free,
no key). Values are cached for 15 minutes. Query anywhere inside the NCR
bbox via inverse-distance-weighted interpolation.

Warm start: at import (and lazily inside refresh) AirField loads the
newest built air-index snapshot from data/field/snapshots — the local
mirror of s3://alive108-air/field/YYYY/MM/DD/HHmm.json.gz written by
ingest_worker (doc 05 §2). The snapshot serves pm25 (with its per-cell
kriging sigma) until a live refresh lands — freshest source wins, both
are honestly timestamped in status().

When CPCB station feeds are wired in (data.gov.in key pending), station
measurements get blended in with higher weight than the model grid.
"""
import asyncio
import glob
import gzip
import json
import math
import os
import time
from datetime import datetime
from typing import Optional

import httpx

OPEN_METEO = "https://air-quality-api.open-meteo.com/v1/air-quality"
METEO = "https://api.open-meteo.com/v1/forecast"
OPENAQ = "https://api.openaq.org/v3"
POLLUTANTS = ("pm2_5,pm10,nitrogen_dioxide,ozone,carbon_monoxide,"
              "sulphur_dioxide,ammonia,us_aqi,european_aqi,dust,"
              "aerosol_optical_depth")
CACHE_TTL = 900  # 15 min — CAMS updates hourly; shorter adds nothing

# --- snapshot serving (warm start from the built air index) ---------------
_HERE = os.path.dirname(os.path.abspath(__file__))
SNAPSHOT_DIR = os.path.join(_HERE, "data", "field", "snapshots")
STALE_AFTER_S = 45 * 60  # doc 05 §6: CloudWatch alarms on field age >45 min
_SNAP_COVER_KM = 3.0     # >this from every covered cell => out-of-coverage
_LOAD_SKEW_S = 120.0     # a file can't honestly post-date its own mtime (+NTP slop)
_IDX_BUCKET = 0.02       # deg (~2.2 km) — spatial-hash bucket for the warmed index
_LRU_MAX = 16384         # exact-key memo for value()/sigma() lookups
_KY = 110.6              # km per degree latitude (matches krige.py)
_KX = 99.4               # km per degree longitude at 28.6N (matches krige.py)

# Directional-IDW strength: a sample dead-upwind of the query counts up to
# ~1.45x, dead-downwind ~0.55x, scaled by wind speed (calm air => isotropic).
UPWIND_GAIN = 0.45
IDW_P = 2.0

# NCR bbox (lon/lat) shared with main.py
BBOX = (76.80, 28.20, 77.90, 28.95)

# Major CPCB/DPCC continuous stations — coordinates for provenance + to
# anchor the field at the places Delhi actually monitors. Values today
# come from the model grid; a CPCB key will swap in real measurements.
STATIONS = [
    {"name": "Anand Vihar", "lat": 28.6468, "lon": 77.3162},
    {"name": "Ashok Vihar", "lat": 28.6927, "lon": 77.1754},
    {"name": "Bawana", "lat": 28.7936, "lon": 77.0326},
    {"name": "Burari", "lat": 28.7265, "lon": 77.2010},
    {"name": "DTU", "lat": 28.7501, "lon": 77.1112},
    {"name": "Dwarka Sec-8", "lat": 28.5710, "lon": 77.0640},
    {"name": "ITO", "lat": 28.6315, "lon": 77.2426},
    {"name": "Jahangirpuri", "lat": 28.7328, "lon": 77.1708},
    {"name": "Lodhi Road", "lat": 28.5918, "lon": 77.2277},
    {"name": "Mandir Marg", "lat": 28.6364, "lon": 77.2015},
    {"name": "Narela", "lat": 28.8522, "lon": 77.0929},
    {"name": "Nehru Nagar", "lat": 28.5686, "lon": 77.2515},
    {"name": "Okhla Ph-2", "lat": 28.5308, "lon": 77.2813},
    {"name": "Patparganj", "lat": 28.6237, "lon": 77.3067},
    {"name": "Punjabi Bagh", "lat": 28.6692, "lon": 77.1316},
    {"name": "Pusa", "lat": 28.6396, "lon": 77.1691},
    {"name": "RK Puram", "lat": 28.5640, "lon": 77.1868},
    {"name": "Rohini", "lat": 28.7325, "lon": 77.1188},
    {"name": "Shadipur", "lat": 28.6516, "lon": 77.1474},
    {"name": "Sirifort", "lat": 28.5511, "lon": 77.2263},
    {"name": "Sonia Vihar", "lat": 28.7330, "lon": 77.2494},
    {"name": "Vivek Vihar", "lat": 28.6723, "lon": 77.3153},
    {"name": "Wazirpur", "lat": 28.6999, "lon": 77.1658},
    {"name": "Aya Nagar", "lat": 28.4706, "lon": 77.1317},
    {"name": "Noida Sec-125", "lat": 28.5440, "lon": 77.3220},
    {"name": "Sector 51 Gurugram", "lat": 28.4100, "lon": 77.0620},
    {"name": "Indirapuram Ghaziabad", "lat": 28.6427, "lon": 77.3741},
    {"name": "Nehru Stadium Faridabad", "lat": 28.3700, "lon": 77.3150},
]


def _grid_points() -> list:
    """Stations plus a coarse fill grid so unmonitored areas still get a value."""
    pts = [(s["lat"], s["lon"], s["name"]) for s in STATIONS]
    lats = [28.25, 28.40, 28.55, 28.70, 28.85]
    lons = [76.85, 77.05, 77.25, 77.45, 77.75]
    covered = set()
    for lat in lats:
        for lon in lons:
            # skip if within ~6km of a station — avoids redundant calls
            if any(abs(slat - lat) < 0.05 and abs(slon - lon) < 0.05 for slat, slon, _ in pts):
                continue
            key = (round(lat, 2), round(lon, 2))
            if key not in covered:
                covered.add(key)
                pts.append((lat, lon, None))
    return pts


_h3_mod = None


def _h3():
    """h3-py if installed (optional dep — snapshot grids may be H3 ids)."""
    global _h3_mod
    if _h3_mod is None:
        try:
            import h3 as _m
            _h3_mod = _m
        except Exception:  # noqa: BLE001 - absent or broken: g8 ids still work
            _h3_mod = False
    return _h3_mod or None


class AirField:
    def __init__(self) -> None:
        self._samples: list = []  # (lat, lon, name|None, {pollutant: ug/m3})
        self._fetched_at: float = 0.0
        self._wind: tuple = (0.0, 0.0)  # (speed km/h, FROM-direction deg)
        self._wx: dict = {}  # ambient weather for the safety layer
        self._source = "open-meteo/cams"
        self._station_count = 0  # live OpenAQ sensor readings blended in
        self._stations_src = None  # "openaq" | "waqi" — which feed filled them
        self._kalman: dict = {}  # station_id → [x, P] scalar Kalman state
        self._lock = asyncio.Lock()
        self._sigma: Optional[float] = None  # krige std-dev at last query
        # --- served snapshot (built air index; see load_snapshot) ----------
        self._snap: Optional[dict] = None      # decoded snapshot field dict
        self._snap_epoch: float = 0.0          # effective embedded build epoch
        self._snap_path: Optional[str] = None  # file it was loaded from
        self._snap_centers: list = []          # (lat, lon, cell) — decoded ids
        self._snap_bbox: Optional[tuple] = None  # (lon_min, lat_min, lon_max, lat_max)
        self._snap_sigma_cells: int = 0        # cells carrying an honest sigma
        self._snap_idx: Optional[dict] = None  # warmed spatial hash (bucket->cells)
        self._snap_idx_extent: tuple = (0, 0, 0, 0)  # bucket bounds for ring search
        self._load_warnings: int = 0           # corrupt/skipped snapshot files
        self._load_warn_names: list = []       # basenames of recent skips
        self._lru: dict = {}                   # exact-key memo: (lat,lon)->cell|None
        self._next_snap_scan: float = 0.0      # lazy reload gate inside refresh()

    def _smooth(self, key: str, lat: float, lon: float, v: float) -> float:
        """Scalar Kalman filter per station — instruments spike on a gust
        or a truck idling past; the field should track the sustained
        level, not the jitter. R inflated for low-cost sensors."""
        sid = f"{key}:{round(lat, 4)},{round(lon, 4)}"
        Q, R = 12.0, 60.0  # process noise / measurement noise µg²
        st = self._kalman.get(sid)
        if st is None:
            self._kalman[sid] = [v, R]
            return v
        x, P = st
        P += Q
        K = P / (P + R)
        x = x + K * (v - x)
        st[0], st[1] = x, (1 - K) * P
        return x

    async def refresh(self, client: httpx.AsyncClient, force: bool = False) -> None:
        # Warm start / upgrade scan: retry at most once per TTL — covers a
        # dir that appeared late, a failed first load, AND a fresher file
        # written by the ingest worker while we serve. load_snapshot is a
        # no-op when the winner is what we already hold, so rescanning a
        # loaded field costs one dir walk, never a re-decode.
        if time.time() >= self._next_snap_scan:
            self._next_snap_scan = time.time() + CACHE_TTL
            try:
                self.load_snapshot()
            except Exception:  # noqa: BLE001 - snapshot load never crashes
                pass
        if not force and time.time() - self._fetched_at < CACHE_TTL and self._samples:
            return
        async with self._lock:
            if not force and time.time() - self._fetched_at < CACHE_TTL and self._samples:
                return
            pts = _grid_points()
            sem = asyncio.Semaphore(10)
            results = []

            async def grab(lat, lon, name):
                async with sem:
                    try:
                        r = await client.get(OPEN_METEO, params={
                            "latitude": lat, "longitude": lon,
                            "current": POLLUTANTS,
                        })
                        r.raise_for_status()
                        cur = r.json().get("current", {})
                        if cur.get("pm2_5") is not None:
                            results.append((lat, lon, name, cur))
                    except httpx.HTTPError:
                        pass

            stations = await self._grab_openaq(client)
            await asyncio.gather(
                *(grab(lat, lon, name) for lat, lon, name in pts),
                self._grab_wind(client),
            )
            if results:
                self._samples = self._debias(results + stations)
                KF.fit(self._samples)
                self._station_count = len(stations)
                if stations:
                    self._source = (
                        f"{self._stations_src or 'openaq'}-stations"
                        "+open-meteo/cams")
                self._fetched_at = time.time()
                self._lru.clear()  # live layer may take over serving now

    def _debias(self, samples: list) -> list:
        """Spatially-varying de-bias of the model grid against instruments.

        CAMS systematically under-reads Delhi (tonight: DTU instrument 451
        vs model ~53). Left raw, model points drag interpolated estimates
        down between stations. For each real instrument we measure the
        model's local multiplicative bias b_i = inst / model_IDW(inst_loc),
        then scale every model sample by the IDW-smoothed b at its own
        location — a standard bias-correction pass. Model points keep
        their shape; instruments stay untouched. Skipped when the network
        is too thin to trust (<8 instruments or <10 model points)."""
        inst = [s for s in samples if set(s[3].keys()) == {"pm2_5"}]
        model = [s for s in samples if set(s[3].keys()) != {"pm2_5"}]
        if len(inst) < 8 or len(model) < 10:
            return samples

        def idw(lat, lon, pts, key):
            num = den = 0.0
            for slat, slon, _n, vals in pts:
                v = vals.get(key)
                if v is None:
                    continue
                d = math.hypot(slat - lat, slon - lon)
                if d < 1e-6:
                    return float(v)
                w = 1.0 / (d * d)
                num += w * float(v)
                den += w
            return num / den if den else None

        # model-only estimate at each instrument -> local bias ratio
        ratios = []
        for ilat, ilon, _n, vals in inst:
            m = idw(ilat, ilon, model, "pm2_5")
            if m and m > 5:
                b = float(vals["pm2_5"]) / m
                if 0.2 < b < 10:
                    ratios.append((ilat, ilon, b))
        if len(ratios) < 8:
            return samples

        out = []
        for slat, slon, name, vals in samples:
            if set(vals.keys()) == {"pm2_5"}:
                out.append((slat, slon, name, vals))
                continue
            num = den = 0.0
            for ilat, ilon, b in ratios:
                d = math.hypot(ilat - slat, ilon - slon)
                if d < 1e-6:
                    num, den = b, 1.0
                    break
                w = 1.0 / (d * d)
                num += w * b
                den += w
            b = min(6.0, max(0.5, num / den)) if den else 1.0
            adj = dict(vals)
            for k in adj:
                adj[k] = float(adj[k]) * b if isinstance(adj[k], (int, float)) else adj[k]
            out.append((slat, slon, name, adj))
        return out

    async def _grab_openaq(self, client: httpx.AsyncClient) -> list:
        """Real government CAAQMS readings via OpenAQ v3 (X-API-Key),
        WAQI (WAQI_API_KEY) as the fallback source of the same CPCB/DPCC
        instruments when OpenAQ yields nothing.

        The model grid interpolates between ~40 synthetic points; these are
        actual instruments measuring actual Delhi air right now. Each one
        enters the IDW with the station 3x weight and its real name, so
        near a working station the field follows the instrument, not the
        model. Returns [] without a key or on any API failure — the model
        field stands alone as before. self._stations_src records which
        feed actually contributed ('openaq'|'waqi'|None) so the field
        source label stays honest.
        """
        out: list = []
        key = os.environ.get("OPENAQ_API_KEY")
        if key:
            headers = {"X-API-Key": key}
            locations = []
            for attempt in range(3):
                try:
                    r = await client.get(f"{OPENAQ}/locations", headers=headers, params={
                        "bbox": f"{BBOX[0]},{BBOX[1]},{BBOX[2]},{BBOX[3]}",
                        "parameters_id": 2, "limit": 200,
                    })
                    if r.status_code == 429:
                        await asyncio.sleep(8 * (attempt + 1))
                        continue
                    r.raise_for_status()
                    locations = r.json().get("results", [])
                    break
                except httpx.HTTPError:
                    break      # fall through to the WAQI fallback below

            pm25_sensors: dict[int, dict] = {}  # sensorsId -> {"lat","lon","name"}
            for loc in locations:
                coords = loc.get("coordinates") or {}
                for s in loc.get("sensors", []):
                    if (s.get("parameter") or {}).get("id") == 2:
                        pm25_sensors[s["id"]] = {
                            "lat": coords.get("latitude"),
                            "lon": coords.get("longitude"),
                            "name": loc.get("name") or f"station {loc.get('id')}",
                            "loc_id": loc["id"],
                        }
            if pm25_sensors:

                loc_ids = sorted({v["loc_id"] for v in pm25_sensors.values()})
                sem = asyncio.Semaphore(12)

        async def latest(loc_id: int):
            async with sem:
                try:
                    for attempt in range(3):
                        r = await client.get(
                            f"{OPENAQ}/locations/{loc_id}/latest",
                            headers=headers, params={"limit": 100})
                        if r.status_code == 429:
                            await asyncio.sleep(6 * (attempt + 1))
                            continue
                        break
                    r.raise_for_status()
                    # multiple pm2.5 instruments can sit at one site (e.g.
                    # reference + low-cost) — keep the freshest reading
                    best: dict = {}
                    for m in r.json().get("results", []):
                        meta = pm25_sensors.get(m.get("sensorsId"))
                        v = m.get("value")
                        if meta and v is not None and 0 <= v <= 1500:
                            ts = (m.get("datetime") or {}).get("utc") or ""
                            if not best or ts > best["ts"]:
                                best = {"ts": ts, "meta": meta, "v": float(v)}
                    if best:
                        meta = best["meta"]
                        # Kalman-smooth the raw read — tracks the sustained
                        # level, damps instrument jitter/spikes
                        v = self._smooth("pm2_5", meta["lat"], meta["lon"], best["v"])
                        out.append((meta["lat"], meta["lon"], meta["name"],
                                    {"pm2_5": round(v, 1)}))
                except httpx.HTTPError:
                    pass

            await asyncio.gather(*(latest(l) for l in loc_ids))
        if out:
            self._stations_src = "openaq"
        else:
            # OpenAQ keyed-out/down — WAQI republishes the same CPCB/DPCC
            # instruments; same honesty rules (key absent or any failure
            # leaves out empty and the model field stands alone).
            try:
                import ingest_waqi
                rows = await ingest_waqi.grab_async(client)
            except Exception:  # noqa: BLE001 — adapter contract is [] anyway
                rows = []
            for slat, slon, sname, vals in rows:
                v = vals.get("pm2_5")
                if v is None:
                    continue
                v = self._smooth("pm2_5", slat, slon, v)
                out.append((slat, slon, sname, {"pm2_5": round(v, 1)}))
            if out:
                self._stations_src = "waqi"
        return out

    async def _grab_wind(self, client: httpx.AsyncClient) -> None:
        """Boundary-layer wind over NCR centre — drives the directional
        weighting below (air at a point arrives *from* upwind)."""
        try:
            r = await client.get(METEO, params={
                "latitude": 28.61, "longitude": 77.21,
                "current": "wind_speed_10m,wind_direction_10m,precipitation,visibility,temperature_2m,is_day",
                "forecast_days": 1,
            })
            cur = r.json().get("current", {})
            if cur.get("wind_speed_10m") is not None:
                self._wind = (float(cur["wind_speed_10m"]),
                              float(cur.get("wind_direction_10m") or 0.0))
            if cur:
                self._wx = {
                    "precip_mm": cur.get("precipitation"),
                    "visibility_m": cur.get("visibility"),
                    "temp_c": cur.get("temperature_2m"),
                    "is_day": cur.get("is_day"),
                }
        except httpx.HTTPError:
            pass

    def wind(self) -> dict:
        """Current boundary wind: speed km/h + the direction air comes FROM."""
        speed, from_deg = self._wind
        return {"speed_kmh": speed, "from_deg": from_deg,
                "factor": min(1.0, speed / 30.0)}

    def weather(self) -> dict:
        """Ambient conditions a rider feels: rain + fog/dust visibility —
        the safety half of 'safety first'."""
        return self._wx or {"precip_mm": None, "visibility_m": None,
                            "temp_c": None, "is_day": None}

    # ------------------------------------------------------------ snapshots
    # The built air index (airindex.build_field -> ingest_worker) lands as
    # gzip JSON under data/field/snapshots/YYYY/MM/DD/HHmm.json.gz — cells
    # keyed by H3-res8 or "g8:<lat>:<lon>" ids, each carrying pm25 + a
    # per-cell kriging sigma + lo/hi. Serving the newest usable snapshot
    # is strictly better than serving nothing until the first refresh.

    def _note_skip(self, path: str) -> None:
        self._load_warnings += 1
        self._load_warn_names.append(os.path.basename(path))
        del self._load_warn_names[:-8]

    @staticmethod
    def _decode_snap(blob: bytes) -> dict:
        return json.loads(gzip.decompress(blob).decode("utf-8"))

    @staticmethod
    def _snap_embedded(field: dict) -> Optional[float]:
        """Embedded generated-at epoch: built_epoch, then ISO stamps
        (generated_at / built_at). None when the file carries no stamp."""
        v = field.get("built_epoch")
        if isinstance(v, (int, float)):
            return float(v)
        for k in ("generated_at", "built_at"):
            v = field.get(k)
            if isinstance(v, (int, float)):
                return float(v)
            if isinstance(v, str):
                try:
                    return datetime.fromisoformat(
                        v.replace("Z", "+00:00")).timestamp()
                except ValueError:
                    continue
        return None

    @staticmethod
    def _cell_center(cid: str):
        """(lat, lon) of a cell id — g8: parses inline, h3 via h3-py."""
        if cid.startswith("g8:"):
            try:
                _g, la, lo = cid.split(":", 2)
                return float(la), float(lo)
            except (ValueError, IndexError):
                return None
        h3 = _h3()
        if h3 is None:
            return None
        try:
            fn = getattr(h3, "cell_to_latlng", None) or getattr(h3, "h3_to_geo")
            la, lo = fn(cid)
            return float(la), float(lo)
        except Exception:  # noqa: BLE001
            return None

    def load_snapshot(self, snapshot_root: Optional[str] = None,
                      warm: bool = True) -> dict:
        """Warm-start serving from the newest usable snapshot under `root`
        (default: data/field/snapshots). Never raises — a corrupt file is
        skipped with a warning count, never crashes the app.

        Selection is fully deterministic:
          candidates  — every *.json.gz under root, walked newest-mtime
                        first (path asc as the filesystem tie-break);
          skip rule   — undecodable / unusable files are counted in
                        status()["load_warnings"] and never win;
          winner      — max by (embedded_generated_at, mtime, path) where
                        embedded_generated_at is the snapshot's own
                        built_epoch/generated_at/built_at stamp, clamped
                        to <= mtime + 120 s (a file can't honestly claim
                        a build after its own write; skew covers NTP slop)
                        and defaulted to mtime when no stamp exists;
          early exit  — a snapshot is written after it is built, so an
                        unparsed file whose mtime + skew is already below
                        the best embedded stamp can no longer win.
        `warm` builds the bucketed spatial index (identical results,
        ~100x faster lookups); pass warm=False for the linear path.
        -> summary dict {"loaded", "path", "built_at", "cells", ...}.
        """
        out = {"loaded": False, "path": None, "candidates": 0,
               "warnings": self._load_warnings}
        root = snapshot_root or SNAPSHOT_DIR
        try:
            paths = glob.glob(os.path.join(root, "**", "*.json.gz"),
                              recursive=True)
        except Exception:  # noqa: BLE001
            return out
        cands = []
        for p in paths:
            try:
                cands.append((os.path.getmtime(p), p))
            except OSError:
                self._note_skip(p)
        cands.sort(key=lambda t: (-t[0], t[1]))
        out["candidates"] = len(cands)

        best_key = None   # (eff_epoch, mtime, path)
        best = None       # (path, field_dict, centers)
        for mtime, p in cands:
            # unparsed file can only win if mtime + skew >= best eff epoch
            if best_key is not None and mtime + _LOAD_SKEW_S < best_key[0]:
                break
            try:
                with open(p, "rb") as fh:
                    f = self._decode_snap(fh.read())
                if not isinstance(f.get("cells"), dict) or not f["cells"]:
                    raise ValueError("no cells")
            except Exception:  # noqa: BLE001 - corrupt: skip to next-newest
                self._note_skip(p)
                continue
            emb = self._snap_embedded(f)
            eff = mtime if emb is None else min(emb, mtime + _LOAD_SKEW_S)
            key = (eff, mtime, p)
            if best_key is not None and key <= best_key:
                continue
            centers = []
            for cid, c in f["cells"].items():
                if not isinstance(c, dict) or c.get("pm25") is None:
                    continue
                cc = self._cell_center(cid)
                if cc is not None:
                    centers.append((cc[0], cc[1], c))
            if not centers:
                self._note_skip(p)   # decodes but unservable (e.g. h3-less)
                continue
            best_key, best = key, (p, f, centers)

        out["warnings"] = self._load_warnings
        if best is None:
            return out
        path, field, centers = best
        if path == self._snap_path and best_key[0] == self._snap_epoch:
            out["already_current"] = True
            return out
        self._snap = field
        self._snap_path = path
        self._snap_epoch = best_key[0]
        self._snap_centers = centers
        g = field.get("grid") or {}
        bb = g.get("bbox")
        if isinstance(bb, (list, tuple)) and len(bb) == 4:
            self._snap_bbox = (float(bb[0]), float(bb[1]),
                               float(bb[2]), float(bb[3]))
        else:
            lats = [c[0] for c in centers]
            lons = [c[1] for c in centers]
            self._snap_bbox = (min(lons), min(lats), max(lons), max(lats))
        self._snap_sigma_cells = sum(
            1 for _la, _lo, c in centers if c.get("sigma") is not None)
        self._lru.clear()
        self._snap_idx = self._build_idx(centers) if warm else None
        out.update({"loaded": True, "path": path,
                    "built_at": field.get("built_at"),
                    "built_epoch": self._snap_epoch,
                    "grid": g.get("system"), "cells": len(centers)})
        return out

    def _build_idx(self, centers: list) -> dict:
        """Bucketed spatial hash over cell centers: exact nearest
        neighbour by branch-and-bound ring expansion — identical result
        to a linear scan, without the O(n) per lookup."""
        idx = {}
        imin = jmin = 10 ** 9
        imax = jmax = -10 ** 9
        for la, lo, c in centers:
            ib, jb = math.floor(la / _IDX_BUCKET), math.floor(lo / _IDX_BUCKET)
            imin, imax = min(imin, ib), max(imax, ib)
            jmin, jmax = min(jmin, jb), max(jmax, jb)
            idx.setdefault((ib, jb), []).append((la, lo, c))
        self._snap_idx_extent = (imin, imax, jmin, jmax)
        return idx

    def _snap_nearest(self, lat: float, lon: float):
        """-> (cell_dict, km) of the nearest covered cell center, or
        (None, inf). Exact nearest neighbour — the warmed index only
        changes the cost, never the answer."""
        centers = self._snap_centers
        if not centers:
            return None, float("inf")
        if self._snap_idx is None:  # unwarmed: linear scan, same answer
            best, bd = None, float("inf")
            for la, lo, c in centers:
                d = math.hypot((la - lat) * _KY, (lo - lon) * _KX)
                if d < bd:
                    bd, best = d, c
            return best, bd
        idx = self._snap_idx
        bi = math.floor(lat / _IDX_BUCKET)
        bj = math.floor(lon / _IDX_BUCKET)
        imin, imax, jmin, jmax = self._snap_idx_extent
        maxr = max(bi - imin, imax - bi, bj - jmin, jmax - bj) + 1
        best, bd = None, float("inf")
        r = 0
        while True:
            if best is not None:
                # every point in ring r sits >= (r-1)*bucket deg away on at
                # least one axis — past that, nothing left can beat `best`
                edge_km = (r - 1) * _IDX_BUCKET * _KX
                if edge_km > bd:
                    break
            elif r > maxr:
                break
            for di in range(-r, r + 1):
                dj_range = range(-r, r + 1) if di in (-r, r) else (-r, r)
                for dj in dj_range:
                    for la, lo, c in idx.get((bi + di, bj + dj), ()):  # noqa: B007
                        d = math.hypot((la - lat) * _KY, (lo - lon) * _KX)
                        if d < bd:
                            bd, best = d, c
            r += 1
        return best, bd

    def _cell_at(self, lat: float, lon: float):
        """Serving-cell lookup with an exact-key memo — strip sampling
        calls value()+sigma() at the same coords; both hit one lookup.
        None (cached too) outside coverage: >_SNAP_COVER_KM from every
        covered cell."""
        key = (lat, lon)
        if key in self._lru:
            return self._lru[key]
        cell, km = self._snap_nearest(lat, lon)
        cell = cell if km <= _SNAP_COVER_KM else None
        if len(self._lru) >= _LRU_MAX:
            self._lru.clear()
        self._lru[key] = cell
        return cell

    def _serving_snapshot(self) -> bool:
        """The snapshot serves while it's the freshest field we hold —
        before the first live refresh, or if it was built more recently
        than the last one. Live `_samples` win whenever they're fresher."""
        return bool(self._snap_centers) and (
            not self._samples or self._snap_epoch >= self._fetched_at)

    def _concentration(self, lat: float, lon: float, key: str) -> Optional[float]:
        """Advection-weighted IDW (p=2) over grid samples.

        Pure distance-IDW treats the field as static smoke. It isn't:
        air arriving at a point just came through the upwind side, so a
        sample upwind of the query is a better predictor of what a person
        breathes there than an equally distant downwind sample. We rotate
        each sample's bearing against the 10m wind vector and scale the
        IDW weight by the alignment (max +/- UPWIND_GAIN, zeroed in calm
        air). Named stations still count 3x."""
        if not self._samples:
            return None
        # kriged estimate + uncertainty when the variogram fit holds;
        # citizen traversals then update it Bayesianly — a corridor of
        # commutes sharpens the field where stations never reach
        kr = KF.estimate(lat, lon)
        if kr is not None and key == "pm2_5":
            mu, sd = kr
            # krige σ covers interpolation error only; every sample is a
            # model point or an instrument with its own noise — carry a
            # 12% instrument/model-error floor so bands stay honest where
            # the field is flat, not fake-tight
            sd = math.sqrt(sd * sd + (0.12 * mu) ** 2)
            ce = corridor_estimate(lat, lon)
            if ce is not None:
                c, csd, _n = ce
                # precision-weighted posterior (Gaussian update)
                var = 1.0 / (1.0 / (sd * sd) + 1.0 / (csd * csd))
                mu = (mu / (sd * sd) + c / (csd * csd)) * var
                sd = math.sqrt(var)
            self._sigma = sd
            return mu
        self._sigma = None
        speed_kmh, from_deg = self._wind
        wf = min(1.0, speed_kmh / 30.0)  # calm => isotropic
        wind_from_rad = math.radians(from_deg)
        num = 0.0
        den = 0.0
        for slat, slon, name, vals in self._samples:
            v = vals.get(key)
            if v is None:
                continue
            d = math.hypot(slat - lat, slon - lon)
            if d < 1e-6:
                return float(v)
            w = (3.0 if name else 1.0) / (d ** IDW_P)
            if wf > 0:
                # bearing from the query to the sample; a sample sitting on
                # the bearing the wind comes FROM is upwind of the query
                bearing = math.atan2(
                    (slon - lon) * math.cos(math.radians(lat)),
                    slat - lat)
                align = math.cos(bearing - wind_from_rad)
                w *= 1.0 + UPWIND_GAIN * align * wf
            num += w * float(v)
            den += w
        return num / den if den else None

    def value(self, lat: float, lon: float, pollutant: str = "pm2_5") -> Optional[float]:
        if self._serving_snapshot():
            # the built index carries pm25 only — other pollutants are
            # honestly uncovered (None), never interpolated into fiction
            if pollutant not in ("pm2_5", "pm25"):
                return None
            cell = self._cell_at(lat, lon)
            return float(cell["pm25"]) if cell is not None else None
        return self._concentration(lat, lon, pollutant)

    def sigma(self, lat: float, lon: float) -> Optional[float]:
        """Uncertainty (µg/m³ std-dev) of the last kriged read. None when
        the IDW fallback ran — no fake precision."""
        if self._serving_snapshot():
            cell = self._cell_at(lat, lon)
            if cell is None:
                return None   # out-of-coverage: no band, no fake precision
            s = cell.get("sigma")
            return float(s) if s is not None else None
        self._concentration(lat, lon, "pm2_5")
        return self._sigma

    def nearest_sample_km(self, lat: float, lon: float) -> float:
        if self._serving_snapshot():
            _c, km = self._snap_nearest(lat, lon)
            return km
        if not self._samples:
            return float("inf")
        return min(math.hypot(slat - lat, slon - lon) * 111.0
                   for slat, slon, _, _ in self._samples)

    def status(self) -> dict:
        serving = ("snapshot" if self._serving_snapshot()
                   else "live" if self._samples else "none")
        epoch = (self._snap_epoch if serving == "snapshot"
                 else self._fetched_at)
        age = round(time.time() - epoch) if epoch else None
        now = time.time()
        if serving == "live" and self._fetched_at:
            refresh_in = max(0, round(CACHE_TTL - (now - self._fetched_at)))
        elif serving == "snapshot" and self._next_snap_scan:
            refresh_in = max(0, round(self._next_snap_scan - now))
        else:
            refresh_in = None
        st = {
            "source": self._source,
            "samples": len(self._samples),
            "station_readings": self._station_count,
            "age_s": age,
            "refresh_in_s": refresh_in,
            "refresh_ttl_s": CACHE_TTL,
            "wind": self.wind(),
            "kriging": "on" if KF.on else "idw",
            # --- serving honesty (additive; keys above unchanged) --------
            "serving": serving,
            "stale": (age > STALE_AFTER_S) if age is not None else None,
            "stale_after_s": STALE_AFTER_S,
            "load_warnings": self._load_warnings,
            "load_warn_files": list(self._load_warn_names),
            "sigma_coverage": self._sigma_coverage(serving),
            "coverage": self._coverage(serving),
            "snapshot": ({
                "path": self._snap_path,
                "built_at": self._snap.get("built_at"),
                "built_epoch": self._snap_epoch,
                "grid": (self._snap.get("grid") or {}).get("system"),
                "cells": len(self._snap_centers),
            } if self._snap is not None else None),
        }
        return st

    def _sigma_coverage(self, serving: str):
        """Honest σ reporting: how much of the served field carries an
        uncertainty band. 'none' means value() answers with no honest
        precision — the caller must not imply one."""
        if serving == "snapshot":
            n = len(self._snap_centers)
            if not self._snap_sigma_cells:
                return "none"
            return ("full" if self._snap_sigma_cells == n
                    else f"partial:{self._snap_sigma_cells}/{n}")
        if serving == "live":
            return "per-query" if KF.on else "none"
        return "none"

    def _coverage(self, serving: str):
        """Bounds of the served field — outside these, value() is None.
        lon/lat bbox + the beyond-km rule that defines 'out'."""
        if serving == "snapshot" and self._snap_bbox is not None:
            w, s, e, n = self._snap_bbox
            return {"bbox": [w, s, e, n],
                    "out_beyond_km": _SNAP_COVER_KM,
                    "cells": len(self._snap_centers),
                    "sigma_cells": self._snap_sigma_cells}
        if serving == "live" and self._samples:
            lats = [p[0] for p in self._samples]
            lons = [p[1] for p in self._samples]
            return {"bbox": [min(lons), min(lats), max(lons), max(lats)],
                    "out_beyond_km": None,
                    "cells": len(self._samples),
                    "sigma_cells": None}
        return None


def grap_indicative(pm25: Optional[float]) -> dict:
    """Indicative GRAP stage from NCR PM2.5 (Delhi's emergency rules,
    CAQM). GRAP triggers are declared on AQI; these map the PM2.5 bands
    that correspond: I=poor air (~AQI 201-300), II=very poor (301-400),
    III=severe (401-450), IV=severe+ (>450). Labeled 'indicative' — the
    legal stage is CAQM's call, not ours."""
    if pm25 is None:
        return {"indicative_stage": None, "basis_pm25": None}
    stage = 4 if pm25 > 350 else 3 if pm25 > 250 else 2 if pm25 > 120 else 1 if pm25 > 90 else 0
    return {"indicative_stage": stage, "basis_pm25": round(pm25, 1),
            "note": "indicative only — legal GRAP stage is declared by CAQM"}


from krige import KF  # noqa: E402
from community import corridor_estimate  # noqa: E402

FIELD = AirField()

# Warm start: serve the newest built air-index snapshot until the first
# live refresh lands — best-effort, never raises; AIRFIELD_NO_SNAPSHOT=1
# disables (offline dev, tests that must see an empty field).
if os.environ.get("AIRFIELD_NO_SNAPSHOT") != "1":
    try:
        FIELD.load_snapshot()
    except Exception:  # noqa: BLE001 - load never crashes the app
        pass
