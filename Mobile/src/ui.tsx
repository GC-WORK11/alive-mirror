/** ALive-108 component primitives — v2 light design system (docs/plan/03).
 * Sheets: surface + 1px line top edge, spring (damping 22, stiffness 220),
 * 3 detents (peek 15% · half 50% · full 92%). */
import React, { useEffect, useState } from "react";
import {
  Animated, Dimensions, Pressable, StyleSheet, Text, View,
  type StyleProp, type ViewStyle,
} from "react-native";
import { CIG_UG, F, NUM, V2Radius, V2T, V2Type } from "./theme";
import { Icon, vehicleGlyph, type Glyph } from "./icons";
import { t, type Lang } from "./i18n/strings";
import { DYNAMIC_TYPE } from "./a11y";

const WIN_H = () => Dimensions.get("window").height;

/** Solid "accent wash" — accent composited 14% over surface2. No rgba surface
 *  fills: every card/row in the kit is opaque so the map never ghosts through. */
const SEL_TINT = V2T.accentTint;

/** AlertBanner severities — solid light fills + muted borders. */
const ALERT_SEV = {
  info:   { glyph: "info" as Glyph, color: V2T.accent,  bg: V2T.accentWash, border: "#A9BEF2" },
  warn:   { glyph: "warn" as Glyph, color: V2T.breath1, bg: "#FBF0DA", border: "#D9B468" },
  danger: { glyph: "warn" as Glyph, color: V2T.pinDest, bg: "#FBEAEA", border: "#DFA0A2" },
} as const;

/** Bottom sheet — grabber + optional X. Solid white surface, hairline top edge. */
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
  const [anim] = useState(() => new Animated.Value(0));
  useEffect(() => {
    Animated.spring(anim, { toValue: 1, damping: 22, stiffness: 220, useNativeDriver: true }).start();
  }, [anim]);
  return (
    <Animated.View
      style={[us.sheet, {
        maxHeight: Math.max(96, h),
        transform: [{ translateY: anim.interpolate({ inputRange: [0, 1], outputRange: [60, 0] }) }],
      }, style]}
    >
      <View style={us.grabberRow}>
        <View style={us.grabber} />
        {onClose && (
          <Pressable onPress={onClose} hitSlop={14} style={us.sheetX} accessibilityRole="button"
            accessibilityLabel={t("settingsClose", lang)}>
            <Icon name="close" color={V2T.text3} size={16} />
          </Pressable>
        )}
      </View>
      {children}
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
      style={({ pressed }) => [us.modeRow, pressed && { opacity: 0.55 }, selected && us.modeRowSel]}
      accessibilityRole="button" accessibilityState={{ selected }}>
      <Icon name={vehicleGlyph(vehicle)} color={selected ? V2T.accent : V2T.text2} size={30} filled={selected} />
      <View style={{ flex: 1, marginLeft: 12 }}>
        <View style={{ flexDirection: "row", alignItems: "baseline" }}>
          <Text style={us.modeLabel} numberOfLines={1} {...DYNAMIC_TYPE}>{label}</Text>
          {tag ? <Text style={us.bestTag} {...DYNAMIC_TYPE}>{tag}</Text> : null}
          {!tag && recommended ? <Text style={us.bestTag} {...DYNAMIC_TYPE}>{t("compare_pick", lang)}</Text> : null}
        </View>
        {meta ? <Text style={us.modeMeta} numberOfLines={1} {...DYNAMIC_TYPE}>{meta}</Text> : null}
        {reasonLine ? <Text style={us.modeReason} numberOfLines={2} {...DYNAMIC_TYPE}>{reasonLine}</Text> : null}
      </View>
      <View style={{ alignItems: "flex-end" }}>
        <Text style={[us.modeEta, NUM]} {...DYNAMIC_TYPE}>
          {etaMin}<Text style={us.modeEtaUnit} {...DYNAMIC_TYPE}> {t("minUnit", lang)}</Text>
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

/** Legacy dose bar — thin track, depth = dose vs cigarette budget. */
export function DoseBar({ frac, color }: { frac: number; color?: string }) {
  const c = color ?? V2T.text3;
  return (
    <View style={us.doseTrack}>
      <View style={[us.doseFill, { flex: Math.max(0.02, Math.min(1, frac)), backgroundColor: c }]} />
      <View style={{ flex: Math.max(0, 1 - frac) }} />
    </View>
  );
}

/** Cigarette strip: N glyphs, last one partially filled (receipt). */
export function CigStrip({ ug, size = 16, color = V2T.text, max = 7 }: {
  ug: number | null | undefined; size?: number; color?: string; max?: number;
}) {
  if (ug == null || ug <= 0) return null;
  const cigs = ug / CIG_UG;
  const full = Math.floor(cigs);
  const partial = cigs - full;
  const n = Math.min(max, Math.max(1, Math.ceil(cigs)));
  return (
    <View style={{ flexDirection: "row", alignItems: "center", gap: 3 }}>
      {Array.from({ length: n }).map((_, i) => (
        <View key={i} style={{ width: size, height: size }}>
          <Icon name="cigarette" color={i < full ? color : V2T.line} size={size} filled={i < full} />
          {i === full && partial > 0.05 && (
            <View style={{ position: "absolute", left: 0, top: 0, bottom: 0, width: size * partial, overflow: "hidden" }}>
              <Icon name="cigarette" color={color} size={size} filled />
            </View>
          )}
        </View>
      ))}
      {cigs > max && <Text style={[us.cigMore, NUM, { color }]} {...DYNAMIC_TYPE}>+{Math.round(cigs - max)}</Text>}
    </View>
  );
}

/** Endpoint pins: origin = white ring, destination = red pinlet (doc 03). */
export function EndpointPin({ kind }: { kind: "origin" | "dest" }) {
  if (kind === "origin") {
    return (
      <View style={us.originPin}>
        <View style={us.originDot} />
      </View>
    );
  }
  return <Icon name="pin" color={V2T.pinDest} size={32} filled />;
}

/** Round floating map control — one shadow level (doc 03 §elevation). */
export function MapButton({
  glyph, onPress, active, label, filled,
}: {
  glyph: "locate" | "layers"; onPress: () => void; active?: boolean;
  label?: string; filled?: boolean;
}) {
  return (
    <Pressable onPress={onPress} hitSlop={8} accessibilityRole="button" accessibilityLabel={label}
      style={({ pressed }) => [us.mapBtn, active && us.mapBtnOn, pressed && { opacity: 0.6 }]}>
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
      <Text style={us.alertTxt} numberOfLines={2} {...DYNAMIC_TYPE}>{text}</Text>
      {onClose && (
        <Pressable onPress={onClose} hitSlop={15} accessibilityRole="button"
          accessibilityLabel={t("settingsClose", lang)}>
          <Icon name="close" color={V2T.text2} size={14} />
        </Pressable>
      )}
    </View>
  );
}

const us = StyleSheet.create({
  sheet: {
    backgroundColor: V2T.surface, borderTopLeftRadius: V2Radius.sheet, borderTopRightRadius: V2Radius.sheet,
    borderCurve: "continuous",
    borderTopWidth: 1, borderTopColor: V2T.line,
    shadowColor: "#000", shadowOpacity: 0.14, shadowRadius: 16, shadowOffset: { width: 0, height: -4 },
    elevation: 12, overflow: "hidden",
  },
  grabberRow: { alignItems: "center", paddingTop: 8, paddingBottom: 6 },
  grabber: { width: 40, height: 5, borderRadius: 2.5, backgroundColor: V2T.out3 },
  sheetX: { position: "absolute", right: 14, top: 4, padding: 4 },

  /* cards in the sheet's 16px rhythm: opaque surface2, hairline border,
     row radius — no separators, no translucent washes */
  modeRow: {
    flexDirection: "row", alignItems: "center",
    marginHorizontal: 16, marginVertical: 4,
    paddingVertical: 11, paddingHorizontal: 14, minHeight: 56,
    backgroundColor: V2T.surface2, borderRadius: V2Radius.row, borderCurve: "continuous",
    borderWidth: 1, borderColor: V2T.line,
  },
  modeRowSel: { backgroundColor: SEL_TINT, borderColor: V2T.accent },
  modeLabel: { fontFamily: F.med, fontSize: V2Type.body, color: V2T.text, flexShrink: 1 },
  bestTag: { fontFamily: F.med, fontSize: V2Type.label, color: V2T.accent, marginLeft: 8 },
  modeMeta: { fontFamily: F.reg, fontSize: V2Type.label, color: V2T.text3, marginTop: 1 },
  modeReason: { fontFamily: F.reg, fontSize: V2Type.label, color: V2T.text3, marginTop: 3 },
  modeEta: { fontFamily: F.semi, fontSize: V2Type.body, color: V2T.text },
  modeEtaUnit: { fontFamily: F.reg, fontSize: V2Type.label, color: V2T.text2 },
  segRow: { flexDirection: "row", gap: 3, marginTop: 5 },
  seg: { width: 10, height: 4, borderRadius: 2 },

  doseTrack: { width: 44, height: 5, borderRadius: 2.5, backgroundColor: V2T.line, flexDirection: "row", overflow: "hidden", marginTop: 4 },
  doseFill: { borderRadius: 2.5 },
  cigMore: { fontFamily: F.med, fontSize: 11 },

  originPin: {
    width: 20, height: 20, borderRadius: 10, backgroundColor: V2T.bg,
    borderWidth: 2.5, borderColor: V2T.text, alignItems: "center", justifyContent: "center",
    shadowColor: "#000", shadowOpacity: 0.18, shadowRadius: 3, shadowOffset: { width: 0, height: 1 },
  },
  originDot: { width: 7, height: 7, borderRadius: 3.5, backgroundColor: V2T.accent },

  mapBtn: {
    width: 46, height: 46, borderRadius: 23, backgroundColor: V2T.surface,
    alignItems: "center", justifyContent: "center",
    borderWidth: 1, borderColor: V2T.line,
    shadowColor: "#000", shadowOpacity: 0.14, shadowRadius: 8, shadowOffset: { width: 0, height: 2 },
    elevation: 6,
  },
  mapBtnOn: { backgroundColor: V2T.accent, borderColor: V2T.accent },

  alert: {
    flexDirection: "row", alignItems: "center", backgroundColor: V2T.surface2,
    paddingHorizontal: 12, paddingVertical: 9, borderRadius: V2Radius.row,
    borderCurve: "continuous", gap: 8,
    borderWidth: 1, borderColor: V2T.line,
  },
  alertTxt: { flex: 1, fontFamily: F.med, fontSize: V2Type.label, color: V2T.text },
});
