# copy-r4 — strings.ts audit notes (lane r4-copy)

Rule applied: no complex language while still delivering advanced detail.
Jargon is removed from surface copy and *paired* where it must stay
(detail expanders, the "how we got this" panel, settings deep-dive).
Honest qualifiers are never removed — "estimated", "last known", "stale",
"reconnecting" all stay, in simpler words.

## Word decisions

- "dose" → "smoke you breathe" / "smoke you breathed" everywhere
  (`howWe_conf` is now "how sure the smoke number is").
- "emissions" → "smoke your ride puts out" (already dominant — kept
  consistent; `howWe_out`, `howAliveBody` aligned to it).
- internals → consumer words: "model field" → "estimated from
  satellite + weather data", "H3 street grid" → "a street grid",
  "rotated" id → "id that changes", "thinned" → "about one dot per
  100 m", "air strip" → "live air update", "instrument error" → "what
  the meters miss".
- scientific labels kept *paired*: "fine smoke (PM2.5) … µg/m³"
  (`cityBasisPm25`), "fine dust (PM2.5)" (`receipt_pmBand`),
  "316 µg of PM2.5" (Berkeley Earth rule in `settingsHowNumbersBody`).
  µg stays in the detail expander — the one place raw numbers live.
- `nav_in` says "metres" not "m" — it is spoken by TTS; "m" reads as
  the letter. `nav_noSignal` "waiting for a fix" → "locating you…"
  ("fix" is GPS jargon).
- `vehicleQ1` "What do you usually ride?" → "How do you usually get
  around?" — a metro rider doesn't "ride" a vehicle they own.
- `followRoute` dropped the colour claim ("blue line") — route colour
  is segment-driven and can change (gradient lanes).
- `consent_body` "trips people donate" → "trips people share" — matches
  the button copy ("Share trips anonymously").

## Keys added (en + hi)

- `departTomorrow` — CompareSheet's "tomorrow 08:30" leave-later row.
- `a11yBack` — three screens hardcode `accessibilityLabel="back"`.
- `placeCurrentLocation`, `placeCentralDelhi` — fallback place names
  hardcoded in useShellFlow/App.tsx (flow hook has no lang today).

## Hardcoded strings found — need small component edits (NOT done here)

- `Mobile/src/components/shell/CompareSheet.tsx:45` — `"tomorrow "`
  prefix → `t("departTomorrow", lang) + " "`.
- `Mobile/src/screens/SearchScreen.tsx:212` — `accessibilityLabel="back"`
  → `t("a11yBack", lang)`; line 234 `accessibilityLabel="clear"` →
  existing `t("a11yClear", lang)`.
- `Mobile/src/screens/DelhiToday.tsx:174` — `accessibilityLabel="back"`
  → `t("a11yBack", lang)`.
- `Mobile/src/screens/LedgerScreen.tsx:283` — `accessibilityLabel="back"`
  → `t("a11yBack", lang)`.
- `Mobile/App.tsx:99` — `{ name: "current location" }` →
  `t("placeCurrentLocation", lang)` (line 211 already does this with
  `yourLocation`).
- `Mobile/src/components/shell/useShellFlow.ts:82-83` — `"current
  location"` / `"central delhi"` place names; hook doesn't import t()
  yet — wire `lang` through before using `placeCurrentLocation` /
  `placeCentralDelhi`.
