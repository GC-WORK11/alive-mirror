#!/usr/bin/env python3
"""Oct-7 field-truth sampler (Lane A, docs/lanes/oct7-test-plan.md).

Samples the PROD /aqi field at 12 Delhi cells — each pinned to a live
DPCC continuous-monitoring station — and pulls the matching DPCC
real-time station pages as a HOLDOUT set (dpccairdata.com is not one
of our ingest sources, so field-vs-station is a genuine comparison).

Also pulls /v2/why each epoch to check the "stubble smoke" driver
claim against the actual wind (claim is honest iff fires.carrying is
true when a fires driver is listed).

GETs only — never POSTs to prod.

Usage:
    python3 field_sampler.py --once --out out_dir
    python3 field_sampler.py --loop --every-s 840 --minutes 60 --out out_dir
    python3 field_sampler.py --report out_dir   # markdown table to stdout

Stdlib only. No deps.
"""

import argparse
import base64
import datetime as dt
import json
import os
import re
import sys
import time
import urllib.request
import urllib.error

PROD = os.environ.get("ALIVE_PROD", "http://65.2.28.40")
DPCC_INDEX = "https://www.dpccairdata.com/dpccairdata/display/index.php"
DPCC_PAGE = ("https://www.dpccairdata.com/dpccairdata/display/"
             "AallStationView5MinData.php?stName={}")
IST = dt.timezone(dt.timedelta(hours=5, minutes=30))
UA = {"User-Agent": "alive108-field-truth-sampler/1.0 (GET-only probe)"}

# 12 cells = live DPCC stations, spread N→S + W→E across the NCR field.
# stName is base64 of the station slug exactly as index.php links it.
STATIONS = [
    # name (display)            b64 stName                     lat       lon
    ("Narela",                  "TmFyZWxh",                    28.8429, 77.0940),
    ("Pooth Khurd, Bawana",     "UG9vdGhLaHVyZEJhd2FuYQ==",    28.7768, 77.0510),
    ("Jahangirpuri",            "SmFoYW5naXJwdXJp",            28.7328, 77.1706),
    ("Rohini",                  "Um9oaW5pU2VjdG9yMTY=",        28.7431, 77.1166),
    ("Mundka",                  "TXVuZGth",                    28.6828, 77.0307),
    ("Punjabi Bagh",            "UHVuamFiaUJhZ2g=",            28.6683, 77.1167),
    ("Mandir Marg",             "TWFuZGlybWFyZw==",            28.6364, 77.2016),
    ("Major Dhyan Chand Nat. Stadium", "TmF0aW9uYWxTdGFkaXVt", 28.6120, 77.2372),
    ("Anand Vihar",             "QW5hbmRWaWhhcg==",            28.6469, 77.3159),
    ("Nehru Nagar",             "TmVocnVOYWdhcg==",            28.5676, 77.2503),
    ("R.K. Puram",              "UktQdXJhbQ==",                28.5633, 77.1869),
    ("Najafgarh",               "TmFqYWZnYXJo",                28.6137, 76.9855),
]

FETCH_TIMEOUT = 20


def _get(url, timeout=FETCH_TIMEOUT):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def get_json(path):
    return json.loads(_get(PROD + path).decode())


# ---------- DPCC parsing ----------

def dpcc_station_map():
    """index.php embeds the live station list as stName=<b64> links.
    Returns {b64: display_name} for every non-commented link."""
    html = _get(DPCC_INDEX).decode("utf-8", "replace")
    html = re.sub(r"<!--.*?-->", "", html, flags=re.S)
    found = re.findall(r"stName=([A-Za-z0-9+/=]+)'", html)
    out = {}
    for b64 in found:
        try:
            slug = base64.b64decode(b64).decode()
        except Exception:
            continue
        out[b64] = slug
    return out


_TD = re.compile(r"<td[^>]*>(.*?)</td>", re.S)


def dpcc_reading(b64):
    """Fetch one station's 5-min page; return newest PM2.5 + PM10 reads
    with their page timestamps. Page = flat <td> table:
    param | date | time(IST) | concentration | standard | remarks."""
    html = _get(DPCC_PAGE.format(b64)).decode("utf-8", "replace")
    cells = [re.sub(r"<[^>]+>", "", c).replace("&nbsp;", " ").strip()
             for c in _TD.findall(html)]
    cells = [c for c in cells if c]
    res = {"params": {}}
    m = re.search(r"Air Quality Monitoring Station\s*:\s*(.+)", html)
    if m:
        res["page_station"] = re.sub(r"<[^>]+>", "", m.group(1)).strip()
    for i, c in enumerate(cells):
        key = None
        if "Particulate Matter < 2.5" in c:
            key = "pm25"
        elif "Particulate Matter < 10" in c:
            key = "pm10"
        if key and key not in res["params"]:
            # next cells: date, time, concentration, standard
            tail = cells[i + 1:i + 5]
            conc = None
            when = None
            for j, t in enumerate(tail):
                v = re.search(r"(-?[\d.]+)\s*(?:&micro;|µ|u)?g/m3", t)
                if v and conc is None:
                    conc = float(v.group(1))
                if re.match(r"\d{2}:\d{2}:\d{2}", t):
                    when = t
            res["params"][key] = {"value": conc, "time_ist": when,
                                  "date": tail[0] if tail else None}
    return res


def dpcc_stale_minutes(reading, now_ist):
    """Minutes since the page's PM2.5 timestamp (today's date assumed —
    pages are 5-min cadence; a stale page still shows its last stamp)."""
    p = (reading.get("params") or {}).get("pm25") or {}
    ts = p.get("time_ist")
    if not ts:
        return None
    try:
        hh, mm, ss = (int(x) for x in ts.split(":"))
        stamp = now_ist.replace(hour=hh, minute=mm, second=ss,
                                microsecond=0)
        if stamp > now_ist:  # rolled past midnight
            stamp -= dt.timedelta(days=1)
        return round((now_ist - stamp).total_seconds() / 60, 1)
    except Exception:
        return None


# ---------- one epoch ----------

def sample_epoch(stations):
    """One full pass over prod cells + DPCC pages + /v2/why."""
    now_utc = dt.datetime.now(dt.timezone.utc)
    now_ist = now_utc.astimezone(IST)
    ep = {"t_utc": now_utc.isoformat(timespec="seconds"),
          "t_ist": now_ist.isoformat(timespec="seconds"), "cells": []}

    why = None
    try:
        why = get_json("/v2/why")
    except Exception as e:
        ep["why_error"] = str(e)
    if why:
        ev = why.get("evaluated", {})
        fires = ev.get("fires", {})
        driver_kinds = [d.get("kind") for d in why.get("drivers", [])]
        ep["why"] = {
            "line": why.get("line"),
            "drivers": driver_kinds,
            "fires_claimed": "fires" in driver_kinds,
            "carrying": fires.get("carrying"),
            "belt_fires": fires.get("belt_fires"),
            "n_fires": fires.get("n_fires"),
            "modifier": fires.get("modifier"),
            "feed_age_s": fires.get("feed_age_s"),
            "wind": why.get("wind"),
            "ventilation": ev.get("ventilation"),
            "trend": {k: ev.get("trend", {}).get(k)
                      for k in ("delta_ug", "span_h", "to_pm25")},
            "generated_at": why.get("generated_at"),
        }
        # honesty check: a fires driver claimed while wind does NOT
        # advect belt→Delhi (carrying=false) would be a misread
        ep["fires_claim_consistent"] = (
            not ep["why"]["fires_claimed"] or bool(fires.get("carrying")))

    for name, b64, lat, lon in stations:
        cell = {"station": name, "lat": lat, "lon": lon}
        try:
            a = get_json(f"/aqi?lat={lat}&lon={lon}")
            f = a.get("field") or {}
            w = a.get("wind") or {}
            cell["our"] = {
                "pm25": a.get("pm25"),
                "pm25_ambient": a.get("pm25_ambient"),
                "pm25_lo": a.get("pm25_lo"),
                "pm25_hi": a.get("pm25_hi"),
                "us_aqi": a.get("us_aqi"),
                "nearest_sample_km": a.get("nearest_sample_km"),
                "smoke_modifier": a.get("smoke_modifier"),
                "field_age_s": f.get("age_s"),
                "field_built_at": f.get("built_at"),
                "field_samples": f.get("samples"),
                "station_readings": f.get("station_readings"),
                "stations_status": f.get("stations_status"),
                "wind_kmh": w.get("speed_kmh"),
                "wind_from_deg": w.get("from_deg"),
            }
            if a.get("error"):
                cell["our"]["error"] = a.get("error")
        except Exception as e:
            cell["our"] = {"error": str(e)}
        try:
            rd = dpcc_reading(b64)
            p = (rd.get("params") or {})
            cell["dpcc"] = {
                "pm25": (p.get("pm25") or {}).get("value"),
                "pm25_time_ist": (p.get("pm25") or {}).get("time_ist"),
                "pm10": (p.get("pm10") or {}).get("value"),
                "stale_min": dpcc_stale_minutes(rd, now_ist),
                "page_station": rd.get("page_station"),
            }
            ours = (cell.get("our") or {}).get("pm25_ambient")
            theirs = cell["dpcc"]["pm25"]
            if ours is not None and theirs is not None:
                cell["diff_ug"] = round(ours - theirs, 1)
        except Exception as e:
            cell["dpcc"] = {"error": str(e)}
        ep["cells"].append(cell)
    return ep


def append_jsonl(path, obj):
    with open(path, "a") as fh:
        fh.write(json.dumps(obj) + "\n")


# ---------- report ----------

def load_epochs(out_dir):
    path = os.path.join(out_dir, "samples.jsonl")
    if not os.path.exists(path):
        return []
    return [json.loads(l) for l in open(path) if l.strip()]


def report(out_dir):
    eps = load_epochs(out_dir)
    if not eps:
        return "no samples yet"
    L = []
    L.append("| epoch (IST) | station | our field µg | DPCC µg | diff | "
             "DPCC stamp | field_age_s | wind |")
    L.append("|---|---|---|---|---|---|---|---|")
    for ep in eps:
        t = ep["t_ist"][11:16]
        for c in ep["cells"]:
            o, d = c.get("our") or {}, c.get("dpcc") or {}
            wind = (f"{o.get('wind_kmh')}km/h@{o.get('wind_from_deg')}°"
                    if o.get("wind_kmh") is not None else "—")
            L.append(
                f"| {t} | {c['station']} | {o.get('pm25_ambient','—')} | "
                f"{d.get('pm25','—')} | {c.get('diff_ug','—')} | "
                f"{d.get('pm25_time_ist','—')} ({d.get('stale_min','?')}m) | "
                f"{o.get('field_age_s','—')} | {wind} |")
        w = ep.get("why") or {}
        L.append("")
        L.append(f"**{t} claim-check** — line: \"{w.get('line','—')}\" · "
                 f"drivers: {','.join(w.get('drivers') or []) or 'none'} · "
                 f"fires claimed: {w.get('fires_claimed')} · "
                 f"carrying: {w.get('carrying')} · belt {w.get('belt_fires')} · "
                 f"modifier ×{w.get('modifier')} · consistent: "
                 f"{ep.get('fires_claim_consistent')}")
        L.append("")
    # ambient movement across epochs
    means = []
    for ep in eps:
        vals = [c["our"]["pm25_ambient"] for c in ep["cells"]
                if (c.get("our") or {}).get("pm25_ambient") is not None]
        means.append(sum(vals) / len(vals) if vals else None)
    L.append(f"ambient field mean by epoch: "
             f"{[round(m,1) if m is not None else '—' for m in means]}")
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--loop", action="store_true")
    ap.add_argument("--every-s", type=int, default=840,
                    help="sampling interval (default 840s ≈ 14min — "
                         "inside one 15-min field rebuild so each pass "
                         "catches the epoch boundary)")
    ap.add_argument("--minutes", type=int, default=60)
    ap.add_argument("--out", required=True)
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--stations", type=int, default=0,
                    help="limit station count (0 = all 12)")
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)
    stations = STATIONS[:args.stations or None]

    if args.report:
        print(report(args.out))
        return

    # sanity: which of our 12 stations are still on the DPCC live list
    try:
        live = dpcc_station_map()
        missing = [s[0] for s in stations if s[1] not in live]
        if missing:
            print(f"WARN: dropped from DPCC index: {missing}",
                  file=sys.stderr)
    except Exception as e:
        print(f"WARN: DPCC index unreachable: {e}", file=sys.stderr)

    passes = 0
    deadline = time.time() + (args.minutes * 60 if args.loop else 0)
    while True:
        tick = time.time()
        ep = sample_epoch(stations)
        append_jsonl(os.path.join(args.out, "samples.jsonl"), ep)
        with open(os.path.join(
                args.out, f"epoch-{ep['t_ist'][:16].replace(':','')}.json"),
                "w") as fh:
            json.dump(ep, fh, indent=1)
        passes += 1
        ok = sum(1 for c in ep["cells"] if c.get("diff_ug") is not None)
        print(f"[{ep['t_ist'][11:19]} IST] epoch {passes}: {ok}/{len(ep['cells'])} "
              f"cells matched · field_age={ep['cells'][0]['our'].get('field_age_s')}s "
              f"· drivers={','.join((ep.get('why') or {}).get('drivers') or []) or 'none'}",
              flush=True)
        if not args.loop or time.time() + args.every_s * 0.5 >= deadline:
            break
        time.sleep(max(30, args.every_s - (time.time() - tick)))


if __name__ == "__main__":
    main()
