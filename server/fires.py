"""Stubble-fire layer + transport modifier — the October-November Delhi weapon.

Punjab/Haryana crop-residue burning contributes ~14-20% of Delhi PM2.5 on
Oct-Nov average and 50-75% on episode days (npj Clim. Atmos. Sci. 2025;
WRF-Chem, ES&T 2020). Fire belt is NW of Delhi; seasonal inflow is from NW —
the modifier downscales when prevailing wind is not from the NW quadrant.

Two real-data paths, both NASA FIRMS, zero fabricated detections:
- FIRMS_MAP_KEY present -> area API (VIIRS_SNPP_NRT, ~3h latency).
- no key -> the FIRMS public daily CSV snapshots, which are downloadable
  without a key (data/active_fire/*/csv/*_Global_24h.csv) for Suomi-NPP
  (N), NOAA-20 (N20), NOAA-21 (N21) and Terra+Aqua MODIS (T/A).
  NASA GIBS (gibs.earthdata.nasa.gov) serves the same detections as free
  no-key WMS tiles (MODIS_Terra_Thermal_Anomalies_Day etc.) for the map
  layer; the CSVs give the vector points directly so we don't have to
  sample raster tiles.
"""
import csv
import io
import os
import time
from datetime import datetime, timezone
from typing import Optional

import httpx

# Upwind fire belt NW of Delhi (Punjab/Haryana burns): W,S,E,N — drives the
# smoke modifier only.
FIRE_BELT_BBOX = (73.5, 28.5, 77.5, 31.5)
# /fires coverage: NCR + ~150km ring around Delhi centre (W,S,E,N).
RING_BBOX = (75.75, 27.20, 78.75, 30.05)
DELHI = (77.2090, 28.6139)  # lon, lat for wind check
CACHE_S = 6 * 3600           # task spec: 6h cache for the overlay

# Contribution mapping: index 1.0 ≈ typical ~15-20% share; episode days
# reach ~3.75× (50-75% vs ~20%). Fire counts are normalized against a
# documented baseline of ~80 detections/day in the belt during the season.
BASELINE_FIRES_48H = 160.0
MAX_MODIFIER = 3.75

# Public no-key FIRMS snapshots (rolling 24h global detections).
PUBLIC_CSVS = [
    ("suomi-npp-viirs-c2/csv/SUOMI_VIIRS_C2_Global_24h.csv", "VIIRS"),
    ("noaa-20-viirs-c2/csv/J1_VIIRS_C2_Global_24h.csv", "VIIRS"),
    ("noaa-21-viirs-c2/csv/J2_VIIRS_C2_Global_24h.csv", "VIIRS"),
    ("modis-c6.1/csv/MODIS_C6_1_Global_24h.csv", "MODIS"),
]
CSV_BASE = "https://firms.modaps.eosdis.nasa.gov/data/active_fire/"

SAT_NAME = {"N": "Suomi-NPP", "N20": "NOAA-20", "N21": "NOAA-21",
            "T": "Terra", "A": "Aqua", "SNPP": "Suomi-NPP"}
# VIIRS CSV confidence is a label; MODIS is a 0-100 number. Normalise to a
# score for consumers while keeping the raw value.
CONF_SCORE = {"low": 30, "nominal": 55, "high": 90}

_csv_client: Optional[httpx.AsyncClient] = None


def _big_client() -> httpx.AsyncClient:
    """Separate client for the multi-MB snapshot downloads — the shared one
    carries an 8s total timeout that a 5MB CSV can exceed."""
    global _csv_client
    if _csv_client is None or _csv_client.is_closed:
        _csv_client = httpx.AsyncClient(
            timeout=httpx.Timeout(45.0, connect=8.0),
            headers={"User-Agent": "delhi-air-108/0.1 (hackathon)"})
    return _csv_client


def _in_bbox(lat, lon, bbox):
    w, s, e, n = bbox
    return s <= lat <= n and w <= lon <= e


def _conf(conf_raw):
    """(raw_label, numeric_score) — VIIRS text label or MODIS percent."""
    try:
        v = float(conf_raw)
        return str(int(v)), int(v)
    except (TypeError, ValueError):
        label = str(conf_raw or "").strip().lower() or None
        return label, CONF_SCORE.get(label) if label else None


def _parse_rows(text, instrument):
    rows = []
    for x in csv.DictReader(io.StringIO(text)):
        if not x.get("latitude") or not x.get("longitude"):
            continue
        lat, lon = float(x["latitude"]), float(x["longitude"])
        if not _in_bbox(lat, lon, RING_BBOX):
            continue
        conf, score = _conf(x.get("confidence"))
        t = str(x.get("acq_time") or "").zfill(4)
        rows.append({
            "lat": lat, "lon": lon,
            "frp": float(x.get("frp") or 0),
            "satellite": SAT_NAME.get(str(x.get("satellite") or "").upper(),
                                      x.get("satellite")),
            "instrument": instrument,
            "confidence": conf, "confidence_score": score,
            "acq_date": x.get("acq_date"), "acq_time_utc": t,
            "daynight": x.get("daynight"),
            "belt": _in_bbox(lat, lon, FIRE_BELT_BBOX),
        })
    return rows


class FireField:
    def __init__(self) -> None:
        self._fires: Optional[list] = None     # row dicts, see _parse_rows
        self._fetched_at = 0.0
        self._wind_deg: Optional[float] = None
        self._status = "cold"
        self._source = None

    async def _refresh_keyed(self, client: httpx.AsyncClient, key: str) -> bool:
        """FIRMS area API (needs the free MAP_KEY). Belt-belt bbox only."""
        w, s, e, n = FIRE_BELT_BBOX
        url = f"https://firms.modaps.eosdis.nasa.gov/api/area/csv/{key}/VIIRS_SNPP_NRT/{w},{s},{e},{n}/1"
        r = await client.get(url)
        r.raise_for_status()
        rows = list(csv.DictReader(io.StringIO(r.text)))
        self._fires = [
            {"lat": float(x["latitude"]), "lon": float(x["longitude"]),
             "frp": float(x.get("frp") or 0),
             "satellite": SAT_NAME.get(str(x.get("satellite") or "").upper(),
                                       x.get("satellite")),
             "instrument": "VIIRS",
             "confidence": _conf(x.get("confidence"))[0],
             "confidence_score": _conf(x.get("confidence"))[1],
             "acq_date": x.get("acq_date"),
             "acq_time_utc": str(x.get("acq_time") or "").zfill(4),
             "daynight": x.get("daynight"), "belt": True}
            for x in rows if x.get("latitude") and x.get("longitude")
        ]
        self._source = "firms-api"
        return True

    async def _refresh_public(self) -> bool:
        """Key-free path: public FIRMS daily CSV snapshots over the
        NCR + ~150km ring. Multi-satellite, per-pixel satellite+confidence."""
        client = _big_client()
        all_rows, ok = [], 0
        for path, instrument in PUBLIC_CSVS:
            try:
                r = await client.get(CSV_BASE + path)
                r.raise_for_status()
                all_rows.extend(_parse_rows(r.text, instrument))
                ok += 1
            except httpx.HTTPError:
                continue  # one satellite's snapshot missing must not kill the layer
        if not ok:
            return False
        self._fires = all_rows
        self._source = "firms-public-csv"
        return True

    async def refresh(self, client: httpx.AsyncClient, force: bool = False) -> None:
        if not force and time.time() - self._fetched_at < CACHE_S and self._fires is not None:
            return
        key = os.environ.get("FIRMS_MAP_KEY")
        try:
            ok = await (self._refresh_keyed(client, key) if key
                        else self._refresh_public())
            if not ok:
                self._status = "upstream-error"
                return
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
        """Raw detection load in the NW burn belt vs seasonal baseline."""
        if not self._fires:
            return 0.0
        belt = [f for f in self._fires if f.get("belt")]
        return len(belt) / BASELINE_FIRES_48H

    def smoke_modifier(self) -> float:
        """City-wide PM2.5 multiplier in [1.0, MAX_MODIFIER]."""
        if self._status != "live" or not self._fires:
            return 1.0
        idx = self.fire_index()
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
             "geometry": {"type": "Point", "coordinates": [f["lon"], f["lat"]]},
             "properties": {k: f.get(k) for k in (
                 "satellite", "instrument", "confidence", "confidence_score",
                 "frp", "acq_date", "acq_time_utc", "daynight", "belt")}}
            for f in (self._fires or [])
        ]
        return {
            "type": "FeatureCollection",
            "features": feats,
            "metadata": {
                "count": len(feats),
                "source": self._source,
                "bbox_wsen": list(RING_BBOX),
                "status": self._status,
                "cache_s": CACHE_S,
                "age_s": round(time.time() - self._fetched_at) if self._fetched_at else None,
            },
        }

    def status(self) -> dict:
        return {"status": self._status,
                "source": self._source,
                "fires": len(self._fires or []),
                "belt_fires": len([f for f in (self._fires or []) if f.get("belt")]),
                "wind_deg": self._wind_deg,
                "modifier": self.smoke_modifier(),
                "age_s": round(time.time() - self._fetched_at) if self._fetched_at else None,
                # the feed's own fetch instant — 'as of' without
                # back-computing from age_s
                "fetched_at": (datetime.fromtimestamp(
                    self._fetched_at, tz=timezone.utc)
                    .isoformat(timespec="seconds")
                    if self._fetched_at else None)}


FIRES = FireField()
