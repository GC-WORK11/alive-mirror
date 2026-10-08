# union-regression-v2 lane — second collision pass

Lane goal: the first union pass (`union-regression-report.md` @
`01cde84`) cleared 15 parallel lanes. Since then **20 more commits**
landed on `base/v2`, several of them on the same files that wave-1
touched (`t0.ts`, `client.ts`, `server/v2/search.py`,
`App.tsx`, `strings.ts`). Same law: did the wave break anything?

Commits under test, `01cde84..25dc9e5` (in order):

```
15e6b50 map-perf report        849fd4a sigbus-release (iOS)
e147dbd leftover-fixup         5f4d99f demo-script-v3 (docs)
56ea591 lifecycle-drive        0b6144b lifecycle-drive (report note)
c9a298c lifecycle-android      f39a63c hi strings
9e75472 boot-burst (input-priority)
1384a6c / ba2b125 boot-burst reports
918d1ac daycount-honesty       b4c82ce boot-film-truth
9a0799a boot-storm (cap() wt + patches fix)
e22240c / 869ae21 / ea5dfb9 deploy-8 audit fixes
b7bf20b deploy-8 report        fda1083 index-prebuild
25dc9e5 index-prebuild report
```

HEAD at verification: `25dc9e5`. Prod probed GET-only.

## Verdict

**Three real union breaks found, all fixed in this commit.** HEAD was
CI-red at two gates before the fix (`tsc`, and `Search index tests` via
the prebuilt-parity case; the third break failed
`test_contract_sync`). One break is **already live on prod** (evidence
below); it ships the fix on the next deploy.

---

## BROKE → FIXED

### Break A — `hydrateNext` dropped `wt`: every prebuilt query scored NaN

Collision: `boot-storm` `9a0799a` added a precomputed `wt` field to
`Entry` (rank weight, so `cap()` stops running the `typeBonus` regex
gauntlet per compare). `index-prebuild` `fda1083` had authored its
chunk-hydrate path ~9 min earlier and never saw `wt` — `hydrateNext()`
pushed entries without it.

On the **shipped path** (prebuilt chunks — the default every device
runs; lazy build is only the fallback), this meant:

- `npx tsc --noEmit`: `TS2345` at the `cap()` call — `weight()` reads
  `e.wt` which is `undefined` on hydrated entries.
- Every hydrated entry scored `NaN` in `cap()`'s comparator → rank
  order degenerated to posting order → wrong results for real queries
  (the parity test's "karol bagh" returned temple/church rows instead
  of the macrohood).
- `areaNear` compared `NaN > best` → always false → `"x · locality"`
  subtitles dead on the prebuilt path.

Detection: `tsc` + `src/search/test-runner.mjs` parity case
("prebuilt hydrate: identical results to the lazy build"). The parity
test exists precisely for this class of drift and caught it.

Fix (`src/search/t0.ts`): single shared formula `rankWeight(c, w, k) =
typeBonus(c) + w*0.5 + k*2`, used by both `indexRow` (lazy build) and
`hydrateNext` (chunk merge — chunks ship `c/w/k` and recompute;
`typeBonus` is memoized so this is ~720 regex evals, not 124k).
Verified: tsc clean, parity 5/5, `test-t0.mjs` rankings correct on the
shipped chunks.

### Break B — `_t1_pos` scratch field leaks onto the wire (live on prod)

Collision: `deploy-8` `869ae21` widened `_merge`'s dedupe to the
client's `sameNamedPlace` rule (400 m with an admin side, admin
yields). That collapses **intra-t1** dupes (e.g. the Connaught Place
district↔macrohood pair at 117 m) that the old 75 m wire dedupe never
reached. The strip loop at the end of `_merge` only popped `_t1_pos`
from `merged` — but a row that *loses* the dedupe stays in `t1_rows`,
and the endpoint returns that array raw. Dormant pre-869ae21 because
nothing that far inside t1 ever got collapsed; activated the moment
the rule widened.

Live evidence (prod, GET `?q=connaught`):
`t1` array carries `"_t1_pos": 2` on exactly the deduped CP district
row — while every merged survivor shows the key popped. Merged results
are correct (CP collapses to one row — dedupe works); the leak is in
the raw `t1` diagnostic array only. Contract
(`tests/test_contract_sync.py::test_nested_place_and_strip_rows`)
forbids `_t1_pos` on the wire; it failed.

Fix (`server/v2/search.py`): strip the scratch field from `t1 + t2`
(the source lists), not just `merged`. Verified: contract test +
`test_v2.py` (incl. the new +27-case admin-collapse probe) all pass.
Ships on next deploy — the leak is **live on prod today**.

### Break C — `test-t0.mjs` harness fell to zero (returned [] for all queries)

Not a product bug — a harness broken by `fda1083`'s changed contract:
`query()` never sync-builds now, it answers `[]` until the index lands
on the scheduler. The dev harness still called `query()` cold and
every check degenerated to "returned 0 rows".

Fix (`src/search/test-t0.mjs`): hydrate the **shipped** chunked index
(`assets/t0-index/chunks.js` via `__t0.hydrate`) before probing — i.e.
exercise the prebuilt path the app actually runs, not the lazy
fallback. Rankings now correct and assertive again (karol bagh →
macrohood first; "bakery near hanuman mandir" → real bakeries with
`· Hanuman Mandir Flyover` subtitles — `kindScan` + `areaNear` live).

---

## CLEAN — each named intersection verified

**Early-query → dedupe → pick ordering** — `index-prebuild`'s
`[]`-when-cold + `onIndexReady` replay composes with the armed-from
pick fix (`e147dbd`) and the client dedupe. `SearchScreen` replays
through `qRef`/`locRef` (latest state, not stale args), `armed` is
matched by `sameNamedPlace` so it survives the row-swap when the real
index lands, and `pick` honors `editWhich` (`useShellFlow` /
`App.tsx`). `nearestPlace()→null` cold is honest — the coordinate
fallback path in `shell/net.ts` is unchanged.

**WelcomeScreen deleted (`b4c82ce`)** — zero references in `src/`;
`welcome.ts` install-flag stubs are intentional (still read by
`App.tsx`). First-boot sequence intact: ambient beat → `gateReady` →
OnboardingScreen → `introSeen` → location ask (`App.tsx` 626-672).

**Input-priority (`9e75472`) vs chunk hydration (`fda1083`)** — both
yield on the same gate: `hydrateNext` runs *inside* `step()`, which
checks `msSinceInput() < 1200` before every unit — chunk hydration and
`buildSlice` yield identically. `tileWarm`/`warmBasemap` wait for 2 s
quiet (`INPUT_QUIET_MS`). Interleave is by construction, verified in
code.

**hindi parity (`f39a63c` + `918d1ac` + `b4c82ce`)** —
`hi: Record<StringKey, string>` is compiler-enforced; tsc clean ⇒ no
key can exist in one language but not the other. Measured anyway:
947 keys `en`, 947 keys `hi`.

**Server `_merge` dedupe vs client dedupe** — identical rule on both
sides (`d<75 m`, or `d<400 m` with an admin side, admin yields; early
list wins). Compose is idempotent: applying the same deterministic
rule twice cannot collapse a third legit row that survived the first
pass. `normalize()` vocab drift (server `gazetteer` is a superset —
TOKEN/PHRASE aliases + `&`→`and`) can only *under*-collapse on the
client, never over-collapse — safe direction.

**Line-name regexes (`ea5dfb9`)** — dotted feed-id union composes with
existing strip rules; `transit_v2.py` updated in lockstep.

**`patches/*.patch` (`9a0799a`)** — diff-format fix verified on this
box: fresh `npm ci` postinstall applied all 3 patches cleanly
(expo-modules-core 57.0.20, expo-modules-jsi 57.1.1,
react-native 0.86.3). Pre-fix clones silently applied none — this
box's stale `node_modules` confirmed that was real.

**`check_inline_scripts.py`** — 4 inline blocks in 4 files parse clean
(deploy-8's `landing.html` + `DepartGraph` `now:null` handling in
scope); 2 prose-comment warnings, not code.

## Gates (union tree, post-fix HEAD 25dc9e5)

| gate | result |
|------|--------|
| `npx tsc --noEmit` | clean, 0 errors |
| `npx expo lint` | clean |
| `node src/search/test-runner.mjs` | **5/5** (was failing parity pre-fix) |
| `node src/store/test-runner.mjs` | 16/16 |
| `node src/nav/test-runner.mjs` | 76/76 |
| `node src/api/test-runner.mjs` | 17/17 |
| `node src/offline/test-runner.mjs` | 16/16 |
| `node src/search/test-t0.mjs` | correct rankings on shipped chunks (was returning `[]` for everything pre-fix) |
| server `pytest -q tests` | **1262 pass, 5 skip, 0 fail** (565 s) — was 1 fail (`_t1_pos` contract) pre-fix |
| `python3 scripts/check_inline_scripts.py` | OK — 4 blocks parse clean |

## Files changed by this lane

- `Mobile/src/search/t0.ts` — `rankWeight` shared by `indexRow` +
  `hydrateNext` (Break A)
- `Mobile/src/search/test-t0.mjs` — hydrate shipped chunks, exercise
  the real path (Break C)
- `server/v2/search.py` — strip `_t1_pos` from `t1 + t2`, not just
  `merged` (Break B)

## Residuals

- **`_t1_pos` leak is live on prod** (deploy-8 shipped the widened
  merge). Harmless field, wrong contract. Clears on the next deploy —
  no action beyond the normal ship.
- `normalize()` vocabulary divergence (server ⊋ client) is worth a
  named TODO at some point — today it only under-collapses on the
  client, which is the safe direction.
