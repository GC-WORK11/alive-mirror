# routegrad-r4 — route-wise AQI gradient

Lane: `r4-routegrad` (Alive). Route polylines shaded per ~250 m chunk by
the live field's PM2.5 — the hero "which road do I breathe" visual.

## Files (this lane owns all of them — new files only)

| File | What |
|---|---|
| `Mobile/src/map/routeTint.ts` | Pure math: geometry + concentrations → `FeatureCollection` of short `LineString`s with `pm25`/`lo`/`hi`/`color`/`src` props. No RN/MapLibre imports. |
| `Mobile/src/map/routeTint.test.ts` | Node-runnable self-test (32 assertions). Recipe in its header. |
| `Mobile/src/components/RouteTint.tsx` | `<RouteTintSource>` — `GeoJSONSource` + `Layer` binding (`@maplibre/maplibre-react-native` v11). |

## Data path (what the server actually gives us)

`POST /v2/plan` options carry **no per-segment pm25** today (`server/v2/plan.py`
`_option`). What exists:

| Source | Field | Where |
|---|---|---|
| Geometry | `option.geometry` (LineString; `route_geojson` alias) | `/v2/plan` option |
| Route mean | `option.dose.avg_conc_ugm3` | `/v2/plan` option |
| Per-250 m field samples | `GET /v2/strip?route_id` → `samples[] = {lat, lon, dist_m, pm25, lo, hi}` | `src/api/strip.ts` → `fetchStrip()` |
| Per-segment payload | `option.segments` (`Seg[]`: `coords`, `avg_conc_ugm3`, `start_frac`, `end_frac`) | legacy seam on `V2Option`; `server/segments.py` annotates the *legacy* `/routes` endpoint — `/v2/plan` does not emit it yet |

`routeTint` resolves in that order per option: **segments → strip → dose
average → null**. Strip distance is cumulative (`stripCumM` — server `dist_m`
is the chunk *length ending at* each sample) and is rescaled onto geometry
metres before querying `fieldAtAlongM` at each chunk midpoint — both odometers
describe the same path, so the rescale is ~1 and end-clamping covers the rest.

## Wiring contract (integrator)

```tsx
// useShellFlow (or a sibling hook) — fetch once per plan, keyed by route_id:
const [strips, setStrips] = useState<Record<string, RouteStrip>>({});
useEffect(() => {
  options.forEach((o) => {
    if (!o.route_id || strips[o.route_id]) return;
    fetchStrip(o.route_id)
      .then((s) => setStrips((m) => ({ ...m, [o.route_id!]: s })))
      .catch(() => {});                       // option just stays flat-tinted
  });
}, [options]);

// App.tsx inside <Map> — REPLACE the "alts" and "route" GeoJSONSources:
<RouteTintSource options={flow.options} selected={flow.selected} strips={strips} />
```

| Prop | Type | Notes |
|---|---|---|
| `options` | `V2Option[]` | ranked set from `planOptions()` |
| `selected` | `number \| string \| null` | option **index** (`flow.selected`) or `route_id` |
| `strips` | `Record<string, RouteStrip> \| Map \| (id) => strip` | optional; lookup key is `route_id` |
| `stepM` | `number` | chunk length, default `TINT_STEP_M` = 250 |
| `showAlts` | `boolean` | draw unselected options (default `true`) |

Without `strips` every option still renders — flat-tinted by its own
`dose.avg_conc_ugm3` (honest: it *is* the option's mean). No data at all →
quiet grey, never invented.

Alternative minimal-diff path: feed `collectionsFor(options, flow.selected,
strips)` into the existing memos — `routeSegs` ← `.selected`, `altSegs` ←
`.alts`. Both existing layers already paint `["get","color"]`; the features
are drop-in.

## Colour scale — identical to `theme.doseColor`

Same stops everywhere so a red street means the same thing as red dose text:

| PM2.5 µg/m³ | Colour | Token |
|---|---|---|
| `null` or `< 60` | `#8A94A0` grey — quiet = *absence* of colour (doc 03: no green) | `V2T.text3` |
| `60 – 130` | `#F2C14E` amber | `V2T.breath1` |
| `130 – 250` | `#F08A3C` orange | `V2T.breath2` |
| `≥ 250` | `#EE5A5F` red | `V2T.breath3` |

Colours are **baked** per feature (`color` prop, via `doseColor`) — the same
contract the current `route-line` layer uses. `PM25_LINE_COLOR` exports the
equivalent `["step", …]` expression for layers that prefer `["get","pm25"]`.
`Seg.color` from legacy payloads is deliberately re-tinted: it was the old
server scale; the map must not carry two scales.

## Rendering

- Selected: 9 px `V2T.bg` casing under a 6 px gradient line (doc 03 widths).
- Unselected: 3 px at 50% opacity — thinner/dimmer but still breath-ramp
  coloured so alternates keep their meaning on the map.
- Round caps soften each ~250 m colour step into the next.
- `useMemo` keys the derivation on `[options, selected, strips, stepM]` —
  per-option resampling runs once per plan fetch, never per render.

## Sample feature (strip path)

```json
{
  "type": "Feature",
  "properties": {"pm25": 230.0, "lo": 184.0, "hi": 276.0,
                 "color": "#F08A3C", "seg": 3, "opt": 0, "src": "strip"},
  "geometry": {"type": "LineString",
               "coordinates": [[77.2025, 28.6000], [77.2027, 28.6004], …]}
}
```

## Self-test

```bash
cd Mobile
npx tsc src/map/routeTint.test.ts --ignoreConfig --outDir /tmp/rgt-check \
  --module nodenext --moduleResolution nodenext --target es2022 \
  --skipLibCheck --esModuleInterop --strict --types geojson
node /tmp/rgt-check/map/routeTint.test.js   # → "routeTint self-test OK — 32 assertions"
```
