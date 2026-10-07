# Lane report — `/v2/skill` 6 s tail

**Date:** 2026-10-07 ~11:45–12:20 UTC. **Lane:** `/v2/skill` latency
(flagged by `landing-perf-report.md`: 761 B payload, 6.00 s TTFB — a
6 s tail holding one of six HTTP/1.1 slots). **Baseline:** prod
`43913dc0`; fix measured on this box, not deployed.

## What the measurement actually showed

`/v2/skill` already had a 120 s payload cache (`skill._CACHE`, TTL +
fingerprint `fp = (len, max, root, bucket)`). The cost isn't the cache
— it's what a **miss** does: `skill_payload` re-read **every** archive
doc the enumeration lists (44 snapshots, 5.9 kB gz each). Local mirror
reads are ~0.7 ms/doc, but the mirror only holds what the *current
task* wrote — every snapshot older than the last deploy/crash is
S3-only. At ~130 ms per sequential `get_object`:

| prod situation | miss cost |
|---|---:|
| archive mostly S3-side (post-deploy, crash-restart) | **44 sequential GETs + 1 LIST ≈ 5.9 s** — the landing lane's 6.00 s |
| live recomputes caught on prod 12:04–12:15 UTC (task ~7 h old, ~36 docs S3-side): gen advanced ~every 120 s under traffic, each miss **4.5–4.9 s**, queued callers 2.2–3.4 s | **4.83–4.94 s** |
| archive all-local (long-lived task) | ~90–280 ms CPU |

And the misses are frequent, not rare: the payload cache only serves
inside 120 s **and** an unchanged `fp`, but a new snapshot lands every
IST hour (`len`/`max` bust) and any traffic gap > 120 s expires it.
Live evidence: `generated_ist` advances roughly every ~120 s — prod
recomputes hundreds of times a day, each ~5 s while the archive is
S3-side. Two misses inside the same window can also queue on the
single-worker `_SKILL_EXEC`.

## What changed (`server/skill.py`, `server/archive.py`)

Kept the payload cache semantics; made the recompute cheap instead of
blocking on it:

- **`_DOCS` parsed-doc cache** — `(day,hh) → (sig, doc)`. Each entry
  carries the source signature enumeration just saw (local mtime / S3
  `LastModified`+`Size`), so a miss re-reads **only** sources that are
  new or rewrote — not "the newest file is probably mutable" reasoning,
  a content-level check per key. Scoped to `(root,bucket)`; gone-from-
  archive keys drop; bounded `_DOCS_MAX` (env, default 256) oldest-key
  eviction — an over-cap listed doc reads as *unreadable* (thin
  direction, never invented numbers) and re-fills next miss.
- **`fp` gains `tuple(sorted(sigs))`** — the payload cache now busts on
  any source-content change (a capture rewriting its own current-hour
  bucket refreshes immediately instead of up to 120 s stale). S3 sig
  needs `LastModified`/`Size`, which `_enum_s3` now keeps — two extra
  keys on the info dict; `_load_doc` and the other enumerate callers
  are untouched.
- **Cold fill parallelized** — when > 4 docs need loading (post-deploy,
  process restart), they're fetched 8-wide (`ALIVE_SKILL_LOAD_WORKERS`)
  off one shared boto client, instead of strictly sequential.

## Numbers (this box, simulated prod latency 130 ms/S3 op, 44 docs)

| path | before | after |
|---|---:|---:|
| cold fill (all-S3 archive, once per process) | ~6.3 s sequential | **1.03 s** (1 LIST + 44 GET ×8) |
| TTL-expired miss, archive unchanged | ~6.3 s | **0.13 s** (1 LIST + 0 GET) |
| hourly `fp` bust (1 new snapshot) | ~6.3 s | **0.33 s** (1 LIST + 1 GET + join) |
| doc parsed size held in cache | — | ~0.42 MB → 256-doc cap ≈ ~108 MB worst |

Wire bytes, payload contract, pair semantics: unchanged — a miss still
re-scans the whole archive; it just stops re-fetching it.

## Tests

`tests/test_skill.py` +2 (13/13 pass; focused run
skill+archive+executor+cache 50/50):

- `test_doc_cache_loads_only_the_delta` — spies `_load_doc`: cold fill
  reads all 12; an expired-TTL miss reads **0**; one new snapshot reads
  **1**.
- `test_same_hour_rewrite_is_regraded` — re-captures the same IST bucket
  (same keys, same max, new content): the payload re-scores the new doc
  inside the TTL. **Fails on the old code** — the old `fp` couldn't see
  a same-count rewrite and served the stale payload for up to 120 s.

## Honest caveats

- The ~6 s "before" is the S3-side path at ~130 ms/op — matching the
  landing lane's 6.00 s almost exactly, and the live recomputes caught
  on prod (4.83–4.94 s, ~every 120 s under traffic, 12:04–12:15 UTC)
  are consistent with ~36 of 44 docs S3-side on the current task.
  On a task with a fully local mirror the miss was already ~0.1–0.3 s —
  the fix bounds the S3-side tail, which is when users/judges actually
  feel it.
- Still O(archive) CPU per miss (enumerate LIST + the join over cached
  docs ~0.1 s today). The archive grows ~24 docs/day; `_DOCS_MAX` bounds
  memory but past it each miss re-reads the overflow. Fine for the demo
  window; the long-term shape is incremental aggregation if this
  matters post-demo.
- Not deployed — deploy lane batches server changes; the 120 s TTL and
  env knobs (`ALIVE_SKILL_TTL_S`, `_DOCS_MAX`, `_LOAD_WORKERS`) carry
  defaults that need no ops action.
