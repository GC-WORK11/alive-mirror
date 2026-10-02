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
    # real instruments = openaq entries: named + only pm2_5 measured
    inst = [(i, s) for i, s in enumerate(samples)
            if s[2] is not None and set(s[3].keys()) == {"pm2_5"}]
    if len(inst) < 5:
        print(f"only {len(inst)} instrument readings — calibration skipped")
        return

    errs = []
    for idx, (slat, slon, name, vals) in inst:
        actual = float(vals["pm2_5"])
        keep = samples[:idx] + samples[idx + 1:]
        field._samples = keep
        est = field.value(slat, slon, "pm2_5")
        field._samples = samples
        if est is None:
            continue
        errs.append((name, actual, est))

    field._samples = samples

    abs_e = [abs(a - e) for _, a, e in errs]
    signed = [e - a for _, a, e in errs]
    pct = [abs(a - e) / a * 100 for _, a, e in errs if a > 5]
    rmse = math.sqrt(sum((a - e) ** 2 for _, a, e in errs) / len(errs))

    report = {
        "method": "leave-one-out over live OpenAQ instrument readings",
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
