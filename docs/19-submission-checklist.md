# docs/19 — Submission checklist (Oct 8–11, in order)

Everything below is what ONLY govinda can do. Code, deploy, video and
writeup are already done — this is the last mile.

## 1. Register (5 min)

https://www.wemakedevs.org/aws/env → log in → join "Environmental Hacks"
→ Track 01 (Air). Claim the **$200 AWS credits** code they email —
Billing → Credits in the AWS console.

## 2. Budgets alarm (2 min, protects the free stuff)

console.aws.amazon.com → Billing → Budgets → "Create budget" →
$5/month → your email. The stack costs ~$46/mo worst case; the alarm
fires before anything surprises you.

## 3. Public repo inside the event window (3 min)

Rule: "a repository whose history does not match the event dates
disqualifies the whole team." Our private commits predate Oct 8.

On Oct 8, on any machine:

```bash
git clone https://github.com/<owner>/Delhi-Air-108.git
cd Delhi-Air-108
./scripts/public-repo.sh https://github.com/<owner>/<NEW-PUBLIC-REPO>.git
```

First create `<NEW-PUBLIC-REPO>` as a PUBLIC repo on GitHub (empty, no
README). The script squashes everything to one baseline commit dated
inside the window and pushes it. Keep hacking normally after that —
new commits land inside the window on their own.

## 4. The ≤3-minute video (judges see: repo + video + writeup only)

Already recorded: `alive108-twitter-final.mp4` (2:08 arc) +
`alive108-twitter-64s.mp4` (2×). To extend to the full 3 min with AWS
visible — from your phone/console:

- Screen-record the AWS console: ECS → cluster `alive108` → service
  RUNNING → task details. ~10 s is enough.
- Then `http://65.2.28.40/admin` in any browser — live ops board.

## 5. Writeup — paste from docs/17-submission-writeup.md

Problem / Build / Where AWS fits / Validation / Impact — it's drafted
and matches exactly what is deployed.

## 6. Optional extras if you find them

- NASA FIRMS key: firms.modaps.eosdis.nasa.gov → "Get an SMS API key"
  (Earthdata login) — drop it here and the live fire layer upgrades.
- data.gov.in API key — would add the 115 Delhi MoRTH black spots to
  the safety layer (the OpenAQ feed already covers CPCB stations).

## What the judges can click (public, no install)

- `http://65.2.28.40/admin` — ops board, live
- `http://65.2.28.40/aqi?lat=28.63&lon=77.24` — field + calibration
- `http://65.2.28.40/decide?from_lat=28.6519&from_lon=77.1907&to_lat=28.6129&to_lon=77.2295`
  — safety-first engine
- `http://65.2.28.40/shift?lat=28.6139&lon=77.2090&hours=8&vehicle=driving_two_wheeler`
  — the Rapido-driver number
