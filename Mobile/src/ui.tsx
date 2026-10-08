/** Alive component primitives — v2 light design system (docs/plan/03).
 * Sheets: surface + 1px line top edge, spring (damping 22, stiffness 220),
 * 3 detents (peek 15% · half 50% · full 92%). */
import React, { useEffect, useMemo, useRef, useState } from "react";
import {
  Animated, Dimensions, Easing, PanResponder, Pressable, StyleSheet, Text, View,
  type StyleProp, type TextStyle, type ViewStyle,
} from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { F, FMONO, NUM, V2Elev, V2Radius, V2T, V2Type, fam, famMonoText, famSerif } from "./theme";
import { Icon, vehicleGlyph, type Glyph } from "./icons";
import { t, type Lang } from "./i18n/strings";
import { DYNAMIC_TYPE, useReduceMotion } from "./a11y";
import { tick } from "./haptics";
import { jank } from "./perf";

const WIN_H = () => Dimensions.get("window").height;

/** Selected-row tint — accent-tint glass (milky morphism, Oct '26). */

/** AlertBanner severities — flat washes keyed to the register (sage for
 *  plain info; the CPCB ramp where the tone carries data weight). Borders
 *  stay hairline; colour is the only signal. */
const ALERT_SEV = {
  info:   { glyph: "info" as Glyph, color: V2T.accentInk, bg: V2T.accentWash, border: V2T.hairline },
  warn:   { glyph: "warn" as Glyph, color: V2T.breath1,  bg: "rgba(213,140,74,0.10)", border: V2T.hairline },
  danger: { glyph: "warn" as Glyph, color: V2T.pinDest, bg: "rgba(184,84,66,0.10)", border: V2T.hairline },
} as const;

/** Press feedback — the register's one press gesture: a hair of scale
 *  + a soft fade (Uber's 0.98 made quiet for paper). Spread into any
 *  Pressable's style callback: `[base, pressFx(pressed)]`. */
export const pressFx = (pressed: boolean): ViewStyle | null =>
  pressed ? { opacity: 0.78, transform: [{ scale: 0.985 }] } : null;

/** Mount-in motion — a short fade + 10px rise. `delay` staggers card
 *  stacks so a sheet's children arrive, not pop. Native driver: a single
 *  value feeding opacity + translateY through one interpolate — the RN 0.86
 *  native-detach class needs a mixed graph (Sheet's Animated.add), absent
 *  here. */
export function FadeIn({ delay = 0, children, style }: {
  delay?: number; children: React.ReactNode; style?: StyleProp<ViewStyle>;
}) {
  const reduceMotion = useReduceMotion();
  const [v] = useState(() => new Animated.Value(reduceMotion ? 1 : 0));
  const [ty] = useState(() => v.interpolate({ inputRange: [0, 1], outputRange: [10, 0] }));
  useEffect(() => {
    if (reduceMotion) { v.setValue(1); return; }
    Animated.timing(v, {
      toValue: 1, duration: 260, delay, easing: Easing.out(Easing.quad),
      useNativeDriver: true,
    }).start();
  }, [v, delay, reduceMotion]);
  return (
    <Animated.View style={[style, { opacity: v, transform: [{ translateY: ty }] }]}>
      {children}
    </Animated.View>
  );
}

/** The score-reveal moment — a number that counts up to its value when
 *  the surface mounts (Oura's ring-tick). ~36 frames on one Text node,
 *  JS-driven, silenced under reduce-motion. */
/** The soul of the register: a tinted card's edge breathes — a 4.4s
 *  sine opacity loop on a band-ink border ring (0.12→0.32). Subtle
 *  enough to be felt not watched; the only ambient motion on a
 *  surface, and it means something — a dosimeter is a breathing
 *  thing. Skipped under Reduce Motion. Mount inside any rounded
 *  tinted card (borderRadius 24). */
export function BreathEdge({ color, radius = 24 }: { color: string; radius?: number }) {
  const reduce = useReduceMotion();
  const [v] = useState(() => new Animated.Value(0));
  useEffect(() => {
    if (reduce) return;
    const loop = Animated.loop(
      Animated.sequence([
        Animated.timing(v, { toValue: 1, duration: 2200, easing: Easing.inOut(Easing.sin), useNativeDriver: true }),
        Animated.timing(v, { toValue: 0, duration: 2200, easing: Easing.inOut(Easing.sin), useNativeDriver: true }),
      ]));
    loop.start();
    return () => loop.stop();
  }, [v, reduce]);
  if (reduce) return null;
  /* design-v4: the breath is light, not a line — the band's own ink
     swells through the whole field (0→7%) and settles, like a held
     breath. No outline ever rings the hero. */
  return (
    <Animated.View pointerEvents="none"
      style={[StyleSheet.absoluteFill, {
        borderRadius: radius, backgroundColor: color,
        opacity: v.interpolate({ inputRange: [0, 1], outputRange: [0, 0.07] }),
      }]} />
  );
}

export function CountUp({ value, format, style, duration = 620, ...rest }: {
  value: number; format?: (n: number) => string; duration?: number;
  /* animated-capable style: the hero inks the numeral through an
     interpolation so a band change cross-fades instead of snapping —
     needs Animated.Text below, plain Text can't take animated values */
  style?: Animated.WithAnimatedValue<StyleProp<TextStyle>>; [k: string]: unknown;
}) {
  const reduceMotion = useReduceMotion();
  /* mount paints the real number — a count-up is a CHANGE indicator,
     not a reveal: while the JS thread is starved the rAF loop can't
     run, and the initial "0" sat as a false reading ~25–60 s on
     offline cold start and every plan option card (e2e-sweep P1-1:
     "real user could read 'no dose' on a 78 µg day"). The tick still
     animates every live update — the dose accreting is the marquee a
     count-up was always meant to be. `cur` mirrors what's actually on
     screen so a value change mid-sweep continues from the shown
     number, never snaps back to a settled value it already left; the
     reduce branch deliberately leaves it alone so `disp` can never go
     stale — every setDisp lives inside the rAF frame. */
  const [disp, setDisp] = useState(value);
  const cur = useRef(value);
  useEffect(() => {
    if (reduceMotion) return;
    const from = cur.current;
    if (from === value) return;
    const t0 = Date.now();
    let raf = 0;
    const step = () => {
      const p = Math.min(1, (Date.now() - t0) / duration);
      const e = 1 - Math.pow(1 - p, 3);
      const n = from + (value - from) * e;
      cur.current = n;
      setDisp(n);
      if (p < 1) raf = requestAnimationFrame(step);
    };
    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }, [value, duration, reduceMotion]);
  /* reduce-motion skips the whole sweep — the final value renders
     statically, no ticking state at all */
  const shown = reduceMotion ? value : disp;
  return <Animated.Text style={style} {...rest}>{format ? format(shown) : `${Math.round(shown)}`}</Animated.Text>;
}

/** Honest-but-designed empty state: a hairline ring holding the glyph,
 *  a serif line, a muted sub — quiet instead of bare. */
export function Quiet({ glyph, title, sub, lang = "en" }: {
  glyph: Glyph; title: string; sub?: string; lang?: Lang;
}) {
  return (
    <View style={us.quiet}>
      <View style={us.quietRing}>
        <Icon name={glyph} color={V2T.text3} size={20} />
      </View>
      <Text {...DYNAMIC_TYPE} style={[us.quietTitle, { fontFamily: famSerif(lang, "med") }]}>
        {title}
      </Text>
      {sub ? (
        <Text {...DYNAMIC_TYPE} style={[us.quietSub, { fontFamily: fam(lang, "reg") }]}>
          {sub}
        </Text>
      ) : null}
    </View>
  );
}

/** Bottom sheet — grabber + optional X. Milk pane: translucent white +
 *  sheen top edge + a real shadow lift; the map ghosts through the frost. */
export function Sheet({
  detent = "peek", onClose, children, style, lang = "en",
}: {
  detent?: "peek" | "half" | "full";
  onClose?: () => void;
  lang?: Lang;
  children: React.ReactNode;
  style?: StyleProp<ViewStyle>;
}) {
  const h = detent === "peek" ? WIN_H() * 0.15 : detent === "half" ? WIN_H() * 0.5 : WIN_H() * 0.92;
  const insets = useSafeAreaInsets();
  const [anim] = useState(() => new Animated.Value(0));
  /* interpolation must be a stable node across renders — creating it inline
     makes RN 0.86's animated-props hook detach the swapped node and throw
     `undefined is not a function` on sheet close (reproduced live). */
  const [ty] = useState(() => anim.interpolate({ inputRange: [0, 1], outputRange: [60, 0] }));
  /* grabber drag-to-dismiss — Google-Maps-grade sheet affordance: the
     handle is the gesture surface; a downward pan follows the finger and
     either flings closed (>90 px or fast) or springs back. JS driver —
     same RN 0.86 native-detach guard as the enter spring. */
  const [drag] = useState(() => new Animated.Value(0));
  const [slide] = useState(() => Animated.add(ty, drag));
  const pan = useMemo(() => {
    if (!onClose) return null;
    return PanResponder.create({
      onMoveShouldSetPanResponder: (_e, g) => { jank("sheet.drag"); return g.dy > 6 && Math.abs(g.dy) > Math.abs(g.dx); },
      onPanResponderMove: (_e, g) => drag.setValue(Math.max(0, g.dy)),
      onPanResponderRelease: (_e, g) => {
        if (g.dy > 90 || g.vy > 0.6) {
          Animated.timing(drag, {
            toValue: WIN_H(), duration: 170, useNativeDriver: false,
          }).start(onClose);
        } else {
          Animated.spring(drag, { toValue: 0, damping: 22, stiffness: 220, useNativeDriver: false }).start();
        }
      },
      onPanResponderTerminate: () =>
        Animated.spring(drag, { toValue: 0, damping: 22, stiffness: 220, useNativeDriver: false }).start(),
    });
  }, [drag, onClose]);
  /* touches are dead until the enter spring lands — a tap mid-flight
     hits whatever child is under the finger at that translateY, not the
     one it aimed at (testday-ios: a compare option tap logged "bus" for
     the card that slid away). The veil EATS the touch (topmost hit, no
     responder) instead of letting it fall through to the map. */
  const [settled, setSettled] = useState(false);
  useEffect(() => {
    /* useNativeDriver must stay false here: RN 0.86's createAnimatedPropsHook
       throws `undefined is not a function` inside its queueMicrotask detach /
       mixed native-graph path (reproduced live on the search sheet). A 60 px
       one-shot enter doesn't need the native driver anyway. */
    jank("enter.sheet");
    Animated.spring(anim, { toValue: 1, damping: 22, stiffness: 220, useNativeDriver: false })
      .start(() => setSettled(true));
  }, [anim]);
  return (
    <Animated.View
      style={[us.sheet, {
        maxHeight: Math.max(96, h),
        // gesture-nav pill / home indicator must never sit on sheet content
        paddingBottom: insets.bottom,
        transform: [{ translateY: slide }],
      }, style]}
    >
      <View style={us.grabberRow} {...(pan?.panHandlers ?? {})}>
        <View style={us.grabber} />
        {onClose && (
          <Pressable onPress={onClose} hitSlop={14} accessibilityRole="button"
            accessibilityLabel={t("settingsClose", lang)}
            style={({ pressed }) => [us.sheetX, pressed && { opacity: 0.55 }]}>
            <Icon name="close" color={V2T.text3} size={16} />
          </Pressable>
        )}
      </View>
      {children}
      {!settled && <View style={us.enterVeil} pointerEvents="auto" />}
    </Animated.View>
  );
}

/** 4-step smoke bar — relative within this trip, no units (doc 02 §S4).
 *  tone "breath" = warm ramp (smoke you breathe); tone "out" = cool greys
 *  (smoke your ride puts out). Brighter = heavier; absence reads as light. */
export function SmokeBar({ frac, color, tone = "breath", label }: {
  frac: number; color?: string; tone?: "breath" | "out"; label?: string;
}) {
  const f = Math.max(0, Math.min(1, frac));
  const lit = f <= 0 ? 0 : Math.max(1, Math.ceil(f * 4));
  const c = color ?? (tone === "out"
    ? (f > 0.66 ? V2T.out1 : f > 0.33 ? V2T.out2 : V2T.out3)
    : (f > 0.66 ? V2T.breath3 : f > 0.33 ? V2T.breath2 : V2T.breath1));
  return (
    <View style={us.segRow} accessibilityLabel={label}>
      {[0, 1, 2, 3].map((i) => (
        <View key={i} style={[us.seg, { backgroundColor: i < lit ? c : V2T.line }]} />
      ))}
    </View>
  );
}

/** Mode row (doc 02 §S4): mode icon | label + meta + reason | ETA |
 *  two stacked 4-step bars — in (dose) over out (emissions), relative
 *  within this trip, no units. Tag chips come from the server; a
 *  recommended row without a split tag still reads as picked. */
export function ModeRow({
  vehicle, label, etaMin, meta, inFrac, outFrac, tag, recommended, reasonLine,
  selected, onPress, onLongPress, lang = "en",
}: {
  vehicle: string; label: string; etaMin: number; meta?: string;
  inFrac: number | null; outFrac?: number | null; tag?: string;
  recommended?: boolean; reasonLine?: string; selected: boolean;
  onPress: () => void; onLongPress?: () => void; lang?: Lang;
}) {
  return (
    <Pressable onPress={onPress} onLongPress={onLongPress} delayLongPress={420}
      style={({ pressed }) => [us.modeRow, pressFx(pressed), selected && us.modeRowSel]}
      accessibilityRole="button" accessibilityState={{ selected }}>
      <Icon name={vehicleGlyph(vehicle)} color={selected ? V2T.accent : V2T.text2} size={30} filled={selected} />
      <View style={{ flex: 1, marginLeft: 12 }}>
        <View style={{ flexDirection: "row", alignItems: "baseline" }}>
          <Text style={[us.modeLabel, { fontFamily: fam(lang, "med") }]} numberOfLines={1} {...DYNAMIC_TYPE}>{label}</Text>
          {tag ? <Text style={[us.bestTag, { fontFamily: fam(lang, "med") }]} {...DYNAMIC_TYPE}>{tag}</Text> : null}
          {!tag && recommended ? <Text style={[us.bestTag, { fontFamily: fam(lang, "med") }]} {...DYNAMIC_TYPE}>{t("compare_pick", lang)}</Text> : null}
        </View>
        {meta ? <Text style={[us.modeMeta, { fontFamily: fam(lang, "reg") }]} numberOfLines={1} {...DYNAMIC_TYPE}>{meta}</Text> : null}
        {reasonLine ? <Text style={[us.modeReason, { fontFamily: fam(lang, "reg") }]} numberOfLines={2} {...DYNAMIC_TYPE}>{reasonLine}</Text> : null}
      </View>
      <View style={{ alignItems: "flex-end" }}>
        <Text style={[us.modeEta, NUM, { fontFamily: famMonoText(lang, "semi") }]} {...DYNAMIC_TYPE}>
          {etaMin}<Text style={[us.modeEtaUnit, { fontFamily: famMonoText(lang, "reg") }]} {...DYNAMIC_TYPE}> {t("minUnit", lang)}</Text>
        </Text>
        {inFrac != null && (
          <SmokeBar frac={inFrac} tone="breath" label={t("compare_smokeIn", lang)} />
        )}
        {outFrac != null && (
          <SmokeBar frac={outFrac} tone="out" label={t("compare_smokeOut", lang)} />
        )}
      </View>
    </Pressable>
  );
}

/** Endpoint pins: origin = white ring, destination = red pinlet (doc 03).
 *  The pin DROPS onto the map when it mounts — the first beat of the
 *  chooser's from → to frame: the origin ring pops in, then the
 *  destination pinlet lands a hair later (the map "placing" the trip's
 *  two ends). Reduce-motion renders them static. */
export function EndpointPin({ kind }: { kind: "origin" | "dest" }) {
  const reduceMotion = useReduceMotion();
  /* lazy-useState pattern (refs in render are a lint error) — one value
     drives scale + drop + fade in a single spring */
  const [v] = useState(() => new Animated.Value(reduceMotion ? 1 : 0));
  useEffect(() => {
    if (reduceMotion) { v.setValue(1); return; }
    Animated.spring(v, {
      toValue: 1,
      /* a soft arrival — lands and settles without a rubbery bounce */
      damping: 16,
      stiffness: 210,
      mass: 0.75,
      /* the destination lands a beat after the origin: from → to */
      delay: kind === "dest" ? 110 : 0,
      useNativeDriver: false,
    }).start();
  }, [v, kind, reduceMotion]);
  if (kind === "origin") {
    return (
      <Animated.View
        style={[
          us.originPin,
          {
            opacity: v,
            transform: [
              {
                scale: v.interpolate({
                  inputRange: [0, 1],
                  outputRange: [0.4, 1],
                }),
              },
            ],
          },
        ]}>
        <View style={us.originDot} />
      </Animated.View>
    );
  }
  return (
    <Animated.View
      style={{
        opacity: v,
        transform: [
          {
            translateY: v.interpolate({
              inputRange: [0, 1],
              outputRange: [-15, 0],
            }),
          },
          {
            scale: v.interpolate({
              inputRange: [0, 1],
              outputRange: [0.65, 1],
            }),
          },
        ],
      }}>
      <Icon name="pin" color={V2T.pinDest} size={32} filled />
    </Animated.View>
  );
}

/** Round floating map control — one shadow level (doc 03 §elevation). */
export function MapButton({
  glyph, onPress, active, label, filled,
}: {
  glyph: "locate" | "layers"; onPress: () => void; active?: boolean;
  label?: string; filled?: boolean;
}) {
  return (
    <Pressable onPress={() => { tick(); onPress(); }} hitSlop={8} accessibilityRole="button" accessibilityLabel={label}
      style={({ pressed }) => [us.mapBtn, active && us.mapBtnOn, pressed && { opacity: 0.75, transform: [{ scale: 0.9 }] }]}>
      {/* active = accent puck → the glyph must go light (V2T.bg ≈7:1 on
          accent); ink-on-accent was the dark-theme leftover */}
      <Icon name={glyph} color={active ? V2T.bg : V2T.text2} size={22} filled={filled ?? active} />
    </Pressable>
  );
}

/** Small banner strip — hazard-grade events. severity: info (accent) /
 *  warn (breath1) / danger (pinDest) — solid tinted fill, muted tone border,
 *  leading severity glyph. `lang` keeps the close button labelled. */
export function AlertBanner({ text, onClose, lang = "en", severity = "info" }: {
  text: string; onClose?: () => void; lang?: Lang;
  severity?: "info" | "warn" | "danger";
}) {
  const sev = ALERT_SEV[severity];
  return (
    <View style={[us.alert, { backgroundColor: sev.bg, borderColor: sev.border }]}
      accessibilityRole="alert">
      <Icon name={sev.glyph} color={sev.color} size={15} />
      <Text style={[us.alertTxt, { fontFamily: fam(lang, "med") }]} numberOfLines={2} {...DYNAMIC_TYPE}>{text}</Text>
      {onClose && (
        <Pressable onPress={onClose} hitSlop={15} accessibilityRole="button"
          accessibilityLabel={t("settingsClose", lang)}
          style={({ pressed }) => [pressed && { opacity: 0.55 }]}>
          <Icon name="close" color={V2T.text2} size={14} />
        </Pressable>
      )}
    </View>
  );
}

const us = StyleSheet.create({
  sheet: {
    ...V2Elev.sheet,
    backgroundColor: V2T.glass, borderTopLeftRadius: V2Radius.sheet, borderTopRightRadius: V2Radius.sheet,
    borderCurve: "continuous",
    overflow: "hidden",
  },
  /* the X must fit INSIDE the row — 24px control at top:4 overflows a
     19px row and lands on the first card's dose numeral (android audit
     #6). 8 + grabber 5 + 15 = 28px reserves it. */
  grabberRow: { alignItems: "center", paddingTop: 8, paddingBottom: 15 },
  grabber: { width: 40, height: 5, borderRadius: 2.5, backgroundColor: V2T.out3 },
  sheetX: { position: "absolute", right: 14, top: 4, padding: 4 },
  /* entry gate — invisible, swallows touches until the spring settles */
  enterVeil: { position: "absolute", top: 0, right: 0, bottom: 0, left: 0 },

  /* rows in the sheet's 16px rhythm — inner frost tiles on the milk pane */
  modeRow: {
    flexDirection: "row", alignItems: "center",
    marginHorizontal: 16, marginVertical: 4,
    paddingVertical: 11, paddingHorizontal: 14, minHeight: 56,
    backgroundColor: V2T.surface2, borderRadius: V2Radius.row, borderCurve: "continuous",
  },
  modeRowSel: { backgroundColor: V2T.surface, ...V2Elev.card },
  modeLabel: { fontFamily: F.med, fontSize: V2Type.body, color: V2T.text, flexShrink: 1 },
  bestTag: { fontFamily: F.med, fontSize: V2Type.label, color: V2T.accent, marginLeft: 8 },
  modeMeta: { fontFamily: F.reg, fontSize: V2Type.label, color: V2T.text3, marginTop: 1 },
  modeReason: { fontFamily: F.reg, fontSize: V2Type.label, color: V2T.text3, marginTop: 3 },
  modeEta: { fontFamily: FMONO.semi, fontSize: V2Type.body, color: V2T.text },
  modeEtaUnit: { fontFamily: FMONO.reg, fontSize: V2Type.micro, color: V2T.text2 },
  segRow: { flexDirection: "row", gap: 3, marginTop: 5 },
  seg: { width: 10, height: 4, borderRadius: 2 },



  originPin: {
    width: 20, height: 20, borderRadius: 10, backgroundColor: V2T.bg,
    borderWidth: 2.5, borderColor: V2T.text, alignItems: "center", justifyContent: "center",
  },
  originDot: { width: 7, height: 7, borderRadius: 3.5, backgroundColor: V2T.accent },

  mapBtn: {
    ...V2Elev.float,
    width: 46, height: 46, borderRadius: 23, backgroundColor: V2T.glassFaint,
    alignItems: "center", justifyContent: "center",
  },
  mapBtnOn: { backgroundColor: V2T.accent, borderColor: V2T.accent },

  alert: {
    flexDirection: "row", alignItems: "center", backgroundColor: V2T.surface2,
    paddingHorizontal: 12, paddingVertical: 9, borderRadius: V2Radius.row,
    borderCurve: "continuous", gap: 8,
  },
  alertTxt: { flex: 1, fontFamily: F.med, fontSize: V2Type.label, color: V2T.text },

  /* Quiet — the designed empty state */
  quiet: { alignItems: "center", paddingVertical: 22, paddingHorizontal: 20 },
  quietRing: {
    width: 52, height: 52, borderRadius: 26,
    backgroundColor: V2T.surface2,
    alignItems: "center", justifyContent: "center",
    marginBottom: 10,
  },
  quietTitle: { fontSize: V2Type.secondary, color: V2T.text, textAlign: "center" },
  quietSub: { fontSize: V2Type.label, color: V2T.text3, marginTop: 4, textAlign: "center", lineHeight: 18 },
});
