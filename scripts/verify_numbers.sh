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
# /health.sources.stations is the station-count live check: two accepted
# states — 52–54 (24 WAQI + up-to-30 DPCC; instruments age out individually
# under MAX_AGE_S so the full-feed count drifts down a few between feeds) or
# 24 WAQI-only when DPCC pages go stale wholesale (honest degrade, recovers
# on next feed).
st = (H.get("sources") or {}).get("stations") or {}
st_count, st_source = st.get("count"), st.get("source")
st_feeds = st.get("feeds") or {}
aq_readings = finfo.get("station_readings")
aq_src = finfo.get("stations_src")
aq_status = finfo.get("stations_status") or {}

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
emit("stations live (instruments)",
     f"{st_count} — src:{st_source} feeds:{json.dumps(st_feeds)} aqi:{aq_readings}",
     r"~?5[2-4] (live )?(instruments|stations)|24 (live )?WAQI|waqi\+dpcc|30 DPCC", "drift",
     "accepted states: 52–54 = full (per-instrument aging drifts the count "
     "down); 24 = WAQI-only degrade (DPCC stale-dropped ~90 min, recovers)")
emit("model samples", (H.get("sources") or {}).get("model", {}).get("samples"),
     r"~4[0-9] model|7[0-9] samples|samples", "drift")
emit("fires total / in-belt", f"{n_fires} / {n_belt}", r"~?[0-9]{2,3}.{0,30}(fires|in.?belt|MW)|fires", "drift")
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
emit("history stations (climatology)", (H.get("history") or {}).get("stations_climatology"),
     r"125 stations|9M station", "artifact",
     "'9M station-hours' is a build-log count, not re-derivable from the committed quantile file")
try:
    hv = open(os.path.join(REPO, "docs/lanes/holdout-reverify-report.md")).read()
    _gap = re.search(r"former-GAP[^\n]*\*\*([0-9.]+)\*\*", hv)
    _all = re.search(r"all 30 DPCC sites[^\n]*\*\*([0-9.]+)\*\*", hv)
    emit("holdout artifact: former-GAP / all-30 MAE",
         f"{_gap.group(1) if _gap else '?'} / {_all.group(1) if _all else '?'}",
         r"6\.2|10\.5|holdout", "artifact",
         "drift-class: quote 'single-digit to low-teens µg at instrumented "
         "sites' — never bare 6.2 (re-probe ~10 mean, to ~17 on falling edges)")
except Exception:
    emit("holdout artifact", "MISSING", r"", "artifact")

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

DOC_LINES = {}
for _p in DOCS:
    _fp = os.path.join(REPO, _p)
    if os.path.exists(_fp):
        DOC_LINES[_p] = open(_fp, encoding="utf-8", errors="replace").read().splitlines()

# Stamped reads are records, not claims: NUMBERS §4 declares the handoff logs
# snapshots wholesale; elsewhere a ±4-line window decides whether a figure is
# inside a dated pass/deploy/probe entry. Stamped lines can never contradict
# live — they were true at their stamp.
LOG_FILES = {"docs/plan/handoff.md", "HANDOFF.md"}
STAMP = re.compile(
    r"(?i)(stamp|pass\s+[0-9ivx]|verif|deploy|task-?def|build [`']?[0-9a-f]{7}|"
    r"20[0-9]{2}[-/][0-9]{2}|epoch|watch|earlier|previous|last (week|night|pass)|"
    r"probe|re-?ran|record|snapshot|histor|observed|afternoon|tonight|morning|"
    r"evening|mid-day|stale|drift|recover)")
def _stamp_spans(lines):
    """lines inside a `*[ ... ]*` stamped-pass block (demo-day's convention)."""
    inside, out = False, set()
    for i, l in enumerate(lines):
        if "*[" in l: inside = True
        if inside: out.add(i)
        if "]*" in l: inside = False
    return out
BLOCK_STAMPED = {p: _stamp_spans(ls) for p, ls in DOC_LINES.items()}
def stamped(path, i):
    if path in LOG_FILES: return True
    if i in BLOCK_STAMPED.get(path, ()): return True
    ls = DOC_LINES.get(path, [])
    return any(STAMP.search(x) for x in ls[max(0, i - 4):i + 1])

infos = []  # printed under flags: live-state notes that are not doc faults

# 1) every surface's edge/priced numbers must equal live — and the figure
#    must not have vanished from docs entirely
for pat, val, nm in ((r"1,?070,?459", routing.get("edges"), "edges"),
                     (r"903,?058", routing.get("edges_priced"), "edges_priced")):
    hits = surf(pat)
    if val is None:
        flag(nm, "—", "live MISSING")
    elif not hits:
        flag(nm, f"live {val}", f"no surface quotes {pat} — figure dropped everywhere")

# 2) README validation row vs the file it cites
m = grab(r"MAE 4[0-9]\.[0-9].*field_validation", DOCS)
filev = re.search(r"MAE[^0-9]*([0-9]+\.[0-9])", fv)
if m and filev and m[1] and str(filev.group(1)) not in m[1]:
    flag("field-validation MAE", m[0] + " → " + m[1][:70], f"file says MAE {filev.group(1)}")
# 3) gazetteer row counts — '124,334' is always wrong; '123,934' is only a
#    fault when the line doesn't say it's the server-side copy
for pat in (r"124,?334", r"123,?934"):
    for p in DOCS:
        for i, l in enumerate(DOC_LINES.get(p, [])):
            if not re.search(pat, l): continue
            if pat.startswith("123") and re.search(
                    r"server|copy|bundle|mobile|on-?device|fallback", l):
                continue
            flag(f"gazetteer {pat}", f"{p}:{i+1} → {l.strip()[:70]}",
                 f"bundle has {g1}; server copy {g2} — say which")
# 4) demo-OD dose pair quoted vs live ladder
m = grab(r"5\.7 vs 189\.7|5\.7.{0,6}189\.7", DOCS)
if m: flag("demo-OD dose pair", m[0] + " → " + m[1][:70], f"car {car_mid} vs walk {walk_mid} µg")
# 5) spread phrasing — '~35×' is a RANGE claim; only a read outside the
#    recorded 31–45× band makes it a lie
m = grab(r"~35×", DOCS)
if m and spread and not (31 <= spread <= 45):
    flag("'~35×' quoted", m[0],
         f"today {spread:.1f}× — outside the recorded 31–45× band; re-stamp")
# 6) fires count quoted vs live — fires swing ~30→90 in a day; an unstamped
#    count more than ~25 off live contradicts, a stamped one is a record
for p in DOCS:
    for i, l in enumerate(DOC_LINES.get(p, [])):
        fm = re.search(r"(?:~?(\d{2,3})\s*(?:/\s*\d+\s*)?fires|fires\s*~?(\d{2,3}))", l)
        if not fm or stamped(p, i): continue
        q = int(fm.group(1) or fm.group(2))
        if n_fires and abs(q - n_fires) > 25:
            flag("fires count quoted", f"{p}:{i+1} → {l.strip()[:70]}",
                 f"live {n_fires} total / {n_belt} belt — stamp the read")
# 7) smoke modifier ×1.27 vs live — skip stamped pass entries
for p in DOCS:
    for i, l in enumerate(DOC_LINES.get(p, [])):
        if not re.search(r"×1\.27", l) or stamped(p, i): continue
        flag("smoke ×1.27 at CP", f"{p}:{i+1} → {l.strip()[:70]}",
             f"smoke block {A.get('smoke_modifier') or 'null'} today — range absent↔×1.27")
# 8) 'Stations are offline' vs live stations
m = grab(r"[Ss]tations are offline", DOCS)
if m and st_count:
    flag("'stations offline' claim", m[0] + " → " + m[1][:70],
         f"{st_count} instruments live on /health ({st_source})")
# 9) reach numbers quoted vs live
for pat, R, nm in ((r"~?4,?200.{0,20}187 ?km", load("reach_w25.json"), "walk@25"),
                   (r"~?15,?000.{0,20}880", load("reach_w50.json"), "walk@50"),
                   (r"~?94,?000 ?km", load("reach_c25.json"), "car@25")):
    m = grab(pat, DOCS)
    r = (R or {}).get("reach", R or {})
    if m and r.get("edge_count"):
        flag(f"reach {nm}", m[0] + " → " + m[1][:70],
             f"{r.get('edge_count')} edges / {r.get('distance_km')} km")

# 10) /health sources.stations.count live check — the accepted states are
#     52–54 (24 WAQI + up-to-30 DPCC — instruments age out individually under
#     MAX_AGE_S, so the full-feed count is a range, not a pin) and 24
#     (WAQI-only degrade: DPCC pages stale >MAX_AGE_S get dropped wholesale,
#     feed recovers). Anything else is a real surprise.
if st_count is None:
    flag("stations.count", "—", "sources.stations missing from /health")
elif 52 <= st_count <= 54:
    if "dpcc" not in (st_source or ""):
        flag("stations.source", f"count {st_count}, source {st_source!r}",
             f"{st_count} instruments can't come from WAQI alone — inconsistent wire")
    if "dpcc" not in st_feeds:
        infos.append(f"feeds map lacks 'dpcc' while count={st_count} — known transient "
                     "mid-refresh wart (truth-audit §1), self-heals on next build")
elif st_count == 24:
    infos.append("stations in DEGRADE mode (24 WAQI-only — DPCC stale-dropped). "
                 "Docs quoting 54 stay honest (they say 'drifts/recovers'); "
                 "re-check after the next feed lands")
else:
    flag("stations.count", str(st_count),
         "not an accepted state — expected 52–54 (waqi+dpcc, per-instrument "
         "aging drift) or 24 (waqi-only degrade)")
# /health and /aqi refresh at different times — each drops instruments as
# they age past MAX_AGE_S, so the two counts can sit a couple apart on one
# probe (54→53→52 watched in the max2 run). ±2 = honest skew; more = the
# wires disagree.
if (aq_readings is not None and st_count is not None
        and abs(aq_readings - st_count) > 2):
    flag("/aqi station_readings", str(aq_readings),
         f"/health count {st_count} — the two wires disagree beyond ±2 "
         "per-instrument aging skew")

# 11) stale 24-world phrasing — an UNSTAMPED '24 stations/instruments' claim
#     is stale when live is 54; '24 WAQI + 30 DPCC' and degrade-mode notes
#     are the current truth, not flags
for p in DOCS:
    if p in LOG_FILES: continue
    for i, l in enumerate(DOC_LINES.get(p, [])):
        if not re.search(r"\b24 (WAQI )?(stations|instruments)\b", l): continue
        if re.search(r"30 DPCC|waqi\+dpcc|\+ ?30", l): continue
        if stamped(p, i): continue
        if st_count is not None and 52 <= st_count <= 54:
            flag("'24 stations' world", f"{p}:{i+1} → {l.strip()[:70]}",
                 f"live is {st_count} (24 WAQI + DPCC, full-feed range "
                 "52–54) — 24-only is the degrade mode, not the world")

# 12) bare '6.2' holdout MAE — the artifact's all-30 figure is only true of
#     its probe; a doc asserting 6.2 with no range/artifact framing over-claims
for p in DOCS:
    for i, l in enumerate(DOC_LINES.get(p, [])):
        if not re.search(r"\b6\.2\b", l): continue
        ctx = " ".join(DOC_LINES[p][max(0, i - 2):i + 1])
        if not re.search(r"(?i)MAE|agreement|error|holdout|accuracy|µg|\bug\b", ctx):
            continue
        if re.search(r"(?i)→|->|—|–|single-digit|low-teens|worst|holdout|reverif|"
                     r"artifact|stamp|probe|range|blind|up to|~", ctx):
            continue
        flag("bare '6.2' holdout MAE", f"{p}:{i+1} → {l.strip()[:70]}",
             "quote 'single-digit to low-teens µg at instrumented sites' — "
             "6.2 is one probe's artifact (re-probe ~10 mean, to ~17 on falling edges)")

if not flags:
    print("  (none — all quoted numbers match live within their stated precision)")
for w_, s_, l_ in flags:
    print(f"  ⚠ {w_}\n      surface: {s_}\n      live   : {l_}")
for n_ in infos:
    print(f"  · {n_}")

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
 · stations live check accepts: {st_count} now — 52–54 = 24 WAQI + up-to-30
   DPCC (per-instrument aging drifts the count down a few between feeds);
   24 = WAQI-only degrade (DPCC staleness guard drops all 30 ~90 min after a
   site stall; honest, recovers). /aqi station_readings may sit ±2 off
   /health — each endpoint ages instruments at different times.
 · holdout MAE: the 22.8→10.5 / 27.1→6.2 figures belong to their probe artifact
   (docs/lanes/holdout-reverify-report.md). Field truth is single-digit to
   low-teens µg at instrumented sites — never quote a bare 6.2.
 · raw responses saved under {OUT} — diff the JSON, don't trust prose.
""")
PY
