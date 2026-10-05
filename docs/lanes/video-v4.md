# Lane: demo video v4 — cut4 at HEAD (dosimeter home + why + band bars)

Owner's deadline: Oct 8-11 hackathon video ≤3min, MUST show AWS console (~25s, owner films
himself — leave the placeholder). cut3 exists at `a5ab92d8`-era footage; the app's visible
surface has evolved (band-colored forecast bars, why-line on DelhiToday, press states,
strided reach veil on /city). This lane re-shoots at base/v2 HEAD and assembles cut4.

## Hard rules
- Every frame REAL: no mocked text, no staging, no copy-paste captions that aren't fetched
  or rendered live. Same evidence standard as cut3 (`docs/lanes/video-v3.md`, beats dir
  convention from prior lanes — find it under `video/` or the lane's own prior artifacts).
- App footage: drive the dev client on the iOS sim (macOS box) OR the fresh Android APK on
  an emulator if this box is Linux. The iOS sim on the lead's box had a stale binary —
  rebuild yours (`npx expo run:ios`, scheme `ALive108`, delete any stray `app.xcworkspace`
  first if the build errors on scheme). Point at LIVE AWS (raw ALB IP `http://65.2.28.40`
  if sim DNS wedges on the ELB hostname — see memory/skill notes).
- Web beats: /city hero + "the day, recorded" strip + why chip + reach veil (walk ≤25µg
  paints in ~2s — capture the paint) + admin engine room + self-grade tile.
- Numbers on tape must match what the live service returns at shoot time — fetch them,
  don't transcribe old ones (breath ≈3 cig/day currently, spread ~33-35×, skill thin —
  honest thinness is a BEAT: "it refuses to quote a MAE until it has its own receipts").

## Arc (same spine as cut3, tightened)
1. hero landing (live breath figure) ~15s
2. app cold-open → dosimeter home (≈µg today + THE MOVE + days ahead) ~30s
3. the dose gap: search→vehicle→compare sheet dose hero (car ~11 vs walk ~360-400µg; say
   the live ratio "about 33×", never a memorized number) ~35s
4. /v2/why + DelhiToday why-line ("the air is barely moving…" style — whatever's live) ~15s
5. reach veil paint + days-ahead strip ~20s
6. admin engine room + self-grade honest-thin beat ~20s
7. AWS console placeholder ~25s (owner inserts `80_aws.mov`)
8. close (privacy line: "only k≥3 aggregates ever leave") ~10s

Total target ≤2:50 including the placeholder. Deliverables: `cut4.mp4` uploaded +
beat timestamps + a one-line "what changed vs cut3" list. Report numbers actually fetched.
