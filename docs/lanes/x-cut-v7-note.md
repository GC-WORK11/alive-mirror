# x_reel_v7.mp4 — 96s X-ready demo reel (v7 air-gate)

Re-cut on the v7 binary — the old 106s reel was filmed pre-airgate (band-tinted route polylines since removed). Filmed end-to-end on a KVM x86_64 emulator, frame-indexed cut, real numbers only, zero overlays.

- https://app.devin.ai/attachments/af5fda3a-96bc-483e-8447-032426c8728b/x_reel_v7.mp4 · 95.6s · 8.6MB h264 1080x2400 yuv420p ~30fps · no audio · sha256 cdd6a5da5c4966154815eddbbd50ad22c030a0235b26cdaab2324570f494b533

## Binary
`alive-90bc055-universal.apk` — sha256 `776540987ca732d52dbd7677a2950d47961911157901177b6771c94749c2c849` (188,869,392 B, 4-ABI universal, `EXPO_PUBLIC_API_URL=http://65.2.28.40`, usesCleartextTraffic). base/v2 @ 66c0c8e, air-gate build 90bc055.

## Rig
KVM x86_64 AVD `demo` (pixel_7, android-35 google_apis): `emulator -avd demo -accel on -gpu swiftshader_indirect -no-window -no-snapshot -no-audio -no-boot-anim -memory 3072`. `/dev/kvm` needed `sudo -n chmod 666` (root:kvm 0660, ubuntu not in group). Location dual-inject: `adb emu geo fix 77.2167 28.6315` (gps) + `cmd location providers add-test-provider fused` / `set-test-provider-enabled fused true` / `set-test-provider-location fused --location "28.6315,77.2167"` — the bare `Location[fused ...]` string form throws IllegalArgumentException on this Android 15 image; the `--location` flag form works. Perms granted pre-install (FINE+COARSE+POST_NOTIFICATIONS). `adb root` on google_apis image; seeds pushed to `/data/data/com.anonymous.app/files/` then `chown -R 10209:10209` (uid from `stat -c %u`).

## Seed
Per lane brief verbatim: vehicle car/petrol/y2017_2020; consent `sharing:"off"` (hard rule — zero telemetry POSTs); settings/welcome/coach as specified; ledger = the exact 10-trip array ≈152µg wk, ts-shifted; daylog = 19 samples over last ~3h ending now−1min (amb 80–98, bz≈0.42×amb, jittered around 28.6315,77.2167, checkins keyed to device-local day). No daysum.json (app recomputes). Result on screen: hero ≈82–90 µg, "3h+ counted", ≈225 µg this week.

## Filmed takes → reel segments
Each beat = one continuous take (`adb shell screenrecord --bit-rate 8000000 --size 1080x2400`). SwiftShader screenrecord collapses pts (all-blank pts_time), so segments are cut by frame index (`select='gte(n,N0)*lte(n,N1)',setpts=N/(R*TB)`), stamped R≈5.5–7.5 fps real-time, `tpad` end-holds on money frames, `fps=30,format=yuv420p`, concat, `-an`.

| # | take | source frames | reel ts | beat |
|---|------|---------------|---------|------|
| 1 | b1.mp4 (250f) | n=24–144 +2.0s hold | 0:00–0:18 | cold open → hero ≈82 µg "moderate · 3h counted · ≈225 this week" |
| 2 | b2.mp4 (107f) | n=24–80 | 0:18–0:26 | Where to? → "air…" → "the air map" intent |
| 3 | b2.mp4 | n=80–106 +3.0s hold | 0:26–0:32 | kriged field paints + legend (51 live stations, 11 min old) + tap readout "81 µg/m³ — moderate · Connaught Place" |
| 4 | b3.mp4 (288f) | n=40–120 | 0:32–0:43 | type "connaught place" → results |
| 5 | b3.mp4 | n=128–156 +0.5s | 0:43–0:47 | place sheet → Directions → "checking every way there…" |
| 6 | b3.mp4 | n=184–240 | 0:47–0:58 | compare options: Car ≈1 µg, windows-down ≈2 "+1 µg more than car", Bike ≈2 "~2× more inhaled" |
| 7 | b3.mp4 | n=240–288 +3.0s hold | 0:58–1:09 | Bus ≈2 ~2.6× · Auto ≈3 · Bicycle ≈7 ~7.2× · Metro ≈8 ~8.7× · **On foot ≈10 "~10.9× more inhaled than car · −59% air · worth it"** |
| 8 | b45.mp4 (151f) | n=24–120 | 1:09–1:22 | "hotels near lodhi garden" → "stays — lightest air first" → sheet |
| 9 | b45.mp4 | n=120–136 +3.0s hold | 1:22–1:28 | ranked hotel rows ~100 µg · "11.x µg lighter" each |
| 10 | b45.mp4 | n=136–151 +4.5s hold | 1:28–1:35.6 | "when to go out": least-bad window 13:30–19:30 ~86 µg/m³ avg (8 lighter than now) + banded 24h curve + heaviest ~140 |

## Gates verified (extracted frames, final render)
- **Air intent**: kriged field visibly paints + "the air map · 51 live stations · air reading: 11 min old" legend + real tap readout "81 µg/m³ — moderate · Connaught Place".
- **Where-to air-gate**: ZERO colored field cells on every route/options frame in the cut — plain basemap only; picked = flat forest polyline, alternates = grey. (Source had a ~1.5s transient field paint at n≈160–178 while options loaded — place-phase paint by design; excluded from the cut.)
- **No dev-client toasts** in any kept frame.
- **Real numbers only**: every µg on screen is app output; no overlays.
- **Consent off**: `consent.json sharing:"off"` seeded before recording; filming drove only search/plan/stays calls (no pcap taken — optional gate).

## Discarded takes
- **b3.mp4 take C (28s)** — filmed the Google Calendar first-run: 3× `keyevent 4` from the explore sheet exited to the launcher and subsequent blind taps opened Calendar. Lesson baked into `~/film.sh`: force-stop + `monkey` relaunch + uiautomator home-check BEFORE recording; never blind-chain backs.
- Early where-to take (pre-reseed): "couldn't get your location — type a place instead" until fused test-provider was injected.

## Notes for next lane
- Reusable rig scripts left on the box: `~/film.sh` (verify-home → record → pull), `~/drive.py` (adb+uiautomator helper), `~/seedgen.py`, `~/cut.sh`.
- screenrecord emits frames only while surfaces change; ~4–8 fps effective. Frame-indexed selects are mandatory (pts are garbage); stamp 5.5–7.5 fps for real-time pacing, `tpad=stop_mode=clone:stop_duration` for end-holds.
- `input text` needs `%s` for spaces. `screenrecord --time-limit` self-terminates cleanly.
