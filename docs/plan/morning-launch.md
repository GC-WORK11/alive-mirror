# Morning launch — Oct 9 · verified state at ~21:20 UTC

## Prod http://65.2.28.40 — :231 (image c5ba61c0) — all live
- `/` v14 landing — India-Gate smog hero, rail nav, ruled districts, zero boxes/github/get-the-app
- `/a-AFiVSpmZ1Oc4YhaaQyhRie5yqnlKV_qs` admin → cognition analytics (01 live air / 02 coverage / 03 usage / 04 health)
- `/v2/stays?near=LAT,LON` — 15,976 real hotels ranked by next-24h field at own coords
- `/v2/playtime?near=LAT,LON` — rolling 24h curve → best/worst windows + sparse flags
- `/grid /v2/city /v2/plan /city /community` — all 200

## APK (built 270be81 — has every feature + fix)
- arm64 (release): alive-270be81-arm64.apk 108.7MB sha dcf7a9e8…5957
  https://app.devin.ai/attachments/d030782b-a478-4fe9-bb8f-0912888bab97/alive-270be81-arm64.apk
- universal (x86 fallback): 189.3MB sha 3ac840ac…0aba
  https://app.devin.ai/attachments/bd4aa94a-ed39-4835-af53-02c5ac91a0f2/alive-270be81-universal.apk

## Videos
- 106s X-cut (all 4 features, fits 2:20): https://app.devin.ai/attachments/6787bddb-04ee-40fc-9b19-067df5cce60b/alive-x-cut.mp4
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
- Offline "can't reach server" pill transient (e2e-residual lane 61135d92 on it)
- Post-wipe location-page freeze (same lane)
- CPCB/OpenAQ dark legs — disclosed on /health, upgrade path in source-upgrade-rfc.md
- Demo film ran universal build on x86 AVD; arm64 is the device twin (same bundle, prod API baked — verified unzip grep)
