"""Field calibration: leave-one-out cross-validation against real instruments.

Every OpenAQ station reading inside the field is an instrument measuring
actual Delhi air. Hold each one out, re-interpolate the field at its
location from the remaining samples, and compare — that is the honest
error a user sees between stations, not the zero error AT a station.

Run:  .venv312/bin/python calibrate.py
Writes: data/field_calibration.json (consumed by /meta for the writeup).
"""
import asyncio
import json
import math
import os
import statistics

import httpx

import airfield


async def main() -> None:
    field = airfield.FIELD
    async with httpx.AsyncClient(timeout=30) as client:
        await field.refresh(client, force=True)

    samples = field._samples
    # real instruments = the rows _grab_stations returned this refresh
    # (WAQI + flag-gated DPCC). Named sample-shape used to mark them
    # ('pm2_5'-only rows) but stations now carry every measured species,
    # and named model anchors (Bawana, ITO…) would sneak in on name
    # alone — so match on the fetched station coordinates instead.
    async with httpx.AsyncClient(timeout=30) as client:
        station_rows = await field._grab_stations(client)
    inst_xy = {(round(s[0], 4), round(s[1], 4)) for s in station_rows}
    inst = [(i, s) for i, s in enumerate(samples)
            if (round(s[0], 4), round(s[1], 4)) in inst_xy]
    if len(inst) < 5:
        print(f"only {len(inst)} instrument readings — calibration skipped")
        return

    errs = []
    for idx, (slat, slon, name, vals) in inst:
        actual = float(vals["pm2_5"])
        keep = samples[:idx] + samples[idx + 1:]
        field._samples = keep
        # the serve path is KF.estimate — refit without the held-out
        # instrument or the krige object still 'saw' it (the pre-DPCC
        # artifact measured exactly that: a LOO that held nothing out).
        airfield.KF.fit(keep)
        est = field.value(slat, slon, "pm2_5")
        field._samples = samples
        airfield.KF.fit(samples)
        if est is None:
            continue
        errs.append((name, actual, est))

    field._samples = samples
    airfield.KF.fit(samples)

    abs_e = [abs(a - e) for _, a, e in errs]
    signed = [e - a for _, a, e in errs]
    pct = [abs(a - e) / a * 100 for _, a, e in errs if a > 5]
    rmse = math.sqrt(sum((a - e) ** 2 for _, a, e in errs) / len(errs))

    report = {
        "method": "leave-one-out over live WAQI+DPCC instrument readings (krige refit per held-out station)",
        "n_stations": len(errs),
        "mae_ug": round(statistics.mean(abs_e), 1),
        "rmse_ug": round(rmse, 1),
        "median_abs_pct": round(statistics.median(pct), 1),
        "mean_bias_ug": round(statistics.mean(signed), 1),
        "note": "error between stations — at a station the field reads the instrument itself",
    }
    os.makedirs("data", exist_ok=True)
    with open("data/field_calibration.json", "w") as f:
        json.dump(report, f, indent=2)
    print(json.dumps(report, indent=2))
    worst = sorted(errs, key=lambda x: abs(x[1] - x[2]), reverse=True)[:5]
    for n, a, e in worst:
        print(f"  worst: {n:38s} actual {a:6.1f}  est {e:6.1f}")


if __name__ == "__main__":
    asyncio.run(main())
