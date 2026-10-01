"""Stubble-fire transport modifier — the October-November Delhi weapon.

Punjab/Haryana crop-residue burning contributes ~14-20% of Delhi PM2.5 on
Oct-Nov average and 50-75% on episode days (npj Clim. Atmos. Sci. 2025;
WRF-Chem, ES&T 2020). NASA FIRMS VIIRS NRT gives 375m fire detections
with <3h latency. Fire belt is NW of Delhi; seasonal inflow is from NW —
the modifier downscales when prevailing wind is not from the NW quadrant.

Needs FIRMS_MAP_KEY env var (free registration — see FIRMS_SETUP.md).
Without a key every function degrades to neutral; nothing is fabricated.
"""
import csv
import io
import os
import time
from typing import Optional

import httpx

# Upwind fire belt NW of Delhi (Punjab/Haryana burns): W,S,E,N
FIRE_BELT_BBOX = (73.5, 28.5, 77.5, 31.5)
DELHI = (77.2090, 28.6139)  # lon, lat for wind check
CACHE_S = 3 * 3600           # FIRMS NRT latency is ~3h; no point polling faster

# Contribution mapping: index 1.0 ≈ typical ~15-20% share; episode days
# reach ~3.75× (50-75% vs ~20%). Fire counts are normalized against a
# documented baseline of ~80 detections/day in the belt during the season.
BASELINE_FIRES_48H = 160.0
MAX_MODIFIER = 3.75


class FireField:
    def __init__(self) -> None:
        self._fires: Optional[list] = None     # [(lat, lon, frp)]
        self._fetched_at = 0.0
        self._wind_deg: Optional[float] = None
        self._status = "cold"

    async def refresh(self, client: httpx.AsyncClient, force: bool = False) -> None:
        key = os.environ.get("FIRMS_MAP_KEY")
        if not key:
            self._status = "no-key"
            return
        if not force and time.time() - self._fetched_at < CACHE_S and self._fires is not None:
            return
        w, s, e, n = FIRE_BELT_BBOX
        url = f"https://firms.modaps.eosdis.nasa.gov/api/area/csv/{key}/VIIRS_SNPP_NRT/{w},{s},{e},{n}/1"
        try:
            r = await client.get(url)
            r.raise_for_status()
            rows = list(csv.DictReader(io.StringIO(r.text)))
            self._fires = [
                (float(x["latitude"]), float(x["longitude"]),
                 float(x.get("frp") or 0))
                for x in rows if x.get("latitude") and x.get("longitude")
            ]
            w_r = await client.get("https://api.open-meteo.com/v1/forecast", params={
                "latitude": DELHI[1], "longitude": DELHI[0],
                "current": "wind_direction_10m",
            })
            w_r.raise_for_status()
            self._wind_deg = w_r.json().get("current", {}).get("wind_direction_10m")
            self._fetched_at = time.time()
            self._status = "live"
        except (httpx.HTTPError, KeyError, ValueError):
            self._status = "upstream-error"

    def fire_index(self) -> float:
        """Raw detection load vs seasonal baseline. 0 when no key/data."""
        if not self._fires:
            return 0.0
        return len(self._fires) / BASELINE_FIRES_48H

    def smoke_modifier(self) -> float:
        """City-wide PM2.5 multiplier in [1.0, MAX_MODIFIER]."""
        if self._status != "live" or not self._fires:
            return 1.0
        idx = self._fire_index()
        mod = 1.0 + min(idx, 1.0) * (MAX_MODIFIER - 1.0)
        # NW quadrant ~270-360°. Downscale linearly when wind isn't advecting
        # the burn plume toward Delhi (documented assumption, not magic).
        if self._wind_deg is not None:
            wd = self._wind_deg % 360
            in_quad = 270 <= wd <= 360
            if not in_quad:
                mod = 1.0 + (mod - 1.0) * 0.3
        return round(mod, 2)

    def fires_geojson(self) -> dict:
        feats = [
            {"type": "Feature",
             "geometry": {"type": "Point", "coordinates": [lon, lat]},
             "properties": {"frp": frp}}
            for lat, lon, frp in (self._fires or [])
        ]
        return {"type": "FeatureCollection", "features": feats}

    def status(self) -> dict:
        return {"status": self._status,
                "fires": len(self._fires or []),
                "wind_deg": self._wind_deg,
                "modifier": self.smoke_modifier(),
                "age_s": round(time.time() - self._fetched_at) if self._fetched_at else None}


FIRES = FireField()
