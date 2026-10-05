# Lane: mobile-web — every web surface on a phone viewport

Judges get sent links — they open them on phones, not laptops. landing `/`, `/city`,
`/community`, `/admin` were built and verified on desktop viewports. A broken phone
layout is a silent killer: the hero crops, the veil smears, stats overflow, taps miss.

## Work
1. Serve the built pages locally (same static files the server serves) AND check live
   http://alive108-2699c171ddded465.elb.ap-south-1.amazonaws.com in a phone-sized
   viewport (Chrome DevTools device emulation at 390×844 iPhone-14 + a 360×800
   Android size). Real screenshots, not "looks fine".
2. Audit per page, phone widths:
   - Landing: hero (art + copy + the live number), the day-recorded strip, sections,
     footer — any horizontal overflow, clipped text, off-canvas elements.
   - /city: the map canvas + veil + chips + "what happened" replay + why chip +
     days-ahead strip — do controls fit? do taps hit?
   - /admin: the tile grid — does it collapse sanely to one column? provenance lines
     readable? the FIRS map usable?
   - /community: consent explainer + counters.
3. Fix what's broken: mobile CSS (media queries exist? check), viewport meta, overflow,
   tap-target sizes (≥44px), font scaling. Keep the register (serif + mono + hairline
   + muted CPCB) — mobile fixes must not change the desktop look.
4. Report: before/after screenshots per page per width, issues found+fixed, and the
   one worst remaining mobile rough edge if any.

## Rules
- server/static + landing sources only; pull --rebase before pushes (lanes live in same
  files); never deploy; nothing fake — if a surface is intentionally desktop-only say so
  and add an honest note rather than a broken squeeze.
