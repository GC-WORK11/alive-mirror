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
 *     from={fromPin} to={toPin}         // [lon,lat] — the frame act's
 *                                       // endpoint rings (optional;
 *                                       // falls back to the selected
 *                                       // geometry's own endpoints)
 *     lang={lang}                       // pill copy language
 *   />
 *
 * `strips` is optional: without it every option still tints flat by its
 * own dose.avg_conc_ugm3 (the honest route-mean). Feed it as strips
 * arrive — one GET /v2/strip?route_id per option — and each polyline
 * resolves into a real along-route gradient. /v2/plan `segments`
 * (the {geometry, pm25, band} spans) outrank strips when present.
 *
 * MOTION — THE CHOOSER. When a NEW option set lands the map visibly
 * thinks, in four acts inside whenMapDrawFree:
 *   0. frame — before any line draws, a ring breathes once on each
 *      endpoint (origin first, then destination ~170 ms later): the
 *      trip itself is marked on the map — your from and your to —
 *      while nothing else moves. ~640 ms.
 *   1. ways  — up to three drawable candidates (candidatesFor: ranked
 *      alternates first, the selected row LAST) trace on span by span
 *      at an ease-out cadence (the pen relaxes as it arrives), each
 *      option ~¾ s and staggered ~540 ms so every alternative lands as
 *      its own felt moment — all at one equal "contender" opacity:
 *      every line a real option the server priced.
 *   2. hold  — a ~300 ms breath where all candidates read as equals.
 *   3. settle — the losers dip toward hairline while the winner
 *      re-traces itself bold from → to (three slices, ~190 ms apart,
 *      rising opacity: 9 px casing under 6 px line = thickens), the
 *      losers ease back to the hairline alternate style, and a verdict
 *      pill pins onto the route just after the winner's weight lands:
 *      one short claim re-derived from the set's own numbers
 *      (chooserVerdict — "cleanest · 41% less than fastest" only when
 *      the fastest option's dose really is that much heavier). ~4 s
 *      on, then it fades. The whole beat lands in ~3½–5 s depending
 *      on how many candidates the server priced.
 *  A tap-swap on the SAME set keeps the older motion: the new choice
 *  settles into its bold state (~300 ms) while the demoted one eases
 *  down into the alternatives (~450 ms).
 *  Every stage is feature `op` props stepped on a timer — the two
 *  sources and the pill Marker stay mounted for the app's whole life
 *  (the SIGSEGV class: unmounting a GeoJSONSource/MarkerView mid-draw
 *  segfaults the iOS-sim render thread). Reduce-motion collapses every
 *  stage to the final state (the pill still labels — sans fade); the
 *  first tick waits for whenMapDrawFree so a data flush can never ride
 *  a sheet-mount frame on the sim. The beat is interruptible: any new
 *  selection/options change clears every pending stage.
 *
 * Render order: unselected options first (thinner 3 px — alternates keep
 * their meaning), then the selected option: 9 px bg casing under a 6 px
 * gradient line — the same widths the shell already uses (doc 03: route
 * 6 px on 9 px casing). Round caps soften each colour step into the next.
 */
import React, { useEffect, useMemo, useRef, useState } from "react";
import { Animated, Easing, StyleSheet, Text, View } from "react-native";
import { GeoJSONSource, Layer, Marker } from "@maplibre/maplibre-react-native";
import { fam, V2Elev, V2Radius, V2T } from "../theme";
import { useReduceMotion } from "../a11y";
import { whenMapDrawFree } from "../map/drawHold";
import { Icon } from "../icons";
import { t, type Lang } from "../i18n/strings";
import { reasonTxt } from "./shell/CompareSheet";
import { DELHI } from "./shell/net";
import { flattenCoords, type LonLat } from "../nav/offroute";
import type { V2Option } from "./shell/types";
import {
  candidatesFor,
  chooserVerdict,
  collectionsFor,
  MAP_QUIET,
  pointAtFrac,
  TINT_STEP_M,
  type ChooserVerdict,
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
  /** trip endpoints [lon,lat] — the frame act's ring pulse sits on each
   *  pin. Optional; falls back to the selected geometry's own ends. */
  from?: LonLat | null;
  to?: LonLat | null;
  /** pill copy language (default en) */
  lang?: Lang;
};

const EMPTY_FC: GeoJSON.FeatureCollection = {
  type: "FeatureCollection",
  features: [],
};

/* ── the chooser's clock ────────────────────────────────────────────────
 * frame → ways → settle (see the file header). The frame holds the map
 * for one breath while a ring marks each endpoint; each candidate then
 * gets ~¾ s of its own — span batches land on an ease-out cadence
 * (CAND_GROUP_DELAY: quick early spans relax into the tail, so the line
 * draws like a pen, not a progress bar) with the next option starting
 * CAND_STAGGER_MS after the previous one BEGAN — overlapping trails,
 * each alternative its own visible moment. The settle lands
 * SETTLE_GAP_MS after the final chunk: losers hairline, the winner
 * re-traces bold from → to in WIN_SWEEP slices, and the verdict pins
 * PILL_DELAY_MS after the winner's full weight lands. Three ~12-span
 * candidates ≈ 3.4 s of motion, then the pill — felt, not rushed. */
const ALT_OP = 0.5;          // resting opacity of an alternative
const CAND_OP = 0.85;        // contender opacity — equal, prominent
const FRAME_MS = 640;        // endpoint rings land before the first line
const FRAME_STAGGER_MS = 170;// origin ring, then the destination ring
const RING_MS = 640;         // one ring's expand + fade
const FRAME_NO_END_MS = 220; // no endpoints to frame → a short pre-roll
const CAND_STAGGER_MS = 540;
const CAND_GROUPS = 11;
/* ease-out span cadence — cumulative ms at each group index. Draws
   fast where the line is being born, settles as it arrives. */
const CAND_GROUP_DELAY: readonly number[] = [
  0, 42, 88, 138, 192, 250, 312, 378, 448, 522, 600,
];
const CAND_IN: readonly (readonly [number, number])[] = [
  [0, 0.16],           // span appears faint
  [120, 0.5],          // blooms
  [230, CAND_OP],      // settles to contender opacity
];
const SETTLE_GAP_MS = 300;   // the equality breath before the claim
const DROP_OP = 0.3;    // losers' dip — a visible demotion, not a cut
const WIN_SWEEP_MS = 190;   // winner re-traces: bold slices from → to
const ALT_SET_MS = 420;   // ghost clears, losers rest at ALT_OP — one
                          // clean beat after the winner's sweep lands
const PILL_DELAY_MS = 260;  // verdict lands just after the winner's weight
const DEMOTE_OP = 0.18;   // tap-swap: just-deselected route fades down
const DEMOTE_MS = 450;
const SELECT_FADE_MS = 300; // newly-chosen route settles into its bold state
const PILL_HOLD_MS = 4200;  // verdict pill's time on route

/** `fc`'s features painted at `op` — opt null = every feature (the
 *  selected FC is one option; the alts merges filter per option). */
const atOp = (fc: GeoJSON.FeatureCollection, opt: number | null, op: number) =>
  fc.features
    .filter((f) => opt == null || f.properties?.opt === opt)
    .map((f) => ({
      ...f,
      properties: { ...f.properties, op },
    }));

/** `feats` painted at `op`. */
const withOp = (feats: GeoJSON.Feature[], op: number) =>
  feats.map((f) => ({ ...f, properties: { ...f.properties, op } }));

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

/** refresh a staged FC's geometry/colour from the newest tint while
 *  KEEPING each feature's staged opacity — strip arrivals mid-beat
 *  recolour in place instead of rewinding the reveal. Maps over the
 *  STAGED features (not next's): a chunk the beat hasn't drawn yet must
 *  stay undrawn — mapping next would land every pending chunk and the
 *  winner at default opacity mid-reveal. Match on (opt, seg): the
 *  chunk's stable identity inside collectionsFor. */
const recolor = (
  cur: GeoJSON.FeatureCollection,
  next: GeoJSON.FeatureCollection,
): GeoJSON.FeatureCollection => ({
  type: "FeatureCollection",
  features: cur.features.map((cf) => {
    const nf = next.features.find(
      (f) =>
        f.properties?.opt === cf.properties?.opt &&
        f.properties?.seg === cf.properties?.seg,
    );
    return nf ? { ...nf, properties: { ...nf.properties, op: cf.properties?.op } } : cf;
  }),
});

/** The pill's one line — every claim re-derived by chooserVerdict from
 *  the served numbers; `reason` is the server's own reason_line run
 *  through the sheet's verbatim translator. */
const verdictText = (v: ChooserVerdict, lang: Lang): string | null => {
  if (!v) return null;
  switch (v.kind) {
    case "best": return t("chooser_best", lang);
    case "cleanestVsFastest":
      return t("chooser_lessVsFastest", lang, { n: v.pct });
    case "cleanest": return t("chooser_cleanest", lang);
    case "fastest": return t("chooser_fastest", lang);
    case "reason": return v.text ? reasonTxt(v.text, lang) : null;
  }
};

function RouteTintSourceFn({
  options,
  selected = 0,
  strips,
  stepM = TINT_STEP_M,
  showAlts = true,
  from = null,
  to = null,
  lang = "en",
}: RouteTintSourceProps) {
  // one derivation per plan fetch / strip arrival / selection change —
  // perOption inside is already the per-option precompute, never rebuilt
  // per render.
  const tint = useMemo(
    () => collectionsFor(options, selected, strips, { stepM }),
    [options, selected, strips, stepM],
  );
  const reduceMotion = useReduceMotion();
  /* timers scheduled inside whenMapDrawFree close over `tint` — which a
     strip arrival swaps mid-beat. Reads go through the ref so a staged
     step always paints the NEWEST colours, never a stale closure. */
  const tintRef = useRef(tint);
  useEffect(() => {
    tintRef.current = tint;
  });

  /* staged paint: what the sources actually carry. Staggered updates
     rewrite feature `op` only — the layer's data-driven line-opacity
     animates them; sources/layers never unmount (the crash class). */
  const [stagedAlts, setStagedAlts] = useState<GeoJSON.FeatureCollection>(tint.alts);
  const [stagedSel, setStagedSel] = useState<GeoJSON.FeatureCollection>(tint.selected);
  const prevOptionsRef = useRef(options);
  const prevSelectedRef = useRef(selected);

  /* ── the verdict pill ── anchored ON the selected route a little past
     its midpoint; appears at the settle, holds ~4 s, fades away. The
     Marker itself never unmounts and its coordinate parks on the last
     real anchor — the same always-mounted pattern the endpoint pins use
     (annotation churn mid-draw is the sim SIGSEGV class). */
  const selIdx = typeof selected === "number"
    ? selected
    : options.findIndex((o) => o.route_id === selected);
  const anchor = useMemo(
    () => pointAtFrac(options[selIdx]?.geometry, 0.45),
    [options, selIdx],
  );
  const verdict = useMemo(
    () => (selIdx >= 0 ? chooserVerdict(options, selIdx) : null),
    [options, selIdx],
  );
  const line = verdictText(verdict, lang);
  const leafGlyph = verdict != null && verdict.kind !== "fastest" && verdict.kind !== "reason";
  const [pillEpoch, setPillEpoch] = useState(0);
  /* a stable Animated.Value via lazy useState — useRef(...).current in
     render is a lint error (refs during render) */
  const [pillV] = useState(() => new Animated.Value(0));
  /* ── the frame act's endpoint rings — always-mounted Markers whose
     children swap <View/> → ring at beat start (the sanctioned
     annotation-content pattern; the Marker itself never unmounts).
     Anchors are the real endpoint pins when App passes them, else the
     selected route's own snapped ends. The epoch is a counter so a new
     plan re-fires the pulse; each ring's Value resets then expands. */
  const endCoords = useMemo(() => {
    const g = flattenCoords(options[selIdx]?.geometry);
    return {
      from: from ?? g[0] ?? null,
      to: to ?? g[g.length - 1] ?? null,
    };
  }, [options, selIdx, from, to]);
  const endsRef = useRef(endCoords);
  useEffect(() => {
    endsRef.current = endCoords;
  });
  const [ringFromEpoch, setRingFromEpoch] = useState(0);
  const [ringToEpoch, setRingToEpoch] = useState(0);
  const [ringFromV] = useState(() => new Animated.Value(0));
  const [ringToV] = useState(() => new Animated.Value(0));
  useEffect(() => {
    if (!ringFromEpoch || reduceMotion) return;
    ringFromV.setValue(0);
    Animated.timing(ringFromV, {
      toValue: 1, duration: RING_MS,
      easing: Easing.out(Easing.cubic), useNativeDriver: false,
    }).start();
  }, [ringFromEpoch, ringFromV, reduceMotion]);
  useEffect(() => {
    if (!ringToEpoch || reduceMotion) return;
    ringToV.setValue(0);
    Animated.timing(ringToV, {
      toValue: 1, duration: RING_MS,
      easing: Easing.out(Easing.cubic), useNativeDriver: false,
    }).start();
  }, [ringToEpoch, ringToV, reduceMotion]);
  /* the settle flashes the pill only when there's an honest line and a
     real anchor — mirrored through a ref so timer closures can check. */
  const pillReady = useRef<{ text: string | null; anchor: LonLat | null }>({
    text: null,
    anchor: null,
  });
  useEffect(() => {
    pillReady.current = { text: line, anchor };
  });
  useEffect(() => {
    if (!pillEpoch) return;
    Animated.timing(pillV, {
      toValue: 1,
      duration: reduceMotion ? 0 : 240,
      useNativeDriver: false,
    }).start();
    const t = setTimeout(() => {
      Animated.timing(pillV, {
        toValue: 0,
        duration: reduceMotion ? 0 : 340,
        useNativeDriver: false,
      }).start();
    }, PILL_HOLD_MS);
    return () => clearTimeout(t);
  }, [pillEpoch, pillV, reduceMotion]);

  /* Beat + swap timers live in refs, NOT in an effect cleanup list.
     Effect A re-runs on every tint churn — strips stream in over
     seconds after each plan — and a cleanup-owned beat died on the
     first strip, ~ms after options: on sim the final state appeared
     with no candidate draw and no pill. A beat clears only when a NEW
     option set lands or the component unmounts; a stale draw-free
     callback can't resurrect a dead beat because it checks the
     generation before scheduling. */
  const beatTimers = useRef<ReturnType<typeof setTimeout>[]>([]);
  const swapTimers = useRef<ReturnType<typeof setTimeout>[]>([]);
  const beatGen = useRef(0);
  const alive = useRef(true);
  useEffect(() => () => {
    alive.current = false;
    for (const t of [...beatTimers.current, ...swapTimers.current]) {
      clearTimeout(t);
    }
  }, []);

  /* A — a NEW option set runs the chooser beat (see the file header):
     candidates draw on as equals → a breath → the winner settles bold
     and the pill names why. Strip arrivals or other tint churn on the
     SAME set only re-colour the staged features in place — the reveal
     never rewinds for fresher data. */
  useEffect(() => {
    const newSet = prevOptionsRef.current !== options;
    prevOptionsRef.current = options;
    /* selection tracking belongs to effect B — only a brand-new set
       resets it here (setting it unconditionally would swallow B's
       demote-settle, which runs after this effect on the same commit) */
    if (newSet) prevSelectedRef.current = selected;
    if (!newSet) {
      /* strip churn mid-beat: recolour what's staged, keep pending
         chunks pending — the beat's own writes read tintRef anyway */
      const t = setTimeout(() => {
        setStagedAlts((cur) => recolor(cur, tintRef.current.alts));
        setStagedSel((cur) => recolor(cur, tintRef.current.selected));
      }, 0);
      return () => clearTimeout(t);
    }

    beatGen.current += 1;
    const gen = beatGen.current;
    const bt = beatTimers.current;
    for (const t of [...bt, ...swapTimers.current]) clearTimeout(t);
    bt.length = 0;
    swapTimers.current.length = 0;
    const flash = () => {
      /* the pill pins only when the verdict has an honest line and a
         real anchor — checked via the ref so stale closures can't
         flash a pill the data doesn't back */
      if (pillReady.current.text && pillReady.current.anchor) {
        setPillEpoch((e) => e + 1);
      }
    };
    /* every staged write rides a timer — synchronous setState in an
       effect body is both a lint error and a commit the draw-hold
       machinery can't order (the crash class is mount-vs-draw) */
    if (reduceMotion || options.length === 0) {
      bt.push(
        setTimeout(() => {
          setStagedAlts(tint.alts);
          setStagedSel(tint.selected);
          flash();
        }, 0),
      );
      return;
    }
    /* the beat — t=0 both sources empty; the frame act pulses a ring on
       each endpoint (the trip's from → to marked before any line), then
       candidates (≤3 drawable, selected last) trace on at an ease-out
       cadence, each option's own felt moment; at the settle the losers
       dip to hairline while the winner re-traces itself bold from → to
       and the verdict pins onto the route. */
    const cands = candidatesFor(options, selected, tint.perOption);
    bt.push(
      setTimeout(() => {
        setStagedSel(EMPTY_FC);
        setStagedAlts(EMPTY_FC);
      }, 0),
    );
    whenMapDrawFree(() => {
      if (!alive.current || gen !== beatGen.current) return;
      /* act 0 — frame: mark the endpoints (origin, then destination).
         Rings anchor on the passed pins or the winner's snapped ends —
         no pins and no geometry → the frame collapses to a pre-roll. */
      const ends = endsRef.current;
      const framed = ends.from != null || ends.to != null;
      const frameMs = framed ? FRAME_MS : FRAME_NO_END_MS;
      if (ends.from) {
        bt.push(setTimeout(() => setRingFromEpoch((e) => e + 1), 0));
      }
      if (ends.to) {
        bt.push(
          setTimeout(() => setRingToEpoch((e) => e + 1), FRAME_STAGGER_MS),
        );
      }
      /* act 1 — ways */
      cands.forEach((opt, pos) => {
        const start = frameMs + pos * CAND_STAGGER_MS;
        const n0 = tintRef.current.perOption[opt]?.features.length ?? 0;
        const n = Math.max(1, Math.min(CAND_GROUPS, n0));
        for (let g = 0; g < n; g++) {
          for (const [dt, op] of CAND_IN) {
            bt.push(
              setTimeout(() => {
                const fs = tintRef.current.perOption[opt]?.features ?? [];
                const cut = Math.ceil((fs.length * (g + 1)) / n);
                setStagedAlts((cur) =>
                  mergeOpt(cur, withOp(fs.slice(0, cut), op), opt));
              }, start + CAND_GROUP_DELAY[g] + dt),
            );
          }
        }
      });
      /* act 2 — settle */
      const lastFeats = cands.length
        ? tintRef.current.perOption[cands[cands.length - 1]]?.features.length ?? 0
        : 0;
      const revealMs =
        CAND_GROUP_DELAY[Math.max(0, Math.min(CAND_GROUPS, lastFeats) - 1)] +
        CAND_IN[CAND_IN.length - 1][0];
      const settleT =
        frameMs + Math.max(0, cands.length - 1) * CAND_STAGGER_MS +
        revealMs + SETTLE_GAP_MS;
      /* the winner's claim: everything staged dips toward hairline —
         the winner keeps a faint ghost — while its line re-traces bold
         from → to over it (cumulative slices at rising weight). When
         the sweep completes the alts pool returns to just the losers at
         resting opacity (the winner's ghost leaves with it). */
      const winSweep = () => {
        const fs = tintRef.current.selected.features;
        const thirds = [
          fs.slice(0, Math.ceil(fs.length / 3)),
          fs.slice(0, Math.ceil((2 * fs.length) / 3)),
        ];
        return [0.62, 0.82].map((op, i) =>
          setTimeout(
            () =>
              setStagedSel({
                type: "FeatureCollection",
                features: withOp(thirds[i], op),
              }),
            settleT + i * WIN_SWEEP_MS,
          ),
        );
      };
      bt.push(
        setTimeout(() => {
          setStagedAlts((cur) => ({
            type: "FeatureCollection",
            features: withOp(cur.features, DROP_OP),
          }));
        }, settleT),
        ...winSweep(),
        setTimeout(
          () => setStagedSel(tintRef.current.selected),
          settleT + 2 * WIN_SWEEP_MS,
        ),
        setTimeout(
          () => setStagedAlts(tintRef.current.alts),
          settleT + ALT_SET_MS,
        ),
        /* the verdict pins just after the winner's full weight lands */
        setTimeout(flash, settleT + 2 * WIN_SWEEP_MS + PILL_DELAY_MS),
      );
    });
    // options identity marks the plan fetch; tint carries strips/selected
  }, [options, tint, reduceMotion, selected]);

  /* B — a tap-swap on the SAME option set: the new choice settles into
     its bold state with a short fade and the demoted route eases down
     into the alternatives — the swap reads as settle, not a jump-cut.
     The pill re-derives: a user pick that is neither cleanest nor
     fastest shows the server's own reason_line. */
  useEffect(() => {
    const prevSel = prevSelectedRef.current;
    if (prevSel === selected || prevSel == null) return;
    prevSelectedRef.current = selected;
    const demoted =
      typeof prevSel === "number"
        ? prevSel
        : options.findIndex((o) => o.route_id === prevSel);
    /* swap timers ride their own ref for the same reason the beat does:
       a strip landing mid-demote must not strand the swap half-eased */
    const st = swapTimers.current;
    for (const t of st) clearTimeout(t);
    st.length = 0;
    if (reduceMotion) {
      st.push(
        setTimeout(() => {
          setStagedAlts(tint.alts);
          setStagedSel(tint.selected);
        }, 0),
      );
      return;
    }
    st.push(
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
      setTimeout(() => {
        if (pillReady.current.text && pillReady.current.anchor) {
          setPillEpoch((e) => e + 1);
        }
      }, SELECT_FADE_MS),
    );
  }, [selected, tint, options, reduceMotion]);

  /* Sources + layers + the pill Marker stay mounted for the app's whole
    life: unmounting a GeoJSONSource/MarkerView issues removeSource/
    removeAnnotation on the native style, and when that lands mid-draw
    on the iOS-sim render thread it segfaults (upstream MapLibre class —
    hit here at receipt-Done/options-clear). Swapping data for an empty
    FeatureCollection — or an invisible <View/> child — never removes
    anything, draws nothing, and costs one no-op native call. */
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
      {/* the frame act's endpoint rings — parked at the real pins (or
          the route's snapped ends), always mounted; the child swaps to
          the pulsing ring only while a beat fires it (same annotation-
          content pattern as the endpoint pins / the pill below). */}
      <Marker lngLat={endCoords.from ?? DELHI} anchor="center">
        {ringFromEpoch > 0 ? (
          <Animated.View
            pointerEvents="none"
            style={[
              st.ring,
              { borderColor: V2T.text },
              {
                opacity: ringFromV.interpolate({
                  inputRange: [0, 0.18, 1],
                  outputRange: [0, 0.55, 0],
                }),
                transform: [
                  {
                    scale: ringFromV.interpolate({
                      inputRange: [0, 1],
                      outputRange: [0.3, 2.2],
                    }),
                  },
                ],
              },
            ]}
          />
        ) : (
          <View />
        )}
      </Marker>
      <Marker lngLat={endCoords.to ?? DELHI} anchor="center">
        {ringToEpoch > 0 ? (
          <Animated.View
            pointerEvents="none"
            style={[
              st.ring,
              { borderColor: V2T.pinDest },
              {
                opacity: ringToV.interpolate({
                  inputRange: [0, 0.18, 1],
                  outputRange: [0, 0.55, 0],
                }),
                transform: [
                  {
                    scale: ringToV.interpolate({
                      inputRange: [0, 1],
                      outputRange: [0.3, 2.2],
                    }),
                  },
                ],
              },
            ]}
          />
        ) : (
          <View />
        )}
      </Marker>
      <Marker lngLat={anchor ?? DELHI} anchor="bottom">
        {line && anchor ? (
          <Animated.View
            pointerEvents="none"
            style={[
              st.pill,
              {
                opacity: pillV,
                transform: [
                  {
                    translateY: pillV.interpolate({
                      inputRange: [0, 1],
                      outputRange: [5, 0],
                    }),
                  },
                  {
                    scale: pillV.interpolate({
                      inputRange: [0, 1],
                      outputRange: [0.92, 1],
                    }),
                  },
                ],
              },
            ]}>
            {leafGlyph ? <Icon name="leaf" color={V2T.accent} size={12} /> : null}
            <Text style={[st.pillTxt, { fontFamily: fam(lang, "med") }]} numberOfLines={2}>
              {line}
            </Text>
          </Animated.View>
        ) : (
          <View />
        )}
      </Marker>
    </>
  );
}

const st = StyleSheet.create({
  /* the frame ring — a single breathing circle on each endpoint. 26 px
     at rest, expands ~2.2× while fading; a hairline-weight stroke keeps
     it on the paper register, no glow. */
  ring: {
    width: 26,
    height: 26,
    borderRadius: 13,
    borderWidth: 2,
    backgroundColor: "transparent",
  },
  /* the verdict pill — floating-chrome elevation over the map, warm
     surface, a hairline edge. Nothing under 11px (label = 13). */
  pill: {
    flexDirection: "row",
    alignItems: "center",
    gap: 5,
    backgroundColor: V2T.surface,
    borderRadius: V2Radius.pill,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: V2T.hairline,
    paddingHorizontal: 11,
    paddingVertical: 6,
    maxWidth: 230,
    marginBottom: 4,
    ...V2Elev.float,
  },
  pillTxt: {
    fontSize: 13,
    color: V2T.text,
    letterSpacing: -0.1,
  },
});

/** memoized: the parent re-renders every poll tick; these
 *  map children only earn a commit when their own props move */
export const RouteTintSource = React.memo(RouteTintSourceFn);

export default RouteTintSource;
