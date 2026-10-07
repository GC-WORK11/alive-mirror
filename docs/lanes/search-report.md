# search — the killer feature, fixed for how the owner actually types

Owner verbatim: "live location ain't even working — typed my location,
hardcoded garbage — on Google Maps I write my home address, it guesses
street then locality then landmark — here I said a landmark and it gave a
religious place. Not even 1% close to Google." Delta added mid-lane:
"nandanagri, a block pocket something" / "ashook nagar shadara gali no
<N>" / "pawan bakery near hanuman mandir" must resolve to THE REAL place
— phonetic spellings, gali/block/pocket numbers, near-landmark
compositional phrasing; no guesses, no dupes, no generic icons, show the
resolved address.

## Root causes found (audit before fix)

1. **T0 gazetteer weight table was poisoned.** The bundled 124k-row
   index ranked `hindu_place_of_worship w=9`, `historic_site w=10` over
   `address w=2`, had no fuzzy/phonetic matching and no unit (gali/block)
   understanding — it painted first and buried the actually-correct
   server rows. "India gate" → temple rows; a gali address → a religious
   place. That is the religious-place complaint, reproduced.
2. **Server compound layer died on context tokens.** `core_engine`
   resolved "X near Y" only when the query matched the anchor exactly —
   one extra locality token ("shahdara" in "ashok nagar shahdara") and
   anchor lookup returned empty → caller fabricated guesses.
3. **Live-location 'from' was a fabrication chain.** Search bias read
   the plan's `from`, not the real fix; "Your location" silently no-op'd
   on fix failure; a missing fix fell back to a literal "Central Delhi"
   origin pin. 'from' never saw his GPS.

## What changed (₹0, offline-first preserved)

- **`search/parse.ts` (new)** — one query parser for every tier: strips
  structural filler ("gali no", "number", "pocket", "block", "near"),
  extracts `units` ({struct:gali, value:4}), `kind` (bakery/atm/…),
  `near` anchors, and a transliteration `fold` per token (Delhi phonetic
  skeleton: ashok→xk, shahdara→xdr, nandanagri→ndngr).
- **`search/t0.ts` rewritten** — folded-token + fused-name-skeleton
  indexes alongside the plain prefix index; type weighting
  street/address > landmark > locality (owner's ranking law) with corpus
  w/k at half weight; unit resolution anchored to the nearest matching
  locality; kind-scan "X near Y" → nearest X-kind rows around the nearest
  Y anchor; subtitles show `kind · area` (the resolved address, not just
  a name); hard dedupe on fused-name+geo cell. Rebased onto jank-perf's
  sliced build (6k rows/macrotask) — same rows, same slices.
- **`search/client.ts` t3 = Photon** (komoot's hosted OSM geocoder,
  free, no key) — labeled `· OpenStreetMap`, fires only when t0 misses or
  is thin; the network tier is a fallback, never the floor. Rows shown
  with resolved street/area/city address.
- **`useShellFlow` + `SearchScreen`** — killed the Central-Delhi
  fabrication; "Your location" now waits for and uses the real fix and
  shows an honest "couldn't get your location" notice when it can't;
  search bias reads the real fix.
- **`server/core_engine.py`** — same near/context-tolerant anchor retry
  server-side (GET-only change; prod deploys itself).
- **`CategoryIcon`** — no religious/generic icon when kind doesn't
  match; kind-mapped glyphs only.

## Verified on the iPhone 17 sim (dev client, base/v2)

Typed by set_text on the real sheet, bias fix = Shahdara (his area):

| Owner query | Result (top rows) |
|---|---|
| `karol bagh` | Karol Bagh Terminal bus station · Jhandewalan, 12 km; station · WEA; metro · …; market · Jhandewalan |
| `ashook nagar shadara gali no 4` | Street Number 4 · HDFC Bank Gagan Vihar, 1.8 km; Shaheed Nagar rows (phonetic hit); **t3: "AJIT NAGAR GALI NO.4, Ajit Nagar, Shahdara South · OpenStreetMap, 5.2 km"** |
| `pawan bakery near hanuman mandir` | Parul Cake And Confectioners bakery · Hanuman Mandir Park A Block, 1.5 km; Bikaner Sweets; Sweet Chariot; Mother Bakery — all anchored on the nearest real Hanuman Mandir |
| `nandanagri a block` | Block A · Rajendar Parsad Colony, 350 m; Nand Nagari Flyover · Nand Nagari; Nand Nagri Park |
| `india gate` | India Gate Entry … monument rows first (monument beats locality now) |
| `Your location` | Real fix resolved → plan `0 km · arrive now` degenerate (from==to==fix — proves the fix feeds 'from'); previously a Central-Delhi pin |

Honest misses hold: `zyxwv nonsense placename` → 0 rows + "not in the
map yet" notice; `gali` alone → 0 (filler isn't a place). Shots:
`docs/lanes/search-shots/` (s1–s6). Harness: `node src/search/test-t0.mjs`
— phonetic spellings resolve identically to correct ones.

## Known limits (honest)

- T0 corpus still has no house-number row for every Delhi gali — "gali
  no 4" answers with real gali-4 rows near the anchor locality, which is
  the correct honest answer; t3 Photon fills true address granularity
  when online. No fabricated "ashok nagar shahdara" pin is ever invented.
- t3 requires network + Photon availability; offline t0/t1 unchanged and
  still primary.
- Gates: `npx tsc --noEmit` clean, `npx expo lint` clean.
