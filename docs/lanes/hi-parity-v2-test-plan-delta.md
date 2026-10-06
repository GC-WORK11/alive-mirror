# hi-parity-v2 DELTA — kg→किग्रा consistency re-verify (3 captures only)

Env: same as main sweep — iOS 26.5 sim D0B64A8A, app com.anonymous.app, Hindi persisted, server :8000, Metro :8081, location India Gate 28.612913,77.229507 already set pre-launch. App already relaunched to fetch new bundle.

Diff evidence (uncommitted): strings.ts `unitsKg` hi="किग्रा"; `tripsOutDetail` hi="अंदाज़न {n} किग्रा छोड़ा"; LedgerScreen hero sumUnit → t("unitsKg"), trip-row emit → t("nav_kg",{n:"≈N"}); tripRoute Text → numberOfLines=1 adjustsFontSizeToFit minimumFontScale=0.7; NavChrome co2 band → t("nav_kg",{n:"lo–hi"}); SearchBar label → adjustsFontSizeToFit minimumFontScale=0.75.

## 1. hi-ledger-v2.png — Ledger sheet
Path: ☰ → यात्राएँ.
Pass criteria (pixel check on simctl screenshot):
- Hero emit line reads "…किग्रा" (unitsKg) — NO Latin " kg" after the number.
- Trip row emit shows "≈N किग्रा" — NO "≈N kg".
- Week/out detail line (tripsOutDetail) shows "किग्रा छोड़ा" — NO "kg छोड़ा".
- Trip route line "…→ Connaught Place" — record whether the name renders fuller than prior "Co…" clip; if destination is short and doesn't trigger shrink, note it as inconclusive-but-acceptable.

## 2. hi-navchrome-v2.png — Nav counter during active trip
Path: search → pick destination → शुरू करें on a vehicle option (कार AC, same as before).
Pass: right counter band text under "आपकी गाड़ी का धुआँ" reads "0.0 किग्रा" / "N–N किग्रा" — NO Latin "kg". Jiggle GPS 1–2 fixes if band needs emission accumulation.

## 3. hi-searchbar-v2.png — long destination in search bar
Path: during compare phase (sheet open) capture the top SearchBar label after picking a LONG destination (e.g. "Indira Gandhi International Airport").
Pass: destination label shrinks to fit (readable smaller text) instead of hard "…" clip at ~2 chars; smaller clips with ellipsis acceptable if the string remains substantially readable — minimumFontScale 0.75 means modest shrink, not magic.

Cleanup: end trip via खत्म करें so state is left clean.
