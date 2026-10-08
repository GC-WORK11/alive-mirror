<!-- Release BODY template for the Alive GitHub Release.
     The <fill at freeze-cut> lines are filled by scripts/release_prep.sh
     → docs/release/RELEASE-NOTES.filled.md. Everything else is final copy —
     edit this file, never the filled one. -->

# Alive — demo build (Android APK)

```
TAG:    <fill at freeze-cut>
BUILD:  <fill at freeze-cut>
APK:    <fill at freeze-cut>
SIZE:   <fill at freeze-cut>
SHA256: <fill at freeze-cut>
```

## What it is

Alive is a personal PM2.5 dosimeter for Delhi — no hardware. It
reconstructs what you inhaled by crossing your own timeline with a live
modelled concentration field, so every trip prices in two numbers maps
don't show: the smoke you will breathe on each way there, and the smoke
your ride puts into the air — estimated before you leave, counted live
while you travel, receipted when you arrive. The phone measures nothing
itself, and only consented, anonymized **k≥3 aggregates** ever leave it.
Built for the AWS × WeMakeDevs Environmental Hacks hackathon, Track 01
(Air), Oct 8–11 2026. Delhi/NCR only, by design.

## Install

1. Download the `.apk` from this release's **Assets**.
2. Check it before sideloading: `shasum -a 256 <file>` must equal the
   `SHA256:` line above; the byte size is on the `SIZE:` line.
3. Copy it to the phone, tap to install, and allow **Install unknown
   apps** once for your browser or Files app.
4. **Play Protect will warn** ("unknown developer"). The APK is
   debug-signed — tap **Install anyway**. That's the cost of a
   sideloaded demo build, not malware: the build recipe is in the repo
   (`docs/demo-day.md` → "Release APK") and the binary is reproducible
   at the tagged commit with
   `cd Mobile/android && ./gradlew assembleRelease`.
5. Open → the consent card is the one real decision — sharing on or off
   are both honest answers, and nothing else is required.

The file itself: `com.anonymous.app` · versionCode 1 · versionName
`1.0.0` · targetSdk 36 · universal (arm64 + x86_64) ·
`usesCleartextTraffic=true` — the backend is HTTP :80, see below.

## What's inside

- **Plan any Delhi trip by dose.** FROM→TO over a bundled
  124,311-place gazetteer — works air-gapped. Every option carries an
  ETA, an inhaled-PM2.5 **dose band** (µg) and an **emission band**,
  each with its stated basis. On the demo OD the same minutes read
  ~9 µg in an AC car vs ~310 µg on foot — a ~35× spread no map shows.
- **The chooser beat.** Candidate routes draw in as equals — coloured
  per segment by the live field's CPCB band — the engine's pick settles
  bold, and a verdict pill pins onto the route saying why: "cleanest
  and fastest", "cleanest · N% less than fastest", or the server's own
  reason. Never an invented claim.
- **Live trip.** Turn-by-turn chrome; dose + exhaust counters tick at
  1 Hz off the route strip the server handed it — no per-second
  network. Reroute is served when you drift. The arrival receipt lands
  in the on-device ledger.
- **Your lungs' ledger.** Today's dose arc, the week strip, per-trip
  receipts; the Delhi-today card (pollutant table vs WHO, "N% below the
  10-yr average"). All reconstructed on-device.
- **Air alerts — local, and only when there's something real to say.**
  An on-device engine reads the field every ~60 s in the foreground and
  pings real changes: stagnation, clean windows, air turning, GRAP
  moves, your day on the road — plus a departure reminder when a later
  slot is served lighter, and a daily brief. Verified firing as real
  OS banners on Android and iOS.
- **Offline honesty.** Last-good data marked "updated N min ago" —
  never stale-as-fresh, never fake-fresh. The bundled gazetteer and the
  Delhi-NCR map pack (744 tiles, 27.4 MB, prefetched on first render)
  work fully air-gapped. A consented donation made offline queues in
  the outbox and lands once, on reconnect: "saved — will send when back
  online".
- **Consent-first.** Sharing off means zero donation traffic —
  pcap-verified: only GETs plus your own plan calls. Consent off leaves
  no outbox file at all. Delete-my-data wipes every store and disarms
  every pending ping.
- **Hindi + English.** The whole UI localizes (switch in Settings);
  English is the install default.
- **Map layers.** The stubble-fire belt, community corridors (streets
  only publish after 3 travellers), hazard reports. CPCB band scale
  under every air number; a freshness chip shows field age everywhere.

## What it does not claim

This section is a feature, not a disclaimer.

- **Sideload demo build.** Debug-signed, `com.anonymous.app` package
  id, not on Play Store. The Play Protect warning is expected.
- **Plaintext HTTP edge.** The prod API is an NLB on `http://…:80` —
  no TLS terminator today (a domain + ACM cert away). Donations are
  anonymized aggregates, but the wire is plaintext.
- **Phones measure nothing.** Dose = field sample × breathing-zone
  factor × ventilation × time. User traversals adjust dose estimates,
  never the field itself.
- **Emissions are class-level bands.** "Vehicles like yours … ~1.1–1.6
  kg CO₂" from published factors — never "your car emitted 42.0 g".
- **Aggregate-only uploads, k≥3.** A donated trip is trimmed 300 m at
  both ends, thinned, rounded, folded into cells, and the device token
  is hashed before anything can store or log it. Nothing publishes
  below 3 distinct devices in 72 h — the suppression counter is public
  at `GET /v2/city/moves` (`min_k: 3`).
- **Demo-room capacity.** One Fargate task in ap-south-1: honest ~8–15
  concurrent users. A demo room, not the internet.
- **Alerts are foreground-poll**, not push. Quiet data means a quiet
  phone — fires and GRAP kinds fire only on real field moves.
- **iOS is not in this release.** Simulator-only today (no Apple
  developer account); this build is Android-only.
- **The community layer is young.** The k≥3 suppression that keeps it
  honest also keeps the public corridor table sparse. We say so.
- **Delhi/NCR only.** Outside the service box the app says so rather
  than guessing.

## Verify the download

The `SHA256:` and `SIZE:` lines at the top were computed from the exact
asset attached to this release by `scripts/release_prep.sh`. Re-check
them after download: `shasum -a 256 alive108-*.apk`.

## License

MIT — see [`LICENSE`](../LICENSE) in the repo.

## Links

- Live web demo, no install:
  http://alive108-2699c171ddded465.elb.ap-south-1.amazonaws.com
  (`/` landing, `/city`, `/community`, `/admin`; `GET /health` is public)
- Repo: https://github.com/<owner>/Delhi-Air-108
- Privacy transform chain: `PRIVACY.md` · threat model + self-run
  pentest: `SECURITY.md`, `docs/lanes/pentest-report.md`
- Every verification this page leans on:
  `docs/lanes/apk-v10-report.md`, `testday-android-report.md`,
  `testday-offline-report.md`, `route-chooser-report.md`,
  `notify-e2e-report.md`, `codebase-mobile-report.md`,
  `map-depth-report.md`
