/**
 * <RouteTintSource/> — the route-wise AQI gradient on the map: every plan
 * option's polyline shaded per ~250 m chunk by the field's PM2.5
 * (lane r4-routegrad; all math in src/map/routeTint.ts — read its header
 * for the data contract and the colour scale).
 *
 * WIRING — inside <Map>, REPLACE the existing "alts" + "route"
 * GeoJSONSources (App.tsx ~L162-172) with:
 *
 *   <RouteTintSource
 *     options={flow.options}
 *     selected={flow.selected}          // index, or a route_id string
 *     strips={stripsByRouteId}          // Record<route_id, RouteStrip> —
 *                                       // optional; see below
 *   />
 *
 * `strips` is optional: without it every option still tints flat by its
 * own dose.avg_conc_ugm3 (the honest route-mean). Feed it as strips
 * arrive — one GET /v2/strip?route_id per option — and each polyline
 * resolves into a real along-route gradient. If a future payload revives
 * option.segments, no prop changes are needed.
 *
 * Render order: unselected options first (thinner 3 px, 50% opacity,
 * still breath-ramp coloured — alternates keep their meaning), then the
 * selected option: 9 px bg casing under a 6 px gradient line — the same
 * widths the shell already uses (doc 03: route 6 px on 9 px casing).
 * Chunk-end round caps soften each colour step into the next.
 */
import React, { useMemo } from "react";
import { GeoJSONSource, Layer } from "@maplibre/maplibre-react-native";
import { V2T } from "../theme";
import type { V2Option } from "./shell/types";
import {
  collectionsFor,
  TINT_STEP_M,
  type StripLookup,
} from "../map/routeTint";

export type RouteTintSourceProps = {
  /** the ranked option set from planOptions() (POST /v2/plan) */
  options: V2Option[];
  /** selected option — INDEX into `options` (flow.selected) or a
   *  route_id string; null/undefined → nothing drawn selected */
  selected?: number | string | null;
  /** strips keyed by route_id — Record, Map, or (routeId)=>strip */
  strips?: StripLookup;
  /** chunk length in metres (default 250 — the strip cadence) */
  stepM?: number;
  /** draw unselected alternates (default true) */
  showAlts?: boolean;
};

export function RouteTintSource({
  options,
  selected = 0,
  strips,
  stepM = TINT_STEP_M,
  showAlts = true,
}: RouteTintSourceProps) {
  // one derivation per plan fetch / strip arrival / selection change —
  // perOption inside is already the per-option precompute, never rebuilt
  // per render.
  const tint = useMemo(
    () => collectionsFor(options, selected, strips, { stepM }),
    [options, selected, strips, stepM],
  );

  if (!options.length) return null;
  return (
    <>
      {showAlts && tint.alts.features.length > 0 && (
        <GeoJSONSource id="routeTintAlts" data={tint.alts}>
          <Layer
            id="routeTint-alts-line"
            type="line"
            paint={{
              "line-color": ["coalesce", ["get", "color"], V2T.text3],
              "line-width": 3,
              "line-opacity": 0.5,
            }}
            layout={{ "line-cap": "round", "line-join": "round" }}
          />
        </GeoJSONSource>
      )}
      {tint.selected.features.length > 0 && (
        <GeoJSONSource id="routeTintSel" data={tint.selected}>
          <Layer
            id="routeTint-sel-casing"
            type="line"
            paint={{ "line-color": V2T.bg, "line-width": 9 }}
            layout={{ "line-cap": "round", "line-join": "round" }}
          />
          <Layer
            id="routeTint-sel-line"
            type="line"
            paint={{
              "line-color": ["coalesce", ["get", "color"], V2T.text3],
              "line-width": 6,
            }}
            layout={{ "line-cap": "round", "line-join": "round" }}
          />
        </GeoJSONSource>
      )}
    </>
  );
}

export default RouteTintSource;
