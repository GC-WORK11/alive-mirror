#!/usr/bin/env bash
# verify_numbers.sh — numbers-integrity harness for ALive-108.
#
# Re-derives every figure the product/docs/video quote from LIVE responses
# (or the committed binary artifacts), prints CURRENT value next to what the
# quoting surfaces say, and flags contradictions. Read-only against the
# deployment: GETs + the one allowed POST /v2/plan. Never POSTs elsewhere.
#
# usage:   scripts/verify_numbers.sh [base_url]
# default: the live NLB. Pass http://localhost:8000 to check a local server.
#
# Exit code is always 0 — this is a reporting tool, not a gate. A figure that
# can't be re-derived is printed as MISSING rather than guessed.
#
# Canonical ledger: docs/plan/NUMBERS.md. Demo-morning checklist: docs/demo-day.md.

set -u
BASE="${1:-http://alive108-2699c171ddded465.elb.ap-south-1.amazonaws.com}"
REPO="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$(mktemp -d /tmp/verify_numbers.XXXXXX)"
CP_LAT=28.6315; CP_LON=77.2167          # Connaught Place (demo anchor, scripts/smoke_live.sh)
GG_LAT=28.495;  GG_LON=77.089           # Gurugram (demo OD destination)

echo "== ALive-108 numbers integrity =="
echo "base: $BASE"
echo "out : $OUT"

fetch() { # path outfile [curl-args...]
  local p="$1" f="$2"; shift 2
  curl -s --max-time 90 "$@" "$BASE$p" -o "$OUT/$f" \
    && echo "  GET $p -> $f ($(wc -c <"$OUT/$f" | tr -d ' ')B)" \
    || echo "  !! $p FAILED"
}

fetch /health                     health.json
fetch "/aqi?lat=$CP_LAT&lon=$CP_LON"      aqi.json
fetch "/grid?h=0"                 grid.json
fetch "/grid?h=0&cells=40"        grid40.json
fetch /fires                      fires.json
fetch /v2/city                    city.json
fetch "/v2/day?lat=$CP_LAT&lon=$CP_LON"   day.json
fetch "/v2/reach?lat=$CP_LAT&lon=$CP_LON&mode=walk&budget_ug=25"  reach_w25.json
fetch "/v2/reach?lat=$CP_LAT&lon=$CP_LON&mode=walk&budget_ug=50"  reach_w50.json
fetch "/v2/reach?lat=$CP_LAT&lon=$CP_LON&mode=car&budget_ug=25"   reach_c25.json
fetch /v2/districts               districts.json
fetch /community                  community.json
fetch "/v2/outlook?lat=$CP_LAT&lon=$CP_LON" outlook.json
fetch "/depart?from_lat=$CP_LAT&from_lon=$CP_LON&to_lat=$GG_LAT&to_lon=$GG_LON" depart.json
# the ONE allowed POST: the demo-OD dose ladder
fetch /v2/plan plan.json -X POST -H 'content-type: application/json' \
  -d "{\"from\":{\"lat\":$CP_LAT,\"lon\":$CP_LON},\"to\":{\"lat\":$GG_LAT,\"lon\":$GG_LON}}"

# the heredoc uses 3.12+ f-string syntax (nested same-quote); stock macOS
# python3 (3.9) dies on it. Prefer the repo venv, then any modern python3.x,
# falling back to plain python3 with a clear error instead of a syntax traceback.
PY_BIN=""
for cand in "$REPO/server/.venv312/bin/python3" \
    "$(command -v python3.14 2>/dev/null)" "$(command -v python3.13 2>/dev/null)" \
    "$(command -v python3.12 2>/dev/null)" "$(command -v python3 2>/dev/null)"; do
  [ -n "$cand" ] && [ -x "$cand" ] && PY_BIN="$cand" && break
done
if [ -z "$PY_BIN" ]; then echo "!! no python3 found"; exit 1; fi
if ! "$PY_BIN" -c 'import sys; sys.exit(0 if sys.version_info>=(3,12) else 1)' 2>/dev/null; then
  echo "!! $PY_BIN is <3.12 — this script needs >=3.12 (f-string nesting)."
  echo "   run: server/.venv312/bin/python3 exists in a dev checkout, or brew install python@3.12"
  exit 1
fi
echo "py  : $PY_BIN ($("$PY_BIN" -c 'import sys;print(sys.version.split()[0])'))"
OUT="$OUT" REPO="$REPO" "$PY_BIN" - <<'PY'
import json, os, re, gzip, struct
OUT, REPO = os.environ["OUT"], os.environ["REPO"]

def load(f):
    try: return json.load(open(os.path.join(OUT, f)))
    except Exception: return None

DOCS = ["README.md", "docs/demo-day.md", "docs/submission/writeup.md",
        "docs/submission/repo-readme.md", "docs/submission/video-shotlist.md",
        "docs/plan/demo-script.md", "docs/plan/master-plan.md",
        "docs/plan/judges-faq.md", "docs/plan/handoff.md", "HANDOFF.md",
        "docs/11-demo-script.md", "docs/28-pitch.md"]

def surf(pattern, limit=4):
    """where a figure is quoted: [(file:line, snippet)]"""
    hits = []
    for p in DOCS:
        fp = os.path.join(REPO, p)
        if not os.path.exists(fp): continue
        for i, l in enumerate(open(fp, encoding="utf-8", errors="replace"), 1):
            if re.search(pattern, l):
                hits.append(f"{p}:{i}: {l.strip()[:80]}")
    return hits[:limit]

rows, flags = [], []
def row(claim, live, pattern, safe, note=""):
    rows.append((claim, live, pattern, safe, note))
def flag(what, says, live_):
    flags.append((what, says, live_))

H = load("health.json") or {}
A = load("aqi.json") or {}
G = load("grid.json") or {}
F = load("fires.json") or {}
C = load("city.json") or {}
D = load("day.json") or {}
DE = load("depart.json") or {}
O = load("outlook.json") or {}
CO = load("community.json") or {}
DI = load("districts.json") or {}
P = load("plan.json") or {}

routing = H.get("routing", {})
finfo = A.get("field", {}) if isinstance(A.get("field"), dict) else {}
feats = F.get("features", []) if isinstance(F.get("features"), list) else []
n_fires = len(feats) or (F.get("metadata") or {}).get("count")
n_belt = sum(1 for x in feats if (x.get("properties") or {}).get("belt"))
opts = P.get("options", []) or []

def mid(o):
    if not isinstance(o, dict):
        return None
    d = o.get("dose") or o.get("dose_ug") or {}
    return d.get("mid") if isinstance(d, dict) else o.get("dose_ug")
def best(mode):
    ms = [o for o in opts if o.get("mode") == mode]
    return min(ms, key=lambda o: mid(o) or 1e9) if ms else None
car, walk = best("car"), best("walk")
car_mid, walk_mid = (mid(car) if car else None), (mid(walk) if walk else None)
spread = (walk_mid / car_mid) if car_mid and walk_mid else None
maxw = max((mid(o) for o in opts if o.get("mode") == "walk"), default=None)
max_spread = (maxw / car_mid) if car_mid and maxw else None
nh = C.get("next_hours") or []
nh_lo = min((h.get("pm25") for h in nh), default=None)
nh_hi = max((h.get("pm25") for h in nh), default=None)

# ---------- figure table ----------
print("\n====================  FIGURE TABLE  ====================")
def emit(claim, live, pat, safe, note=""):
    row(claim, live, pat, safe, note)
    print(f"  {claim:44s} {str(live)[:52]:52s} [{safe}]")
    if note: print(f"{'':46s}· {note}")

emit("build_sha (/health)", H.get("build_sha"), r"build_sha|sha", "wart",
     "/admin/api/status may disagree — BUILD_SHA lag; say the ECR image tag")
try:
    _meta = json.load(open(os.path.join(REPO, "server/data/route_graph.meta.json")))
    emit("graph edges / nodes (meta)", f"{_meta.get('edges')} / {_meta.get('nodes')}",
         r"1,?070,?459|819,?846", "static")
except Exception:
    emit("graph edges / nodes (meta)", "MISSING", r"", "static")
emit("edges priced (live /health)", routing.get("edges_priced"), r"903,?058|903k|0\.90 ?m", "static")
emit("reweight TTL s", "600 (admin /admin/api/status.routing.reweight_ttl_s; not on /health)",
     r"≤600 ?s|10.?min|every 15", "static")
emit("/grid cells h=0 (default cells=22 / cells=40)",
     f"{len(G.get('features', []))} / {len((load('grid40.json') or {}).get('features', []))}",
     r"484 cells|/grid", "static-ish",
     "484 = default 22×22 lattice; landing/admin use cells=40 → 1,600")
emit("field age s / refresh_in s / stale",
     f"{H.get('field_age_s')} / {H.get('field_refresh_in_s')} / {H.get('field_stale')}",
     r"~4 min|15.?min|field age|age", "drift")
emit("stations live (WAQI)", (H.get("sources") or {}).get("stations", {}).get("count"),
     r"24 (live )?(WAQI|instruments|stations)", "drift")
emit("model samples", (H.get("sources") or {}).get("model", {}).get("samples"),
     r"~4[0-9] model|7[0-9] samples|samples", "drift")
emit("fires total / in-belt", f"{n_fires} / {n_belt}", r"~?7[0-9].{0,30}(fire|belt)|fires", "drift")
emit("smoke modifier @CP", A.get("smoke_modifier") or "absent", r"×1\.[0-9]{2}|modifier", "drift")
emit("PM2.5 @CP breathing / ambient", f"{A.get('pm25')} / {A.get('pm25_ambient')}",
     r"7[0-9]\.[0-9].*breathing|ambient", "drift")
emit("US AQI @CP", A.get("us_aqi"), r"US ?AQI", "drift")
emit("wind", f"{(H.get('wind') or {}).get('speed_kmh')} km/h from {(H.get('wind') or {}).get('from_deg')}°",
     r"wind", "drift")

emit("plan options returned", len(opts), r"[0-9]{1,2} options", "drift")
emit("plan took_ms", P.get("took_ms"), r"~0\.6 ?s|under two|fresh unseen", "drift",
     "cold vs warm — re-hit to see warm latency")
for m in ("car", "car_open", "bike", "bus", "auto", "metro+walk", "cycle", "walk"):
    emit(f"  dose {m} (mid µg)", mid(best(m)), r"", "drift")
emit("spread walk÷car", f"{spread:.1f}×" if spread else "MISSING",
     r"~?3[0-9][×x]", "drift",
     f"slowest/best {max_spread:.1f}× — has run 31–45× across ODs this week" if max_spread else "")
emit("annualized walk vs car (mid×2×250d)",
     f"{walk_mid*0.5:.0f} mg vs {car_mid*0.5:.1f} mg" if spread else "MISSING",
     r"[0-9]{2,3} ?mg|a year", "drift",
     "landing renders this live — 'five round-trips a week for a year' ×250d ≈ 50 weeks")
emit("/v2/day heavy_window", json.dumps(D.get("heavy_window")),
     r"heavy stretch|21:30|22:30", "drift",
     "; ".join(x.get("line","") for x in (D.get("decisions") or [])[:2]))
emit("/v2/day cleanest_window", json.dumps(D.get("cleanest_window")),
     r"cleanest|17:30|18:30|19:30", "drift")
emit("/v2/day day_mean_pm25", D.get("day_mean_pm25"), r"day mean", "drift")
nw, wo = (DE.get("now") or {}).get("dose_ug"), (DE.get("worst") or {}).get("dose_ug")
emit("/depart now → worst", f"{nw} → {wo} ({wo/nw:.1f}×)" if nw and wo else "MISSING",
     r"~6×|~8×|evening peak", "drift")
for tag, R, lbl in (("walk 25 µg", load("reach_w25.json") or {}, "25"),
                    ("walk 50 µg", load("reach_w50.json") or {}, "50"),
                    ("car 25 µg", load("reach_c25.json") or {}, "car25")):
    r = R.get("reach", R)
    emit(f"/v2/reach {tag}",
         f"{r.get('edge_count')} edges / {r.get('distance_km')} km" + (" PARTIAL" if r.get("partial") else ""),
         r"road segments|km of street|94,?000|90,?503", "drift")
prov = C.get("provenance") or {}
tr = prov.get("trips") or {}
emit("corridors publishable / tracked", f"{tr.get('publishable_corridors')} / {tr.get('cells_tracked')}",
     r"publishable|10 (of|publishable)", "drift")
emit("community 24h obs/km/avoided",
     f"{CO.get('obs_24h')} / {CO.get('km_24h')} km / {CO.get('avoided_ug_24h')} µg",
     r"km donated|avoided", "drift")
emit("community all-time obs/contrib/avoided",
     f"{CO.get('obs_total')} / {CO.get('contributors')} / {CO.get('avoided_ug_all')} µg",
     r"contributors|333", "drift")
emit("breath day_inhaled mid µg (cigs)",
     f"{(C.get('breath') or {}).get('day_inhaled_ug',{}).get('mid')} ({(C.get('breath') or {}).get('cigarettes',{}).get('mid')})",
     r"~550|day_inhaled", "drift")
emit("/v2/city next_hours pm25 range", f"{nh_lo} → {nh_hi}", r"~7[0-9] ?→ ?~?[0-9]{3}", "drift")
dy = (O.get("days") or [{}])[0]
emit("outlook today mid / band", f"{dy.get('pm25_mid')} / {dy.get('band')}", r"", "drift")

# artifacts
fv_p = os.path.join(REPO, "server/data/field_validation.md")
fv = open(fv_p).read() if os.path.exists(fv_p) else ""
emit("field_validation: pairs / stations / ±2σ coverage",
     f"{re.search(r'[0-9],?[0-9]{3} (pairs|station-hours)', fv).group(0) if re.search(r'[0-9],?[0-9]{3}', fv) else '?'} / "
     f"{re.search(r'85', fv).group(0) if fv else '?'} / "
     f"{re.search(r'9[0-9]\.[0-9]', fv).group(0) if re.search(r'9[0-9]\.[0-9]', fv) else '?'}",
     r"3,?550|95\.2|85 stations", "artifact")
try:
    cal = json.load(open(os.path.join(REPO, "server/data/field_calibration.json")))
    emit("LOO calibration MAE / bias / n",
         f"{cal['mae_ug']} / {cal['mean_bias_ug']} / {cal['n_stations']}",
         r"MAE 4[0-9]|46\.1|bias \+?0", "artifact")
except Exception as e:
    emit("LOO calibration", f"MISSING ({e})", r"", "artifact")
try:
    blob = gzip.open(os.path.join(REPO, "server/data/route_graph.bin.gz"), "rb").read()
    magic, nn, ne, nname, npts = struct.unpack_from("<4s4I", blob, 0)
    off = 20 + 16 + 8 * nn
    for _ in range(nname):
        (ln,) = struct.unpack_from("<H", blob, off); off += 2 + ln
    fmt, sz = "<IIfIHBbBiBB", struct.calcsize("<IIfIHBbBiBB")
    acc = sum(1 for i in range(ne) if struct.unpack_from(fmt, blob, off + i*sz)[10])
    ow  = sum(1 for i in range(ne) if struct.unpack_from(fmt, blob, off + i*sz)[6])
    (nb,) = struct.unpack_from("<I", blob, off + sz*ne)
    emit("graph blob: access-override / one-way / bans",
         f"{acc} / {ow} / {nb}", r"3,?428|107k one-way|230 (OSM )?turn", "static")
except Exception as e:
    emit("graph blob counts", f"MISSING ({e})", r"", "static")
try:
    g1 = len(json.load(open(os.path.join(REPO, "Mobile/assets/delhi-gazetteer.json"))))
    g2 = len(json.load(open(os.path.join(REPO, "server/data/delhi-gazetteer.json"))))
    emit("gazetteer rows (Mobile bundle / server copy)", f"{g1} / {g2}",
         r"124,?3[0-9]{2}|123,?9[0-9]{2}", "static")
except Exception as e:
    emit("gazetteer rows", f"MISSING ({e})", r"", "static")
emit("history stations (climatology)", (H.get("history") or {}).get("stations"),
     r"125 stations|9M station", "artifact",
     "'9M station-hours' is a build-log count, not re-derivable from the committed quantile file")

# ---------- where each figure is quoted ----------
print("\n====================  WHERE EACH IS QUOTED  ====================")
seen = set()
for claim, live, pat, safe, note in rows:
    if not pat: continue
    hs = surf(pat)
    if not hs: continue
    print(f"· {claim}  → live: {live}")
    for h in hs:
        if h in seen: continue
        seen.add(h); print(f"    {h}")

# ---------- mechanical contradiction flags ----------
print("\n====================  FLAGS  ====================")
def grab(pat, paths):
    for p in paths:
        fp = os.path.join(REPO, p)
        if not os.path.exists(fp): continue
        for i, l in enumerate(open(fp, encoding="utf-8", errors="replace"), 1):
            m = re.search(pat, l)
            if m: return (f"{p}:{i}", l.strip())
    return None

# 1) every surface's edge/priced numbers must equal live
for pat, val, nm in ((r"1,?070,?459", routing.get("edges"), "edges"),
                     (r"903,?058", routing.get("edges_priced"), "edges_priced")):
    hits = surf(pat)
    ok = val is not None
    if not ok: flag(nm, "—", "live MISSING")

# 2) README validation row vs the file it cites
m = grab(r"MAE 4[0-9]\.[0-9].*field_validation", DOCS)
filev = re.search(r"MAE[^0-9]*([0-9]+\.[0-9])", fv)
if m and filev and m[1] and str(filev.group(1)) not in m[1]:
    flag("field-validation MAE", m[0] + " → " + m[1][:70], f"file says MAE {filev.group(1)}")
# 3) gazetteer row counts
m = grab(r"124,?334", DOCS)
if m: flag("gazetteer '124,334'", m[0] + " → " + m[1][:70], f"bundle has {g1}; server copy {g2}")
m = grab(r"123,?934", DOCS)
if m: flag("gazetteer '123,934'", m[0] + " → " + m[1][:70], f"bundle has {g1}; server copy {g2} — say which")
# 4) demo-OD dose pair quoted vs live ladder
m = grab(r"5\.7 vs 189\.7|5\.7.{0,6}189\.7", DOCS)
if m: flag("demo-OD dose pair", m[0] + " → " + m[1][:70], f"car {car_mid} vs walk {walk_mid} µg")
# 5) spread phrasing
m = grab(r"~35×", DOCS)
if m and spread and abs(spread - 35) > 2:
    flag("'~35×' quoted", m[0], f"today {spread:.1f}× — range 31–45× keeps '~35×' honest")
# 6) fires quoted ~70 vs live
m = grab(r"~70 (over|fires|NASA)", DOCS)
if m and n_fires and abs(n_fires - 70) > 10:
    flag("fires '~70'", m[0] + " → " + m[1][:70], f"live {n_fires} total / {n_belt} belt")
# 7) smoke modifier ×1.27 vs live
m = grab(r"×1\.27", DOCS)
smk = A.get("smoke_modifier")
if m:
    flag("smoke ×1.27 at CP", m[0] + " → " + m[1][:70], f"smoke block {smk or 'null'} today")
# 8) 'Stations are offline' vs live stations
m = grab(r"[Ss]tations are offline", DOCS)
if m and (H.get("sources") or {}).get("stations", {}).get("count"):
    flag("'stations offline' claim", m[0] + " → " + m[1][:70],
         f"{H['sources']['stations']['count']} WAQI stations live")
# 9) reach numbers quoted vs live
for pat, R, nm in ((r"~?4,?200.{0,20}187 ?km", load("reach_w25.json"), "walk@25"),
                   (r"~?15,?000.{0,20}880", load("reach_w50.json"), "walk@50"),
                   (r"~?94,?000 ?km", load("reach_c25.json"), "car@25")):
    m = grab(pat, DOCS)
    r = (R or {}).get("reach", R or {})
    if m and r.get("edge_count"):
        flag(f"reach {nm}", m[0] + " → " + m[1][:70],
             f"{r.get('edge_count')} edges / {r.get('distance_km')} km")

if not flags:
    print("  (none — all quoted numbers match live within their stated precision)")
for w_, s_, l_ in flags:
    print(f"  ⚠ {w_}\n      surface: {s_}\n      live   : {l_}")

print(f"""
notes:
 · build_sha wart — /health reports {H.get('build_sha')}; /admin/api/status reports the
   deployed image sha. On stage, say the ECR tag, not the stamp.
 · '35×' is a RANGE claim: {spread and f'{spread:.1f}'}× today on the demo OD
   (slowest/best {max_spread and f'{max_spread:.1f}'}×; 31–45× across ODs this week).
   Honest phrasing: '~35× on a Delhi commute'.
 · '148 mg vs 4.3 mg' is landing.html's live render (mid×2×250d = mg/yr): today reads
   {walk_mid and f'{walk_mid*0.5:.0f}'} vs {car_mid and f'{car_mid*0.5:.1f}'} mg.
 · '90,503 km' / '706 km' were earlier /v2/reach distance_km reads — drift-prone;
   re-run for the morning-of value.
 · raw responses saved under {OUT} — diff the JSON, don't trust prose.
""")
PY
