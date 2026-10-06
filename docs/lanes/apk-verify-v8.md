# Lane: apk-verify-v8 — the FINAL binary's device drive

Repo `<owner>/Delhi-Air-108`, branch `base/v2`, HEAD `5fd2990`+.
The final demo binary was rebuilt by the lead on the macOS box and is
uploaded at:
  https://app.devin.ai/attachments/a269e379-68ea-4f82-9817-dba52afd15ec/alive108-5fd2990.apk
(137 MB, sha256 `d354f704a3396719…`). It is ONE commit newer than the
binary apk-rebuild-v7 drove (21f8363): the delta is a one-line restore of
the first-use "µg (micrograms)" gloss on the home peek card
(`Mobile/src/screens/HomeScreen.tsx` peekUnit now renders `t("unitUg")`
whole instead of `.split(" ")[0]`).

## Mission
Drive THIS apk on the Android emulator (Linux KVM box — spawn your own
drive child if needed; KVM children count toward the 5-session cap, warn
the lead first). Verify the delta + regression-check the criticals:

1. **The gloss (the delta).** The peek card (home hero, needs logged
   hours: run a real nav drive or accept the sim's seeded daylog) must
   render "µg (micrograms)" / "µg (माइक्रोग्राम)" next to the dose
   numeral — NOT bare "µg". Screenshot it in BOTH en and hi. The hero
   week-dots line correctly keeps bare "µg".
2. **Armed-skip** (fresh plan → vehicle wizard armed → sheet ✕/skip
   closes it on FIRST tap).
3. **10 clean search opens** (tap search → sheet → back, watch for the
   GC SIGSEGV class — should be 10/10 clean).
4. **pcap spot-check** consent-off: no POST /v2/trip, /observe, or any
   location write on the wire.
5. Cold-open → first real number timing.

## Rules
- Never POST /v2/feedback, /observe, /v2/trip to the LIVE NLB/ALB.
- Report = `docs/lanes/apk-verify-v8-report.md`: verdict table
  PASS/FAIL per check + screenshots. Terminate your drive child when
  done (slot cap).
