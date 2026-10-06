# Lane: hi-parity-v2 — Hindi coverage after the component overhaul

## Why
app-overhaul-v2 `d210492` rewrote labels/copy across EVERY Mobile
surface (doors, chips, heroes, tiles). The coldread lane's en/hi
parity rule can now be broken: new English strings without hi.json
keys → English leaks in Hindi mode on the demo phone. The owner
WILL show Hindi.

## Scope
- Static: diff en.json vs hi.json key coverage after `d210492` —
  every user-visible string needs a hi entry or an explicit
  localization-exemption reason.
- Dynamic: run the app on iOS sim in Hindi (the hi toggle lives in
  Settings) and screenshot EVERY surface: home hero + doors,
  the move, DelhiToday, compare, nav chrome, receipt, ledger,
  settings, onboarding. Flag: English leaks, tofu boxes (the
  Devanagari font issue solved before — verify it holds on the
  new type), clipped/overlong Hindi on the new chunky components
  (tiles have less room than prose).
- Fix what's broken (hi.json additions, fit adjustments for
  overlong strings — NOT restructuring the components).
- Gates: npx tsc --noEmit && npx expo lint && both test-runners.
  Commit to base/v2 (pull --rebase).

## Deliverable
- Report → docs/lanes/hi-parity-v2-report.md with per-surface
  screenshots + the leak list (or clean verdict) + what the APK
  rebuild must re-verify in Hindi.
- Never deploy. Live API GETs only. SearchScreen lifecycle code
  is another lane's territory — don't touch it.
