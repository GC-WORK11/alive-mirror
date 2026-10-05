# Lane: apk-drive-v3 — the FINAL demo-phone build

Spawn only after perf-fps lands (its Mobile commits should ride this binary — one final
build, not per-commit). Same shape as docs/lanes/apk-drive-v2.md; the delta is HEAD.

## Deliver
- Release APK at current base/v2 HEAD — carries: dosimeter home, cold-open ~2.8s,
  hi-locale, why hero, vibe-polish craft, perf/nativeDriver fixes (whatever perf landed).
- Emulator drive at HEAD on a Linux child (KVM box): cold-open ms, home surfaces,
  journey incl. DRAWER2CLS regression, consent-OFF silent in logcat, why hero,
  hi Devanagari no-tofu, D1 drag real-bug-vs-artifact verdict.
- Upload APK + ≤2min recording via upload_attachment. This APK is what the owner
  installs on the demo phone Oct 8 morning — the filename should carry the HEAD sha.

## Checks that must pass before upload
- App hits LIVE api (ELB) — confirm requests in logs, not localhost.
- No dev-bundle artifacts: it's a Release build — the iOS-crash dev-bundle class
  can't exist; verify zero red screens / logcat fatals across the drive.
- The home must show LIVE numbers (≈µg today, outside now µg/m³, THE MOVE windows)
  — screenshot proof, not a claim.

Report: APK URL, sha inside the binary if derivable, surface×verdict table,
cold-open ms, D1 verdict, diffs-vs-a2b36fe.
