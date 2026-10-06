# video-v5 — cut5.mp4 report

**Deliverable:** `~/video/cut5.mp4` — 168s (2:48), 1920x1080, h264, 4.4 MB.
Uploaded: https://app.devin.ai/attachments/39400707-7135-41b9-a87a-375c18fe9c47/cut5.mp4

Assembled by `scripts/video/assemble.sh` (OUT default now `cut5.mp4`; slot table
rebalanced — see diff). Title card stamps live `build_sha=fa08e968` from the NLB.

## What changed vs cut4

Three beats re-recorded because their footage predated shipped changes; the rest
of cut4's tape was kept verbatim.

| Beat | Slot dur | Source (cut5) | What changed vs cut4 |
|---|---|---|---|
| `10_hero` | 11s | `~/video/beats/10_hero.mp4` — rec_hero2.mp4 sparse-hero still + rec_flow.mp4 populated hero | **Re-recorded.** Fresh-install hero is now the designed sparse state (`dbbc76a`): 5s sparse (no fake data) → 6s populated hero |
| `25_journey` | 14s | `beats/25_journey.mp4` — rec_chain265.mp4 run1 chain (pts ~1290–1425) | **Re-recorded.** compare sheet → scroll → **Auto-rickshaw ≈6µg card SELECTED** → Start → nav lands on the auto 3.6km route (`59a7da8`: compare→Start launches the selected option, pick persists) |
| `26_receipt` | 8s | `beats/26_receipt.mp4` — rec_run3.mp4 real-trip tail (n≈5040–5460) | **New slot.** Arrival receipt (≈1µg · 2.9km · Bicycle·least-smoke rd · "47.6× less than Metro + walk") → sidebar → Trips ledger listing **2 trip rows** (`0fdd597`: dedupe gone) |
| `20_yourday` | 10s | cut4 beat | Kept |
| `28_today` | 8s | cut4 beat | Kept |
| `30_dosegap` | 24s | cut4 beat | Kept (was 26s — trimmed for budget) |
| `40_city` | 24s | cut4 beat | Kept (was 26s — trimmed for budget) |
| `65_community` | 8s | cut4 beat | Kept |
| `50_admin` | 22s | cut4 beat | Kept (was 24s — trimmed for budget) |
| `80_aws` | 25s | placeholder card | Owner-filmed console slot (`docs/plan/aws-console-shotlist.md`) — drop `80_aws.mov|.mp4` into `~/video/beats/` and re-run assemble.sh |
| `00_title`/`90_close`/`99_end` | 3/6/5s | cards + cut4 beat | Kept |

Total 168s against the ≤2:50 budget with the AWS placeholder still inside.

## Recording conditions

- Build: iOS-sim Release app at base/v2 HEAD `0a26f5a` (apk-v4 APK not up yet; same-HEAD rule per lane doc)
- Live API `http://65.2.28.40` — GETs + /v2/plan + /v2/reroute only
- `settings.json` `"share":false` on the sim before every recorded nav trip; receipts show "kept on this phone only"
- Numbers verified against live endpoints during capture (plan doses ≈2-7µg for CP→IG auto/car options; receipt/ledger reads from the app's own ledger.json)

## Known caveats

- `26_receipt` shows a bicycle trip from run3 rather than the run1 auto trip — the run1 process was GC-killed before its receipt (sim-only `hermes HadesGC` segfault, see prior lane notes). The beat still demonstrates the dedupe-gone ledger: both trips appear as separate rows.
- Journey beat splices run1's compare→select→Start with the same run's nav-landing; no cross-run footage mixed.
