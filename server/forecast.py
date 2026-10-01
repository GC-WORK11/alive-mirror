"""Hourly PM2.5 forecast field + departure-time optimizer for Delhi NCR.

Extends airfield.py's live concentration field into the future. Fetches
the Open-Meteo hourly air-quality forecast (CAMS, 5 days = 120 hourly
slots) and hourly meteorology (boundary-layer height + 10 m wind) over
the same NCR grid, then applies a ventilation-based stagnation
correction. Query anywhere inside the NCR bbox via the same IDW scheme
as AirField (p=2, named stations weighted 3x).

Real data only: every upstream failure degrades to None — nothing is
invented.
"""
import asyncio
import math
import time
from datetime import datetime, timedelta, timezone
from typing import Optional, Union

import httpx

from airfield import _grid_points  # same NCR grid as the live field

AQ_API = "https://air-quality-api.open-meteo.com/v1/air-quality"
MET_API = "https://api.open-meteo.com/v1/forecast"
AQ_VARS = "pm2_5,pm10,nitrogen_dioxide"
MET_VARS = "boundary_layer_height,wind_speed_10m,wind_direction_10m"
FORECAST_DAYS = 5  # API gives 120 hourly slots starting 00:00 UTC today
CACHE_TTL = 1800  # 30 min — forecast cycles update ~hourly

# Stagnation correction.
#
# Ventilation coefficient VC = BLH x U (m^2/s) — the standard dispersion
# proxy used in Indian air-quality work and reported in IITM/IMD EWS
# bulletins (e.g. Sengupta et al., Atmos. Res. 2016; IMD ventilation
# index guidance). We rescale the model field by the ratio of reference
# to current ventilation:
#
#     factor = (BLH_REF x U_REF) / (BLH x max(U, U_FLOOR))
#            clamped to [FACTOR_MIN, FACTOR_MAX]
#
# BLH_REF = 1000 m and U_REF = 3 m/s approximate a neutral, well-mixed
# Delhi daytime boundary layer, so factor = 1.0 there. A shallow stable
# layer (<400 m) with calm wind (<1.5 m/s) traps pollution -> factor >1;
# a deep/windy layer disperses it -> factor <1. U_FLOOR prevents
# division by zero on calm nights.
BLH_REF = 1000.0   # m
U_REF = 3.0        # m/s
U_FLOOR = 0.5      # m/s
FACTOR_MIN, FACTOR_MAX = 0.6, 2.5


def _parse_time(s: str) -> datetime:
    return datetime.fromisoformat(s).replace(tzinfo=timezone.utc)


class ForecastField:
    """Hourly forecast concentration field over the NCR grid."""

    def __init__(self) -> None:
        # per grid point: {"lat", "lon", "name", "t0": datetime,
        #                  "vars": {var: [120 hourly values]}}
        self._aq: list = []
        self._met: list = []
        self._fetched_at: float = 0.0
        self._lock = asyncio.Lock()

    # ---------- fetching ----------

    async def refresh(self, client: httpx.AsyncClient, force: bool = False) -> None:
        """Fetch both forecast grids. Two bulk requests total: Open-Meteo
        accepts comma-separated lat/lon and returns one JSON array."""
        if not force and time.time() - self._fetched_at < CACHE_TTL and self._aq:
            return
        async with self._lock:
            if not force and time.time() - self._fetched_at < CACHE_TTL and self._aq:
                return
            pts = _grid_points()
            lats = ",".join(str(p[0]) for p in pts)
            lons = ",".join(str(p[1]) for p in pts)
            aq_task = client.get(AQ_API, params={
                "latitude": lats, "longitude": lons,
                "hourly": AQ_VARS, "forecast_days": FORECAST_DAYS,
            })
            met_task = client.get(MET_API, params={
                "latitude": lats, "longitude": lons,
                "hourly": MET_VARS, "forecast_days": FORECAST_DAYS,
                "wind_speed_unit": "ms",
            })
            try:
                aq_resp, met_resp = await asyncio.gather(aq_task, met_task)
            except httpx.HTTPError:
                return
            aq = self._parse_points(aq_resp, pts, AQ_VARS.split(","))
            met = self._parse_points(met_resp, pts, MET_VARS.split(","))
            if aq:
                self._aq = aq
                self._met = met  # met may legitimately be [] -> None factors
                self._fetched_at = time.time()

    @staticmethod
    def _parse_points(resp: httpx.Response, pts: list, keys: list) -> list:
        """Map the multi-location array back onto grid points. A single
        location returns a bare object instead of a list; error bodies
        ({"error": true, ...}) and missing hourly blocks are skipped."""
        try:
            resp.raise_for_status()
            payload = resp.json()
        except (httpx.HTTPError, ValueError):
            return []
        if isinstance(payload, dict):
            payload = [payload]
        if not isinstance(payload, list):
            return []
        out = []
        for (lat, lon, name), entry in zip(pts, payload):
            if not isinstance(entry, dict):
                continue
            hourly = entry.get("hourly") or {}
            times = hourly.get("time") or []
            if not times:
                continue
            series = {}
            for k in keys:
                vals = hourly.get(k)
                if isinstance(vals, list) and len(vals) == len(times):
                    series[k] = vals
            if not series:
                continue
            out.append({"lat": lat, "lon": lon, "name": name,
                        "t0": _parse_time(times[0]),
                        "times": times, "vars": series})
        return out

    # ---------- spatial interpolation ----------

    @staticmethod
    def _idw(points: list, lat: float, lon: float, key: str, idx: int) -> Optional[float]:
        """IDW (p=2) over grid points at one forecast hour, 3x for stations."""
        num = den = 0.0
        for p in points:
            vals = p["vars"].get(key)
            if vals is None or idx >= len(vals):
                continue
            v = vals[idx]
            if v is None:
                continue
            d = math.hypot(p["lat"] - lat, p["lon"] - lon)
            if d < 1e-6:
                return float(v)
            w = (3.0 if p["name"] else 1.0) / (d * d)
            num += w * float(v)
            den += w
        return num / den if den else None

    # ---------- time indexing ----------

    def _t0(self) -> Optional[datetime]:
        return self._aq[0]["t0"] if self._aq else None

    def _n_hours(self) -> int:
        return len(self._aq[0]["times"]) if self._aq else 0

    def hour_index(self, when: Union[int, float, datetime]) -> Optional[int]:
        """Resolve `when` to an index into the hourly arrays.

        int/float = hours ahead of now; datetime = absolute (naive read
        as UTC). None outside the 120h forecast horizon.
        """
        t0 = self._t0()
        if t0 is None:
            return None
        now = datetime.now(timezone.utc)
        if isinstance(when, datetime):
            target = when if when.tzinfo else when.replace(tzinfo=timezone.utc)
        else:
            if when < 0:  # contract is a future hour 0-120h out
                return None
            target = now + timedelta(hours=float(when))
        # the array starts at 00:00 UTC today; past slots are not forecasts
        if target < now.replace(minute=0, second=0, microsecond=0):
            return None
        idx = int((target - t0).total_seconds() // 3600)
        return idx if 0 <= idx < self._n_hours() else None

    # ---------- public API ----------

    def stagnation_factor(self, lat: float, lon: float, hour_idx: int) -> Optional[float]:
        """Ventilation multiplier for the forecast hour, ~[0.6, 2.5].

        None when no met field is loaded or hour_idx is out of range;
        1.0 (neutral) when BLH or wind is missing at that hour — never
        invents a correction.
        """
        detail = self.stagnation_detail(lat, lon, hour_idx)
        return detail["factor"] if detail else None

    def stagnation_detail(self, lat: float, lon: float, hour_idx: int) -> Optional[dict]:
        """Factor plus its inputs and an `estimated` flag (True when BLH
        was missing and the neutral 1.0 was returned)."""
        if not self._met or not (0 <= hour_idx < self._n_hours()):
            return None
        blh = self._idw(self._met, lat, lon, "boundary_layer_height", hour_idx)
        wind = self._idw(self._met, lat, lon, "wind_speed_10m", hour_idx)
        if blh is None or wind is None:
            return {"factor": 1.0, "blh_m": blh, "wind_ms": wind,
                    "estimated": True}
        vc_ratio = (BLH_REF * U_REF) / (blh * max(wind, U_FLOOR))
        factor = min(FACTOR_MAX, max(FACTOR_MIN, vc_ratio))
        return {"factor": factor, "blh_m": round(blh, 1),
                "wind_ms": round(wind, 2), "estimated": False}

    def pm25(self, lat: float, lon: float, when: Union[int, float, datetime]) -> Optional[float]:
        """Expected PM2.5 (µg/m³) at a future hour: IDW over the CAMS
        forecast grid x stagnation factor. None outside the horizon.
        If met data failed, the raw model value is returned uncorrected
        (degraded, not invented)."""
        idx = self.hour_index(when)
        if idx is None:
            return None
        base = self._idw(self._aq, lat, lon, "pm2_5", idx)
        if base is None:
            return None
        factor = self.stagnation_factor(lat, lon, idx)
        return base * (factor if factor is not None else 1.0)

    def pollutant(self, lat: float, lon: float, when: Union[int, float, datetime],
                  key: str = "pm10") -> Optional[float]:
        """Same as pm25 for the other fetched variables (pm10, no2)."""
        idx = self.hour_index(when)
        if idx is None:
            return None
        return self._idw(self._aq, lat, lon, key, idx)

    def best_departure_window(self, lat: float, lon: float,
                              from_h: float, to_h: float) -> Optional[dict]:
        """3 lowest-PM2.5 hourly slots in [from_h, to_h) plus the worst.

        Powers "leave later, breathe X% less". Each slot: ISO start time,
        hour index, expected PM2.5, and the stagnation factor applied.
        None when the window has no usable forecast hours.
        """
        slots = []
        for h in range(int(from_h), int(to_h)):
            v = self.pm25(lat, lon, h)
            idx = self.hour_index(h)
            if v is None or idx is None:
                continue
            slots.append({
                "start": self._aq[0]["times"][idx],
                "hour_idx": idx,
                "hours_ahead": h,
                "pm25_ugm3": round(v, 1),
                "stagnation": (self.stagnation_factor(lat, lon, idx)),
            })
        if not slots:
            return None
        ordered = sorted(slots, key=lambda s: s["pm25_ugm3"])
        return {"best": ordered[:3], "worst": ordered[-1]}

    def status(self) -> dict:
        return {
            "aq_points": len(self._aq),
            "met_points": len(self._met),
            "hours": self._n_hours(),
            "age_s": round(time.time() - self._fetched_at) if self._fetched_at else None,
        }


FORECAST = ForecastField()
