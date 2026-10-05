You are the /city legibility lane for ALive-108. Admin and /community both got plain-language passes; /city is the public map page and still reads like an engineer wrote it. Owner's bar: a Delhiite who can't spell AQI should answer "what is this / what does it represent" on every element. KEEP THE LOOK — paper, serif, mono, hairlines, muted CPCB, honest-empty. Comprehension comes from WORDS + structure, not new chrome.

Repo: <owner>/Delhi-Air-108, branch base/v2 (pull latest — lanes push often). File: server/city.html (+ any /v2/city wire labels it renders). Live: http://alive108-2699c171ddded465.elb.ap-south-1.amazonaws.com/city.

HARD RULES
- Push code only — never deploy. GETs only on live.
- Nothing fake: every number still traces to the wire; honest-empty stays honest. If a term is load-bearing jargon (e.g. 'breath'), rename on the page AND explain once in plain words — never redefine silently.
- Do NOT touch the recorded strip / replay mechanics — they're new and correct; you may only clarify their captions/labels.

MANDATE
1. Cold-read /city top-to-bottom as a non-technical Delhiite. Write down every element failing "what is this": candidate suspects — the dose 'breath' figure (≈N cigarettes), cells vs district fills (two different things on one map), recorded·model·δ pills, the hourly strip squares, "▶ what happened" vs "watch the day" (two time controls?), outlook strip, µg/m³ numbers everywhere, confidence wording.
2. Plain-English pass, same pattern as admin (`gtiles .lbl` sub-lines) and community (`w` sub-lines): every stat/section gets a one-line "what this is" in Delhiite English. Section intros that answer "what am I looking at" in one sentence.
3. Unify the vocabulary with community's purge: street stretch not cell, "enough phones" not k≥3 (if it appears), plain band names stay (Poor/Moderate are CPCB-official — keep, but gloss once what the number means for a person: e.g. '82 µg/m³ — the air Delhi breathes this hour').
4. The recorded-vs-model flip is the honesty artifact — make it LEGIBLE: "what the model called vs what Delhi actually breathed, per hour" in one line a layperson gets.
5. Verify noscript + JS-off still clean.

Tests: server has pytest — run the tests touching city/landing serve markers and update any literal-string assertions honestly (`pytest -q tests -k 'city or landing'` at minimum; report if a broader suite assertion breaks on your copy change).

Report: cold-read fails list, diffs pushed, live-GET verification of every changed label.
