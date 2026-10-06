# Lane: video-v6 — cut6 matching the final binary

## Why
cut5.mp4 (2:48) predates vibe-polish `9b3abe4` (solid panes, numeral
hierarchy) and coldread `7facc34` ("µg (micrograms)", "least smoky
way", "counted", "about"). The video must show what a judge opens —
the final binary ships the new copy. Also /v2/day now serves the
persistence-blend forecast + GRAP line — the today/day beats show
stale values.

## Scope
- Read scripts/video/ + docs/plan/video-shotlist.md + docs/lanes/
  video-v5-report.md — reuse the beats pipeline verbatim.
- Re-record ONLY beats whose on-screen copy/surfaces changed:
  hero (µg gloss + solid panes), journey compare (new qualifiers),
  receipt ("about" copy), ledger rows, DelhiToday (blend forecast +
  grap-adjacent copy if visible). Keep cut5's good beats (nav drive,
  reach veil, admin engine-room, community, close).
- Use the iOS-sim release app at HEAD (same path as v5 — the
  delhi-air-108-ios-testing skill has the quirks; Release config,
  not Debug).
- ≤2:50 total incl. the 25s 80_aws placeholder (docs/plan/
  aws-console-shotlist.md — the owner's film job stays a placeholder).
- Frame-verify: every beat's numbers must be real (curl the shown
  endpoints to sanity-check), zero skeletons/stale surfaces.
- Upload cut6.mp4 via upload_attachment + report →
  docs/lanes/video-v6-report.md.

## Hard rules
- Live API http://65.2.28.40 — GETs + /v2/plan + /v2/reroute only;
  consent/share OFF before any recorded nav.
- No app code changes (this build is final). Never deploy.
- Commit assemble/report to base/v2 (pull --rebase).
