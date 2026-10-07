# demo-script-v3 — lane report

**Lane:** sync the stage script + judge card + morning runbook to the
Oct-7 Mobile fix wave (~19 commits) so the stage narration matches what
the app actually does.
**Scope:** `docs/plan/demo-script.md` (rewritten → v3),
`docs/plan/demo-kit.md`, `docs/lanes/judge-answers-v7.md` (NEW — delta
card over v6), `docs/plan/demo-morning.md`. Docs only — no code touched.
**HEAD at write:** `e147dbd` — two commits landed **mid-lane** and are
folded in: `849fd4a` sigbus-release (**SIGBUS closed on sim**: YG-scavenge
class root-caused, `withAllocInYoung(false)` → 40/40 repro-clean — v7
attack #13 re-written as RESOLVED) and `e147dbd` leftover-fixup (ageTick
30 s drives the "N min old" surfaces, health-ping AbortController,
same-name dedupe, exitNav cleanup, `transit_v2.line_name` extended —
server part DEPLOY-PENDING). **Live prod:** `6bc2b808` (deploy-7)
verified by curl ~21:00–21:10 UTC.

---

## Verification — every brief item checked against code/lane reports, not memory

| claim in the brief | verdict | evidence |
|---|---|---|
| 4-act chooser ~5 s | TRUE — code read | `RouteTint.tsx` `2590598`: FRAME 170ms stagger (~640 ms), CAND ~¾ s @540 ms, HOLD 300 ms, pill +260 ms / ~4 s hold; header "~3½–5 s"; on-device shots `chooser-craft-report.md` |
| air map = visible band field + contours + numbers | TRUE — code read | `AirFieldLayer.tsx` `677dc5d`+`e1e9d22`: airfieldCells CONF_A .92/.60/.34, airfieldEdges contours, airfieldValues z≥10.5, airStationDots/Names z≥14.5; shots in audit-fix/union-regression reports |
| raw-phrase search | TRUE — lane verified on sim | `search-report.md`: ashook nagar / pawan bakery verified; `c583cab` phonetic fold + units + near-anchor + Photon `· OpenStreetMap` |
| Delhi Today honest no-trips + incidents card | TRUE | `delhi-today-truth-report.md` (`own===0` collapse) + `HomeScreen.tsx` IncidentsCard above DoorRow; `incidentsTitle`/"no trips yet" strings in `strings.ts` |
| honest ambient framing | TRUE | `home-truth-report.md` + `App.tsx` ambientMeta (source/readAt/nearest_km) |
| "your lungs' calendar" week sheet | TRUE | `weekTitle` + `WeekSheet.tsx` + home-truth shots |
| offline pack 744 tiles airplane-verified | TRUE | `offline-verify-report.md` (sqlite counts + 938 ms cold relaunch) |
| no welcome film, cold open ~1–3 s | TRUE — code read | `WelcomeScreen` fully unmounted in `App.tsx` (import gone); `welcome_seen_v1` flag still writes once; gauntlet = ambient beat (4 s/9 s) → onboarding → location; notif perm **lazy** (`events.ts`/`notify.ts` — no boot dialog anymore) |
| felt-buttons/jank fixes | TRUE | `jank-perf-report.md`: Where-to ~200–250 ms, air map ~50–70 ms, check-in echo ~80 ms, gazetteer slice-warm at boot +900 ms |
| transit real names on prod | TRUE — live curl | `/v2/plan` on `6bc2b808`: "Bus 405", "0AIRPORTEXP-4(NS) → 764EXT" |

## The finding that reframes the lane — the pinned APK predates the wave

`git log ef5d95f..HEAD -- Mobile/` = **19 commits** (17 at pull, +2
mid-lane: sigbus-release `849fd4a`, leftover-fixup `e147dbd`). The
canonical demo binary `alive108-ef5d95f.apk` carries: r2 offline pack
(`54a296e`), the **v1** chooser (`e2ff634`), cause_note (`795ff3b`) —
but NOT the 4-act chooser, visible field, search rewrite, home-truth,
delhi-today gate, no-film boot, the `edc4666` Android-launch fix, or
the SIGBUS close. The wave's lanes all
verified on dev clients / sims; the docs now say so plainly:

- `demo-script.md` header: **"The binary decides which script is real"**
  — assume a re-cut ≥`e147dbd`, never `d8c7b41..edc4666` (map-perf alone
  crashes Android at launch); contingency row for narrating v2 beats on
  the old binary.
- `demo-kit.md` §1 renamed to "RE-CUT REQUIRED" with the same guardrails.
- `demo-morning.md` GO/NO-GO #4 requires a re-cut ≥`e147dbd` and checks
  "the field must be painted, not a bare basemap" as the tell.
- `judge-answers-v7.md` watch item K' makes it the top risk.

**Whoever owns the APK lane:** re-cut ≥`e147dbd`. Verified recipe is in
`apk-recut-report.md` + memory (Linux KVM box, ~25 min toolchain + ~4 min
build, `assembleRelease`).

## What changed in each file

**`docs/plan/demo-script.md` → v3 (full rewrite of the beat table).**
Phone-first arc: cold open (no film, hero honesty lines, incidents card)
→ Air map (the visible field — new money shot) → raw-phrase search →
plan + 4-act chooser + ladder + leave-later → lungs' calendar + Delhi
Today → web corroboration (`/` + `/community` + `/city` + `/admin`) →
AWS console (mandatory) → honesty close. Kept: AWS console moment, CLI
understudy, contingency table (updated), do-not-say list (8 new entries
incl. dead beats + SIGBUS + Android-feel honesty), rehearsal logs (added
pass 7). Numbers sheet re-pinned on `6bc2b808` ~21:05 UTC.

**`docs/plan/demo-kit.md`.** §1 re-cut required (guardrails above); §3
adds chooser-craft/audit-fix/home-truth/search/offline-verify shot dirs
and flags `chooser.mp4` as the v1 chooser; §4 truth card → v7 with the 5
must-know updated; §6 holes rewritten: APK staleness top, iOS SIGBUS,
mid-range Android feel unproven, offline pack CLOSED (was "ambient cache
is the plan"), legacy /observe rows aged out, metro GTFS-hours flicker.

**`docs/lanes/judge-answers-v7.md` (NEW — delta over v6, not a rewrite).**
v6 stands for unchanged attacks. v7 carries: 5 must-know re-armed;
attacks #13 (SIGBUS re-arm), #16 (offline closed end-to-end), #20
(outlook: tomorrow least-bad of 5), #14 (instruments on the glass), #17
(honest-emptiness surfaces); NEW attacks #24 (canned search), #25 (paint
job map), #26 (mid-range Android feel); watch items F' (metro absent
tonight), G', I' (closed), J' (Android = demo device), K' (binary gap),
L' (v1 film-strip); numbers card re-pinned.

**`docs/plan/demo-morning.md`.** Header re-stamped `6bc2b808` + wave +
the binary-decides block; T-90 #4 requires the re-cut + the painted-field
tell; T-45 phone block rewritten (new gauntlet — ambient beat →
onboarding → location, no film, lazy notif perm; iOS SIGBUS ~90 s
caution); live-lines comments re-pinned (depart pct 27; plan 23
opts/34.5×/metro absent overnight); pinned-numbers updated (chooser 4-act
timing, cold-open/sheet ms, offline 938 ms); T-0 table = new 8-beat order;
fallback table updated (one pill, r2 pack rides ef5d95f, SIGBUS row);
standing rule: Android is the demo device.

## Live numbers re-pinned (prod `6bc2b808`, ~21:05 UTC)

plan demo OD: 23 opts, car-AC 15.5 mid / walk 535.1 → **34.5×**, warm
took_ms 118–326, **metro+walk absent** (~02:35 IST GTFS-hours) ·
`/aqi` @CP 72.4/67.1/AQI 157/nearest 1.8 km · fires 90/16 ×1.08 refused
· `/v2/why` stagnation, VC 521 m²/s, +11.0 µg/5.8 h · `/v2/city` mean
92.5/aqi 209/GRAP-1 (dirty evening) · community 47/25/34.7 km/1,410.3
µg · depart pct 27 (best Oct-8 11:00) · outlook Oct-8 Moderate ~80
best-of-5 → 4× Very Poor.

## Known limits of this lane

- Docs-only: the re-cut itself is **not** done here — flagged as the
  top risk everywhere a stage read could hit it.
- `docs/11-demo-script.md` (the 3-min video script, Karol Bagh→India
  Gate ~31×) was **not** in this lane's list and still describes the v1
  chooser era — flag to owner if the video gets re-recorded.
- `docs/demo-day.md` (the big playbook) references the v2 script order;
  the T-0 table in demo-morning is now the canonical one; demo-day's
  numbers are superseded by the v3 numbers sheet.
