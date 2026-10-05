You are the first-open lane for ALive-108 — the cold-install experience audit. A judge or a Delhiite installs the APK and opens it: what happens in the first 30 seconds decides everything. Deliver: a timed audit + fixes for every wall between install and the first real "my lungs" number.

Repo: <owner>/Delhi-Air-108, branch base/v2 (pull latest — lanes push often; rebase before push). App: Mobile/ (Expo RN SDK54). Android emulator on this box (KVM perms/maven mirror notes apply if it's a KVM box; if this box lacks KVM, say so and pivot to whatever device surface exists — iOS sim or a thorough static trace of the launch path).

HARD RULES
- Push code only — never deploy. NEVER POST /v2/feedback, /observe, /v2/trip to live.
- `npx tsc --noEmit && npx expo lint` before push.
- Onboarding/consent stays HONEST — never auto-consent or hide the donation ask; but nothing that doesn't need consent should block the first value moment.
- Nothing fake: if the first number can't render without the field, the honest loading state must be fast and explicit, not a dead screen.

MANDATE
1. Cold install the release APK (build at HEAD if none exists on this box). Stopwatch the launch: install → icon tap → first pixel → first readable content → first REAL number on screen. Time each.
2. Audit the walls: location permission prompt timing (does it block before value?), consent sheet (when does it appear, can it be deferred?), empty daylog ("0h accounted" — does it still land as meaningful?), first-fetch latency on venue-grade wifi (throttle to ~1Mbps and re-measure first-number time).
3. Fix what fails the 30-second test: the dosimeter hero should paint SOMETHING real fast (disk-first pattern exists from the offline lane — check it's used on first open, not just warm opens). Walls that exist before value should move after it, unless consent-honest.
4. Verify the fixed cold-open on the emulator — record it (screen recording the launch → first number).
5. Report: timing table before/after, walls found+fixed (or defended), cold-open recording, what still blocks first value honestly (e.g. field fetch floor).
