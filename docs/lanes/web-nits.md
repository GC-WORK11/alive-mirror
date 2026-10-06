# web-nits — fold web-cold-eye's flagged nits + accent canon

You are the web-nits lane for ALive-108 (AWS×WeMakeDevs Air track demo Oct
8–11). Repo: <owner>/Delhi-Air-108, branch base/v2, pull first.
Surfaces: server/landing.html, server/city.html, server/admin.html. Read
docs/lanes/web-cold-eye-report.md first — you own its remaining flags.

## Owner's bar (hard rules)
Light theme, muted expensive tones. NO neon/cyberpunk/retro/3D/decorative
SVG. NO lime-slime/chocolaty-green/cheap-yellow. Minimal words, honest
numbers. Components get color; the page stays classy.

## Tasks
1. **Accent canon**: three hues currently fight — admin --accent #2456D6
   (blue "engine room"), landing+/city sage #4D7C0F, app register forest
   #3A6844 (canon per docs/plan/register-card.md "web siblings track the
   register, not a fork"). DECISION (already made by lead): landing+city
   sage → forest #3A6844 so every web surface shares the register accent;
   admin keeps #2456D6 as the ONE documented backstage exception — record
   that exception inside register-card.md so it's canon not drift.
   Adjust hover/tint/wash derivatives so nothing looks off after the swap.
2. **390px label squeeze**: `.day-head`/`.dist-head` `<b>` qualifier wraps
   to an awkward right-shifted second line at phone width — fix (tighter
   tracking, shorter wrap, or block flow).
3. **`.detail` popover dock**: district popover pins bottom:170px —
   verify it clears the day tiles on 390px AND desktop; adjust dock if it
   overlaps the peek strip on real content.
4. Verify at 390px (CDP Emulation.setDeviceMetricsOverride, DSF 2 —
   plain --window-size is unreliable per the report) and 1280px; attach
   before/after captures. Zero features removed. No curl regressions:
   /, /city, /admin all 200 and render.
5. Commit; write docs/lanes/web-nits-report.md.
