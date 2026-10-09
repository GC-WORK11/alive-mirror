# Morning launch — Oct 9 · verified state at ~21:20 UTC

## Prod http://65.2.28.40 — :231 (image c5ba61c0) — all live
- `/` v14 landing — India-Gate smog hero, rail nav, ruled districts, zero boxes/github/get-the-app
- `/a-AFiVSpmZ1Oc4YhaaQyhRie5yqnlKV_qs` admin → cognition analytics (01 live air / 02 coverage / 03 usage / 04 health)
- `/v2/stays?near=LAT,LON` — 15,976 real hotels ranked by next-24h field at own coords
- `/v2/playtime?near=LAT,LON` — rolling 24h curve → best/worst windows + sparse flags
- `/grid /v2/city /v2/plan /city /community` — all 200

## APK — install THIS one (v7, 90bc055 — every feature + every fix + air-gate)
- arm64 release: alive-90bc055-arm64.apk 108.3MB sha c6282daf…76fe3
  https://app.devin.ai/attachments/9af3be9a-b067-48e1-adc5-7aaa1670b7e9/alive-90bc055-arm64.apk
- universal (x86 emulators too): alive-90bc055-universal.apk 188.9MB sha 77654098…
  https://app.devin.ai/attachments/b3773c76-a29a-41a0-b222-26b987429306/alive-90bc055-universal.apk
- v7 = v6 (e2e-residual) + air-gate: plain basemap everywhere, PM2.5 field paints only on air intent; boot smoke all-pass on KVM AVD (cold 1563ms, zero crashes)
- universal x86 fallback (v5, 270be81): 189.3MB sha 3ac840ac…0aba
  https://app.devin.ai/attachments/bd4aa94a-ed39-4835-af53-02c5ac91a0f2/alive-270be81-universal.apk
- (v5 arm64 superseded — was missing the 5 residual fixes)

## Videos
- 95s X-cut on v7 (all features, air-gate true on camera, fits 2:20): https://app.devin.ai/attachments/af5fda3a-96bc-483e-8447-032426c8728b/x_reel_v7.mp4 — POST THIS ONE; the old 106s cut shows the removed colored routes
- 15min full take: https://app.devin.ai/attachments/1653d8a8-c80d-4bb7-a266-52f0e780da3b/v5.mp4
- landing v14 89s: https://app.devin.ai/attachments/4ecc601b-c2a1-4ba8-8fb7-2f87b97a113f/landing-v14-final.mp4
- admin console 61s: https://app.devin.ai/attachments/bc466100-90a0-4c3c-b78b-7198f1110d9b/admin-v2-final.mp4

## Vercel — ready on both branches
- `main` @40622c5 + `landing` @61b9a60 — v14 standalone index.html + 5 statics at root, prod-absolute API refs, zero github refs
- Caveat: HTTPS page → HTTP API = live widgets degrade honestly ("unreachable — retrying"), never fake. Prod direct-HTTP shows all live.

## Judges' pack (docs/judges/)
data-truth.md · demo-script.md (3-min, real numbers) · checklist-vs-brief.md · source-upgrade-rfc.md · x-post-thread.md

## HIS 2 decisions
1. APK public link: Devin attachment URLs 401 for outsiders → public squashed repo + Release asset (scripts/public-repo.sh), or /alive.apk route on prod (HTTP warning)
2. HTTPS for API if live numbers must show on the Vercel URL (needs domain + cert)

## Honest gaps
- e2e-residual ec2ed08 FIXED all 5 sweep leftovers (post-wipe freeze, offline pill, IST clock, expander, hi a11y) — baked in v6 APK
- CPCB/OpenAQ dark legs — disclosed on /health, upgrade path in source-upgrade-rfc.md
- Demo film ran universal build on x86 AVD; arm64 is the device twin (same bundle, prod API baked — verified unzip grep)
