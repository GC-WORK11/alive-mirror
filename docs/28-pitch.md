# Alive — The Pitch: judge psychology, six 4-line candidates, the failure-proof 3:00

*Deep-research deliverable. Reads alongside docs/20 (playbook), docs/11 (demo script v2), docs/22 (breakthroughs), docs/24 (design). Every external claim cited in §g; every product claim maps to shipped code or a named delta. Jargon rule: no "AQI / PM2.5 / µg / API / kriging" appears in any consumer-facing line below — those words live in the writeup and the why-expander, where technical judges go looking for them.*

---

## (a) Judge psychology — what actually wins, from the judges' mouths

Assembled from five named judges' own descriptions of their process (Devpost's panel: Square, Databricks, Google, NEAR, Atlassian), a judge's field notes from three hackathons in ten days, JetBrains' judging-table interviews (Stateshift, Scarf, OpenAI, Nebius, JetBrains), Amazon's own judge guide, and four winner postmortems. The claims below are theirs, not ours.

**The judging situation, as judges describe it.** A judge is not evaluating you against an ideal — they are ranking you against the last six videos they watched, inside a fixed window, while the demos blur together. Judges see **30–100+ submissions** and form opinions in the **first ~30 seconds**. Multi-stage funnels (screen → technical pass → top-30 panel) mean most projects die unseen except as a title and a video thumbnail. [S1, S2, S8]

**The ten findings, ranked by consequence for us:**

| # | Finding | Who said it | What it means for Alive |
|---|---|---|---|
| 1 | **"Whether the demo ran" is the single largest score differentiator.** A working demo "removes doubt, and doubt is what a judge is actually managing under time pressure." Slides of an ambitious thing lose to a working narrow thing "almost every time." | Kurbaitaev (3× judge) [S2] | Our submission IS a video — the bar is not "runs live on stage" but "footage that is unambiguously the product working." Real taps, drifting numbers, status-bar clock visible. §(c). |
| 2 | **Anchor first, story second.** "The teams that scored well opened with a plain declarative: this is a tool that does X for Y. The teams that lost ground opened with context." By the time the product appeared, "I had spent a third of the slot without knowing what I was looking at." | Kurbaitaev [S2]; Jono Bacon: "get your audience of judges sharing your frustration" [S3] | **Say what it is at 0:00, then the 8.2-year stat.** Current script (docs/11) opens with a mood line — the product name/category appears ~0:18. Fix in §(c). |
| 3 | **One "oh, this is possible now" moment beats a feature tour.** Bonnie Xu: build from "what's something I can build now that I probably couldn't have built before," and make the contrast obvious. MIT winner: sketch the wow moment first, build backward — "that moment was when the judges leaned forward." | OpenAI [S3]; samanvya.dev [S9] | Pick ONE jaw-drop: the same trip on foot = ~30× a closed car, on camera, live. Everything else is supporting cast. |
| 4 | **Pick the sentence you want a judge to repeat to another judge an hour later.** "Judges score partly on whether they can imagine explaining your project to someone else… the projects that survive that conversation are the ones with a one-line identity." | Kurbaitaev [S2] | The 4-line pitch (§b) exists to BE that sentence. A judge should be able to say: "the Delhi map that prices trips in cigarettes." |
| 5 | **Admitting a limitation raises scores.** "Teams that say nothing breaks lose credibility instantly, and teams that name the weakness gain more than they lose by naming it." Avi Press: "Judges can tell when you're talking around a feature that doesn't exist yet. Being honest about it reads as confidence." | Kurbaitaev [S2]; Scarf [S3] | Our confidence-drops/nearest-sample/MAE badge is not a caveat — it's the credibility asset. Put the honesty beat in the video itself (§c). |
| 6 | **"Would I want to install it?" is the silent criterion.** Atlassian judge: "Is that finished product something that I would want to use?" NEAR judge: "do they see the problem behind the solution… if they sell it, if I see the fire in their eyes." | Marusiak, Yarotska [S1] | This is the "I want this to exist" feeling — it comes from personal motive (your lungs, your commute), not civic scale. Lead with the personal; the sensor-network moat is the close, not the open. |
| 7 | **Rewards track the sponsor's business goals, not the rubric.** "Judges did not necessarily reward superior technical output… the rewards were about the sponsor and their business goals." Rules are a filter, not a sort. | Ray Deck, 5× winner [S12] | AWS-sponsor hackathon → AWS on camera is both a rule and the sponsor story. Our Fargate/NLB/S3/CodeBuild/Secrets-Manager-with-war-stories IS the sponsor's desired narrative (Well-Architected fluency, frugal ~$36/event-window bill [docs/18]). |
| 8 | **The demo hygiene checklist is scored.** "Mock everything you can… Pre-fill the data. Mock the slow API call. Remove every place the demo could stall." TechCrunch/Devpost: skip mundane flows; every click should move toward the aha. | Nebius [S3]; TensorHack [S8] | Pre-warm map tiles, pre-type FROM/TO via paste (simctl pbcopy — docs/11), FROM defaults to current location. No loading spinner survives the cut — cut it in the edit, don't narrate it. |
| 9 | **Over-indexing on one criterion loses.** Square judge: teams that are "extremely back-end heavy with almost no front end" or that nail one criterion and miss the rest get scored down. The rubric compresses; balance across all five. | Moot [S1]; Kurbaitaev [S2] | Rubric map (docs/20 C.1) stays: idea+impact / AWS / design / execution / video all need a named beat. |
| 10 | **Enthusiasm and storytelling are scored signal.** "Presentation and storytelling matters and it can be a huge part of your success." Judges sense enthusiasm — "the teams that practiced it look like they practiced it." | Bajza-Terlouw [S1]; JetBrains panel [S3] | VO recorded separately, warm + unhurried. A person who clearly built this to breathe easier in Delhi beats a neutral narrator. |

**Two prior-art anchors for "I want this to exist" > "impressive tech":** First Commit's winners (same rulebook, 3 weeks ago) were a voice companion for aging parents and an agent for the 3 AM page — visceral personal problems, not platform breadth [docs/20 §B.1]. The SIH winner's own postmortem: "We won not because we had the best code — because we solved the actual problem while everyone else built impressive tech that missed the point… a working ugly prototype beats a beautiful non-working presentation." [S16]

---

## (b) The 4-line plain-English test — six candidates, ranked

Constraints applied literally: exactly 4 lines; a Delhi rickshaw driver gets every line; one provable, live-demoable wow in each; no jargon; every claim already shipped (endpoint/file cited) or named as a small delta. Rank criteria: legibility at 10-second skim × strength of the provable wow × differentiation vs. the 200 AQI-dashboard clones × honesty risk.

### Rank 1 — "The receipt" (the complete arc; video opener)

> Delhi's air takes years off a life — one commute at a time.
> Type where you're going; every way there gets priced in what your lungs pay.
> Same trip, same minute: your feet can cost you thirty times a closed car.
> When you arrive, it receipts what you just inhaled — in cigarettes.

- **Why first:** the whole product in four lines — problem (AQLI-anchored, "takes years" is deliberately less precise but unfakeable), mechanism (dose pricing, no jargon), the provable wow (live dose card: 89.7 vs 2.9 µg measured Oct 1, ~31×), and the arrival **dose receipt** — shipped at ~80 m auto-arrival (`App.tsx` receipt card: "trip done · N µg · 🚬 strip · the smokiest way would have cost you N µg more"). Every line films.
- **Rickshaw test:** passes — "what your lungs pay," "receipts."
- **Judge test:** the repeat-to-another-judge sentence is embedded: *prices trips in what your lungs pay*.

### Rank 2 — "Same trip, thirty times" (the jaw-drop line; mid-video punch)

> Same start. Same end. Same traffic outside your window.
> In an open auto you breathe several-fold what the man in the closed car beside you breathes.
> On foot, that gap can be thirty times — the app's live count, not a slogan.
> It ranks every way there by breath, so the cheapest ride is one tap.

- **Why second:** the single sharpest provable number we own, and it's about HIS job — the rickshaw driver's own trade. Auto-vs-closed-car gap on the verified commute ≈ 3× (8.6 vs 2.9 µg); the mode science says up to 5.3× rickshaw-vs-metro and 28.2× walk-vs-metro per km (Goel et al., docs/23 #56) — "several-fold" and "thirty times" are both defensible. `GET /compare` shows it live.
- **Risk:** none on honesty if we keep "can be" — re-verify day-of; VO says "about thirty."

### Rank 3 — "The cigarette counter" (the personal loop)

> You can't see what a Delhi trip does to your lungs. Your phone now counts it.
> Every ride adds up — the auto, the metro, the walk — into one number anyone can read.
> That number is cigarettes. The only smoke-count that needs no explaining.
> Week's end, it shows you the ones you dodged.

- **Why third:** the most sticky unit (Sh*t I Smoke went global on it — prior art is real but our ledger + **avoided** number is the upgrade [docs/22 §f.5]). "The ones you dodged" = the shipped `avoidedUg` ledger field (167.9 µg verified Oct 1). Personal motive first — the Sensor.Community lesson (docs/22 §d).
- **Risk:** closest to derivative of the six — that's why it can't be the opener; it rides after the routing wow.

### Rank 4 — "The cheap hour" (the utility hook)

> Delhi piles its smoke up before dawn and thins it out by noon.
> The same trip at eight and at twelve-thirty can cost you a fifth of the smoke.
> The app knows the cheap hour for your trip — and nags you when it comes.
> One tap sets the reminder; the phone does the rest.

- **Why fourth:** the most *actionable* line — a thing a person can do tomorrow morning for free. `/depart` verified −83% on the Oct-1 uniform field (a "fifth" understates it; honest); the iOS notification permission prompt films beautifully and is deterministic — can't fail on camera. Boundary-layer physics is the mechanism (`forecast.py`, docs/10).
- **Risk:** least emotional of the six; it's the install-trigger, not the heart-grab.

### Rank 5 — "The city measures itself" (the moat; the close)

> A hundred government machines can't see your lane.
> Every phone running this takes a reading just by travelling through it.
> Three commutes down a street and it becomes a measurement; enough phones and the map learns a lane.
> Delhi never got a sensor on every street. It got people. This joins them.

- **Why fifth:** the civic-moat vision — strongest with sponsor/Amazon judges, weakest on the rickshaw test ("a reading" is near-jargon). **Shipped:** corridor cells need ≥3 fresh traversals to count as a measurement — `community.py` literally implements "one journey is an anecdote, a corridor of commutes is a measurement" (72h freshness, corridor→field Bayesian feedback live). `/city` surface renders the field breathing + corridor measurements.
- **Risk:** cold-start — community counts are our own traversals today; honest framing "the flywheel every trip feeds," never fake adoption numbers (docs/20 §e.8).

### Rank 6 — "It shows its work" (the skeptic-killer; writeup lede)

> Other apps show one number for a whole city and call it "now."
> Ours shows where every number was born — a hundred real machines, and the kilometre to your nearest one.
> When it's guessing, the guess wears a label.
> Then it counts your cigarettes anyway — honestly.

- **Why last as a pitch, first as a trust weapon:** zero emotional hook, but it is the line that disarms technical judges — judge finding #5 made concrete. **Shipped:** `field.station_readings` count + nearest-sample distance + confidence that visibly drops + LOO calibration MAE 8.8 µg/m³ shown on camera (README/docs/10). Put it in the honesty beat (§c) and the README/writeup first line, not the cold open.

**Recommended stack (consistent with docs/20 §d, now tied to shipped wows):** opener = #1 · jaw-drop = #2 · loop = #3 · utility = #4 · moat close = #5 · trust card + writeup lede = #6. The repeat-to-another-judge sentence across all six is the same: **"the Delhi map that prices trips in breath."**

---

## (c) The ≤3:00 arc that survives a bad-network day

**The reframe.** This hackathon has *no live demo* — "the video is what the judges see" [rules]. So "surviving network failure" means two things: **(i) the recording must not depend on a good network day, and (ii) the footage must read as live anyway.** The fix is that **recording order ≠ playback order**: shoot the network-dependent beats first while the field, tiles, and backend are hot; shoot the deterministic beats any time; edit to the judge-psychology order.

### The playback arc (what the judge sees)

| Time | Beat | Pitch line | On screen | Failure class |
|---|---|---|---|---|
| 0:00–0:08 | **Anchor, then stat.** "This is Alive — a Delhi map that prices every trip in breath, not minutes. Delhi's air takes years off a life." | #1 L1–2 | Live field drifting over the mono map | needs field+server |
| 0:08–0:38 | **Golden path.** Karol Bagh → India Gate; search, route painted by dose; the dose card: closed car ~3 vs on foot ~90 — "thirty times, live." | #2 | Phone/sim, real taps | **money shot — record first** |
| 0:38–0:55 | **The physics one tap away.** Tap auto → route repaints crimson; why-expander (breathing-zone × exertion, live field). | #2 tail | why-expander | same take as above |
| 0:55–1:18 | **The receipt + the ledger.** Auto-arrival receipt ("N µg · 🚬 · the smokiest way cost N more"); ledger: today's cigarettes + the ones you dodged. | #1 L4, #3 | nav → receipt → ledger | receipt needs a recorded nav run — shoot once, reuse |
| 1:18–1:38 | **The cheap hour.** "Leave at 12:30 — a fifth of the smoke" → remind-me → **real notification permission on camera** → ambient glance. | #4 | depart screen → iOS prompt | deterministic — shoot any time |
| 1:38–1:58 | **The moat.** Corridor layer + "measured by N commutes"; `/city` breathing surface (kriged field drifting with wind, cigarette strip). | #5 | corridor map → /city | needs field+server |
| 1:58–2:16 | **AWS, on camera (rule).** ECS service RUNNING → NLB DNS → `/health` JSON → S3 community bucket → Secrets Manager → CodeBuild. "~$36 for the whole event window, inside the credits." | sponsor beat | console tabs, 12–15 s + 4 s arch card | console-only — indestructible |
| 2:16–2:40 | **It shows its work.** Tap a thin-field point → confidence visibly drops, "nearest sample 1.3 km"; MAE badge. "When it's guessing, the guess wears a label." | #6 | app + calibration block | needs field+server |
| 2:40–3:00 | **Impact close.** "On Delhi's worst corridors that's up to half the smoke — same trip. Every trip the map gets truer." End card: name, one-liner, repo, live URL. | #5/#1 | end card | indestructible |

Beat logic vs docs/11: **(1) anchor-first** — the declarative is now the first sentence (finding #2); **(2) the receipt is promoted** — breakthrough #1 shipped since docs/11 was written and it's the purest "oh, that's possible now" moment (finding #3); **(3) AWS moved to ~2:00** — deep enough that skimmers who bail early still hit it in the first two minutes, and it's console footage so it can't fail; **(4) honesty beat lands as second-to-last** — the leave-behind is "trust us," not "admin dashboard" (findings #5, #6).

### The recording order (what we shoot first)

1. **Golden path + why-expander** — while the field is fresh, tiles cached, backend hot. 3 takes minimum. This is the only take that can't be faked or reshot lazily.
2. **Moat + honesty beats** — same network dependency, same session.
3. **Ledger + receipt** — receipt from a real nav run; record once, splice.
4. **AWS console** — independent of everything; shoot between takes.
5. **Deterministic beats** (depart → notification → ambient; end cards) — any time.
6. **VO last** — never network-dependent; numbers spoken in ranges ("about thirty times", "a fifth") so field drift between takes never contradicts the narration.

### The fallback ladder (if recording day goes wrong)

- **NLB/region flakes** → run identical shots on `server/.venv312/bin/uvicorn` localhost (same code, same data files). Never fake the URL on camera — the AWS proof is the console footage, which is separately real.
- **Map tiles flake** → the bundled 26.5k-POI gazetteer keeps search instant (<10 ms local); pre-warm the tile cache on the exact viewport before rolling; cached tiles keep the mono map drawn offline.
- **Field goes flat (uniform day)** → narrate it as honesty: "a flat field day — the app shows one color because that's the truth." A day with visible gradients is better for the repaint shot; if unavailable, the dose-card numbers still carry the wow.
- **Numbers drift between takes** → keep every shot of one trip in the same take-set; re-curl `/compare` immediately before rolling (docs/11 curl); VO ranges, never frozen figures.
- **Any stall** → cut in the edit. Never narrate a spinner, never speed-ramp a load — reads as hiding (finding #8).
- **Whole-day insurance** → the edited backup cut from the last green day is the floor (Kurbaitaev: "record a screen capture as insurance — wifi fails at most events I judged").

**Upload:** unlisted YouTube, opens signed-out, ≤3:00, submitted **Oct 10 evening IST** — deadline hour still TBD; YouTube links work while processing finishes [S5, S6].

---

## (d) Anti-patterns — what makes judges distrust, mapped onto our demo

| Anti-pattern | What judges actually see | Evidence | Our current exposure | The fix |
|---|---|---|---|---|
| **Anchor-late opening** | "a third of the slot without knowing what I was looking at" | Kurbaitaev [S2] | docs/11 opens with a mood line; product named ~0:18 | Declarative at 0:00 (§c) |
| **Hardcoded-data vibes** | frozen round numbers, identical values across shots, "Test User" names → "if this is their demo, what does their product look like?" | Demo-env autopsy [S14]; forensic skepticism (frame-by-frame catch) [S15] | LOW but nonzero: on flat-field days identical numbers across takes *can* look frozen | keep station-age + "nearest sample 1.3 km" chips visible; show the drift, don't hide it |
| **"Trust me" claims** | claims with no mechanism on screen read as vapor | Devpost judge panel [S1]; "won on evidence" postmortem [S17] | LOW — why-expander + calibration exist | keep them on camera; VO never asserts without a mechanism in the same breath |
| **Dashboards of unexplained numbers** | grids of numbers nobody asked for; "nice video + weak description still loses" | Square + Google judges [S1] | MEDIUM: `/admin` + `/city` are number-dense | each gets exactly one VO line of meaning; prefer cigarette-glyph surfaces over µg tables |
| **Feature tour** | breadth reads as no judgment: "a platform in 36 hours reads as a team that did not make decisions" | Kurbaitaev [S2]; WeMakeDevs rubric [rules] | HIGH — 15+ endpoints exist | golden path + 2 support beats only; §e cut list |
| **Fake precision** | point estimates where the data is thin read as either fake or naive | judge "name the weakness" finding [S2] | LOW — uncertainty bands shipped (krige σ → dose bands) | put the band + confidence-drop ON camera (honesty beat) |
| **Sponsor named, not shown** | literal DQ + lost criterion | rules | ZERO once console beat filmed | §c beat 7 |
| **Slides that fill time** | "Slide decks… do not persuade. The only slide I ever wanted was one screenshot of the thing running." | Kurbaitaev [S2] | LOW — we use ≤3 cards | keep cards to cold-open, arch (4 s), end |
| **Demo stalls / typing lag** | dead air reads as broken | Nebius [S3]; TechCrunch via TensorHack [S8] | MEDIUM — sim typing drops chars | pbcopy paste (docs/11); pre-warm; cut stalls in edit |
| **Polish that outscales the backend** | "past a point it makes me wonder where the backend time went" | Kurbaitaev [S2] | our UI is Google-Maps-grade — could read as template | show shots only our system produces: dose-repaint, auto-arrival receipt, honest band |
| **Onboarding friction** | login/accounts are mundane flows | TechCrunch/Devpost [S7, S8] | none — no auth | keep it that way through demo week |
| **The mystery repo** | "A messy repo says 'I finished 5 minutes ago.'" | Amazon Nova guide [S4] | README already judge-clickable (live URLs) | keep live-URL section; add video-GIF hero |

---

## (e) What to CUT from the current presentation

Against docs/11 (script) and docs/20 §C.2 (beat map). Features stay in the repo — this is a video cut, not a product cut.

| Cut | Where it was | Why |
|---|---|---|
| `/escape` (where to breathe) | docs/11 ambient beat tail | third-best utility; can't afford a 4th feature beat inside 3:00 (finding #3) — B-roll only |
| `/shift` (gig-driver 8-hr dose) | not scripted, exists | powerful number (1.1–1.5 cig-eq/shift) but it's a second persona mid-video — moves to **writeup + README live URL** where it costs nothing |
| `/decide` (safety-first ranking) | README | second ranking engine = explanation tax; keep as judge-clickable URL |
| FIRMS fires + DTP blackspots layers | new commits | map furniture that doesn't advance the one commute — off video, in repo + writeup |
| `/admin` ops board as a section | docs/20 beat 1:55–2:20 | internal-console vibes, unexplained numbers (§d); compress to a 3-s insert inside the moat beat |
| "125-station × decade climatology" stats | README/health | meaningful to a technical reader, noise on camera — writeup only |
| OTP2/GTFS transit depth | docs/20 beat | metro already shows station-to-station names; the routing-engine war story is writeup material |
| Endpoint alphabet (`/compare?from_lat=…`) | README table | never show query strings on video — reads as API demo, not product |
| The IST-vs-UTC climatology gotcha + NLB target-group race | internal | perfect "what fought back" writeup stories; wrong register for the 3:00 |
| Problem-stat-before-product opening | docs/11 0:00–0:18 | violates anchor-first (finding #2) — replaced by pitch #1 L1–2 |
| Any "we will/would/could" | VO | every verb in the video is present-tense shipped; futures live only in the end-card vision line |

---

## (f) The one-paragraph verdict

Judges rank relative, skim hard, and reward: (1) a declarative anchor in the first sentence, (2) one working golden path with a single provable wow, (3) footage that removes doubt rather than producing it, (4) a weakness named out loud, and (5) the sponsor's own story told back to them on camera. Our winning version: open on pitch #1, drop the ~30× live dose card inside 40 seconds, receipt the trip in cigarettes, prove the cheap hour, flash the citizen grid, show AWS on the console, end on the honesty beat + the half-the-smoke number. **The pitch the judges repeat is: "the Delhi map that prices your trip in breath — and receipts it in cigarettes."**

---

## (g) Sources

**Judge psychology**
1. Devpost — *How to win a hackathon: Advice from 5 seasoned judges* (Square, Databricks, Google, NEAR, Atlassian): https://info.devpost.com/blog/hackathon-judging-tips
2. Kurbaitaev — *What Judges Actually Score: Notes From a Year of Hackathon Judging* (MLH×DigitalOcean, Sports World Cup, Aethera Hacks): https://dev.to/kurbaitaev/what-judges-actually-score-notes-from-a-year-of-hackathon-judging-3p4l
3. JetBrains — *How to Win a Hackathon: Notes From the Judging Table* (Bacon, Press, Xu, Lowenberg, Wortmann): https://blog.jetbrains.com/ai/2026/06/how-to-win-a-hackathon-notes-from-the-judging-table/
4. Amazon Nova — *Level Up Your Build: How to Wow the Judges* (golden path, 30-s UI rule, pre-recorded fail-safe): https://amazon-nova.devpost.com/updates/42214-level-up-your-build-how-to-wow-the-judges

**Video craft**
5. Devpost Help — *Video-making best practices* (screencast, elevator pitch first seconds, upload early): https://help.devpost.com/article/84-video-making-best-practices
6. Devpost — *6 Tips for making a winning hackathon demo video* (community winners; script early, upload-link trick, kids-setting quirk): https://info.devpost.com/blog/6-tips-for-making-a-hackathon-demo-video
7. Devpost — *How to present a successful hackathon demo* (scene → working demo → sell the dream; skip mundane flows): https://info.devpost.com/blog/how-to-present-a-successful-hackathon-demo
8. TensorHack — *Hackathon Demo Guide* (AngelHack 30–100 demos/30-s opinions; TechCrunch order; fallback-path rule): https://tensorhack.com/guides/hackathon-demo-guide

**Winner postmortems / failure evidence**
9. Samanvya Tripathi — *How We Won 1st Place at the MIT LLM Hackathon* (demo-backward; the judges-leaned-forward moment): https://samanvya.dev/blog/mit-llm-hackathon-first-place
10. Ian Webster — *Things I learned from the LAUNCH hackathon* ($13.5k winner; landing-page first impression): https://ianww.com/blog/2015/03/03/things-learned-from-launch-hackathon
11. LayerX — *We entered Fixathon as hackers. We left as winners.* ("we won on evidence"; never-seen-data test): https://layerx.xyz/blog/fixathon-win
12. Ray Deck — *Lessons from Winning Five Hackathons* (rewards track sponsor business goals): https://sustained.substack.com/p/lessons-from-winning-five-hackathons
13. Eugene Yan — *How to Win a Data Hackathon* (judge's view: clean data + simple UI wins): https://eugeneyan.com/writing/how-to-win-data-hackathon/
14. Jitendra Devabhaktuni — *The Demo Environment Is a Lie* (fake-looking demo data kills trust): https://dev.to/jitendra_devabhaktuni_0f1/the-demo-environment-is-a-lie-heres-why-thats-hurting-your-sales-c4g · corroborating: Drew DiLorenzo/Sean Marshall, 86-demo observation: https://www.linkedin.com/posts/drewdil_observation-from-86-customer-interviews-activity-7345817222780436484-Fgj9
15. Fly Emu — *Interrupt: crowdfunding scam analysis* (frame-by-frame demo skepticism): https://flyemu.com/interrupt-the-coolest-hacking-gadget-or-the-next-crowdfunding-scam/
16. Reskilll — *How I Won Smart India Hackathon* (working-ugly-beats-impressive; last-12h demo prep): https://reskilll.com/blogs/how-i-won-smart-india-hackathon-lessons-36-hours-changed-everything/
17. Steve Harrison — *Pre-record your demos* (Meta Connect self-DDOS; Jobs iPhone-4 WiFi fail): https://steveharrison.dev/pre-record-your-demos/
18. KUFA Hackathon — *How to Prepare a Winning Pitch* (4-part structure; demo reliability): https://hackathon.uokufa.edu.iq/en/guides/how-to-prepare-winning-pitch/
19. arXiv 2206.04744 — *Design Practices of Hackathon Winners* (32 winners/16 countries, double-diamond process)

**Rules / internal anchors**
- WeMakeDevs Env Hacks rules + rubric + First Commit comps — cited via docs/20 source list
- Product ground truth: `server/main.py` (endpoint list), `server/community.py` (≥3-traversal corridor rule), `Mobile/App.tsx` (auto-arrival ~80 m receipt, `breathing N` banner), `Mobile/src/theme.ts` (`CIG_UG=316`), `Mobile/src/gazetteer.ts` (26.5k-POI local search), `server/city.html` (/city breathing surface), docs/10 (provenance), docs/18 (AWS + cost), docs/11 (script v2), docs/22 (breakthroughs + impact math), docs/24 (design spec).
