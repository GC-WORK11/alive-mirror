/** Sidebar — full-height milk drawer from the ☰ in the search bar
 * (doc 02 §sidebar, items 1–8). Rules enforced here:
 *  - no stats dashboard beyond Today + This week
 *  - nothing appears without data — no fake numbers, ever
 *  - every consumer string goes through t() (en + hi).
 * r5 pass: distributed tile rhythm — stats land as spaced frost tiles
 * (the admin district-tile spacing the owner likes), saved places and
 * the daily actions are a 2-col tile grid, vehicle choice expands into
 * an icon grid under its own tile. Sections rise in with a stagger on
 * open; every tile gives press feedback. */
import React, { useEffect, useMemo, useState } from "react";
import {
  Alert, Animated, BackHandler, Dimensions, LayoutAnimation, Pressable,
  ScrollView, StyleSheet, Switch, Text, View,
} from "react-native";
import { F, NUM, V2Elev, V2Radius, V2T, V2Type, cigOf, fam, famMono, famSerif } from "../../theme";
import { DYNAMIC_TYPE, useReduceMotion } from "../../a11y";
import { tick } from "../../haptics";
import { Icon, vehicleGlyph, type Glyph } from "../../icons";
import { approx, doseUgRound, modeLabel, placeNameLabel, t, type Lang } from "../../i18n/strings";
import { stats as ledgerStats, weekStats, type Trip } from "../../store/ledger";
import type { SavedPlace, ShellSettings } from "./settings";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { bump, jank } from "../../perf";

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

type Section = "vehicle" | "settings" | "how" | null;

/** Staggered rise-in for a drawer section — each tile group fades and
 *  drifts up ~14px as the drawer opens. One-shot per open, JS driver
 *  (RN 0.86 native-detach guard — see ui.tsx Sheet). Skipped entirely
 *  under reduce-motion. */
function Rise({ i, open, children }: { i: number; open: boolean; children: React.ReactNode }) {
  const reduce = useReduceMotion();
  const [v] = useState(() => new Animated.Value(0));
  const [ty] = useState(() => v.interpolate({ inputRange: [0, 1], outputRange: [14, 0] }));
  useEffect(() => {
    if (reduce) { v.setValue(1); return; }
    if (open) {
      v.setValue(0);
      Animated.timing(v, {
        toValue: 1, duration: 260, delay: 60 + i * 55, useNativeDriver: false,
      }).start();
    }
  }, [open, i, reduce, v]);
  return (
    <Animated.View style={{ opacity: v, transform: [{ translateY: ty }] }}>
      {children}
    </Animated.View>
  );
}

function SidebarInner({
  open, onClose, trips, lang, settings, onSettings, onDeleteData,
  onArmBrief, onNavigate, currentDest, onDelhiToday, onTripReceipt,
  onFullSettings, onLang, onShare, onShareTrip, onPickPlace,
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
  onTripReceipt?: (tr: Trip) => void; // opens the trips ledger (App wires the
                                     // modal — the arg is kept for a future
                                     // deep-link into one trip)
  onFullSettings?: () => void;       // opens the dedicated SettingsScreen
  onLang?: (l: Lang) => void;        // SEAM(lang): dedicated language callback —
                                     // falls back to onSettings({lang}) when unwired
  onShare?: () => void;              // SEAM(share): system share of the app —
                                     // the row stays hidden until wired
  onShareTrip?: (tr: Trip) => void;  // SEAM(share-trip): share one trip's
                                     // numbers — trailing affordance per row
  onPickPlace?: (slot: "home" | "work") => void; // SEAM(set-place): search-pick
                                     // a place for an unset home/work slot
}) {
  bump("shell.Sidebar");
  const [slide] = useState(() => new Animated.Value(-DRAWER_W));
  /* stable interpolation node — inline re-creation trips RN 0.86's
     animated-props detach path (see ui.tsx Sheet) */
  const [scrimOp] = useState(() =>
    slide.interpolate({ inputRange: [-DRAWER_W, 0], outputRange: [0, 1] }));
  const [section, setSection] = useState<Section>(null);
  const insets = useSafeAreaInsets();
  const reduceMotion = useReduceMotion();
  const toggle = (k: Section) => {
    /* option grid mounts/unmounts under the tile — ease it open like the
       settings expanders (off under reduce-motion) */
    if (!reduceMotion) LayoutAnimation.configureNext(LayoutAnimation.Presets.easeInEaseOut);
    setSection((s) => (s === k ? null : k));
  };

  // drawer stays mounted off-canvas; the wrapper swallows touches when closed
  // NB: JS driver — RN 0.86's native-animated detach path segfaults the
  // sheet flow (see ui.tsx Sheet for the same guard)
  /* the live translateX comes off once the drawer has slid home — a
     residual transform on the drawer's container swallowed drag gestures
     on Android 15 while taps still landed (emulator drive, D1). Static
     post-settle style is visually identical; closing re-arms it. */
  const [openSettled, setOpenSettled] = useState(false);
  const [wasOpen, setWasOpen] = useState(open);
  if (open !== wasOpen) {
    /* sanctioned render-phase reset — closing re-arms the spring */
    setWasOpen(open);
    setOpenSettled(false);
  }
  useEffect(() => {
    jank(open ? "drawer.open" : "drawer.close");
    Animated.spring(slide, {
      toValue: open ? 0 : -DRAWER_W, damping: 22, stiffness: 220, useNativeDriver: false,
    }).start(({ finished }) => {
      if (finished && open) setOpenSettled(true);
    });
  }, [open, slide]);

  /* Android hardware BACK closes the drawer — this overlay has no Modal
     onRequestClose, so without it BACK fell through and exited the app
     (Android forensic find) */
  useEffect(() => {
    if (!open) return;
    const sub = BackHandler.addEventListener("hardwareBackPress", () => {
      onClose();
      return true;
    });
    return () => sub.remove();
  }, [open, onClose]);

  const st = useMemo(() => ledgerStats(trips), [trips]);
  const week = useMemo(() => weekStats(trips, undefined, lang), [trips, lang]);
  const yesterdayUg = useMemo(() => {
    const d = new Date(); d.setDate(d.getDate() - 1);
    const k = dayKey(d.getTime());
    return trips.filter((x) => dayKey(x.ts) === k).reduce((s, x) => s + x.dose_ug, 0);
  }, [trips]);
  const recent = useMemo(() => [...trips].sort((a, b) => b.ts - a.ts).slice(0, 5), [trips]);
  const todayCig = cigOf(st.todayUg) ?? 0;
  /* cigarette-equivalence is opt-in — the drawer reads µg unless the
     user turns on "show cigarette comparison" in settings */
  const showCig = settings.show_cig === true;
  // doc 02 §sidebar-1's second number — shown only when today's trips carry
  // real emit_kg readings (SEAM(emissions) rows predate the field).
  const todayKg = useMemo(
    () => Math.round(st.today.reduce((sum, x) => sum + (x.emit_kg ?? 0), 0) * 10) / 10,
    [st],
  );
  const weekMax = Math.max(...week.days.map((d) => d.ug), 1);

  const setLang = (l: Lang) => (onLang ? onLang(l) : onSettings({ lang: l }));

  /** Section heading — small-caps caption, the drawer's outer rhythm mark. */
  const sectionLabel = (text: string, first = false) => (
    <Text {...DYNAMIC_TYPE} style={[s.sectionLabel, first && s.sectionLabelFirst,
      { fontFamily: fam(lang, "semi") }]}>{text}</Text>
  );

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
          {p.sub ? <Text {...DYNAMIC_TYPE} style={[s.rowSub, { fontFamily: fam(lang, "reg") }]} numberOfLines={1}>{p.sub}</Text> : null}
          {p.hint ? <Text {...DYNAMIC_TYPE} style={[s.rowHint, { fontFamily: fam(lang, "reg") }]}>{p.hint}</Text> : null}
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
      <Pressable onPress={() => { tick(); p.onPress!(); }} accessibilityRole="button"
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
  const card = (items: React.ReactNode[], marginTop = 10) => {
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

  /** The admin district-tile grammar — a frosted square-ish tile: icon badge,
   *  label, then a value or affordance. Tappable tiles get press feedback
   *  (dips into the accent-tint glass). */
  const gridTile = (p: {
    glyph: Glyph; label: string; value: string; valueAccent?: boolean;
    onPress?: () => void; chevron?: boolean; open?: boolean;
    corner?: React.ReactNode; a11y?: string; disabled?: boolean;
  }) => (
    <Pressable disabled={!p.onPress} onPress={p.onPress ? () => { tick(); p.onPress!(); } : undefined}
      accessibilityRole={p.onPress ? "button" : undefined}
      accessibilityState={p.open != null ? { expanded: p.open } : p.disabled ? { disabled: true } : undefined}
      accessibilityLabel={p.a11y ?? `${p.label} — ${p.value}`}
      style={({ pressed }) => [s.gridTile, pressed && !!p.onPress && s.gridTileDown]}>
      <View style={s.tileTop}>
        <View style={s.tileIcon}>
          <Icon name={p.glyph} color={V2T.accent} size={19} filled={p.open} />
        </View>
        {p.corner}
        {p.chevron && !p.corner && (
          <View style={{ transform: [{ rotate: p.open ? "90deg" : "0deg" }] }}>
            <Icon name="chevron" color={V2T.text3} size={14} />
          </View>
        )}
      </View>
      <Text {...DYNAMIC_TYPE} style={[s.tileLabel, { fontFamily: fam(lang, "reg") }]} numberOfLines={1}>
        {p.label}
      </Text>
      <Text {...DYNAMIC_TYPE} style={[s.tileValue, { fontFamily: fam(lang, "med") },
        p.valueAccent && { color: V2T.accent }]} numberOfLines={1}>
        {p.value}
      </Text>
    </Pressable>
  );

  /** A saved-place tile — tap navigates when set, picks when not; the
   *  corner slot carries the clear/set affordance. */
  const placeTile = (slot: "home" | "work") => {
    const place = settings[slot];
    const labelKey = slot === "home" ? "home" : "work";
    const label = t(labelKey, lang);
    const tap = place
      ? () => { onNavigate(place); onClose(); }
      : onPickPlace ? () => onPickPlace(slot)
        : currentDest ? () => onSettings({ [slot]: currentDest })
          : undefined;
    return (
      <View key={slot} style={{ flex: 1 }}>
        {gridTile({
          glyph: slot,
          label,
          value: place ? place.name : currentDest && !place && !onPickPlace ? t("setCurrentDest", lang) : t("setPlace", lang),
          valueAccent: !place,
          onPress: tap,
          disabled: !tap,
          a11y: place ? `${label} — ${place.name}` : `${label} — ${t("setPlace", lang)}`,
          corner: place ? (
            <Pressable hitSlop={10} onPress={() => onSettings({ [slot]: null })}
              accessibilityRole="button" accessibilityLabel={t("a11yClearSaved", lang)}
              style={({ pressed }) => [s.tileCorner, pressed && { opacity: 0.6 }]}>
              <Icon name="close" color={V2T.text3} size={13} />
            </Pressable>
          ) : undefined,
        })}
      </View>
    );
  };

  const switchRow = (labelKey: Parameters<typeof t>[0], value: boolean,
    onValue: (v: boolean) => void, hintKey?: Parameters<typeof t>[0]) => (
    <View style={s.subRow}>
      <View style={{ flex: 1 }}>
        <Text {...DYNAMIC_TYPE} style={[s.subLabel, { fontFamily: fam(lang, "reg") }]}>{t(labelKey, lang)}</Text>
        {hintKey ? <Text {...DYNAMIC_TYPE} style={[s.rowHint, { fontFamily: fam(lang, "reg") }]}>{t(hintKey, lang)}</Text> : null}
      </View>
      {/* light-theme switch: white knob on the line/accent track —
          thumbColor=V2T.text left an ink blob on the light track */}
      <Switch value={value} onValueChange={onValue} accessibilityLabel={t(labelKey, lang)}
        trackColor={{ false: V2T.line, true: V2T.accent }} thumbColor={V2T.surface} />
    </View>
  );

  const tripRow = (tr: Trip, i: number) => (
    <Pressable key={`${tr.ts}-${i}`} disabled={!onTripReceipt}
      onPress={() => { tick(); onTripReceipt?.(tr); }}
      accessibilityRole={onTripReceipt ? "button" : undefined}
      accessibilityState={{ disabled: !onTripReceipt }}
      accessibilityLabel={`${placeNameLabel(tr.from, lang)} — ${placeNameLabel(tr.to, lang)}`}
      style={({ pressed }) => [s.trip, pressed && !!onTripReceipt && s.rowPressed]}>
      <View style={s.tripIcon}>
        <Icon name={vehicleGlyph(tr.vehicle)} color={V2T.text2} size={18} />
      </View>
      <View style={s.tripMid}>
        <Text {...DYNAMIC_TYPE} style={[s.tripTxt, { fontFamily: fam(lang, "med") }]} numberOfLines={1}>
          {placeNameLabel(tr.from, lang)} → {placeNameLabel(tr.to, lang)}
        </Text>
        <Text {...DYNAMIC_TYPE} style={[s.tripMeta, { fontFamily: fam(lang, "reg") }]}>{modeLabel(tr.vehicle, tr.label, lang)} · {timeAgo(tr.ts)}</Text>
      </View>
      <Icon name="dust" color={V2T.text3} size={13} />
      <Text {...DYNAMIC_TYPE} style={[s.tripNum, NUM, { fontFamily: famMono(lang, "med") }]}>
        {t("doseUg", lang, { n: approx(doseUgRound(tr.dose_ug)) })}
      </Text>
      {onShareTrip && (
        <Pressable hitSlop={8} onPress={() => onShareTrip(tr)}
          accessibilityRole="button"
          accessibilityLabel={`${t("share", lang)} — ${placeNameLabel(tr.from, lang)} ${placeNameLabel(tr.to, lang)}`}
          style={({ pressed }) => [s.miniBtn, pressed && { opacity: 0.6 }]}>
          <Icon name="share" color={V2T.text3} size={15} />
        </Pressable>
      )}
    </Pressable>
  );

  let rise = 0; // stagger order across the scroll content

  return (
    <View style={[StyleSheet.absoluteFill, s.overlayZ]} pointerEvents={open ? "auto" : "none"}>
      <Animated.View style={[s.scrim, {
        opacity: scrimOp,
      }]}>
        <Pressable style={StyleSheet.absoluteFill} onPress={onClose}
          accessibilityRole="button" accessibilityLabel={t("settingsClose", lang)} />
      </Animated.View>
      <Animated.View style={[s.drawer, openSettled ? null : { transform: [{ translateX: slide }] }]}>
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
          {/* 1 — Today: breathed / put-out as twin hero tiles
              (doc 02 §sidebar-1 — both numbers, never fake) */}
          {st.todayUg > 0 && (
            <Rise i={rise++} open={open}>
              {sectionLabel(t("sidebarToday", lang), true)}
              <View style={s.tileRow}>
                <View style={s.statTile}>
                  <View style={s.statHead}>
                    <Icon name="dust" color={V2T.text3} size={15} />
                    <Text {...DYNAMIC_TYPE} style={[s.statCap, { fontFamily: fam(lang, "reg") }]}>{t("breathed", lang)}</Text>
                  </View>
                  <Text {...DYNAMIC_TYPE} style={[s.statNum, NUM, { fontFamily: famSerif(lang, "semi") }]}>
                    {t("doseUg", lang, { n: approx(doseUgRound(st.todayUg)) })}
                  </Text>
                  {/* yesterday delta + opt-in cigarette equivalence sit in
                      the caption row — µg keeps the tile number */}
                  {yesterdayUg > 0 && (
                    <Text {...DYNAMIC_TYPE} style={[s.statCmp, { fontFamily: fam(lang, "reg") }]}>
                      {t(st.todayUg <= yesterdayUg ? "lessThanYesterday" : "moreThanYesterday", lang, {
                        p: Math.abs(Math.round((1 - st.todayUg / yesterdayUg) * 100)),
                      })}
                    </Text>
                  )}
                  {showCig && todayCig > 0 && (
                    <Text {...DYNAMIC_TYPE} style={[s.statCmp, { fontFamily: fam(lang, "reg") }]}>
                      {t("tripsCigs", lang, { n: approx(todayCig > 0 && todayCig < 0.01 ? 0.01 : todayCig) })}
                    </Text>
                  )}
                </View>
                {todayKg > 0 && (
                  <View style={s.statTile}>
                    <View style={s.statHead}>
                      <Icon name="smoke" color={V2T.text3} size={15} />
                      <Text {...DYNAMIC_TYPE} style={[s.statCap, { fontFamily: fam(lang, "reg") }]}>{t("putOut", lang)}</Text>
                    </View>
                    <Text {...DYNAMIC_TYPE} style={[s.statNum, NUM, { fontFamily: famSerif(lang, "semi") }]}>{t("nav_kg", lang, { n: approx(todayKg) })}</Text>
                  </View>
                )}
              </View>
            </Rise>
          )}

          {/* 2 — This week: 7 thin bars + the honest rollup line */}
          {week.totalTrips > 0 && (
            <Rise i={rise++} open={open}>
              {sectionLabel(t("sidebarThisWeek", lang), st.todayUg === 0)}
              <View style={s.tile}>
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
                      <Text {...DYNAMIC_TYPE} style={[s.dayLabel, { fontFamily: fam(lang, "reg") }]}>{d.label}</Text>
                    </View>
                  ))}
                </View>
                <Text {...DYNAMIC_TYPE} style={[s.weekCap, { fontFamily: fam(lang, "reg") }]}>
                  {t(week.totalTrips === 1 ? "tripsCountOne" : "tripsCount", lang, { n: week.totalTrips })}
                  {" · "}
                  {t("doseUg", lang, { n: approx(doseUgRound(week.weekUg)) })}
                  {showCig
                    ? ` · ${t("tripsCigs", lang, { n: approx(week.weekCigEq > 0 && week.weekCigEq < 0.01 ? 0.01 : week.weekCigEq) })}`
                    : ""}
                </Text>
              </View>
            </Rise>
          )}

          {/* 3 — the district-tile wall: saved places + the two daily
              actions, four equal tiles in the admin 2-col rhythm */}
          <Rise i={rise++} open={open}>
            {sectionLabel(t("sidebarSavedPlaces", lang), st.todayUg === 0 && week.totalTrips === 0)}
            <View style={s.tileRow}>{placeTile("home")}{placeTile("work")}</View>
            {(onDelhiToday || true) && (
              <View style={[s.tileRow, { marginTop: 10 }]}>
                {onDelhiToday ? (
                  <View style={{ flex: 1 }}>
                    {gridTile({
                      glyph: "city", label: t("sidebarDelhiToday", lang),
                      value: t("delhiTodayOpen", lang), valueAccent: false,
                      onPress: () => { onDelhiToday(); },
                      chevron: true,
                    })}
                  </View>
                ) : <View style={{ flex: 1 }} />}
                <View style={{ flex: 1 }}>
                  {gridTile({
                    glyph: (settings.vehicle ? vehicleGlyph(settings.vehicle) : "bike") as Glyph,
                    label: t("sidebarMyVehicle", lang),
                    value: settings.vehicle ? t(vehicleLabelKey(settings.vehicle), lang) : t("notSet", lang),
                    onPress: () => toggle("vehicle"), chevron: true, open: section === "vehicle",
                  })}
                </View>
              </View>
            )}
            {section === "vehicle" && (
              <View style={s.optGrid}>
                {VEHICLES.map((v) => {
                  const sel = settings.vehicle === v.key;
                  return (
                    <Pressable key={v.key} accessibilityRole="button"
                      accessibilityState={{ selected: sel }}
                      onPress={() => { tick(); onSettings({ vehicle: v.key }); setSection(null); }}
                      style={({ pressed }) => [
                        s.optTile, sel && s.optTileOn, pressed && !sel && { opacity: 0.7 },
                      ]}>
                      <Icon name={vehicleGlyph(v.key)} color={sel ? V2T.accent : V2T.text2} size={20} />
                      <Text {...DYNAMIC_TYPE} style={[s.optTileTxt, { fontFamily: fam(lang, "reg") },
                        sel && { color: V2T.accent }]}>
                        {t(v.labelKey, lang)}
                      </Text>
                    </Pressable>
                  );
                })}
              </View>
            )}
          </Rise>

          {/* 4 — Trips: tap → the ledger; "all saved trips" lands the
              full ledger too */}
          {recent.length > 0 && (
            <Rise i={rise++} open={open}>
              <View style={s.tripsHead}>
                <Text {...DYNAMIC_TYPE} style={[s.sectionLabel, { fontFamily: fam(lang, "semi"), marginBottom: 0, marginTop: 0 }]}>
                  {t("sidebarTrips", lang)}
                </Text>
                {onTripReceipt && (
                  <Pressable hitSlop={8} onPress={() => { tick(); onTripReceipt(recent[0]); }}
                    accessibilityRole="button" accessibilityLabel={t("ledgerAllTime", lang)}
                    style={({ pressed }) => [s.allBtn, pressed && { opacity: 0.65 }]}>
                    <Icon name="history" color={V2T.accent} size={13} />
                    <Text {...DYNAMIC_TYPE} style={[s.allBtnTxt, { fontFamily: fam(lang, "med") }]}>{t("ledgerAllTime", lang)}</Text>
                  </Pressable>
                )}
              </View>
              {card(recent.map((tr, i) => tripRow(tr, i)), 8)}
            </Rise>
          )}

          {/* 5 — app group (language · sharing · settings · about) */}
          <Rise i={rise++} open={open}>
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
                    <Pressable key={l} onPress={() => { tick(); setLang(l); }}
                      accessibilityRole="button" accessibilityState={{ selected: lang === l }}
                      style={[s.seg, lang === l && s.segOn]}>
                      <Text {...DYNAMIC_TYPE} style={[s.segTxt, { fontFamily: fam(l, "med") }, lang === l && { color: V2T.text }]}>
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
                  glyph: "settings", label: t("sidebarSettings", lang),
                  onPress: () => (onFullSettings ? onFullSettings() : toggle("settings")),
                  open: onFullSettings ? undefined : section === "settings",
                })}
                {!onFullSettings && section === "settings" && (
                  <View style={s.panel}>
                    {switchRow("settingsVoice", settings.voice, (v) => onSettings({ voice: v }))}
                    {switchRow("settingsShowCig", settings.show_cig, (v) => onSettings({ show_cig: v }), "settingsShowCigHint")}
                    <View style={s.subRow}>
                      <Text {...DYNAMIC_TYPE} style={[s.subLabel, { fontFamily: fam(lang, "reg") }]}>{t("settingsUnits", lang)}</Text>
                      <Text {...DYNAMIC_TYPE} style={[s.subValue, { fontFamily: fam(lang, "reg") }]}>{t("unitsKm", lang)}</Text>
                    </View>
                    {switchRow("morningAlert", settings.brief, async (v) => {
                      if (v) onSettings({ brief: await onArmBrief() });
                      else onSettings({ brief: false });
                    })}
                  </View>
                )}
              </View>,
              <View key="how">
                {menuRow({
                  glyph: "info", label: t("sidebarHowAliveWorks", lang),
                  onPress: () => toggle("how"), open: section === "how",
                })}
                {section === "how" && (
                  <View style={s.panel}>
                    <Text {...DYNAMIC_TYPE} style={[s.howBody, { fontFamily: fam(lang, "reg") }]}>{t("howAliveBody", lang)}</Text>
                  </View>
                )}
              </View>,
              onShare && (
                <View key="share">
                  {menuRow({ glyph: "share", label: t("share", lang), onPress: onShare })}
                </View>
              ),
            ])}
          </Rise>

          {/* destructive — a quiet row under the groups, not a card:
              reachable, low-key, out of the accidental-tap path */}
          <Rise i={rise++} open={open}>
            <Pressable
              onPress={() =>
                Alert.alert(t("deleteConfirmTitle", lang), t("deleteConfirmBody", lang), [
                  { text: t("cancel", lang), style: "cancel" },
                  { text: t("deleteConfirmYes", lang), style: "destructive", onPress: onDeleteData },
                ])}
              accessibilityRole="button" accessibilityLabel={t("settingsDeleteData", lang)}
              style={({ pressed }) => [s.deleteRow, pressed && { opacity: 0.6 }]}>
              <Icon name="trash" color={V2T.breath3} size={15} />
              <Text {...DYNAMIC_TYPE} style={[s.deleteTxt, { fontFamily: fam(lang, "reg") }]}>
                {t("settingsDeleteData", lang)}
              </Text>
            </Pressable>
          </Rise>
        </ScrollView>
      </Animated.View>
    </View>
  );
}

export const Sidebar = React.memo(SidebarInner);

const s = StyleSheet.create({
  /* elevation must beat HomeScreen's 24 — Android dispatches sibling touches
     by z before mount order, so the still-mounted home scroll swallowed the
     drawer's drags. iOS ignores it. */
  overlayZ: { elevation: 30 },
  scrim: { position: "absolute", top: 0, bottom: 0, left: 0, right: 0, backgroundColor: V2T.scrimDeep },
  drawer: {
    position: "absolute", left: 0, top: 0, bottom: 0, width: DRAWER_W,
    backgroundColor: V2T.glassDeep, borderRightWidth: 1, borderRightColor: V2T.glassEdge,
    ...V2Elev.pop,
  },

  header: {
    flexDirection: "row", alignItems: "center", justifyContent: "space-between",
    paddingHorizontal: 16, paddingBottom: 14,
    borderBottomWidth: 1, borderBottomColor: V2T.glassLine,
  },
  brandRow: { flexDirection: "row", alignItems: "center", gap: 10 },
  mark: {
    width: 30, height: 30, borderRadius: 9, backgroundColor: V2T.glassSoft,
    borderWidth: 1, borderColor: V2T.glassLine, alignItems: "center", justifyContent: "center",
  },
  wordmark: { fontFamily: F.semi, fontSize: V2Type.secondary, color: V2T.text, letterSpacing: 2.4 },
  closeBtn: {
    width: 32, height: 32, borderRadius: 16, backgroundColor: V2T.glassSoft,
    borderWidth: 1, borderColor: V2T.glassLine,
    alignItems: "center", justifyContent: "center",
  },

  scroll: { paddingHorizontal: 14, paddingTop: 4 },

  sectionLabel: {
    fontSize: V2Type.label, color: V2T.text3, letterSpacing: 0.8,
    textTransform: "uppercase", marginTop: 18, marginBottom: 8, marginLeft: 2,
  },
  sectionLabelFirst: { marginTop: 12 },

  /* ---- the tile grammar — inner frost tiles on the milk pane,
     admin-district rhythm: 10px gaps, 12px radius, generous padding ---- */
  tileRow: { flexDirection: "row", gap: 10 },
  tile: {
    backgroundColor: V2T.glassSoft, borderRadius: V2Radius.row, borderCurve: "continuous",
    borderWidth: 1, borderColor: V2T.glassLine,
  },
  gridTile: {
    backgroundColor: V2T.glassSoft, borderRadius: V2Radius.row, borderCurve: "continuous",
    borderWidth: 1, borderColor: V2T.glassLine,
    paddingHorizontal: 12, paddingTop: 10, paddingBottom: 12, minHeight: 92,
  },
  gridTileDown: { backgroundColor: V2T.glassSel, borderColor: V2T.accentTint },
  tileTop: { flexDirection: "row", alignItems: "center", justifyContent: "space-between" },
  tileIcon: {
    width: 34, height: 34, borderRadius: 10,
    backgroundColor: V2T.accentWash, borderWidth: 1, borderColor: V2T.glassLine,
    alignItems: "center", justifyContent: "center",
  },
  tileCorner: { padding: 4, marginTop: -4, marginRight: -4 },
  tileLabel: { fontSize: V2Type.label, color: V2T.text3, marginTop: 10 },
  tileValue: { fontSize: V2Type.secondary, color: V2T.text, marginTop: 2 },

  /* vehicle option grid — 2-col tiles under the vehicle tile */
  optGrid: {
    flexDirection: "row", flexWrap: "wrap", gap: 8, marginTop: 10,
  },
  optTile: {
    flexBasis: "48%", flexGrow: 1, flexDirection: "row", alignItems: "center", gap: 9,
    paddingHorizontal: 12, paddingVertical: 12, minHeight: 48,
    borderRadius: V2Radius.row, borderCurve: "continuous",
    borderWidth: 1, borderColor: V2T.glassLine, backgroundColor: V2T.glassSoft,
  },
  optTileOn: { borderColor: V2T.accent, backgroundColor: V2T.glassSel },
  optTileTxt: { fontSize: V2Type.label, color: V2T.text, flexShrink: 1 },

  card: {
    backgroundColor: V2T.glassSoft, borderRadius: V2Radius.row, borderCurve: "continuous",
    borderWidth: 1, borderColor: V2T.glassLine,
    overflow: "hidden",
  },
  hair: { height: StyleSheet.hairlineWidth, backgroundColor: V2T.glassLine, marginLeft: 50 },

  row: {
    flexDirection: "row", alignItems: "center", gap: 12,
    minHeight: 52, paddingHorizontal: 14, paddingVertical: 10,
  },
  rowPressed: { backgroundColor: "rgba(255,255,255,0.55)" },
  rowDangerPress: { backgroundColor: "#FBEAEA" },
  rowIcon: { width: 24, alignItems: "center" },
  rowMid: { flex: 1 },
  rowLabel: { fontSize: V2Type.secondary, color: V2T.text },
  rowSub: { fontFamily: F.reg, fontSize: V2Type.label, color: V2T.text3, marginTop: 1 },
  rowHint: { fontFamily: F.reg, fontSize: V2Type.label, color: V2T.text3, marginTop: 3, lineHeight: 17 },

  panel: {
    marginHorizontal: 8, marginBottom: 8, borderRadius: 10,
    backgroundColor: V2T.glassFaint, borderWidth: 1, borderColor: V2T.glassLine, paddingVertical: 2,
  },
  subRow: {
    flexDirection: "row", alignItems: "center", gap: 10,
    minHeight: 44, paddingHorizontal: 12, paddingVertical: 9,
  },
  subLabel: { flex: 1, fontSize: V2Type.secondary, color: V2T.text },
  subValue: { fontFamily: F.reg, fontSize: V2Type.label, color: V2T.text3 },
  miniBtn: { padding: 6 },
  miniAction: { fontFamily: F.med, fontSize: V2Type.label, color: V2T.accent },

  /* today hero tiles */
  statTile: {
    flex: 1, backgroundColor: V2T.glassSoft, borderRadius: V2Radius.row, borderCurve: "continuous",
    borderWidth: 1, borderColor: V2T.glassLine,
    paddingHorizontal: 14, paddingVertical: 14,
  },
  statHead: { flexDirection: "row", alignItems: "center", gap: 6 },
  statCap: { fontFamily: F.reg, fontSize: V2Type.label, color: V2T.text2 },
  statNum: { fontSize: 30, color: V2T.text, lineHeight: 36, marginTop: 8 },
  statCmp: { fontFamily: F.reg, fontSize: V2Type.label, color: V2T.text3, marginTop: 6 },

  weekRow: { flexDirection: "row", alignItems: "flex-end", paddingHorizontal: 12, paddingTop: 14 },
  weekCap: {
    fontSize: V2Type.label, color: V2T.text3,
    paddingHorizontal: 14, paddingTop: 8, paddingBottom: 11,
    borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: V2T.glassLine, marginTop: 10,
  },
  dayCol: { flex: 1, alignItems: "center" },
  dayBarWrap: { height: 46, justifyContent: "flex-end" },
  dayBar: { width: 10, borderRadius: 4 },
  dayLabel: { fontFamily: F.reg, fontSize: 10, color: V2T.text3, marginTop: 6 },

  tripsHead: {
    flexDirection: "row", alignItems: "center", justifyContent: "space-between",
    marginTop: 18, marginBottom: 0, marginLeft: 2,
  },
  allBtn: {
    flexDirection: "row", alignItems: "center", gap: 5,
    paddingHorizontal: 10, paddingVertical: 6, borderRadius: V2Radius.row,
    backgroundColor: V2T.glassSoft, borderWidth: 1, borderColor: V2T.glassLine,
  },
  allBtnTxt: { fontSize: V2Type.label, color: V2T.accent },

  trip: {
    flexDirection: "row", alignItems: "center", gap: 12,
    minHeight: 52, paddingHorizontal: 14, paddingVertical: 10,
  },
  tripIcon: {
    width: 32, height: 32, borderRadius: 9, backgroundColor: V2T.glassFaint,
    borderWidth: 1, borderColor: V2T.glassLine,
    alignItems: "center", justifyContent: "center",
  },
  tripMid: { flex: 1 },
  tripTxt: { fontSize: V2Type.secondary, color: V2T.text },
  tripMeta: { fontSize: V2Type.label, color: V2T.text3, marginTop: 2 },
  tripNum: { fontSize: V2Type.secondary, color: V2T.text2 },

  segWrap: {
    flexDirection: "row", borderRadius: V2Radius.row,
    borderWidth: 1, borderColor: V2T.glassLine, overflow: "hidden",
    backgroundColor: V2T.glassSoft,
  },
  seg: { paddingHorizontal: 12, paddingVertical: 6 },
  segOn: { backgroundColor: V2T.glassSel },
  segTxt: { fontFamily: F.med, fontSize: V2Type.label, color: V2T.text3 },
  langBadge: {
    width: 24, height: 24, borderRadius: 7, backgroundColor: V2T.accentWash,
    borderWidth: 1, borderColor: V2T.glassLine, alignItems: "center", justifyContent: "center",
  },
  langBadgeTxt: { fontFamily: F.semi, fontSize: 10, color: V2T.text2 },

  howBody: {
    fontSize: V2Type.secondary, color: V2T.text2, lineHeight: 22,
    paddingHorizontal: 12, paddingVertical: 10,
  },

  deleteRow: {
    flexDirection: "row", alignItems: "center", justifyContent: "center", gap: 8,
    marginTop: 22, paddingVertical: 12,
  },
  deleteTxt: { fontSize: V2Type.secondary, color: V2T.breath3 },
});
