// S-settings — the settings surface the sidebar's section 7 grew into
// (docs/plan/02 §sidebar-7, docs/plan/07 §3, docs/plan/10).
// Contract: <SettingsScreen visible onClose lang current onChange(key,value)
//           onArmBrief? onDeleteData? />
// Controlled component — reads `current` (the persisted ShellSettings), and
// reports every edit through onChange; the parent applies the patch through
// shell/settings.saveSettings. Same Modal-sheet contract as SearchScreen:
// mounted only while visible, dark V2 tokens, every string through t().
// Data sharing is explained in plain words and turns OFF in one labelled tap —
// no dark patterns (doc 07 §3).
//
// Groups: profile (vehicle) → presentation (language / voice / units) →
// privacy & sharing → notifications → about. Cards are the grouping; text
// headers render only where string keys exist today.
//
// PROPOSED string keys (strings.ts is owned by the strings lane — these are
// comments only; no code references them):
//   settingsGeneral   — header over the language/voice/units card ("General"
//                       or "Appearance & language")
//   settingsPrivacy   — header over the sharing card ("Privacy & sharing")
//   settingsVoiceHint — e.g. "spoken turn-by-turn guidance" (row currently
//                       reuses the existing "turnByTurn" key as its hint)
//   settingsUnitsHint — e.g. "metric only" (row currently shows a bare "km")

import React, { useState } from "react";
import {
  Alert,
  Modal,
  Platform,
  Pressable,
  ScrollView,
  StatusBar as RNStatusBar,
  StyleSheet,
  Switch,
  Text,
  View,
} from "react-native";
import { StatusBar } from "expo-status-bar";
import Constants from "expo-constants"; // transitively installed via `expo` (SDK 57)
import { F, V2Radius, V2T, V2Type, fam } from "../theme";
import { Icon, vehicleGlyph } from "../icons";
import { t, type Lang, type StringKey } from "../i18n/strings";
import { a11y, DYNAMIC_TYPE } from "../a11y";
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

type ExpandKey = "store" | "numbers" | "how";

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
  const toggle = (k: ExpandKey) => setExpand((e) => (e === k ? null : k));
  // brief arming awaits OS perms — guard re-entry so a double-tap can't
  // queue two permission prompts (the row also reports busy to TalkBack).
  const [arming, setArming] = useState(false);

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
        onPress={() => onValue(!value)}
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
            <Text {...DYNAMIC_TYPE} style={ss.hint}>{t(hintKey, lang)}</Text>
          ) : null}
        </View>
        <Switch
          accessible={false}
          value={value}
          onValueChange={onValue}
          disabled={disabled}
          trackColor={{ false: V2T.line, true: V2T.accent }}
          thumbColor={V2T.text}
        />
      </Pressable>
    );
  };

  const expander = (labelKey: StringKey, k: ExpandKey, body: React.ReactNode) => (
    <View>
      <Pressable
        onPress={() => toggle(k)}
        {...a11y(t(labelKey, lang), undefined, "button", { expanded: expand === k, lang })}
        style={({ pressed }) => [ss.row, pressed && ss.rowPressed]}
      >
        <Icon name="info" color={V2T.text2} size={20} />
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
    <View style={ss.root}>
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

      <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={ss.scroll}>
        {/* ── profile: vehicle drives every dose/emission estimate (S8) ── */}
        <View style={ss.card}>
          <Pressable
            onPress={() => onChange("editVehicle")}
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
              <Text {...DYNAMIC_TYPE} style={ss.hint} numberOfLines={2}>
                {current.vehicle
                  ? `${t(VEHICLE_LABEL[current.vehicle] ?? "vehicleQ1", lang)} · ${t("settingsVehicleLike", lang)}`
                  : t("notSet", lang)}
              </Text>
            </View>
            <Text {...DYNAMIC_TYPE} style={[ss.action, { fontFamily: fam(lang, "med") }]}>
              {t("changeLabel", lang)}
            </Text>
          </Pressable>
        </View>

        {/* ── presentation: language, guidance voice, units ──
            PROPOSED section header: settingsGeneral */}
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
                  onPress={() => onChange("lang", code)}
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
            // PROPOSED settingsVoiceHint — "turnByTurn" covers it today
            "turnByTurn",
          )}
          <View style={ss.hairline} />
          <View style={ss.row}>
            <Text
              {...DYNAMIC_TYPE}
              style={[ss.rowLabel, ss.rowMid, { fontFamily: fam(lang, "med") }]}
            >
              {t("settingsUnits", lang)}
            </Text>
            {/* metric only — PROPOSED settingsUnitsHint if the strings lane
                wants to say that out loud */}
            <Text {...DYNAMIC_TYPE} style={ss.value}>{t("unitsKm", lang)}</Text>
          </View>
        </View>

        {/* ── privacy & sharing: explained, one labelled tap off (doc 07 §3) ──
            PROPOSED section header: settingsPrivacy */}
        <View style={ss.card}>
          {switchRow("settingsShareData", current.share, (v) => onChange("share", v))}
          <View style={ss.explainWrap}>
            <Text {...DYNAMIC_TYPE} style={ss.explain}>{t("settingsShareExplain", lang)}</Text>
            {/* live status line — the consequence of the CURRENT choice in
                plain words: anonymous + aggregate when on, sealed when off */}
            <Text {...DYNAMIC_TYPE} style={[ss.explain, ss.explainStatus]}>
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
            <Text {...DYNAMIC_TYPE} style={ss.value}>{VERSION ?? t("settingsDevBuild", lang)}</Text>
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
              {t("settingsHowNumbersBody", lang)}
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
  return (
    <Modal
      visible={visible}
      transparent
      animationType="slide"
      onRequestClose={onClose}
      statusBarTranslucent
    >
      <View style={ss.backdrop}>
        <StatusBar style="dark" />
        {visible ? (
          <SettingsSheet
            onClose={onClose}
            lang={lang}
            current={current}
            onChange={onChange}
            onArmBrief={onArmBrief}
            onDeleteData={onDeleteData}
          />
        ) : null}
      </View>
    </Modal>
  );
}

export default SettingsScreen;

const ss = StyleSheet.create({
  backdrop: { flex: 1, backgroundColor: V2T.scrim },
  root: {
    flex: 1,
    marginTop: Platform.select({
      ios: 48,
      android: (RNStatusBar.currentHeight ?? 24) + 8,
      default: 16,
    }),
    backgroundColor: V2T.bg,
    borderTopLeftRadius: V2Radius.sheet,
    borderTopRightRadius: V2Radius.sheet,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderColor: V2T.line,
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
  scroll: { paddingHorizontal: 16, paddingBottom: 40 },

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
    backgroundColor: V2T.surface,
    borderRadius: V2Radius.row,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: V2T.line,
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
  rowPressed: { backgroundColor: V2T.surface2 },
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
  hairline: { height: StyleSheet.hairlineWidth, backgroundColor: V2T.line, marginHorizontal: 14 },

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
    borderRadius: V2Radius.pill,
    borderWidth: 1,
    borderColor: V2T.line,
    overflow: "hidden",
  },
  // 44pt-tall segment targets (HIG floor), compact look preserved
  seg: { paddingHorizontal: 16, minHeight: 44, justifyContent: "center" },
  segOn: { backgroundColor: V2T.surface2 },
  segTxt: { fontSize: V2Type.label, color: V2T.text3 },
});
