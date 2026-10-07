# Lane report: offline-walk — does `delhi-ncr-z9-13-r1` land on the canonical APK?

**Date:** 2026-10-07 · **Verdict: PACK DOES NOT LAND.** `OfflineManager.createPack` creates the
region row (name `delhi-ncr-z9-13-r1`, correct bounds/zooms) but downloads **zero tiles —
`region_tiles=0`, `region_resources=0`** because Mbgl-HttpRequest cannot parse the
`file://` style URL tileWarm passes as `mapStyle`. Everything else offline degrades
**honestly**: map renders only the ambient-cache viewport, search works from the bundled
gazetteer, plan/compare and DelhiToday fail with real error + retry, home shows last-known
numbers, reconnect repaints live. **Demo-morning plan: the basemap will NOT cover the venue
if WiFi is dead — only whatever the user panned over that day will render.**

Rig: fresh Linux box, KVM (`/dev/kvm` chmod 666), 31 GB / 8 cores. AVD `demo` = pixel_7,
android-35, google_apis, x86_64, launched
`-no-window -gpu swiftshader_indirect -no-snapshot-load -no-audio -no-metrics -no-boot-anim -memory 1536`.
`adb root` works (uid=0).

## Binary

- `alive108-c3f7e9e.apk` · size `137,133,148 B` · sha256 `4faa08ed99844371c7be42f3a0787809c51b0fbd6461338144631b99578d7c72`
  — matches canonical exactly.

## Pack verdict — the headline

**NO.** Three independent signals, all agree:

1. **sqlite (primary):** `/data/data/com.anonymous.app/files/mbgl-offline.db` final size
   `1,269,760 B`. `regions` has **1 row** — the pack —
   `definition={"style_url":"file:///data/user/0/com.anonymous.app/cache/alive-v2-style.json","min_zoom":9.0,"max_zoom":13.0,"pixel_ratio":2.625,"bounds":[28.2,76.8,28.95,77.9]}`,
   `metadata={"name":"delhi-ncr-z9-13-r1"}`. But `region_tiles = 0`, `region_resources = 0`.
   Expected ≈744 region tiles ≈27 MB — **nothing was ever downloaded into the pack.**
   (Full transcript: `offline-walk-shots/pack-evidence.txt`; raw db pulled to
   `offline-walk-shots/mbgl-offline-final.db`.)
2. **logcat:** `E Mbgl-HttpRequest: [HTTP] Unable to parse resourceUrl
   file:///data/user/0/com.anonymous.app/cache/alive-v2-style.json` — fires **once per app
   launch** (12:39:03, 12:58:14, …). The region is created, then the native fetcher rejects
   the `file://` style URL and the download never starts.
3. **db growth is ambient only:** 679,936 B at first map open → 1,081,344 → 1,269,760 B
   during ~5 min of panning at CP. Final `tiles` table = **8 rows**, all ambient viewport
   tiles: z8(182,106), z11(1463,853), z12(2926,1707/1708), z14(11705-11706,6830-6831) —
   Connaught Place only. `resources` = 9 rows (planet TileJSON, `ofm@2x` sprite json/png,
   Noto Sans pbfs). `alive-v2-style.json` (37,449 B) IS written to cache — tileWarm runs,
   the pack just never fetches.

Not fixed per lane rules — this is a verification lane. For the fixing lane: the
`style_url` in `createPack` needs to be a fetchable scheme (http(s) URL or
`asset://`), or the region must reference the same style source the live map uses;
`file://` is rejected by Mbgl-HttpRequest on this MapLibre Native build.

## Offline drive — works / drifts / broken

Network kill: `svc wifi disable` + `svc data disable`, `ping 65.2.28.40` →
`Network is unreachable`. (NB: that host drops ICMP even when online — the kill was
confirmed by route loss + app behavior, not ping alone.)

| Surface | Result | Evidence |
|---|---|---|
| Cold relaunch pill | **WORKS** — map screen shows "can't reach the server — trying again" then "offline — showing last known air · updated N min ago" | `13-offline-map-cp.png`, `32-map-back.png` |
| Map inside ambient cache | **WORKS** — CP viewport renders fully rendered streets/green areas at cached zooms | `13-offline-map-cp.png`, `offline-walk.mp4` |
| Map outside cache (Dwarka, east, whole-NCR zoom) | **BROKEN (pack symptom)** — ~2 pans SW → near-blank with faint overzoomed parents; zoomed-out NCR = empty canvas + user dot | `24-dwarka.png`, `28-z9-all.png` |
| Relaunch restores cached view | **WORKS** — force-stop → relaunch → CP map fully rendered offline | `32-map-back.png` |
| Offline search | **WORKS** — "India Gate" → bundled-gazetteer results ("India Gate Entry Kashturba Gandhi Marg / monument", "…Shahjahan Road"); persists to `places.json` recents | `41-results.png` |
| Plan / compare | **FAILS HONESTLY** — picking a result flies to destination pin, then sheet: "couldn't load the ways there — check the connection" + "try again". No fake options | `44-plan2.png` |
| Home numbers offline | **WORKS** — last-known hero + dose from `alive-cache/` daycurve/outlook; empty-dosimeter state worded honestly ("your count starts once the phone logs its first hours") | `46-home-offline2.png` |
| DelhiToday offline | **FAILS HONESTLY** — "can't reach the server — trying again" + "try again" (no cache for this surface) | `47-delhi-today.png` |
| Outbox | **N/A** — `outbox.json` never created (no donations queued in this walk; nothing to flush or lose) | `files/` listing |
| Recovery | **WORKS** — `svc wifi enable` + `svc data enable`: home repaints live (`outside ~54 → ~52`, dose 18 µg, pill gone) within seconds; DelhiToday reloads on tap of "try again" → "reading Delhi's air…" → full sheet (533 µg, pollutants, "updated 1 min ago") | `51-home-recovered.png`, `53-delhi-ok.png` |

## On-device files (evidence of the honesty paths)

`files/` after the walk: `daylog.json` (dose samples w/ lat/lon+amb/bz), `daysum.json`
(day-arc cache), `events.json`, `places.json` (search recents incl. the offline India Gate
hit — `tier:"t0"` bundled gazetteer), `settings.json`, `consent.json`,
`alive-cache/` (fetchCached envelopes: `v2_outlook` + `v2_daycurve` for the two geo fixes).
No `outbox.json` — nothing was queued.

## Zoom method that worked on this rig

Two-finger pinch via `sendevent` MT events reaches `/dev/input/event2` (getevent shows the
finger down/up) but the map **does not scale** — do not waste time on it. Working recipe:
`input tap 540 1200` then immediately `input swipe 540 1200 540 <y> 350` — swipe **up**
zooms out, swipe **down** zooms in (MapLibre quick-zoom). Plain double-tap zooms in.
Pan = normal `input swipe` drags.

## False-friends (verified, NOT reported as bugs)

- No basemap text labels at any zoom — SwiftShader/maplibre-native#3648. Geometry + colors render; judged by that.
- First taps eaten after sheet/keyboard settle — re-tap.
- `input text` drops spaces — KEYCODE_SPACE (62) between words.
- "Try out your stylus" system overlay appeared over the search field once — dismissed via Cancel.

## Rules kept

- No product code touched; no fake data; every claim above is backed by a sqlite count,
  logcat line, file listing, or screenshot in `offline-walk-shots/`.
- Media: mp4 2.0 MB (163 s), shots ≤1.5 MB each, raw db 1.3 MB, `pack-evidence.txt` transcript.
