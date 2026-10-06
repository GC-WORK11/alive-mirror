# demo-reverify @ c1fbfb88 — live figures re-derived (lead, 2026-10-06 ~07:55 UTC)

| claim | live value | source curl | verdict |
|---|---|---|---|
| build | c1fbfb88 | GET /health | ✔ deployed |
| edges_priced | 903,058 (of 1,070,459) | GET /health | ✔ |
| field_age_s | 242–532s cycling | GET /health | ✔ fresh |
| dose gap O→D (India Gate→Huda) | 10.2 µg car → 365.0 µg walk = **35.8×** | POST /v2/plan | ✔ inside published ~33–36× |
| option count | 19 | same | ✔ inside published 19–24 |
| why-history survives deploy | **29 recorded builds, span 5.9h**, trend −60.0µg (88.4→28.5) | GET /v2/why | ✔ S3 reader working; history no longer dies on task swap |
| why drivers | trend PRIMARY 1.0 "easing off the earlier high"; stagnation secondary vc 2,253 vs ~3,000; 8 belt fires seen, modifier 1.14, evaluated-not-claimed | GET /v2/why | ✔ honest attribution |
| day_mean / GRAP | 66.4 µg/m³ → AQI 122, equivalent_stage 0 ("computed, not CAQM's declaration") | GET /v2/day | ✔ honest basis line |
| least-bad hour | ~59.2 µg/m³ at h+3 | GET /v2/day hours | ✔ plausible vs day_mean |
| landing hero | hnum tile LIVE chip + serif + provenance caption (hnumV hydrates client-side) | GET / | ✔ new grammar serving |
| web grammar live | landing .door/.dchip; city washHex day tiles; admin .kchip/.cap | GET /,/city,/admin | ✔ |
| breath ≈ cigarettes | landing copy "≈ 1 cigarette a day · 22 {noT}-day" (placeholder template hydrated client-side — VERIFY hi substitution non-broken) | GET / | ⚠ `${noT}` template literal seen in static HTML — check it hydrates to a number, not raw |

FLAGS: (1) `${noT}` in landing static markup — likely a template slot the JS fills; verify it renders a number, not the literal. (2) everything else inside published ranges — no drift >10%.
