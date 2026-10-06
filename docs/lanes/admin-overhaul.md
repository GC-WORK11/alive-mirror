# Lane: admin-overhaul — the operator's read, not an OS

Owner's ask (verbatim essence): "admin website... should be easy for non-technical... all components easily readable... should not be a complex piece of crap or an operating system... so sexy, orgasmic and easy to present around."

## Files you own this pass
`server/admin.html` (the whole page), `server/landing.html` ONLY if a nav link needs fixing. Do NOT touch server/*.py route code — admin endpoints already serve; this is presentation + clarity.

## The bar
A non-technical person (a judge, a journalist, govinda's mom) opens /admin,
enters the token, and understands Delhi's air system in <60 seconds without
reading a manual. Think "mission control for people, not operators".

## Current sins (verify yourself, fix all)
- Information is operator-fluent: endpoint names, epoch ms, internal field
  names, JSON-ish dumps. Translate EVERYTHING to plain English:
  "stations online: 24 of 24" not "waqi_ingest: ok".
- Numbers without verdicts — every metric needs its honest qualifier
  (good/watching/down) — reuse the muted band ramp, never neon on dark.
- Sections are unlabeled plumbing — group into plain-English panels:
  "the air right now" (field state), "what the sensors see" (ingest health),
  "the fire belt" (FIRMS count + direction), "trips being planned" (demand).
- Keep every existing stat/button/token flow — NOTHING gets deleted,
  it gets *translated*. The boot strip stays.
- The page must stay self-contained (inline CSS/JS, no build step,
  no new deps, no external requests beyond the existing /v2/* fetches).

## Hard rules
- Light-on-dark is allowed ONLY where the page already is (admin is the
  dark "engine room" by design — keep it, refine it). Muted ramp only.
- Numbers stay honest — read from the same endpoints; no invented states.
- "operator sign in" chip stays the gate; after auth, the read begins.
- Works at 390px phone width (judges open links on phones).
- The reduced-motion + once-per-session boot strip behavior stays.

## Verify
- `python3 -m pytest tests -q` in server/ keeps passing (test_admin_serve
  and friends). Serve locally and screenshot: pre-auth, post-auth,
  390px. Attach shots in docs/lanes/admin-overhaul-shots/.
- Deploy is lead's job — commit to base/v2 only.

## Report
docs/lanes/admin-overhaul-report.md — what changed, which stats were
re-worded to plain English, shots.
