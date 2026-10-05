/** Live-trip chrome (doc 02 §S6): next-turn card, off-route pill,
 * the two live counters (smoke you breathe / smoke your ride puts out)
 * as one bottom instrument cluster + an ETA/distance-left footer.
 *
 * Consumes useNavEngine output via the optional `nav` prop; without it
 * the legacy props (option/steps/doseUg) still render a working chrome
 * so the pre-integration call site keeps compiling. Bands stay intact
 * in `nav` — the counters render the mid with "≈" per copy rules, and
 * the lo→hi spread shows as a thin band bar + a small range label under
 * each value. Maneuver arrows come from the shared set (icons.tsx —
 * Material Symbols turn/merge/ramp geometry). */
import React, { useEffect, useRef, useState } from "react";
import { Animated, Pressable, StyleSheet, Text, View } from "react-native";
import { NUM, V2Elev, V2Radius, V2T, V2Type, cigOf, fam, famMonoText } from "../../theme";
import { DYNAMIC_TYPE, useReduceMotion } from "../../a11y";
import { Icon, vehicleGlyph, type Glyph } from "../../icons";
import { approx, doseUgRound, t, type Lang } from "../../i18n/strings";
import { confirm, tap } from "../../haptics";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import type { Band } from "../../nav/strip";
import { isTransit } from "./types";
import type { CompareOption, Step } from "./types";

/** The slice of the engine the chrome needs (subset of useNavEngine's
 *  return — pass the whole object, it satisfies this shape). */
export type NavView = {
  dose: Band;            // µg inhaled
  co2: Band;             // kg put out
  pm25?: Band;           // g put out (banner detail only)
  etaS: number;
  distRemainingM: number;
  offRoute: boolean;
  stripOk?: boolean;       // false → /v2/strip failed, counters frozen
  outsideField?: boolean;  // true once reroute answers 'outside_service_area'
  running?: boolean;
  progress?: number;       // 0..1 along-route → cluster hairline
  nextStep?: {
    instruction: string;
    distM: number;                          // metres to the maneuver
    type?: string | null;                   // OSRM/transit type if carried
    modifier?: string | null;               // e.g. "slight left"
  } | null;
  snapped?: [number, number] | null;
};

const clock = (etaS: number) => {
  const d = new Date(Date.now() + Math.max(0, etaS) * 1000);
  return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
};

/** Trip-remaining km as a plain number string — the nav_left template
 *  already carries the "km" unit. 2dp below a kilometre keeps it honest
 *  (the old helper injected a literal " m" here → "350 m km left"). */
const kmNum = (m: number) =>
  m >= 950 ? (m / 1000).toFixed(1) : (Math.max(0, m) / 1000).toFixed(2);

/** Distance to the next maneuver — "350 m" / "1.2 km". */
const distToStr = (m: number, lang: Lang) =>
  m >= 950
    ? `${(m / 1000).toFixed(1)} ${t("unitsKm", lang)}`
    : `${Math.max(10, Math.round(m / 10) * 10)} m`;

/* ------------------------------------------------------------------ */
/* maneuver glyph                                                      */
/* ------------------------------------------------------------------ */

type Maneuver =
  | "left" | "right" | "slightLeft" | "slightRight" | "uturn"
  | "roundabout" | "merge" | "exit" | "straight"
  | "arrive" | "walk" | "transit" | "mode";

/** Steps carry only an English instruction sentence (+ optional OSRM
 *  type/modifier when a payload inlines them). Map words → maneuver.
 *  Server vocabulary (server/v2/deps.py): "Turn/Bear/Keep left|right …",
 *  "Make a U-turn", "At the roundabout, take the Nth exit", "Take the
 *  ramp/exit", "Merge", "Continue …", "Head out", "You'll arrive",
 *  transit legs "Take {line} …" / "Walk to …". */
function maneuverOf(
  instruction: string,
  type?: string | null,
  modifier?: string | null,
): Maneuver {
  const ty = (type ?? "").toLowerCase();
  const mod = (modifier ?? "").toLowerCase();
  const s = (instruction || "").toLowerCase();

  if (mod.includes("uturn") || ty === "uturn" || s.includes("u-turn")) return "uturn";
  if (ty === "arrive") return "arrive";
  if (ty === "roundabout" || ty === "rotary" || s.includes("roundabout")) return "roundabout";
  if (ty === "merge" || s.includes("merge")) return "merge";
  if (ty === "metro" || ty === "bus" || ty === "tram" || ty === "train") return "transit";
  if (ty === "walk" || ty === "transfer") return "walk";
  if (ty === "fork") {
    return mod.includes("left") ? "slightLeft" : mod.includes("right") ? "slightRight" : "straight";
  }
  if (mod) {
    if (mod.includes("left")) return mod.startsWith("slight") ? "slightLeft" : "left";
    if (mod.includes("right")) return mod.startsWith("slight") ? "slightRight" : "right";
    if (mod.includes("straight")) return "straight";
  }
  if (s.includes("arrive") || s.includes("destination")) return "arrive";
  if (s.includes("ramp") || s.includes("exit")) return "exit";
  if (s.includes("left")) {
    return s.includes("bear") || s.includes("keep") || s.includes("slight") ? "slightLeft" : "left";
  }
  if (s.includes("right")) {
    return s.includes("bear") || s.includes("keep") || s.includes("slight") ? "slightRight" : "right";
  }
  if (s.includes("walk")) return "walk";
  if (s.includes("metro") || s.includes("board") || s.includes("take the") || s.includes("take a")) {
    return "transit";
  }
  return "straight"; // head out / continue / unknown
}

/** Big glanceable maneuver glyph — every arrow comes from the shared set
 *  (Material Symbols turn/merge/ramp geometry), so nav directions and the
 *  rest of the chrome speak one icon language. */
const MANEUVER_GLYPH: Record<Exclude<Maneuver, "arrive" | "walk" | "transit" | "mode">, Glyph> = {
  left: "turnL",
  right: "turnR",
  slightLeft: "slightL",
  slightRight: "slightR",
  uturn: "uturn",
  roundabout: "roundabout",
  merge: "mergeDir",
  exit: "ramp",
  straight: "arrowUp",
};

function ManeuverIcon({ m, mode, size = 30 }: { m: Maneuver; mode?: string; size?: number }) {
  if (m === "arrive") return <Icon name="pin" color={V2T.pinDest} size={size - 2} filled />;
  if (m === "walk") return <Icon name="walk" color={V2T.text} size={size} />;
  if (m === "transit" || m === "mode") {
    return <Icon name={vehicleGlyph(mode ?? "")} color={V2T.text} size={size} />;
  }
  return <Icon name={MANEUVER_GLYPH[m]} color={V2T.text} size={size} />;
}

/* ------------------------------------------------------------------ */
/* counter cell — one channel of the instrument                        */
/* ------------------------------------------------------------------ */

type BandViz = { lo: number; mid: number; hi: number; text: string };

function CounterCell({
  icon, tint, label, value, band, dim, lang,
}: {
  icon: Glyph; tint: string; label: string; value: string;
  band: BandViz | null; dim?: boolean; lang: Lang;
}) {
  const span = band && band.hi > 0 ? band.hi : 0;
  const pct = (v: number) => (span > 0 ? Math.min(100, Math.max(0, (v / span) * 100)) : 0);
  return (
    <View style={[s.cell, dim && s.cellDim]}>
      <View style={s.cellHead}>
        <Icon name={icon} color={tint} size={14} />
        {/* long captions ("smoke your ride puts out") must shrink to fit,
            not ellipsize — 'PUTS…' read broken on 1080px (forensic find) */}
        <Text {...DYNAMIC_TYPE} style={[s.cellLbl, { fontFamily: fam(lang, "med") }]}
          numberOfLines={1} adjustsFontSizeToFit minimumFontScale={0.72}>
          {label}
        </Text>
      </View>
      <Text {...DYNAMIC_TYPE} style={[s.cellVal, NUM, { fontFamily: famMonoText(lang, "med") }]} numberOfLines={1}>
        {value}
      </Text>
      {band && span > 0 && (
        <View style={s.bandTrack} accessible={false} importantForAccessibility="no">
          {/* lo→hi as a slice of the band's own scale, mid tick on top */}
          <View style={[
            s.bandSeg,
            { left: `${pct(band.lo)}%`, width: `${Math.max(3, pct(band.hi) - pct(band.lo))}%`, backgroundColor: tint },
          ]} />
          <View style={[s.bandMid, { left: `${pct(band.mid)}%`, backgroundColor: V2T.text }]} />
        </View>
      )}
      {band && (
        <Text {...DYNAMIC_TYPE} style={[s.cellBand, NUM, { fontFamily: famMonoText(lang, "reg") }]} numberOfLines={1}>
          {band.text}
        </Text>
      )}
    </View>
  );
}

/* ------------------------------------------------------------------ */

export function NavChrome({
  option, steps, doseUg, onExit, lang, nav, onRecenter, showCig = false,
}: {
  option: CompareOption; steps: Step[] | null; doseUg: number;
  onExit: () => void; lang: Lang;
  nav?: NavView | null; onRecenter?: (() => void) | null;
  /** cigarette-equivalence framing — off by default (settings.show_cig) */
  showCig?: boolean;
}) {
  const insets = useSafeAreaInsets();
  const min = Math.max(0, Math.round((nav?.etaS ?? option.duration_min * 60) / 60));
  const leftM = nav?.distRemainingM ?? (option.distance_km ?? 0) * 1000;
  const next = nav?.nextStep ?? null;
  const step0 = steps?.[0] ?? null;
  const transit = isTransit(option);
  const banner = next?.instruction
    ?? step0?.instruction
    ?? (transit && option.stations
      ? t("boardMetro", lang, { a: option.stations.board, b: option.stations.alight })
          + (option.lines?.length ? `  ·  ${option.lines.join(", ")}` : "")
      : t("followRoute", lang));
  const maneuver: Maneuver = next
    ? maneuverOf(next.instruction, next.type, next.modifier)
    : step0
      ? maneuverOf(step0.instruction, step0.type)
      : transit ? "transit" : "mode";

  const cigs = nav ? cigOf(nav.dose.mid) : cigOf(doseUg);
  /* µg readout for the default surface (cigarette metaphor off) — the
     same live dose, rounded whole; "µg" is the plain unit everywhere */
  const ugMid = nav ? nav.dose.mid : doseUg;
  const showOut = nav != null && nav.co2.hi > 0;
  const outKg = showOut ? Math.round(Math.max(0, nav.co2.mid) * 10) / 10 : null; // kg, 1dp
  const frozen = nav?.stripOk === false; // counters paused — dimmed, pill explains
  const progress = typeof nav?.progress === "number"
    ? Math.min(1, Math.max(0, nav.progress)) : null;
  const mode = option.mode || option.vehicle;

  const meta = nav
    ? `${t("nav_left", lang, { min, km: kmNum(leftM) })} · ${t("arriveAt", lang, { t: clock(nav.etaS) })}`
    : `${Math.round(option.duration_min)} ${t("minUnit", lang)} · ${option.distance_km ?? 0} ${t("unitsKm", lang)} · ${t("arriveAt", lang, { t: clock(option.duration_min * 60) })}`;

  /* instruction swap: only the sentence/arrow change earns motion — the
     1 Hz distance tick under it must not re-animate the card. Fade+rise
     on `banner`/`maneuver` change, JS driver, off under reduce-motion. */
  const reduceMotion = useReduceMotion();
  const [swap] = useState(() => new Animated.Value(1));
  const [swapTy] = useState(() =>
    swap.interpolate({ inputRange: [0, 1], outputRange: [7, 0] }));
  const lastCue = useRef<string | null>(null);
  const cueKey = `${maneuver}|${banner}`;
  useEffect(() => {
    if (reduceMotion) { swap.setValue(1); return; }
    if (lastCue.current === cueKey) return;
    lastCue.current = cueKey;
    swap.setValue(0);
    Animated.timing(swap, { toValue: 1, duration: 160, useNativeDriver: false }).start();
  }, [cueKey, swap, reduceMotion]);

  const doseBand: BandViz | null = nav != null && nav.dose.hi > 0
    ? {
      ...nav.dose,
      // a band that rounds to the same integer prints as one number —
      // "0–0 µg" reads like a formatting bug to anyone glancing at it.
      // show_cig appends the equivalence to this sub-line — secondary,
      // never the counter's own number
      text: (() => {
        const lo = Math.round(Math.max(0, nav.dose.lo)); const hi = Math.round(Math.max(0, nav.dose.hi));
        const base = lo === hi ? `${lo} µg` : `${lo}–${hi} µg`;
        return showCig && cigs != null
          ? `${base} · ${t("nav_cigs", lang, { n: approx(cigs > 0 && cigs < 0.01 ? 0.01 : cigs) })}`
          : base;
      })(),
    }
    : null;
  const co2Band: BandViz | null = showOut
    ? { ...nav.co2, text: nav.co2.lo.toFixed(1) === nav.co2.hi.toFixed(1) ? `${nav.co2.lo.toFixed(1)} kg` : `${nav.co2.lo.toFixed(1)}–${nav.co2.hi.toFixed(1)} kg` }
    : null;

  return (
    <>
      {/* next-turn card — glance: arrow, distance, then the sentence */}
      <View style={[s.banner, { top: insets.top + 12 }]}>
        <Animated.View style={[s.tile, { opacity: swap, transform: [{ translateY: swapTy }] }]} accessible={false}
          accessibilityElementsHidden importantForAccessibility="no-hide-descendants">
          <ManeuverIcon m={maneuver} mode={mode} />
        </Animated.View>
        <Animated.View style={[s.bannerTxt, { opacity: swap, transform: [{ translateY: swapTy }] }]}>
          {next && (
            <Text {...DYNAMIC_TYPE} style={[s.dist, NUM, { fontFamily: famMonoText(lang, "semi") }]} numberOfLines={1}>
              {distToStr(next.distM, lang)}
            </Text>
          )}
          <Text {...DYNAMIC_TYPE}
            style={[next ? s.instrNext : s.instr, { fontFamily: fam(lang, next ? "med" : "semi") }]}
            numberOfLines={2}>
            {banner}
          </Text>
        </Animated.View>
        {onRecenter && (
          <Pressable onPress={() => { tap(); onRecenter(); }} hitSlop={6}
            accessibilityRole="button" accessibilityLabel={t("nav_recenter", lang)}
            style={({ pressed }) => [s.act, pressed && s.actDown]}>
            <Icon name="locate" color={V2T.text2} size={20} />
          </Pressable>
        )}
        <Pressable onPress={() => { confirm(); onExit(); }} hitSlop={6}
          accessibilityRole="button" accessibilityLabel={t("end", lang)}
          style={({ pressed }) => [s.act, pressed && s.actDown]}>
          <Icon name="close" color={V2T.text2} size={20} />
        </Pressable>
      </View>

      {/* reroute in flight — warm dot says "working", not alarm */}
      {nav?.offRoute && (
        <View style={[s.pill, { top: insets.top + 92 }]}>
          <View style={s.pillDot} />
          <Text {...DYNAMIC_TYPE} style={[s.pillTxt, { fontFamily: fam(lang, "med"), color: V2T.text }]}>
            {t("findingNewWay", lang)}
          </Text>
        </View>
      )}
      {/* left the dose field entirely — reroute answered the typed
          outside code; one persistent honest pill (reuses the search
          string: dose can't be estimated out there) */}
      {nav?.outsideField && !nav.offRoute && (
        <View style={[s.pill, { top: insets.top + 92 }]}>
          <Icon name="pin" color={V2T.text3} size={13} />
          <Text {...DYNAMIC_TYPE} style={[s.pillTxt, { fontFamily: fam(lang, "med"), marginLeft: 6 }]}>
            {t("outsideDelhi", lang)}
          </Text>
        </View>
      )}
      {nav?.stripOk === false && !nav.offRoute && !nav.outsideField && (
        <View style={[s.pill, { top: insets.top + 92 }]}>
          <Text {...DYNAMIC_TYPE} style={[s.pillTxt, { fontFamily: fam(lang, "med") }]}>
            {t("strip_unavailable", lang)}
          </Text>
        </View>
      )}

      {/* instrument cluster — the two signature counters + trip meta */}
      <View style={[s.cluster, { bottom: insets.bottom + 12 }]}>
        {progress != null && progress > 0 && (
          <View style={s.progTrack} accessible={false} importantForAccessibility="no">
            <View style={[s.progFill, { width: `${progress * 100}%` }]} />
          </View>
        )}
        <View style={s.cells}>
          <CounterCell
            lang={lang}
            icon="dust"
            tint={V2T.breath1}
            label={t("nav_breathe", lang)}
            dim={frozen}
            band={doseBand}
            value={ugMid == null ? t("nav_noSignal", lang)
              : t("doseUg", lang, { n: approx(doseUgRound(ugMid)) })} />
          {showOut && outKg != null && (
            <>
              <View style={s.cellDiv} />
              <CounterCell
                lang={lang}
                icon="smoke"
                tint={V2T.out1}
                label={t("nav_putOut", lang)}
                dim={frozen}
                band={co2Band}
                value={t("nav_kg", lang, { n: approx(outKg) })} />
            </>
          )}
        </View>
        <View style={s.metaRow}>
          <Text {...DYNAMIC_TYPE}
            style={[s.metaTxt, NUM, { fontFamily: famMonoText(lang, "reg") }]}
            numberOfLines={1} adjustsFontSizeToFit minimumFontScale={0.8}>
            {meta}
          </Text>
        </View>
      </View>
    </>
  );
}

const s = StyleSheet.create({
  banner: {
    position: "absolute", left: 12, right: 12,
    flexDirection: "row", alignItems: "center",
    backgroundColor: V2T.glass, borderRadius: V2Radius.card,
    paddingVertical: 10, paddingHorizontal: 12,
    ...V2Elev.float,
    borderWidth: 1, borderColor: V2T.glassLine,
  },
  tile: {
    width: 52, height: 52, borderRadius: V2Radius.row + 2,
    backgroundColor: V2T.glassSoft, borderWidth: 1, borderColor: V2T.glassLine,
    alignItems: "center", justifyContent: "center",
  },
  bannerTxt: { flex: 1, marginLeft: 12, marginRight: 4 },
  dist: { fontSize: V2Type.title, color: V2T.text },
  instr: { fontSize: V2Type.body, color: V2T.text },
  instrNext: { fontSize: V2Type.secondary, color: V2T.text2, marginTop: 1 },
  act: {
    minWidth: 44, minHeight: 44, marginLeft: 2,
    alignItems: "center", justifyContent: "center",
  },
  actDown: { opacity: 0.55 },

  pill: {
    position: "absolute", alignSelf: "center",
    flexDirection: "row", alignItems: "center",
    backgroundColor: V2T.glassFaint, borderRadius: V2Radius.row,
    paddingHorizontal: 14, paddingVertical: 8,
    ...V2Elev.card,
    borderWidth: 1, borderColor: V2T.glassLine,
  },
  pillDot: {
    width: 7, height: 7, borderRadius: 4,
    backgroundColor: V2T.breath1, marginRight: 8,
  },
  pillTxt: { fontSize: V2Type.label, color: V2T.text2 },

  cluster: {
    position: "absolute", left: 14, right: 14,
    backgroundColor: V2T.glass, borderRadius: V2Radius.card,
    ...V2Elev.float,
    borderWidth: 1, borderColor: V2T.glassLine, overflow: "hidden",
  },
  progTrack: { height: 3, backgroundColor: V2T.glassSoft },
  progFill: {
    height: 3, backgroundColor: V2T.accent,   // echoes the route line colour
    borderTopRightRadius: 2, borderBottomRightRadius: 2,
  },
  cells: { flexDirection: "row" },
  cell: { flex: 1, paddingHorizontal: 14, paddingVertical: 10 },
  cellDim: { opacity: 0.5 },
  cellDiv: { width: 1, backgroundColor: V2T.line, marginVertical: 10 },
  cellHead: { flexDirection: "row", alignItems: "center" },
  cellLbl: {
    fontSize: 10, color: V2T.text3, marginLeft: 6, flexShrink: 1,
    letterSpacing: 0.5, textTransform: "uppercase",
  },
  cellVal: { fontSize: V2Type.body, color: V2T.text, marginTop: 4 },
  bandTrack: {
    height: 3, borderRadius: 2, marginTop: 7,
    backgroundColor: V2T.glassSoft, overflow: "visible",
  },
  bandSeg: { position: "absolute", top: 0, bottom: 0, borderRadius: 2, opacity: 0.5 },
  bandMid: {
    position: "absolute", top: -1, width: 3, height: 5,
    marginLeft: -1.5, borderRadius: 1.5,
  },
  cellBand: { fontSize: 10, color: V2T.text3, marginTop: 5 },
  metaRow: {
    borderTopWidth: 1, borderTopColor: V2T.line,
    paddingVertical: 8, paddingHorizontal: 14,
  },
  metaTxt: { fontSize: V2Type.label, color: V2T.text3, textAlign: "center" },
});
