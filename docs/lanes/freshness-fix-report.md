# Freshness-fix lane — the 8 stale numbers

Companion to `freshness-15-report.md` (the audit). Each finding got the
smallest honest change: re-pull against the real source cadence where a
refresh exists, disclose true age where the source can't move faster.
The field's 900 s CACHE_TTL is the floor everywhere — nothing below
claims newer than its source.

## 1. Landing + /city forecast timeline — cached per-h for the page session

**Changed** (`server/landing.html`, `server/city.html`): `tlFetch` now
stamps the served `properties.cell_epoch` (for `/grid?h=N` =
`[forecast_at, field_at, obs_version]`, so `epoch[1]` is the field build
the horizon frames were fetched under) plus a `touched` wall-clock. New
`tlInvalidate()` drops the cache, bumps `seq` (kills in-flight scrub
paints), and re-shows only the on-screen hour — the rest go back to lazy
fetch-on-touch. Two triggers, both free — no new polling loop:
the existing live polls compare `ep[0]` (live `cell_epoch` = field_at)
against `TL.epoch[1]`; `tlAged()` applies the 900 s floor; and the
existing `visibilitychange` handler runs `tlAged()` on tab re-entry.

**New worst case**: a field rebuild lands → next live poll (≤120 s
landing / ≤10 min city after F5's cap) drops the horizon cache. With a
hidden tab it waits for re-entry, then checks the same predicates.
Bounded by ~one field cadence + poll gap ≈ **17 min landing, ~15 min
city**; before, frames could sit the whole page session.

## 2. App fires + corridors — fetched once per app run

**Changed** (`Mobile/App.tsx`): `pullFires`/`pullCommunity` stamp
`firesAtRef`/`communityAtRef` on success. The existing 60 s reports poll
re-pulls any *enabled* overlay whose stamp crossed 15 min; toggling a
layer back on re-reads when its data crossed the cadence instead of
reviving launch-time dots. Spots (`/blackspots`) stays fetch-once — a
static list, no live clock to lag. Failed re-pulls keep last-good dots.

**New worst case**: **≤16 min** for an enabled overlay (15 min gate +
60 s poll beat); `/fires` itself serves 6 h caches with `acq` stamps —
unchanged intrinsic source truth, now disclosed rather than frozen.

## 3. Nav dose counters + receipt age — strip fetched once at trip start

**Changed** (`Mobile/src/nav/engine.ts`, `Mobile/src/nav/index.ts`,
`Mobile/App.tsx`): the 1 Hz tick re-pulls the strip after 10 min
(`STRIP_REFRESH_MS`, measured from attempt start so fetches never stack).
`stripSeqRef` = latest wins (reroute lands a new route_id mid-flight),
`stripBusyRef` dedupes same-id concurrent pulls, failed re-pulls keep
the last strip — it still mirrors a field epoch and discloses its age;
only a never-loaded strip freezes the counter (`stripOk=false`, as
before). `fieldAgeMin` state became `stripAge = {ageMin, at}` — the
serve-time age plus when it landed; `App.tsx` derives the receipt's
'updated N min ago' at render as `ageMin + (now − at)`, so the printed
age counts the trip's own elapsed. `start()` clears strip state — no
cross-trip bleed.

**New worst case**: dose counters integrate against a field read
**≤~10–11 min** old mid-ride (was: whole trip on start-time data);
receipt age print is **render-true** (was: fetch-time figure + up to
1 h of ride). Server route_ids die at 1 h — a re-pull then serves a
fresh route's strip or fails into the disclosed-age path.

## 4. DelhiToday sheet — frozen at open

**Changed** (`Mobile/src/screens/DelhiToday.tsx`): the mount effect now
runs `pull()` on a 60 s interval while the sheet is open (cleanup still
aborts on close; a poll blip only marks `failed` when nothing has ever
loaded — a mid-view blip keeps the last data). The age chip adds the
sheet's own sit: `nowMs` state ticks every 30 s (effects own the clock —
`react-hooks/purity`), printed age = `freshness.age_min` + elapsed since
the serve landed, and the chip self-marks stale past 15 min even if the
payload was served 'live'. `Math.round` keeps the minute honest.

**New worst case**: numbers refresh **≤60 s** while open; printed age is
render-true to ~30 s. (Was: everything frozen at open-time.)

## 5. /city poll — slept a full `refresh_in_s`

**Changed** (`server/city.html`): `rs = Math.min(refresh_in_s*1000,
600000)` — the donation counters (trips/dose/km today) move when a trip
lands, not when the field rebuilds, so the sleep caps at 10 min instead
of inheriting the field's 15-min cadence.

**New worst case**: **10 min** for the whole `/city` surface (was 15;
donation truth lags ≤10 min now, `/community` direct view stays 60 s —
the page can't outrun its own endpoint cadence, it just stops napping).

## 6. /city wind tag — no age printed

**Changed** (`server/city.html`, `server/landing.html`): the tag and
both landing wind reads append `· Nm old` once `wind.age_s > 900`
(one field cadence — wind's own ~31 min server expiry already ships
`age_s` on the wire).

**New worst case**: the *number* still dies at its source expiry (~31
min) — but it's **disclosed** past 15 min, which is the honest-cheap fix
the brief allows for a source that can't refresh faster.

## 7. Landing daybar 'now' marker — frozen on long-open pages

**Changed** (`server/landing.html`): the bar markup moved into
`dayBarsHtml(hrs, mx, now)`; `dayStrip` stores `DAY_HRS` and renders
through it; `dayTick()` re-derives the IST hour and re-marks `.now` —
hooked into the existing 120 s interval. No refetch: the climatology
curve is recorded history, only the marker is a clock fact.

**New worst case**: **≤120 s** across an hour boundary (was: the whole
page session).

## 8. /v2/city 'live' label — tolerated 2×TTL = 30 min

**Changed** (`server/v2/city.py`): `STALE_S = _FIELD_TTL` (was `2×`).
A field that just missed its own cadence now reads 'stale' until the
build lands — a brief honest flutter per cycle over a 'live' claim that
could stretch to 30 min. `tests/test_v2_city.py` pins the boundary:
`STALE_S` → live, `STALE_S + 1` → stale.

**New worst case**: the badge never claims live past **one field
cadence** (15 min); flutter at the boundary is the cost of honesty and
is documented in the comment.

---

## Verification

- `scripts/check_inline_scripts.py` — 4 script blocks parse clean
  (2 pre-existing prose warnings).
- `server/.venv312` rebuilt on this box; `pytest tests/test_v2_city.py
  tests/test_inline_scripts.py` — **17 pass** (includes the new
  STALE_S boundary asserts).
- `cd Mobile && npx tsc --noEmit` clean; `npx expo lint` clean
  (the age-chip clock went through `nowMs` state — `react-hooks/purity`
  and `set-state-in-effect` both apply, render stays pure).
- `node src/{store,nav,api,offline}/test-runner.mjs` — all pass
  (nav 94).
- Prod: not touched; GET-comparison applies only after a later deploy.

## Lane notes

- No new strings → en/hi parity untouched; no new fetches beyond the
  declared cadences; failed refreshes keep last-good + disclosed age —
  never a fake timer, never a number newer than its source.
- F6's wind number can't out-refresh its source expiry — disclosure is
  the fix, as the brief prescribed for genuinely heavy cases.
