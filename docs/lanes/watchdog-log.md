# Prod watchdog log — freeze watch, 2026-10-07

Lane: prod watchdog. Watch until ~20:00 IST (freeze cut + APK rebuild window).
Prod: `http://alive108-2699c171ddded465.elb.ap-south-1.amazonaws.com` (GET-only surface).
Cadence: /health + /v2/why(cause_note) every ~3 min (sampler → `~/watchdog-raw.log`),
/community + CloudWatch alarms + full surface check periodically.

Fail conditions watched: `field_age_s` > ~1200 s (field generator stall = demo-killer),
`field_stale`, HTTP != 200, cause_note empty, sha transition without verification,
CloudWatch alarms `alive108-field-age` / `alive108-field-emitter-dead` / `alive108-target-down` → ALARM.

## Entries (UTC)

### 2026-10-07 10:55 — baseline
- `/health`: `sha=698cf808`, `field_age_s=816`, `field_stale=false`, `field_refresh_in_s=84`,
  stations 52 (waqi+dpcc ok), fires 44, engine alive_core, routing 1,070,459 edges / 903,058 priced.
- `/v2/why` cause_note populated: "12 fires in the Punjab–Haryana belt — the wind isn't carrying it this way right now · city mean 59.4 → 46.7 µg/m³ over 5.6 h" (basis=measured).
- `/v2/city`: full payload, cause_note embedded, typical vs now −24%.
- `/community`: obs_total 44, contributors 24, avoided_ug_all 1278.9, top corridors populated.
- `/v2/usage` guest: 401 (expected).
- CloudWatch (ap-south-1): all 3 alarms `OK` — field-age, field-emitter-dead, target-down.
- Baseline verdict: prod healthy on 698cf808 (news-layer build). Sampler started ~10:56 UTC.

### 2026-10-07 11:36 — ~40 min mark, 13 samples
- Three full field cycles observed, ~15 min cadence: peaks 914→912→911, resets to ~180 on schedule.
- Stations dipped 52→46 between 11:14–11:24, self-recovered to 52 at 11:30 (transient feed flake, not a stall).
- cause_note present every cycle (83–124 chars, content rotates with new field builds — currently fires-belt note).
- CloudWatch re-check 11:36: all 3 alarms `OK`. `/community` unchanged (44 obs / 24 contributors / 0 active reports).
- Surface spot-check 11:19: `/`, `/landing`, `/admin`, `/city` all HTTP 200; landing title + boot overlay + 79 KB inline script intact, no control chars (dead-page trap clear).
- No sha transitions, no anomalies.

### 2026-10-07 11:42 — SHA TRANSITION `698cf808 → 43913dc0`
- Landed: landing-perf (47d7bff — webp+preload hero, dedupe boot fetches, /v2/city 60 s cache,
  cache headers, overlay count-in) + notify-e2e/admin-login docs commits. Field cycle continued
  through the deploy (age 730→197 on the new sha, refresh cadence intact, cause_note populated).
- Surface sweep on 43913dc0 — all pass:
  - `/` `/landing` `/admin` `/city` `/v2/city` all HTTP 200; landing payload 114 KB → 115.8 KB.
  - Landing live-verified in Chrome ~11:47: boot overlay clears, live number paints
    (35.1 µg/m³ · SATISFACTORY, cigarette-equiv line + dose row all live). Dead-page trap clear.
  - Landing inline JS: `node --check` PARSE-OK on the real script (65,857 B; the two
    `<script>`-inside-comment false matches are identical on old/new builds).
  - `/admin` login card present (operator token field + sign-in). `/v2/usage` guest → 401.
  - `/v2/why` cause_note populated: "12 fires in the Punjab–Haryana belt — the wind isn't
    carrying it this way right now".

### 2026-10-07 12:16 — ~80 min mark, 24 samples
- 5 field refresh cycles observed since watch start (~15 min cadence, all on schedule:
  resets at ~10:59, ~11:14, ~11:30, ~11:54, ~12:12). `field_stale` never true, max age 922 s.
- Stations 53→54 (recovered past baseline 52). cause_note populated every sample.
- CloudWatch 12:16: all 3 alarms `OK`. `/community` steady: 44 obs / 24 contributors / 0 active
  reports / latest_obs_age 315 min (donation feed idle — expected pre-demo).
- Deploy survived: field generator kept cycling through the 43913dc0 cutover, zero stall.
