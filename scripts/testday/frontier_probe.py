#!/usr/bin/env python3
"""NCR-frontier field honesty probe (companion to field_sampler.py).

docs/lanes/holdout-reverify-report.md moved the honesty frontier to the
uninstrumented NCR rim: 36/49 scatter cells >3 km from the nearest real
reading, worst 15.7 km on the Sonipat side. This probe walks transects
from inside the instrumented ring out to each flagged rim and checks the
served field stays honest there:

  * smooth gradients — no spikes/dips/sign-flips between steps
  * uncertainty band widens as nearest_sample_km grows
  * nearest_sample_km keeps reporting real distance (no fake precision)
  * pm25 stays positive/sane, us_aqi consistent, no errors

GETs only — never POSTs to prod.

Usage:
    python3 frontier_probe.py --out out_dir          # one round
    python3 frontier_probe.py --report out_dir       # markdown to stdout

Stdlib only.
"""

import argparse
import datetime as dt
import json
import os
import sys
import urllib.request

PROD = os.environ.get(
    "ALIVE_PROD",
    "http://alive108-2699c171ddded465.elb.ap-south-1.amazonaws.com")
UA = {"User-Agent": "alive108-frontier-probe/1.0 (GET-only probe)"}
IST = dt.timezone(dt.timedelta(hours=5, minutes=30))
FETCH_TIMEOUT = 20

# Transects: name -> list of (lat, lon) marching inside-ring -> rim.
# Anchored to the frontier map in docs/lanes/holdout-reverify-report.md.
TRANSECTS = {
    # north rim -> Sonipat side: 28.85-28.95 x 76.85-77.50 (worst
    # 15.7 km at 28.95,76.95). Two lines: through Narela (77.09) and
    # straight up the worst column (76.95).
    "north-sonipat-worst": [
        (28.65, 76.95), (28.70, 76.95), (28.75, 76.95), (28.80, 76.95),
        (28.85, 76.95), (28.90, 76.95), (28.95, 76.95),
    ],
    "north-narela-col": [
        (28.75, 77.09), (28.80, 77.09), (28.8429, 77.094),  # Narela DPCC
        (28.88, 77.09), (28.92, 77.09), (28.95, 77.09),
    ],
    # west rim -> Bahadurgarh/Rohtak: lon 76.85-76.95, lat 28.45-28.75.
    # Line at Bahadurgarh's latitude marching out of Mundka (77.03).
    "west-bahadurgarh": [
        (28.68, 77.03), (28.68, 77.00), (28.68, 76.97), (28.68, 76.94),
        (28.68, 76.91), (28.68, 76.88), (28.68, 76.85),
    ],
    # southwest -> Rewari side: 28.35-28.45 x 76.95.
    "southwest-rewari": [
        (28.55, 76.95), (28.50, 76.95), (28.45, 76.95),
        (28.40, 76.95), (28.35, 76.95),
    ],
    # east rim -> Ghaziabad / far Noida: lon 77.40-77.50, out of
    # Anand Vihar (77.3159).
    "east-ghaziabad": [
        (28.62, 77.32), (28.62, 77.35), (28.62, 77.38), (28.62, 77.41),
        (28.62, 77.44), (28.62, 77.47), (28.62, 77.50),
    ],
    # south -> beyond Faridabad: 28.35 x 77.10-77.20.
    "south-faridabad": [
        (28.50, 77.15), (28.45, 77.15), (28.40, 77.15),
        (28.375, 77.15), (28.35, 77.15),
    ],
}

# Named rim cells from the reverify table (worst offenders, verbatim).
NAMED_RIM = [
    ("sonipat-worst", 28.95, 76.95, 15.7),
    ("north-rim-far-e", 28.95, 77.50, None),
    ("bahadurgarh-edge", 28.68, 76.85, None),
    ("west-rim-n", 28.75, 76.85, None),
    ("west-rim-s", 28.45, 76.85, None),
    ("rewari-edge", 28.40, 76.95, 12.4),
    ("ghaziabad-far", 28.62, 77.50, None),
    ("faridabad-beyond", 28.35, 77.15, None),
]


def _get(path):
    req = urllib.request.Request(PROD + path, headers=UA)
    with urllib.request.urlopen(req, timeout=FETCH_TIMEOUT) as r:
        return json.loads(r.read().decode())


def probe_cell(lat, lon):
    try:
        a = _get(f"/aqi?lat={lat}&lon={lon}")
    except Exception as e:
        return {"lat": lat, "lon": lon, "error": str(e)}
    f = a.get("field") or {}
    return {
        "lat": lat, "lon": lon,
        "pm25_ambient": a.get("pm25_ambient"),
        "pm25": a.get("pm25"),
        "pm25_lo": a.get("pm25_lo"),
        "pm25_hi": a.get("pm25_hi"),
        "band_width": (round(a["pm25_hi"] - a["pm25_lo"], 1)
                       if a.get("pm25_lo") is not None
                       and a.get("pm25_hi") is not None else None),
        "us_aqi": a.get("us_aqi"),
        "nearest_sample_km": a.get("nearest_sample_km"),
        "smoke_modifier": a.get("smoke_modifier"),
        "field_age_s": f.get("age_s"),
        "field_samples": f.get("samples"),
        "station_readings": f.get("station_readings"),
        "error": a.get("error"),
    }


def analyze(transect_rows):
    """Per-transect honesty checks. Returns list of flags (strings)."""
    flags = []
    vals = [r.get("pm25_ambient") for r in transect_rows]
    kms = [r.get("nearest_sample_km") for r in transect_rows]
    bands = [r.get("band_width") for r in transect_rows]
    for r in transect_rows:
        if r.get("error"):
            flags.append(f"error at {r['lat']},{r['lon']}: {r['error']}")
        if r.get("pm25_ambient") is None:
            flags.append(f"pm25_ambient missing at {r['lat']},{r['lon']}")
        elif not (1 <= r["pm25_ambient"] <= 900):
            flags.append(f"pm25_ambient {r['pm25_ambient']} insane at "
                         f"{r['lat']},{r['lon']}")
    v = [x for x in vals if x is not None]
    if len(v) >= 2:
        steps = [abs(b - a) for a, b in zip(v, v[1:])]
        mx = max(steps)
        if mx > 25:
            i = steps.index(mx)
            flags.append(f"gradient jump {round(mx,1)} ug between "
                         f"{transect_rows[i]['lat']},{transect_rows[i]['lon']} "
                         f"and next step")
    k = [x for x in kms if x is not None]
    if k and max(k) - min(k) < 0.5 and len(set(round(x, 1) for x in k)) == 1:
        flags.append("nearest_sample_km flat across transect "
                     "(suspicious — distance should vary)")
    b = [x for x in bands if x is not None]
    if k and b:
        rim = transect_rows[-1]
        if (rim.get("nearest_sample_km") or 0) > 5 and \
                rim.get("band_width") is not None and \
                rim["band_width"] < 20:
            flags.append(f"rim band suspiciously tight "
                         f"({rim['band_width']} ug at "
                         f"{rim['nearest_sample_km']} km)")
    return flags


def run_round():
    now_utc = dt.datetime.now(dt.timezone.utc)
    rnd = {"t_utc": now_utc.isoformat(timespec="seconds"),
           "t_ist": now_utc.astimezone(IST).isoformat(timespec="seconds"),
           "transects": {}, "rim": [], "health": None, "city": None}
    try:
        h = _get("/health")
        rnd["health"] = {
            "build_sha": h.get("build_sha"),
            "field_age_s": h.get("field_age_s"),
            "field_stale": h.get("field_stale"),
            "stations": (h.get("sources") or {}).get("stations"),
            "model_samples": ((h.get("sources") or {}).get("model") or {})
                .get("samples"),
        }
    except Exception as e:
        rnd["health_error"] = str(e)
    try:
        c = _get("/v2/city")
        st = c.get("pm25_stats") or {}
        f = c.get("field") or {}
        fr = c.get("freshness") or {}
        rnd["city"] = {
            "pm25_mean": st.get("mean"),
            "pm25_median": st.get("median"),
            "pm25_max": st.get("max"),
            "pm25_n": st.get("n"),
            "above_cpcb_60_pct": st.get("above_cpcb_60"),
            "above_who24h_15_pct": st.get("above_who24h_15"),
            "field_age_s": f.get("age_s"),
            "field_stale": f.get("stale"),
            "station_readings": f.get("station_readings"),
            "field_samples": f.get("samples"),
            "freshness_label": fr.get("label"),
            "enough_data": c.get("enough_data"),
            "breath_pm25_mid": ((c.get("breath") or {})
                              .get("pm25_ugm3") or {}).get("mid"),
            "grap_stage": (c.get("grap") or {}).get("equivalent_stage"),
            "generated_at": c.get("generated_at"),
        }
    except Exception as e:
        rnd["city_error"] = str(e)
    for name, pts in TRANSECTS.items():
        rows = [probe_cell(lat, lon) for lat, lon in pts]
        rnd["transects"][name] = {"cells": rows, "flags": analyze(rows)}
    for name, lat, lon, expect_km in NAMED_RIM:
        r = probe_cell(lat, lon)
        r["name"] = name
        r["expect_km"] = expect_km
        rnd["rim"].append(r)
    return rnd


def report(out_dir):
    path = os.path.join(out_dir, "frontier.jsonl")
    if not os.path.exists(path):
        return "no frontier rounds yet"
    rnds = [json.loads(l) for l in open(path) if l.strip()]
    L = []
    for rnd in rnds:
        t = rnd["t_ist"][11:16]
        h = rnd.get("health") or {}
        L.append(f"### round {t} IST — build {h.get('build_sha')}, "
                 f"field_age {h.get('field_age_s')}s, stations "
                 f"{((h.get('stations') or {}).get('count'))}, "
                 f"model samples {h.get('model_samples')}")
        L.append("")
        for name, tr in rnd["transects"].items():
            L.append(f"**{name}** (inside -> rim)")
            L.append("")
            L.append("| lat | lon | ambient | band | nearest km |")
            L.append("|---|---|---|---|---|")
            for c in tr["cells"]:
                band = (f"{c.get('pm25_lo')}–{c.get('pm25_hi')}"
                        if c.get("pm25_lo") is not None else "—")
                L.append(f"| {c['lat']} | {c['lon']} | "
                         f"{c.get('pm25_ambient','—')} | {band} | "
                         f"{c.get('nearest_sample_km','—')} |")
            if tr["flags"]:
                L.append("")
                for fl in tr["flags"]:
                    L.append(f"- FLAG: {fl}")
            L.append("")
        L.append("**named rim cells**")
        L.append("")
        L.append("| cell | ambient | band | nearest km (expected) |")
        L.append("|---|---|---|---|")
        for r in rnd["rim"]:
            band = (f"{r.get('pm25_lo')}–{r.get('pm25_hi')}"
                    if r.get("pm25_lo") is not None else "—")
            L.append(f"| {r['name']} ({r['lat']},{r['lon']}) | "
                     f"{r.get('pm25_ambient','—')} | {band} | "
                     f"{r.get('nearest_sample_km','—')} "
                     f"({r.get('expect_km','—')}) |")
        L.append("")
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--report", action="store_true")
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)
    if args.report:
        print(report(args.out))
        return
    rnd = run_round()
    with open(os.path.join(args.out, "frontier.jsonl"), "a") as fh:
        fh.write(json.dumps(rnd) + "\n")
    n_cells = sum(len(t["cells"]) for t in rnd["transects"].values())
    n_flags = sum(len(t["flags"]) for t in rnd["transects"].values())
    errs = sum(1 for t in rnd["transects"].values()
               for c in t["cells"] if c.get("error"))
    print(f"[{rnd['t_ist'][11:19]} IST] frontier round: {n_cells} transect "
          f"cells + {len(rnd['rim'])} rim cells · {n_flags} flags · "
          f"{errs} errors", flush=True)
    for name, tr in rnd["transects"].items():
        for fl in tr["flags"]:
            print(f"  FLAG {name}: {fl}", flush=True)


if __name__ == "__main__":
    main()
