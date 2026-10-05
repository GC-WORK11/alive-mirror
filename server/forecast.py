"""Hourly PM2.5 forecast field + departure-time optimizer for Delhi NCR.

Extends airfield.py's live concentration field into the future. Fetches
the Open-Meteo hourly air-quality forecast (CAMS, 5 days = 120 hourly
slots) and hourly meteorology (boundary-layer height + 10 m wind) over
the same NCR grid, then applies a ventilation-based stagnation
correction. Each hourly lookup runs a bounded semi-Lagrangian
back-trajectory on the hour's 10 m wind — the model surface is sampled
where the arriving air parcel came from, so a moving plume reads as
moved smoke (capped at ADV_MAX_M, degrades to undisplaced when met is
missing). Query anywhere inside the NCR bbox via the same IDW scheme
as AirField (p=2, named stations weighted 3x).

Live-field anchor (r5): the forecast horizon is a model fetch — FIELD
has no future data, so refresh() must pull its own grids — but every
pm25() read is ANCHORED to the live field: delta = (live - corrected
model now), applied with exp(-h/ANCHOR_TAU_H) decay, so the forecast
starts at what the served field actually reports and relaxes toward raw
CAMS over ~9 h. The live value comes from airfield.FIELD — the same
freshness-honest serving layer the app reads (live pull or newest
snapshot, never a stale file path this module manages). A stale (>3 h)
or empty field contributes nothing — the raw model stands, honestly
flagged in status().

Real data only: every upstream failure degrades to None — nothing is
invented.
"""
import asyncio
import math
import time
from datetime import datetime, timedelta, timezone
from typing import Optional, Union

import httpx

from airfield import _grid_points, FIELD  # same NCR grid + the live field

AQ_API = "https://air-quality-api.open-meteo.com/v1/air-quality"
MET_API = "https://api.open-meteo.com/v1/forecast"
AQ_VARS = "pm2_5,pm10,nitrogen_dioxide"
MET_VARS = "boundary_layer_height,wind_speed_10m,wind_direction_10m"
FORECAST_DAYS = 5  # API gives 120 hourly slots starting 00:00 UTC today
CACHE_TTL = 1800  # 30 min — forecast cycles update ~hourly

# Live-anchor tuning. ANCHOR_TAU_H is the e-folding horizon of the
# nowcast correction — persistence information decays over ~6-12 h in
# air-quality nowcasting; at +9 h ~37% of the live-vs-model delta
# remains, by +24 h ~7% (CAMS seasonal skill takes over). Not measured —
# a documented, conservative choice. ANCHOR_MAX_AGE_S gates the live
# read: a served field older than the station-QC staleness rule
# (airindex.STALE_S = 3 h) must not bend the horizon — its truth has
# decayed.
ANCHOR_TAU_H = 9.0
ANCHOR_MAX_AGE_S = 3 * 3600

# pm25(live=...) / ForecastField(live=...) sentinel: the default live
# source is airfield.FIELD — pass None to disable, or a callable
# (lat, lon) -> pm25|None to inject (tests).
_FIELD_ANCHOR = object()

# Advection cap: the back-trajectory may reach at most this far upwind
# — ~the extent of the fetched NCR grid. 45 km at 15 m/s ≈ 50 min of
# transport; uncapped, +120 h horizons would look up air that "came
# from" hundreds of km outside the modeled region — displaced sampling
# would then just clip to grid edges and silently re-report edge
# values. The cap keeps the lookup inside the data we actually have;
# anything beyond it honestly samples the boundary instead of a point
# the model never covered.
ADV_MAX_M = 45_000.0
_DEG_M = 111_320.0  # metres per degree latitude (IUGG mean)


def _live_field_pm25(lat: float, lon: float) -> Optional[float]:
    """Current pm2_5 from the live field — only while FIELD's serving
    layer is fresh enough to anchor a forecast (age <= ANCHOR_MAX_AGE_S).
    Stale or empty -> None: an old truth must not bend the horizon.
    Best-effort, never raises — the forecast stands alone without it."""
    try:
        age = (FIELD.status() or {}).get("age_s")
        if age is None or age > ANCHOR_MAX_AGE_S:
            return None
        return FIELD.value(lat, lon, "pm2_5")
    except Exception:  # noqa: BLE001 - the anchor is strictly optional
        return None

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
    """Hourly forecast concentration field over the NCR grid.

    live: the nowcast anchor — default _FIELD_ANCHOR reads
    airfield.FIELD (the app's live field: freshest of live pull / newest
    snapshot). Pass None to serve the raw model horizon, or a callable
    (lat, lon) -> pm25|None to inject another truth source."""

    def __init__(self, live=_FIELD_ANCHOR) -> None:
        # per grid point: {"lat", "lon", "name", "t0": datetime,
        #                  "vars": {var: [120 hourly values]}}
        self._aq: list = []
        self._met: list = []
        self._fetched_at: float = 0.0
        self._lock = asyncio.Lock()
        self._live = _live_field_pm25 if live is _FIELD_ANCHOR else live

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

    # ---------- advection ----------

    def _advected_origin(self, lat: float, lon: float,
                         idx: int) -> tuple:
        """Where the air arriving at (lat,lon) at forecast hour `idx`
        left from — a one-step semi-Lagrangian back-trajectory.

        The met feed gives 10 m wind (m/s) and direction FROM which it
        blows (Open-Meteo convention). Air travels h*3600*ws metres
        along the TO-bearing, so the parcel's origin is that distance
        back along the same bearing. Sampled at the origin instead of
        the query point, the model surface translates with the wind —
        a plume advecting across the grid shows up as moved smoke, not
        a static smear.

        Degrades to (lat,lon) — i.e. the pre-existing undisplaced IDW —
        when met is missing, the slot is the current hour, or wind is
        ~calm. Displacement is capped at ADV_MAX_M so far-horizon slots
        never sample outside the fetched grid."""
        if not self._met:
            return lat, lon
        idx0 = self.hour_index(0)
        if idx0 is None or idx <= idx0:
            return lat, lon
        ws = self._idw(self._met, lat, lon, "wind_speed_10m", idx)
        wd = self._idw(self._met, lat, lon, "wind_direction_10m", idx)
        if ws is None or wd is None or ws < 0.3:  # ~calm: transport ≈ 0
            return lat, lon
        dist = min(ws * (idx - idx0) * 3600.0, ADV_MAX_M)
        to_rad = math.radians(wd + 180.0)  # FROM-bearing -> TO-bearing
        return (lat - dist * math.cos(to_rad) / _DEG_M,
                lon - dist * math.sin(to_rad)
                / (_DEG_M * math.cos(math.radians(lat))))

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

    def slot_index_at(self, when: datetime) -> Optional[int]:
        """Index of the hourly slot covering absolute `when` — past OR
        future — while the fetched run still holds it.

        hour_index() is the forecast-serving contract and refuses the
        past; this one exists for the archive's recorded-vs-model
        comparison, which reads the run's own stored slots for hours
        that already happened. Same array bounds, no forward gate."""
        t0 = self._t0()
        if t0 is None:
            return None
        target = when if when.tzinfo else when.replace(tzinfo=timezone.utc)
        idx = int((target - t0).total_seconds() // 3600)
        return idx if 0 <= idx < self._n_hours() else None

    def model_pm25_at(self, lat: float, lon: float,
                      hour_idx: int) -> Optional[float]:
        """The run's raw pm2.5 at slot `hour_idx` — base IDW x stagnation
        factor, NO live anchor, NO advection.

        Both of those are nowcast moves that only make sense pointing
        forward from 'now': the anchor needs a live field to bend toward,
        and _advected_origin degrades to the undisplaced point for any
        slot at or before the current hour anyway. What remains is the
        model's own stored value for that hour — the honest object to
        compare a recorded field against."""
        if not (0 <= hour_idx < self._n_hours()):
            return None
        base = self._idw(self._aq, lat, lon, "pm2_5", hour_idx)
        if base is None:
            return None
        factor = self.stagnation_factor(lat, lon, hour_idx)
        return base * (factor if factor is not None else 1.0)

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

    def _live_delta(self, lat: float, lon: float, idx: int,
                    live=_FIELD_ANCHOR) -> Optional[float]:
        """Nowcast correction for forecast slot `idx`:
        (live_pm25 - corrected_model_now) * exp(-(idx - idx0)/TAU).

        At the current-hour slot the correction is exact (pm25 returns
        the live value); it decays to ~7% by +24 h where CAMS skill
        dominates. -> delta µg/m³, or None when either side is missing —
        a forecast never invents an anchor."""
        fn = self._live if live is _FIELD_ANCHOR else live
        if fn is None or not self._aq:
            return None
        idx0 = self.hour_index(0)
        if idx0 is None or idx < idx0:
            return None
        try:
            lv = fn(lat, lon)
            lv = float(lv) if lv is not None else None
        except Exception:  # noqa: BLE001 - a bad live fn loses the anchor
            return None
        if lv is None:
            return None
        model_now = self._idw(self._aq, lat, lon, "pm2_5", idx0)
        if model_now is None:
            return None
        f0 = self.stagnation_factor(lat, lon, idx0)
        model_now *= f0 if f0 is not None else 1.0
        return (lv - model_now) * math.exp(-(idx - idx0) / ANCHOR_TAU_H)

    def pm25(self, lat: float, lon: float, when: Union[int, float, datetime],
             live=_FIELD_ANCHOR) -> Optional[float]:
        """Expected PM2.5 (µg/m³) at a future hour: IDW over the CAMS
        forecast grid x stagnation factor, plus the decaying live-field
        anchor (see _live_delta). None outside the horizon.
        If met data failed, the raw model value is returned uncorrected;
        if the live field is stale/absent, no anchor is applied —
        degraded, never invented. live= overrides the field's anchor
        source for this call (None disables)."""
        idx = self.hour_index(when)
        if idx is None:
            return None
        alat, alon = self._advected_origin(lat, lon, idx)
        base = self._idw(self._aq, alat, alon, "pm2_5", idx)
        sampled_at = (alat, alon)
        if base is None and (alat, alon) != (lat, lon):
            # displaced point left the grid — fall back to the
            # undisplaced sample rather than returning nothing
            base = self._idw(self._aq, lat, lon, "pm2_5", idx)
            sampled_at = (lat, lon)
        if base is None:
            return None
        factor = self.stagnation_factor(lat, lon, idx)
        v = base * (factor if factor is not None else 1.0)
        # the anchor must correct the PARCEL's air, not the query
        # point's: with advection on, base was sampled at the upwind
        # origin, so a query-point delta (model's bias at the
        # destination) would over-correct a genuinely different cell —
        # seen live: CP h+2..6 pinned to 0.0 while a 7.8 km/h westerly
        # displaced the origin ~15-30 km into cleaner model cells.
        delta = self._live_delta(sampled_at[0], sampled_at[1], idx, live)
        if delta is not None:
            corrected = v + delta
            if corrected <= 0.0:
                # non-physical, with two different honest resolutions:
                #  * idx <= idx0: the correction IS (essentially) the
                #    live reading — at the anchor hour corrected ==
                #    live, and a near-zero instrument is the truth.
                #  * idx > idx0: the anchor extrapolated a same-site
                #    hour-0 bias onto a small future signal past the
                #    physical floor — the correction lost skill, so
                #    serve the model's own number for that hour (real
                #    physics, stated basis), not a clamped literal 0.0.
                idx0 = self.hour_index(0) or 0
                if idx <= idx0:
                    return 0.0
                return v if v > 0.0 else None
            v = corrected
        return v

    def pollutant(self, lat: float, lon: float, when: Union[int, float, datetime],
                  key: str = "pm10") -> Optional[float]:
        """Same as pm25 for the other fetched variables (pm10, no2) —
        deliberately UNANCHORED: the served live field (snapshot layer)
        carries pm2_5 only, so there is no honest live truth to anchor
        these species to."""
        idx = self.hour_index(when)
        if idx is None:
            return None
        alat, alon = self._advected_origin(lat, lon, idx)
        v = self._idw(self._aq, alat, alon, key, idx)
        if v is None and (alat, alon) != (lat, lon):
            v = self._idw(self._aq, lat, lon, key, idx)
        return v

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

    def time_at(self, hour_idx: int) -> Optional[str]:
        """ISO start label for a forecast slot index, or None."""
        if not self._aq or not (0 <= hour_idx < self._n_hours()):
            return None
        return self._aq[0]["times"][hour_idx]

    def status(self) -> dict:
        return {
            "aq_points": len(self._aq),
            "met_points": len(self._met),
            "hours": self._n_hours(),
            "age_s": round(time.time() - self._fetched_at) if self._fetched_at else None,
            # the horizon fetch instant — 'as of' for days-ahead cards
            "fetched_at": (datetime.fromtimestamp(
                self._fetched_at, tz=timezone.utc)
                .isoformat(timespec="seconds")
                if self._fetched_at else None),
            # whether pm25 reads are anchored to the live field, and by
            # what — honest about which truth the horizon starts from
            "live_anchor": {
                "enabled": self._live is not None,
                "source": ("airfield.FIELD" if self._live is _live_field_pm25
                           else "custom" if self._live is not None else None),
                "tau_h": ANCHOR_TAU_H,
                "max_age_s": ANCHOR_MAX_AGE_S,
            },
        }


FORECAST = ForecastField()
