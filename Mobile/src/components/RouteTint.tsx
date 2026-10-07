/**
 * <RouteTintSource/> — the route-wise AQI gradient on the map: every plan
 * option's polyline shaded per span by the field's PM2.5 on the CPCB band
 * ramp (all math in src/map/routeTint.ts — read its header for the data
 * contract and the colour scale).
 *
 * WIRING — mounted inside <Map> from App.tsx:
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
 * resolves into a real along-route gradient. /v2/plan `segments`
 * (the {geometry, pm25, band} spans) outrank strips when present.
 *
 * MOTION — the suggestion sequence, in the shell's timing:
 *  - a new option set: the recommended (selected) route paints at once —
 *    it asserts — while each alternative fades in over ~460 ms, staggered
 *    ~280 ms apart (option order, so the next-best leads).
 *  - a tap-swap: the newly chosen route settles into its bold state
 *    (~300 ms fade) and the demoted one fades down into the alternatives
 *    (~450 ms) — the swap reads as motion, not a jump-cut.
 *  - the mechanism is feature `op` props stepped on a timer — the two
 *    sources stay mounted for the app's whole life (the SIGSEGV class:
 *    unmounting a GeoJSONSource mid-draw segfaults the iOS-sim render
 *    thread). Reduce-motion collapses every stage to the final state;
 *    the first tick waits for whenMapDrawFree so a data flush can never
 *    ride a sheet-mount frame on the sim.
 *
 * Render order: unselected options first (thinner 3 px, ~50% opacity —
 * alternates keep their meaning), then the selected option: 9 px bg
 * casing under a 6 px gradient line — the same widths the shell already
 * uses (doc 03: route 6 px on 9 px casing). Round caps soften each
 * colour step into the next.
 */
import React, { useEffect, useMemo, useRef, useState } from "react";
import { GeoJSONSource, Layer } from "@maplibre/maplibre-react-native";
import { V2T } from "../theme";
import { useReduceMotion } from "../a11y";
import { whenMapDrawFree } from "../map/drawHold";
import type { V2Option } from "./shell/types";
import {
  collectionsFor,
  MAP_QUIET,
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

const EMPTY_FC: GeoJSON.FeatureCollection = {
  type: "FeatureCollection",
  features: [],
};

/* stagger timing — the compare-sheet card cadence (PressSpring ~250 ms)
 * stretched to map scale: alternatives appear one at a time, each fading
 * through three opacity steps (~460 ms) starting ~280 ms after the last.
 * ALT_OP is the resting opacity of an alternative — "muted ~50%". */
const ALT_OP = 0.5;
const STAGGER_MS = 280;
const FADE_START_MS = 350;
const FADE_STEPS: readonly (readonly [number, number])[] = [
  [0, 0.2],        // t+0   appear faint
  [230, 0.34],     // t+230 mid-fade
  [460, ALT_OP],   // t+460 settled — ~460 ms per option, inside the 400–600 ask
];
const DEMOTE_OP = 0.18;   // just-deselected route fades down into the alts
const DEMOTE_MS = 450;
const SELECT_FADE_MS = 300; // newly-chosen route settles into its bold state

/** `fc`'s features painted at `op` — opt null = every feature (the
 *  selected FC is one option; the alts merges filter per option). */
const atOp = (fc: GeoJSON.FeatureCollection, opt: number | null, op: number) =>
  fc.features
    .filter((f) => opt == null || f.properties?.opt === opt)
    .map((f) => ({
      ...f,
      properties: { ...f.properties, op },
    }));

/** splice one option's staged features into the current alts FC —
 *  other options keep whatever opacity stage they've reached. */
const mergeOpt = (
  cur: GeoJSON.FeatureCollection,
  feats: GeoJSON.Feature[],
  opt: number,
): GeoJSON.FeatureCollection => ({
  type: "FeatureCollection",
  features: [...cur.features.filter((f) => f.properties?.opt !== opt), ...feats],
});

function RouteTintSourceFn({
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
  const reduceMotion = useReduceMotion();

  /* staged paint: what the sources actually carry. Staggered updates
     rewrite feature `op` only — the layer's data-driven line-opacity
     animates them; sources/layers never unmount (the crash class). */
  const [stagedAlts, setStagedAlts] = useState<GeoJSON.FeatureCollection>(tint.alts);
  const [stagedSel, setStagedSel] = useState<GeoJSON.FeatureCollection>(tint.selected);
  const prevOptionsRef = useRef(options);
  const prevSelectedRef = useRef(selected);

  /* A — a NEW option set: recommended asserts immediately, alternatives
     reveal staggered in option order (index 0 = recommended leads the
     alts too when it isn't the selected one). Strip arrivals or other
     tint churn on the SAME set paint plainly — data refresh trumps
     animation. */
  useEffect(() => {
    const newSet = prevOptionsRef.current !== options;
    prevOptionsRef.current = options;
    /* selection tracking belongs to effect B — only a brand-new set
       resets it here (setting it unconditionally would swallow B's
       demote-settle, which runs after this effect on the same commit) */
    if (newSet) prevSelectedRef.current = selected;
    /* every staged write rides a timer — synchronous setState in an
       effect body is both a lint error and a commit the draw-hold
       machinery can't order (the crash class is mount-vs-draw) */
    const timers: ReturnType<typeof setTimeout>[] = [];
    if (!newSet || reduceMotion) {
      timers.push(
        setTimeout(() => {
          setStagedAlts(tint.alts);
          setStagedSel(tint.selected);
        }, 0),
      );
      return () => timers.forEach(clearTimeout);
    }
    const altOpts = [
      ...new Set(tint.alts.features.map((f) => f.properties?.opt as number)),
    ].sort((a, b) => a - b);
    timers.push(
      setTimeout(() => setStagedSel(tint.selected), 0),
      setTimeout(() => setStagedAlts(EMPTY_FC), 0),
    );
    whenMapDrawFree(() => {
      altOpts.forEach((opt, k) => {
        for (const [dt, op] of FADE_STEPS) {
          timers.push(
            setTimeout(
              () =>
                setStagedAlts((cur) =>
                  mergeOpt(cur, atOp(tint.alts, opt, op), opt)),
              FADE_START_MS + k * STAGGER_MS + dt,
            ),
          );
        }
      });
    });
    return () => timers.forEach(clearTimeout);
    // options identity marks the plan fetch; tint carries strips/selected
  }, [options, tint, reduceMotion, selected]);

  /* B — a tap-swap on the SAME option set: the new choice settles into
     its bold state with a short fade and the demoted route eases down
     into the alternatives — the swap reads as settle, not a jump-cut. */
  useEffect(() => {
    const prevSel = prevSelectedRef.current;
    if (prevSel === selected || prevSel == null) return;
    prevSelectedRef.current = selected;
    const demoted =
      typeof prevSel === "number"
        ? prevSel
        : options.findIndex((o) => o.route_id === prevSel);
    const timers: ReturnType<typeof setTimeout>[] = [];
    if (reduceMotion) {
      timers.push(
        setTimeout(() => {
          setStagedAlts(tint.alts);
          setStagedSel(tint.selected);
        }, 0),
      );
      return () => timers.forEach(clearTimeout);
    }
    timers.push(
      setTimeout(() => {
        setStagedSel({ type: "FeatureCollection", features: atOp(tint.selected, null, 0.35) });
        setStagedAlts({
          type: "FeatureCollection",
          features: tint.alts.features.map((f) =>
            f.properties?.opt === demoted
              ? { ...f, properties: { ...f.properties, op: DEMOTE_OP } }
              : f),
        });
      }, 0),
      setTimeout(() => setStagedSel(tint.selected), SELECT_FADE_MS),
      setTimeout(() => setStagedAlts(tint.alts), DEMOTE_MS),
    );
    return () => timers.forEach(clearTimeout);
  }, [selected, tint, options, reduceMotion]);

  /* Sources + layers stay mounted for the app's whole life: unmounting a
    GeoJSONSource issues removeSource/removeLayer on the native style, and
    when that lands mid-draw on the iOS-sim render thread it segfaults
    (upstream MapLibre class — hit here at receipt-Done/options-clear).
    Swapping data for an empty FeatureCollection never removes anything,
    draws nothing, and costs one no-op native call. */
  const altsData =
    showAlts && options.length ? stagedAlts : EMPTY_FC;
  return (
    <>
      <GeoJSONSource id="routeTintAlts" data={altsData}>
        <Layer
          id="routeTint-alts-line"
          type="line"
          paint={{
            "line-color": ["coalesce", ["get", "color"], MAP_QUIET],
            "line-width": 3,
            "line-opacity": ["coalesce", ["get", "op"], ALT_OP],
          }}
          layout={{ "line-cap": "round", "line-join": "round" }}
        />
      </GeoJSONSource>
      <GeoJSONSource id="routeTintSel" data={options.length ? stagedSel : EMPTY_FC}>
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
            "line-color": ["coalesce", ["get", "color"], MAP_QUIET],
            "line-width": 6,
            "line-opacity": ["coalesce", ["get", "op"], 1],
          }}
          layout={{ "line-cap": "round", "line-join": "round" }}
        />
      </GeoJSONSource>
    </>
  );
}

/** memoized: the parent re-renders every poll tick; these
 *  map children only earn a commit when their own props move */
export const RouteTintSource = React.memo(RouteTintSourceFn);

export default RouteTintSource;
