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
