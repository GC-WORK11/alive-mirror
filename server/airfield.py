"""Live concentration field for Delhi NCR.

Grid of sample points across NCR (Delhi + Noida + Gurugram + Ghaziabad +
Faridabad) fetched from the Open-Meteo air-quality API (CAMS model — free,
no key). Values are cached for 15 minutes. Query anywhere inside the NCR
bbox via inverse-distance-weighted interpolation.

When CPCB station feeds are wired in (data.gov.in key pending), station
measurements get blended in with higher weight than the model grid.
"""
import asyncio
import math
import time
from typing import Optional

import httpx

OPEN_METEO = "https://air-quality-api.open-meteo.com/v1/air-quality"
POLLUTANTS = "pm2_5,pm10,nitrogen_dioxide,ozone"
CACHE_TTL = 900  # 15 min — CAMS updates hourly; shorter adds nothing

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


class AirField:
    def __init__(self) -> None:
        self._samples: list = []  # (lat, lon, name|None, {pollutant: ug/m3})
        self._fetched_at: float = 0.0
        self._source = "open-meteo/cams"
        self._lock = asyncio.Lock()

    async def refresh(self, client: httpx.AsyncClient, force: bool = False) -> None:
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

            await asyncio.gather(*(grab(lat, lon, name) for lat, lon, name in pts))
            if results:
                self._samples = results
                self._fetched_at = time.time()

    def _concentration(self, lat: float, lon: float, key: str) -> Optional[float]:
        """IDW (p=2) over grid samples, weighting named stations 3x."""
        if not self._samples:
            return None
        num = 0.0
        den = 0.0
        for slat, slon, name, vals in self._samples:
            v = vals.get(key)
            if v is None:
                continue
            d = math.hypot(slat - lat, slon - lon)
            if d < 1e-6:
                return float(v)
            w = (3.0 if name else 1.0) / (d * d)
            num += w * float(v)
            den += w
        return num / den if den else None

    def value(self, lat: float, lon: float, pollutant: str = "pm2_5") -> Optional[float]:
        return self._concentration(lat, lon, pollutant)

    def nearest_sample_km(self, lat: float, lon: float) -> float:
        if not self._samples:
            return float("inf")
        return min(math.hypot(slat - lat, slon - lon) * 111.0
                   for slat, slon, _, _ in self._samples)

    def status(self) -> dict:
        return {
            "source": self._source,
            "samples": len(self._samples),
            "age_s": round(time.time() - self._fetched_at) if self._fetched_at else None,
        }


FIELD = AirField()
