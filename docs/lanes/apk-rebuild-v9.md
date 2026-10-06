# apk-rebuild-v9 — canonical binary at HEAD + device drive

You are the apk-rebuild lane for ALive-108 (AWS×WeMakeDevs Air track).
Repo: <owner>/Delhi-Air-108, base/v2, pull latest.

## Build (macOS recipe — proven)
1. `cp scripts/gradle-init-mirror.gradle ~/.gradle/init.d/mirror.gradle` (mkdir -p init.d first)
2. If `foojay-resolver` fails: `sed -i.bak '/foojay-resolver-convention/d' Mobile/node_modules/@react-native/gradle-plugin/settings.gradle.kts`
3. Ensure ≥5GB free disk; `./gradlew --stop` if fileHashes lock wedges
4. `cd Mobile/android && EXPO_PUBLIC_API_URL=http://65.2.28.40 ./gradlew assembleRelease -x lint` (~5min → app/build/outputs/apk/release/app-release.apk)
5. Rename alive108-<shortsha>.apk, sha256 it, upload_attachment, send me the link.

## Drive (spawn ONE linux/KVM child with ATTACHMENT marker for the apk)
Checklist on the shipped binary (canonical-artifact rule: install the UPLOADED apk,
sha256-verify before install — never a same-commit rebuild):
- cold open → first real number timing
- "Where to?" pill tap via `input swipe x y x y 100` (adb input TAP is flaky on
  RN rows — swipe at identical coords is the reliable inject; report BOTH)
- search sheet ×10 clean opens (the autofocus SIGSEGV fix)
- armed vehicle-skip first-tap close
- µg gloss on populated DayPeek card (en + hi): seed daylog if needed
- consent-off pcap: only /v2/plan + /v2/reroute POSTs, zero writes
- cold-eye fixes visible: receipt band collapse (no "0.1–0.1 kg"), hi ledger
  clock shows पूर्वाह्न/अपराह्न not am/pm
- HomeScreen pill works end-to-end (dead-tap residual — re-verify on Android)
Report → docs/lanes/apk-rebuild-v9-report.md committed; verdict table with
screenshot/pcap evidence links. NEVER POST mutating endpoints to live.
