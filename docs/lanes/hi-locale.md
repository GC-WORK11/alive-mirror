You are the Hindi-locale lane for ALive-108. The app speaks en+hi (strings.ts pattern) but the new dosimeter surfaces landed en-first — a Delhi consumer app at a Delhi hackathon must read real Hindi end-to-end. Deliver: complete, natural hi translations for every new surface + on-device verification of both locales.

Repo: <owner>/Delhi-Air-108, branch base/v2 (pull latest — other lanes push often; rebase before push). App: Mobile/ (Expo RN SDK54). Live: http://alive108-2699c171ddded465.elb.ap-south-1.amazonaws.com (GETs only).

HARD RULES
- Push code only — never deploy. NEVER POST /v2/feedback, /observe, /v2/trip to live.
- `npx tsc --noEmit && npx expo lint` before push.
- Hindi must be REAL: natural Delhi Hindi (the way a CP shopkeeper talks), not textbook-translation cringe. Technical terms that Delhiites actually use in English stay English (AQI stays "AQI"/"एक्यूआई" glossed once; µg/m³ stays µg/m³). No machine-translation tone. If a string has no natural Hindi, keep it English — honest over forced.
- Verify BOTH locales render: overflow, clipped text, broken glyphs (Devanagari needs the font to support it — CHECK the bundled fonts actually render Devanagari on device; if not, that's the headline bug to fix or report).

MANDATE
1. Audit strings.ts (+ any hardcoded literals) for every string lacking a hi entry — new home (dose hero, the move, your day, days ahead, how you felt, budget), journey additions (dose heroes, N× gap, receipt lines incl. receipt_queued), offline pill/freshness strings, Delhi today.
2. Write the hi values. Register: warm, plain, no Sanskritization, contractions Delhiites use.
3. Font check: does the type stack render Devanagari? If Fraunces/plex fall back to system for hi strings, decide honestly (system font for hi is FINE — mixed-script is normal) but verify no tofu boxes.
4. On-device: flip to hi, drive home→journey→receipt, screenshot key surfaces, check overflow/clipping at real DPI.
5. Report: strings added, device screenshots hi+en, any string you deliberately left English and why, font verdict.
