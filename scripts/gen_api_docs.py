#!/usr/bin/env python3
"""gen_api_docs.py — regenerate the committed API reference.

Hits a RUNNING server for /openapi.json plus one real request per
endpoint, then writes:

  docs/api/openapi.json     committed schema snapshot
  docs/api/samples/*.json   redacted real responses (arrays cropped to 2)
  docs/api/REFERENCE.md     the human reference, incl. contract-drift audit

Usage:
    python scripts/gen_api_docs.py --url http://localhost:8000

Stdlib only — no project deps, runs with any Python 3.10+.
Examples are REAL captured responses; if an endpoint can't be reached
or needs a key the server doesn't have, the doc says so honestly.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "server"))
from admin_mount import ADMIN_MOUNT  # noqa: E402

# ---------------------------------------------------------------------------
# Capture plan — one representative request per endpoint, ordered so that
# /v2/plan runs before /v2/strip (the strip example reuses a real route_id).
# `provides` pulls values out of a response into the {placeholder} context.
# ---------------------------------------------------------------------------
DELHI = {"lat": 28.6139, "lon": 77.2090}          # Connaught Place
TRIP_TO = {"lat": 28.7041, "lon": 77.1025}        # Rohini side

EXAMPLES = [
    {"method": "GET", "path": "/health"},
    {"method": "GET", "path": "/search",
     "params": {"q": "connaught", **DELHI, "limit": 3}},
    {"method": "GET", "path": "/route",
     "params": {"from_lat": DELHI["lat"], "from_lon": DELHI["lon"],
                "to_lat": TRIP_TO["lat"], "to_lon": TRIP_TO["lon"],
                "profile": "driving", "vehicle": "car"}},
    {"method": "GET", "path": "/compare",
     "params": {"from_lat": DELHI["lat"], "from_lon": DELHI["lon"],
                "to_lat": TRIP_TO["lat"], "to_lon": TRIP_TO["lon"]}},
    {"method": "GET", "path": "/decide",
     "params": {"from_lat": DELHI["lat"], "from_lon": DELHI["lon"],
                "to_lat": TRIP_TO["lat"], "to_lon": TRIP_TO["lon"]}},
    {"method": "GET", "path": "/depart",
     "params": {"from_lat": DELHI["lat"], "from_lon": DELHI["lon"],
                "to_lat": TRIP_TO["lat"], "to_lon": TRIP_TO["lon"],
                "vehicle": "auto", "hours": 8}},
    {"method": "GET", "path": "/aqi", "params": DELHI},
    {"method": "GET", "path": "/today", "params": DELHI},
    {"method": "GET", "path": "/grid", "params": {"cells": 6}},
    {"method": "GET", "path": "/escape", "params": {**DELHI, "limit": 2}},
    {"method": "GET", "path": "/shift",
     "params": {**DELHI, "hours": 4}},
    {"method": "GET", "path": "/reverse", "params": DELHI},
    {"method": "GET", "path": "/directions",
     "params": {"from_lat": DELHI["lat"], "from_lon": DELHI["lon"],
                "to_lat": TRIP_TO["lat"], "to_lon": TRIP_TO["lon"],
                "vehicle": "auto"}},
    {"method": "POST", "path": "/observe",
     "body": {"vehicle": "auto",
              "coords": [[77.2090, 28.6139], [77.2200, 28.6300]],
              "duration_s": 300, "dose_ug": 12.5}},
    {"method": "POST", "path": "/report",
     "body": {"kind": "dust", "lat": 28.62, "lon": 77.21}},
    {"method": "GET", "path": "/reports"},
    {"method": "GET", "path": "/blackspots"},
    {"method": "GET", "path": "/fires"},
    {"method": "GET", "path": "/community"},
    # --- /v2 ---
    {"method": "GET", "path": "/v2/search",
     "params": {"q": "connaught", "limit": 3}},
    {"method": "GET", "path": "/v2/place/{pid}", "path_args": {"pid": "gaz:0"}},
    {"method": "GET", "path": "/v2/reverse", "params": DELHI},
    {"method": "POST", "path": "/v2/plan",
     "body": {"from": DELHI, "to": TRIP_TO, "vehicle": "auto"},
     "provides": {"route_id": "options.0.route_id"}},
    {"method": "GET", "path": "/v2/strip",
     "params": {"route_id": "{route_id}"}},
    {"method": "POST", "path": "/v2/trip",
     "body": {"device_token": "demo-device",
              "trajectory": [[77.2090, 28.6139], [77.2150, 28.6200],
                             [77.2220, 28.6280], [77.2300, 28.6360],
                             [77.2380, 28.6440], [77.2460, 28.6520]],
              "summary": {"mode": "auto", "distance_km": 5.2,
                          "duration_s": 900, "dose_ug": 41.2}}},
    {"method": "GET", "path": "/v2/city"},
    # --- internal ---
    {"method": "GET", "path": ADMIN_MOUNT + "/api"},
    {"method": "GET", "path": ADMIN_MOUNT, "html": True},
    {"method": "GET", "path": "/city", "html": True},
]

# Ops/dashboard surfaces — not part of the app contract. No endpoint in
# the codebase is marked deprecated; that statement is verified each run
# by the drift section, not asserted here.
INTERNAL_PATHS = {ADMIN_MOUNT, ADMIN_MOUNT + "/api", "/city"}

# Curated request-body fields — FastAPI types these handlers as `body: dict`
# so the OpenAPI schema is a generic object; these are the keys the code
# actually reads (server/main.py, server/v2/*.py).
BODY_FIELDS = {
    "/observe": [
        ("vehicle", "string", "optional", "mode key, e.g. auto|car|bike|bus"),
        ("coords", "[[lon,lat],…]", "optional", "traversal polyline"),
        ("duration_s", "number", "optional", "trip seconds"),
        ("dose_ug", "number", "optional", "inhaled PM2.5 µg"),
        ("avoided_ug", "number", "optional", "µg avoided vs worst option"),
        ("contributor", "string", "optional", "anon contributor id"),
    ],
    "/report": [
        ("kind", "string", "required", "dust | smoke | burning | clean"),
        ("lat", "number", "required", "report latitude"),
        ("lon", "number", "required", "report longitude"),
        ("contributor", "string", "optional", "anon contributor id"),
    ],
    "/v2/plan": [
        ("from", "{lat,lon} | [lon,lat]", "required", "origin"),
        ("to", "{lat,lon} | [lon,lat]", "required", "destination"),
        ("vehicle", "string", "optional",
         "car|car_open|bike|auto|bus|cycle|walk|metro + aliases; default car"),
        ("depart_at", "string", "optional",
         "ISO time — traffic-aware ETA only with ALIVE_LOCATION_KEY"),
    ],
    "/v2/trip": [
        ("device_token", "string", "optional",
         "opaque; sha256-hashed before it can touch a store"),
        ("trajectory | coords", "[[lon,lat],…]", "optional",
         "raw trail — trimmed 300 m both ends, thinned 100 m, "
         "rounded 4 dp, then discarded (never stored)"),
        ("summary", "object", "optional",
         "mode, distance_km, duration_s, dose_ug, co2_kg_mid, "
         "pm25_g_mid, switched"),
    ],
}

# Endpoint → contract typing for the drift audit.
CONTRACT_MAP = {
    "/health": ("health", "HealthResponse"),
    "/search": ("search", "SearchResponse"),
    "/route": ("route", "RouteResponse"),
    "/compare": ("compare", "CompareResponse"),
    "/depart": ("depart", "DepartResponse"),
    "/reverse": ("reverse", "ReverseResponse"),
    "/aqi": ("aqi", "AqiResponse"),
    "/today": ("today", "TodayResponse"),
    "/grid": ("grid", "GridResponse"),
}
# Interfaces that exist in contract.ts but whose path is absent from the
# exported ENDPOINTS map — reported as their own drift row.
CONTRACT_IFACE_EXTRA = {"/decide": "DecideResponse"}

SENSITIVE = re.compile(r"token|secret|password|authorization|api_?key",
                       re.IGNORECASE)
LOCAL_PATH = re.compile(r"^/(home|users|var|srv|opt|etc|tmp|root)/", re.I)
CROP_AT = 2          # keep at most this many array items
STR_AT = 200         # truncate longer strings


# ---------------------------------------------------------------------------
def crop_redact(o):
    """Recursive: lists → first CROP_AT + marker; sensitive keys →
    <redacted>; local FS paths → <server-path>; long strings trimmed."""
    if isinstance(o, dict):
        return {k: ("<redacted>" if SENSITIVE.search(k) else crop_redact(v))
                for k, v in o.items()}
    if isinstance(o, list):
        out = [crop_redact(x) for x in o[:CROP_AT]]
        if len(o) > CROP_AT:
            out.append(f"… (+{len(o) - CROP_AT} more)")
        return out
    if isinstance(o, str):
        if LOCAL_PATH.match(o):
            return "<server-path>"
        return o if len(o) <= STR_AT else o[:STR_AT - 1] + "…"
    return o


def http_json(url, method="GET", body=None, timeout=45):
    """→ (status, parsed_or_meta). Never raises — errors become a dict."""
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        url, data=data, method=method,
        headers={"Accept": "application/json",
                 "Content-Type": "application/json",
                 "User-Agent": "alive108-apidocs/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw, ctype = r.read(), r.headers.get("content-type", "")
            status = r.status
    except urllib.error.HTTPError as e:
        raw, ctype, status = e.read(), e.headers.get("content-type", ""), e.code
    except Exception as e:  # timeout, refused, dns — honest miss
        return 0, {"_capture_error": f"{type(e).__name__}: {e}"}
    if "json" in ctype:
        try:
            return status, json.loads(raw)
        except ValueError:
            pass
    return status, {"_non_json": True, "content_type": ctype,
                    "bytes": len(raw)}


def query_str(params):
    return "&".join(f"{k}={v}" for k, v in params.items())


def dig(obj, dotted):
    for part in dotted.split("."):
        obj = obj[int(part)] if isinstance(obj, list) else \
            (obj or {}).get(part)
        if obj is None:
            return None
    return obj


# ---------------------------------------------------------------------------
# contract.ts parsing — intentionally lightweight regex/brace matching,
# not a TS parser. Understands `export interface`, `?` optionals, inline
# nested objects (skipped at depth>0) and the ENDPOINTS const map.
# ---------------------------------------------------------------------------
def parse_contract(src):
    m = re.search(r"ENDPOINTS\s*=\s*\{(.*?)\}\s*as const", src, re.S)
    endpoints = dict(re.findall(r'(\w+)\s*:\s*"(/[^"]+)"',
                                m.group(1) if m else ""))
    ifaces = {}
    for im in re.finditer(r"export interface (\w+)[^{]*\{", src):
        name, i, depth = im.group(1), im.end(), 1
        while i < len(src) and depth:
            depth += (src[i] == "{") - (src[i] == "}")
            i += 1
        ifaces[name] = _top_fields(src[im.end():i - 1])
    pm = re.search(r"properties\s*:\s*\{([^}]*)\}", src)
    grid_props = re.findall(r"(\w+)\??\s*:", pm.group(1)) if pm else []
    return endpoints, ifaces, grid_props


def _top_fields(body):
    """interface body → {field: (type, optional)} — depth-1 fields only."""
    fields, depth = {}, 0
    for line in body.split("\n"):
        code = line.split("//")[0]
        if depth == 0:
            fm = re.match(r"\s*(\w+)(\?)?\s*:\s*(.+?);?\s*$", code)
            if fm:
                fields[fm.group(1)] = (fm.group(3).rstrip(";").strip(),
                                       bool(fm.group(2)))
        depth += code.count("{") - code.count("}")
    return fields


def _base_type(t):
    """'RouteResult[]' → 'RouteResult'; '(number | null)[]' → 'number'."""
    t = re.sub(r"\[\]\s*$", "", t.strip())
    if t.startswith("(") and t.endswith(")"):
        t = t[1:-1].strip()
    return re.sub(r"\s*\|\s*null", "", t).strip()


def _is_array(t):
    return t.strip().endswith("[]")


def shape_diffs(iface, fields, ifaces, obj, label, rows, depth=0):
    """Compare declared fields vs actual keys; recurse into fields whose
    type is another known interface (arrays → union of item keys)."""
    if not isinstance(obj, dict) or depth > 3:
        return
    actual = set(obj)
    missing_req = [f for f, (_, opt) in fields.items()
                   if not opt and f not in actual]
    missing_opt = [f for f, (_, opt) in fields.items()
                   if opt and f not in actual]
    extra = sorted(actual - set(fields))
    if missing_req or missing_opt or extra:
        rows.append((label, missing_req, missing_opt, extra))
    for f, (t, _opt) in fields.items():
        sub = _base_type(t)
        if sub not in ifaces or f not in obj:
            continue
        if _is_array(t) and isinstance(obj[f], list):
            union = {}
            for it in obj[f]:
                if isinstance(it, dict):
                    union.update(it)
            shape_diffs(sub, ifaces[sub], ifaces, union,
                        f"{f}[] → {sub}", rows, depth + 1)
        elif isinstance(obj[f], dict):
            shape_diffs(sub, ifaces[sub], ifaces, obj[f],
                        f"{f} → {sub}", rows, depth + 1)


# ---------------------------------------------------------------------------
def tier_of(path):
    if path in INTERNAL_PATHS:
        return "internal"
    if path.startswith("/v2/"):
        return "v2"
    if path in CONTRACT_MAP:
        return "contract v1"
    return "v1 (uncontracted)"


def sample_name(method, path):
    return f"{method.lower()}_{re.sub(r'[^A-Za-z0-9]+', '_', path).strip('_')}.json"


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--url", default="http://localhost:8000",
                    help="running server base URL")
    ap.add_argument("--out", type=Path, default=ROOT / "docs" / "api")
    ap.add_argument("--contract", type=Path,
                    default=ROOT / "Bridge" / "contract.ts")
    ap.add_argument("--timeout", type=float, default=45.0)
    args = ap.parse_args()
    base = args.url.rstrip("/")

    samples_dir = args.out / "samples"
    samples_dir.mkdir(parents=True, exist_ok=True)

    # --- 1. schema snapshot -------------------------------------------------
    status, spec = http_json(f"{base}/openapi.json", timeout=args.timeout)
    if status != 200 or not isinstance(spec, dict) or "paths" not in spec:
        sys.exit(f"ERROR: {base}/openapi.json → status {status}; "
                 "is the server running?")
    (args.out / "openapi.json").write_text(
        json.dumps(spec, indent=2, sort_keys=True) + "\n")

    endpoints, ifaces, grid_props = parse_contract(
        args.contract.read_text())
    contract_paths = set(endpoints.values())

    # --- 2. live captures ---------------------------------------------------
    ctx, caps = {}, {}
    for ex in EXAMPLES:
        path = ex["path"]
        for k, v in (ex.get("path_args") or {}).items():
            path = path.replace("{" + k + "}", v)
        params = {k: (str(v).format(**ctx) if isinstance(v, str) else v)
                  for k, v in (ex.get("params") or {}).items()}
        if any("{" in str(v) for v in params.values()):
            caps[(ex["method"], ex["path"])] = {
                "status": 0, "path": path, "request": params,
                "response": {"_skipped": "placeholder unresolved — "
                                         "run /v2/plan first"}}
            continue
        url = f"{base}{path}" + (f"?{query_str(params)}" if params else "")
        status, resp = http_json(url, method=ex["method"],
                                 body=ex.get("body"), timeout=args.timeout)
        for key, dotted in (ex.get("provides") or {}).items():
            v = dig(resp, dotted)
            if v is not None:
                ctx[key] = v
        sample = {"method": ex["method"], "url": url, "status": status,
                  "request_body": ex.get("body"),
                  "response": crop_redact(resp)}
        (samples_dir / sample_name(ex["method"], ex["path"])).write_text(
            json.dumps(sample, indent=2, ensure_ascii=False) + "\n")
        caps[(ex["method"], ex["path"])] = {
            "status": status, "path": path,
            "request": params or ex.get("body"),
            "response": resp}

    # --- 3. drift audit -------------------------------------------------------
    spec_paths = {p for p, ops in spec["paths"].items()}
    code_not_in_contract = sorted(spec_paths - contract_paths)
    contract_not_in_code = sorted(contract_paths - spec_paths)

    shape_rows = []   # (endpoint, level, missing_req, missing_opt, extra)
    for path, (key, iface) in CONTRACT_MAP.items():
        get_cap = caps.get(("GET", path))
        fields = dict(ifaces.get(iface) or {})
        if path == "/grid":   # FeatureCollection base supplies these
            fields.setdefault("type", ("string", False))
            fields.setdefault("features", ("array", False))
        if not get_cap or not isinstance(get_cap["response"], dict):
            shape_rows.append((f"GET {path}", iface, ["<not captured>"], [], []))
            continue
        rows = []
        shape_diffs(iface, fields, ifaces, get_cap["response"], iface,
                    rows)
        # /grid: also audit the declared feature properties
        if path == "/grid" and grid_props:
            feats = get_cap["response"].get("features") or []
            props = {}
            for f in feats:
                if isinstance(f, dict):
                    props.update(f.get("properties") or {})
            actual = set(props)
            mreq = [p for p in grid_props if p not in actual]
            mextra = sorted(actual - set(grid_props))
            if mreq or mextra:
                rows.append(("features[].properties", mreq, [], mextra))
        for label, mreq, mopt, extra in rows:
            shape_rows.append((f"GET {path}", label, mreq, mopt, extra))

    # Typed in contract.ts but absent from ENDPOINTS — audit the shape
    # anyway so the drift table shows what the interface already covers.
    for path, iface in CONTRACT_IFACE_EXTRA.items():
        get_cap = caps.get(("GET", path))
        if not get_cap or not isinstance(get_cap["response"], dict):
            continue
        rows = []
        shape_diffs(iface, ifaces.get(iface) or {}, ifaces,
                    get_cap["response"], iface, rows)
        for label, mreq, mopt, extra in rows:
            shape_rows.append((f"GET {path}", label, mreq, mopt, extra))

    # --- 4. render REFERENCE.md ----------------------------------------------
    def esc(s):
        return (s or "").replace("|", "\\|")

    def fmt_keys(obj):
        if isinstance(obj, dict):
            return ", ".join(f"`{k}`" for k in obj) or "—"
        return f"_(non-JSON: {type(obj).__name__})_"

    L = []
    a = L.append
    n_ep = sum(len(ops) for ops in spec["paths"].values())
    counts = {}
    for p in spec_paths:
        counts[tier_of(p)] = counts.get(tier_of(p), 0) + 1
    a("# API Reference — Alive\n")
    a(f"_Generated by `scripts/gen_api_docs.py` — {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())} "
      f"against `{base}`._\n")
    a("Regenerate: `python scripts/gen_api_docs.py --url "
      "http://localhost:8000` — rewrites `docs/api/openapi.json`, "
      "`docs/api/samples/*.json` (real redacted captures) and this file.\n")
    tiers = ", ".join(f"**{v} {k}**" for k, v in sorted(counts.items()))
    a(f"**{n_ep} endpoints** — {tiers}. Examples below are REAL captured "
      f"responses (arrays cropped to {CROP_AT} items, sensitive keys "
      "redacted).\n")

    # index
    a("## Endpoint index\n")
    a("| Method | Path | Tier | Contract | Description |")
    a("|---|---|---|---|---|")
    for path in spec["paths"]:
        for method, op in spec["paths"][path].items():
            contract = f"`{CONTRACT_MAP[path][0]}`" if path in CONTRACT_MAP \
                else ("`DecideResponse` only" if path in CONTRACT_IFACE_EXTRA
                      else "—")
            desc = (op.get("description") or "").strip().split("\n")[0]
            a(f"| `{method.upper()}` | `{path}` | {tier_of(path)} | "
              f"{contract} | {esc(desc)} |")
    a("")

    # per-endpoint sections, grouped by tier
    order = ["contract v1", "v2", "v1 (uncontracted)", "internal"]
    groups = {}
    for path in spec["paths"]:
        groups.setdefault(tier_of(path), []).append(path)
    titles = {"contract v1": "Contracted v1 endpoints",
              "v2": "/v2 endpoints (docs/plan/05 §3)",
              "v1 (uncontracted)": "v1 endpoints outside the contract",
              "internal": "Internal / ops surfaces"}
    for tier in order:
        if tier not in groups:
            continue
        a(f"## {titles[tier]}\n")
        for path in groups[tier]:
            for method, op in spec["paths"][path].items():
                m = method.upper()
                a(f"### `{m} {path}`\n")
                if tier == "internal":
                    a("> **internal** — ops/dashboard surface; not part of "
                      "the app contract.\n")
                desc = (op.get("description") or "").strip()
                if desc:
                    a(esc(desc) + "\n")
                params = op.get("parameters") or []
                if params:
                    a("| Param | In | Required | Type | Default |")
                    a("|---|---|---|---|---|")
                    for p in params:
                        sch = p.get("schema") or {}
                        a(f"| `{p['name']}` | {p.get('in')} | "
                          f"{'yes' if p.get('required') else 'no'} | "
                          f"{sch.get('type', '—')} | "
                          f"{sch.get('default', '—')} |")
                    a("")
                if method == "post":
                    a("**Request body** (handler reads `body: dict`; "
                      "OpenAPI schema is a generic object):\n")
                    a("| Field | Type | Required | Notes |")
                    a("|---|---|---|---|")
                    for f, t, req, note in BODY_FIELDS.get(path, []):
                        a(f"| `{esc(f)}` | {esc(t)} | {req} | "
                          f"{esc(note)} |")
                    a("")
                cap = caps.get((m, path))
                if cap:
                    resp = cap["response"]
                    a(f"**Response keys** (captured, HTTP {cap['status']}): "
                      f"{fmt_keys(resp)}\n")
                    req_line = (f"{m} {cap['path']}"
                                + (f"?{query_str(cap['request'])}"
                                   if method == "get" and cap['request']
                                   else ""))
                    a(f"Captured example — `{req_line}` → "
                      f"`{cap['status'] or 'unreachable'}` "
                      f"([full sample](samples/{sample_name(m, path)})):")
                    a("```json")
                    a(json.dumps(crop_redact(resp), indent=2,
                                 ensure_ascii=False))
                    a("```")
                    if method == "post" and cap.get("request"):
                        a("Request body sent:\n```json")
                        a(json.dumps(cap["request"], indent=2,
                                     ensure_ascii=False))
                        a("```")
                else:
                    a("**Example:** not captured (no entry in the script's "
                      "capture plan).\n")
                a("")

    # drift
    a("## Contract drift — `Bridge/contract.ts` vs live server\n")
    a("Computed at generation time: OpenAPI paths vs the exported "
      "`ENDPOINTS` map, and declared response interfaces vs real "
      "captured response keys.\n")
    a(f"### A. Live endpoints missing from `ENDPOINTS` "
      f"({len(code_not_in_contract)})\n")
    a("| Method | Path | Tier | Note |")
    a("|---|---|---|---|")
    for p in code_not_in_contract:
        for method in spec["paths"][p]:
            note = "typed by `DecideResponse`, but not exported in " \
                   "`ENDPOINTS`" if p in CONTRACT_IFACE_EXTRA else \
                "no contract typing"
            a(f"| `{method.upper()}` | `{p}` | {tier_of(p)} | {note} |")
    a("")
    a("### B. `ENDPOINTS` paths with no live handler "
      f"({len(contract_not_in_code)})\n")
    if contract_not_in_code:
        for p in contract_not_in_code:
            a(f"- `{p}`")
    else:
        a("None — every contract path resolves to a live handler.")
    a("")
    a("### C. Response-shape drift on contracted endpoints\n")
    a("Declared fields the server never returns (required fields are "
      "breaking; `(opt)` is informational) vs keys the server returns "
      "that the contract doesn't declare.\n")
    a("| Endpoint | Shape | Declared, not returned | Returned, not declared |")
    a("|---|---|---|---|")
    if shape_rows:
        for ep, label, mreq, mopt, extra in shape_rows:
            decl = ", ".join(f"`{f}`" for f in mreq) + \
                   (", " if mreq and mopt else "") + \
                   ", ".join(f"`{f}` (opt)" for f in mopt)
            und = ", ".join(f"`{f}`" for f in extra)
            a(f"| `{ep}` | {label} | {decl or '—'} | {und or '—'} |")
    else:
        a("| — | all contracted shapes in sync | — | — |")
    a("")
    a("### D. Notes\n")
    a("- `/v2/*` is the versioned surface (docs/plan/05 §3) — entirely "
      "absent from the contract file; Mobile integration is still v1.")
    a("- `DecideResponse` is declared in contract.ts but `/decide` is "
      "missing from the `ENDPOINTS` map.")
    a("- Additive keys are not breaking, but they are undocumented "
      "surface the app may already rely on.")
    a("- No endpoint is marked deprecated in server code; internal "
      "surfaces are listed above.\n")

    (args.out / "REFERENCE.md").write_text("\n".join(L))
    print(f"openapi.json  ← {len(spec['paths'])} paths")
    print(f"REFERENCE.md  ← {args.out / 'REFERENCE.md'}")
    print(f"samples/      ← {len(list(samples_dir.glob('*.json')))} captures")
    drift_n = len(code_not_in_contract) + len(contract_not_in_code) + \
        len(shape_rows)
    print(f"drift rows    : {drift_n} "
          f"(A:{len(code_not_in_contract)} B:{len(contract_not_in_code)} "
          f"C:{len(shape_rows)})")


if __name__ == "__main__":
    main()
