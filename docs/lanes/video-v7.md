# lane: video-v7 — cut7 on the overhauled app + web (owner's eyes only)

Read docs/demo-day.md + docs/lanes/video-v6.md (the prior cut's method + pitfalls) first. base/v2 only.

CUT6 predates the whole overhaul — cut7 must show: the NEW dosimeter home (paper doors + tinted chips), the overhauled landing (hero stat tile + door tiles + band-washed districts), /city (band-washed day tiles + why line), /admin (kchip + cap captions). All footage real — app on emulator (KVM pattern in docs/lanes/apk-drive-v5.md, or reuse apk-rebuild-v7's binary if its drive finishes and it shares the path), web via headless Chrome screenshot/scroll recording. Live backend http://65.2.28.40.

Video grammar: ≤3min, no fake data, the AWS-console slot stays a placeholder (owner films it himself — docs/plan/aws-console-shotlist.md). Owner's anti-list applies to any motion graphic: no neon/3D/SVG-noise.

Deliverables: scripts/video/cut7.mp4 rendered at scripts/video/assemble.sh (extend the beat list — keep beats dir structure), an attachment upload of the final mp4, and a report → docs/lanes/video-v7-report.md with per-beat frame-verification (what live number is on tape where). Commit brief-artifacts + beats on base/v2 (pull --rebase); the mp4 goes to attachments, not git.
