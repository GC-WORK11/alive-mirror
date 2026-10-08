# vid-retakes lane — report (Oct-8)

Demo-video retakes. One continuous take each, Chrome real window (fullscreen), prod `http://65.2.28.40`. Film CDP-driven via playwright (`~/vidrig/drive_*.mjs`), screen-recorded, heads trimmed, h264 mp4.

**Design churn note:** landing iterated v10 → v11 → v13 → **v14** (final) while this lane waited; three earlier landing takes were filmed then discarded on HOLD orders. The shipped landing take is on v14 (`fb5cbb79`, deploy-21) — the build the owner launches with.

## Deliverables (final)

| video | file | duration | attachment URL |
|---|---|---|---|
| landing (**v14**) | `landing-v14-final.mp4` | 89.1 s | https://app.devin.ai/attachments/4ecc601b-c2a1-4ba8-8fb7-2f87b97a113f/landing-v14-final.mp4 |
| admin (restyled gate) | `admin-final.mp4` | 45.9 s | https://app.devin.ai/attachments/4299e88c-6829-45da-b86c-40e6ae3397dc/admin-final.mp4 |

## Landing take (v14) — beats verified on camera

| beat | evidence |
|---|---|
| load → hero | full-bleed India-Gate-in-smog photograph (`/hero-delhi-smog.webp`), "Delhi's air, counted." headline, "delhi ncr" mark, left-rail text links (home / the field / delhi / community) — NO navbar, NO boxes |
| live figure | rail readout "pm2.5 **87.7** µg/m³ · map 13–14 min fresh" — matches `/v2/city` mean (~87.7) at take time |
| numbered sections | margin index numbers 001 / 007 / 008 / 013 visible through scroll; serif body; thin hairline rules; bezel-free iOS shots (`ios-dose.png`, `ios-choose-priced.png`, `ios-feat-trips.webp`, `ios-feat-week.webp`) |
| unboxed data lines | "87.7 µg/m³ ×14.4 m³/day = ≈1,260 µg inhaled ≈ 4.0 cigarettes", "53 stations live · usual 86 · wind 6 km/h · 903k road segments priced", honesty line "over 69 recorded hours … missed by 22.8 µg/m³ on average · 510 pairs" |
| ruled districts leaderboard | ranked 1–29 thin-rule rows w/ colored boundary thumbs + aqi (NW Delhi 271 → East Delhi 152) |
| demoChip → real plan | `POST /v2/plan` → **200**; "connaught place → i.g.i." priced live on camera: Car (AC) 13.5 µg, Bike 37.3, Auto-rickshaw 40.3, Bicycle 165.7 · "5 options priced in 0.0 s" + dose-climb sparkline |
| /city | "Delhi NCR air, right now" — 88 µg/m³ Moderate · aqi 192 · 29 districts live (easiest 152 / heaviest 271); why-now / grap / parali-watch live cards (16 fires); colored district map |
| /community | "What Delhi breathed together — merged, never named." + live counts resolved: 31 phones · 54 trips · 9.3 µg today · 1,811 µg dodged · last trip 4.3 h ago |
| end frame | back on smog hero |
| zero-check | 0× `get the app` / `github.com` strings in served HTML; no boxes/cards rendered; no notifications/dialogs on camera |

## Admin take — beats verified on camera

| beat | evidence |
|---|---|
| mount URL → gate | warm restyled gate card (ALIVE / "engine room", black pill **sign in**) — no green capsule |
| entry | `#gatetok` (type=password) JS-filled → dots on camera, never typed; `form.requestSubmit()` → POST `<mount>/login` |
| boards unlock | gate hides; fires map (120 fires, belt ringed 16, source firms-public-csv), district-by-district map, forecast grading table (498 checks / 67 recorded hours, right-band 90.1% → 37.2%), header "updated … IST · refreshes itself every 30 s" |
| sign out | `#tokbtn` click → back to gate |

## Discarded takes

- `rec-ba186bdb` — landing on v10 (HOLD'd; superseded)
- `rec-42bd3af1` — admin take 1 (Chrome "Save password?" dialog; fixed via `/tmp/chrome-vid` profile prefs + `ctx.clearCookies()`)
- `rec-landing-v11-t1/t2` — landing on v11 (superseded by v13 order)
- `rec-1e5a236a` — admin take 2 (gate dwell ~2 s; reshot w/ 6 s dwell)
- `rec-landing-v14-t1` — stuck "GoogleUpdater" macOS banner top-right + unmaximized window after relaunch; dismissed + fullscreened, reshot

## FINDING (resolved by design)

`get the app` links → private `github.com/…/releases` → 404 for logged-out viewers — the v11 take caught it on camera. v14 removed all download/GitHub links, so moot on the final page. Preserved here for the record.

## Method notes

- Rig: Chrome `--user-data-dir=/tmp/chrome-vid` + CDP :29229, playwright-core drivers in `~/vidrig`; recordings trimmed from raw mkv → mp4 (accurate-cut `-ss` after `-i`).
- Wait-gates used: landing.html blob on `origin/base/v2` (v11 `ff976ec` → v13 `0c1559f`), then prod `/` HTML markers (v11 `hero-alive.webp`, v14 `Delhi's air, counted.` + zero app-refs ×2 consecutive reads).
- Live-data verification: rail pm2.5 87.7 = `/v2/city` `pm25_stats.mean` ~87.7 at take time; plan POST 200 observed; districts/fires/record counts rendered live on camera.
