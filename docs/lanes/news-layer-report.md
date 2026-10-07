# Lane report — news-layer (the parali/news card, `cause_note`)

Commit: `5e46b5d` on `base/v2` (rebased over c3f7e9e). One line of
plain-words context built **only from measured fields** — belt
detections, carrying wind, ventilation, recorded city mean — shipped
as `cause_note` + `cause_note_fields` on `/v2/why` and `/v2/city`,
re-rendered through i18n in the app, appended as `{note}` to every
air-event ping, and tiled as **parali watch** on `city.html`.

## 1. Inventory — what a notification said when parali smoke carried

Verified on live prod (`GET /v2/why`, 07 Oct ~09:00 UTC):

```json
evaluated.fires: {seen:true, belt_fires:12, belt_frp_mw:26.2,
                  n_fires:44, modifier:1.06, feed:"firms-public-csv",
                  feed_status:"live", carrying:false}
wind: {from_deg:218, speed_kmh:5.5}
```

The existing context chain: `drivers[]` (kind/weight/score/evidence)
→ `line` ("local background — no single driver stands out") →
client `causeClause` (" — stubble smoke riding the north-west wind")
on trend/outlook pings; `notifyFiresBody` = "{a} → {b} fires in the
burn belt — wind carrying it this way". **Gap**: a ping named the
driver but never assembled the *situation* — belt trend vs recorded
builds, stillness, measured city mean, GRAP — and the app air-card
had no news line at all.

## 2. Free news feeds — the honest verdict

Nothing on the internet is both free and a licensable "news" feed for
Delhi air:

| source | status |
|---|---|
| NASA FIRMS | already wired — belt counts ARE the parali signal |
| CPCB daily AQI Bulletin | PDF of *measurements* (same numbers we already serve), not news copy |
| SAFAR/IITM EWS | `ews.tropmet.res.in` unreachable (RFC1918 private IP, iitm_probe.py); SAFAR = email-alert form only |
| IMD API | account/key-gated |
| PTI / granthamin / any wire RSS | copyrighted, not free |

So the implementation is **measured-data-as-news** — package what we
already measure, labeled "measured, not reported" on every surface.

## 3. `cause_note` — grammar from real fields only

`server/v2/why.py:_cause_note` composes ` · `-joined clauses; every
clause is gated on the same floors the explainers themselves use:

- `"{n} fires in the Punjab–Haryana belt"` — `belt_fires ≥ SMOKE_MIN_BELT` (belt ≥10);
  below it "a quiet belt — {n} fires burning" / "a quiet belt right now".
- `"up from {a} over ~{h}h"` — `_belt_delta`: live count vs the **oldest
  in-window recorded build** in the served history. Gates: `feed_status=="live"`
  (a recorded fallback vs a recorded build compares the same number twice),
  ≥2 belt rows, span ≥ `HISTORY_MIN_SPAN_S` (3h), |Δ| ≥ `_NOTE_DELTA_MIN` (5 —
  under that it's FIRMS re-count noise).
- carry clause — `carrying` true/false/null read three honest ways, with
  the real `from_deg` compass + `speed_kmh`.
- `"air barely mixing — ventilation {vc} m²/s vs ~3,000 typical"` —
  `factor ≥ STAG_FACTOR_MIN` (1.25), `vc_m2s` from the served read.
- `"city mean {a} → {b} µg/m³ over {h}h"` — `|delta_ug| ≥ TREND_MIN_DELTA_UG`
  with served endpoints.
- verdict tail — `"smoke inflow meeting still air"` when carrying+stag
  stack; `"the climb is still on"` on an admitted rising trend.
- empty → `"local background — no big driver in play right now"`.

`cause_note_fields` carries the compact ingredient set (basis="measured",
belt_fires, belt_delta{,_h}, carrying, wind_{from_deg,kmh}, vc_m2s,
stag_factor, trend_{from,to,span_h}) so consumers re-localize without
parsing English.

Live example (local server, live FIRMS public CSV, 10:26 UTC):
`"12 fires in the Punjab–Haryana belt — the wind isn't carrying it
this way right now"` — belt 12, SW wind 236° → not carrying; belt_delta
null (fresh snap root, one build — the floor held honestly).

## 4. Surfaces

- **Notifications** — `{note}` appended to every air-event body:
  fires/fires_nc (skip `belt` — the ping narrates its own count+carry),
  band, stagnation (skip `stag`), severe, grap_up/down/clear,
  trend_up/down (skip `trend`), outlook_heavy/light (skip `trend`).
  Note is empty when `/v2/why` didn't run that poll — a notification
  never pads with nothing.
- **App air-card** — `DelhiToday.tsx`: the note under the hero why-line
  with a dimmed ` · measured, not reported` tag. en keeps the wire
  `cause_note`; hi rebuilds from `cause_note_fields` via
  `causeNote()`/`causeFieldsFromWhy` in `events-core.ts` (wire English
  never reaches the hi UI; an old server leaves the line absent).
- **Web** — `city.html` "parali watch" tile in the same `.whyline`
  family as "why tonight"/"grap": mono tag + text, warm neutral card.
- Mirrors updated: `Mobile/src/api/city.ts`, `Bridge/contract.ts`.

## 5. Tests + verification

- `server/tests/test_v2_why.py` (+8): `_belt_delta` gates, full-carry
  compose, blocked-wind wording, cold-feed suppresses "jumped", quiet/
  background paths, every floor holds, endpoint serves note+fields,
  city.html tile present. **36 passed.**
- `Mobile/src/store/events.test.ts` (+8): field derivation incl. the
  served-history belt delta, cold-feed/sup-floor suppression, skip
  clauses, hi localization (no wire-English leak), null→empty.
  **84 passed** via `node src/store/test-runner.mjs`.
- Gates: `npx tsc --noEmit` clean; `npx expo lint` clean;
  `check_inline_scripts.py` OK; `test_contract_sync` + `test_v2_city` +
  `test_city_moves` + `test_health_detail` 100 passed.
- Full server suite: 1162 passed / 3 failed — all three in
  `test_path_legality.py`/`test_query_tolerance.py` (`alive_core`
  optional engine module not importable on this box + one latency
  assert) — unrelated, pre-existing environment gap.
- **Live render**: local server booted with live feeds (FIRMS public
  CSV, Open-Meteo; stations key absent → honest degrade), `/v2/why` +
  `/v2/city` verified above; `city.html` card screenshot —
  PARALI WATCH tile under the why/grap tiles.

## Design-law check

Warm-neutral surface, no new colors, mono tag label + body text
(13px+), no alarm words — "worsening" appears only as "the climb is
still on" behind an admitted positive trend; the honest empty answer
is "local background", never silence.
