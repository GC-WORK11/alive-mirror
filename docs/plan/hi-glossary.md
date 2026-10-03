# Hindi glossary — ALive consumer strings

Register: **conversational Delhi Hindi** (doc 02 §principle 3) — words a 12-year-old in
Delhi uses. Spoken loanwords (लोकेशन, सैटेलाइट, फ़्यूल, अलर्ट, लेयर, ऑफ़लाइन) are
correct; Sanskritized/formal Hindi (उत्सर्जन, उपग्रह, इंधन, साझा करना, संख्या) is not.
Address = आप; imperatives polite (चुनें, शुरू करें); prefer gender-neutral phrasing
where free ("ठीक है" over "समझ गया").

## Core concepts — one word per concept

| English | हिंदी | Notes |
|---|---|---|
| smoke (you breathe / ride puts out) | धुआँ | Never उत्सर्जन/निष्कासन — newspaper register. Inhaled = "साँस में जाने वाला धुआँ" long form, "धुआँ" short. |
| breathe (smoke) | साँस में लेना | Not श्वास/साँस लेना alone — "साँस में लिया" keeps the smoke object implied. |
| put out (emissions) | छोड़ना | "गाड़ी ने धुआँ छोड़ा" is how people say a vehicle emits. उत्सर्जन rejected: formal, unreadable at a glance. |
| lighter / heavier (smoke) | हल्का / भारी | Always paired: "यहाँ धुआँ हल्का" / "यहाँ धुआँ भारी". Don't swap in ज़्यादा/कम for these tags. |
| lightest | सबसे हल्का | "lightest for you/Delhi/both" all use सबसे हल्का. |
| estimate (n / v) | अंदाज़ा / अंदाज़ा लगाना | Not अनुमान (formal). "धुएँ का अंदाज़ा", "अंदाज़ा लगाएँगे". |
| number | नंबर | "यह नंबर कैसे निकला" — संख्या is book-register. |
| trip / journey | यात्रा | Everywhere: trips list, trip done, donated trips. Not ट्रिप (kept Devanagari-pure), not सफ़र (posh). |
| route / way | रास्ता | "हर रास्ता", "नया रास्ता ढूँढ रहे हैं". |
| directions (action) | रास्ता दिखाएँ | Button label. Turn list = मोड़-दर-मोड़ (see below). |
| turn | मोड़ | turn-by-turn → मोड़-दर-मोड़; hide turns → मोड़ छिपाएँ. |
| place / location | जगह / लोकेशन | जगह = saved/recent places; लोकेशन = the GPS "your location" row (spoken word). |
| destination | मंज़िल | "अभी की मंज़िल सेव करें". |
| map | नक्शा | "नक्शे पर चुनें", "हवा-नक्शा" (the shared air field — keep the compound). |
| layer | लेयर | Map layers; the a11y label mirrors: "नक्शे के लेयर". परतें rejected (formal). |
| air | हवा | "आज की हवा", "हवा-कीमत" (air price). वायु rejected. |
| anonymous | गुमनाम | "गुमनाम रहती हैं". |
| share / donate | शेयर करें | One verb everywhere — "शेयर करें", "डेटा शेयर करें", "शेयर की हुई यात्राएँ". साझा करें rejected (formal). |
| delete | मिटाना (action) / हटना (result) | "मेरा डेटा मिटाएँ?" then "…फ़ोन से हट जाएँगे". |
| vehicle (generic) | गाड़ी | Covers scooter/car/auto/cab. वाहन rejected. |
| fuel | फ़्यूल | Question header "फ़्यूल?". ईंधन rejected (written register). |
| satellite | सैटेलाइट | उपग्रह rejected — nobody says it. |
| alert | अलर्ट | "सुबह का हवा-अलर्ट". चेतावनी only if a sentence needs a noun of warning. |
| crash spot | एक्सीडेंट स्पॉट | दुर्घटना rejected. |
| measured streets | मापी गई सड़कें | मापना standard; नापना acceptable but मापी preferred. |
| metro / auto / cab / cycle / walk | मेट्रो / ऑटो / कैब / साइकिल / पैदल | "मेट्रो" alone — no "मेट्रो स्टेशन" suffix. |
| cigarette | सिगरेट | Reserved for when a string needs the word; UI uses the 🚬 icon + number. |
| recent | हाल की | "हाल की जगहें" (recents are places, not searches). |
| settings / units / voice / language | सेटिंग्स / इकाइयाँ / आवाज़ / भाषा | इकाइयाँ kept (standard UI Hindi); यूनिट also fine if space-pinched. |
| roughly / about | लगभग / ≈ | "लगभग कब खरीदी थी?"; ≈ used inline in counters. |
| cancel / done / start / end | रद्द करें / हो गया / शुरू करें / खत्म करें | "हो गया" = done, natural. |
| offline / server / live / model / data | ऑफ़लाइन / सर्वर / लाइव / मॉडल / डेटा | All spoken loanwords. |
| km / min | किमी / मिनट | "34 मिनट", "12.4 किमी". |
| station (air) | स्टेशन | "लाइव स्टेशन फिर से जुड़ रहे हैं". |

## Number & script conventions

- **Digits stay Latin** (0-9), never Devanagari digits (०-९): Indian phone users read
  "34 मिनट" instantly; doc 03 requires tabular numerals and Noto Sans Devanagari's
  Latin digits render tabular alongside Devanagari text.
- Year ranges keep en form: "2010–2016".
- Interpolated `{n}/{p}/{time}/{a}/{b}/{t}` must survive verbatim — Hindi word order
  wraps around them ("{n} मिनट पहले अपडेट हुआ", "{a} पर चढ़ें → {b} पर उतरें").
- Nukta characters ज़ फ़ (ज़्यादा, फ़ोन, फ़्यूल) and chandra-bindu (पहुँच, ढूँढ, हूँ)
  are standard Delhi spellings — both shape correctly in Noto Sans Devanagari.
- Currency of speech: mixed English nouns inside Devanagari sentences are fine
  ("सर्वर ऑफ़लाइन"), matching how Delhi Hindi is actually spoken.

## Devanagari rendering (fam())

- `fam('hi', w)` maps reg/med/semi → NotoSansDevanagari_400/500/600; all three weights
  are loaded in App.tsx `useFonts` — switching works.
- `fam` only accepts reg|med|semi, so hi can never get an unmapped weight.
- ⚠️ Known gap (other lanes' files): many `Text` styles hard-code `F.reg/F.med`
  (Inter) instead of `fam(lang, …)` — e.g. CompareSheet `loadingTxt`, `departTxt`,
  `stepTxt`, `noResults`; NavChrome `meta`; Sidebar `todayCap`, `tripMeta`, `hint`,
  `howBody` partially uses fam. Inter has **zero** Devanagari glyphs — Android falls
  back to the system Devanagari font (weight/shaping mismatch, no tabular-nums
  guarantee); on iOS it falls back to Kohinoor. Cosmetic consistency issue only —
  conjuncts (क्षेत्र removed anyway) and nukta/chandra marks still render via
  fallback, but flag to screens lane to swap remaining `F.*` on text that can carry
  Hindi for `fam(lang, …)`.
