# hi-parity-v2 — Hindi parity sweep, every surface (iOS sim)

Env: iPhone 17 iOS 26.5 sim (D0B64A8A-D5F1-4668-8FFC-A86B400AF527), ALive-108 dev client (com.anonymous.app), Metro :8081, backend :8000 (localhost). Location preset to India Gate 28.612913,77.229507 BEFORE app launch (the `from` is captured at destination-pick).

Screenshots dir: ~/repos/Delhi-Air-108/docs/assets/hi-parity-v2/ — capture via `xcrun simctl io <udid> screenshot <path>.png`.

Global pass/fail rubric applied to EVERY screenshot:
(a) English leaks — any Latin word that is NOT an exempt unit/proper noun/brand/regulatory symbol (µg, kg, CO₂, PM2.5, AQI, m, km, g, ALIVE-108, place names like "Connaught Place", road names in step text).
(b) Tofu boxes □ / missing glyphs anywhere.
(c) Clipped/ellipsized Devanagari on the new chunky tiles — watch door labels (esp. "आपकी यात्राएँ"), hero stat rows, compare option labels, pill labels.
(d) Latin "am/pm"/"h"/"m"/"d" suffixes inside Devanagari text (e.g. "2h", "8am" next to Hindi).

Flow order (Hindi first via Settings → भाषा → हिंदी):

1. hi-onboarding.png — SKIP on first pass (default lang en); captured at END cheaply: quit app, backup Documents/*.json, delete consent.json, relaunch → OnboardingScreen (consent gate) in Hindi → screenshot → restore consent.json + relaunch.
   Pass: onboarding pages (introTitle "दिल्ली की हर यात्रा की एक हवा-कीमत है।", consent buttons "यात्राएँ गुमनाम साझा करें"/"सब कुछ मेरे फ़ोन पर रखें") fully Devanagari, no tofu/clips. If wipe path fails → mark untested, say so.

2. hi-settings.png — launch → consent → Home → ☰ sidebar → सेटिंग्स → full sheet. Set भाषा = हिंदी here (English/हिंदी segments).
   Pass: section headers "भाषा और दिखावट"/"निजता और शेयरिंग", rows "आवाज़"/"भाषा"/"इकाइयाँ", "मेरा डेटा मिटाएँ", "ALive·108 को रेट करें", version row; no English leak.

3. hi-sidebar.png — ☰ drawer after ≥1 trip (recency line). Verify uncommitted fix: trip rows show "अभी"/"Nमि"/"Nघं"/"Nदिन" — NO "now"/"Nm"/"Nh"/"Nd". Header links: यात्राएँ, मेरी गाड़ी, आज की दिल्ली, सेटिंग्स.
   If no trip yet, capture empty state ("अभी तक कोई यात्रा नहीं") and re-capture after the trip in step 6.

4. hi-home.png — Home: hero card (peekTitle "आपका दिन अब तक", dose ring, week dots, budget line "budgetTitle"), DoorRow icon tiles: "हवा का नक्शा" / "आज की दिल्ली" / "आपकी यात्राएँ".
   Pass: all three door labels fully visible (not truncated — chunky tiles risk), hero stats in Hindi.

5. hi-move.png — scroll Home to the move card: moveTitle + morning window + sparkline (+{n}घं ticks) + days-ahead cells (dayOutlook).
   Pass: hour ticks use "घं" not "h"; verdict strings Devanagari.

6. hi-delhitoday.png — tap "आज की दिल्ली" door → DelhiToday: hero µg (cityHeroLead "दिल्ली की हवा का एक दिन"), source chips (लाइव स्टेशन/सैटेलाइट अंदाज़ा), species/mode rows, outlook (अगले 12 घंटे), CityMoves card (दिल्ली कैसे चलती है) if present.
   Pass: all Hindi, chips/pills unclipped.

7. hi-compare.png — tap search bar → paste "Connaught Place" (pbcopy+Cmd+V) → pick → compare sheet. Screenshot option cards; tap one card to expand detail; toggle "मोड़-दर-मोड़" steps list.
   Pass: option labels localized (mode_* keys), pill labels (हमारी पसंद/आपकी सामान्य/सबसे सुरक्षित रास्ता), "शुरू करें" button, steps in Hindi (navStep_*), road names may stay Latin (exempt).

8. hi-navchrome.png — "शुरू करें" → NavChrome: maneuver banner (verify step0 fix: Hindi instruction, not English server sentence), dose counters (आपके साँस का धुआँ/आपकी गाड़ी का धुआँ), bottom line "N मिनट · N किमी बाकी · {t} तक पहुँचें". Jiggle GPS 28.6224,77.2266 ↔ 28.6226,77.2267 to get a real instruction.
   Pass: banner Hindi; counters Hindi; no "cigarettes"/"kg" Latin (nav_cigs/nav_kg fix: "N सिगरेट"/"N किग्रा" only in share text; counters show µg/किग्रा).

9. hi-receipt.png — GPS-arrive at destination: jiggle 28.6315,77.2167 ↔ 28.6316,77.2168 (2 fixes ≤60m → arrival) OR tap "खत्म करें" for end-early.
   Pass: "आप पहुँच गए।"/"यात्रा ख़त्म हुई।", "आपने साँस में लिया"/"आपकी गाड़ी ने छोड़ा", दूरी/समय rows, "सहेजें" — all Hindi.

10. hi-ledger.png — sidebar → यात्राएँ → LedgerScreen with the just-finished trip.
    Pass: "सभी सेव की गई यात्राएँ", trip row Hindi mode + recency, totals rows Hindi.

Known-intermittent SIGSEGV (~40% on search-mount sheet over live map): relaunch + retry; NOT an app bug.

Search-field input: `xcrun simctl pbcopy <udid>` then Cmd+V (simctl type drops chars).

Report: verdict per surface + real bugs vs exempt Latin + screenshot paths. Do NOT commit.
