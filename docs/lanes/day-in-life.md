# Lane: day-in-life — a Delhi day through the app (owner request)

## Why — verbatim owner ask
"record me a working of how does a app work in a daily life of
delhites and they use for and what changes from being a low numbered
map that wasnt bringing much change to something a big deal and
coolest things."

This is NOT the submission reel — it's the story video: one ordinary
Delhi day, told through the app, with the map app→life app contrast
made visible.

## The narrative (script it like a day, not a feature list)
Real screens, real data — every beat is the shipped app driving
itself. Rough spine (adjust to what the app actually shows):

1. **~8am, waking up** — open app: "what have I already breathed /
  what does today look like" — the morning card + day curve, the
  least-bad window it names.
2. **~9am, commute** — search work (e.g. CP → Gurgaon-class OD):
  the mode compare, the dose gap ("this ride home by car vs on
  foot = N×"), start nav, the ticking breath counter.
3. **~1pm, midday** — the move / today card, what the dose so far
  looks like on the day arc.
4. **~6pm, evening plan** — days-ahead strip: picking tomorrow's
  outdoor slot (gym/run/errand) off the forecast; the honest
  confidence caveat where it thins.
5. **~10pm, night** — symptom check-in (breath/eyes/energy),
  "stays on this phone — never uploaded" visible; ledger: the
  week's trips + where the dose came from.
6. **Close** — the contrast line: "a map app tells you minutes.
  This tells you what you breathed."

## Mechanics
- iOS-sim release build at HEAD (delhi-air-108-ios-testing skill:
  Release config, sim quirks). Mobile-web /city + /admin beats are
  NOT needed here — this is the phone story.
- Record each beat as clean segment footage (the video lanes'
  scripts/video/ beats pattern is reusable). Add minimal title
  cards ("8:04 AM — Lajpat Nagar, Delhi") via the assemble step —
  text only, no music, no fakery.
- Assemble one mp4 ~90-150s. Upload via upload_attachment.
- Frame-verify: every number on screen is real (curl the shown
  endpoint if in doubt). No skeletons, no stale states, consent
  OFF before any recorded nav (or ON only if the donation UI is
  part of the story — but bare POSTs to /v2/trip on live are
  banned, so keep consent OFF and let the receipt show
  "kept on this phone only" — that IS a story beat).

## Deliverable
- day-in-life.mp4 uploaded + link in report →
  docs/lanes/day-in-life-report.md (beat list, what each shows,
  any beat that couldn't be made honest).
- Commits to base/v2 (pull --rebase). Never deploy. GETs +
  /v2/plan + /v2/reroute only on live.
