# vid-retakes lane — report (Oct-8)

Demo-video retakes for the v10→v11 redesign. One continuous take each, Chrome real window, prod `http://65.2.28.40`. Film CDP-driven via playwright (`~/vidrig/drive_*.mjs`), screen-recorded, heads trimmed, h264 mp4.

## Deliverables

| video | file | duration | attachment URL |
|---|---|---|---|
| landing (v11) | `landing-final.mp4` | 77.5 s | https://app.devin.ai/attachments/575cefc6-be8b-4b1e-aa64-726a1f56e6f1/landing-final.mp4 |
| admin (restyled gate) | `admin-final.mp4` | 45.9 s | https://app.devin.ai/attachments/4299e88c-6829-45da-b86c-40e6ae3397dc/admin-final.mp4 |

## Landing take — beats verified on camera

| beat | evidence |
|---|---|
| load → v11 hero | giant `alive` (430 px) over full-bleed Delhi-dawn photograph (`/hero-alive.webp`), `delhi ncr` corner mark — no band-ink numeral in hero chrome (`#hnumV` lives in a `hidden` div now; live value moved to top bar: "pm2.5 80.0 µg/m³ · map 4 min fresh") |
| full scroll | "The next twelve hours" live forecast sparkline (71.3–104.0 µg/m³), "The city, kept" hourly record w/ `now` bar, 29 district boundary cards live-colored (Outer North Delhi 228 aqi …), app section, footer |
| demoChip click → real plan | `POST /v2/plan` → **200**; route draws Connaught Place → IGI on the air map; options priced live: Car (AC) 11.5 µg, Bike 31.4, Auto-rickshaw 33.9, Bicycle 141.3; "5 options priced in 0.7 s" |
| honesty numbers on screen | "over 67 recorded hours the forecast we served missed the air delhi got by 23.2 µg/m³ on average · 497 pairs" |
| /city | "Delhi NCR air, right now" 80 µg/m³ Moderate · aqi 167; why-now / grap / parali-watch live cards (16 fires Punjab–Haryana belt); district map |
| /community | live counts resolved on camera: 31 phones sharing · 54 trips · 9.3 µg breathed today · 1,811 µg dodged all-time · last trip 2.3 h ago |
| get the app → back | nav pill click → `github.com/<owner>/Delhi-Air-108/releases` → **404** (~1.2 s flash, logged-out view) → back to hero |

## Admin take — beats verified on camera

| beat | evidence |
|---|---|
| mount URL → gate | warm restyled gate card (ALIVE / "engine room", black pill **sign in**) — no green capsule |
| entry | `#gatetok` (type=password) JS-filled → dots on camera, never typed; `form.requestSubmit()` → POST `<mount>/login` |
| boards unlock | gate hides; fires map (120 fires, belt ringed 16, source firms-public-csv), district-by-district map, forecast grading table (498 checks / 67 recorded hours, right-band 90.1% → 37.2%), header "updated … IST · refreshes itself every 30 s" |
| sign out | `#tokbtn` click → back to gate |

## Discarded takes

- `rec-ba186bdb` — landing on v10 (HOLD'd; v11 spec superseded)
- `rec-42bd3af1` — admin take 1 (Chrome "Save password?" dialog covered boards ~half the take; fixed via `/tmp/chrome-vid` profile prefs + `ctx.clearCookies()`)
- `rec-landing-v11-t1` — landing on v11 but the get-the-app beat dwelt 3.2 s on the 404; re-shot with 1.4 s dwell
- `rec-1e5a236a` — admin take 2, gate dwell ~2 s; re-shot take 3 with 6 s dwell (final)

## FINDING (product, not video)

`get the app` links (nav pill, hero CTA, footer) all target `https://github.com/<owner>/Delhi-Air-108/releases`, which 404s for anyone logged out / without repo access — the repo is private. Every public visitor's primary CTA dead-ends. Suggest: public releases, a `/download` page on prod, or TestFlight/Play-store links. Visible at ~t 66–70 in the landing take (brief flash; kept because it's the true behavior).

## Method notes

- Rig: Chrome `--user-data-dir=/tmp/chrome-vid` + CDP :29229, playwright-core drivers in `~/vidrig`; recordings trimmed from raw mkv to mp4.
- Wait-gates used: landing.html blob on `origin/base/v2` (v11 landed at `ff976ec`), then prod `/` for `hero-alive.webp` ×2 consecutive reads.
- Live-data verification: top-bar pm2.5 80.0 = `/v2/city` `pm25_stats.mean` ≈ 80.8 at take time; plan POST returned 200.
