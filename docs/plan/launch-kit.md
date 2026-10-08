# Alive — LAUNCH KIT (tomorrow-evening Android release)

*Release-prep lane, written 2026-10-08 UTC. Everything below was verified
against `base/v2` HEAD (`d1dc452`), the live NLB, and the APK bytes
themselves — not from memory. If a lane doc disagrees, the lane report
wins.*

Canonical names:

- **APK:** `alive-06919ca.apk` — 169,337,404 bytes (161.5 MiB),
  sha256 `bdadb36e8c86bacf6c1ddbbf0cdc61c86b1742f186c88c9f8799588170e2b3dc`.
  Built at `06919ca`, camera-proven by `docs/lanes/apk-final-v4-report.md`
  (12/12 beats PASS, 0 crashes, 13.5-min single take). Artifact lives on
  the v4 lane session (attachment `e11a5066-…`); re-downloaded and
  hash-verified this session — the sha above is real.
- **Prod:** `http://alive108-2699c171ddded465.elb.ap-south-1.amazonaws.com`
  (= `http://65.2.28.40`, EIP). HTTP :80 only. `/health` re-checked at
  write time: `build_sha ea2c0fb7`, `field_stale:false`, 46 stations,
  bus+metro real feeds true.
- **Landing:** standalone `index.html` on `main` and `landing` branches
  (identical trees, last sync `ef4cedd` v11). 4 CTAs point at
  `github.com/<owner>/Delhi-Air-108/releases`.
- **Tag:** `v1.0.0-demo` (release_prep default; matches versionName 1.0.0).

**⚠ Two structural facts before any step:**

1. **Delhi-Air-108 is still private** (404 unauthenticated right now) —
   and it must NOT be the public launch repo. Its history predates the
   Oct-8 window; `scripts/public-repo.sh` exists because making *this*
   repo public is the disqualifier, not the fix. The public repo is a
   NEW squashed-baseline repo (e.g. `<owner>/Alive`). Every
   landing CTA says `Delhi-Air-108/releases` — those links 404 for the
   public today and keep pointing at the wrong repo after launch unless
   repointed. This is the single link that makes "get the app" resolve.
2. **Every `base/v2` push triggers a prod rebuild** (watchdog; observed
   4×). This docs push itself will flip `build_sha` to a `d1dc452`-era
   task. Harmless for the release (APK talks to the API, not the build),
   but freeze `base/v2` during the launch window so `/health` and the
   stage don't move under you.

---

## 1. THE HOST-APK DECISION — where 169 MB resolves publicly

**Recommendation: public-repo GitHub Release (path B). It's already
wired — the landing's only job is a URL swap.**

| path | honest verdict |
|---|---|
| **B — GitHub Release asset on the squashed public repo** | **Ship this.** 2 GB per-asset limit (169 MB = 8.5% of it), free, public download URL forever: `…/releases/download/v1.0.0-demo/alive-06919ca.apk`. Zero new infra, zero new cost. The Releases page is where the CTAs already point. |
| A — APK committed to the landing branch (served by Vercel) | **Dead at this size.** GitHub hard-rejects blobs >100 MB on push — `public-repo.sh` aborts on them too. Git LFS dodges the push limit but free LFS is 1 GB storage / 1 GB-month bandwidth → ~6 downloads then dead links, and Vercel serves the LFS *pointer text*, not the binary. Don't. |
| Cloudflare R2 public bucket | Viable backup (zero egress fees) but needs console setup + bucket + public URL — not tonight unless GitHub breaks. |
| Devin attachment URL | **Not public** — org-auth'd. Never give this out. |

### Steps (path B)

1. Owner creates the public repo: **empty** repo on github.com (no
   README/license), then from any authed clone:
   `./scripts/public-repo.sh https://github.com/<owner>/<NEW>.git`
   — it squashes `base/v2` to one baseline commit and pushes `main`.
2. Fill the release body — `scripts/release_prep.sh <apk> v1.0.0-demo`
   expects filename `alive108-<sha>.apk`; ours is `alive-06919ca.apk`
   (no "108"). Either `cp alive-06919ca.apk alive108-06919ca.apk` and run
   it, or skip the script — the filled body is §2 below, paste as-is.
3. github.com/<NEW>/releases/new → tag `v1.0.0-demo` → target = `main`
   (the baseline commit — its tree contains the code the APK was built
   from plus later docs/audit fixes; the body says this honestly) →
   title `Alive — demo build (v1.0.0-demo)` → paste body → attach
   `alive-06919ca.apk` → tick **pre-release** → publish.
4. Repoint the landing: 4 `Delhi-Air-108/releases` hrefs in `index.html`
   (on `landing` and `main`) → `https://github.com/<owner>/<NEW>/releases`.
   Same 4 lines in `server/landing.html` on `base/v2` for the prod copy.
5. Download the release asset once from a second browser/account's
   incognito window — verify it starts downloading unauthenticated, then
   `shasum -a 256` against the header line.

### Backup plan if a link 404s on launch night

- `get the app` 404s → the repoint push didn't deploy. Direct-asset URL
  works regardless of the page: pin it in the X post's reply + bio,
  then fix the landing.
- Release asset download dies mid-way → GitHub Releases rarely dies;
  the fallback host is R2/archive.org — a 30-min emergency, not a plan.
- Vercel itself down → the always-live fallback is the raw prod URL
  `http://65.2.28.40/` — ugly, works, every live widget paints.
- Repo stays private accidentally → releases 404 for everyone. Step 1's
  check: `curl -s -o /dev/null -w "%{http_code}" https://github.com/<NEW>`
  must print 200 while logged out.

---

## 2. RELEASE NOTES — final GitHub Release body (paste-ready)

*Register kept: plain words, "Delhi's air…" voice, zero jargon, honesty
section is a feature. Filled for the real binary. If the binary is
re-cut at HEAD (see decision below), only the BUILD/APK/SIZE/SHA256
block and the delete-my-data caveat change.*

---

# Alive — demo build (Android APK)

A Delhi PM2.5 personal air counter: what you inhaled today, and what
each way there costs before you leave. Android APK, sideload install —
not on the Play Store.

```
TAG:    v1.0.0-demo
BUILD:  06919ca (private dev repo; public baseline squashes it)
APK:    alive-06919ca.apk
SIZE:   169,337,404 bytes (161.5 MiB)
SHA256: bdadb36e8c86bacf6c1ddbbf0cdc61c86b1742f186c88c9f8799588170e2b3dc
```

## What it is

Alive is a personal smoke counter for Delhi — no hardware. It
reconstructs what you inhaled by crossing your own timeline with a live
modelled air field, so every trip prices in two numbers maps don't
show: the smoke you will breathe on each way there, and the smoke your
ride puts into the air — estimated before you leave, counted live while
you travel, receipted when you arrive. The phone measures nothing
itself, and only consented, anonymized **k≥3 aggregates** ever leave it.
Delhi/NCR only, by design.

## Install

1. Download the `.apk` from this release's **Assets**.
2. Check it before sideloading: `shasum -a 256 <file>` must equal the
   `SHA256:` line above; byte size is the `SIZE:` line.
3. Copy it to the phone, tap to install, and allow **Install unknown
   apps** once for your browser or Files app.
4. **Play Protect will warn** ("unknown developer"). The APK is
   debug-signed — tap **Install anyway**. That's the cost of a
   sideloaded demo build, not malware.
5. Open it. The consent card is the one real decision — sharing on or
   off are both honest answers.

The file itself: `com.anonymous.app` · versionCode 1 · versionName
`1.0.0` · targetSdk 36 · universal (arm64 + x86_64) ·
`usesCleartextTraffic=true` — the backend is HTTP :80, see below.

## What's inside

- **Plan any Delhi trip by breath.** FROM→TO over a bundled
  124,311-place gazetteer — works air-gapped. Every option carries an
  ETA, an inhaled-PM2.5 band (µg) and an emission band, each with its
  stated basis. On the demo OD the same minutes read ~9 µg in an AC car
  vs ~310 µg on foot — a ~35× spread no map shows.
- **The chooser beat.** Candidate routes draw in as equals — coloured
  per segment by the live field's CPCB band — the engine's pick settles
  bold, and a verdict pill pins onto the route saying why: "cleanest
  and fastest", "cleanest · N% less than fastest", or the server's own
  reason. Never an invented claim.
- **Live trip.** Turn-by-turn chrome; breath + exhaust counters tick at
  1 Hz off the route strip the server handed it — no per-second
  network. Park and it says so ("ride meters paused — still counting
  the air"). Reroute is served when you drift. The arrival receipt
  lands in the on-device ledger.
- **Your lungs' ledger.** Today's count arc, the week strip, per-trip
  receipts; the Delhi-today card (pollutant table vs WHO, "N% below the
  10-yr average"). All reconstructed on-device.
- **Air alerts — local, and only when there's something real to say.**
  An on-device engine reads the field every ~60 s in the foreground and
  pings real changes: stagnation, clean windows, air turning, GRAP
  moves, a departure nudge when a later slot is served lighter, a daily
  brief. Verified firing as real OS banners on Android and iOS.
- **Offline honesty.** Last-good data marked "updated N min ago" —
  never stale-as-fresh. The bundled gazetteer and the Delhi-NCR map
  pack (744 tiles, 27.4 MB, prefetched on first render) work fully
  air-gapped. A consented donation made offline queues in the outbox
  and lands once, on reconnect.
- **Consent-first.** Sharing off means zero donation traffic —
  pcap-verified: only GETs plus your own plan calls. Consent off leaves
  no outbox file at all.
- **Hindi + English.** The whole UI localizes (switch in Settings);
  English is the install default.
- **Map layers.** The stubble-fire belt, community corridors (streets
  only publish after 3 travellers), hazard reports. CPCB band scale
  under every air number; a freshness chip shows field age everywhere.

## What's verified (the v4 take — `docs/lanes/apk-final-v4-report.md`)

One continuous 13.5-minute screen record on this exact binary, zero
crashes, zero ANRs. Every beat passed on camera:

- cold open → onboarding first, no home flash; live ~65 µg/m³ already
  on slide 1
- consent, coach tour once (never reappears), force-stop relaunch →
  straight home
- hero number live and ticking (65→68 µg/m³), "air reading: 0 min old"
- air-map tap → named locality + field answer
- where-to → "connaught" → suggestions → plan → band-painted route
- turn-by-turn with live counters; parked ~35 s → meters pause, breath
  keeps counting
- drawer → Trips → Delhi-today (pollutants vs WHO, week mode split)
- double-back exit toast; airplane-mode relaunch → honest offline home
  ("can't reach the server — trying again"), no fabricated numbers

## What it does not claim

This section is a feature, not a disclaimer.

- **Sideload demo build.** Debug-signed, `com.anonymous.app` package
  id, not on Play Store. The Play Protect warning is expected.
- **Plaintext HTTP edge.** The prod API is an NLB on `http://…:80` —
  no TLS terminator today. Donations are anonymized aggregates, but the
  wire is plaintext.
- **Phones measure nothing.** Count = field sample × breathing-zone
  factor × ventilation × time. User traversals adjust dose estimates,
  never the field itself.
- **Emissions are class-level bands.** "Vehicles like yours … ~1.1–1.6
  kg CO₂" from published factors — never "your car emitted 42.0 g".
- **Aggregate-only uploads, k≥3.** A donated trip is trimmed 300 m at
  both ends, thinned, rounded, folded into cells, and the device token
  is hashed before anything can store or log it. Nothing publishes
  below 3 distinct devices in 72 h.
- **Delete-my-data wipes every store** — with one honest caveat on this
  binary: a share-toggle tap inside the same queued-write instant as a
  wipe can rewrite `consent.json` after it (audit-3 F1, fixed in the
  public baseline's `Mobile/src/store/consent.ts`; this binary predates
  the fix by a few commits).
- **Demo-room capacity.** One Fargate task in ap-south-1: honest ~8–15
  concurrent users. A demo room, not the internet.
- **Alerts are foreground-poll**, not push. Quiet data means a quiet
  phone.
- **iOS is not in this release.** Simulator-only today; this build is
  Android-only.
- **The community layer is young.** The k≥3 suppression that keeps it
  honest also keeps the public corridor table sparse. We say so.
- **Delhi/NCR only.** Outside the service box the app says so rather
  than guessing.

## Verify the download

The `SHA256:` and `SIZE:` lines were computed from the exact asset
attached to this release. Re-check after download:
`shasum -a 256 alive-*.apk`.

## License

MIT — see `LICENSE` in the repo.

## Links

- Live web demo, no install:
  http://alive108-2699c171ddded465.elb.ap-south-1.amazonaws.com
  (`/` landing, `/city`, `/community`; `GET /health` is public)
- Privacy transform chain: `PRIVACY.md` · threat model + pentest:
  `SECURITY.md`
- Verification this page leans on: `docs/lanes/apk-final-v4-report.md`,
  `apk-drive-v5-report.md`, `testday-android-report.md`,
  `testday-offline-report.md`, `notify-e2e-report.md`

---

## 3. LAUNCH CHECKLIST — tomorrow evening (Fri Oct 9, IST)

The load-bearing decisions are pinned at the top; do them BEFORE the
clock, not during.

### Decision A — ship `06919ca` or re-cut at HEAD?

- The v4 binary predates audit-3: **F1 HIGH (delete-my-data race can
  resurrect consent.json and re-arm sharing)**, F3/F4 cosmetic-med.
  The release body above already carries the honest caveat line for
  shipping `06919ca` as-is — that's an acceptable launch.
- A re-cut at `d1dc452`+ removes the caveat but is a NEW binary: the
  12/12 take does not cover it. If it's rebuilt by ~14:00 IST and the
  core beats re-driven on the KVM lane, ship the new one; later than
  that, ship `06919ca` and keep the caveat. Do not ship an unverified
  rebuild at 19:00.
- Server side is orthogonal — prod self-rebuilds on every push; the
  audit-3 server fix (shared rate bucket) is already landing via this
  docs push anyway.

### Decision B — public repo name + CTA repoint (owner, 20 min)

- Repo name suggestion: `<owner>/Alive` (capital-A reads clean
  in release URLs). Empty repo → `./scripts/public-repo.sh <url>` →
  verify `curl` 200 logged out.
- The 4 CTA repoints in `index.html` (landing + main) and
  `server/landing.html` (base/v2) are the launch. Without them every
  "get the app" lands on a private repo's 404.

### The evening, hour by hour

| IST | step |
|---|---|
| 16:00 | **Health gate:** `curl -s $NLB/health` → `field_stale:false`, `build_sha` noted, `field_age_s` < 1200. `python3 tools/warm_task.py` → priced engine warm. If either fails, hold the launch post — fix first. |
| 16:30 | **Deploy freeze declared** — no `base/v2` pushes until the posts are out (watchdog rebuilds mid-window = moving stage). |
| 16:45 | **Public repo + Release done** (path B steps 1–3). Incognito-download the asset once. |
| 17:15 | **CTA repoint + Vercel:** edit the 4 hrefs on `landing` branch `index.html` → new repo releases URL; push; Vercel project = repo import, root dir = `/` (index.html at root), production branch `landing`, framework "Other", no build command. Same repoint in `server/landing.html` on base/v2 ships to prod landing whenever it deploys — but note prod landing is HTTP (see caveat). |
| 17:45 | **Vercel caveat check** — open the vercel.app URL: chrome/paint works, hero, copy, CTAs, GET THE APP → release. **Expected honest gap:** every `http://65.2.28.40` fetch is mixed-content blocked on HTTPS — live chips/field-widgets hide themselves by design (they render honest absence, never fake numbers). If that reads too empty for a launch page, the X posts link the prod `http://65.2.28.40/` directly — fully live, uglier URL. Real fix = domain + Cloudflare TLS on the NLB (the CF token exists for it — stretch item, not tonight's blocker). |
| 18:00 | **X post 1 (landing reveal)** — draft in `docs/plan/x-posts.md`, attach the scroll clip + hero shot. |
| 18:30 | **X post 2 (launch)** — APK live + install→first-number clip (78 s, ready-made on this session — `alive-install-to-first-number.mp4`, or re-cut from `alive-v4-take.mp4` 0:00–0:38 + 2:15–2:55). Pin the direct asset URL as first reply. |
| 19:00 | **Watch + respond.** Keep `curl $NLB/health` in a corner — demo-room capacity is ~8–15 concurrent; if it melts, that's the honest story too. |
| 20:00+ | **X post 3 (demo-day recap)** — after the room quiets; attach the submission/twitter cut. |

### If tomorrow's health gate fails

Field stale >20 min after two cycles → ingest loop dead → restart task
(`deploy.sh`/force-new-deployment), re-check, then proceed or slip the
posts an hour. Never post "live" over a stale field — the app itself
will say "updated N min ago" and contradict the post.

---

## 4. ASSET INVENTORY (what exists, where)

| asset | where | use |
|---|---|---|
| `alive-06919ca.apk` (169 MB, verified sha) | v4 lane attachment `e11a5066-…`; downloaded + hash-verified this session | the release binary |
| `alive-v4-take.mp4` (812 s, 73.9 MB, 1080×2400) | v4 lane attachment `aebb9507-…` | source for all app clips |
| `alive-install-to-first-number.mp4` (78 s, 1.9 MB) | **cut this session** — take 0:00–0:38 + 2:15–2:55 | X post 2 attach |
| landing scroll clips (16 s desktop / 18.6 s phone) | `docs/lanes/landing-final-pack/*/scroll.mp4` | X post 1 attach |
| v11 landing stills | `docs/lanes/landing-v11-shots/landing-1440-hero.png` etc. | post 1/3 stills, fallback |
| `docs/video/cut1.mp4` (161 s) + `cut2.mp4` (157 s) | repo, plays air-gapped | post 3 attach if trimmed ≤140 s (X free-tier cap); twitter-64s cut from the video lane fits as-is |
| release body | this file §2 (or `scripts/release_prep.sh` output) | github release |
