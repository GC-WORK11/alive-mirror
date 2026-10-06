# Lane report: welcome-loading — the first-breath cinematic (app) + boot strip (web)

**Date:** 2026-10-06 · **Verdict: SHIPPED — all beats verified on-device + in-browser, gates green, honesty contract proven** · Sim: iPhone 17 iOS 26.5 (`EDD9B083-63F1-44E6-9A7B-0A6964CC2561` — the brief's UDID `D0B64A8A…` no longer exists on this box; same device class substituted) · Server `localhost:8000` · Metro `:8081`

## What shipped

| Surface | Beats | Gate | Max length | Skip |
|---------|-------|------|-----------|------|
| `Mobile/src/screens/WelcomeScreen.tsx` | digit field → real live PM2.5 → band colour + word | `welcome_seen_v1` (document file, consent.ts pattern) | ~4.1s | tap / HW back |
| `server/landing.html` `#boot` | same three beats, same number | `sessionStorage.alive_boot_v1`, parse-time removal | ~2.75s | click/scroll/key |
| `server/admin.html` `#boot` | same, "engine room" voice | same key (once per session across the site) | ~2.75s | same |

The number is `/v2/city`'s `pm25_stats.mean` — the app's ambient `/aqi` read is the
honest fallback inside the film; on web the strip's own fetch with an 1.8s
deadline. Miss either way → the designed type-only frame, never a fake figure.

## App proof (iPhone 17 sim, `simctl io` captures — repo copies in `welcome-loading-shots/`)

| Beat | Evidence |
|------|----------|
| frame 1 — digit field + `reading Delhi's air…▌` | [app-01](https://app.devin.ai/attachments/9507e812-b170-4641-8c3e-21802960a3f4/final_banded.png) |
| resolved + banded — **80.8 µg/m³**, muted moderate, `live · field mean over the ncr lattice`, foot beat 2 | [app-02](https://app.devin.ai/attachments/e715ee91-5cae-4d1c-bf30-a53a17bec386/app_footfix.png) |
| honest degrade (backend down) — `no live air reading right now` + `nothing served — never faked` | [app-03](https://app.devin.ai/attachments/f09dfa2b-eeed-4a0b-92ba-827d02d946ba/app_degrade2.png) |
| once-only — second launch boots straight to home, no flash | [app-04](https://app.devin.ai/attachments/93485586-16d8-44b9-b373-8be9f1760d9a/app_second.png) |
| exit → onboarding armed (fresh install) | `app-05-exit-to-onboarding.png` (shots dir) |

- **Skip:** coordinate tap mid-film → overlay dissolved, `welcome_seen_v1.json` (`{"seen":true}`) written, home + armed onboarding behind it.
- **Once-only:** flag deleted → film replays; flag present → `welcomeSeen===false` never renders (null-gated until the flag reads, so no flash).
- **`clearAllData` re-arms** the film alongside consent — `settings.ts` calls `clearWelcomeSeen()`.
- Mounted last in `App.tsx` (zIndex 40) — sits above every sheet incl. the consent gate; exits into whichever gate applies (onboarding on fresh installs, home afterwards).

## Web proof (Chrome 154 via CDP, real-clock timed captures)

| Beat | Landing | Admin |
|------|---------|-------|
| digits frame | [web-01](https://app.devin.ai/attachments/85cc6006-721f-496e-b74c-e40a94915732/landing_400.png) | — |
| resolved + banded (**80.8** — same live mean) | [web-02](https://app.devin.ai/attachments/37ae38af-ec2b-4766-be65-37bbb2b4ec31/landing3_1900.png) | [web-05](https://app.devin.ai/attachments/398612b6-66e9-473e-baea-4ce2c6f60dc8/admin2_2000.png) |
| after — clean page ~2.75s | `web-03-landing-after.png` (shots dir) | `admin_3200` verified |
| second visit — strip never paints | [web-04](https://app.devin.ai/attachments/cff67a77-11f4-46b2-b7aa-e12108545555/landing_second_1600.png) | `admin_second_1500` verified |

## Hard rules audit

- **No fake number — PROVEN** (degrade capture; web shows `no live air reading right now` on fetch miss).
- **No neon — enforced on review:** admin initially read raw `CPCB_BANDS` hexes — pure `#FFFF00` on the near-black canvas read neon → now the muted product ramp `[#7AAB59 #C8B25A #D58C4A #B85442 #8F3C49 #6E3C54]` everywhere (the landing `BAND` table on landing, a local `MUTED` copy on admin).
- **No images/CDNs/deps — zero assets added;** type + the real number carry both surfaces. App reuses `band_*`/`cityLoading`/`cityNoField`/`onb_skip` strings (no `strings.ts` edit — lead-owned).
- **Reduce-motion** → static frame, no digit flipping, no cursor blink (app `useReduceMotion`, web `prefers-reduced-motion` media + JS gate).
- **Landing test constraints** — strip JS lives inside the existing first `<script>`; no `/admin`, `border-radius:999px`, `aether`, `ROUTE_ODS`, `TODO`, `FIXME`, placeholder strings added.
- **`tsc --noEmit` clean · `expo lint` clean · 119 server tests pass** (test_landing_serve 30, admin/community v2 89).

## Fixes made during verification

1. `react-hooks/refs` ×2 — render-time ref writes moved into `useEffect`; `finish` is now a stable `useCallback` reading ref mirrors.
2. `react-hooks/set-state-in-effect` — reduce-motion `setBanded` deferred one tick.
3. Web read-line flush-left at viewport edge → centered on the numeral's axis.
4. Admin band colour → muted ramp (see neon note).
5. App foot wrapped mid-word → two deliberate one-line beats; degrade provenance shortened so it can't wrap.

## Notes for the lead

- `welcomeSeen` loads beside `loadConsent` in App's boot effect; `onDone` → `markWelcomeSeen()` + drop. A force-quit mid-film replays it (flag writes on completion — intentional).
- The strip key `alive_boot_v1` is origin-scoped, so landing→admin navigation doesn't re-run it — matches "once per session".
- File ownership respected: WelcomeScreen.tsx (new), store/welcome.ts (new), App.tsx wiring, shell/settings.ts one call, landing.html, admin.html. No lead-owned files touched.
