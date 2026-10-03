/** Sidebar — full-height light drawer from the ☰ in the search bar
 * (doc 02 §sidebar, items 1–8). Rules enforced here:
 *  - no stats dashboard beyond Today + This week
 *  - nothing appears without data — no fake numbers, ever
 *  - every consumer string goes through t() (en + hi).
 * r4 pass: solid surface, fixed brand header, grouped cards
 * (navigate / app), inset hairlines, ≥44pt rows, first-class
 * language + sharing rows.
 * SEAM(i18n): group headers would use proposed keys
 *   sidebarNavigate ("Navigate" / "नेविगेट") and
 *   sidebarApp ("App" / "ऐप") — groups ship unlabeled (the cards
 *   carry the grouping) until strings.ts lands them. */
import React, { useEffect, useMemo, useState } from "react";
import {
  Alert, Animated, Dimensions, Pressable, ScrollView,
  StyleSheet, Switch, Text, View,
} from "react-native";
import { F, NUM, V2Radius, V2T, V2Type, cigOf, fam } from "../../theme";
import { DYNAMIC_TYPE } from "../../a11y";
import { Icon, vehicleGlyph, type Glyph } from "../../icons";
import { t, type Lang } from "../../i18n/strings";
import { stats as ledgerStats, weekStats, type Trip } from "../../store/ledger";
import type { SavedPlace, ShellSettings } from "./settings";
import { useSafeAreaInsets } from "react-native-safe-area-context";

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
  onFullSettings, onLang, onShare, onShareTrip,
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
  onLang?: (l: Lang) => void;        // SEAM(lang): dedicated language callback —
                                     // falls back to onSettings({lang}) when unwired
  onShare?: () => void;              // SEAM(share): system share of the app —
                                     // the row stays hidden until wired
  onShareTrip?: (tr: Trip) => void;  // SEAM(share-trip): share one trip's
                                     // numbers — trailing affordance per row
}) {
  const [slide] = useState(() => new Animated.Value(-DRAWER_W));
  const [section, setSection] = useState<Section>(null);
  const insets = useSafeAreaInsets();
  const toggle = (k: Section) => setSection((s) => (s === k ? null : k));

  // drawer stays mounted off-canvas; the wrapper swallows touches when closed
  // NB: JS driver — RN 0.86's native-animated detach path segfaults the
  // sheet flow (see ui.tsx Sheet for the same guard)
  useEffect(() => {
    Animated.spring(slide, {
      toValue: open ? 0 : -DRAWER_W, damping: 22, stiffness: 220, useNativeDriver: false,
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
  // doc 02 §sidebar-1's second number — shown only when today's trips carry
  // real emit_kg readings (SEAM(emissions) rows predate the field).
  const todayKg = useMemo(
    () => Math.round(st.today.reduce((sum, x) => sum + (x.emit_kg ?? 0), 0) * 10) / 10,
    [st],
  );
  const weekMax = Math.max(...week.days.map((d) => d.ug), 1);

  const setLang = (l: Lang) => (onLang ? onLang(l) : onSettings({ lang: l }));

  /** One drawer row — fixed icon slot, label (+sub/hint), chevron when it
   *  navigates or expands. Non-pressable content renders as a plain View so
   *  nested controls keep their own semantics. */
  const menuRow = (p: {
    glyph?: Glyph; icon?: React.ReactNode; label: string;
    sub?: string; hint?: string;
    onPress?: () => void; open?: boolean;
    trailing?: React.ReactNode; hideChevron?: boolean;
    danger?: boolean; a11y?: string;
  }) => {
    const body = (
      <>
        <View style={s.rowIcon}>
          {p.icon ?? (p.glyph ? (
            <Icon name={p.glyph} color={p.danger ? V2T.breath3 : V2T.text2}
              size={20} filled={p.open} />
          ) : null)}
        </View>
        <View style={s.rowMid}>
          <Text {...DYNAMIC_TYPE} style={[s.rowLabel, { fontFamily: fam(lang, "med") },
            p.danger && { color: V2T.breath3 }]}>
            {p.label}
          </Text>
          {p.sub ? <Text {...DYNAMIC_TYPE} style={s.rowSub} numberOfLines={1}>{p.sub}</Text> : null}
          {p.hint ? <Text {...DYNAMIC_TYPE} style={s.rowHint}>{p.hint}</Text> : null}
        </View>
        {p.trailing}
        {p.onPress && !p.hideChevron && (
          <View style={{ transform: [{ rotate: p.open ? "90deg" : "0deg" }] }}>
            <Icon name="chevron" color={V2T.text3} size={15} />
          </View>
        )}
      </>
    );
    if (!p.onPress) return <View style={s.row}>{body}</View>;
    return (
      <Pressable onPress={p.onPress} accessibilityRole="button"
        accessibilityLabel={p.a11y ?? p.label}
        accessibilityState={p.open != null ? { expanded: p.open } : undefined}
        style={({ pressed }) => [
          s.row, pressed && (p.danger ? s.rowDangerPress : s.rowPressed),
        ]}>
        {body}
      </Pressable>
    );
  };

  /** Card = one visual group; hairlines inset to the label edge. */
  const card = (items: React.ReactNode[], marginTop = 20) => {
    const list = items.filter(Boolean);
    if (list.length === 0) return null;
    return (
      <View style={[s.card, { marginTop }]}>
        {list.map((it, i) => (
          <React.Fragment key={i}>
            {i > 0 && <View style={s.hair} />}
            {it}
          </React.Fragment>
        ))}
      </View>
    );
  };

  /** Expanded content under a row — solid inset panel, no left-rail. */
  const panel = (kids: React.ReactNode) => <View style={s.panel}>{kids}</View>;

  const placeRow = (slot: "home" | "work") => {
    const place = settings[slot];
    const labelKey = slot === "home" ? "home" : "work";
    return (
      <View key={slot} style={s.subRow}>
        <Icon name={slot} color={V2T.text2} size={18} />
        <Pressable style={{ flex: 1 }} disabled={!place}
          onPress={() => { if (place) { onNavigate(place); onClose(); } }}
          accessibilityRole="button" accessibilityState={{ disabled: !place }}
          accessibilityLabel={place ? `${t(labelKey, lang)} — ${place.name}` : t(labelKey, lang)}>
          <Text {...DYNAMIC_TYPE} style={[s.subLabel, { fontFamily: fam(lang, "reg") }]}>{t(labelKey, lang)}</Text>
          <Text {...DYNAMIC_TYPE} style={s.subValue} numberOfLines={1}>
            {place ? place.name : t("notSet", lang)}
          </Text>
        </Pressable>
        {place ? (
          <Pressable hitSlop={8} onPress={() => onSettings({ [slot]: null })}
            accessibilityRole="button" accessibilityLabel={t("a11yClearSaved", lang)}
            style={({ pressed }) => [s.miniBtn, pressed && { opacity: 0.6 }]}>
            <Icon name="close" color={V2T.text3} size={14} />
          </Pressable>
        ) : currentDest ? (
          <Pressable hitSlop={8} onPress={() => onSettings({ [slot]: currentDest })}
            accessibilityRole="button" accessibilityLabel={t("setCurrentDest", lang)}
            style={({ pressed }) => [s.miniBtn, pressed && { opacity: 0.6 }]}>
            <Text {...DYNAMIC_TYPE} style={s.miniAction}>{t("setCurrentDest", lang)}</Text>
          </Pressable>
        ) : null}
      </View>
    );
  };

  const switchRow = (labelKey: Parameters<typeof t>[0], value: boolean,
    onValue: (v: boolean) => void, hintKey?: Parameters<typeof t>[0]) => (
    <View style={s.subRow}>
      <View style={{ flex: 1 }}>
        <Text {...DYNAMIC_TYPE} style={[s.subLabel, { fontFamily: fam(lang, "reg") }]}>{t(labelKey, lang)}</Text>
        {hintKey ? <Text {...DYNAMIC_TYPE} style={s.rowHint}>{t(hintKey, lang)}</Text> : null}
      </View>
      {/* light-theme switch: white knob on the line/accent track —
          thumbColor=V2T.text left an ink blob on the light track */}
      <Switch value={value} onValueChange={onValue} accessibilityLabel={t(labelKey, lang)}
        trackColor={{ false: V2T.line, true: V2T.accent }} thumbColor={V2T.surface} />
    </View>
  );

  const tripRow = (tr: Trip, i: number) => (
    <Pressable key={`${tr.ts}-${i}`} disabled={!onTripReceipt}
      onPress={() => onTripReceipt?.(tr)}
      accessibilityRole={onTripReceipt ? "button" : undefined}
      accessibilityState={{ disabled: !onTripReceipt }}
      accessibilityLabel={`${tr.from} — ${tr.to}`}
      style={({ pressed }) => [s.trip, pressed && !!onTripReceipt && s.rowPressed]}>
      <View style={s.rowIcon}>
        <Icon name={vehicleGlyph(tr.vehicle)} color={V2T.text2} size={20} />
      </View>
      <View style={s.tripMid}>
        <Text {...DYNAMIC_TYPE} style={[s.tripTxt, { fontFamily: fam(lang, "med") }]} numberOfLines={1}>
          {tr.from} → {tr.to}
        </Text>
        <Text {...DYNAMIC_TYPE} style={s.tripMeta}>{tr.label} · {timeAgo(tr.ts)}</Text>
      </View>
      <Icon name="cigarette" color={V2T.text3} size={13} />
      <Text {...DYNAMIC_TYPE} style={[s.tripNum, NUM]}>{cigOf(tr.dose_ug) ?? 0}</Text>
      {onShareTrip && (
        <Pressable hitSlop={8} onPress={() => onShareTrip(tr)}
          accessibilityRole="button"
          accessibilityLabel={`${t("share", lang)} — ${tr.from} ${tr.to}`}
          style={({ pressed }) => [s.miniBtn, pressed && { opacity: 0.6 }]}>
          <Icon name="share" color={V2T.text3} size={15} />
        </Pressable>
      )}
    </Pressable>
  );

  return (
    <View style={StyleSheet.absoluteFill} pointerEvents={open ? "auto" : "none"}>
      <Animated.View style={[s.scrim, {
        opacity: slide.interpolate({ inputRange: [-DRAWER_W, 0], outputRange: [0, 1] }),
      }]}>
        <Pressable style={StyleSheet.absoluteFill} onPress={onClose}
          accessibilityRole="button" accessibilityLabel={t("settingsClose", lang)} />
      </Animated.View>
      <Animated.View style={[s.drawer, { transform: [{ translateX: slide }] }]}>
        {/* fixed header — app mark + wordmark + close (stays put while
            the list scrolls) */}
        <View style={[s.header, { paddingTop: insets.top + 14 }]}>
          <View style={s.brandRow}>
            <View style={s.mark}>
              <Icon name="wind" color={V2T.accent} size={15} />
            </View>
            <Text {...DYNAMIC_TYPE} style={s.wordmark}>ALIVE<Text {...DYNAMIC_TYPE} style={{ color: V2T.accent }}>-108</Text></Text>
          </View>
          <Pressable onPress={onClose} hitSlop={10} accessibilityRole="button"
            accessibilityLabel={t("settingsClose", lang)}
            style={({ pressed }) => [s.closeBtn, pressed && { opacity: 0.6 }]}>
            <Icon name="close" color={V2T.text2} size={14} />
          </Pressable>
        </View>

        <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={[s.scroll, { paddingBottom: insets.bottom + 20 }]}>
          {/* 1 — Today: breathed; put-out joins when the ledger has kg
              (doc 02 §sidebar-1 — both numbers, never fake) */}
          {st.todayUg > 0 && (
            <>
              <Text {...DYNAMIC_TYPE} style={[s.sectionLabel, s.sectionLabelFirst,
                { fontFamily: fam(lang, "semi") }]}>{t("sidebarToday", lang)}</Text>
              <View style={s.card}>
                <View style={s.todayRow}>
                  <View style={s.statCol}>
                    <View style={s.statHead}>
                      <Icon name="cigarette" color={V2T.text3} size={15} />
                      <Text {...DYNAMIC_TYPE} style={s.statCap}>{t("breathed", lang)}</Text>
                    </View>
                    <Text {...DYNAMIC_TYPE} style={[s.statNum, NUM]}>{todayCig}</Text>
                    {yesterdayUg > 0 && (
                      <Text {...DYNAMIC_TYPE} style={s.statCmp}>
                        {t(st.todayUg <= yesterdayUg ? "lessThanYesterday" : "moreThanYesterday", lang, {
                          p: Math.abs(Math.round((1 - st.todayUg / yesterdayUg) * 100)),
                        })}
                      </Text>
                    )}
                  </View>
                  {todayKg > 0 && (
                    <>
                      <View style={s.statDiv} />
                      <View style={s.statCol}>
                        <View style={s.statHead}>
                          <Icon name="smoke" color={V2T.text3} size={15} />
                          <Text {...DYNAMIC_TYPE} style={s.statCap}>{t("putOut", lang)}</Text>
                        </View>
                        <Text {...DYNAMIC_TYPE} style={[s.statNum, NUM]}>{t("nav_kg", lang, { n: todayKg })}</Text>
                      </View>
                    </>
                  )}
                </View>
              </View>
            </>
          )}

          {/* 2 — This week: 7 thin bars */}
          {week.totalTrips > 0 && (
            <>
              <Text {...DYNAMIC_TYPE} style={[s.sectionLabel, { fontFamily: fam(lang, "semi") }]}>{t("sidebarThisWeek", lang)}</Text>
              <View style={s.card}>
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
                      <Text {...DYNAMIC_TYPE} style={s.dayLabel}>{d.label.slice(0, 1)}</Text>
                    </View>
                  ))}
                </View>
              </View>
            </>
          )}

          {/* 3 — Trips: tap → that receipt; share affordance appears with
              SEAM(share-trip) */}
          {recent.length > 0 && (
            <>
              <Text {...DYNAMIC_TYPE} style={[s.sectionLabel, { fontFamily: fam(lang, "semi") }]}>{t("sidebarTrips", lang)}</Text>
              {card(recent.map((tr, i) => tripRow(tr, i)), 0)}
            </>
          )}

          {/* ── navigate group (saved places · Delhi today · my vehicle) ── */}
          {card([
            <View key="places">
              {menuRow({
                glyph: "star", label: t("sidebarSavedPlaces", lang),
                onPress: () => toggle("places"), open: section === "places",
              })}
              {section === "places" && panel(<>{placeRow("home")}{placeRow("work")}</>)}
            </View>,
            onDelhiToday && (
              <View key="delhi">
                {menuRow({ glyph: "pin", label: t("sidebarDelhiToday", lang), onPress: onDelhiToday })}
              </View>
            ),
            <View key="vehicle">
              {menuRow({
                glyph: settings.vehicle ? vehicleGlyph(settings.vehicle) : "bike",
                label: t("sidebarMyVehicle", lang),
                sub: settings.vehicle ? t(vehicleLabelKey(settings.vehicle), lang) : t("notSet", lang),
                onPress: () => toggle("vehicle"), open: section === "vehicle",
              })}
              {section === "vehicle" && panel(
                <View style={s.chipWrap}>
                  {VEHICLES.map((v) => {
                    const sel = settings.vehicle === v.key;
                    return (
                      <Pressable key={v.key} accessibilityRole="button"
                        accessibilityState={{ selected: sel }}
                        onPress={() => { onSettings({ vehicle: v.key }); setSection(null); }}
                        style={({ pressed }) => [
                          s.chip, sel && s.chipOn, pressed && { opacity: 0.7 },
                        ]}>
                        <Icon name={vehicleGlyph(v.key)} color={sel ? V2T.accent : V2T.text2} size={18} />
                        <Text {...DYNAMIC_TYPE} style={[s.chipTxt, { fontFamily: fam(lang, "reg") },
                          sel && { color: V2T.accent }]}>
                          {t(v.labelKey, lang)}
                        </Text>
                      </Pressable>
                    );
                  })}
                </View>,
              )}
            </View>,
          ])}

          {/* ── app group (language · sharing · settings · about) ── */}
          {card([
            // language — first-class segmented toggle (doc 02 §sidebar-7)
            <View key="lang" style={s.row}>
              <View style={s.langBadge}>
                <Text {...DYNAMIC_TYPE} style={s.langBadgeTxt}>अA</Text>
              </View>
              <Text {...DYNAMIC_TYPE} style={[s.rowLabel, s.rowMid, { fontFamily: fam(lang, "med") }]}>
                {t("settingsLanguage", lang)}
              </Text>
              <View style={s.segWrap}>
                {(["en", "hi"] as Lang[]).map((l) => (
                  <Pressable key={l} onPress={() => setLang(l)}
                    accessibilityRole="button" accessibilityState={{ selected: lang === l }}
                    style={[s.seg, lang === l && s.segOn]}>
                    <Text {...DYNAMIC_TYPE} style={[s.segTxt, lang === l && { color: V2T.text }]}>
                      {l === "en" ? "English" : "हिंदी"}
                    </Text>
                  </Pressable>
                ))}
              </View>
            </View>,
            // anonymous trip donation — first-class action, explained in one
            // line, one tap off (doc 07 §3)
            <View key="donate">
              {menuRow({
                glyph: "wind", label: t("settingsShareData", lang),
                hint: t("shareDataHint", lang), hideChevron: true,
                onPress: () => onSettings({ share: !settings.share }),
                trailing: (
                  <Switch value={settings.share}
                    onValueChange={(v) => onSettings({ share: v })}
                    accessibilityLabel={t("settingsShareData", lang)}
                    trackColor={{ false: V2T.line, true: V2T.accent }} thumbColor={V2T.surface} />
                ),
              })}
            </View>,
            // settings — full screen when mounted; the inline expander stays
            // as the fallback path (voice · units · morning alert)
            <View key="settings">
              {menuRow({
                glyph: "layers", label: t("sidebarSettings", lang),
                onPress: () => (onFullSettings ? onFullSettings() : toggle("settings")),
                open: onFullSettings ? undefined : section === "settings",
              })}
              {!onFullSettings && section === "settings" && panel(
                <>
                  {switchRow("settingsVoice", settings.voice, (v) => onSettings({ voice: v }))}
                  <View style={s.subRow}>
                    <Text {...DYNAMIC_TYPE} style={[s.subLabel, { fontFamily: fam(lang, "reg") }]}>{t("settingsUnits", lang)}</Text>
                    <Text {...DYNAMIC_TYPE} style={s.subValue}>{t("unitsKm", lang)}</Text>
                  </View>
                  {switchRow("morningAlert", settings.brief, async (v) => {
                    if (v) onSettings({ brief: await onArmBrief() });
                    else onSettings({ brief: false });
                  })}
                </>,
              )}
            </View>,
            <View key="how">
              {menuRow({
                glyph: "info", label: t("sidebarHowAliveWorks", lang),
                onPress: () => toggle("how"), open: section === "how",
              })}
              {section === "how" && panel(
                <Text {...DYNAMIC_TYPE} style={[s.howBody, { fontFamily: fam(lang, "reg") }]}>{t("howAliveBody", lang)}</Text>,
                // SEAM(sources): claims-ledger sources link lands with doc 10 web surface
              )}
            </View>,
            onShare && (
              <View key="share">
                {menuRow({ glyph: "share", label: t("share", lang), onPress: onShare })}
              </View>
            ),
          ])}

          {/* destructive — lives in the sidebar by contract (settings-screen
              doc); first-class row so it stays reachable when the inline
              expander never mounts */}
          {card([
            menuRow({
              glyph: "trash", label: t("settingsDeleteData", lang), danger: true,
              hideChevron: true,
              onPress: () =>
                Alert.alert(t("deleteConfirmTitle", lang), t("deleteConfirmBody", lang), [
                  { text: t("cancel", lang), style: "cancel" },
                  { text: t("deleteConfirmYes", lang), style: "destructive", onPress: onDeleteData },
                ]),
            }),
          ])}
        </ScrollView>
      </Animated.View>
    </View>
  );
}

const s = StyleSheet.create({
  scrim: { position: "absolute", top: 0, bottom: 0, left: 0, right: 0, backgroundColor: V2T.scrimDeep },
  drawer: {
    position: "absolute", left: 0, top: 0, bottom: 0, width: DRAWER_W,
    backgroundColor: V2T.bg, borderRightWidth: StyleSheet.hairlineWidth, borderRightColor: V2T.line,
    shadowColor: "#000", shadowOpacity: 0.18, shadowRadius: 24, shadowOffset: { width: 4, height: 0 },
    elevation: 12,
  },

  header: {
    flexDirection: "row", alignItems: "center", justifyContent: "space-between",
    paddingHorizontal: 16, paddingBottom: 14,
    borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: V2T.line,
  },
  brandRow: { flexDirection: "row", alignItems: "center", gap: 10 },
  mark: {
    width: 30, height: 30, borderRadius: 9, backgroundColor: V2T.surface2,
    borderWidth: 1, borderColor: V2T.line, alignItems: "center", justifyContent: "center",
  },
  wordmark: { fontFamily: F.semi, fontSize: V2Type.secondary, color: V2T.text, letterSpacing: 2.4 },
  closeBtn: {
    width: 32, height: 32, borderRadius: 16, backgroundColor: V2T.surface2,
    borderWidth: StyleSheet.hairlineWidth, borderColor: V2T.line,
    alignItems: "center", justifyContent: "center",
  },

  scroll: { paddingHorizontal: 16, paddingTop: 6 },

  sectionLabel: {
    fontSize: V2Type.label, color: V2T.text3, letterSpacing: 0.8,
    textTransform: "uppercase", marginTop: 18, marginBottom: 8, marginLeft: 2,
  },
  sectionLabelFirst: { marginTop: 10 },

  card: {
    backgroundColor: V2T.surface, borderRadius: V2Radius.row,
    borderWidth: StyleSheet.hairlineWidth, borderColor: V2T.line,
    overflow: "hidden",
  },
  hair: { height: StyleSheet.hairlineWidth, backgroundColor: V2T.line, marginLeft: 50 },

  row: {
    flexDirection: "row", alignItems: "center", gap: 12,
    minHeight: 50, paddingHorizontal: 14, paddingVertical: 10,
  },
  rowPressed: { backgroundColor: V2T.surface2 },
  rowDangerPress: { backgroundColor: "#FBEAEA" },
  rowIcon: { width: 24, alignItems: "center" },
  rowMid: { flex: 1 },
  rowLabel: { fontSize: V2Type.secondary, color: V2T.text },
  rowSub: { fontFamily: F.reg, fontSize: V2Type.label, color: V2T.text3, marginTop: 1 },
  rowHint: { fontFamily: F.reg, fontSize: V2Type.label, color: V2T.text3, marginTop: 3, lineHeight: 17 },

  panel: {
    marginHorizontal: 8, marginBottom: 8, borderRadius: 10,
    backgroundColor: V2T.surface2, paddingVertical: 2,
  },
  subRow: {
    flexDirection: "row", alignItems: "center", gap: 10,
    minHeight: 44, paddingHorizontal: 12, paddingVertical: 9,
  },
  subLabel: { flex: 1, fontSize: V2Type.secondary, color: V2T.text },
  subValue: { fontFamily: F.reg, fontSize: V2Type.label, color: V2T.text3 },
  miniBtn: { padding: 6 },
  miniAction: { fontFamily: F.med, fontSize: V2Type.label, color: V2T.accent },

  chipWrap: { flexDirection: "row", flexWrap: "wrap", gap: 8, padding: 10 },
  chip: {
    flexDirection: "row", alignItems: "center", gap: 7,
    paddingHorizontal: 12, paddingVertical: 8,
    borderRadius: V2Radius.pill, borderWidth: 1, borderColor: V2T.line,
  },
  chipOn: { borderColor: V2T.accent, backgroundColor: V2T.accentTint },
  chipTxt: { fontSize: V2Type.label, color: V2T.text },

  todayRow: { flexDirection: "row", alignItems: "stretch" },
  statCol: { flex: 1, paddingHorizontal: 16, paddingVertical: 16 },
  statHead: { flexDirection: "row", alignItems: "center", gap: 6 },
  statCap: { fontFamily: F.reg, fontSize: V2Type.label, color: V2T.text2 },
  statNum: { fontFamily: F.semi, fontSize: 30, color: V2T.text, lineHeight: 36, marginTop: 6 },
  statCmp: { fontFamily: F.reg, fontSize: V2Type.label, color: V2T.text3, marginTop: 6 },
  statDiv: { width: StyleSheet.hairlineWidth, backgroundColor: V2T.line, marginVertical: 14 },

  weekRow: { flexDirection: "row", alignItems: "flex-end", paddingHorizontal: 12, paddingVertical: 14 },
  dayCol: { flex: 1, alignItems: "center" },
  dayBarWrap: { height: 46, justifyContent: "flex-end" },
  dayBar: { width: 10, borderRadius: 4 },
  dayLabel: { fontFamily: F.reg, fontSize: 10, color: V2T.text3, marginTop: 6 },

  trip: {
    flexDirection: "row", alignItems: "center", gap: 12,
    minHeight: 52, paddingHorizontal: 14, paddingVertical: 10,
  },
  tripMid: { flex: 1 },
  tripTxt: { fontSize: V2Type.secondary, color: V2T.text },
  tripMeta: { fontFamily: F.reg, fontSize: V2Type.label, color: V2T.text3, marginTop: 2 },
  tripNum: { fontFamily: F.semi, fontSize: V2Type.secondary, color: V2T.text2 },

  segWrap: {
    flexDirection: "row", borderRadius: V2Radius.pill,
    borderWidth: 1, borderColor: V2T.line, overflow: "hidden",
  },
  seg: { paddingHorizontal: 12, paddingVertical: 6 },
  segOn: { backgroundColor: V2T.surface2 },
  segTxt: { fontFamily: F.med, fontSize: V2Type.label, color: V2T.text3 },
  langBadge: {
    width: 24, height: 24, borderRadius: 7, backgroundColor: V2T.surface2,
    borderWidth: 1, borderColor: V2T.line, alignItems: "center", justifyContent: "center",
  },
  langBadgeTxt: { fontFamily: F.semi, fontSize: 10, color: V2T.text2 },

  howBody: {
    fontSize: V2Type.secondary, color: V2T.text2, lineHeight: 22,
    paddingHorizontal: 12, paddingVertical: 10,
  },
});
