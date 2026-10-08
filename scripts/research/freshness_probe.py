#!/usr/bin/env python3
"""Read-only freshness + honesty probe for ALive-108 prod.

GET-only against http://65.2.28.40 — no token, no POST, no admin paths.
Prints every number the judges' docs cite so they can be re-verified in
one command before a demo or a post. Stdlib only.

    python3 scripts/research/freshness_probe.py
"""
import json
import urllib.request

BASE = "http://65.2.28.40"
CP = (28.6139, 77.2090)          # Connaught Place — the demo point
IG = (28.6129, 77.2295)          # India Gate
HUDA = (28.4593, 77.0725)        # HUDA City Centre


def get(path, timeout=40):
    with urllib.request.urlopen(BASE + path, timeout=timeout) as r:
        return json.load(r)


def main():
    h = get("/health")
    print("== /health ==")
    print("build:", h.get("build_sha"), "| engine:", h.get("engine"))
    print("field_age_s:", h.get("field_age_s"),
          "| refresh_in:", h.get("field_refresh_in_s"),
          "| stale:", h.get("field_stale"))
    s = h.get("sources", {})
    print("model:", "up" if (s.get("model") or {}).get("up") else "DOWN",
          "| source:", (s.get("model") or {}).get("source"),
          "| samples:", (s.get("model") or {}).get("samples"))
    st = s.get("stations") or {}
    print("stations:", "up" if st.get("up") else "DOWN",
          "| count:", st.get("count"),
          "| src:", st.get("source"), "| feeds:", st.get("feeds"))
    print("fires:", "up" if (s.get("fires") or {}).get("up") else "DOWN",
          "| n:", (s.get("fires") or {}).get("fires"),
          "| age_s:", (s.get("fires") or {}).get("age_s"))
    print("wind:", h.get("wind"), "| transit real_feeds:",
          (h.get("transit") or {}).get("real_feeds"))

    a = get("/aqi?lat=%s&lon=%s" % CP)
    f = a.get("field") or {}
    print("\n== /aqi @ Connaught Place ==")
    print("pm25:", a.get("pm25"), "| ambient:", a.get("pm25_ambient"),
          "| lo/hi:", a.get("pm25_lo"), "/", a.get("pm25_hi"))
    print("pm10:", a.get("pm10"), "| no2:", a.get("no2"),
          "| us_aqi:", a.get("us_aqi"),
          "(model's own:", a.get("us_aqi_model"), ")")
    print("nearest_station_km:", a.get("nearest_station_km"),
          "| nearest_sample_km:", a.get("nearest_sample_km"))
    print("instruments:", f.get("station_readings"),
          "| samples:", f.get("samples"),
          "| src:", f.get("source"), "| serving:", f.get("serving"))

    c = get("/compare?from_lat=%s&from_lon=%s&to_lat=%s&to_lon=%s"
            % (IG + HUDA))
    print("\n== /compare India Gate -> HUDA City Centre ==")
    for o in c.get("options", []):
        e = o.get("exposure") or {}
        print(" %-38s %5skm %4smin dose=%s vs_best=%s%%"
              % (o.get("label"), o.get("distance_km"),
                 o.get("duration_min"), e.get("dose_ug"),
                 e.get("dose_vs_best_pct")))

    d = get("/v2/districts")
    print("\n== /v2/districts (sparse honesty) ==")
    for r in (d.get("districts") or d.get("rows") or []):
        print(" %-16s pm25=%s conf=%s cells=%s centroid_read=%s"
              % (r.get("name"), r.get("pm25"), r.get("confidence"),
                 r.get("cells_covered"), r.get("centroid_read")))

    sh = get("/shift?lat=%s&lon=%s&hours=8&start_hour=7&mode=two_wheeler"
             % CP)
    print("\n== /shift 8h two-wheeler from 07:00 @CP ==")
    print("dose_ug:", sh.get("dose_ug"), "| range:", sh.get("dose_lo_ug"),
          "-", sh.get("dose_hi_ug"), "| cigarettes:", sh.get("cigarettes"),
          "| vs_desk:", sh.get("vs_desk_pct"))

    print("\n(re-read before every demo — numbers drift with the air.)")


if __name__ == "__main__":
    main()
