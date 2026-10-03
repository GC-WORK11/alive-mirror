"""Unit tests for the 15-min air index — fully synthetic, no network.

Every test injects the `inputs` bundle, so build_field() never touches
Open-Meteo/FIRMS/OpenAQ. Covers the doc-05 §2 contract: bbox coverage,
per-cell keys, QC (flatline / >5-sigma spike / staleness), honest bands,
deterministic serialization, per-source provenance with ages.

Run from repo root:   python3 -m pytest server/tests/test_airindex.py
or from server/:      python3 -m pytest tests/test_airindex.py
"""
import gzip
import json
import os
import sys
import time

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_HERE))          # server/ on sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(_HERE)))  # repo root

import airindex              # noqa: E402
import ingest_worker         # noqa: E402
import rollup                # noqa: E402

NOW = 1_780_000_000.0  # fixed epoch — deterministic ages


def _model_samples():
    """~96-point synthetic CAMS grid over the NCR bbox, N-S gradient."""
    out = []
    for i in range(12):
        for j in range(8):
            lat = 28.18 + j * 0.11
            lon = 76.80 + i * 0.10
            out.append({"lat": lat, "lon": lon, "name": None,
                        "pm25": 60.0 + 5.0 * j + 1.5 * i})
    return out


def _stations(now):
    """24 QC-clean stations (6x4) that read ~1.3x the local model —
    non-constant residuals so the kriging path actually fits — plus
    three planted bad actors."""
    import math as _m
    out = []
    k = 0
    for j in range(4):
        for i in range(6):
            lat = 28.25 + j * 0.20
            lon = 76.85 + i * 0.20
            v = 80.0 + 8.0 * j + 3.0 * i       # smooth, model-like shape
            # central hotspot so station-vs-model residuals vary enough
            # for KrigeField's variogram gate (sill >= 2) to fit
            v += 30.0 * _m.exp(-((lat - 28.60) ** 2 + (lon - 77.20) ** 2)
                               / 0.05)
            out.append({"name": f"Stn-{k:02d}", "lat": lat, "lon": lon,
                        "pm25": v, "ts": now - 300,
                        "series": [v - 2, v, v + 1]})
            k += 1
    out.append({"name": "Flatline-Stn", "lat": 28.55, "lon": 77.21,
                "pm25": 77.0, "ts": now - 120,
                "series": [77.0, 77.0, 77.0, 77.0]})
    out.append({"name": "Spike-Stn", "lat": 28.62, "lon": 77.30,
                "pm25": 2500.0, "ts": now - 60,
                "series": [95.0, 2500.0, 98.0]})
    out.append({"name": "Stale-Stn", "lat": 28.40, "lon": 77.10,
                "pm25": 88.0, "ts": now - 4 * 3600,
                "series": [80.0, 88.0]})
    return out


def _inputs(now=NOW, stations=None):
    st_list = _stations(now) if stations is None else stations
    return {
        "model": {"status": "ok", "source": "open-meteo/cams",
                  "fetched_at": now - 45, "samples": _model_samples()},
        "stations": {"status": "ok", "source": "openaq-v3",
                     "fetched_at": now - 120, "stations": st_list},
        "fires": {"status": "ok", "source": "nasa-firms-public-csv",
                  "fetched_at": now - 900, "modifier": 1.0,
                  "n_fires": 12, "belt_fires": 4},
        "met": {"status": "ok", "source": "open-meteo",
                "fetched_at": now - 60, "wind_ms": 2.5, "wind_deg": 315,
                "blh_m": 800.0, "vc_m2s": 2000.0},
    }


@pytest.fixture(scope="module")
def field():
    return airindex.build_field(now=NOW, inputs=_inputs())


# ------------------------------------------------------------- grid

def test_grid_covers_ncr_bbox(field):
    w, s, e, n = airindex.BBOX
    cells = field["cells"]
    assert len(cells) == field["grid"]["n_cells"] > 500
    assert field["grid"]["system"] in ("h3", "latlon-fallback")
    lats, lons = [], []
    for cid in cells:
        lat, lon = airindex.cell_center(cid)
        lats.append(lat)
        lons.append(lon)
        assert s - 0.01 <= lat <= n + 0.01
        assert w - 0.01 <= lon <= e + 0.01
    # coverage reaches every edge of the bbox, not just the middle
    assert min(lats) < s + 0.05 and max(lats) > n - 0.05
    assert min(lons) < w + 0.05 and max(lons) > e - 0.05


def test_cell_required_keys(field):
    for cid, c in field["cells"].items():
        for key in ("pm25", "lo", "hi", "n_stations_within_10km",
                    "nearest_station_km"):
            assert key in c, f"{cid} missing {key}"
        assert isinstance(c["n_stations_within_10km"], int)
        assert c["src"] in ("station", "model", "inferred")


# ------------------------------------------------------------- QC

def test_qc_drops_flatline_and_spike(field):
    dropped = field["qc"]["dropped"]
    assert "Flatline-Stn" in dropped["flatline"]
    assert "Spike-Stn" in dropped["spike"]
    assert "Stale-Stn" in dropped["stale"]
    assert field["qc"]["stations_raw"] == 27
    assert field["qc"]["stations_used"] == 24
    names = [s["name"] for s in field["stations"]]
    assert "Flatline-Stn" not in names and "Spike-Stn" not in names


def test_qc_stations_unit():
    stns = _stations(NOW)
    survivors, dropped = airindex.qc_stations(stns, None, NOW)
    assert len(survivors) == 24
    assert dropped["flatline"] == ["Flatline-Stn"]
    assert dropped["spike"] == ["Spike-Stn"]
    assert dropped["stale"] == ["Stale-Stn"]


# ------------------------------------------------------------- bands

def test_band_lo_le_pm25_le_hi(field):
    for cid, c in field["cells"].items():
        assert c["lo"] <= c["pm25"] <= c["hi"], cid
        assert c["pm25"] >= 0.0


def test_stations_anchor_cells(field):
    # a cell sitting on Stn-00 (28.25, 76.85) should report a nearby station
    best = min(field["cells"].values(),
               key=lambda c: c["nearest_station_km"] or 1e9)
    assert best["nearest_station_km"] < 1.0
    assert best["n_stations_within_10km"] >= 1


# ------------------------------------------------------------- codec

def test_serialize_roundtrip_byte_identical(field):
    b1 = airindex.serialize(field)
    again = airindex.deserialize(b1)
    b2 = airindex.serialize(again)
    assert gzip.decompress(b1) == gzip.decompress(b2)
    assert json.loads(gzip.decompress(b1))["grid"]["n_cells"] == \
        field["grid"]["n_cells"]


# ------------------------------------------------------------- provenance

def test_provenance_per_source_with_age(field):
    prov = field["provenance"]
    for src in ("model", "stations", "fires", "met"):
        assert src in prov
        assert prov[src]["label"] in ("model", "station", "inferred")
        assert isinstance(prov[src]["age_s"], int) and prov[src]["age_s"] >= 0
        assert prov[src]["source"]
        assert prov[src]["status"] == "ok"
    assert prov["stations"]["label"] == "station"
    assert prov["model"]["label"] == "model"


def test_stations_unavailable_no_key_explicit():
    inputs = _inputs()
    inputs["stations"] = {"status": "unavailable: no key",
                          "source": "openaq-v3", "fetched_at": NOW - 10,
                          "stations": []}
    f = airindex.build_field(now=NOW, inputs=inputs)
    assert "unavailable: no key" in f["provenance"]["stations"]["status"]
    assert f["qc"]["stations_used"] == 0
    assert f["grid"]["n_cells"] > 0  # model-only field still builds


# ------------------------------------------------------------- worker

def test_run_index_once_writes_local_snapshot(tmp_path, monkeypatch):
    monkeypatch.delenv("ALIVE_AIR_BUCKET", raising=False)
    res = ingest_worker.run_index_once(now=NOW, inputs=_inputs(),
                                       snapshot_root=str(tmp_path))
    assert res["ok"] and res["backend"] == "local"
    assert os.path.exists(res["snapshot"])
    assert res["snapshot"].endswith(".json.gz")
    snap = airindex.deserialize(open(res["snapshot"], "rb").read())
    assert snap["grid"]["n_cells"] == res["cells"]
    assert res["provenance_status"]["model"] == "ok"
    assert res["metrics"]["emitted"] is False  # no boto3/creds in tests


def test_handler_shape(monkeypatch, tmp_path):
    monkeypatch.setattr(ingest_worker, "run_index_once",
                        lambda **kw: {"ok": True, "cells": 3})
    out = ingest_worker.handler({}, None)
    assert out["statusCode"] == 200
    assert json.loads(out["body"])["ok"] is True


# ------------------------------------------------------------- rollup

def test_daily_rollup_from_snapshots(tmp_path, monkeypatch):
    monkeypatch.delenv("ALIVE_AIR_BUCKET", raising=False)
    # two synthetic snapshots an hour apart, same date
    day = time.strftime("%Y/%m/%d", time.gmtime(NOW))
    for hhmm, bias in (("1000", 0.0), ("1100", 20.0)):
        inputs = _inputs()
        for s in inputs["model"]["samples"]:
            s["pm25"] += bias
        f = airindex.build_field(now=NOW + (0 if hhmm == "1000" else 3600),
                                 inputs=inputs)
        p = tmp_path / day / f"{hhmm}.json.gz"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(airindex.serialize(f))
    date = day.replace("/", "-")
    ro = rollup.daily_rollup(date, snapshot_root=str(tmp_path),
                             daily_dir=str(tmp_path))
    assert ro["n_snapshots"] == 2
    assert ro["city"]["median_pm25"] is not None
    assert ro["city"]["ventilation_m2s"]
    cid = next(iter(ro["cells"]))
    cell = ro["cells"][cid]
    assert cell["max"] > cell["mean"] - 1e-6
    assert cell["worst_hours"] and isinstance(cell["worst_hours"][0], int)
    assert os.path.exists(ro["written_to"])


def test_loso_validation_on_field(field):
    res = rollup.loso_validation(field)
    assert res["status"] == "ok"
    assert res["n"] == 24
    assert res["mae_ugm3"] >= 0
    assert len(res["per_station"]) == 24
