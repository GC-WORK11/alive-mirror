# script-guard — inline-script syntax gate + apostrophe sweep

Lane: `script-guard`. Pass **2026-10-07 ~08:40 UTC** (≈14:10 IST).
Trigger: P0 `326e64e` → fixed `f9ea5ae` — a plain-words copy pass left a
bare `'` inside a single-quoted JS string in `server/landing.html`
(`'the map's reach'`). The apostrophe ended the literal early, the tail
of the line became garbage tokens, and the whole ~54KB inline `<script>`
failed to parse → landing dead on prod for hours. Existing guardrail
`test_landing_script_wellformed` only counts braces — they still
balanced, so it stayed green.

## The gate — `scripts/check_inline_scripts.py` (stdlib only)

- Extracts every inline `<script>` block from `server/*.html` with a real
  HTML parser (`html.parser`), not regex. `<script>` text inside
  `<!-- -->` comments is prose — the earlier regex extraction fell into
  that trap (admin.html:524, landing.html:526 legitimately discuss "the
  parse-time gate at the head of `<script>`"). Those are emitted as
  **warnings**, never extracted as code.
- Writes each block to a temp file padded with newlines so node's
  reported line number **is the HTML file's line number**, then runs
  `node --check`. On failure it retries as `.mjs` (module) before
  reporting the script-mode error, so a future `<script type="module">`
  or top-level `import` doesn't false-alarm.
- No node → fallback string-aware scanner: newline inside a `'`/`"`
  literal, unterminated string/comment/template at EOF, unbalanced
  `(){}[]` outside strings/comments. Tripwire, not a parser — the run
  header prints which checker ran and `--allow-no-node` is required to
  accept it.
- `--strict` promotes warnings to failures.

### Wired in two places

1. `server/tests/test_inline_scripts.py` — runs the script as a
   subprocess (same path CI calls), asserts the four blocks pass and
   the "4 inline script block(s)" marker appears; plus two red tests
   proving the guard fires (below).
2. `.github/workflows/ci.yml` — `Inline script syntax gate` step in the
   server job, right after checkout: a syntax bomb fails the push in
   seconds, before deps/cmake/suite. ubuntu-latest ships node.

### Proof it catches the bug class

Planted the exact f9ea5ae shape in a fixture:

```
$ python3 scripts/check_inline_scripts.py /tmp/bad.html
ERROR /private/tmp/bad.html:8
      '<b>a→b</b> — that point sits outside the map's reach; pick inside it';
                                                    ^
SyntaxError: Unexpected identifier 's'
check_inline_scripts: FAIL — 1 error(s) ... [node --check]
exit=1
```

Line 8 = the real HTML line (padding works). Fallback scanner on the
same fixture: `line 9: unterminated '-quoted string (newline inside
literal — classic bare-apostrophe bomb)`.

```
$ cd server && .venv312/bin/python -m pytest tests/test_inline_scripts.py -q
3 passed in 0.59s
$ python3 scripts/check_inline_scripts.py
WARN  server/admin.html:524: '<script' inside HTML comment (prose — NOT extracted)...
WARN  server/landing.html:526: '<script' inside HTML comment (prose — NOT extracted)...
check_inline_scripts: OK — 4 inline script block(s) in 4 file(s) parse clean [node --check], 2 warning(s)
```

## Apostrophe sweep — every user-facing surface, classified

Pattern: `'[^'\n]*[A-Za-z]'[A-Za-z]` (letter-`'`-letter inside a
single-quoted context = candidate bomb). **Every hit was inspected;
zero live bombs.** All matches are in contexts where `'` is legal:

| file:line | context | verdict |
|---|---|---|
| admin.html:599 | HTML text (`can't`, `isn't`) outside `<script>` | safe |
| admin.html:1243 | inside `` ` `` template literal (`server's`) | safe |
| city.html:73, :1384, :1540 | inside `/* */` comments | safe |
| city.html:820, :940 | inside `` ` `` template literals (`model's`, `today's`) | safe |
| landing.html:1168 | inside `/* */` comment | safe |
| landing.html:1373 | inside `` ` `` template literal (`didn't`) | safe |
| strings.ts:175 | `"`-quoted value (`that's`, `map's`) | safe |
| strings.ts:678 | inside `/* */` comment | safe |
| Mobile src (12 more hits) | all inside `//` or `/* */` comments | safe |
| server/v2/*.py (8 hits) | `#` comments, `"""` docstrings, `"`-quoted payloads (why.py:739) | safe |

Authoritative backstop: `node --check` is green on all four extracted
blocks (admin 1986 lines, city 1089, community 111, landing 1151).
Correct-by-construction evidence: the escaped-`\'` convention is already
in use at 10 sites — landing.html:1293 (the f9ea5ae fix), admin.html:833,
1595, 1600, 2442, 2600, city 1 site, community 3 sites. strings.ts
values are 100% `"`-quoted, so apostrophes there can't terminate a
literal. No inline `on*=` handler builds JS from user data
(admin.html:1599/1600/1932 interpolate code constants; the one
apostrophe in them, `'how it\'s made'`, is escaped). No Python emits
`<script>`/`innerHTML` — grep for `innerHTML|onclick|javascript:` across
server/ finds only middleware.py:326, a CSP comment.

**Verdict: swept, clean.** The one real bomb was already fixed at
f9ea5ae; the grep enumeration above is the proof no second one hides.

## Mobile compile status — honest

The plain-words pass `326e64e` touched `src/i18n/strings.ts`,
`CompareSheet.tsx`, `types.ts` after the release APK base — never
compiled in anger. On this checkout (base/v2 @ f9ea5ae+):

```
$ cd Mobile && npx tsc --noEmit            → exit 0, no output
$ cd Mobile && npx expo lint               → exit 0, no output
$ cd Mobile && npx expo lint --max-warnings 0 → exit 0 (config:
  eslint.config.js, eslint 9 + eslint-config-expo ~57 — the run is real,
  not a no-op)
```

Zero type errors, zero lint errors/warnings. Nothing to fix — the
plain-words files compile clean; they just had never been gated.

## What this does NOT catch (named, not hidden)

- A correctly-quoted string with the *wrong* text (copy regressions are
  review/lane-report work, not syntax).
- External `<script src>` integrity (none exist — all four pages are
  single-block inline).
- JS in `<script>` blocks *generated at runtime* by server Python — none
  exists today; the four pages are static files.
- The fallback scanner's regex heuristic can false-positive on exotic
  regexes; CI/dev boxes have node, so the weak path only arms where
  node is genuinely absent (and `--allow-no-node` must opt in).

## Files

- `scripts/check_inline_scripts.py` — the gate (stdlib only)
- `server/tests/test_inline_scripts.py` — subprocess wiring + red tests
- `.github/workflows/ci.yml` — `Inline script syntax gate` step (server job)
- this report
