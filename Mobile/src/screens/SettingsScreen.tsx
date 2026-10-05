// S-settings — the settings surface the sidebar's section 7 grew into
// (docs/plan/02 §sidebar-7, docs/plan/07 §3, docs/plan/10).
// Contract: <SettingsScreen visible onClose lang current onChange(key,value)
//           onArmBrief? onDeleteData? />
// Controlled component — reads `current` (the persisted ShellSettings), and
// reports every edit through onChange; the parent applies the patch through
// shell/settings.saveSettings. Same Modal-sheet contract as SearchScreen:
// mounted only while visible, light V2 tokens, every string through t().
// Data sharing is explained in plain words and turns OFF in one labelled tap —
// no dark patterns (doc 07 §3).
//
// Groups: profile (vehicle) → presentation (language / voice / units) →
// privacy & sharing → notifications → about. Cards are the grouping; text
// headers render only where string keys exist today.
//
// String keys landed in strings.ts: settingsGeneral/settingsPrivacy
// (section headers), settingsVoiceHint, settingsUnitsHint.

import React, { useEffect, useState } from "react";
import {
  Alert,
  Animated,
  BackHandler,
  LayoutAnimation,
  Pressable,
  ScrollView,
  StyleSheet,
  Switch,
  Text,
  TextInput,
  View,
} from "react-native";
import { StatusBar } from "expo-status-bar";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import Constants from "expo-constants"; // transitively installed via `expo` (SDK 57)
import { F, V2Elev, V2Radius, V2T, V2Type, fam } from "../theme";
import { Icon, vehicleGlyph, type Glyph } from "../icons";
import { API, postJson } from "../components/shell/net";
import { t, type Lang, type StringKey } from "../i18n/strings";
import { a11y, DYNAMIC_TYPE, useReduceMotion } from "../a11y";
import { tick } from "../haptics";
import type { ShellSettings } from "../components/shell/settings";

/** Action seams that carry no persisted value — the parent owns what they open. */
export type SettingsActionKey = "editVehicle";

/** The change callback: persisted keys take a typed value; action keys take none. */
export interface SettingsChangeFn {
  <K extends keyof ShellSettings>(key: K, value: ShellSettings[K]): void;
  (key: SettingsActionKey): void;
}

/* Same S8 vehicle-key → label map the sidebar uses (docs/plan/02 §S8). */
const VEHICLE_LABEL: Record<string, StringKey> = {
  bike: "vehicleScooterBike",
  car: "vehicleCar",
  auto: "vehicleAuto",
  cab: "vehicleCab",
  transit: "vehicleBusMetro",
  walk: "vehicleCycleWalk",
};

/* "What we store" — doc 07 §3 privacy rules, one plain line each. */
const STORE_BULLETS: StringKey[] = [
  "settingsStoreNoAccount",
  "settingsStoreTrim",
  "settingsStoreThin",
  "settingsStoreCells",
  "settingsStoreToken",
  "settingsStoreK",
  "settingsStoreOff",
];

/* Language segments — the label text itself is the a11y label, announced in
 * each language's own voice via accessibilityLanguage. */
const LANGS: { code: Lang; name: string }[] = [
  { code: "en", name: "English" },
  { code: "hi", name: "हिंदी" },
];

type ExpandKey = "store" | "numbers" | "how" | "rate";

const VERSION = Constants.expoConfig?.version ?? null; // app.json version; null → "dev build"

/* ---------- sheet (mounted only while visible → expanders reset each open) ---------- */

function SettingsSheet({
  onClose,
  lang,
  current,
  onChange,
  onArmBrief,
  onDeleteData,
}: {
  onClose: () => void;
  lang: Lang;
  current: ShellSettings;
  onChange: SettingsChangeFn;
  onArmBrief?: () => Promise<boolean>;
  onDeleteData?: () => void;
}) {
  const [expand, setExpand] = useState<ExpandKey | null>(null);
  const reduceMotion = useReduceMotion();
  const toggle = (k: ExpandKey) => {
    tick();
    /* the body mounts/unmounts — ease it in while siblings slide
       (native path; enabled once in useShellFlow) */
    if (!reduceMotion) LayoutAnimation.configureNext(LayoutAnimation.Presets.easeInEaseOut);
    setExpand((e) => (e === k ? null : k));
  };
  // brief arming awaits OS perms — guard re-entry so a double-tap can't
  // queue two permission prompts (the row also reports busy to TalkBack).
  const [arming, setArming] = useState(false);
  const insets = useSafeAreaInsets();

  /* rate ALive·108 — quiet expander in the About card: 1–5 stars + an
     optional one-liner, POST /v2/feedback {stars, note, build}. Public,
     no token; the honest states are inline (no modal fanfare). */
  const [rateStars, setRateStars] = useState(0);
  const [rateNote, setRateNote] = useState("");
  const [rateState, setRateState] = useState<"idle" | "sending" | "ok" | "err">("idle");
  const sendRate = async () => {
    if (!rateStars || rateState === "sending") return;
    setRateState("sending");
    try {
      await postJson(`${API}/v2/feedback`, {
        stars: rateStars,
        note: rateNote.trim().slice(0, 240) || undefined,
        build: VERSION ?? "dev",
      });
      setRateState("ok");
    } catch {
      setRateState("err");   // keep stars+note so a retry loses nothing
    }
  };

  const sectionLabel = (key: StringKey) => (
    <Text
      {...DYNAMIC_TYPE}
      accessibilityRole="header"
      style={[ss.sectionLabel, { fontFamily: fam(lang, "semi") }]}
    >
      {t(key, lang)}
    </Text>
  );

  /* A switch row is ONE accessible control — the whole row is the switch
   * (≥52pt target, role "switch", checked state); the visual Switch is
   * hidden from the a11y tree so screen readers don't meet it twice. */
  const switchRow = (
    labelKey: StringKey,
    value: boolean,
    onValue: (v: boolean) => void,
    hintKey?: StringKey,
    opts?: { disabled?: boolean; busy?: boolean },
  ) => {
    const disabled = !!opts?.disabled;
    return (
      <Pressable
        onPress={() => { tick(); onValue(!value); }}
        disabled={disabled}
        {...a11y(
          t(labelKey, lang),
          hintKey ? t(hintKey, lang) : undefined,
          "switch",
          { checked: value, disabled, busy: opts?.busy, lang },
        )}
        style={({ pressed }) => [
          ss.row,
          pressed && !disabled && ss.rowPressed,
          disabled && ss.rowDisabled,
        ]}
      >
        <View style={ss.rowMid}>
          <Text {...DYNAMIC_TYPE} style={[ss.rowLabel, { fontFamily: fam(lang, "med") }]}>
            {t(labelKey, lang)}
          </Text>
          {hintKey ? (
            <Text {...DYNAMIC_TYPE} style={[ss.hint, { fontFamily: fam(lang, "reg") }]}>
              {t(hintKey, lang)}
            </Text>
          ) : null}
        </View>
        <Switch
          accessible={false}
          value={value}
          onValueChange={onValue}
          disabled={disabled}
          trackColor={{ false: V2T.line, true: V2T.accent }}
          thumbColor={V2T.surface}
        />
      </Pressable>
    );
  };

  const expander = (labelKey: StringKey, k: ExpandKey, body: React.ReactNode, icon: Glyph = "info") => (
    <View>
      <Pressable
        onPress={() => toggle(k)}
        {...a11y(t(labelKey, lang), undefined, "button", { expanded: expand === k, lang })}
        style={({ pressed }) => [ss.row, pressed && ss.rowPressed]}
      >
        <Icon name={icon} color={V2T.text2} size={20} />
        <Text
          {...DYNAMIC_TYPE}
          style={[ss.rowLabel, ss.rowMid, { fontFamily: fam(lang, "med") }]}
        >
          {t(labelKey, lang)}
        </Text>
        <View style={{ transform: [{ rotate: expand === k ? "90deg" : "0deg" }] }}>
          <Icon name="chevron" color={V2T.text3} size={16} />
        </View>
      </Pressable>
      {expand === k && <View style={ss.expandBody}>{body}</View>}
    </View>
  );

  const confirmDelete = () =>
    Alert.alert(t("deleteConfirmTitle", lang), t("deleteConfirmBody", lang), [
      { text: t("cancel", lang), style: "cancel" },
      { text: t("deleteConfirmYes", lang), style: "destructive", onPress: onDeleteData },
    ]);

  return (
    <View style={[ss.root, { marginTop: insets.top + 8 }]}>
      {/* header: back + title */}
      <View style={ss.header}>
        <Pressable
          onPress={onClose}
          {...a11y(t("settingsClose", lang), undefined, "button", { lang })}
          style={({ pressed }) => [ss.headerBtn, pressed && { opacity: 0.6 }]}
        >
          <View style={{ transform: [{ rotate: "180deg" }] }}>
            <Icon name="chevron" color={V2T.text2} size={20} />
          </View>
        </Pressable>
        <Text
          {...DYNAMIC_TYPE}
          accessibilityRole="header"
          style={[ss.title, { fontFamily: fam(lang, "semi") }]}
        >
          {t("sidebarSettings", lang)}
        </Text>
        <View style={ss.headerBtn} />
      </View>

      <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={[ss.scroll, { paddingBottom: insets.bottom + 24 }]}>
        {/* ── profile: vehicle drives every dose/emission estimate (S8) ── */}
        <View style={ss.card}>
          <Pressable
            onPress={() => { tick(); onChange("editVehicle"); }}
            {...a11y(
              t("sidebarMyVehicle", lang),
              current.vehicle
                ? t(VEHICLE_LABEL[current.vehicle] ?? "vehicleQ1", lang)
                : t("notSet", lang),
              "button",
              { lang },
            )}
            style={({ pressed }) => [ss.row, pressed && ss.rowPressed]}
          >
            <Icon name={vehicleGlyph(current.vehicle ?? "car")} color={V2T.text2} size={22} />
            <View style={ss.rowMid}>
              <Text {...DYNAMIC_TYPE} style={[ss.rowLabel, { fontFamily: fam(lang, "med") }]}>
                {t("sidebarMyVehicle", lang)}
              </Text>
              <Text {...DYNAMIC_TYPE} style={[ss.hint, { fontFamily: fam(lang, "reg") }]} numberOfLines={2}>
                {current.vehicle
                  ? `${t(VEHICLE_LABEL[current.vehicle] ?? "vehicleQ1", lang)} · ${t("settingsVehicleLike", lang)}`
                  : t("notSet", lang)}
              </Text>
            </View>
            <Text {...DYNAMIC_TYPE} style={[ss.action, { fontFamily: fam(lang, "reg") }]}>
              {t("changeLabel", lang)}
            </Text>
          </Pressable>
        </View>

        {/* ── presentation: language, guidance voice, units ── */}
        {sectionLabel("settingsGeneral")}
        <View style={ss.card}>
          <View style={ss.row}>
            <Text
              {...DYNAMIC_TYPE}
              style={[ss.rowLabel, ss.rowMid, { fontFamily: fam(lang, "med") }]}
            >
              {t("settingsLanguage", lang)}
            </Text>
            <View
              style={ss.segWrap}
              accessibilityRole="radiogroup"
              accessibilityLabel={t("settingsLanguage", lang)}
            >
              {LANGS.map(({ code, name }) => (
                <Pressable
                  key={code}
                  onPress={() => { tick(); onChange("lang", code); }}
                  {...a11y(name, undefined, "radio", { selected: lang === code, lang: code })}
                  style={[ss.seg, lang === code && ss.segOn]}
                >
                  <Text
                    {...DYNAMIC_TYPE}
                    style={[
                      ss.segTxt,
                      { fontFamily: fam(code, "med") },
                      lang === code && { color: V2T.text },
                    ]}
                  >
                    {name}
                  </Text>
                </Pressable>
              ))}
            </View>
          </View>
          <View style={ss.hairline} />
          {switchRow(
            "settingsVoice",
            current.voice,
            (v) => onChange("voice", v),
            "settingsVoiceHint",
          )}
          <View style={ss.hairline} />
          {/* cigarette-equivalence — opt-in (owner: "absolutely wrong and
              disgusting" as a headline); the dose stays in µg until on */}
          {switchRow(
            "settingsShowCig",
            current.show_cig,
            (v) => onChange("show_cig", v),
            "settingsShowCigHint",
          )}
          <View style={ss.hairline} />
          <View style={ss.row}>
            <Text
              {...DYNAMIC_TYPE}
              style={[ss.rowLabel, ss.rowMid, { fontFamily: fam(lang, "med") }]}
            >
              {t("settingsUnits", lang)}
            </Text>
            <View>
              <Text {...DYNAMIC_TYPE} style={[ss.value, { fontFamily: fam(lang, "reg") }]}>{t("unitsKm", lang)}</Text>
              <Text {...DYNAMIC_TYPE} style={[ss.hint, { fontFamily: fam(lang, "reg") }]}>{t("settingsUnitsHint", lang)}</Text>
            </View>
          </View>
        </View>

        {/* ── privacy & sharing: explained, one labelled tap off (doc 07 §3) ── */}
        {sectionLabel("settingsPrivacy")}
        <View style={ss.card}>
          {switchRow("settingsShareData", current.share, (v) => onChange("share", v))}
          <View style={ss.explainWrap}>
            <Text {...DYNAMIC_TYPE} style={[ss.explain, { fontFamily: fam(lang, "reg") }]}>
              {t("settingsShareExplain", lang)}
            </Text>
            {/* live status line — the consequence of the CURRENT choice in
                plain words: anonymous + aggregate when on, sealed when off */}
            <Text {...DYNAMIC_TYPE} style={[ss.explain, ss.explainStatus, { fontFamily: fam(lang, "reg") }]}>
              {t(current.share ? "shareDataHint" : "settingsStoreOff", lang)}
            </Text>
          </View>
          <View style={ss.hairline} />
          {expander(
            "settingsWhatWeStore",
            "store",
            <View>
              {STORE_BULLETS.map((k) => (
                <View key={k} style={ss.bulletRow}>
                  <View style={ss.bulletDot} />
                  <Text {...DYNAMIC_TYPE} style={[ss.bulletTxt, { fontFamily: fam(lang, "reg") }]}>
                    {t(k, lang)}
                  </Text>
                </View>
              ))}
            </View>,
          )}
          {/* SEAM(delete-data): renders only when the parent passes
              onDeleteData — App.tsx wires it to `deleteAll` (clearAllData +
              state reset, the same path the sidebar's confirm uses). Without
              it no destructive row sits on this surface. */}
          {onDeleteData ? (
            <>
              <View style={ss.hairline} />
              <Pressable
                onPress={confirmDelete}
                {...a11y(t("settingsDeleteData", lang), t("deleteConfirmBody", lang), "button", { lang })}
                style={({ pressed }) => [ss.row, pressed && ss.rowPressed]}
              >
                <Icon name="trash" color={V2T.breath3} size={20} />
                <Text
                  {...DYNAMIC_TYPE}
                  style={[ss.rowLabel, ss.rowMid, ss.dangerTxt, { fontFamily: fam(lang, "med") }]}
                >
                  {t("settingsDeleteData", lang)}
                </Text>
              </Pressable>
            </>
          ) : null}
        </View>

        {/* ── notifications ── */}
        {sectionLabel("settingsNotifications")}
        <View style={ss.card}>
          {switchRow("settingsDepartRemind", current.remind, (v) => onChange("remind", v), "settingsDepartRemindHint")}
          <View style={ss.hairline} />
          {switchRow(
            "morningAlert",
            current.brief,
            async (v) => {
              // arming needs OS perms + a scheduled fire — the parent owns that
              // side effect via onArmBrief; off is always a direct write.
              if (v && onArmBrief) {
                setArming(true);
                try {
                  onChange("brief", await onArmBrief());
                } finally {
                  setArming(false);
                }
              } else {
                onChange("brief", v);
              }
            },
            "settingsBriefHint",
            { disabled: arming, busy: arming },
          )}
        </View>

        {/* ── about / provenance ── */}
        {sectionLabel("settingsAbout")}
        <View style={ss.card}>
          <View style={ss.row}>
            <Text
              {...DYNAMIC_TYPE}
              style={[ss.rowLabel, ss.rowMid, { fontFamily: fam(lang, "med") }]}
            >
              {t("settingsVersion", lang)}
            </Text>
            <Text {...DYNAMIC_TYPE} style={[ss.value, { fontFamily: fam(lang, "reg") }]}>
              {VERSION ?? t("settingsDevBuild", lang)}
            </Text>
          </View>
          <View style={ss.hairline} />
          <View style={ss.row}>
            <Icon name="wind" color={V2T.text2} size={20} />
            <Text
              {...DYNAMIC_TYPE}
              style={[ss.sourcesTxt, ss.rowMid, { fontFamily: fam(lang, "reg") }]}
            >
              {t("settingsDataSources", lang)}
            </Text>
          </View>
          <View style={ss.hairline} />
          {expander(
            "settingsHowNumbers",
            "numbers",
            <Text {...DYNAMIC_TYPE} style={[ss.bodyTxt, { fontFamily: fam(lang, "reg") }]}>
              {/* the Berkeley-rule sentence only shows when the metaphor
                  itself is enabled — same explainer, minus that clause */}
              {t(current.show_cig ? "settingsHowNumbersBody" : "settingsHowNumbersBodyPlain", lang)}
            </Text>,
          )}
          <View style={ss.hairline} />
          {expander(
            "sidebarHowAliveWorks",
            "how",
            <Text {...DYNAMIC_TYPE} style={[ss.bodyTxt, { fontFamily: fam(lang, "reg") }]}>
              {t("howAliveBody", lang)}
            </Text>,
          )}
          <View style={ss.hairline} />
          {expander(
            "settingsRate",
            "rate",
            rateState === "ok" ? (
              <View style={ss.rateDoneRow}>
                <Icon name="star" filled color={V2T.accent} size={18} />
                <Text {...DYNAMIC_TYPE} style={[ss.bodyTxt, { fontFamily: fam(lang, "reg") }]}>
                  {t("settingsRateThanks", lang)}
                </Text>
              </View>
            ) : (
              <View>
                <View style={ss.rateStars} accessibilityRole="radiogroup">
                  {[1, 2, 3, 4, 5].map((n) => (
                    <Pressable
                      key={n}
                      hitSlop={8}
                      onPress={() => { tick(); setRateStars(n); if (rateState === "err") setRateState("idle"); }}
                      {...a11y(`${n} / 5`, undefined, "radio", { selected: rateStars >= n, lang })}
                    >
                      <Icon
                        name="star"
                        filled={rateStars >= n}
                        color={rateStars >= n ? V2T.accent : V2T.text3}
                        size={28}
                      />
                    </Pressable>
                  ))}
                </View>
                <TextInput
                  {...DYNAMIC_TYPE}
                  value={rateNote}
                  onChangeText={setRateNote}
                  placeholder={t("settingsRateNotePh", lang)}
                  placeholderTextColor={V2T.text3}
                  maxLength={240}
                  returnKeyType="send"
                  onSubmitEditing={sendRate}
                  style={[ss.rateInput, { fontFamily: fam(lang, "reg") }]}
                />
                <View style={ss.rateFoot}>
                  <Text
                    {...DYNAMIC_TYPE}
                    style={[ss.hint, rateState === "err" && ss.rateErrTxt, { fontFamily: fam(lang, "reg") }]}
                  >
                    {t(rateState === "err" ? "settingsRateFail" : "settingsRateHint", lang)}
                  </Text>
                  <Pressable
                    onPress={sendRate}
                    disabled={!rateStars || rateState === "sending"}
                    {...a11y(
                      t("settingsRateSend", lang),
                      rateStars ? undefined : t("settingsRateHint", lang),
                      "button",
                      { disabled: !rateStars || rateState === "sending", busy: rateState === "sending", lang },
                    )}
                    style={({ pressed }) => [
                      ss.rateSendBtn,
                      (!rateStars || rateState === "sending") && { opacity: 0.45 },
                      pressed && { backgroundColor: V2T.accentTint },
                    ]}
                  >
                    <Text {...DYNAMIC_TYPE} style={[ss.rateSendTxt, { fontFamily: fam(lang, "med") }]}>
                      {t(rateState === "sending" ? "settingsRateSending" : "settingsRateSend", lang)}
                    </Text>
                  </Pressable>
                </View>
              </View>
            ),
            "star",
          )}
        </View>
      </ScrollView>
    </View>
  );
}

/* ---------- public component ---------- */

export function SettingsScreen({
  visible,
  onClose,
  lang = "en",
  current,
  onChange,
  onArmBrief,
  onDeleteData,
}: {
  visible: boolean;
  onClose: () => void;
  lang?: Lang;
  /** The persisted ShellSettings snapshot — the screen is fully controlled. */
  current: ShellSettings;
  /** Every edit lands here: settings keys carry a typed value, "editVehicle" opens the S8 vehicle sheet. */
  onChange: SettingsChangeFn;
  /** SEAM: asks the parent to request perms + schedule the daily brief; returns whether it armed. */
  onArmBrief?: () => Promise<boolean>;
  /** SEAM(delete-data): parent's confirmed wipe (App.tsx `deleteAll`). The
   *  destructive row renders only when this prop exists. */
  onDeleteData?: () => void;
}) {
  /* hardware back closes the sheet — the Modal's onRequestClose used to
     provide this; the overlay needs BackHandler explicitly. */
  useEffect(() => {
    if (!visible) return;
    const sub = BackHandler.addEventListener("hardwareBackPress", () => { onClose(); return true; });
    return () => sub.remove();
  }, [visible, onClose]);

  /* plain absolute overlay — RN Modal's native present/dismiss segfaults
     this stack (reproduced on the search sheet three times) — no Modal,
     no crash class. The slide-up the Modal provided is kept as a JS-driver
     enter spring (the proven-safe pattern from Sheet/SearchScreen). */
  const [enter] = useState(() => new Animated.Value(0));
  const [enterTy] = useState(() => enter.interpolate({ inputRange: [0, 1], outputRange: [36, 0] }));
  useEffect(() => {
    if (visible) {
      enter.setValue(0);
      Animated.spring(enter, { toValue: 1, damping: 24, stiffness: 240, useNativeDriver: false }).start();
    }
  }, [visible, enter]);

  if (!visible) return null;
  return (
    <View style={ss.backdrop}>
      <StatusBar style="dark" />
      <Animated.View style={{ flex: 1, opacity: enter, transform: [{ translateY: enterTy }] }}>
        <SettingsSheet
          onClose={onClose}
          lang={lang}
          current={current}
          onChange={onChange}
          onArmBrief={onArmBrief}
          onDeleteData={onDeleteData}
        />
      </Animated.View>
    </View>
  );
}

export default SettingsScreen;

const ss = StyleSheet.create({
  /* elevation must beat HomeScreen's 24 — Android dispatches sibling touches
     by z before mount order, so the still-mounted home scroll swallowed this
     sheet's drags. iOS ignores it. */
  backdrop: { ...StyleSheet.absoluteFill, backgroundColor: V2T.scrim, elevation: 30 },
  root: {
    flex: 1,

    backgroundColor: V2T.glassDeep,
    borderTopLeftRadius: V2Radius.sheet,
    borderTopRightRadius: V2Radius.sheet,
    borderTopWidth: 1,
    borderColor: V2T.glassEdge,
    overflow: "hidden",
  },
  header: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: 8,
    paddingTop: 14,
    paddingBottom: 8,
  },
  headerBtn: { width: 44, height: 44, alignItems: "center", justifyContent: "center" },
  title: { fontSize: V2Type.body, color: V2T.text },
  scroll: { paddingHorizontal: 16 },

  sectionLabel: {
    fontSize: V2Type.label,
    color: V2T.text3,
    letterSpacing: 0.8,
    textTransform: "uppercase",
    marginTop: 22,
    marginBottom: 8,
    marginLeft: 4,
  },
  card: {
    ...V2Elev.card,
    backgroundColor: V2T.glassSoft,
    borderRadius: V2Radius.row,
    borderWidth: 1,
    borderColor: V2T.glassLine,
    marginTop: 8,
    overflow: "hidden",
  },

  // ≥52pt rows: every control clears the 44pt target floor (a11y MIN_TOUCH)
  row: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
    paddingHorizontal: 14,
    paddingVertical: 10,
    minHeight: 52,
  },
  rowPressed: { backgroundColor: "rgba(255,255,255,0.55)" },
  rowDisabled: { opacity: 0.55 },
  rowMid: { flex: 1 },
  rowLabel: { fontSize: V2Type.secondary, color: V2T.text },
  hint: { fontFamily: F.reg, fontSize: V2Type.label, color: V2T.text3, marginTop: 2, lineHeight: 17 },
  value: { fontFamily: F.reg, fontSize: V2Type.secondary, color: V2T.text3 },
  action: { fontSize: V2Type.secondary, color: V2T.accent },
  dangerTxt: { color: V2T.breath3 },

  explainWrap: { paddingHorizontal: 14, paddingBottom: 12, marginTop: -4 },
  explain: {
    fontFamily: F.reg,
    fontSize: V2Type.label,
    color: V2T.text2,
    lineHeight: 18,
  },
  explainStatus: { color: V2T.text3, marginTop: 6 },
  hairline: { height: StyleSheet.hairlineWidth, backgroundColor: V2T.glassLine, marginHorizontal: 14 },

  expandBody: { paddingHorizontal: 14, paddingBottom: 12 },
  bulletRow: { flexDirection: "row", gap: 8, paddingVertical: 4 },
  bulletDot: {
    width: 5,
    height: 5,
    borderRadius: 2.5,
    backgroundColor: V2T.text3,
    marginTop: 7,
  },
  bulletTxt: { flex: 1, fontSize: V2Type.label, color: V2T.text2, lineHeight: 18 },
  bodyTxt: { fontSize: V2Type.label, color: V2T.text2, lineHeight: 19 },
  sourcesTxt: { fontSize: V2Type.label, color: V2T.text2, lineHeight: 18 },

  segWrap: {
    flexDirection: "row",
    borderRadius: V2Radius.row,
    borderWidth: 1,
    borderColor: V2T.glassLine,
    overflow: "hidden",
    backgroundColor: V2T.glassSoft,
  },
  // 44pt-tall segment targets (HIG floor), compact look preserved
  seg: { paddingHorizontal: 16, minHeight: 44, justifyContent: "center" },
  segOn: { backgroundColor: V2T.glassSel },
  segTxt: { fontSize: V2Type.label, color: V2T.text3 },

  /* rate ALive·108 — stars + one-line note + send, inside the about card */
  rateStars: { flexDirection: "row", gap: 12, paddingVertical: 6 },
  rateInput: {
    backgroundColor: V2T.glassSoft,
    borderRadius: V2Radius.row,
    borderWidth: 1,
    borderColor: V2T.glassLine,
    paddingHorizontal: 12,
    paddingVertical: 9,
    fontSize: V2Type.secondary,
    color: V2T.text,
    minHeight: 44,
    marginTop: 4,
  },
  rateFoot: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", gap: 10, marginTop: 8 },
  rateErrTxt: { color: V2T.breath3, flex: 1 },
  rateSendBtn: {
    backgroundColor: V2T.glassSel,
    borderRadius: V2Radius.row,
    borderWidth: 1,
    borderColor: V2T.glassLine,
    paddingHorizontal: 16,
    minHeight: 36,
    justifyContent: "center",
  },
  rateSendTxt: { fontSize: V2Type.secondary, color: V2T.accent },
  rateDoneRow: { flexDirection: "row", alignItems: "center", gap: 8, paddingVertical: 6 },
});
