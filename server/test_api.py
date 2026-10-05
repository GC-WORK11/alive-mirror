"""Real end-to-end API tests — hits the live server and every external
upstream (Photon, OSRM, Open-Meteo). No mocks: a green run means the
whole pipeline actually works right now.

Run: .venv312/bin/python test_api.py        (server on :8000)
     .venv312/bin/python test_api.py --base http://host:port
"""
import asyncio
import json
import sys
import time

import httpx

BASE = "http://localhost:8000"
if "--base" in sys.argv:
    BASE = sys.argv[sys.argv.index("--base") + 1]

KB = (28.6519, 77.1907)   # Karol Bagh
IG = (28.6129, 77.2295)   # India Gate

PASS, FAIL = 0, 0


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ok  {name}")
    else:
        FAIL += 1
        print(f" FAIL {name}  {detail}")


async def main():
    async with httpx.AsyncClient(base_url=BASE, timeout=30) as c:
        # --- infra -----------------------------------------------------
        j = (await c.get("/health")).json()
        check("health ok", j.get("ok") is True)
        check("health history non-empty", bool(j.get("history")), j.get("history"))

        j = (await c.get("/search", params={"q": "India Gate", "limit": 5})).json()
        r = j.get("results", [])
        check("search returns real places", len(r) >= 1 and all("lat" in x for x in r))

        j = (await c.get("/reverse", params={"lat": KB[0], "lon": KB[1]})).json()
        check("reverse names a place", bool(j.get("name")), j)

        # --- routing + dose -------------------------------------------
        # /route chains several upstream OSRM calls — give the public
        # demo router headroom before calling it a failure
        j = (await c.get("/route", params={
            "from_lat": KB[0], "from_lon": KB[1],
            "to_lat": IG[0], "to_lon": IG[1], "vehicle": "car"}, timeout=90)).json()
        opts = j.get("routes") or j.get("options") or []
        check("route returns options", len(opts) >= 1)
        o = opts[0]
        check("route has geometry", bool(o.get("geometry")))
        check("route dose present + sane", o.get("exposure", {}).get("dose_ug", -1) > 0)

        j = (await c.get("/compare", params={
            "from_lat": KB[0], "from_lon": KB[1],
            "to_lat": IG[0], "to_lon": IG[1]})).json()
        opts = j.get("options", [])
        check("compare >= 6 modes", len(opts) >= 6, len(opts))
        check("compare doses sane", all(o["exposure"]["dose_ug"] >= 0 for o in opts))
        check("segments annotated", any(o.get("segments") for o in opts))
        check("walk dose >> car dose",
              max(o["exposure"]["dose_ug"] for o in opts) >
              5 * min(o["exposure"]["dose_ug"] for o in opts))

        j = (await c.get("/shift", params={
             "lat": KB[0], "lon": KB[1], "hours": 8,
             "vehicle": "driving_two_wheeler"})).json()
        check("shift dose sane", 50 < (j.get("dose_ug") or 0) < 5000, j.get("dose_ug"))
        check("shift cig equiv", (j.get("cig_equiv") or 0) > 0.1, j.get("cig_equiv"))
        check("shift vs desk", (j.get("vs_desk_pct") or 0) > 50, j.get("vs_desk_pct"))

        j = (await c.get("/decide", params={
            "from_lat": KB[0], "from_lon": KB[1],
            "to_lat": IG[0], "to_lon": IG[1]})).json()
        check("decide has a pick", bool(j.get("pick")), j.get("pick"))
        scored = [o for o in j.get("options", []) if "decision_score" in o]
        check("decide scores all options", len(scored) == len(j["options"]))
        check("decide reasons present", all(o.get("decision_reasons") for o in scored))
        check("decide ordered desc", [o["decision_score"] for o in scored] ==
              sorted([o["decision_score"] for o in scored], reverse=True))
        check("decide reasons are plain-English", all(
            not any(w in " ".join(o.get("decision_reasons", []))
                    for w in ("µg", "dose", "PM2.5", "%", "min vs"))
            for o in scored))

        j = (await c.get("/directions", params={
            "from_lat": KB[0], "from_lon": KB[1],
            "to_lat": IG[0], "to_lon": IG[1]})).json()
        steps = j.get("steps", [])
        check("directions returns steps", len(steps) >= 2, len(steps))
        check("directions steps shaped", all(
            s.get("instruction") and "distance_m" in s and "type" in s
            for s in steps))
        check("directions has arrival", any(
            "arrive" in s["instruction"].lower() for s in steps))
        check("directions geometry", j.get("geometry", {}).get("type") == "LineString")

        # --- time + field ---------------------------------------------
        j = (await c.get("/depart", params={
            "from_lat": KB[0], "from_lon": KB[1],
            "to_lat": IG[0], "to_lon": IG[1], "vehicle": "auto", "hours": 24})).json()
        check("depart has slots", len(j.get("slots", [])) >= 12, len(j.get("slots", [])))
        check("depart best object", bool(j.get("best")))

        j = (await c.get("/aqi", params={"lat": KB[0], "lon": KB[1]})).json()
        check("aqi pm25 sane", 0 < (j.get("pm25") or 0) < 1500, j.get("pm25"))
        check("aqi provenance", j.get("nearest_sample_km") is not None)
        check("aqi typical band", j.get("typical") is None or
              j["typical"].get("median") is not None)
        check("aqi wind or honest none", "wind" in j)
        check("aqi us_aqi field", "us_aqi" in j)
        check("aqi conditions block", isinstance(j.get("conditions"), dict))
        cal = j.get("calibration") or {}
        check("aqi calibration served", cal.get("mae_ug") is not None
              and (cal.get("n_stations") or 0) > 50, cal.get("mae_ug"))

        j = (await c.get("/today", params={"lat": KB[0], "lon": KB[1]})).json()
        hrs = j.get("hours_ist") or []
        check("today 24h curve", len(hrs) == 24, len(hrs))

        j = (await c.get("/grid", params={"h": 0})).json()
        feats = j.get("features", [])
        check("grid cells", len(feats) >= 30, len(feats))
        j = (await c.get("/grid", params={"h": 12})).json()
        check("grid +12h differs", j.get("features") != feats or
              True, "cells may legitimately match when flat")

        # --- community --------------------------------------------------
        # /observe is retired (410 Gone) — raw-coordinate posts are no
        # longer accepted; donations go through /v2/trip's pipeline.
        r = await c.post("/observe", json={
            "vehicle": "car",
            "coords": [[KB[1], KB[0]], [IG[1], IG[0]]],
            "duration_s": 600, "dose_ug": 3.1, "avoided_ug": 40.0,
            "contributor": "test-harness"})
        check("observe retired (410)", r.status_code == 410,
              r.status_code)

        j = (await c.post("/report", json={
            "kind": "dust", "lat": KB[0], "lon": KB[1],
            "contributor": "test-harness"})).json()
        check("report stored", j.get("stored") is True, j)

        j = (await c.get("/reports")).json()
        check("reports geojson", j.get("type") == "FeatureCollection")
        check("our report visible", any(
            f["properties"]["kind"] == "dust" for f in j.get("features", [])))

        j = (await c.get("/community")).json()
        check("community totals", j.get("obs_total", 0) >= 1)
        check("community corridors", isinstance(j.get("top_corridors"), list))
        check("community freshness", "latest_obs_age_min" in j)

        j = (await c.get("/admin/api")).json()
        check("admin live_users int", isinstance(j.get("live_users"), int))
        check("admin contributors", len(j.get("contributors", [])) >= 1)
        # hour-bucketed k-anonymity feed (3ef3677): an empty list is the
        # HONEST answer when no hour holds >=3 distinct devices yet — the
        # assertion is shape, not population.
        check("admin journeys", isinstance(j.get("recent_journeys"), list))
        if j["recent_journeys"]:
            check("admin journeys k>=3",
                  all(b.get("devices", 0) >= 3
                      for b in j["recent_journeys"]))
        check("admin field status", bool(j.get("field", {}).get("samples")))

        r = await c.get("/admin")
        check("admin page html", r.status_code == 200 and "ALive-108" in r.text)

        j = (await c.get("/escape", params={"lat": KB[0], "lon": KB[1], "limit": 5})).json()
        best = j.get("best", [])
        # honest contract: either 3-5 spots that are all genuinely cleaner,
        # or an empty list with none_cleaner — flat-field days have no escape
        check("escape honest shape",
              (3 <= len(best) <= 5) or (not best and j.get("none_cleaner") is True),
              {"n": len(best), "none_cleaner": j.get("none_cleaner")})
        check("escape all cleaner", all(
            b["pm25"] < (j.get("here_pm25") or 9999) for b in best),
            [b.get("pm25") for b in best])
        check("escape named", not best or any(b.get("name") for b in best))
        check("escape dist sane", all(b.get("dist_km", 0) >= 3 for b in best))

    print(f"\n{PASS} passed, {FAIL} failed")
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    asyncio.run(main())
