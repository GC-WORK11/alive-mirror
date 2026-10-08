# demo-vid-admin lane report — one continuous take of the engine room on live prod

Date: 2026-10-08 · Branch: `base/v2` (HEAD `1ff8d62`) · Scope: a single
unbroken screen recording of the admin console on **prod**
(`http://65.2.28.40/a-AFiVSpmZ1Oc4YhaaQyhRie5yqnlKV_qs` — the obscure
mount from `server/admin_mount.py`), from gate card to sign-out.
Prod was touched **GET-only plus the login/logout POSTs themselves** —
no staging, no fixture, no deploy.

Deliverables: `alive-admin-board-demo.mp4` (58.8 s, 1440×812, h264,
2.3 MB) + 6 frames in `demo-vid-admin-shots/`.

---

## 1. The rig (this box is macOS — no Xvfb, used the CDP recipe)

- Real **Chrome 154** launched with
  `--remote-debugging-port=29229 --user-data-dir=~/.chrome-admin-vid`
  (dedicated throwaway profile — required on Chrome ≥136, and it also
  means no personal cookies/history can leak into frame).
- `playwright-core` (`~/admin-vid-rig/`) attaches over CDP, opens a
  `Page.startScreencast` (jpeg q88, 1440×900 cap) session, writes every
  `screencastFrame` to disk with its protocol timestamp, acks each one.
- ffmpeg concat-demuxer rebuilds the mp4 at **true wall-clock pacing**
  (per-frame duration = timestamp delta), then `fps=30` resamples CFR +
  1 px crop for h264 even-height. Page-only capture — no OS chrome.
- Driver: `record.mjs`. Rehearsal pass (`rehearse.mjs`) mapped the DOM
  first: one continuous 9,720 px board, hero + 8 numbered sections, no
  tab strip ("usage" is section 07, inline in the scroll).

## 2. The take — beats as recorded

| t (s) | Beat |
|---|---|
| 0–4 | Gate card hero — `ALIVE / engine room · OPERATOR ONLY`, empty token field |
| ~4–9 | Token filled (JS value-set — see §4) → **SIGN IN** → board renders; masthead briefly reads `9 LOCKED — SIGN IN AS OPERATOR` then unlocks to full internals — the transition is visible on camera |
| 9–50 | Slow anchor-scroll top→bottom: hero (59.5 µg/m³ SATISFACTORY, 25 cells) → freshness tiles (14 m rebuild, 52 feeds, 100 pts, 9,03,058 streets priced, 71 fires) → 01 feeds/pipeline → 02 honesty (hidden-monitor 13.9 µg/m³, dose-math table, engine state, API stopwatch) → 03 causes → 04 districts → 05 live air map → 06 rider-sharing ledger → 07 usage counters → 08 archive + forecast self-grade table. ~2 s dwell per block; numbers are legible in every frame checked |
| 50–54 | Smooth scroll back to top — signed-in masthead (`SIGN OUT` · `NO PERSON IS EVER SHOWN · GROUPS OF 3+ PHONES ONLY` · `REFRESHES ITSELF · EVERY 30S`) |
| ~54–59 | **SIGN OUT** → gate card returns instantly, empty field; hold to end |

No cuts, no duplicates, no dead air — one take, 58.8 s.

## 3. Live numbers the video shows (as they were on prod, ~02:14 PM IST)

- city mean **59.5 µg/m³ SATISFACTORY** (indian aqi 99), median 62.1,
  worst 77.3, 25 sampled cells, 8% below a typical Oct day
- map rebuilt **14–15 m** ago (every ~15 m), **52** govt feeds,
  **100** map points, **9,03,058 / 10,70,459** streets priced,
  **71** fires (15 in belt), next rebuild countdown ticking live
- hidden-monitor honesty **8.8 → 13.9 µg/m³** (live recheck drifted
  while we watched — it's a live number, not a decal)
- dose math ×0.45 metro → ×1.3 walking/auto; engine: PathEngine,
  10,70,459 streets · 8,19,846 junctions, fingerprint `83ef9b91051bbd29`
- API stopwatch: air-at-point 16 ms avg (9/10 ≤25 ms), map 314 ms
- riders: 53 shared trips / 210.9 km, 30 phones ever shared,
  10 shareable streets (≥3 phones), 5★ ×2 reviews, 0 hazard flags
- archive: 63 saved maps since 2026-10-05, forecast self-grade table
  (+0h 90.9% band → +9h 28.9%)

## 4. Token handling — never on camera, never in this repo

- Pulled from SM `alive108/admin-token` to `~/.alive-admin-token`
  (`chmod 600`) via aws-cli in `~/.aws-venv` — the value **never entered
  the script's context, logs, this report, or any file in the repo**.
- The field is `type="password"` (masked natively) *and* it was filled
  by DOM value-set (`el.value = …` + input/change events) — no typing,
  no paste echo, no reveal state exists in the UI.
- Verified in the extracted frames: the field shows placeholder/masked
  dots only. The 49-byte secret (48 chars + LF, `[0-9a-z]` format)
  matched the documented shape.

## 5. Prod safety

- Only writes were `POST <mount>/login` and `POST <mount>/logout` —
  the flow the board itself is built for. Every other interaction was
  page scroll/read; no `api/*` mutating call exists to hit anyway.
- Board session ended by real SIGN OUT (cookie `Max-Age=0`), confirmed
  by the gate card returning on camera.
- Chrome profile deleted post-take hygiene: throwaway `user-data-dir`,
  nothing saved/synced.

## 6. Reproduce

```bash
cd ~/admin-vid-rig
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  --remote-debugging-port=29229 --user-data-dir=$HOME/.chrome-admin-vid \
  --no-first-run --window-size=1440,900 about:blank &
node record.mjs      # needs ~/.alive-admin-token (SM: alive108/admin-token)
# stamps.json → concat.txt: per-frame `duration` = timestamp delta to next frame
ffmpeg -f concat -safe 0 -i concat.txt -vf "crop=1440:812:0:0,fps=30,format=yuv420p" \
  -c:v libx264 -crf 20 -movflags +faststart alive-admin-board-demo.mp4
```

Honest limits: it's a video, so the 30 s self-refresh is only glimpsed
(masthead `UPDATED` ticks + the honesty tile drift); the `9 LOCKED`
transitional chip at sign-in is real prod behavior left in on purpose —
it shows the lock opening, which is the point of the shot.
