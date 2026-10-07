# Lane report — delhi-today-truth: the phantom trips + the incidents card

Owner complaints (verbatim):
1. "Delhi Today is all bullshit hardcoded — it says I travelled, I just
   downloaded the app and it shows no trips but Delhi Today says where I
   travelled"
2. "I want local pollution incidents happening — parali and all — before
   Delhi Today"

Commit: `7a2cedd` on `base/v2`. Gates: `tsc --noEmit` clean,
`expo lint` clean, node:test store 84 / nav 76 / api 12 / offline 12 —
0 fail.

## 1. Audit — where the "trips" on a fresh install come from

**No seed, fixture, demo file, or ledger hydrate exists.** Traced every
path that could put trips in front of a fresh install:

- `DelhiToday.tsx` renders ONLY wire data: `fetchCity()`
  (`GET /v2/city`, `api/city.ts:124`) for corridors + day totals +
  `fetchCityMoves()` (`GET /v2/city/moves`) — 15-min last-good TTL cache
  (`api/cache.ts`), never bundled content.
- `store/ledger.ts` — `ledger.json` starts absent on a fresh install;
  the ONLY writer is `logTrip()`, called from `recordTrip` in
  `useShellFlow.ts:406` — itself called only on a REAL nav arrival
  (arrival-Done). Onboarding writes `consent.json`/`welcome_seen_v1.json`,
  never the ledger. `assets/delhi-gazetteer.json` is the search index
  (place names), not trips.
- `outbox.json` (`offline/queue.ts`) holds queued `POST /v2/trip`
  donations — written only after a logged trip with sharing ON
  (`consent.json` gate); empty on fresh install.
- Server side: `server/v2/city.py` builds `corridors` from
  `TRIPS.corridors()` (the donated-trip store, k≥3/72 h) and
  `trips.days` from the same store — no synthetic rows.

**The real mechanism — community aggregate rendered where it reads as
personal.** Live prod, `GET http://65.2.28.40/v2/city`, 07 Oct ~16:45 UTC:

    corridors: 9 — "hanuman lane 16 trips · 12 devices",
    "Punjab National Bank 5 · 5", "Atul Grove Road 10 · 8",
    "Fire Brigade Lane 3 · 3", "moti 11 · 7", "Battle of Basantar 7 · 5",
    "Motilal Nehru Marg 7 · 6", "Jodhpur Officers' Hostel 7 · 5"
    trips.days: 10-03: 17 trips · 71.7 km; 10-04: 14 · 58.1 km;
                10-05: 8 · 37.8 km; 10-07: 5 · 31.4 km

These are REAL donated trips — mostly dev/QA drives — but a fresh user
sits in an app whose job is counting HIS trips ("Your trips" door shows
"no trips yet"), opens "Delhi today", and sees "hanuman lane — 16 trips"
+ "what ALive travellers did today — 5 trips". Nothing on the sheet says
whose trips they are, so it reads as the app claiming his travel —
"bullshit hardcoded".

## 2. Fix — the traveller aggregates are gated on one real own trip

`DelhiToday.tsx`: `loadTrips()` resolves on sheet mount alongside the
fetches → `own` (trip count on THIS phone).

- `own === null` (ledger still reading — deferred to after the first
  frame by design): the corridor/totals/moves cluster renders nothing —
  the aggregate must never flash for a beat then vanish.
- `own === 0` (fresh install): the whole cluster — "streets travellers
  crossed", "what ALive travellers did today", `<CityMoves/>` —
  collapses to one quiet well: **"no trips yet — go live your day, we'll
  count it here"** + sub-line **"the streets and totals in this view are
  counted from trips other people share"** (en; hi keys added).
- `own > 0`: identical to before, including the pre-existing
  `corridors.length === 0 → cityEmptyStreets` and the CityMoves
  insufficient-data states.

The city-wide content stays for everyone: the hero breath figure,
species, 10-yr typical, 12-h forecast, why-line, cause_note, and the
"why this is an estimate" basis block — Delhi's air is real for a user
with no trips; only the *travel ledger of strangers* was the lie.

Nothing was deleted — the aggregate feature still exists, gated on the
state where it can no longer masquerade as the user's own history.

## 3. The local-incidents block — on home, above the Delhi-today door

`HomeScreen.tsx`: new `IncidentsCard` between `HeroBlock` and `DoorRow`
(the door list that opens "Delhi today") — literally *before Delhi
Today* in scroll order, visible without opening the sheet.

- Data: `fetchCity()` → `why.cause_note` / `cause_note_fields` — the
  measured parali/belt + ventilation + recorded-trend line the
  news-layer lane (795ff3b) already ships. Rides the shared 15-min
  last-good cache — no extra wire, no new endpoint.
- i18n: `en` keeps the wire line; `hi` rebuilds from
  `cause_note_fields` via `causeNote()` (same grammar as the sheet's
  `noteLine`) — wire English never reaches the hi UI.
- Provenance: the line ends with `· measured, not reported`
  (noteMeasured) — same tag as the sheet.
- Honest absence: renders nothing until a real note arrives (no
  skeleton/fake); on fetch failure stays absent rather than guessing.
  When no driver is in play the server-composed "local background"
  line is itself the honest answer and renders.
- Design law: paper card, flame glyph + warm label "in Delhi's air
  right now" (incidentsTitle, en+hi), neutral inks — no band colour;
  nothing in the card encodes a band.

Live prod note rendering in it right now (07 Oct ~16:45 UTC): "16 fires
in the Punjab–Haryana belt — the wind isn't carrying it this way right
now · air barely mixing — ventilation 2,356 m²/s vs ~3,000 typical ·
city mean 34.7 → 54.2 µg/m³ over 5.7 h · the climb is still on".

## 4. Verification — fresh install on the iPhone sim

iPhone 17 sim (iOS 26.5, `EDD9B083-…`), Release-iphonesimulator build
`EXPO_PUBLIC_API_URL=http://65.2.28.40`, `simctl uninstall` then
`install` so the container was truly fresh (Documents/ = `total 0`
pre-launch). Shots in `delhi-today-truth-shots/`:

- `00-launch.png` — welcome + the real notification-permission dialog;
  seconds later a real `cause_note` push fired ("the air is sitting
  over the city — 4× stiller than usual… · 16 fires in the
  Punjab–Haryana belt…").
- `01-home-incidents.png` — **the incidents card on home, above the
  doors**: "in Delhi's air right now — 16 fires in the Punjab–Haryana
  belt — the wind isn't carrying it this way right now · air barely
  mixing — ventilation 670 m²/s vs ~3,000 typical · city mean 35.2 →
  65.2 µg/m³ over 5.7 h · the climb is still on · measured, not
  reported". Above Air map / Delhi today / Your trips. The hero
  honestly reads "waiting for the first air reading today" (zero hours
  logged).
- `02-sheet-top.png` — Delhi today top: hero 1205 µg moderate + the
  measured line + species — all real wire data.
- `03-sheet-empty-state.png` — **the money shot**: forecast, then the
  quiet well "no trips yet — go live your day, we'll count it here ·
  the streets and totals in this view are counted from trips other
  people share", then "why this is an estimate". ZERO corridors, ZERO
  "what ALive travellers did today", ZERO CityMoves — while prod was
  simultaneously serving 9 corridors + 40 trips × 4 days (curl'd).

Filesystem truth after the whole flow (`get_app_container … data`,
`ls Documents/`): consent.json, daylog.json, daysum.json(+.bak),
events.json, settings.json, welcome_seen_v1.json, alive-cache/ —
**no ledger.json exists**, which is what the empty state read.

## Open edges / honest holes

- `own === 0` also hides the aggregates for a user who wiped data or
  hasn't finished a trip yet — intended: the sections can't claim
  "travellers" honestly to someone it just showed "no trips".
- Sharing OFF users who travel see the aggregates again (their trips
  count in THEIR Delhi today view; donation stays gated by consent —
  the empty-state sub-line says only that the view is counted from
  shared trips, never that theirs joined).
- Prod aggregate rows are still mostly QA/team devices — real data,
  small community. Not a code lie; flagged, not fixed here.
