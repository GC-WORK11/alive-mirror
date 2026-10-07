# Lane — Mobile audit fixes (mobile-audit.md, audit `01d3e59`)

Fix lane over `Mobile/` on `base/v2`. Four commits, one per numbered
item from the lane brief:

| commit | item |
|---|---|
| `af090ae` | 1 — outbox resurrect-after-wipe (wipeGen guard) |
| `2858f21` | 2 — skip→sharing-on disclosure travels to all 3 onboarding pages |
| `85caf66` | 3 — i18n ×4 (nav metres, gazetteer kinds, share CO₂, welcome gate) |
| `4bfcdb9` | 4 — dead code + stale comments (safe subset only) |

## Gates (all re-run this session, post-fix)

- `npx tsc --noEmit` — clean
- `npx expo lint` — clean
- `node src/store/test-runner.mjs` — 18/18
- `node src/nav/test-runner.mjs` — 70/70
- `node src/api/test-runner.mjs` — 8/8
- `node src/offline/test-runner.mjs` — 6/6 (runner + suite added this lane)

## 1. MED BUG (privacy) — outbox resurrect-after-wipe → fixed

**Finding:** a donation POST that fails *after* `clearOutbox` re-created
`outbox.json` and auto-flushed on the next `up` event — a wiped user
silently re-donated a consented trajectory.

**Fix** — mirrored `cache.ts`'s generation guard exactly:

- `offline/queue.ts`: `wipeGen` counter + `outboxGeneration()` getter;
  `enqueue(url, body, since?)` drops the write when `since != null &&
  since !== wipeGen`; `clearOutbox()` bumps `wipeGen` and deletes the file.
- `nav/engine.ts donate()`: captures `const gen = outboxGeneration()`
  before `postJson`, same shape as `net.ts` capturing `cacheGeneration()`
  at request start; the catch passes `gen` to `enqueueTripDonation`. A
  wipe landing between attempt-fail and enqueue now drops the donation.
- Second hole in the same class, found by the new test: `load()` spread
  the module constant `EMPTY` — `{ ...EMPTY }` shares `EMPTY.items`, so
  `clearOutbox`'s `notify(...)` handed every future `load()` a mutated
  shared array and wiped items resurrected without any file write.
  `empty()` factory now mints a fresh `{ items: [], dropped: 0 }` per call.
- `offline/index.ts` re-exports `outboxGeneration`.
- New `src/offline/test-runner.mjs` (registerHooks; in-memory
  expo-file-system stub with `Paths`/`Directory`/`File` since
  queue → net → cache transitively) + `src/offline/queue.test.ts`.

**Verified:** 6/6 node:test cases — enqueue persists across reload;
enqueue with a stale (pre-wipe) generation is dropped and writes no
file; same-generation enqueue after the bump still lands; clearOutbox
empties the store *and* invalidates in-flight enqueues; the
shared-array resurrection path reproduces dirty-then-clean. `node
src/offline/test-runner.mjs` green.

## 2. MED JUDGE-RISK — skip→sharing-on disclosure doesn't travel → fixed

**Finding:** the persistent top-right Skip is on all 3 onboarding pages
and calls `finish("on")` (sharing ON), but `consent_footnote` rendered
only inside `step === 2` — a page-0/1 skipper consented without ever
seeing the choice.

**Fix:** the footnote `Text` moved out of the `step === 2` block to
render after all three step conditionals inside the shared
`Animated.View` — same small centred line on every page where Skip is
visible. No layout change on the choice page; header comment updated to
document that the disclosure travels with the button.

**Verified:** `consent_footnote` renders unconditionally inside the
page-fade view (`OnboardingScreen.tsx` — grep shows a single render site
outside all `step ===` blocks); `tsc`/`expo lint` clean; nav + store
suites still green.

## 3. LOW BUG ×4 (i18n) → fixed

**a) `NavChrome.tsx:63` hardcoded `" m"`** → `t("unitsM", lang)` — the
hi nav banner now prints "350 मी" not "350 m".

**b) T0 gazetteer subtitles English-only in hi search** → new
`localizeKind(label, lang)` in `i18n/strings.ts`, mirroring
`placeNameLabel`/`PLACE_SENTINEL`: a `KIND_LABEL` map keys on the
English label `kindLabel()` emits and routes through `t()`. It covers
the top 155 labels by corpus weight (`delhi-gazetteer.json`, weight =
`w + k*2`) = **97.01%** of the gazetteer; unknown labels pass through
unchanged — the corpus's own words, honest, never a fabricated guess.
Applied at both `subtitle={p.subtitle}` render sites in
`SearchScreen.tsx` (merged results + recents rows), so stored recents
carrying English kind subtitles re-localize on render too.

**c) `App.tsx:704` share-trip double-unit** — `t("nav_kg", …)` + literal
` CO₂` produced "~1.2 किग्रा CO₂" in hi. New `share_co2` key keeps the
substance inside the unit template: en `"{n} kg CO₂"`, hi
`"CO₂ {n} किग्रा"`.

**d) `WelcomeScreen` hardcoded English** — reachable post-delete (wipe
clears `welcomeSeen`, preserves `lang`). Five strings → new `wel_*`
keys: `wel_provAmbient`, `wel_provCity`, `wel_neverFaked`,
`wel_thenBreathe`, `wel_delhiBreathes`.

**Verified:** en/hi parity is compiler-enforced — `hi` is
`Record<StringKey,string>` and `tsc` is clean, so every new key exists
in both languages. Runtime probe: `localizeKind("school","hi")` →
"स्कूल", `("road","hi")` → "सड़क", unknown label passes through;
`t("share_co2","hi",{n:"~1.2"})` → "CO₂ ~1.2 किग्रा"; `unitsM` →
"मी"/"m"; all five `wel_*` keys resolve in both languages.

## 4. NIT — dead code + stale comments → fixed (safe subset only)

- **`src/api/trip.ts` deleted** — `postTrip` + its four wire types had
  zero importers; donation lives in `engine.ts` (`postJson` + outbox).
  The file's "kept for whoever finishes navigation" seam note was stale.
  `useShellFlow.ts`'s SEAM comment re-pointed at `engine.ts`.
- **`src/components/FieldLayer.tsx` deleted** — zero imports; header's
  "kept for the city-view lane" was stale (DelhiToday landed without a
  map layer — no maplibre usage there at all).
- **`Sidebar.tsx` `(onDelhiToday || true)`** → dropped the always-true
  guard; the inner ternary still handles the optional prop.
- **`OnboardingScreen.tsx:160`** comment said "JS driver" on
  `useNativeDriver: true` — corrected: this is a pure opacity timing
  with none of Sheet's mixed-graph detach risk (the JS-driver guard in
  `ui.tsx` is about drag transforms).
- **`CompareSheet.tsx` selFill comment** claimed an "accentWash wash +
  accent edge" — `selFill` is borderRadius + accentWash only; corrected
  to say the glyph well's `accentTint` supplies the edge colour.

Nothing wired or feature-bearing removed.

## Not touched (per lane scope)

- **MED JUDGE-RISK iOS SIGSEGV class** — needs the verify lane (device
  repro), not more code review.
- `useNetStatus().label` latent i18n nit, WelcomeScreen darkroom
  DESIGN-LAW flag, `Mobile/AGENTS.md` DOC nit — left for owner call.
