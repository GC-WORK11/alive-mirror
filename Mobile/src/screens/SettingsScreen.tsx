// S-settings — the settings surface the sidebar's section 7 grew into
// (docs/plan/02 §sidebar-7, docs/plan/07 §3, docs/plan/10).
// Contract: <SettingsScreen visible onClose lang current onChange(key,value) />
// Controlled component — reads `current` (the persisted ShellSettings), and
// reports every edit through onChange; the parent applies the patch through
// shell/settings.saveSettings. Same Modal-sheet contract as SearchScreen:
// mounted only while visible, dark V2 tokens, every string through t().
// Data sharing is explained in plain words and turns OFF in one labelled tap —
// no dark patterns (doc 07 §3).

import React, { useState } from "react";
import {
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

const VERSION = Constants.expoConfig?.version ?? null; // app.json version; null → "dev build"

/* ---------- sheet (mounted only while visible → expanders reset each open) ---------- */

function SettingsSheet({
  onClose,
  lang,
  current,
  onChange,
  onArmBrief,
}: {
  onClose: () => void;
  lang: Lang;
  current: ShellSettings;
  onChange: SettingsChangeFn;
  onArmBrief?: () => Promise<boolean>;
}) {
  const [expand, setExpand] = useState<"store" | "numbers" | null>(null);
  const toggle = (k: "store" | "numbers") => setExpand((e) => (e === k ? null : k));

  const sectionLabel = (key: StringKey) => (
    <Text style={[ss.sectionLabel, { fontFamily: fam(lang, "semi") }]}>{t(key, lang)}</Text>
  );

  const switchRow = (
    labelKey: StringKey,
    value: boolean,
    onValue: (v: boolean) => void,
    hintKey?: StringKey,
  ) => (
    <View style={ss.row}>
      <View style={ss.rowMid}>
        <Text style={[ss.rowLabel, { fontFamily: fam(lang, "med") }]}>{t(labelKey, lang)}</Text>
        {hintKey ? <Text style={ss.hint}>{t(hintKey, lang)}</Text> : null}
      </View>
      <Switch
        value={value}
        onValueChange={onValue}
        accessibilityLabel={t(labelKey, lang)}
        trackColor={{ false: V2T.line, true: V2T.accent }}
        thumbColor={V2T.text}
      />
    </View>
  );

  const expander = (labelKey: StringKey, k: "store" | "numbers", body: React.ReactNode) => (
    <View>
      <Pressable
        onPress={() => toggle(k)}
        accessibilityRole="button"
        style={({ pressed }) => [ss.row, pressed && { backgroundColor: V2T.surface2 }]}
      >
        <Icon name="info" color={V2T.text2} size={20} />
        <Text style={[ss.rowLabel, ss.rowMid, { fontFamily: fam(lang, "med") }]}>{t(labelKey, lang)}</Text>
        <View style={{ transform: [{ rotate: expand === k ? "90deg" : "0deg" }] }}>
          <Icon name="chevron" color={V2T.text3} size={16} />
        </View>
      </Pressable>
      {expand === k && <View style={ss.expandBody}>{body}</View>}
    </View>
  );

  return (
    <View style={ss.root}>
      {/* header: back + title */}
      <View style={ss.header}>
        <Pressable
          onPress={onClose}
          hitSlop={10}
          accessibilityRole="button"
          accessibilityLabel={t("settingsClose", lang)}
          style={ss.headerBtn}
        >
          <View style={{ transform: [{ rotate: "180deg" }] }}>
            <Icon name="chevron" color={V2T.text2} size={20} />
          </View>
        </Pressable>
        <Text style={[ss.title, { fontFamily: fam(lang, "semi") }]}>{t("sidebarSettings", lang)}</Text>
        <View style={ss.headerBtn} />
      </View>

      <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={ss.scroll}>
        {/* ── language — EN / हिं segmented (doc 02 §sidebar-7) ── */}
        <View style={ss.card}>
          <View style={ss.row}>
            <Text style={[ss.rowLabel, ss.rowMid, { fontFamily: fam(lang, "med") }]}>
              {t("settingsLanguage", lang)}
            </Text>
            <View style={ss.segWrap}>
              {(["en", "hi"] as Lang[]).map((l) => (
                <Pressable
                  key={l}
                  onPress={() => onChange("lang", l)}
                  accessibilityRole="button"
                  accessibilityState={{ selected: lang === l }}
                  style={[ss.seg, lang === l && ss.segOn]}
                >
                  <Text style={[ss.segTxt, lang === l && { color: V2T.text }]}>
                    {l === "en" ? "English" : "हिंदी"}
                  </Text>
                </Pressable>
              ))}
            </View>
          </View>
        </View>

        {/* ── anonymous data sharing — explained, one labelled tap off (doc 07 §3) ── */}
        <View style={ss.card}>
          {switchRow("settingsShareData", current.share, (v) => onChange("share", v))}
          <Text style={ss.explain}>{t("settingsShareExplain", lang)}</Text>
          <View style={ss.hairline} />
          {expander(
            "settingsWhatWeStore",
            "store",
            <View>
              {STORE_BULLETS.map((k) => (
                <View key={k} style={ss.bulletRow}>
                  <View style={ss.bulletDot} />
                  <Text style={[ss.bulletTxt, { fontFamily: fam(lang, "reg") }]}>{t(k, lang)}</Text>
                </View>
              ))}
            </View>,
          )}
        </View>

        {/* ── vehicle profile — summary + change → SEAM(editVehicle): S8 sheet ── */}
        <View style={ss.card}>
          <View style={ss.row}>
            <Icon name={vehicleGlyph(current.vehicle ?? "car")} color={V2T.text2} size={22} />
            <View style={ss.rowMid}>
              <Text style={[ss.rowLabel, { fontFamily: fam(lang, "med") }]}>
                {t("sidebarMyVehicle", lang)}
              </Text>
              <Text style={ss.hint} numberOfLines={2}>
                {current.vehicle
                  ? `${t(VEHICLE_LABEL[current.vehicle] ?? "vehicleQ1", lang)} · ${t("settingsVehicleLike", lang)}`
                  : t("notSet", lang)}
              </Text>
            </View>
            <Pressable
              onPress={() => onChange("editVehicle")}
              hitSlop={8}
              accessibilityRole="button"
            >
              <Text style={[ss.action, { fontFamily: fam(lang, "med") }]}>{t("changeLabel", lang)}</Text>
            </Pressable>
          </View>
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
              if (v && onArmBrief) onChange("brief", await onArmBrief());
              else onChange("brief", v);
            },
            "settingsBriefHint",
          )}
        </View>

        {/* ── about / provenance ── */}
        {sectionLabel("settingsAbout")}
        <View style={ss.card}>
          <View style={ss.row}>
            <Text style={[ss.rowLabel, ss.rowMid, { fontFamily: fam(lang, "med") }]}>
              {t("settingsVersion", lang)}
            </Text>
            <Text style={ss.value}>{VERSION ?? t("settingsDevBuild", lang)}</Text>
          </View>
          <View style={ss.hairline} />
          <View style={ss.row}>
            <Icon name="wind" color={V2T.text2} size={20} />
            <Text style={[ss.sourcesTxt, ss.rowMid, { fontFamily: fam(lang, "reg") }]}>
              {t("settingsDataSources", lang)}
            </Text>
          </View>
          <View style={ss.hairline} />
          {expander(
            "settingsHowNumbers",
            "numbers",
            <Text style={[ss.bodyTxt, { fontFamily: fam(lang, "reg") }]}>
              {t("settingsHowNumbersBody", lang)}
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
        <StatusBar style="light" />
        {visible ? (
          <SettingsSheet
            onClose={onClose}
            lang={lang}
            current={current}
            onChange={onChange}
            onArmBrief={onArmBrief}
          />
        ) : null}
      </View>
    </Modal>
  );
}

export default SettingsScreen;

const ss = StyleSheet.create({
  backdrop: { flex: 1, backgroundColor: "rgba(0,0,0,0.35)" },
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
    paddingHorizontal: 12,
    paddingTop: 14,
    paddingBottom: 8,
  },
  headerBtn: { width: 32, padding: 6 },
  title: { fontSize: V2Type.body, color: V2T.text },
  scroll: { paddingHorizontal: 16, paddingBottom: 40 },

  sectionLabel: {
    fontSize: V2Type.label,
    color: V2T.text3,
    letterSpacing: 0.8,
    textTransform: "uppercase",
    marginTop: 20,
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

  row: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
    paddingHorizontal: 14,
    paddingVertical: 12,
  },
  rowMid: { flex: 1 },
  rowLabel: { fontSize: V2Type.secondary, color: V2T.text },
  hint: { fontFamily: F.reg, fontSize: V2Type.label, color: V2T.text3, marginTop: 2, lineHeight: 17 },
  value: { fontFamily: F.reg, fontSize: V2Type.secondary, color: V2T.text3 },
  action: { fontSize: V2Type.secondary, color: V2T.accent },

  explain: {
    fontFamily: F.reg,
    fontSize: V2Type.label,
    color: V2T.text2,
    lineHeight: 18,
    paddingHorizontal: 14,
    paddingBottom: 12,
    marginTop: -4,
  },
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
  seg: { paddingHorizontal: 14, paddingVertical: 6 },
  segOn: { backgroundColor: V2T.surface2 },
  segTxt: { fontFamily: F.med, fontSize: V2Type.label, color: V2T.text3 },
});
