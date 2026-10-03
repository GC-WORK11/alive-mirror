// Trips history — the on-device ledger (doc 02 §sidebar item 3, doc 10).
// Same sheet-over-map contract as SearchScreen: <LedgerScreen visible onClose lang/>.
// Surface speaks in cigarettes; µg and lo–hi bands live one tap down in the
// per-trip details (doc 10: bands allowed at details level, never surface).
// Nothing appears without data — emit_kg / dose bands / donated are optional
// seams on Trip and only render when a real value is stored.
// Delete controls hit store/ledger for real; "delete all" asks first.

import React, { useEffect, useMemo, useState } from "react";
import {
  Alert,
  Modal,
  Platform,
  Pressable,
  ScrollView,
  StatusBar as RNStatusBar,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { StatusBar } from "expo-status-bar";
import Svg, { Path } from "react-native-svg";
import { CIG_UG, NUM, V2Radius, V2T, V2Type, fam } from "../theme";
import { t, type Lang } from "../i18n/strings";
import { Icon, vehicleGlyph } from "../icons";
import {
  clearTrips,
  deleteTrip,
  loadTrips,
  weekStats,
  type Trip,
} from "../store/ledger";

/* ---------- formatting ---------- */

// cigarettes: honest "<0.01" instead of a fake 0 (doc 10 cig equivalence).
const fmtCig = (ug: number) => {
  const c = ug / CIG_UG;
  return c >= 0.01 ? c.toFixed(2) : "<0.01";
};
const fmtUg = (ug: number) =>
  ug >= 10 ? `${Math.round(ug)}` : `${Math.round(ug * 10) / 10}`;
const fmtKg = (kg: number) => (kg >= 0.1 ? kg.toFixed(1) : kg.toFixed(2));

const dayLabel = (ts: number, lang: Lang) =>
  new Date(ts).toLocaleDateString(lang === "hi" ? "hi-IN" : "en-IN", {
    weekday: "short",
    day: "numeric",
    month: "short",
  });
const timeLabel = (ts: number, lang: Lang) =>
  new Date(ts).toLocaleTimeString(lang === "hi" ? "hi-IN" : "en-IN", {
    hour: "numeric",
    minute: "2-digit",
    hour12: true,
  });

function BackGlyph({ color }: { color: string }) {
  return (
    <Svg width={22} height={22} viewBox="0 0 24 24">
      <Path
        d="M14.5 5.5 8 12l6.5 6.5"
        stroke={color}
        strokeWidth={2}
        fill="none"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </Svg>
  );
}

/* ---------- per-trip receipt expander (details level: µg + bands ok) ---------- */

function TripDetail({
  tr,
  lang,
  onDelete,
}: {
  tr: Trip;
  lang: Lang;
  onDelete: () => void;
}) {
  const lo = tr.dose_lo_ug;
  const hi = tr.dose_hi_ug;
  return (
    <View style={ss.detail}>
      <View style={ss.dRow}>
        <Text style={[ss.dLabel, { fontFamily: fam(lang, "reg") }]}>
          {t("tripsBreathed", lang)}
        </Text>
        <View style={ss.dRight}>
          <Text style={[ss.dValue, NUM, { fontFamily: fam(lang, "semi") }]}>
            {t("tripsCigs", lang, { n: fmtCig(tr.dose_ug) })}
          </Text>
          <Text style={[ss.dSub, NUM, { fontFamily: fam(lang, "reg") }]}>
            {lo != null && hi != null
              ? t("tripsDoseBand", lang, { lo: fmtUg(lo), hi: fmtUg(hi) })
              : t("tripsDoseDetail", lang, { n: fmtUg(tr.dose_ug) })}
          </Text>
        </View>
      </View>

      {tr.emit_kg != null && (
        <View style={ss.dRow}>
          <Text style={[ss.dLabel, { fontFamily: fam(lang, "reg") }]}>
            {t("tripsPutOut", lang)}
          </Text>
          <Text style={[ss.dValue, NUM, { fontFamily: fam(lang, "semi") }]}>
            {t("tripsOutDetail", lang, { n: fmtKg(tr.emit_kg) })}
          </Text>
        </View>
      )}

      {tr.avoided_ug > 0 && (
        <Text style={[ss.dSaved, { fontFamily: fam(lang, "reg") }]}>
          {t("tripsSavedVs", lang, { n: fmtCig(tr.avoided_ug) })}
        </Text>
      )}

      {tr.donated === true && (
        <View style={ss.badgeRow}>
          <View style={ss.badge}>
            <Text style={[ss.badgeTxt, { fontFamily: fam(lang, "med") }]}>
              {t("ledgerDonated", lang)}
            </Text>
          </View>
        </View>
      )}

      <View style={ss.dHairline} />
      <Pressable
        onPress={onDelete}
        hitSlop={8}
        accessibilityRole="button"
        accessibilityLabel={t("ledgerDeleteTrip", lang)}
        style={({ pressed }) => [ss.dDelete, pressed && { opacity: 0.6 }]}
      >
        <Icon name="trash" color={V2T.breath3} size={16} />
        <Text style={[ss.dDeleteTxt, { fontFamily: fam(lang, "med") }]}>
          {t("ledgerDeleteTrip", lang)}
        </Text>
      </Pressable>
    </View>
  );
}

/* ---------- trip row ---------- */

function TripRow({
  tr,
  lang,
  open,
  onToggle,
  onDelete,
}: {
  tr: Trip;
  lang: Lang;
  open: boolean;
  onToggle: () => void;
  onDelete: () => void;
}) {
  return (
    <View style={ss.tripWrap}>
      <Pressable
        onPress={onToggle}
        accessibilityRole="button"
        accessibilityLabel={`${tr.from} → ${tr.to}, ${tr.label}`}
        style={({ pressed }) => [
          ss.trip,
          (pressed || open) && { backgroundColor: V2T.surface2 },
        ]}
      >
        <View style={ss.modeBox}>
          <Icon name={vehicleGlyph(tr.vehicle)} color={V2T.text2} size={22} />
        </View>
        <View style={ss.tripMid}>
          <Text
            style={[ss.tripRoute, { fontFamily: fam(lang, "med") }]}
            numberOfLines={1}
          >
            {tr.from} → {tr.to}
          </Text>
          <Text
            style={[ss.tripMeta, { fontFamily: fam(lang, "reg") }]}
            numberOfLines={1}
          >
            {tr.label} · {dayLabel(tr.ts, lang)} · {timeLabel(tr.ts, lang)}
          </Text>
          {tr.avoided_ug > 0 && (
            <Text
              style={[ss.tripSaved, { fontFamily: fam(lang, "reg") }]}
              numberOfLines={1}
            >
              {t("tripsSavedVs", lang, { n: fmtCig(tr.avoided_ug) })}
            </Text>
          )}
        </View>
        <View style={ss.tripNums}>
          <View style={ss.cigRow}>
            <Icon name="cigarette" color={V2T.text3} size={13} />
            <Text style={[ss.cigNum, NUM, { fontFamily: fam(lang, "semi") }]}>
              {fmtCig(tr.dose_ug)}
            </Text>
          </View>
          {tr.emit_kg != null && (
            <Text style={[ss.outNum, NUM, { fontFamily: fam(lang, "reg") }]}>
              ≈{fmtKg(tr.emit_kg)} kg
            </Text>
          )}
        </View>
        <View style={{ transform: [{ rotate: open ? "90deg" : "0deg" }] }}>
          <Icon name="chevron" color={V2T.text3} size={16} />
        </View>
      </Pressable>
      {open && <TripDetail tr={tr} lang={lang} onDelete={onDelete} />}
    </View>
  );
}

/* ---------- sheet (mounted only while visible → fresh state each open) ---------- */

function LedgerSheet({ onClose, lang }: { onClose: () => void; lang: Lang }) {
  const [trips, setTrips] = useState<Trip[]>([]);
  const [openKey, setOpenKey] = useState<string | null>(null);

  useEffect(() => {
    loadTrips().then(setTrips).catch(() => {});
  }, []);

  const sorted = useMemo(() => [...trips].sort((a, b) => b.ts - a.ts), [trips]);
  const week = useMemo(() => weekStats(trips), [trips]);

  // last-7-days rollup for the summary header (calendar days, like weekStats)
  const weekCutoff = useMemo(() => {
    const d = new Date();
    d.setHours(0, 0, 0, 0);
    d.setDate(d.getDate() - 6);
    return d.getTime();
  }, []);
  const weekEmitKg = useMemo(
    () =>
      trips
        .filter((tr) => tr.ts >= weekCutoff && tr.emit_kg != null)
        .reduce((s, tr) => s + (tr.emit_kg ?? 0), 0),
    [trips, weekCutoff],
  );
  const weekTrips = useMemo(
    () => week.days.reduce((s, d) => s + d.trips, 0),
    [week],
  );

  const removeTrip = (tr: Trip) => {
    setOpenKey(null);
    deleteTrip(tr).then(setTrips).catch(() => {});
  };

  const confirmDeleteAll = () =>
    Alert.alert(
      t("ledgerDeleteAllTitle", lang),
      t("ledgerDeleteAllBody", lang),
      [
        { text: t("cancel", lang), style: "cancel" },
        {
          text: t("deleteConfirmYes", lang),
          style: "destructive",
          onPress: () => {
            setOpenKey(null);
            clearTrips().then(setTrips).catch(() => {});
          },
        },
      ],
    );

  return (
    <View style={ss.root}>
      {/* header bar */}
      <View style={ss.bar}>
        <Pressable
          onPress={onClose}
          hitSlop={10}
          accessibilityRole="button"
          accessibilityLabel="back"
          style={ss.barBtn}
        >
          <BackGlyph color={V2T.text2} />
        </Pressable>
        <Text style={[ss.barTitle, { fontFamily: fam(lang, "semi") }]}>
          {t("sidebarTrips", lang)}
        </Text>
        <View style={ss.barBtn} />
      </View>

      <ScrollView
        style={ss.flex}
        contentContainerStyle={ss.listContent}
        showsVerticalScrollIndicator={false}
      >
        {sorted.length === 0 ? (
          /* honest empty state — what gets recorded + privacy line */
          <View style={ss.empty}>
            <Icon name="clock" color={V2T.text3} size={28} />
            <Text style={[ss.emptyTitle, { fontFamily: fam(lang, "med") }]}>
              {t("tripsEmpty", lang)}
            </Text>
            <Text style={[ss.emptyHint, { fontFamily: fam(lang, "reg") }]}>
              {t("ledgerEmptyHint", lang)}
            </Text>
            <Text style={[ss.emptyPrivacy, { fontFamily: fam(lang, "reg") }]}>
              {t("ledgerPrivacy", lang)}
            </Text>
          </View>
        ) : (
          <>
            {/* summary header — last 7 days, nothing without data */}
            <Text style={[ss.sectionLabel, { fontFamily: fam(lang, "semi") }]}>
              {t("ledgerLast7", lang)}
            </Text>
            <View style={ss.summaryCard}>
              <View style={ss.sumCol}>
                <View style={ss.sumHead}>
                  <Icon name="cigarette" color={V2T.text3} size={15} />
                  <Text
                    style={[ss.sumNum, NUM, { fontFamily: fam(lang, "semi") }]}
                  >
                    {fmtCig(week.weekUg)}
                  </Text>
                </View>
                <Text style={[ss.sumCap, { fontFamily: fam(lang, "reg") }]}>
                  {t("breathed", lang)}
                </Text>
              </View>
              {weekEmitKg > 0 && (
                <View style={ss.sumCol}>
                  <Text
                    style={[ss.sumNum, NUM, { fontFamily: fam(lang, "semi") }]}
                  >
                    ≈{fmtKg(weekEmitKg)}
                    <Text style={ss.sumUnit}> kg</Text>
                  </Text>
                  <Text style={[ss.sumCap, { fontFamily: fam(lang, "reg") }]}>
                    {t("putOut", lang)}
                  </Text>
                </View>
              )}
              <View style={ss.sumCol}>
                <Text
                  style={[ss.sumNum, NUM, { fontFamily: fam(lang, "semi") }]}
                >
                  {weekTrips}
                </Text>
                <Text style={[ss.sumCap, { fontFamily: fam(lang, "reg") }]}>
                  {t(weekTrips === 1 ? "tripsCountOne" : "tripsCount", lang, {
                    n: "",
                  }).trim()}
                </Text>
              </View>
            </View>

            {/* trip list */}
            {sorted.map((tr, i) => {
              const key = `${tr.ts}-${i}`;
              return (
                <TripRow
                  key={key}
                  tr={tr}
                  lang={lang}
                  open={openKey === key}
                  onToggle={() => setOpenKey((k) => (k === key ? null : key))}
                  onDelete={() => removeTrip(tr)}
                />
              );
            })}

            {/* privacy + delete all */}
            <View style={ss.footer}>
              <Text style={[ss.privacy, { fontFamily: fam(lang, "reg") }]}>
                {t("ledgerPrivacy", lang)}
              </Text>
              <Pressable
                onPress={confirmDeleteAll}
                hitSlop={8}
                accessibilityRole="button"
                accessibilityLabel={t("ledgerDeleteAll", lang)}
                style={({ pressed }) => [
                  ss.deleteAll,
                  pressed && { opacity: 0.6 },
                ]}
              >
                <Icon name="trash" color={V2T.breath3} size={15} />
                <Text
                  style={[ss.deleteAllTxt, { fontFamily: fam(lang, "med") }]}
                >
                  {t("ledgerDeleteAll", lang)}
                </Text>
              </Pressable>
            </View>
          </>
        )}
      </ScrollView>
    </View>
  );
}

/* ---------- public component: <LedgerScreen visible onClose lang/> ---------- */

export function LedgerScreen({
  visible,
  onClose,
  lang = "en",
}: {
  visible: boolean;
  onClose: () => void;
  lang?: Lang;
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
        {visible ? <LedgerSheet onClose={onClose} lang={lang} /> : null}
      </View>
    </Modal>
  );
}

export default LedgerScreen;

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
  bar: {
    flexDirection: "row",
    alignItems: "center",
    height: 56,
    paddingHorizontal: 12,
  },
  barBtn: { width: 34, padding: 6 },
  barTitle: {
    flex: 1,
    textAlign: "center",
    color: V2T.text,
    fontSize: V2Type.body,
  },
  flex: { flex: 1 },
  listContent: { paddingBottom: 36 },

  sectionLabel: {
    color: V2T.text3,
    fontSize: V2Type.label,
    letterSpacing: 0.8,
    textTransform: "uppercase",
    marginTop: 6,
    marginBottom: 8,
    marginHorizontal: 18,
  },
  summaryCard: {
    flexDirection: "row",
    backgroundColor: V2T.surface,
    borderRadius: V2Radius.row,
    borderWidth: 1,
    borderColor: V2T.line,
    padding: 16,
    marginHorizontal: 14,
    marginBottom: 10,
  },
  sumCol: { flex: 1 },
  sumHead: { flexDirection: "row", alignItems: "center", gap: 6 },
  sumNum: { color: V2T.text, fontSize: V2Type.title, lineHeight: 30 },
  sumUnit: { color: V2T.text2, fontSize: V2Type.secondary },
  sumCap: { color: V2T.text2, fontSize: V2Type.label, marginTop: 2 },

  tripWrap: { marginHorizontal: 8 },
  trip: {
    flexDirection: "row",
    alignItems: "center",
    minHeight: 58,
    paddingHorizontal: 10,
    paddingVertical: 8,
    borderRadius: V2Radius.row,
    gap: 10,
  },
  modeBox: {
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: V2T.surface,
    alignItems: "center",
    justifyContent: "center",
  },
  tripMid: { flex: 1, marginRight: 6 },
  tripRoute: { color: V2T.text, fontSize: V2Type.secondary },
  tripMeta: { color: V2T.text3, fontSize: V2Type.label, marginTop: 1 },
  tripSaved: { color: V2T.text2, fontSize: V2Type.label, marginTop: 2 },
  tripNums: { alignItems: "flex-end", marginRight: 2 },
  cigRow: { flexDirection: "row", alignItems: "center", gap: 5 },
  cigNum: { color: V2T.text2, fontSize: V2Type.secondary },
  outNum: { color: V2T.text3, fontSize: V2Type.label, marginTop: 2 },

  detail: {
    marginHorizontal: 10,
    marginBottom: 8,
    paddingHorizontal: 14,
    paddingVertical: 12,
    backgroundColor: V2T.surface,
    borderRadius: V2Radius.row,
    borderWidth: 1,
    borderColor: V2T.line,
  },
  dRow: { flexDirection: "row", alignItems: "center", paddingVertical: 6 },
  dLabel: { flex: 1, color: V2T.text2, fontSize: V2Type.secondary },
  dRight: { alignItems: "flex-end" },
  dValue: { color: V2T.text, fontSize: V2Type.secondary },
  dSub: { color: V2T.text3, fontSize: V2Type.label, marginTop: 1 },
  dSaved: { color: V2T.text2, fontSize: V2Type.label, paddingVertical: 6 },
  badgeRow: { flexDirection: "row", paddingVertical: 4 },
  badge: {
    borderRadius: V2Radius.pill,
    borderWidth: 1,
    borderColor: V2T.line,
    paddingHorizontal: 10,
    paddingVertical: 3,
    backgroundColor: V2T.surface2,
  },
  badgeTxt: { color: V2T.text2, fontSize: V2Type.label },
  dHairline: {
    height: StyleSheet.hairlineWidth,
    backgroundColor: V2T.line,
    marginTop: 8,
  },
  dDelete: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    paddingVertical: 10,
    alignSelf: "flex-start",
  },
  dDeleteTxt: { color: V2T.breath3, fontSize: V2Type.label },

  empty: { alignItems: "center", paddingTop: 90, paddingHorizontal: 40, gap: 8 },
  emptyTitle: { color: V2T.text, fontSize: V2Type.body, marginTop: 8 },
  emptyHint: {
    color: V2T.text2,
    fontSize: V2Type.secondary,
    textAlign: "center",
    lineHeight: 21,
  },
  emptyPrivacy: { color: V2T.text3, fontSize: V2Type.label, marginTop: 6 },

  footer: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginHorizontal: 18,
    marginTop: 16,
  },
  privacy: { color: V2T.text3, fontSize: V2Type.label },
  deleteAll: {
    flexDirection: "row",
    alignItems: "center",
    gap: 7,
    paddingVertical: 6,
    paddingHorizontal: 4,
  },
  deleteAllTxt: { color: V2T.breath3, fontSize: V2Type.label },
});
