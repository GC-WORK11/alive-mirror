You are the demo-video v3 lane for ALive-108. The app just rebuilt (`6bafd2b`): home is now the dosimeter (YOU'VE BREATHED TODAY hero, THE MOVE, YOUR DAY ledger, DAYS AHEAD, HOW YOU FELT, budget ring) and travel is a feature via the "Where to?" CTA. Video v2 (`docs/demo/beats/` + assemble.sh, cut2 2:37) is stale — its app beats show the old DayScreen, and its web beats need re-verification against current live.

Deliver: cut3.mp4 ≤2:55, same assembly pipeline, all-real footage, the dosimeter arc.

Repo: <owner>/Delhi-Air-108, branch base/v2 (pull latest). Video tooling: `docs/demo/` — read assemble.sh + the beats manifest + prior lane notes in docs/plan. Android KVM emulator on this box (KVM perms, adb input quirks — your memory notes apply). Live: http://alive108-2699c171ddded465.elb.ap-south-1.amazonaws.com.

HARD RULES
- Push code/docs only — never deploy. GETs + /v2/plan + /v2/reroute only on live. NEVER POST /v2/feedback, /observe, /v2/trip.
- All footage REAL — the emulator drive or live-web capture, never mock/screenshot-of-mock. The AWS-console beat stays a marked placeholder (~25s) — the owner films `80_aws.mov` himself; keep the slot + shotlist pointer.
- Keep the proven assembly: same ffmpeg recipe, same caption language (mono lower-third, paper), ≤3:00 hard cap, target ≤2:50.

MANDATE
1. Re-shoot the app beats on a release APK at HEAD (build it if the apk-drive lane hasn't published one — or reuse the rebuild lane's recipe: gradle assembleRelease on this box). The beats to capture on device:
   - cold open on HOME: dose hero + "outside now" + budget ring (this replaces the old DayPeek beat)
   - scroll: THE MOVE → YOUR DAY → DAYS AHEAD → HOW YOU FELT → budget (one smooth pass, ~15-20s usable)
   - the journey beat: "Where to?" → search → compare (dose heroes + N× + "leave tomorrow 12:30 → breathe ~12% less" line if it renders) → nav → receipt
2. Re-verify every web beat against live TODAY (numbers moved): landing hero breath figure, a→b draw, watch-the-day, recorded strip, /v2/reach veil, admin engine room + the model-grades-itself card IF it has shipped by the time you shoot (check live /v2/skill).
3. Re-time the script: the dosimeter arc order — hero → your-day → journey/dose-gap → reach → days ahead → admin engine room → close. ≤2:50.
4. Assemble cut3.mp4 via the pipeline; attach it + a shot-list of what each beat proves. Update docs/demo-day.md beat table if any beat's live number changed.

Report: cut3 attachment URL, beat→source table (each beat's live probe evidence), what's still the owner's (AWS console film), any beat that couldn't be shot real + why.
