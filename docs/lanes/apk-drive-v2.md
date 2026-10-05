You are the APK-drive-v2 lane for ALive-108. HEAD has moved a lot since APK `a2b36fe` (the owner's current demo-phone build): first-open's value-first cold open (`33112f4` — location ask moved post-consent, sheet gated until first read paints, ~+2.8s to first number measured on iOS sim), hi-locale's Devanagari coverage (`416a195`, `c41570a` — still landing more), DelhiToday's `why` hero under the dose hero (`8d032e3` — needs /v2/city `why.line`, live tonight), plus assorted server fixes. Deliver: (1) a fresh release APK at HEAD, uploaded as an attachment for the owner's phone; (2) an emulator smoke of every surface on the new home; (3) defects found, fixed, rebuilt, re-verified.

Repo: <owner>/Delhi-Air-108, branch base/v2 (pull latest — lanes push often). App: Mobile/ (Expo RN SDK54). Android KVM emulator on this box — read memory `android-emulator-box` (KVM perms, Maven-429 mirror fix, adb input quirks) BEFORE building. Live API: http://alive108-2699c171ddded465.elb.ap-south-1.amazonaws.com (GETs + /v2/plan + /v2/reroute only — NEVER POST /v2/feedback, /observe, /v2/trip).

HARD RULES
- Push code only — never deploy. `npx tsc --noEmit && npx expo lint` before any push. Never hand-edit android/ios/ generated dirs.
- vibe-polish lane is live in the same files — pull+rebase RIGHT before push; keep your diff small; re-run tsc/lint if the tree moved.
- Nothing fake: surfaces that can't render without data get the honest-empty capture, not a mock.

MANDATE
1. Build the release APK locally at HEAD (the path that worked before: local gradle assembleRelease per prior lane notes — do NOT eas cloud build).
2. Install on emulator, cold-start recording, then verify against live (curl cross-checks, not vibes):
   a. **Cold-open regression**: first real number paints BEFORE the consent sheet rises (~+2.8-3.0s target on Android — measure it: adb screenrecord or logcat timestamps icon-tap → first text render → sheet rise). Location dialog must NOT fire before consent.
   b. **DelhiToday why hero**: /v2/city `why.line` live tonight = "the air is barely moving — the day's pollution is sitting over the city" — it must render under the dose hero (curl the wire first so you know the expected string).
   c. Journey intact: search → vehicle wizard (metro/cycle pick must stick — the DRAWER2CLS clobber was fixed at `a2b36fe`, regression-check it) → compare (dose heroes + ×-gap) → nav counters → receipt.
   d. hi-locale on device: switch to Hindi — the home hero, THE MOVE, day arc, why line must render Devanagari (no tofu boxes); the decision line must be Hindi composed from served windows (no wire-English leak).
   e. Consent OFF: zero uploads in logcat.
3. Hunt the D1 residual from the last drive: injected scrolls/drags die on the DelhiToday sheet + sidebar ScrollViews on the Android-15 emulator while taps work. Try to reproduce with REAL adb input swipe + `adb shell dumpsys input` — if drags are dead on emulator too, dig ONE level (is it the sheet's gesture handler swallowing? nested ScrollView?); if it's an emulator-only artifact say so with evidence.
4. Fix small defects you find; rebuild; re-verify.
5. Upload the final APK + a ≤2min smoke-drive recording via upload_attachment.

Report: APK attachment URL, surface×verdict table (incl. cold-open ms on Android), D1 verdict (real bug vs emulator artifact — evidence), defects fixed, notes for the owner about what changed since `a2b36fe`.
