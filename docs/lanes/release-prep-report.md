# Lane report — release-prep: the GitHub Release package, ready for one-click upload

**Date:** 2026-10-07 (UTC) · **Lane:** release-prep · **base/v2 @ `b633a2d`**
Deliverable: everything the owner needs to publish the freeze-cut APK as a
GitHub Release — body copy, the fill script, the tag call, and the
release/tag state audit.

## What shipped

| file | what |
|---|---|
| `docs/release/RELEASE-NOTES.md` | The release **body template**. Final copy everywhere except the five `TAG:/BUILD:/APK:/SIZE:/SHA256:` lines the script fills. Thesis paragraph, install steps, verified feature list, honest not-claims, MIT line. |
| `scripts/release_prep.sh` | `<apk> [tag]` → sha256 + size → resolves the build sha from the filename and checks it in-repo → writes `docs/release/RELEASE-NOTES.filled.md` → copies body to clipboard (pbcopy/xclip) → prints **both** release paths: `gh release create` AND the github.com web steps (gh is NOT authed on the work boxes; owner uploads via web UI or a scoped PAT). Prints nothing it didn't verify. |
| `.gitignore` | `docs/release/RELEASE-NOTES.filled.md` — generated, never committed. |

## Release/tag state audit (item 4)

- `git tag -l` → **empty**; `git ls-remote --tags origin` → **empty**.
  Zero tags have ever existed on this repo — there is no release/tag
  convention to follow, this lane *sets* it.
- GitHub cannot host a published release without a tag → **no public
  release exists today**. (The repo is private — unauthenticated
  `api.github.com`/`releases` returns rate-limit/404 — but only an
  invisible draft could exist without a tag, which the owner would see
  in the Releases UI. None reported.)
- APK badging (apk-v10-report): `com.anonymous.app` · versionCode 1 ·
  versionName `1.0.0` · targetSdk 36 · universal arm64+x86_64 ·
  debug-signed · `usesCleartextTraffic=true`.

## Tag picked (item 5): `v1.0.0-demo`

Semver matching the APK's `versionName 1.0.0` + an explicit demo marker.
Rationale: honest about what this build is (a sideloaded hackathon demo,
not a store cut) and it keeps a plain `v1.0.0` free for a future
signed Play build. Tag is annotated and points at the freeze commit.
`release_prep.sh` defaults to this tag; a second arg overrides.

## Owner runbook at freeze-cut (~20:00 IST)

```bash
git pull origin base/v2
scripts/release_prep.sh ~/Downloads/alive108-<newsha>.apk   # tag optional
```

Then either paste the printed `gh release create` line into an authed
shell, or follow the printed github.com steps (the body lands on the
clipboard on macOS/Linux).

## Feature-list verification (item 2 — every bullet traced to evidence)

| notes claim | evidence |
|---|---|
| Plan by dose, per-mode dose+emission bands, ~35× AC-car/foot spread | `testday-android-report.md` compare row PASS; `10-shipped.md`; README demo-OD numbers |
| Chooser beat: equals draw → settle → verdict pill, CPCB per-segment colours | `route-chooser-report.md` (e2ff634 — 3 OD pairs on-device, strip-race fix caught) |
| Live trip: turn chrome, 1 Hz counters off route strip, reroute, receipt→ledger | `testday-android-report.md` nav → receipt PASS ×2 |
| Ledger: day arc, week strip, receipts, Delhi-today card | `testday-android-report.md` rows; `codebase-mobile-report.md` screen table |
| Air alerts engine + real banners; depart remind + daily brief switches wired | `notify-e2e-report.md` (iOS banners real; Android banner live in `testday-android-report.md` §b); switch wiring `b633a2d` / `codebase-mobile-report.md` findings 1–3 |
| Offline honesty: age-marked last-good, honest-empty, air-gapped gazetteer+map pack, outbox lands-once | `testday-offline-report.md` 8/8 PASS; pack = `delhi-ncr-z9-13-r1` 744 tiles / 27.4 MB (`map-depth-report.md`:105) |
| Consent-off = zero donation POSTs; no outbox file; wipe disarms pings | `testday-android-report.md` §f pcap + §a wipe; `apk-v10-report.md` consent row |
| hi/en full localize, English default | `testday-android-report.md` §g Hindi flip PASS |
| Layers: fires, k≥3 corridors, reports; BandScale; freshness chip | `codebase-mobile-report.md` component table (LayersSheet/ReportsLayer/CorridorLayer/HazardLayers/BandScale/FreshnessChip all "real") |
| Sideload/debug-sign/Play-Protect note, badging, cleartext | `apk-v10-report.md` binary block + README "Run it yourself" |
| HTTP :80, k≥3 aggregate-only, phones-measure-nothing, demo capacity, young community, iOS sim-only, NCR-only | README "What it does not claim"; `PRIVACY.md`; `10-shipped.md`; prod `GET /v2/city/moves → min_k: 3` |

No unverified claims shipped. The two items the reports flag as
emulator-unproven (basemap labels on SwiftShader, multi-touch) are
rig notes, not release-notes claims.

## Script test transcript (this box, stand-in 200 KB apk @ HEAD)

- `alive108-b633a2d.apk` → sha/size computed, `b633a2d` resolved
  in-repo, filled body written + clipboard, both paths printed,
  Target=base/v2 (build IS tip). PASS
- `random.apk` → exits 1: "not alive108-<sha>.apk — rename or export
  BUILD_SHA". PASS
- `alive108-deadbeef.apk` → warns "deadbeef is not a commit in this
  clone — pull first", still emits instructions. PASS
- `bash -n` clean; `pbcopy` path exercised on macOS.

## Honest gaps

- Tag target: if the freeze commit lands on `base/v2` tip at upload time
  the web flow targets `base/v2`; if anything lands after, the script
  prints the paste-a-sha variant + the `git tag` fallback.
- `RELEASE-NOTES.filled.md` is regenerated per run — the template is the
  only committed notes file.
- Release is marked **pre-release** (sideload demo, not a store cut).
