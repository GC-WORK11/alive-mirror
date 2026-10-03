/** Sidebar — full-height dark drawer from the ☰ in the search bar
 * (doc 02 §sidebar, items 1–8). Rules enforced here:
 *  - no stats dashboard beyond Today + This week
 *  - nothing appears without data — no fake numbers, ever
 *  - every consumer string goes through t() (en + hi). */
import React, { useEffect, useMemo, useState } from "react";
import {
  Alert, Animated, Dimensions, Pressable, ScrollView,
  StyleSheet, Switch, Text, View,
} from "react-native";
import { F, NUM, V2Radius, V2T, V2Type, cigOf, fam } from "../../theme";
import { Icon, vehicleGlyph, type Glyph } from "../../icons";
import { t, type Lang } from "../../i18n/strings";
import { stats as ledgerStats, weekStats, type Trip } from "../../store/ledger";
import type { SavedPlace, ShellSettings } from "./settings";

const DRAWER_W = Math.min(340, Dimensions.get("window").width * 0.84);
const dayKey = (ts: number) => new Date(ts).toDateString();

const timeAgo = (ts: number) => {
  const m = Math.max(0, Math.round((Date.now() - ts) / 60000));
  if (m < 1) return "now";
  if (m < 60) return `${m}m`;
  const h = Math.floor(m / 60);
  return h < 24 ? `${h}h` : `${Math.floor(h / 24)}d`;
};

const VEHICLES: { key: string; labelKey: Parameters<typeof t>[0] }[] = [
  { key: "bike", labelKey: "vehicleScooterBike" },
  { key: "car", labelKey: "vehicleCar" },
  { key: "auto", labelKey: "vehicleAuto" },
  { key: "cab", labelKey: "vehicleCab" },
  { key: "transit", labelKey: "vehicleBusMetro" },
  { key: "walk", labelKey: "vehicleCycleWalk" },
];
const vehicleLabelKey = (v: string): Parameters<typeof t>[0] =>
  VEHICLES.find((x) => x.key === v)?.labelKey ?? "vehicleQ1";

type Section = "vehicle" | "places" | "settings" | "how" | null;

export function Sidebar({
  open, onClose, trips, lang, settings, onSettings, onDeleteData,
  onArmBrief, onNavigate, currentDest, onDelhiToday, onTripReceipt,
  onFullSettings,
}: {
  open: boolean;
  onClose: () => void;
  trips: Trip[];
  lang: Lang;
  settings: ShellSettings;
  onSettings: (patch: Partial<ShellSettings>) => void;
  onDeleteData: () => void;
  onArmBrief: () => Promise<boolean>;
  onNavigate: (p: SavedPlace) => void;
  currentDest: SavedPlace | null;
  onDelhiToday?: () => void;        // SEAM(delhi-today): doc 07 consumer city view
  onTripReceipt?: (tr: Trip) => void; // SEAM(receipt): S7 receipt screen
  onFullSettings?: () => void;       // opens the dedicated SettingsScreen
}) {
  const [slide] = useState(() => new Animated.Value(-DRAWER_W));
  const [section, setSection] = useState<Section>(null);
  const toggle = (k: Section) => setSection((s) => (s === k ? null : k));

  // drawer stays mounted off-canvas; the wrapper swallows touches when closed
  useEffect(() => {
    Animated.spring(slide, {
      toValue: open ? 0 : -DRAWER_W, damping: 22, stiffness: 220, useNativeDriver: true,
    }).start();
  }, [open, slide]);

  const st = useMemo(() => ledgerStats(trips), [trips]);
  const week = useMemo(() => weekStats(trips), [trips]);
  const yesterdayUg = useMemo(() => {
    const d = new Date(); d.setDate(d.getDate() - 1);
    const k = dayKey(d.getTime());
    return trips.filter((x) => dayKey(x.ts) === k).reduce((s, x) => s + x.dose_ug, 0);
  }, [trips]);
  const recent = useMemo(() => [...trips].sort((a, b) => b.ts - a.ts).slice(0, 5), [trips]);
  const todayCig = cigOf(st.todayUg) ?? 0;
  const weekMax = Math.max(...week.days.map((d) => d.ug), 1);

  const row = (
    icon: Glyph, label: string, opts?: {
      sub?: string; onPress?: () => void; open?: boolean; hideChevron?: boolean; trailing?: React.ReactNode;
    },
  ) => (
    <Pressable key={label} onPress={opts?.onPress} disabled={!opts?.onPress}
      style={({ pressed }) => [s.row, pressed && !!opts?.onPress && { backgroundColor: V2T.surface2 }]}>
      <Icon name={icon} color={V2T.text2} size={22} filled={opts?.open} />
      <View style={s.rowMid}>
        <Text style={[s.rowLabel, { fontFamily: fam(lang, "med") }]}>{label}</Text>
        {opts?.sub ? <Text style={s.rowSub} numberOfLines={1}>{opts.sub}</Text> : null}
      </View>
      {opts?.trailing}
      {opts?.onPress && !opts?.hideChevron && (
        <View style={{ transform: [{ rotate: opts?.open ? "90deg" : "0deg" }] }}>
          <Icon name="chevron" color={V2T.text3} size={16} />
        </View>
      )}
    </Pressable>
  );

  const placeRow = (slot: "home" | "work") => {
    const place = settings[slot];
    const labelKey = slot === "home" ? "home" : "work";
    return (
      <View key={slot} style={s.subRow}>
        <Icon name={slot} color={V2T.text2} size={20} />
        <Pressable style={{ flex: 1 }} disabled={!place}
          onPress={() => { if (place) { onNavigate(place); onClose(); } }}>
          <Text style={[s.subLabel, { fontFamily: fam(lang, "reg") }]}>{t(labelKey, lang)}</Text>
          <Text style={s.subValue} numberOfLines={1}>
            {place ? place.name : t("notSet", lang)}
          </Text>
        </Pressable>
        {place ? (
          <Pressable hitSlop={8} onPress={() => onSettings({ [slot]: null })}
            accessibilityRole="button" accessibilityLabel={t("a11yClearSaved", lang)}>
            <Icon name="close" color={V2T.text3} size={14} />
          </Pressable>
        ) : currentDest ? (
          <Pressable hitSlop={8} onPress={() => onSettings({ [slot]: currentDest })}>
            <Text style={s.miniAction}>{t("setCurrentDest", lang)}</Text>
          </Pressable>
        ) : null}
      </View>
    );
  };

  return (
    <View style={StyleSheet.absoluteFill} pointerEvents={open ? "auto" : "none"}>
      <Animated.View style={[s.scrim, {
        opacity: slide.interpolate({ inputRange: [-DRAWER_W, 0], outputRange: [0, 1] }),
      }]}>
        <Pressable style={StyleSheet.absoluteFill} onPress={onClose}
          accessibilityRole="button" accessibilityLabel={t("settingsClose", lang)} />
      </Animated.View>
      <Animated.View style={[s.drawer, { transform: [{ translateX: slide }] }]}>
        <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={s.scroll}>
          {/* app mark + close */}
          <View style={s.brandRow}>
            <Text style={s.brand}>ALIVE-108</Text>
            <Pressable onPress={onClose} hitSlop={10} accessibilityRole="button"
              accessibilityLabel={t("settingsClose", lang)}>
              <Icon name="close" color={V2T.text3} size={18} />
            </Pressable>
          </View>

          {/* 1 — Today: two big numbers (put-out hidden until ledger records kg) */}
          <Text style={[s.sectionLabel, { fontFamily: fam(lang, "semi") }]}>{t("sidebarToday", lang)}</Text>
          {st.todayUg > 0 ? (
            <View style={s.todayCard}>
              <View style={s.todayCol}>
                <Text style={[s.todayNum, NUM]}>{todayCig}</Text>
                <Text style={s.todayCap}>{t("breathed", lang)}</Text>
                {yesterdayUg > 0 && (
                  <Text style={s.todayCmp}>
                    {t(st.todayUg <= yesterdayUg ? "lessThanYesterday" : "moreThanYesterday", lang, {
                      p: Math.abs(Math.round((1 - st.todayUg / yesterdayUg) * 100)),
                    })}
                  </Text>
                )}
              </View>
            </View>
          ) : null}

          {/* 2 — This week: 7 thin bars (in; out appears when the ledger tracks it) */}
          {week.totalTrips > 0 && (
            <>
              <Text style={[s.sectionLabel, { fontFamily: fam(lang, "semi") }]}>{t("sidebarThisWeek", lang)}</Text>
              <View style={s.weekRow}>
                {week.days.map((d, i) => (
                  <View key={i} style={s.dayCol}>
                    <View style={s.dayBarWrap}>
                      <View style={[s.dayBar, {
                        height: Math.max(3, (d.ug / weekMax) * 46),
                        backgroundColor: i === week.days.length - 1 ? V2T.accent : V2T.out2,
                        opacity: d.ug === 0 ? 0.3 : 1,
                      }]} />
                    </View>
                    <Text style={s.dayLabel}>{d.label.slice(0, 1)}</Text>
                  </View>
                ))}
              </View>
            </>
          )}

          {/* 3 — Trips */}
          {recent.length > 0 && (
            <>
              <Text style={[s.sectionLabel, { fontFamily: fam(lang, "semi") }]}>{t("sidebarTrips", lang)}</Text>
              {recent.map((tr, i) => (
                <Pressable key={`${tr.ts}-${i}`} disabled={!onTripReceipt}
                  onPress={() => onTripReceipt?.(tr)} style={s.trip}>
                  <Icon name={vehicleGlyph(tr.vehicle)} color={V2T.text2} size={22} />
                  <View style={s.tripMid}>
                    <Text style={s.tripTxt} numberOfLines={1}>{tr.from} → {tr.to}</Text>
                    <Text style={s.tripMeta}>{tr.label} · {timeAgo(tr.ts)}</Text>
                  </View>
                  <Icon name="cigarette" color={V2T.text3} size={14} />
                  <Text style={[s.tripNum, NUM]}>{cigOf(tr.dose_ug) ?? 0}</Text>
                </Pressable>
              ))}
            </>
          )}

          <View style={s.div} />

          {/* 4 — My vehicle */}
          {row("bike", t("sidebarMyVehicle", lang), {
            sub: settings.vehicle ? t(vehicleLabelKey(settings.vehicle), lang) : t("notSet", lang),
            onPress: () => toggle("vehicle"), open: section === "vehicle",
          })}
          {section === "vehicle" && (
            <View style={s.subBox}>
              {VEHICLES.map((v) => (
                <Pressable key={v.key} style={s.subRow}
                  onPress={() => { onSettings({ vehicle: v.key }); setSection(null); }}>
                  <Icon name={vehicleGlyph(v.key)} color={settings.vehicle === v.key ? V2T.accent : V2T.text2} size={20} />
                  <Text style={[s.subLabel, { fontFamily: fam(lang, "reg") },
                    settings.vehicle === v.key && { color: V2T.accent }]}>
                    {t(v.labelKey, lang)}
                  </Text>
                </Pressable>
              ))}
            </View>
          )}

          {/* 5 — Delhi today. SEAM(delhi-today): consumer city view (doc 07)
              lands with the screens lane; row stays hidden until then. */}
          {onDelhiToday && row("pin", t("sidebarDelhiToday", lang), { onPress: onDelhiToday })}

          {/* 6 — Saved places */}
          {row("star", t("sidebarSavedPlaces", lang), {
            onPress: () => toggle("places"), open: section === "places",
          })}
          {section === "places" && <View style={s.subBox}>{placeRow("home")}{placeRow("work")}</View>}

          {/* 7 — Settings — full screen when mounted (explainers + quiet
              hours); the inline toggles stay as the fallback path */}
          {row("layers", t("sidebarSettings", lang), {
            onPress: () => onFullSettings ? onFullSettings() : toggle("settings"),
            open: section === "settings",
          })}
          {section === "settings" && (
            <View style={s.subBox}>
              <View style={s.subRow}>
                <Text style={[s.subLabel, { fontFamily: fam(lang, "reg") }]}>{t("settingsVoice", lang)}</Text>
                <Switch value={settings.voice} onValueChange={(v) => onSettings({ voice: v })}
                  trackColor={{ false: V2T.line, true: V2T.accent }} thumbColor={V2T.text} />
              </View>
              <View style={s.subRow}>
                <Text style={[s.subLabel, { fontFamily: fam(lang, "reg") }]}>{t("settingsLanguage", lang)}</Text>
                <View style={s.segWrap}>
                  {(["en", "hi"] as Lang[]).map((l) => (
                    <Pressable key={l} onPress={() => onSettings({ lang: l })}
                      style={[s.seg, lang === l && s.segOn]}>
                      <Text style={[s.segTxt, lang === l && { color: V2T.text }]}>
                        {l === "en" ? "English" : "हिंदी"}
                      </Text>
                    </Pressable>
                  ))}
                </View>
              </View>
              <View style={s.subRow}>
                <Text style={[s.subLabel, { fontFamily: fam(lang, "reg") }]}>{t("settingsUnits", lang)}</Text>
                <Text style={s.subValue}>{t("unitsKm", lang)}</Text>
              </View>
              <View style={s.subRow}>
                <Text style={[s.subLabel, { fontFamily: fam(lang, "reg") }]}>
                  {t("morningAlert", lang)}
                </Text>
                <Switch
                  value={settings.brief}
                  onValueChange={async (v) => {
                    if (v) onSettings({ brief: await onArmBrief() });
                    else onSettings({ brief: false });
                  }}
                  trackColor={{ false: V2T.line, true: V2T.accent }} thumbColor={V2T.text} />
              </View>
              <View style={[s.subRow, { alignItems: "flex-start" }]}>
                <View style={{ flex: 1 }}>
                  <Text style={[s.subLabel, { fontFamily: fam(lang, "reg") }]}>{t("settingsShareData", lang)}</Text>
                  <Text style={s.hint}>{t("shareDataHint", lang)}</Text>
                </View>
                <Switch value={settings.share} onValueChange={(v) => onSettings({ share: v })}
                  trackColor={{ false: V2T.line, true: V2T.accent }} thumbColor={V2T.text} />
              </View>
              <Pressable style={s.subRow} onPress={() =>
                Alert.alert(t("deleteConfirmTitle", lang), t("deleteConfirmBody", lang), [
                  { text: t("cancel", lang), style: "cancel" },
                  { text: t("deleteConfirmYes", lang), style: "destructive", onPress: onDeleteData },
                ])}>
                <Icon name="trash" color={V2T.breath3} size={18} />
                <Text style={[s.subLabel, { fontFamily: fam(lang, "reg"), color: V2T.breath3 }]}>
                  {t("settingsDeleteData", lang)}
                </Text>
              </Pressable>
            </View>
          )}

          {/* 8 — How ALive works */}
          {row("info", t("sidebarHowAliveWorks", lang), {
            onPress: () => toggle("how"), open: section === "how",
          })}
          {section === "how" && (
            <View style={s.subBox}>
              <Text style={[s.howBody, { fontFamily: fam(lang, "reg") }]}>{t("howAliveBody", lang)}</Text>
              {/* SEAM(sources): claims-ledger sources link lands with doc 10 web surface */}
            </View>
          )}
        </ScrollView>
      </Animated.View>
    </View>
  );
}

const s = StyleSheet.create({
  scrim: { position: "absolute", top: 0, bottom: 0, left: 0, right: 0, backgroundColor: "rgba(0,0,0,0.5)" },
  drawer: {
    position: "absolute", left: 0, top: 0, bottom: 0, width: DRAWER_W,
    backgroundColor: V2T.bg, borderRightWidth: 1, borderRightColor: V2T.line,
    shadowColor: "#000", shadowOpacity: 0.5, shadowRadius: 24, shadowOffset: { width: 4, height: 0 },
    elevation: 12,
  },
  scroll: { paddingTop: 58, paddingHorizontal: 18, paddingBottom: 32 },

  brandRow: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", marginBottom: 14 },
  brand: { fontFamily: F.semi, fontSize: V2Type.label, color: V2T.accent, letterSpacing: 3 },

  sectionLabel: {
    fontSize: V2Type.label, color: V2T.text3, letterSpacing: 0.8,
    textTransform: "uppercase", marginTop: 18, marginBottom: 8,
  },
  todayCard: {
    flexDirection: "row", backgroundColor: V2T.surface,
    borderRadius: V2Radius.row, padding: 16, borderWidth: 1, borderColor: V2T.line,
  },
  todayCol: { flex: 1 },
  todayNum: { fontFamily: F.semi, fontSize: V2Type.hero, color: V2T.text, lineHeight: 38 },
  todayCap: { fontFamily: F.reg, fontSize: V2Type.secondary, color: V2T.text2, marginTop: 2 },
  todayCmp: { fontFamily: F.reg, fontSize: V2Type.label, color: V2T.text3, marginTop: 4 },

  weekRow: { flexDirection: "row", alignItems: "flex-end", paddingHorizontal: 4 },
  dayCol: { flex: 1, alignItems: "center" },
  dayBarWrap: { height: 46, justifyContent: "flex-end" },
  dayBar: { width: 12, borderRadius: 4 },
  dayLabel: { fontFamily: F.reg, fontSize: 10, color: V2T.text3, marginTop: 5 },

  trip: { flexDirection: "row", alignItems: "center", gap: 10, paddingVertical: 9 },
  tripMid: { flex: 1, marginRight: 6 },
  tripTxt: { fontFamily: F.med, fontSize: V2Type.secondary, color: V2T.text },
  tripMeta: { fontFamily: F.reg, fontSize: V2Type.label, color: V2T.text3, marginTop: 1 },
  tripNum: { fontFamily: F.semi, fontSize: V2Type.secondary, color: V2T.text2, marginLeft: 4 },

  div: { height: 1, backgroundColor: V2T.line, marginVertical: 12 },

  row: {
    flexDirection: "row", alignItems: "center", gap: 14,
    paddingVertical: 11, paddingHorizontal: 4, borderRadius: V2Radius.row,
  },
  rowMid: { flex: 1 },
  rowLabel: { fontSize: V2Type.secondary, color: V2T.text },
  rowSub: { fontFamily: F.reg, fontSize: V2Type.label, color: V2T.text3, marginTop: 1 },

  subBox: {
    marginLeft: 18, marginBottom: 6, paddingLeft: 14,
    borderLeftWidth: 1, borderLeftColor: V2T.line,
  },
  subRow: { flexDirection: "row", alignItems: "center", gap: 10, paddingVertical: 9 },
  subLabel: { flex: 1, fontSize: V2Type.secondary, color: V2T.text },
  subValue: { fontFamily: F.reg, fontSize: V2Type.label, color: V2T.text3 },
  miniAction: { fontFamily: F.med, fontSize: V2Type.label, color: V2T.accent },
  hint: { fontFamily: F.reg, fontSize: V2Type.label, color: V2T.text3, marginTop: 2, lineHeight: 17 },

  segWrap: {
    flexDirection: "row", borderRadius: V2Radius.pill,
    borderWidth: 1, borderColor: V2T.line, overflow: "hidden",
  },
  seg: { paddingHorizontal: 14, paddingVertical: 6 },
  segOn: { backgroundColor: V2T.surface2 },
  segTxt: { fontFamily: F.med, fontSize: V2Type.label, color: V2T.text3 },

  howBody: { fontSize: V2Type.secondary, color: V2T.text2, lineHeight: 22, paddingVertical: 8 },
});
