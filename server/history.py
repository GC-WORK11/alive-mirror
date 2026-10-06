"""Historical climatology for Delhi NCR air quality.

Loads server/data/delhi_climatology.json.gz produced by
server/history_builder.py from the OpenAQ public archive
(s3://openaq-data-archive/records/csv.gz — real measurements only).

The table holds, per station and per (month, hour-of-day IST) bucket,
p25 / median / p75 for pm2.5 plus pm10 and no2 where archived.

API:
    typical(lat, lon, month, hour, pollutant="pm25", stat="median")
        -> float µg/m³, interpolated over the 3 nearest stations that
        have that bucket (inverse-distance weighting, p=2). Falls back
        to the city-wide curve when no station covers the bucket.
    typical_band(lat, lon, month, hour, pollutant="pm25")
        -> {"p25":…, "median":…, "p75":…}
    diurnal_curve(lat, lon, date=None, pollutant="pm25")
        -> 24 hourly typical values for that month (for "leave later" plots)
    station_meta()
        -> station list with coverage (first/last data seen, years, buckets)
"""
import gzip
import json
import math
import os
from datetime import date as _date, datetime, timedelta, timezone
from typing import Optional

DATA_PATH = os.path.join(os.path.dirname(__file__), "data", "delhi_climatology.json.gz")

# OpenAQ archive parameter names; "pm25" is PM2.5.
POLLUTANTS = ("pm25", "pm10", "no2")

_db: Optional[dict] = None


def _load() -> dict:
    global _db
    if _db is None:
        with gzip.open(DATA_PATH, "rt", encoding="utf-8") as f:
            _db = json.load(f)
    return _db


def _stations() -> list:
    return _load()["stations"]


def _bucket(station: dict, pollutant: str, month: int, hour: int):
    """[p25, median, p75] for one station's (month, hour) cell, or None."""
    return (station.get("m", {})
            .get(str(month), {})
            .get(str(hour), {})
            .get(pollutant))


def _city_bucket(pollutant: str, month: int, hour: int):
    return (_load().get("city", {})
            .get(str(month), {})
            .get(str(hour), {})
            .get(pollutant))


def _nearest(lat: float, lon: float, k: int = 3) -> list:
    """k nearest climatology stations by great-circle-ish distance (km)."""
    def km(s):
        return math.hypot((s["lat"] - lat) * 111.0,
                          (s["lon"] - lon) * 111.0 * math.cos(math.radians(lat)))
    return sorted(_stations(), key=km)[:k]


def _interp(lat: float, lon: float, month: int, hour: int, pollutant: str, idx: int):
    """IDW (p=2) over up to 3 nearest stations that have the bucket.
    idx: 0=p25, 1=median, 2=p75. Falls back to city curve."""
    num = den = 0.0
    for s in _nearest(lat, lon, k=3):
        v = _bucket(s, pollutant, month, hour)
        if v is None or len(v) <= idx or v[idx] is None:
            continue
        d = math.hypot((s["lat"] - lat) * 111.0,
                       (s["lon"] - lon) * 111.0 * math.cos(math.radians(lat)))
        if d < 0.05:  # ~50 m — effectively at the station
            return float(v[idx])
        w = 1.0 / (d * d)
        num += w * v[idx]
        den += w
    if den:
        return num / den
    c = _city_bucket(pollutant, month, hour)
    if c is not None and len(c) > idx and c[idx] is not None:
        return float(c[idx])
    return None


def typical(lat: float, lon: float, month: int, hour: int,
            pollutant: str = "pm25", stat: str = "median") -> Optional[float]:
    """Typical (climatological median) pollutant µg/m³ for any NCR point.

    month: 1-12, hour: 0-23 IST. stat: "median" | "p25" | "p75".
    Returns None if the pollutant/bucket has no data at all."""
    if not 1 <= month <= 12:
        raise ValueError("month must be 1-12")
    if not 0 <= hour <= 23:
        raise ValueError("hour must be 0-23")
    idx = {"p25": 0, "median": 1, "p75": 2}[stat]
    return _interp(lat, lon, month, hour, pollutant, idx)


def typical_band(lat: float, lon: float, month: int, hour: int,
                 pollutant: str = "pm25") -> dict:
    """p25/median/p75 band around the typical value."""
    return {s: _interp(lat, lon, month, hour, pollutant, i)
            for s, i in (("p25", 0), ("median", 1), ("p75", 2))}


def diurnal_curve(lat: float, lon: float, date=None,
                  pollutant: str = "pm25") -> list:
    """24 hourly typical values (median) for the month containing `date`
    (default: today in IST). None fills a bucket only if the whole city
    has no data for it — in practice all buckets are finite."""
    if date is None:
        ist = timezone(timedelta(hours=5, minutes=30))
        month = datetime.now(ist).month
    elif isinstance(date, _date):
        month = date.month
    else:  # "YYYY-MM-DD" or "MM"
        month = int(str(date).split("-")[1] if "-" in str(date) else str(date))
    return [typical(lat, lon, month, h, pollutant) for h in range(24)]


def station_meta() -> list:
    """Station list with real coverage timestamps from the archive."""
    return [{
        "id": s["id"], "name": s["name"],
        "lat": s["lat"], "lon": s["lon"],
        "first_seen": s.get("first_seen"), "last_seen": s.get("last_seen"),
        "years": s.get("years", []),
        "buckets": s.get("buckets"),
    } for s in _stations()]


def summary() -> dict:
    """Artifact provenance + coverage for /health-style introspection."""
    db = _load()
    return {
        "source": db.get("source"),
        "generated_at": db.get("generated_at"),
        "stations": len(db["stations"]),
        "file": DATA_PATH,
        "pollutants": db.get("pollutants", list(POLLUTANTS)),
    }
