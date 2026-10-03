# Ledger screen — trips history (S-sidebar item 3)

`Mobile/src/screens/LedgerScreen.tsx` — full-screen sheet over the map,
same contract as `SearchScreen`:

```tsx
<LedgerScreen visible onClose={...} lang={lang} />
```

Transparent `Modal` (slide), sheet mounts only while `visible` → fresh state
each open. Loads trips itself via `loadTrips()`; no props for data.

## What it shows

- **Summary header** ("last 7 days"): breathed (cigarettes, via
  `weekStats().weekUg` ÷ `CIG_UG`), put out (kg — only when any trip in the
  window carries `emit_kg`), trips count. Columns with no data are omitted
  (doc 02 §4).
- **Trip rows** (newest first): mode icon (`vehicleGlyph(tr.vehicle)`),
  `from → to`, `label · date · time`, breathed in cigarettes, put-out kg when
  stored, "≈ N cigarettes less than the smokiest way" when `avoided_ug > 0`.
- **Per-trip expander** — receipt-style details level (doc 10):
  cigarettes + `est. N µg` (or `est. lo–hi µg` when `dose_lo_ug`/`dose_hi_ug`
  exist), put-out kg, saved-vs-smokiest line, "shared anonymously" badge when
  `donated === true`, and "delete this trip".
- **Empty state**: "no trips yet" + one line on what gets recorded +
  "trips stay on your phone".
- **Delete all** (footer, destructive `breath3`) with `Alert` confirm →
  `clearTrips()`.

## Store additions (`Mobile/src/store/ledger.ts`, additive only)

- `Trip.emit_kg?` — SEAM(emissions): smoke the ride put out; only rendered
  when present. Nothing writes it yet (`useShellFlow` seam).
- `Trip.dose_lo_ug?` / `dose_hi_ug?` — SEAM(bands): shown only when logged;
  never interpolated from the point dose (no fake precision).
- `Trip.donated?` — SEAM(donation): badge renders only when `true`.
- `deleteTrip(match)` — removes one trip matched on ts+from+to+vehicle.
- `clearTrips()` — rewrites `ledger.json` to `[]`.

## Copy rules enforced

Surface strings are consumer wording only (doc 02 §3): cigarettes, "smoke you
breathed / your ride put out", "the smokiest way". `µg` and lo–hi bands appear
only inside the expander. All strings via `t()` — keys `ledger_*` / `trips_*`
in en + hi (plus reused `tripsEmpty`, `breathed`, `putOut`, `cancel`,
`deleteConfirmYes`, `sidebarTrips`). Numbers use `NUM` (tabular-nums);
`fmtCig` returns `<0.01` rather than a fake `0`. Dark V2T tokens only;
no green, no gradients — "lighter" shows as absence of colour.
