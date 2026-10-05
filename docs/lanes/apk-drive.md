You are the APK-drive lane for ALive-108. HEAD now carries the dosimeter restructure (`c4a7801` home = dose hero + the move + arc + days) plus the offline-honesty batch (`a26fb4e`). Nobody has driven the NEW home on a real build. Deliver: (1) a fresh release APK built at HEAD, uploaded as an attachment for the owner's phone; (2) an emulator smoke of every surface; (3) any defect found, fixed.

Repo: <owner>/Delhi-Air-108, branch base/v2 (pull latest — other lanes push often). App: Mobile/ (Expo RN SDK54). Android KVM emulator on this box — read your memory notes `android-emulator-box` (KVM perms, Maven-429 mirror fix, adb input quirks) BEFORE building. Live API: http://alive108-2699c171ddded465.elb.ap-south-1.amazonaws.com (GETs + /v2/plan + /v2/reroute only).

HARD RULES
- Push code only — never deploy. NEVER POST /v2/feedback, /observe, /v2/trip to live.
- `npx tsc --noEmit && npx expo lint` before any push. Never hand-edit android/ios/ generated dirs.
- Other lanes share Mobile/ — pull+rebase right before push; if your tree moved under you, re-run tsc/lint.
- Nothing fake. If a surface can't render without data, capture the honest-empty state, don't fabricate.

MANDATE
1. `cd Mobile && npx eas-cli build` is NOT the path — build locally: `npx expo prebuild` if needed then gradle release, or the documented local release path (check how prior APKs were built — eas build --local or ./gradlew assembleRelease; pick whichever the repo/notes show working on this box). Target: installable .apk at current HEAD.
2. Install on the emulator. Cold-start recording. Drive every surface ON THE NEW HOME:
   - dosimeter home: dose hero card, "the move", week arc, days-ahead — do they render, do numbers match live (/v2/day, /v2/outlook — cross-check one figure by curl)?
   - journey intact: search → vehicle → compare (dose heroes + "vs lightest" deltas) → nav → receipt
   - ledger, Delhi today, settings
   - consent OFF path: nothing uploads
3. Hunt visual/perf defects on the new home specifically: overflow, clipped type, janky scroll, skeleton that never resolves (offline lane fixed the known hangs — verify), wrong-scale numbers.
4. Fix what you find (small, focused), then rebuild + re-verify the fix on device.
5. Upload the final APK via the upload_attachment tool and record the smoke drive (screen recording, ≤2min) — attach both.

Report: APK attachment URL, surface×verdict table, defects found+fixed, anything deliberately left for the app-rebuild lane (it's restructuring home — note collisions it should know).
