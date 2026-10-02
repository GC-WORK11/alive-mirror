# ALive-108 — Hackathon Winning Playbook

Deep research for **Environmental Hacks** (Bharat Builds Tour × AWS Builder Center, Oct 8–11, 2026, Air track). Every claim cited. Read (a) for the rules of the game, (e) first if you're short on time — it's the kill-list.

---

## (a) The hackathon, verified

**What it is.** "Environmental Hacks" — the second stop of the six-hackathon Bharat Builds Tour, run by WeMakeDevs in collaboration with AWS Builder Center. Three tracks: **Air** (ours), Heat & Water, Waste & Energy.
- Source: https://www.wemakedevs.org/aws/env · tour: https://www.wemakedevs.org/aws

**Dates & format.** Online Thu–Sun **Oct 8–11, 2026**, anywhere in India. Optional build day **Sat Oct 10, 8 AM–8 PM at DTU, Delhi** (Shahbad Daulatpur, Main Bawana Road) with AWS workshops, project feedback, Amazon team in the room. Kickoff Oct 8: "Teams form, tracks get picked, repos get made." Submission deadline is **Sun Oct 11 — exact hour still TBD** ("the hours are being finalised… they land on this page first"). Winners are announced on the page + email (First Commit: ended Sep 20 → winners Sep 25, ~5 days).
- Sources: https://www.wemakedevs.org/aws/env/schedule · https://www.linkedin.com/posts/wemakedevs_16000-participants-took-part-in-the-bharat-activity-7509172451524829184-G4Yq

**Eligibility.** University students in India, 18+, teams of 1–4. **Two gates, both required:** a WeMakeDevs account AND an AWS Builder Center profile with SheerID-verified enrollment — "checked against your registration details and your AWS Builder Center profile… before the hackathon you enter." Verification pending ≠ blocked from submitting, but the fast-track and Builder Center rewards wait on it.
- Source: https://www.wemakedevs.org/aws/env/rules

**Prizes (Air track).** Track winner: **₹2,00,000 cash + $2,000 AWS credits** (same for all three tracks). Four more teams across tracks get **$1,000 AWS credits** each. **AirPods 5 to 5 people** for writeups published on AWS Builder Center. Tour kit for top teams. **Fast-track Amazon interviews (6-mo internship / full-time) for top-10 students across all three tracks** — decided separately from prizes, by different people, against different criteria; only 2027/2028 grad-year students eligible.
- Sources: https://www.wemakedevs.org/aws/env · https://www.wemakedevs.org/aws/env/rules

**The exact judging rubric (5 criteria, no published weights).** From the env page verbatim:
1. **Idea and Impact** — "Does it fix a real environmental problem? And what changes for the people living with it? A small problem solved well beats a big one solved vaguely."
2. **Built on AWS** — "Using an AWS open-source project or AWS services is **mandatory** to win a prize." Free Tier counts in full.
3. **Design and usability** — "Would someone who isn't on your team know what to do with it?" (First Commit's wording is sharper: "A judge who has never seen your project should be able to pick it up and use it.")
4. **The execution** — "Does it work? Not perfect, not polished. Working. **One feature that runs beats five that almost do.**"
5. **The demo video** — "Three minutes, recorded, to show what it does, who it is for, and where AWS fits. **There is no live demo, so the video is what the judges see.**"
- Sources: https://www.wemakedevs.org/aws/env · https://www.wemakedevs.org/aws/first-commit

**Submission = exactly three things.** (1) a **public repository**, (2) a **≤3:00 demo video uploaded to YouTube** (public or unlisted; must open signed-out), (3) a **short writeup**: problem, the build, where AWS fits. One submission per team, on the hackathon's form, before the deadline. "Judges score what you submit and nothing else… **If the video does not show it, it does not count, and a feature that exists only in the writeup does not count either.**"
- Source: https://www.wemakedevs.org/aws/env/rules

**The three DQ rules that actually kill teams.**
- "Your project has to use AWS, **and your demo video has to show it.** Naming AWS in the writeup alone is not enough."
- "**Old projects do not count.** Build something new once the clock starts. If you began the project before the hackathon opened, it does not qualify, **even if you rewrote it.**" + "a repository whose history does not match the event dates disqualifies the whole team."
- AI coding tools are legal — but you **must list them in the writeup** (disclose Devin usage).
- Source: https://www.wemakedevs.org/aws/env/rules

**Field size.** First Commit (the same tour, identical rulebook, Sep 17–20) drew **16,000+ participants** and 1,400 in-person builders in Bangalore. Expect comparable or larger for Delhi's environment edition. Your competition is not 3 teams — it's hundreds of AQI dashboards.
- Sources: https://www.linkedin.com/posts/wemakedevs_16000-participants-took-part-in-the-bharat-activity-7509172451524829184-G4Yq · https://www.linkedin.com/posts/wemakedevs_yesterday-we-hosted-the-first-commit-hackathon-activity-7507421383140814848-Gzyy

---

## (b) What wins: pattern analysis with named examples

### B.1 — The freshest possible comp: First Commit winners (same judges' rulebook, 3 weeks ago)

| Prize | Team / Project | What it is | Why it won |
|---|---|---|---|
| Ship It (₹2L + $3k) | **Team StarBugs — "Suraksha"** | Agentic elder-care companion: Galaxy Watch + AI voice companion on AWS; checks on aging parents, escalates to family; **parents control what's shared** | Emotional personal problem (aging parents), a *device+agent* system not a CRUD app, deployed with a URL, privacy designed-in as a feature not a disclaimer |
| Build It (₹2L) | **Prashant Thakur — "Beacon Night Shift"** | Voice on-call agent for the 3 AM page: reads logs, diffs security groups vs golden snapshot, dry-runs one allowlisted fix, phones you; "**consent is checked against the transcript, never the model's argument**" | Visceral scenario everyone knows (3 AM page), agent with *write access* that earns trust via audit — a capability claim, not a feature list |
| Best UI | **Team 3 Builds** | (undisclosed) | Design prize exists at First Commit; at Env Hacks design folds into criterion 3 |
| Runner-up $1k credits | **VOXTON — Magpie** | "AI-native finance workspace" | Named like a startup, single-sentence legibility |
| Runner-up | **Powerpuff Girls — FreshTrace** | Freshness tracking across a journey | Real-world physical problem, traceable unit |
| Runner-up | **Need sleep — Expressive Captions** | Expressive captioning system | Single sharp feature |
| Runner-up | **Mohammed Ali Khan — Factcade** | AI ops copilot for factories | Named persona + domain |

- Sources: winners — https://www.linkedin.com/posts/wemakedevs_16000-participants-took-part-in-the-bharat-activity-7509172451524829184-G4Yq · runners-up — https://www.linkedin.com/posts/wemakedevs_the-bharat-builds-first-commit-hackathon-activity-7509139471314092032-P6mQ · Suraksha detail — https://www.twstalker.com/kunalstwt · Beacon detail — https://lablab.ai/submissions/p7su7y6vahta4mn6p0vp1663
- Blog-prize winners (the Builder Center writeup prize we're also targeting): "KavachPay: financial control plane for autonomous AI agents," "Career Agent," "VaporTrace: real-time distributed tracing for AWS event pipelines," "The Timetable Nobody Has" — all titled like products with a thesis. https://www.linkedin.com/posts/wemakedevs_the-bharat-builds-first-commit-hackathon-activity-7509109843421716480-FW2o

**What the winning *writeups* do** (Beacon's is the model to copy): a scenario opener ("It is 3 AM, payments are failing"), a named persona ("the backend engineer on a team of one to five"), a capability line ("Everything else either asks without acting (PagerDuty) or…"), and a trust mechanism explained as the moat. It's written like engineering fiction with numbers — the writeup *itself* signals depth.

### B.2 — Cross-hackathon pattern: what "technical breakthrough" means to judges

Read across WeMakeDevs winners, Amazon's own hackathon advice, Devpost judge interviews, and env-track winners, the pattern is consistent: **the breakthrough is a new capability made legible in one demo-able moment — not algorithmic novelty.** Judges can't evaluate your kriging math; they evaluate the moment the screen shows a real route with a number nobody else computes.

The recurring winning formula (7 properties):

1. **Category invention, not feature addition.** Winners define a category they alone occupy: Suraksha = "agentic elder-care companion," Beacon = "on-call agent," Magpie = "AI-native finance workspace." Waze did this deliberately — rebranded from "navigation app" to "commuting app"/"social navigation" and became "the world's first social navigation app" ($1.1B exit). ALive-108's category: **exposure-aware routing / dose navigation** — never say "AQI app" or "air quality app."
   - Source: https://www.meaningmakercreative.com/waze
2. **A visceral, personal problem in the first 10 seconds.** Elder parents alone at home; payments failing at 3 AM. Ours: **Delhi air costs the average resident 8.2 years of life expectancy** (UChicago AQLI, Aug 2025 — the largest potential gain of any region on Earth) — and breathing Delhi's air ≈ **~20 cigarettes a day** (Berkeley Earth rule of thumb: 22 µg/m³ PM2.5 ≈ 1 cigarette/day).
   - Sources: https://aqli.epic.uchicago.edu/files/India%20FactSheet_2025_IndiaWV.pdf · https://indianexpress.com/article/cities/delhi/delhi-life-expectancy-air-pollution-chicago-report-10217807/ · https://shootismoke.app/ · https://www.digitaltrends.com/home/air-pollution-cigarettes/
3. **"X does Y, we do Z" positioning against a known incumbent.** Beacon: "PagerDuty asks without acting." Ours: **every AQI app reports the problem; we act on it** — routing + depart-later + dose ledger, not another dashboard. This matters doubly because the cigarette-equivalent trick *already exists* (Sh*t! I Smoke, 2018, went globally viral) — the ledger alone is not novel; **dose-aware routing is.**
   - Sources: https://lablab.ai/submissions/p7su7y6vahta4mn6p0vp1663 · https://shootismoke.app/
4. **Deployed and durable > impressive and local.** At First Commit, "Ship It" (deployed with a URL) is literally where "the grand prize is decided" and "the architecture is part of the score." Env Hacks merged tracks but kept "Built on AWS" as criterion 2 — our live NLB-fronted Fargate deployment is the edge most student teams won't have.
   - Source: https://www.wemakedevs.org/aws/first-commit
5. **A trust mechanism, stated.** Winners name why the system is safe/true: Beacon's consent-vs-transcript check, Suraksha's parent-controlled sharing. Ours: **provenance + honest uncertainty** — 105 real CPCB/DPCC/HSPCB stations, field calibration (LOO CV, MAE 46µg, de-biased), confidence-graded grid, estimated-mode flags. The zero-fake-data rule is a judging asset: in a field of mock-data demos, "every number traceable to a station or model output" is a breakthrough claim.
6. **The demo shows one golden path, start to finish.** Amazon's own judge guide (Nova hackathon): "Get to the UI within the first 30 seconds… show one clear, successful use case… don't spend 2 minutes on slides." Devpost's judge panel: judges skim hundreds of submissions — the video is the first filter, and a nice video + weak description still loses.
   - Sources: https://amazon-nova.devpost.com/updates/42214-level-up-your-build-how-to-wow-the-judges · https://info.devpost.com/blog/hackathon-judging-tips
7. **Breadth loses, sharpness wins** — with a caveat. The SIH-2025 Delhi air winner (Vayu Mitra) shipped a 4-module platform (source-ID AI, forecasting, citizen app, policy dashboard) — that wins SIH's completeness rubric, but WeMakeDevs' rubric explicitly says "one feature that runs beats five that almost do." Keep the engine's breadth *visible* in the architecture slide, but demo **one commute**.
   - Sources: https://github.com/git-lakshy/sih-25 · https://www.wemakedevs.org/aws/env

### B.3 — What AWS-sponsored judging rewards (the sponsor's lens)

- **AWS must be *shown*, not named** — literal rule. Architecture/cost decisions "are part of the score" for deployed work. AWS's own agent-hackathon submissions require an **architecture diagram artifact** — include one in video + README.
  - Sources: https://www.wemakedevs.org/aws/env/rules · https://www.startupnetworks.co.uk/links/link/27605-aws-ai-agent-global-hackathon/
- **Depth over service-bingo.** Seven services wired correctly (NLB→Fargate→ECR→S3→Secrets Manager→CodeBuild→IAM-scoped task role) beats 15 logos. Judges are solutions architects — say the *why*: state survives redeploy in S3 because Fargate is ephemeral; secrets in Secrets Manager not env vars; NLB+EIP because task IPs die on redeploy. That's Well-Architected fluency (reliability + security pillars) told as war stories.
- **Cost-efficiency is a story beat.** "~$46/mo production bill, inside the $200 free-credit budget, zero hardware" = frugal engineering the sponsor loves. First Commit literally says "We judge what you built, not what you spent" — free-tier frugality is scored equal to spend.
- **The Builder Center writeup is a second judge-facing surface** — it's a separate judged prize (AirPods ×5) and the only place you can go deep: problem → stack → "what fought back" (their framing — tell the NLB target-group race bug, the 429 Maven mirror, the IST-vs-UTC climatology gotcha).
  - Source: https://www.wemakedevs.org/aws/env

---

## (c) Our winning strategy

### C.1 — Map ALive-108 onto the rubric

| Criterion | Our play |
|---|---|
| 1. Idea & Impact | Open with the 8.2-year stat + cigarette equivalence. Frame: *exposure* (their own Air-track example) — not monitoring, not awareness, but **reduced inhaled dose per commute**. Small problem solved well: "the Delhi commute." |
| 2. Built on AWS | Live deployment + console footage in video. Name the services aloud; show the arch diagram once, ~8s. Cost line: ~$46/mo. |
| 3. Design & usability | The app already looks Google-Maps-grade — that's the moat vs every Bootstrap dashboard in the field. One-tap golden path: From → To → ranked modes → pick. No tutorial needed. |
| 4. Execution | Demo **one commute end-to-end** flawlessly. Everything else is garnish. Keep the deployment green through judging week. |
| 5. Demo video | Structure below. It's the whole submission — judges never see anything not in it. |

### C.2 — The 3:00 video, beat by beat

| Time | Beat | On screen |
|---|---|---|
| 0:00–0:08 | **Cold open.** "Delhi air costs its residents 8.2 years of life — the worst on Earth. You can't see your daily dose. Until now." One-liner card. | Black card → stat → pitch line |
| 0:08–0:40 | **Golden path.** Real FROM→TO (e.g. Connaught Place → DTU). 8 modes ranked by *inhaled µg*. Tap metro+walk vs car: dose bars, ETA, arrival. | Phone recording, live backend |
| 0:40–1:05 | **The engine — "not an AQI app, a dose engine."** 105 live CPCB/DPCC/HSPCB stations → advection-weighted field → per-edge dose → cigarette equivalents. Show calibration/provenance badge. | Quick schematic + one /compare screen |
| 1:05–1:30 | **Lung Ledger + depart-later.** Week view, cig-equivalent count, leave-later across 120h forecast, nav-mode "breathing N µg/m³" live banner. | App screens |
| 1:30–1:55 | **The moat: citizens become the sensor network.** Observe → corridor teal veil → community map fills; "every commute donated anonymized." | CorridorLayer + /admin rollup |
| 1:55–2:20 | **AWS, on camera (mandatory).** ECS console running task → NLB DNS → S3 community state → Secrets Manager → CodeBuild pipeline → architecture card: "S3 because Fargate is ephemeral; ~$46/mo." | Console footage + diagram |
| 2:20–2:45 | **Impact close.** What changes for a commuter; the vision line; "the sensor network Delhi never had." | Stat callback + map filling |
| 2:45–3:00 | End card: name, one-liner, public repo + live URL. | End card |

Cut list (video only — features stay in repo): /escape, /shift, most admin internals, OTP2/transit depth, stubble-burning FIRMS. One feature that runs, remember.

**Upload unlisted to YouTube, verify signed-out, submit by Oct 10 evening** — don't wait for the TBD Oct 11 deadline hour.

### C.3 — Writeup (submission form + Builder Center version)

- Form writeup: problem → what the dose engine does → where AWS fits → AI tools used (disclose Devin per rules).
- Builder Center long-form (AirPods prize + judge credibility): Beacon-style. Title it like a product thesis: *"ALive-108: routing Delhi's commutes by inhaled dose"* — sections: the 8.2-year problem, the dose engine, the AWS build, what fought back (NLB target-group race, Fargate ephemeral FS→S3, Maven 429 mirror, IST climatology gotcha), what's next.

---

## (d) Ten one-liner pitches, ranked

Ranking basis: legibility-to-a-skimming-judge, mechanism clarity (routing/dose), emotional charge, moat signal, and differentiation from AQI-dashboard clones. Studied anchors: Waze ("Outsmarting Traffic, Together" — verb + collective + named enemy), Plume ("as easy as checking the weather" — democratized access), BreezoMeter ("Breathe Easier" — health outcome), IQAir ("world's largest air quality platform" — authority), Sh*t! I Smoke (unit-translation shock), Stripe ("infrastructure for the internet"), Waze's category-invention lesson (don't be the better X; be the first Y).

| # | Pitch | Verdict |
|---|---|---|
| **1** | **"Google Maps optimizes for minutes. ALive-108 optimizes for breaths."** | Best overall. Contrast-vs-incumbent in one line; invents the metric (dose ≈ breaths); judges get it in 2 seconds; works as video cold-open AND README header. |
| **2** | **"The first navigation app that routes around pollution, not just traffic."** | Category invention, Waze-style. States mechanism plainly. Slightly less punchy than #1 but the clearest one-sentence explainer — ideal writeup/video first line. |
| **3** | **"AQI apps tell you the air is killing you. ALive-108 tells you where to walk."** | The wedge against the clone field — attacks the 200 AQI dashboards in the room. Action-vs-information framing is our real differentiation. Use in the video after the engine beat. |
| **4** | **"Delhi breathes in cigarettes. We built the map that routes around them."** | Fuses the visceral stat with the mechanism. Best emotional line; a hair long for a cold open — great as the close. |
| **5** | **"Outsmart the smog, together."** | The Waze homage — "together" smuggles in the citizen-sensor moat. Elegant but mechanism-free; pair with #1 as tag/subtitle, or as the end-card line. |
| **6** | **"Turning every Delhi commute into the sensor network the city never got."** | The moonshot/moat line — civic infrastructure framing impresses sponsor judges. Weak on what-it-does; use in the community beat + writeup, not the opener. |
| **7** | **"Your commute is smoking. We help it quit."** | Sharpest cigarette-metaphor joke; memorable, risky register. Great tweet, decent video midline; too jokey as the headline for a ₹2L submission. |
| **8** | **"Waze for your lungs."** | Instant legibility, four words — but borrowed-brand framing undersells the depth (we're more than Waze-for-X). Keep as a spoken aside in the video. |
| **9** | **"The map your lungs would draw."** | Poetic, hints at the field-builder. Mechanism too implicit — judges skim; they shouldn't have to decode. Nice section header in writeup. |
| **10** | **"Fastest route home? No — the cleanest one."** | Terser version of #1's contrast. Fine fallback; loses the metric invention that makes #1 sing. |

**Recommended stack:** headline = #1 · category line = #2 · differentiation = #3 · emotional close = #4 · end-card/community = #5/#6.

---

## (e) Brutal gaps — current submission vs the winning standard

Ordered by kill-potential. Each maps to a rule or pattern above.

1. **☠️ Repo-history DQ risk (existential).** Rule: *"If you began the project before the hackathon opened, it does not qualify, even if you rewrote it"* + *"a repository whose history does not match the event dates disqualifies the whole team."* Our repo has commits from Oct 1. The Oct-8 squash-baseline into a **fresh public repo** is mandatory, and scrub every trace of earlier dates: docs/00–19 timestamps, "day N" notes, attachment links, build logs, even `docs/19` checklist dates. Public repo should be *born* Oct 8 with all commits inside Oct 8–11. (You knew this — `scripts/public-repo.sh` exists — but it's the single point of total failure; treat the scrub like a checklist item, not a hope.)
2. **The video doesn't show AWS yet — an automatic DQ-risk and a lost criterion.** Rule: *"your demo video has to show it."* The existing Twitter video has no console footage. Must add: ECS service running, NLB DNS record, S3, Secrets Manager, CodeBuild — recorded from the AWS console — plus a static architecture card. Non-negotiable.
3. **"If the video does not show it, it does not count."** Our feature surface is huge (15+ endpoints). A 3-minute video that tours endpoints looks like breadth-without-depth. Script the golden path; everything else exists only if it appears on screen. Judges *can't* score what they can't see.
4. **Builder Center verification + writeup are unpaid prizes sitting on the table.** SheerID student verification gates both prizes and the fast-track (your actual goal). The Builder Center writeup is a separately-judged prize and the only deep-technical surface judges read. Neither exists yet — both are user-side tasks.
5. **Deployment must stay green through judging week.** No live URL is required by env rules, but "Built on AWS" is criterion 2 and First Commit gave its grand prize to deployed work. http://65.2.28.40 must survive Oct 8–16 (winners ~5 days post-close). Freeze deploys after final build; verify target-group health after any restart (the TG stale-IP bug already bit once).
6. **Pitch currently leads with novelty-adjacent framing.** "Lung Ledger / cigarette-equivalents" alone = Sh*t! I Smoke (2018) territory — derivative to any judge who's seen it. Lead with **dose-aware routing** (the new capability), keep the ledger as the personal loop, the citizen sensor network as the moat. Fix in video script + writeup first lines.
7. **Judges may be non-technical and they skim.** Devpost judge data: description + video are the first filter; most judges never open the repo deeply. README must carry: one-liner, 3 screenshots, live URL, APK/TestFlight link, "how AWS is used" section, setup that works. A repo that's a mystery loses to a repo that's a landing page.
8. **No real-user proof.** We have zero organic users (community layer is simulated by our own traversals — honest, but thin). Mitigate honestly: show the community rollup *live* and frame it as "the flywheel every user feeds" rather than claiming adoption. Alternatively get 5 real Delhi friends to run real trips during Oct 8–10 — even small numbers beat none.
9. **"ALive-108" name legibility.** Judges won't catch the 108-ambulance reference unless told. Say it once in the video ("named for Delhi's emergency helpline") or risk it reading as arbitrary.
10. **Deadline hour is TBD + server-side clock risk.** Schedule page still says hours are being finalized. Plan submission for **Oct 10 evening IST**, not Oct 11 — a TBD 11:59 PM IST cutoff you discover at 11:00 is a silent killer.
11. **Optional-but-free: the DTU build day (Oct 10).** Feedback from the Amazon team in the room is the only pre-judging calibration available. If you're in Delhi and can spare the day, it's asymmetric upside; it's also where judge/mentor expectations get heard first-hand.

---

### Source list (all claims above)

1. https://www.wemakedevs.org/aws/env — hackathon page: tracks, prizes, judging criteria, AWS tool table
2. https://www.wemakedevs.org/aws/env/rules — full rulebook: eligibility, DQ rules, submission spec
3. https://www.wemakedevs.org/aws/env/schedule — Oct 8–11 calendar, TBD deadline hour
4. https://www.wemakedevs.org/aws — tour page: ₹1 crore pool, fast-track mechanics
5. https://www.wemakedevs.org/aws/first-commit — previous stop: same rubric, Ship-It grand prize note
6. https://www.wemakedevs.org/aws/first-commit/rules — shared rulebook
7. https://www.wemakedevs.org/hackathons — edition list
8. https://www.linkedin.com/posts/wemakedevs_16000-participants-took-part-in-the-bharat-activity-7509172451524829184-G4Yq — First Commit winners + 16k participants
9. https://www.linkedin.com/posts/wemakedevs_the-bharat-builds-first-commit-hackathon-activity-7509139471314092032-P6mQ — runner-up projects
10. https://www.linkedin.com/posts/wemakedevs_the-bharat-builds-first-commit-hackathon-activity-7509109843421716480-FW2o — Builder Center blog-prize winners
11. https://www.linkedin.com/posts/wemakedevs_the-second-hackathon-of-the-bharat-builds-activity-7509568355222126594-PS-5 — Environmental Hacks announcement
12. https://www.linkedin.com/posts/wemakedevs_yesterday-we-hosted-the-first-commit-hackathon-activity-7507421383140814848-Gzyy — 1,400 in-person attendance
13. https://www.twstalker.com/kunalstwt — Suraksha project detail; DTU venue partner confirmation
14. https://lablab.ai/submissions/p7su7y6vahta4mn6p0vp1663 — Beacon Night Shift full writeup (winning-style exemplar)
15. https://dev.to/naomiiap/caresync-a-local-health-memory-agent-for-family-caregivers-337c — Suraksha winner's adjacent project (style/persona evidence)
16. https://amazon-nova.devpost.com/updates/42214-level-up-your-build-how-to-wow-the-judges — Amazon's own judge-survival guide
17. https://info.devpost.com/blog/hackathon-judging-tips — 5 judges on what they actually score
18. https://forum.trondao.org/t/tron-grand-hackathon-improving-your-devpost-judge-score/9393 — judge-score analysis (video-first skimming)
19. https://www.startupnetworks.co.uk/links/link/27605-aws-ai-agent-global-hackathon/ — AWS hackathon submission requirements incl. architecture diagram
20. https://github.com/git-lakshy/sih-25 — SIH 2025 Delhi air winner (breadth-style comp)
21. https://devpost.com/software/airguardian-clxrgv , https://devpost.com/software/air_quality_bonanza — env-track project examples
22. https://shootismoke.app/ + https://www.digitaltrends.com/home/air-pollution-cigarettes/ — cigarette-equivalent prior art; Delhi ≈ 20 cigs/day; Berkeley Earth 22µg/m³ rule
23. https://aqli.epic.uchicago.edu/files/India%20FactSheet_2025_IndiaWV.pdf + https://indianexpress.com/article/cities/delhi/delhi-life-expectancy-air-pollution-chicago-report-10217807/ — AQLI 8.2-year Delhi stat
24. https://www.meaningmakercreative.com/waze + https://blog.google/products-and-platforms/products/maps/google-maps-and-waze-outsmarting/ — Waze category invention + tagline
25. https://plumelabs.com/en/air/ — Plume positioning ("as easy as checking the weather")
26. https://www.adsoftheworld.com/campaigns/breathe-easier — BreezoMeter positioning
27. https://www.iqair.com/eu/about-iqair — IQAir authority framing
