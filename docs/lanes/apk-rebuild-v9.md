# apk-rebuild-v9 — SUPERSEDED (lead built directly)

This brief is stale — the rebuild happened outside the lane flow:

- `4f60b28` footer-CTA fix (dead-pill kill) → built by lead, `alive108-4f60b28.apk`
- `6b0bacf` + DelhiToday species tiles → `alive108-6b0bacf.apk` —
  THE binary under verification (apk-v9 lane devin-ac65c4b2 + its KVM child)
- Verification folded into the same lane (verify + cut8 app beats re-tape
  on one device, one child). See docs/lanes/apk-v9-report.md when it lands.

Recipe that worked (macOS box, ~17s incremental): mirror init.gradle
already at ~/.gradle/init.d/mirror.gradle, foojay line already stripped,
`cd Mobile/android && EXPO_PUBLIC_API_URL=http://65.2.28.40 ./gradlew
assembleRelease -x lint`. Disk: keep ≥5Gi free (DerivedData + app/build
cleanup frees ~4.6Gi).
