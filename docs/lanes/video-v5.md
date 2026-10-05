# Lane: video-v5 — cut5 with the new dosimeter home + fixed flows

## Why
cut4.mp4 was shot on `b4a96d2` — since then the exact surfaces it
shows changed: (a) fresh-install hero is the DESIGNED sparse state
(ambient arc + "today's air where you are" + sample meter — no gray
bar), (b) compare→Start now launches the SELECTED option, (c) the
ledger dedupe is gone (real trips all land), (d) trip donations have
a plausibility floor. The demo video judges see must match the app
they'd open.

## Scope
- Read scripts/video/ + docs/plan/video-shotlist.md + cut4's
  assemble.sh — reuse the beats pipeline (screencast beats,
  `--rec` env, transcode-fps=30 then cut).
- Re-record ONLY the beats whose footage is stale: home cold-open
  (new sparse→populated hero), compare→pick→Start flow (pick now
  persists), receipt/ledger (dedupe gone). Keep the good beats
  (nav drive, reach veil, admin, why-line, community) from cut4.
- Keep total ≤2:50 with the 25s `80_aws` placeholder slot for the
  owner's console film (docs/plan/aws-console-shotlist.md).
- Use the apk-v4 build's APK (sibling lane 15047bf3 is building it —
  if not yet uploaded, build on the macOS recipe or use the iOS-sim
  release app on the SAME HEAD).
- Verify frame-by-frame: no skeletons, no stale surfaces, real live
  numbers only (curl the endpoints shown to sanity-check figures).
- Upload cut5.mp4 via upload_attachment + report →
  docs/lanes/video-v5-report.md (beat table: source, duration,
  what changed vs cut4).

## Hard rules
- Live API http://65.2.28.40 — GETs + /v2/plan + /v2/reroute only.
  If the recording does a nav trip, consent/share OFF first
  (no live donation).
- Never deploy. Commit any assemble/beat script changes to base/v2
  (pull --rebase).
