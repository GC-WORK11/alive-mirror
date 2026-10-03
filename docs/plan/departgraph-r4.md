# r4-departgraph — "leave later" dose curve

Lane-owned files (new, no shared-file edits):

- `Mobile/src/components/DepartGraph.tsx` — pure-RN bar/candlestick chart.
- `Mobile/src/api/depart.ts` — typed GET `/depart` client (first api-module
  wrapper for this endpoint; `useShellFlow.ts` previously fetched it inline
  and kept only `best` + `ug_saved_vs_now`, discarding the 24 h `slots`).

## Data contract (server → component)

`GET /depart?from_lat&from_lon&to_lat&to_lon&vehicle&hours=24` returns:

    { vehicle, mode, duration_min, distance_km,
      now|best|worst: { hours_ahead, start, dose_ug, avg_conc_ugm3 },
      ug_saved_vs_now,           // PERCENT despite the name (0–100 int)
      slots: […same slot shape…], // 0..23 in hours_ahead order
      forecast: { age_s, … } }

`depart.ts` maps this to `DepartCurve` with `DepartSlot = { hour, start,
dose_mid, dose_lo, dose_hi, avg_conc_ugm3 }`. `DepartSlot` is a structural
superset of the component's `DepartDatum`, so `curve.slots` feeds `data`
directly. The server emits no lo/hi per slot today — the props carry the
optionals so a future banded payload renders whiskers with no UI change.

## Component props

    data:          DepartDatum[]   // {hour, dose_mid, dose_lo?, dose_hi?, start?}
    bestHour:      number          // = curve.best.hour — accent bar + dot
    selectedHour?: number          // controlled; omit → internal tap state
    onSelectHour?: (hour, d) => {} // omit → non-interactive render
    lang:          Lang            // "en" | "hi"
    height?:       number          // bar area pt, default 64 (total ~110)

## Mount sketch (CompareSheet — under the depart row, or Sidebar)

    const r = await departCurveResult({ from, to, vehicle: options[selected].mode });
    // r.ok + r.stale/ageS for honest offline labelling; fetchDepartCurve()
    // is the data-or-null convenience form.
    {r.ok && r.data.slots.length > 0 &&
      <DepartGraph data={r.data.slots} bestHour={r.data.best?.hour ?? 0}
        lang={lang} onSelectHour={(h) => …} />}

The flow's existing `Depart` state (`shell/types.ts`) is untouched —
integration can keep it for the remind row and fetch the curve separately,
or widen it to keep `slots`.

## Honesty / design notes

- Colours: best = `V2T.accent`, now = `V2T.text3` baseline, others
  `V2T.out2` (design rule: "good" carries no colour ramp).
- Bars scale to `max(dose_hi ?? dose_mid)`; whisker shows the band only
  when `dose_hi > dose_lo` actually differ.
- Axis ticks read the data's own hour values (now/+6/+12/+18/last), not a
  hardcoded 24 — a short forecast stays truthful.
- Caption: `est.` (existing `receipt_estShort` key) + focused slot's
  clock+µg. The word "now" is a small local map in the file marked
  NOTE(l10n) — migrate into `i18n/strings.ts` at merge (lane constraint:
  no shared-file edits).
- `ug_saved_vs_now` is a PERCENT (server `round(100*(1-best/now))`),
  matching the existing "breathe ~{n}% less" copy.
- `start` is naive-UTC ISO → rendered IST (+5:30), same convention as
  `CompareSheet.hourLabel`.

Verified: `npx tsc --noEmit` + `npx expo lint` clean on feat/r4-departgraph.
