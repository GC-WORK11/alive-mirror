#!/usr/bin/env python3
"""Benchmark + validation — kriging kernels, C++ alive_core vs Python.

Heavy validation per docs/plan/08 phase-5 scope: leave-one-station-out
(LOSO) over the archived OpenAQ station climatology
(server/data/delhi_climatology.json.gz — station x month x hour-IST
[p25, median, p75] for ~125 NCR stations).

Implementations under test:

  py-krige      server/krige.py KrigeField            (numpy, legacy sigma)
  cpp-legacy    alive_core.KrigeField legacy_variance=True  (drop-in parity)
  cpp-corrected alive_core.KrigeField legacy_variance=False (exact error var)
  cpp-universal alive_core universal kriging, drift = [1, x_km, y_km]
                (linear trend in km coords — spatially varying, available
                at every target; a constant city-median covariate would
                duplicate the intercept and is singular)
  idw           airindex._idw p=2 baseline (the current fallback)

Metrics per (slice, impl): folds, MAE, RMSE, bias, coverage-95
(|err| <= 1.96 sigma), mean sigma, per-fold wall (mean/p95) and total.
A second table times the production refresh shape: one fit + estimate
over the full airindex fallback grid.

    cd server && PYTHONPATH=core/build:core:. \\
        .venv312/bin/python core/bench/bench_krige.py [--json out.json]
"""

import argparse
import gzip
import json
import os
import statistics
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
_SERVER = os.path.dirname(os.path.dirname(_HERE))
for _p in (_SERVER, os.path.join(_SERVER, "core"),
           os.path.join(_SERVER, "core", "build")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import airindex        # noqa: E402  _idw, _fallback_cells
import krige           # noqa: E402  production KrigeField

try:
    import alive_core  # noqa: E402
except ImportError:
    alive_core = None

CLIMATOLOGY = os.path.join(_SERVER, "data", "delhi_climatology.json.gz")

# month x hour-IST slices spanning the seasonal + diurnal regimes.
SLICES = [
    (1, 20,   "Jan 20:00 IST — deep winter evening"),
    (3, 13,   "Mar 13:00 IST — spring midday"),
    (5, 13,   "May 13:00 IST — summer afternoon"),
    (5, 20,   "May 20:00 IST — summer evening"),
    (8, 11,   "Aug 11:00 IST — monsoon midday"),
    (10, 19,  "Oct 19:00 IST — autumn evening"),
    (12, 8,   "Dec 08:00 IST — winter morning"),
]

BAND_Z = 1.96


def load_slice(doc, month, hour):
    """-> (names, lats, lons, z) for stations with a pm25 median here."""
    names, lats, lons, z = [], [], [], []
    for s in doc["stations"]:
        try:
            med = s["m"][str(month)][str(hour)]["pm25"][1]
        except KeyError:
            continue
        if med is None:
            continue
        names.append(s["name"])
        lats.append(float(s["lat"]))
        lons.append(float(s["lon"]))
        z.append(float(med))
    return names, lats, lons, z


def city_median(doc, month, hour):
    try:
        return float(doc["city"][str(month)][str(hour)]["pm25"][1])
    except KeyError:
        return None


_CP_LAT, _CP_LON = 28.61, 77.21   # Connaught Place — trend origin


def trend_drift(lat, lon):
    """Linear-trend universal-kriging drift row: [1, x_km, y_km]."""
    return [1.0, (lat - _CP_LAT) * 110.6, (lon - _CP_LON) * 99.4]


# ----------------------------------------------------------------- impls

def make_impls():
    """-> {name: (fit(train_lats,lons,z,drift)->obj, est(obj,lat,lon,f0)->(mu,sd))}"""
    impls = {}

    def py_fit(lats, lons, z, drift=None):
        samples = [(la, lo, "", {"pm2_5": v}) for la, lo, v in
                   zip(lats, lons, z)]
        return krige.KrigeField().fit(samples)

    def py_est(obj, la, lo, f0=None):
        out = obj.estimate(la, lo)
        return out if out is not None else None

    impls["py-krige"] = (py_fit, py_est)

    def idw_fit(lats, lons, z, drift=None):
        return list(zip(lats, lons, z))

    def idw_est(pts, la, lo, f0=None):
        v = airindex._idw(pts, la, lo)
        return (v, None) if v is not None else None

    impls["idw"] = (idw_fit, idw_est)

    if alive_core is not None:
        def cpp_fit(legacy):
            def f(lats, lons, z, drift=None):
                p = alive_core.KrigeParams()
                p.legacy_variance = legacy
                kf = alive_core.KrigeField()
                if not kf.fit(lats, lons, z, p):
                    return None
                return kf
            return f

        def cpp_est(obj, la, lo, f0=None):
            return obj.estimate(la, lo)

        impls["cpp-legacy"] = (cpp_fit(True), cpp_est)
        impls["cpp-corrected"] = (cpp_fit(False), cpp_est)

        def uk_fit(lats, lons, z, drift):
            p = alive_core.KrigeParams()
            p.legacy_variance = False
            kf = alive_core.KrigeField()
            if not kf.fit_universal(lats, lons, z, drift, p):
                return None
            return kf

        def uk_est(obj, la, lo, f0=None):
            return obj.estimate(la, lo, f0)

        impls["cpp-universal"] = (uk_fit, uk_est)

    return impls


# ------------------------------------------------------------------- LOSO

def loso_slice(doc, month, hour, impls):
    """Run leave-one-station-out over one (month, hour) slice."""
    names, lats, lons, z = load_slice(doc, month, hour)
    n = len(z)
    drift_all = [trend_drift(la, lo) for la, lo in zip(lats, lons)]

    out = {}
    for name, (fit, est) in impls.items():
        rows = []
        for i in range(n):
            tr_lats = lats[:i] + lats[i + 1:]
            tr_lons = lons[:i] + lons[i + 1:]
            tr_z = z[:i] + z[i + 1:]
            tr_drift = drift_all[:i] + drift_all[i + 1:]
            f0 = drift_all[i]
            t0 = time.perf_counter_ns()
            obj = fit(tr_lats, tr_lons, tr_z, tr_drift)
            t1 = time.perf_counter_ns()
            r = est(obj, lats[i], lons[i], f0) if obj is not None else None
            t2 = time.perf_counter_ns()
            rows.append({
                "held": names[i], "true": z[i],
                "fit_ns": t1 - t0, "est_ns": t2 - t1,
                "ok": r is not None,
                "mu": r[0] if r else None,
                "sd": r[1] if r and r[1] is not None else None,
            })
        errs = [row["mu"] - row["true"] for row in rows if row["ok"]]
        sds = [row["sd"] for row in rows if row["sd"] is not None]
        covered = [row for row in rows
                   if row["ok"] and row["sd"] is not None
                   and abs(row["mu"] - row["true"]) <= BAND_Z * row["sd"]]
        fold_ns = [row["fit_ns"] + row["est_ns"] for row in rows]
        out[name] = {
            "folds": len(rows),
            "n_ok": len(errs),
            "mae": statistics.fmean(abs(e) for e in errs) if errs else None,
            "rmse": (sum(e * e for e in errs) / len(errs)) ** 0.5
                    if errs else None,
            "bias": statistics.fmean(errs) if errs else None,
            "coverage95": len(covered) / len(rows) if rows else None,
            "mean_sigma": statistics.fmean(sds) if sds else None,
            "fold_ms_mean": statistics.fmean(fold_ns) / 1e6,
            "fold_ms_p95": sorted(fold_ns)[int(0.95 * len(fold_ns))] / 1e6,
            "wall_ms": sum(fold_ns) / 1e6,
            "rows": rows,
        }
    return n, out


def bench_grid(doc, impls):
    """Production refresh shape: fit once (fullest slice) + estimate the
    whole airindex fallback grid (~0.74 km2 cells over the NCR bbox)."""
    names, lats, lons, z = load_slice(doc, 5, 20)
    centers = [airindex.cell_center(c) for c in airindex._fallback_cells()]
    drift = [trend_drift(la, lo) for la, lo in zip(lats, lons)]
    out = {}
    for name, (fit, est) in impls.items():
        t0 = time.perf_counter_ns()
        obj = fit(lats, lons, z, drift)
        fit_ns = time.perf_counter_ns() - t0
        t1 = time.perf_counter_ns()
        n_ok = 0
        for (la, lo) in centers:
            f0 = trend_drift(la, lo) if name == "cpp-universal" else None
            if est(obj, la, lo, f0) is not None:
                n_ok += 1
        est_ns = time.perf_counter_ns() - t1
        out[name] = {"fit_ms": fit_ns / 1e6, "est_ms": est_ns / 1e6,
                     "cells": len(centers), "n_ok": n_ok,
                     "per_cell_us": est_ns / 1e3 / len(centers)}
    return out


# -------------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", help="write raw results JSON here")
    args = ap.parse_args()

    with gzip.open(CLIMATOLOGY) as f:
        doc = json.load(f)
    impls = make_impls()
    print(f"climatology: {len(doc['stations'])} stations, "
          f"source={doc['source'][:60]}")
    print(f"impls: {', '.join(impls)}")
    print(f"alive_core: {'yes' if alive_core else 'NO — C++ rows skipped'}\n")

    results = {"slices": {}, "grid": None}
    for month, hour, label in SLICES:
        n, res = loso_slice(doc, month, hour, impls)
        results["slices"][f"{month:02d}-{hour:02d}"] = {
            "label": label, "n_stations": n, "impls": res}
        print(f"## {label} — {n} stations, {n} folds per impl")
        hdr = (f"{'impl':<14} {'folds':>5} {'MAE':>7} {'RMSE':>7} "
               f"{'bias':>7} {'cov95':>6} {'meanσ':>7} "
               f"{'fold ms':>8} {'p95 ms':>8} {'wall ms':>9}")
        print(hdr)
        for name, r in res.items():
            cov = f"{r['coverage95']:.3f}" if r["coverage95"] is not None \
                else "  —"
            msig = f"{r['mean_sigma']:.1f}" if r["mean_sigma"] else "  —"
            mae = f"{r['mae']:.2f}" if r["mae"] is not None else "  —"
            rmse = f"{r['rmse']:.2f}" if r["rmse"] is not None else "  —"
            bias = f"{r['bias']:.2f}" if r["bias"] is not None else "  —"
            print(f"{name:<14} {r['n_ok']:>5} {mae:>7} "
                  f"{rmse:>7} {bias:>7} {cov:>6} "
                  f"{msig:>7} {r['fold_ms_mean']:>8.3f} "
                  f"{r['fold_ms_p95']:>8.3f} {r['wall_ms']:>9.1f}")
        print()

    # aggregate over every slice/fold — pooled errors + total wall
    print(f"## ALL SLICES — pooled")
    print(hdr)
    for name in impls:
        all_rows = []
        for blk in results["slices"].values():
            all_rows += blk["impls"][name]["rows"]
        errs = [r["mu"] - r["true"] for r in all_rows if r["ok"]]
        sds = [r["sd"] for r in all_rows if r["sd"] is not None]
        covered = [r for r in all_rows
                   if r["ok"] and r["sd"] is not None
                   and abs(r["mu"] - r["true"]) <= BAND_Z * r["sd"]]
        fold_ns = [r["fit_ns"] + r["est_ns"] for r in all_rows]
        cov = f"{len(covered)/len(all_rows):.3f}" if all_rows else "  —"
        mae = statistics.fmean(abs(e) for e in errs)
        rmse = (sum(e * e for e in errs) / len(errs)) ** 0.5
        bias = statistics.fmean(errs)
        msig = f"{statistics.fmean(sds):.1f}" if sds else "  —"
        print(f"{name:<14} {len(errs):>5} {mae:>7.2f} {rmse:>7.2f} "
              f"{bias:>7.2f} {cov:>6} {msig:>7} "
              f"{statistics.fmean(fold_ns)/1e6:>8.3f} "
              f"{sorted(fold_ns)[int(0.95*len(fold_ns))]/1e6:>8.3f} "
              f"{sum(fold_ns)/1e6:>9.1f}")
        results["all"] = results.get("all", {})
        results["all"][name] = {
            "folds": len(all_rows), "mae": mae, "rmse": rmse, "bias": bias,
            "coverage95": len(covered) / len(all_rows),
            "mean_sigma": statistics.fmean(sds) if sds else None,
            "fold_ms_mean": statistics.fmean(fold_ns) / 1e6,
            "wall_ms": sum(fold_ns) / 1e6}
    print()

    print("## Grid refresh — fit once on May-20:00 slice, estimate every "
          "fallback-grid cell")
    grid = bench_grid(doc, impls)
    results["grid"] = grid
    print(f"{'impl':<14} {'fit ms':>9} {'cells':>6} {'est ms':>9} "
          f"{'µs/cell':>9}")
    for name, g in grid.items():
        print(f"{name:<14} {g['fit_ms']:>9.3f} {g['cells']:>6} "
              f"{g['est_ms']:>9.1f} {g['per_cell_us']:>9.2f}")

    if args.json:
        raw = {"slices": {}, "grid": grid, "all": results["all"]}
        for key, blk in results["slices"].items():
            raw["slices"][key] = {
                "label": blk["label"], "n_stations": blk["n_stations"],
                "impls": {k: {kk: vv for kk, vv in v.items() if kk != "rows"}
                          for k, v in blk["impls"].items()}}
        with open(args.json, "w") as f:
            json.dump(raw, f, indent=1)
        print(f"\nwrote {args.json}")


if __name__ == "__main__":
    main()
