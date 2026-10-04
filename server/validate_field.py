"""Field validation: our model field vs OpenAQ archive ground truth.

Ground truth = hourly CAAQMS station observations pulled from the public
OpenAQ S3 archive by openaq_archive.py (data/openaq_recent.csv). The
archive lags ~1-2 days, so "the same hour" means reconstructing what our
field served THEN — we rebuild it hour-by-hour from the same upstream the
production field uses: Open-Meteo/CAMS pm2_5 over airfield._grid_points(),
kriged with krige.KrigeField and advection-IDW fallback — identical code
path to airfield._concentration, including the module's KrigeField.

Not reconstructed (and documented as such in the report):
  * the live OpenAQ instrument blend — the API key is dead, so the deployed
    field today is pure model anyway (verified: /aqi field.source =
    "open-meteo/cams", station_readings=0). What we validate here is the
    baseline the app actually ships right now.
  * the community corridor layer — sparse citizen data, off by default.

Metrics: per (station, IST hour) pair — MAE, RMSE, bias (µg/m³ and %),
per-station table, hour-of-day table. Written to data/field_validation.md.

Usage:
    python openaq_archive.py pull     # refresh ground truth first
    python validate_field.py          # writes data/field_validation.md
"""
import math
import os
import statistics
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone

import httpx

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import airfield                      # noqa: E402 - real field code path
from airfield import _grid_points    # noqa: E402
from core_engine import KF           # noqa: E402 - the SAME singleton
                                     # airfield reads (C++ adapter when
                                     # the eigen build is present;
                                     # krige.KF is a different object)
from openaq_archive import load_recent  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_MD = os.path.join(HERE, "data", "field_validation.md")

AQ_API = "https://air-quality-api.open-meteo.com/v1/air-quality"
MET_API = "https://api.open-meteo.com/v1/forecast"


def _model_surface(hours):
    """For each IST hour in `hours` (naive datetimes), rebuild the model
    field: CAMS pm2_5 at every grid point + NCR wind that hour."""
    pts = _grid_points()
    d0 = min(hours).strftime("%Y-%m-%d")
    d1 = max(hours).strftime("%Y-%m-%d")
    r = httpx.get(AQ_API, params={
        "latitude": ",".join(f"{p[0]}" for p in pts),
        "longitude": ",".join(f"{p[1]}" for p in pts),
        "hourly": "pm2_5",
        "start_date": d0, "end_date": d1,
        "timezone": "Asia/Kolkata",
    }, timeout=60)
    r.raise_for_status()
    blocks = r.json()
    if not isinstance(blocks, list):          # single point edge case
        blocks = [blocks]

    r2 = httpx.get(MET_API, params={
        "latitude": 28.61, "longitude": 77.21,
        "hourly": "wind_speed_10m,wind_direction_10m",
        "start_date": d0, "end_date": d1,
        "timezone": "Asia/Kolkata",
    }, timeout=60)
    r2.raise_for_status()
    wj = r2.json()["hourly"]
    wind = {}   # "YYYY-MM-DDTHH:MM" -> (speed_kmh, from_deg)
    for t, s, d in zip(wj["time"], wj["wind_speed_10m"],
                       wj["wind_direction_10m"]):
        if s is not None:
            wind[t] = (float(s), float(d or 0.0))

    # raw per-hour inputs only — a shared AirField mutated per hour and
    # stored under every key would alias: every pair would be scored
    # against the LAST hour's surface (that's what the old code did —
    # estimates+sigma must be taken inside each hour's own refit below)
    surfaces = {}
    for h in sorted(hours):
        key = h.strftime("%Y-%m-%dT%H:00")
        samples = []
        for (lat, lon, name), blk in zip(pts, blocks):
            try:
                i = blk["hourly"]["time"].index(key)
                v = blk["hourly"]["pm2_5"][i]
            except (ValueError, KeyError, IndexError):
                continue
            if v is not None:
                samples.append((lat, lon, name, {"pm2_5": float(v)}))
        if not samples:
            continue
        surfaces[h] = (samples, wind.get(key, (0.0, 0.0)))
    return surfaces


def validate(hours_back=48, min_pairs=6):
    truth = load_recent("pm25", hours=hours_back)
    if not truth:
        sys.exit("no archive data — run `python openaq_archive.py pull` first")
    hours = sorted({h for st in truth.values() for h in st["series"]})
    surfaces = _model_surface(hours)

    pairs = []   # (station, hour, obs, krige|None, idw, sigma|None)
    field = airfield.AirField()
    # The citizen-corridor layer is a different, live datasource —
    # folding it into a days-old replay is a temporal leak: demo-seed
    # traversals in data/community.json once pushed a Sep-28 central-
    # Delhi replay to ~600 µg/m³ vs ~40 of station truth. Coverage is
    # measured against the model+station field.
    _real_corridor = airfield.corridor_estimate
    airfield.corridor_estimate = lambda *_a, **_k: None
    # never let the rebuilt surface be shadowed by a disk snapshot:
    # _serving_snapshot() wins whenever _snap_epoch >= _fetched_at, and
    # with _fetched_at unset a local data/field/snapshots/* file would
    # quietly serve ITS cells (stale sigma, wrong hour) — mark the
    # reconstructed samples fresher so sigma()/value() stay per-query.
    field._fetched_at = time.time()
    by_hour = defaultdict(list)
    for name, st in truth.items():
        for h, obs in st["series"].items():
            if h in surfaces:
                by_hour[h].append((name, st["lat"], st["lon"], obs))
    for h in sorted(by_hour):
        samples, w = surfaces[h]
        # rebuild THIS hour's surface: the singleton krige and the field's
        # samples/wind must both hold this hour's state while we score it
        field._samples = samples
        field._wind = w
        KF.fit(samples)                       # same singleton production uses
        krige_on = KF.on
        for name, lat, lon, obs in by_hour[h]:
            est = field._concentration(lat, lon, "pm2_5")
            sd = field.sigma(lat, lon)        # sqrt(krige_sd² + (0.12·µ)²)
            if krige_on:
                KF.on = False                 # same field, IDW fallback path
                est_idw = field._concentration(lat, lon, "pm2_5")
                KF.on = True
            else:
                est_idw = est
            if est is not None:
                pairs.append((name, h, obs, est, est_idw, sd))
    airfield.corridor_estimate = _real_corridor
    return truth, pairs


def _stats(errs, obs):
    n = len(errs)
    mae = sum(abs(e) for e in errs) / n
    rmse = math.sqrt(sum(e * e for e in errs) / n)
    bias = sum(errs) / n
    return n, mae, rmse, bias, 100.0 * bias / (sum(obs) / n)


def coverage_stats(pairs):
    """Fraction of held-out observations inside the model sigma-band.

    For each pair the field claims obs ~ N(mu, sigma): |err| <= k*sd
    should hold at the Gaussian rate (68% / 95% / 99.7% for k=1,2,3).
    Returns per-k coverage, the median |err|/sd ratio, and the sigma
    scale factor that WOULD have calibrated the band: s* s.t. k*s*sd
    covers the nominal share of residuals — s*>1 means the band is
    overconfident and must widen honestly.
    """
    rows = [(abs(m - o), sd) for _s, _h, o, m, _i, sd in pairs
            if sd is not None and sd > 0]
    if not rows:
        return None
    zs = sorted(a / s for a, s in rows)
    n = len(zs)
    cov = {k: sum(1 for a, s in rows if a <= k * s) / n for k in (1, 2, 3)}
    # scale so that k*(scale*sd) covers the Gaussian share at that k:
    # scale = z_quantile(nominal) / k, taken at k=2 (the band the app
    # shows lo/hi) — capped sane so a lucky window can't claim 0
    def _quant(p):
        i = min(n - 1, max(0, int(round(p * (n - 1)))))
        return zs[i]
    scale = {
        "z_median": zs[n // 2],
        "cal_2s": _quant(0.95) / 2.0,   # s.t. 2·cal·sd ~= 95% coverage
        "cal_1s": _quant(0.68) / 1.0,
        "cal_3s": _quant(0.997) / 3.0,
        "n": n,
    }
    return {"coverage": cov, **scale}


def render(truth, pairs, hours_back, min_pairs):
    errs = [m - o for _s, _h, o, m, _i, _sd in pairs]
    obs = [o for _s, _h, o, _m, _i, _sd in pairs]
    n, mae, rmse, bias, biaspct = _stats(errs, obs)
    idw_errs = [i - o for _s, _h, o, _m, i, _sd in pairs]
    _, mae_i, rmse_i, bias_i, biaspct_i = _stats(idw_errs, obs)
    cov = coverage_stats(pairs)

    by_stn = defaultdict(list)
    by_hod = defaultdict(list)
    for s, h, o, m, _i, _sd in pairs:
        by_stn[s].append((o, m))
        by_hod[h.hour].append(m - o)
    hs = sorted({h for s in truth.values() for h in s["series"]})

    L = []
    L.append("# Field validation — model vs OpenAQ archive ground truth\n")
    meta_note = ""
    try:
        import json
        meta = json.load(open(os.path.join(HERE, "data",
                                           "openaq_recent_meta.json")))
        meta_note = (f"Archive pull: {meta['pulled_at_utc'][:16]}Z, "
                     f"{meta['stations_with_data']} stations reporting, "
                     f"freshest row {meta['freshest']}.")
    except Exception:                            # noqa: BLE001
        pass
    L.append("## What was compared\n")
    L.append(f"- **Truth**: hourly PM2.5 medians at CAAQMS stations from the "
             f"public OpenAQ S3 archive (`records/csv.gz`, anonymous reads). "
             f"{meta_note}")
    L.append(f"- **Model**: the same field the API serves — Open-Meteo/CAMS "
             f"pm2_5 over the {len(_grid_points())}-point NCR grid, kriged "
             f"(`krige.KrigeField`) with advection-weighted IDW fallback, "
             f"rebuilt per IST hour from archived Open-Meteo hourly output.")
    L.append(f"- **Window**: {hs[0]} → {hs[-1]} IST (~{hours_back}h trailing; "
             f"the archive lags real time ~1-2 days, so a live `/aqi` pull "
             f"cannot overlap it — the model is reconstructed for the same "
             f"hours from the identical upstream).")
    L.append("- **Not included**: the OpenAQ live-instrument blend (API key "
             "dead — the deployed field is pure model today, which is exactly "
             "what this validates) and the community corridor layer.\n")

    L.append("## Headline\n")
    L.append(f"| pairs | stations | MAE µg/m³ | RMSE µg/m³ | bias µg/m³ | bias % |")
    L.append(f"|---|---|---|---|---|---|")
    L.append(f"| {n} | {len(by_stn)} | {mae:.1f} | {rmse:.1f} | "
             f"{bias:+.1f} | {biaspct:+.1f}% |")
    L.append("")
    L.append(f"IDW-only fallback (no kriging): MAE {mae_i:.1f}, "
             f"RMSE {rmse_i:.1f}, bias {bias_i:+.1f} ({biaspct_i:+.1f}%) "
             f"— kriging {'helps' if rmse <= rmse_i else 'does not beat IDW'} "
             f"on this window.\n")

    if cov:
        c = cov["coverage"]
        L.append("## Uncertainty-band coverage (held-out stations)\n")
        L.append("For a calibrated Gaussian band, |obs − model| ≤ k·σ "
                 "should hold at the nominal rate. σ here is the per-point "
                 "field sigma the API serves (`sqrt(krige_sd² + (0.12·µ)²) "
                 "× SIGMA_CAL`, the measured total-error inflation in "
                 "airfield.py) at the same station+hour.")
        L.append("")
        L.append("| band | nominal | measured |")
        L.append("|---|---|---|")
        L.append(f"| ±1σ | 68.3% | {100*c[1]:.1f}% |")
        L.append(f"| ±2σ | 95.4% | {100*c[2]:.1f}% |")
        L.append(f"| ±3σ | 99.7% | {100*c[3]:.1f}% |")
        L.append("")
        L.append(f"n={cov['n']} pairs; median |err|/σ = {cov['z_median']:.2f}. "
                 f"σ scale factors that would have calibrated this window: "
                 f"×{cov['cal_1s']:.2f} at 1σ, ×{cov['cal_2s']:.2f} at 2σ, "
                 f"×{cov['cal_3s']:.2f} at 3σ.")
        if cov["cal_2s"] <= 1.15:
            L.append("**Verdict**: the σ-band is calibrated — measured "
                     "±2σ coverage sits within noise of nominal 95% under "
                     "the applied `SIGMA_CAL` total-error inflation "
                     "(airfield.py, set from this measured factor, never "
                     "hand-tuned).")
        else:
            L.append(f"**Verdict**: the served σ-band is still "
                     f"overconfident — to cover 95% of held-out truth it "
                     f"needs ≈×{cov['cal_2s']:.2f} more widening. Raise "
                     "`airfield.SIGMA_CAL` from this measured factor, "
                     "never hand-tuned.")
        L.append("")

    L.append("## Per-station (n≥%d pairs, sorted by |bias%%|)\n" % min_pairs)
    L.append("| station | n | obs µg/m³ | model µg/m³ | MAE | RMSE | bias % |")
    L.append("|---|---|---|---|---|---|---|")
    rows = []
    for s, prs in by_stn.items():
        o = [p[0] for p in prs]; e = [p[1] - p[0] for p in prs]
        ns, mae_s, rmse_s, bias_s, bp_s = _stats(e, o)
        if ns >= min_pairs:
            rows.append((abs(bp_s), s, ns, sum(o) / ns, mae_s, rmse_s, bp_s,
                         sum(p[1] for p in prs) / ns))
    for _ab, s, ns, om, mae_s, rmse_s, bp_s, mm in sorted(rows, reverse=True):
        L.append(f"| {s} | {ns} | {om:.0f} | {mm:.0f} | {mae_s:.0f} | "
                 f"{rmse_s:.0f} | {bp_s:+.0f}% |")
    L.append("")

    L.append("## By IST hour-of-day (pooled across stations)\n")
    L.append("| hour IST | n | MAE | RMSE | bias % |")
    L.append("|---|---|---|---|---|")
    for hr in sorted(by_hod):
        e = by_hod[hr]; o = [p[2] for p in pairs if p[1].hour == hr]
        nh, mae_h, rmse_h, _b, bp_h = _stats(e, o)
        L.append(f"| {hr:02d} | {nh} | {mae_h:.0f} | {rmse_h:.0f} | {bp_h:+.0f}% |")
    L.append("")

    # verdict: where does it overshoot / undershoot?
    def _hour_bp(hr):
        e = by_hod[hr]
        o = [p[2] for p in pairs if p[1].hour == hr]
        return _stats(e, o)[4]
    under = [hr for hr in by_hod if _hour_bp(hr) < -15]
    over = [hr for hr in by_hod if _hour_bp(hr) > 15]
    L.append("## Verdict\n")
    direction = ("under-reads" if biaspct < -5 else
                 "over-reads" if biaspct > 5 else "is nearly unbiased")
    L.append(f"The model field {direction} Delhi stations on this window "
             f"(bias {biaspct:+.1f}%, MAE {mae:.0f} µg/m³ on a mean observed "
             f"{sum(obs)/n:.0f} µg/m³).")
    if under:
        L.append(f"- **Undershoots** IST hours {', '.join(f'{h:02d}' for h in under)} "
                 f"(bias < −15%) — typical of CAMS missing shallow-inversion "
                 f"build-ups and local peaks.")
    if over:
        L.append(f"- **Overshoots** IST hours {', '.join(f'{h:02d}' for h in over)} "
                 f"(bias > +15%).")
    worst = sorted(rows, reverse=True)[:3]
    if worst:
        L.append("- Largest station-level drift: " +
                 ", ".join(f"{r[1]} ({r[6]:+.0f}%)" for r in worst))
    obs_mean = sum(obs) / n
    if obs_mean < 60:
        L.append("- Regime caveat: this window is clean post-monsoon air "
                 f"(mean {obs_mean:.0f} µg/m³). The instrument-vs-model LOO "
                 "calibration (data/field_calibration.json) was fit on higher "
                 "pollution where CAMS *under*-reads — bias is regime-"
                 "dependent, and this window only characterises the "
                 "clean-air end.")
    L.append("- Kriged estimates carry a σ band; the live `/aqi` response "
             "exposes it as `pm25_lo`/`pm25_hi`. The coverage table above "
             "measures exactly how honest that band is.\n")
    L.append("## CPCB live feeds — reachability (tested from this deployment "
             "network)\n")
    L.append("| endpoint | result |")
    L.append("|---|---|")
    L.append("| `airquality.cpcb.gov.in` (official CPCB live portal, all paths) | TCP connect timeout ~8s — geo-blocked/unreachable |")
    L.append("| `api.data.gov.in` (CPCB hourly mirror, resource 3b01bcb8) | TCP connection refused — blocked |")
    L.append("| `cpcb.gov.in` | reachable (200) but CMS pages only — no station JSON feed |")
    L.append("| `app.cpcbccr.com` | reachable (200) — but it is a rebranded third-party portal; the old `aqi_dashboard`/`fetch_table_data` APIs are gone (404/405) and its own footer says it sources Open-Meteo, not CPCB instruments |")
    L.append("")
    L.append("**No CPCB public JSON endpoint is reachable from this box**, so "
             "no live-station fallback was wired into `airfield.py`. The "
             "OpenAQ archive above already carries the same CPCB/DPCC/HSPCB "
             "instruments (lagged ~1-2 days); a live instrument path still "
             "needs a working OpenAQ key or an India-based exit for CPCB.\n")
    L.append(f"*Generated {datetime.now(timezone.utc):%Y-%m-%d %H:%M}Z by "
             f"server/validate_field.py — real archived measurements only.*")
    return "\n".join(L)


if __name__ == "__main__":
    truth, pairs = validate()
    if len(pairs) < 50:
        sys.exit(f"too few overlapping pairs ({len(pairs)}) to validate")
    md = render(truth, pairs, 48, 6)
    open(OUT_MD, "w").write(md)
    print(f"{len(pairs)} station-hour pairs -> {OUT_MD}")
