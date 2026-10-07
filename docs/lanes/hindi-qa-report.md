# Lane report — hindi-qa (user-side QA of every `hi` string)

Branch: `base/v2` · File audited: `Mobile/src/i18n/strings.ts` · Scope: `hi` block only, same keys, zero `en` edits.

## Verdict

The Hindi did NOT read like a Delhi speaker. It was a passable translation layer with heavy bookish register, transliterated-formal words, a few Sanskritized kind labels, mixed-register abbreviations, and **two real render bugs**. 155 values in the `hi` table were rewritten hi-only; en untouched. Verified live on the iOS sim in Hindi end-to-end — no layout breaks, no truncation, no English leaks on any localized surface.

## Real bugs found (not just taste)

1. **`dayMorningMove`** — template appended `बजे` to `{f}`/`{g}` that already render as complete clock words → read "6 बजे बजे के मुक़ाबले". Fixed to `वही काम {f} करने से {g} के मुक़ाबले ~{x}× कम धुआँ`.
2. **`dayOutlookHeavyHours`** — same bug class: `सबसे भारी {h} बजे` rendered "अपराह्न बजे". Fixed to `सबसे भारी {h}`.

## What was wrong, by class

- **Bookish/formal register** (biggest class, ~80 strings): `सहेजा→सेव`, `पूर्वानुमान→आगे का अंदाज़ा`, `उपग्रह→सैटेलाइट`, `उत्सर्जन→गाड़ी का धुआँ`, `क्रमांक→क्रम`, `सूचकांक→नंबर`, `वैकल्पिक→चाहें तो / मर्ज़ी है`, `उपयुक्त→सही/ठीक`, `स्थान→जगह`, `मुद्दा→बात`, `उपकरण→ऐप/स्टेशन`, `अनुक्रम→क्रम`, `दृश्यता→कितनी दूर तक दिखे`, `निम्न→ठंडी/छोटी`, `उच्च→पूरा` (conf), `संतोषजनक→ठीक-ठाक`.
- **Sanskritized place-kind labels** (~30 `kind_*`): हवाई अड्डा→एयरपोर्ट, दूतावास→एम्बेसी, संग्रहालय→म्यूज़ियम, पुस्तकालय→लाइब्रेरी, विश्वविद्यालय→यूनिवर्सिटी, दंत चिकित्सक→दाँतों का डॉक्टर, पशु चिकित्सक→पशु डॉक्टर, आवासीय क्षेत्र→रिहाइशी इलाका, औद्योगिक क्षेत्र→इंडस्ट्रियल इलाका, अपशिष्ट जल संयंत्र→सीवेज प्लांट, प्रवेश→एंट्रेंस, पूजा-स्थल→पूजा की जगह, etc. Street-Delhi transliteration is the *correct* register here — it is what people say.
- **Crypto-abbreviations**: `किग्रा→किलो`, `ग्रा→ग्राम`, `अंदाज़न→करीब`, compact `{h}घं {m}मि गिने→{h} घंटे {m} मिनट गिने`, `{h} घं में→{h} घंटे में` (full words inside sentences; kept `घं` only on the compact chart tick `+3घं`).
- **Awkward literal calques**: `यहाँ दिल्ली एक दिन में`→`दिल्ली की हवा का एक दिन`, `जियोग्राफ़िक`→`जिएँ` register fixes (`अपना दिन जिएँ`), `नंबर-रेखा`→`साँस का नंबर`, `तय सीमा`→`दिन की ~{b} µg में से`, `छाता लेकिन भारी`→`दिल्ली के लिए भारी`.
- **Danda/period drift**: `।` inside UI microcopy normalized to `—`/`,` across ~20 strings.
- **Trust/venue tone**: `जियो कहता`→`की` forms, `फ़र्ज़ी`→`बनावट`, `ज़ीरो-डेटा` register, `हम जो रखते हैं` → kept as `हम क्या रखते हैं`, disclaimer lines (`यही नक्शे की ईमानदारी है`, `मापा हुआ, रिपोर्ट नहीं`) kept — they already read like the owner's voice.

## Machines I checked behind the strings

Not just the table — verified every `hi` value actually reaches its render site:

- `fuelName/className/vehicleLabel` (`src/store/vehicle.ts`) → `FUEL_KEY/CLS_KEY` maps, all localized, Hindi renders (verified in vehicle sheet).
- `localizeKind` + `KIND_SYNONYMS` — search results showed live Hindi kinds (`रिहाइशी इलाका`, `सड़क`, `जगह`, `दिल्ली`).
- `clockLabel/hourLabel` — `{f}`/`{g}` already produce `6 बजे`/`4:32 अपराह्न`, which is why the two `बजे` template bugs were real.
- `HI_DIRS/HI_ORD` (`src/nav/instructions.ts`) — turn instructions render `बाएँ/दाएँ/सीधे`; fixed `navStep_keep` back to `{s} रहें` after spotting a grammar bug in my own first pass (`बाएँ तरफ़` is wrong gender for तरफ़).
- Parity: 948 en keys = 948 hi keys (+7 mode-word entries hi-side by design). **Zero `{placeholder}` mismatches** after edits (checked programmatically).

## Sim verification (iPhone 17, iOS 26.5, dev-client)

Drove the real app in Hindi — home, sidebar, Delhi-today, search→chooser, vehicle prompt, verdict cards, nav, receipt, settings. Screenshots in `docs/lanes/shots/`:

| Shot | Surface | Checks |
|---|---|---|
| hindi-01 | Sidebar | सेव की गई जगहें, जोड़ें, भाषा toggle, गुमनाम शेयर, मेरा डेटा मिटाएँ |
| hindi-02/03/14 | Home (both empty + breathed states) | नमस्कार, मध्यम scale image a11y, WHO ×, सीमा %, आज का फ़ैसला, week strip, check-in facet rows (साँस/आँखें/ताकत), दैनिक सीमा, "25 मिनट गिने" |
| hindi-05/06 | Delhi today | species rows, WHO सीमा, 10-वर्ष औसत, अगले 12 घंटे, सैटेलाइट अंदाज़ा, no-trips "अपना दिन जिएँ" |
| hindi-07/08 | Chooser | vehicle prompt sheet, verdict cards (हमारी पसंद, सबसे कम धुआँ, fairTrade/heavierDelhi reasons), departure banner, hourly strip |
| hindi-09 | Nav | निकलें, नक्शा केंद्र में लाएँ, मिनट/मी/पहुँचें line, µg + ग्राम counters |
| hindi-10 | Receipt | early-end variant: शुरू होने से पहले ही ख़त्म, 100 मी से कम, सिर्फ़ इस फ़ोन पर |
| hindi-11/12/13 | Settings | भाषा और डिस्प्ले, आवाज़, सिगरेट-तुलना, मीट्रिक, privacy toggle, alerts rows (सुबह का हवा-अलर्ट, हवा का बिगड़ना, सड़क पर आपका दिन), ऐप के बारे में, वर्ज़न |

Also confirmed in the a11y tree post-edit: `ये नंबर कैसे बनते हैं` row, `एक m³ हवा में PM2.5 धूल`, kind labels in search results, localized vehicle fill (`मामूली दिल्ली गाड़ी`).

## Dev-environment caveats (not product bugs)

- Mid-run the app hit a dev-client `Unexpected Fiber popped` + sim input wedged — recovered via reinstall + sim reboot. A `[expo-notifications]` keychain-entitlement toast persists on this build (sim-only, entitlement absent) and sits over the bottom strip — ignore in shots.
- `pod` lives at `/opt/homebrew/lib/ruby/gems/3.4.0/bin/pod` (not on PATH); build needs `RCT_USE_PREBUILT_RNCORE=0` + `LANG/LC_ALL=en_US.UTF-8`; **do not run `npm install` during `xcodebuild`** — patch-package rewrote RN headers mid-compile and broke linking once.
- iOS a11y `scroll_to`/`scroll` no-ops on the RN home scroll view — pixel `left_click_drag` works; HID injection flaked once at session end ("Mach port invalid"), a11y reads stayed live.

## Gates

`npx tsc --noEmit` clean · `npx expo lint` exit 0 · node runners: store 84, nav 76, api 17, offline 16 — **193/193 green**.

## Left intentionally

- Units/proper nouns stay Latin (`µg/m³`, `km`, `PM2.5`, `AQI`, `CO`, `NO₂`, `O₃`, `SO₂`, `PUC`, `GPS`, `Wi-Fi`, `BS-IV/VI`, `CNG`, `EV`, `ALive`) — that's correct; people say them that way.
- `मास्टर स्विच`, `टैप`, `मीट्रिक`, `लाइव`, `ऑनलाइन`, `ऐप`, `वर्ज़न`, `सिगरेट-तुलना` — real Delhi Hindi, kept on purpose.
- `c_1`-style ids, street names, and gazetteer proper nouns are never translated (by design).
