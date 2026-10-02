# docs/17 — Submission writeup (draft)

Paste-ready for the hackathon submission form: problem, build, where AWS fits.

## Problem

Delhi is the most polluted megacity on earth — winter PM2.5 regularly
runs 10–20× the WHO guideline. Every resident commutes through it twice
a day, and until now the cost was invisible: Google Maps, Uber and
Rapido optimise for time and money, never for what the trip puts in
your lungs. Delhi also has a coverage problem — government monitors
sparsely cover NCR, so most streets have no measurement at all.

## Build

ALive-108 is a consumer app (Android + iOS, one codebase) that puts an
air price on every trip: pick FROM→TO and see the actual PM2.5 you'd
inhale by car, auto, bus, metro, bike or on foot — ranked by a
safety-first decision engine (50% dose + 30% mode crash-risk anchored
to MoRTH fatality shares + 20% time). Underneath is a real physics
stack, not an AQI lookup: live station/CAMS field interpolated with
wind-advected IDW, breathing-zone microenvironment factors measured on
Delhi roads, per-segment dose colouring, a 120-hour forecast with a
"leave later" optimizer, and a 9-million-measurement climatology from a
decade of NCR stations. The Lung Ledger turns every trip into
cigarette-equivalents and avoided-µg. And every journey donates an
anonymous traversal to a shared community layer — commuters become the
sensor grid covering streets no station can see, plus live hazard flags
(dust/smoke/burning/clean). An ops dashboard (/admin) shows the city
breathing in real time.

## Where AWS fits

- **ECS Fargate** (serverless containers) hosts the FastAPI decision engine —
  `server/Dockerfile` + `server/deploy-aws.sh` deploy in one command.
- **S3** stores the 9M-measurement climatology (OpenAQ's archive is
  itself S3 — same bucket class, our derived product).
- **DynamoDB** (or S3 JSONL) holds donated traversals + hazard reports —
  the community ledger scales without a database admin.
- Video shows the AWS console + a deployed public URL, per the rules.

## Impact

Honest scope: the app cannot remove Delhi's emissions — no app can.
What it does and proves: cuts an individual's inhaled dose by up to ~30×
on the same trip (live, verified numbers), converts avoidance into a
countable ledger (µg avoided, city-wide), and builds the first
community traversal map of exposure in NCR — data that exists nowhere
else and grows with every user.
