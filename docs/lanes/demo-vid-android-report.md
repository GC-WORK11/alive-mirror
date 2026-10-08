# demo-vid-android — one continuous demo take of the Android release APK

Lane: `demo-vid-android` · recorded 2026-10-08 ~16:30 IST on the KVM rig (AVD `demo` = pixel_7, android-35 google_apis x86_64, 1080×2400, `-no-window -gpu swiftshader_indirect -no-snapshot -no-audio -memory 4096`, serial emulator-5554). APK `alive-63b7ed4.apk`, sha256 `4fe61126c9f4af4413aad1beaf620f12d023686a1ab2a03f71098282abed36f0`, 169,315,792 bytes — verified before install, not rebuilt per brief. Repo HEAD at push: `dd2aec3` (`base/v2`). PROD API `http://65.2.28.40` — the app itself called it; no writes issued by the drive. No deploy.

## Deliverable

`alive-demo-android.mp4` — **108.6 s**, 1080×2400 portrait, 30 fps, H.264 (~5.3 MB). One continuous `adb shell screenrecord --time-limit 240` take (212.9 s raw), trimmed with ffmpeg concat-filter to remove dead air only: the install wait, the uiautomator-dump pauses, a ~15 s stale-results wait, and a ~45 s stretch where the scripted drive lost the app to the launcher (see honest notes). No overlays, no voice, no staged content.

Drive method: single adb-driven Python script (`input tap/text/keyevent`, `uiautomator dump` ≥2.5 s-throttled, `dumpsys window` focus checks, `emu geo fix 77.2090 28.6139`). Beat timestamps below are **final-video** times, verified frame-by-frame against the mp4.

## Beats

| t | beat | result |
|---|------|--------|
| 0–9 s | sideload while rolling | **pass** — recording started before `adb install`; launcher drawer open during install, app grid visible |
| 9–16 s | cold open → ambient hero | **pass** — home paints `63 µg/m³ moderate`, "the air near central Delhi" |
| 16–27 s | onboarding, all pages | **pass** — `delhi · right now ~63`, "Every Delhi trip has an air price", "Nothing personal leaves this phone", "One choice — and it's yours", "One permission — where you are" |
| 27–31 s | consent + OS location grant | **pass** — consent page tapped; OS dialog *"Allow Alive to access this device's location?"* on camera, "While using the app" granted |
| 31–55 s | coach-tour, all 5 stops | **pass** — "the air around you", "your day", "least-bad hours", "Where to?", "your lungs' calendar" — each shown ~4 s, next-tapped, dismissed |
| 55–61 s | home live numbers + locality | **pass** — `63 moderate` + "In Delhi's air right now" card + locality caption "read near New Delhi · nearest live monitor ~1.7 km away · air reading: 9 min old" + doors |
| 61–72 s | air-map + tap readouts | **pass** — map opens ("the air map / redder = worse / 52 live stations"), two taps, readout captions "now ~63 µg/m³" and "62 µg/m³ — moderate" visible |
| 72–104 s | live search, both phrases | **pass** — `ashook nagar shadara` typed on camera → real Ashok Nagar/Ashoka rows; field cleared with DEL keys; `pawan bakery near hanuman mandir` typed on camera → after a real ~15 s server wait the list swaps to Hanuman Mandir Road results (Kulfi Kuremal Family, Dujana House, Shiv misthan Bander bakery, Shyam Sweets, Monginis, Theobroma — 4.3–4.6 km) |
| 104–105 s | destination pick → chooser | **missed** — pick tapped a result row while the list re-rendered; the app bounced back to an empty Where-to sheet instead of mounting the chooser. Verdict pill never captured. Shown honestly: the pick and the empty sheet are in the take |
| — | nav / parked-time | **skipped** — chooser never mounted, so nav was unreachable; ~15 s of attempts inside the drive, then bail per brief |
| — | drawer → settings | **missed on camera** — the drive reached it (beat log has real taps + drawer open) but a back-press chain had already ejected the app to the launcher; the stretch is trimmed as dead air. No drawer/settings frame exists in this take |
| — | Trips + DelhiToday | **missed on camera** — same ejection stretch; doors were tapped blind on the launcher |
| — | week / lungs-calendar sheet | **partial** — the sheet itself never mounted on camera, but its coach-tour card ("your lungs' calendar — seven days stick up here as they count") is fully visible at ~t50–55 during the tour |
| 105–108 s | end settled on home | **pass** — relaunch splash → settled home `63 moderate` + locality caption |

## Honest notes

- This is **take 18 of 20 recorded takes**. Earlier takes failed on either content (onboarding Next taps eaten during sheet mount, coach-tour racing its mount window, result-row picks landing during re-render) or on the ~180 s recording cap. The drive script hardened each failure into the next take: self-verifying Next taps, substring a11y matching, DEL-key field clears, focus-guarded recovery.
- The same mid-take failure class hit this take too: after the (real, on-camera) search section, the pick landed during the stale→fresh results swap, the app returned to the empty Where-to sheet, and the scripted recovery taps briefly left the app for the launcher/Google app (~45 s). That stretch contains no product content and is cut as dead air — it is the only large cut in the video and it means **beats 9–13 are not on camera**. Everything before it is real and unmodified.
- `screenrecord` honors `--time-limit` values past the documented 180 s on this build — the raw take is 212.9 s, so no beat was lost to the cap.
- Basemap text labels do not render under SwiftShader (emulator GL limit, not an app bug); map readouts and station counts do render.
- The `emu geo fix` push produces a real fused fix only after Google Maps has run once on the image; locality captions ("read near New Delhi · ~1.7 km away") show the fix took.
- The notification-permission dialog arrives on its own schedule (~10–15 s after the location grant) and is visible over home before the tour.

## File inventory

| file | what |
|------|------|
| `alive-demo-android.mp4` | the 108.6 s showcase cut (attached to the session) |
| `frames/f1..f8_*.png` | 8 key frames: sideload drawer, onboarding hero, onboarding page, OS location dialog, coach-tour card, air-map readout, pawan-bakery results, settled-home end |
| raw take | `t18.mp4` (212.9 s, unmodified capture — session box `/tmp/t18.mp4`) |
| drive script | `/tmp/drive.py` — deterministic adb drive used for all takes |
| beat log | `/tmp/beats2.log` — per-beat epoch marks for takes 15–20 |
