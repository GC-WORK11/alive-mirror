/** ALive-108 component primitives — docs/24 spec §5.4. */
import React, { useEffect, useState } from "react";
import {
  Animated, Pressable, StyleSheet, Text, TextInput, View,
  type StyleProp, type ViewStyle,
} from "react-native";
import { F, NUM, T, cigOf } from "./theme";
import { Icon, vehicleGlyph, type Glyph } from "./icons";

/** 1 — floating search pill: one field, avatar inside right edge. */
export function SearchPill({
  placeholder, value, onFocus, onChange, onAvatar,
  left, hint,
}: {
  placeholder: string; value: string;
  onFocus?: () => void; onChange?: (t: string) => void;
  onAvatar?: () => void;
  left?: React.ReactNode; hint?: string;
}) {
  return (
    <View style={us.pill}>
      {left ?? <Icon name="pin" color={T.ink3} size={18} />}
      <TextInput
        style={us.pillInput}
        placeholder={placeholder}
        placeholderTextColor={T.ink3}
        autoCorrect={false} autoCapitalize="none"
        value={value} onFocus={onFocus} onChangeText={onChange}
        returnKeyType="search" clearButtonMode="while-editing"
      />
      {hint ? <Text style={us.pillHint} numberOfLines={1}>{hint}</Text> : null}
      {onAvatar && (
        <Pressable onPress={onAvatar} hitSlop={8} style={us.avatarBtn}>
          <Icon name="avatar" color={T.surface} size={16} filled />
        </Pressable>
      )}
    </View>
  );
}

/** 2 — bottom sheet with grabber + X (NN/g: both, never stack). */
export function Sheet({
  detent = "peek", onClose, children, style,
}: {
  detent?: "peek" | "half" | "full";
  onClose?: () => void;
  children: React.ReactNode;
  style?: StyleProp<ViewStyle>;
}) {
  const h = detent === "peek" ? 96 : detent === "half" ? 340 : 560;
  const [anim] = useState(() => new Animated.Value(0));
  useEffect(() => {
    Animated.timing(anim, { toValue: 1, duration: 240, useNativeDriver: true }).start();
  }, [anim]);
  return (
    <Animated.View
      style={[us.sheet, { maxHeight: h, transform: [{ translateY: anim.interpolate({ inputRange: [0, 1], outputRange: [40, 0] }) }] }, style]}
    >
      <View style={us.grabberRow}>
        <View style={us.grabber} />
        {onClose && (
          <Pressable onPress={onClose} hitSlop={10} style={us.sheetX}>
            <Icon name="close" color={T.ink3} size={16} />
          </Pressable>
        )}
      </View>
      {children}
    </Animated.View>
  );
}

/** 3 — mode row: silhouette | ETA | meta | dose column. Ledger, not card. */
export function ModeRow({
  vehicle, label, etaMin, meta, doseUg, best, worst, selected, onPress, reason,
}: {
  vehicle: string; label: string; etaMin: number; meta?: string;
  doseUg: number | null; best?: boolean; worst?: boolean;
  selected: boolean; onPress: () => void; reason?: string;
}) {
  const cig = cigOf(doseUg);
  const frac = doseUg == null ? 0 : Math.min(1, doseUg / 316);
  const dc = doseUg == null ? T.doseQuiet
    : frac < 0.25 ? T.doseQuiet : frac < 0.6 ? T.doseWarn
    : frac < 1.2 ? T.doseOver : T.doseSevere;
  return (
    <Pressable onPress={onPress}
      style={({ pressed }) => [us.modeRow, pressed && { opacity: 0.55 }, selected && us.modeRowSel]}>
      <Icon name={vehicleGlyph(vehicle)} color={selected ? T.go : T.ink2} size={30} />
      <View style={{ flex: 1, marginLeft: 12 }}>
        <View style={{ flexDirection: "row", alignItems: "baseline" }}>
          <Text style={us.modeLabel} numberOfLines={1}>{label}</Text>
          {best && <Text style={us.bestTag}>least smoke</Text>}
        </View>
        {reason ? <Text style={us.modeReason} numberOfLines={1}>{reason}</Text> : null}
        {meta ? <Text style={us.modeMeta} numberOfLines={1}>{meta}</Text> : null}
      </View>
      <View style={{ alignItems: "flex-end" }}>
        <Text style={[us.modeEta, NUM]}>{etaMin}<Text style={us.modeEtaUnit}> min</Text></Text>
        <DoseBar frac={frac} color={dc} />
        {cig != null && cig >= 0.05 && (
          <Text style={[us.modeCig, NUM, { color: dc }]}>{cig} 🚬</Text>
        )}
      </View>
    </Pressable>
  );
}

/** 4 — dose bar: 44×5 hairline track, depth = dose vs cigarette budget. */
export function DoseBar({ frac, color }: { frac: number; color?: string }) {
  const c = color ?? T.doseQuiet;
  return (
    <View style={us.doseTrack}>
      <View style={[us.doseFill, { flex: Math.max(0.02, Math.min(1, frac)), backgroundColor: c }]} />
      <View style={{ flex: Math.max(0, 1 - frac) }} />
    </View>
  );
}

/** 5 — cigarette strip: N glyphs, last one partially filled. */
export function CigStrip({ ug, size = 16, color = T.ink, max = 7 }: {
  ug: number | null | undefined; size?: number; color?: string; max?: number;
}) {
  if (ug == null || ug <= 0) return null;
  const cigs = ug / 316;
  const full = Math.floor(cigs);
  const partial = cigs - full;
  const n = Math.min(max, Math.max(1, Math.ceil(cigs)));
  return (
    <View style={{ flexDirection: "row", alignItems: "center", gap: 3 }}>
      {Array.from({ length: n }).map((_, i) => (
        <View key={i} style={{ width: size, height: size }}>
          <Icon name="cigarette" color={i < full ? color : T.hairline} size={size} filled={i < full} />
          {i === full && partial > 0.05 && (
            <View style={{
              position: "absolute", left: 0, top: 0, bottom: 0,
              width: size * partial, overflow: "hidden",
            }}>
              <Icon name="cigarette" color={color} size={size} filled />
            </View>
          )}
        </View>
      ))}
      {cigs > max && <Text style={[us.cigMore, NUM, { color }]}>+{Math.round(cigs - max)}</Text>}
    </View>
  );
}

/** 6 — floating action button (max 2 per screen budget). */
export function Fab({ glyph, onPress, active }: { glyph: Glyph; onPress: () => void; active?: boolean }) {
  return (
    <Pressable onPress={onPress} hitSlop={8}
      style={({ pressed }) => [us.fab, active && us.fabOn, pressed && { opacity: 0.6 }]}>
      <Icon name={glyph} color={active ? T.surface : T.ink} size={20} filled={active} />
    </Pressable>
  );
}

/** 7 — endpoint pins: ink dot ringed paper (origin) / ink teardrop (dest). */
export function EndpointPin({ kind }: { kind: "origin" | "dest" }) {
  if (kind === "origin") {
    return (
      <View style={us.originPin}>
        <View style={us.originDot} />
      </View>
    );
  }
  return (
    <View style={{ alignItems: "center" }}>
      <Icon name="pin" color={T.ink} size={30} filled />
    </View>
  );
}

/** 8 — small one-line banner strip (GRAP / hazard-grade events only). */
export function AlertBanner({ text, onClose }: { text: string; onClose?: () => void }) {
  return (
    <View style={us.alert}>
      <Text style={us.alertTxt} numberOfLines={1}>{text}</Text>
      {onClose && (
        <Pressable onPress={onClose} hitSlop={8}>
          <Icon name="close" color={T.ambientPaper} size={14} />
        </Pressable>
      )}
    </View>
  );
}

const us = StyleSheet.create({
  pill: {
    flexDirection: "row", alignItems: "center",
    backgroundColor: T.surface, borderRadius: 28, height: 52,
    paddingHorizontal: 16, borderWidth: StyleSheet.hairlineWidth,
    borderColor: T.hairline,
    shadowColor: "#000", shadowOpacity: 0.08, shadowRadius: 8, shadowOffset: { width: 0, height: 2 },
    elevation: 3,
  },
  pillInput: { flex: 1, fontFamily: F.med, fontSize: 16, color: T.ink, marginLeft: 10, paddingVertical: 0 },
  pillHint: { fontFamily: F.reg, fontSize: 11, color: T.ink3, maxWidth: 90 },
  avatarBtn: {
    width: 30, height: 30, borderRadius: 15, backgroundColor: T.ink,
    alignItems: "center", justifyContent: "center", marginLeft: 8,
  },
  sheet: {
    backgroundColor: T.surface, borderTopLeftRadius: 16, borderTopRightRadius: 16,
    borderWidth: StyleSheet.hairlineWidth, borderColor: T.hairline, borderBottomWidth: 0,
    shadowColor: "#000", shadowOpacity: 0.12, shadowRadius: 12, shadowOffset: { width: 0, height: -3 },
    elevation: 6, overflow: "hidden",
  },
  grabberRow: { alignItems: "center", paddingTop: 8, paddingBottom: 4 },
  grabber: { width: 36, height: 4.5, borderRadius: 2.5, backgroundColor: T.hairline },
  sheetX: { position: "absolute", right: 14, top: 4, padding: 4 },
  modeRow: {
    flexDirection: "row", alignItems: "center",
    paddingVertical: 12, paddingHorizontal: 16, minHeight: 56,
    borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: T.hairline,
  },
  modeRowSel: { backgroundColor: T.goSoft },
  modeLabel: { fontFamily: F.med, fontSize: 16, color: T.ink },
  bestTag: { fontFamily: F.med, fontSize: 11, color: T.go, marginLeft: 8 },
  modeReason: { fontFamily: F.reg, fontSize: 13, color: T.ink2, marginTop: 1 },
  modeMeta: { fontFamily: F.reg, fontSize: 12, color: T.ink3, marginTop: 1 },
  modeEta: { fontFamily: F.bold, fontSize: 17, color: T.ink },
  modeEtaUnit: { fontFamily: F.reg, fontSize: 12, color: T.ink2 },
  modeCig: { fontFamily: F.med, fontSize: 12, marginTop: 2 },
  doseTrack: {
    width: 44, height: 5, borderRadius: 2.5, backgroundColor: T.hairline,
    flexDirection: "row", overflow: "hidden", marginTop: 4,
  },
  doseFill: { borderRadius: 2.5 },
  cigMore: { fontFamily: F.med, fontSize: 11 },
  fab: {
    width: 44, height: 44, borderRadius: 22, backgroundColor: T.surface,
    alignItems: "center", justifyContent: "center",
    borderWidth: StyleSheet.hairlineWidth, borderColor: T.hairline,
    shadowColor: "#000", shadowOpacity: 0.1, shadowRadius: 6, shadowOffset: { width: 0, height: 2 },
    elevation: 4,
  },
  fabOn: { backgroundColor: T.go, borderColor: T.go },
  originPin: {
    width: 20, height: 20, borderRadius: 10, backgroundColor: T.surface,
    borderWidth: 2, borderColor: T.go, alignItems: "center", justifyContent: "center",
    shadowColor: "#000", shadowOpacity: 0.2, shadowRadius: 3, shadowOffset: { width: 0, height: 1 },
  },
  originDot: { width: 8, height: 8, borderRadius: 4, backgroundColor: T.go },
  alert: {
    flexDirection: "row", alignItems: "center", backgroundColor: T.ink,
    paddingHorizontal: 14, paddingVertical: 8, borderRadius: 8, gap: 10,
  },
  alertTxt: { flex: 1, fontFamily: F.med, fontSize: 13, color: T.ambientPaper },
});
