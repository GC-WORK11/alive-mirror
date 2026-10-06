# Lane: web-overhaul-v2 — landing + /city + /admin component redesign

## Owner's verdict (same mandate as app-overhaul-v2 — read that file)
"look so cheap and also too much complex it's like a fucking
operating system… too dull… so much mini words so much cringe…
without removing a single feature… minimalism and more functional…
individual designed components… colorful like components add little
liquid glassmorphism… don't even compromise over a single feature
or numbers we are showing."
Admin specifically (earlier verbatim): "i like the way it looks dont
remove them but the understanding is so complex so many numbers".

## Scope — all three web surfaces, component by component
- **Landing** — keep the hero+thesis, kill prose density: sections
  become scannable component rows (number + accent + one line),
  not paragraphs. The live number + recorded strip stay.
- **/city** — the comprehension layer already landed (plain lines
  under numbers) — this pass does the COMPONENT work: colorful
  designed tiles for the hero/breath/days-ago/why blocks, mini-words
  cut, one hero per viewport.
- **/admin** — keep the look (owner's words), fix comprehension at
  the COMPONENT level: stat tiles get color-coded accents + band
  semantics instead of prose walls; the "average of where" problem
  is solved by grouping + accent semantics, not more sentences.
  Provenance lines stay but shrink to chips/icons where possible.

## Rules
- Zero features/numbers removed; every wire block keeps its data.
- Light theme only. Shared design language lives in
  docs/lanes/register-card.md — extend it with the web component
  grammar (accent tiles, band semantics, glass tints); don't fork.
- Server suite gate after changes: cd server &&
  PYTHONPATH=core/build312:. .venv312/bin/python -m pytest -q tests
  (the HTML lives in server templates — tests cover wire shape).
- Screenshots per surface (computer tool Chrome at :29229 or plain
  screenshot) before/after in the report.
- Commits to base/v2 (pull --rebase). Never deploy — I deploy.
  Report → docs/lanes/web-overhaul-v2-report.md.
- Mobile has a sibling lane — coordinate via register-card.md,
  don't touch Mobile/.
