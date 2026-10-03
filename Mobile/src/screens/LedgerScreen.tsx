// Trips history — the on-device ledger (doc 02 §sidebar item 3, doc 10).
// Same sheet-over-map contract as SearchScreen: <LedgerScreen visible onClose lang/>.
// Surface speaks in cigarettes; µg and lo–hi bands live one tap down in the
// per-trip details (doc 10: bands allowed at details level, never surface).
// Nothing appears without data — emit_kg / dose bands / donated are optional
// seams on Trip and only render when a real value is stored.
// Delete controls hit store/ledger for real; "delete all" asks first.
//
// PROPOSED i18n keys — src/i18n/strings.ts is owned by another lane, so the
// screen ships on existing keys; these would sharpen the copy when added:
//   ledgerAllTime   en "all saved trips" / hi "सारी सेव की गई यात्राएँ"
//                   — caption under the cumulative totals row
//   ledgerEstNote   en "estimates, honestly ranged" / hi "ईमानदार रेंज वाले अनुमान"
//                   — honesty footnote for the totals card
//   ledgerYesterday en "yesterday" / hi "कल" — day-header special case
//                   (today already reuses sidebarToday)
//   ledgerShowTrip  en "show trip details" / hi "यात्रा की जानकारी देखें"
//                   — accessibilityHint on each trip card
//   a11yBack        en "back" / hi "पीछे" — sheet back button
//                   (currently reuses vehicleQ_back)

import React, { useCallback, useEffect, useMemo, useState } from "react";
import {
  Alert,
  FlatList,
  type ListRenderItem,
  Modal,
  Pressable,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { StatusBar } from "expo-status-bar";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import Svg, { Path } from "react-native-svg";
import { CIG_UG, NUM, V2Radius, V2T, V2Type, fam } from "../theme";
import { DYNAMIC_TYPE } from "../a11y";
import { modeLabel, t, type Lang } from "../i18n/strings";
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

/** Stable row id — the same ts+route+mode tuple deleteTrip matches on. */
const tripKey = (tr: Trip) => `${tr.ts}|${tr.from}|${tr.to}|${tr.vehicle}`;

/** Surface dose tone — colour means severity, quiet trips stay grey (doc 03:
 *  lightness is the absence of colour). Keyed to cigarette-equivalents. */
const cigTone = (ug: number) => {
  const c = ug / CIG_UG;
  return c >= 1 ? V2T.breath2 : c >= 0.3 ? V2T.breath1 : V2T.text2;
};

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
        <Text {...DYNAMIC_TYPE} style={[ss.dLabel, { fontFamily: fam(lang, "reg") }]}>
          {t("tripsBreathed", lang)}
        </Text>
        <View style={ss.dRight}>
          <Text {...DYNAMIC_TYPE} style={[ss.dValue, NUM, { fontFamily: fam(lang, "semi") }]}>
            {t("tripsCigs", lang, { n: fmtCig(tr.dose_ug) })}
          </Text>
          <Text {...DYNAMIC_TYPE} style={[ss.dSub, NUM, { fontFamily: fam(lang, "reg") }]}>
            {lo != null && hi != null
              ? t("tripsDoseBand", lang, { lo: fmtUg(lo), hi: fmtUg(hi) })
              : t("tripsDoseDetail", lang, { n: fmtUg(tr.dose_ug) })}
          </Text>
        </View>
      </View>

      {tr.emit_kg != null && (
        <View style={ss.dRow}>
          <Text {...DYNAMIC_TYPE} style={[ss.dLabel, { fontFamily: fam(lang, "reg") }]}>
            {t("tripsPutOut", lang)}
          </Text>
          <Text {...DYNAMIC_TYPE} style={[ss.dValue, NUM, { fontFamily: fam(lang, "semi") }]}>
            {t("tripsOutDetail", lang, { n: fmtKg(tr.emit_kg) })}
          </Text>
        </View>
      )}

      {tr.avoided_ug > 0 && (
        <Text {...DYNAMIC_TYPE} style={[ss.dSaved, { fontFamily: fam(lang, "reg") }]}>
          {t("tripsSavedVs", lang, { n: fmtCig(tr.avoided_ug) })}
        </Text>
      )}

      {tr.donated === true && (
        <View style={ss.badgeRow}>
          <View style={ss.badge}>
            <Text {...DYNAMIC_TYPE} style={[ss.badgeTxt, { fontFamily: fam(lang, "med") }]}>
              {t("ledgerDonated", lang)}
            </Text>
          </View>
        </View>
      )}

      <View style={ss.dHairline} />
      <Pressable
        onPress={onDelete}
        accessibilityRole="button"
        accessibilityLabel={t("ledgerDeleteTrip", lang)}
        style={({ pressed }) => [ss.dDelete, pressed && { opacity: 0.6 }]}
      >
        <Icon name="trash" color={V2T.breath3} size={16} />
        <Text {...DYNAMIC_TYPE} style={[ss.dDeleteTxt, { fontFamily: fam(lang, "med") }]}>
          {t("ledgerDeleteTrip", lang)}
        </Text>
      </Pressable>
    </View>
  );
}

/* ---------- trip card (memoized — the list can hold up to 500 trips) ---------- */

const TripCard = React.memo(function TripCard({
  tr,
  lang,
  open,
  onToggle,
  onDelete,
}: {
  tr: Trip;
  lang: Lang;
  open: boolean;
  onToggle: (key: string) => void;
  onDelete: (tr: Trip) => void;
}) {
  const key = tripKey(tr);
  return (
    <View style={ss.card}>
      <Pressable
        onPress={() => onToggle(key)}
        accessibilityRole="button"
        accessibilityLabel={`${tr.from} → ${tr.to}, ${modeLabel(tr.vehicle, tr.label, lang)}, ${dayLabel(
          tr.ts,
          lang,
        )} ${timeLabel(tr.ts, lang)}`}
        accessibilityState={{ expanded: open }}
        style={({ pressed }) => [
          ss.cardHead,
          (pressed || open) && { backgroundColor: V2T.surface2 },
        ]}
      >
        <View style={ss.modeBox}>
          <Icon name={vehicleGlyph(tr.vehicle)} color={V2T.text2} size={22} />
        </View>
        <View style={ss.tripMid}>
          <Text {...DYNAMIC_TYPE}
            style={[ss.tripRoute, { fontFamily: fam(lang, "med") }]}
            numberOfLines={1}
          >
            {tr.from} → {tr.to}
          </Text>
          <Text {...DYNAMIC_TYPE}
            style={[ss.tripMeta, { fontFamily: fam(lang, "reg") }]}
            numberOfLines={1}
          >
            {modeLabel(tr.vehicle, tr.label, lang)} · {timeLabel(tr.ts, lang)}
          </Text>
          {tr.avoided_ug > 0 && (
            <Text {...DYNAMIC_TYPE}
              style={[ss.tripSaved, { fontFamily: fam(lang, "reg") }]}
              numberOfLines={1}
            >
              {t("tripsSavedVs", lang, { n: fmtCig(tr.avoided_ug) })}
            </Text>
          )}
        </View>
        <View style={ss.tripNums}>
          <View style={ss.cigRow}>
            <Icon name="cigarette" color={cigTone(tr.dose_ug)} size={13} />
            <Text {...DYNAMIC_TYPE}
              style={[
                ss.cigNum,
                NUM,
                { fontFamily: fam(lang, "semi"), color: cigTone(tr.dose_ug) },
              ]}
            >
              {fmtCig(tr.dose_ug)}
            </Text>
          </View>
          {tr.emit_kg != null && (
            <Text {...DYNAMIC_TYPE} style={[ss.outNum, NUM, { fontFamily: fam(lang, "reg") }]}>
              ≈{fmtKg(tr.emit_kg)} kg
            </Text>
          )}
        </View>
        <View style={{ transform: [{ rotate: open ? "90deg" : "0deg" }] }}>
          <Icon name="chevron" color={V2T.text3} size={16} />
        </View>
      </Pressable>
      {open && <TripDetail tr={tr} lang={lang} onDelete={() => onDelete(tr)} />}
    </View>
  );
});

/* ---------- empty state — type-led, invites the first trip ---------- */

function EmptyState({ lang }: { lang: Lang }) {
  return (
    <View style={ss.emptyWrap}>
      <View style={ss.emptyBadge}>
        <Icon name="clock" color={V2T.text3} size={26} />
      </View>
      <Text {...DYNAMIC_TYPE} style={[ss.emptyTitle, { fontFamily: fam(lang, "semi") }]}>
        {t("tripsEmpty", lang)}
      </Text>
      <Text {...DYNAMIC_TYPE} style={[ss.emptyHint, { fontFamily: fam(lang, "reg") }]}>
        {t("ledgerEmptyHint", lang)}
      </Text>
      <Text {...DYNAMIC_TYPE} style={[ss.emptyPrivacy, { fontFamily: fam(lang, "reg") }]}>
        {t("ledgerPrivacy", lang)}
      </Text>
    </View>
  );
}

/* ---------- sheet (mounted only while visible → fresh state each open) ---------- */

// FlatList rows: a day header each time the calendar day changes, then the
// day's trips (newest first). One list keeps virtualization for 500-trip ledgers.
type Row =
  | { kind: "day"; key: string; label: string }
  | { kind: "trip"; key: string; tr: Trip };

function LedgerSheet({ onClose, lang, onTripsChanged }: { onClose: () => void; lang: Lang; onTripsChanged?: () => void }) {
  const [trips, setTrips] = useState<Trip[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [openKey, setOpenKey] = useState<string | null>(null);
  const insets = useSafeAreaInsets();

  useEffect(() => {
    let alive = true;
    loadTrips()
      .then((ts) => {
        if (alive) setTrips(ts);
      })
      .catch(() => {})
      .finally(() => {
        if (alive) setLoaded(true);
      });
    return () => {
      alive = false;
    };
  }, []);

  const sorted = useMemo(() => [...trips].sort((a, b) => b.ts - a.ts), [trips]);
  const week = useMemo(() => weekStats(trips), [trips]);

  // last-7-days rollup for the summary card (calendar days, like weekStats)
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

  // bar-strip scale: the tallest day tops out, the rest ride it;
  // an empty day still shows a nub so the week reads as a series,
  // not a list of gaps
  const weekMaxUg = useMemo(
    () => Math.max(0.1, ...week.days.map((d) => d.ug)),
    [week],
  );

  // cumulative totals across every saved trip (the ledger caps at 500)
  const allUg = useMemo(
    () => trips.reduce((s, tr) => s + tr.dose_ug, 0),
    [trips],
  );
  const allEmitKg = useMemo(
    () => trips.reduce((s, tr) => s + (tr.emit_kg ?? 0), 0),
    [trips],
  );

  const rows = useMemo<Row[]>(() => {
    const today = new Date().toDateString();
    const out: Row[] = [];
    let day = "";
    for (const tr of sorted) {
      const dk = new Date(tr.ts).toDateString();
      if (dk !== day) {
        day = dk;
        out.push({
          kind: "day",
          // PROPOSED ledgerYesterday — yesterday gets its word too
          key: `day-${dk}`,
          label: dk === today ? t("sidebarToday", lang) : dayLabel(tr.ts, lang),
        });
      }
      out.push({ kind: "trip", key: tripKey(tr), tr });
    }
    return out;
  }, [sorted, lang]);

  const toggleRow = useCallback(
    (key: string) => setOpenKey((k) => (k === key ? null : key)),
    [],
  );

  const removeTrip = useCallback((tr: Trip) => {
    setOpenKey(null);
    deleteTrip(tr).then(setTrips).then(onTripsChanged).catch(() => {});
  }, [onTripsChanged]);

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
            clearTrips().then(setTrips).then(onTripsChanged).catch(() => {});
          },
        },
      ],
    );

  const renderRow = useCallback<ListRenderItem<Row>>(
    ({ item }) =>
      item.kind === "day" ? (
        <Text {...DYNAMIC_TYPE}
          style={[ss.dayHead, { fontFamily: fam(lang, "semi") }]}
          accessibilityRole="header"
        >
          {item.label}
        </Text>
      ) : (
        <TripCard
          tr={item.tr}
          lang={lang}
          open={openKey === item.key}
          onToggle={toggleRow}
          onDelete={removeTrip}
        />
      ),
    [lang, openKey, toggleRow, removeTrip],
  );

  const keyExtractor = useCallback((item: Row) => item.key, []);

  return (
    <View style={[ss.root, { marginTop: insets.top + 8 }]}>
      {/* header bar */}
      <View style={ss.bar}>
        <Pressable
          onPress={onClose}
          accessibilityRole="button"
          // PROPOSED a11yBack — reusing vehicleQ_back ("back") meanwhile
          accessibilityLabel={t("vehicleQ_back", lang)}
          style={ss.barBtn}
        >
          <BackGlyph color={V2T.text2} />
        </Pressable>
        <Text {...DYNAMIC_TYPE} style={[ss.barTitle, { fontFamily: fam(lang, "semi") }]}>
          {t("sidebarTrips", lang)}
        </Text>
        <View style={ss.barBtn} />
      </View>

      <FlatList
        data={rows}
        renderItem={renderRow}
        keyExtractor={keyExtractor}
        extraData={openKey}
        style={ss.flex}
        contentContainerStyle={[ss.listContent, { paddingBottom: insets.bottom + 20 }]}
        showsVerticalScrollIndicator={false}
        initialNumToRender={14}
        maxToRenderPerBatch={10}
        windowSize={9}
        ListHeaderComponent={
          /* totals header — cumulative over saved trips, honest "est." labelling;
             hidden until there's data (doc: no zero-fill) */
          sorted.length > 0 ? (
            <View style={ss.summaryCard}>
              <View style={ss.sumRow}>
                <View style={ss.sumCol}>
                  <Text {...DYNAMIC_TYPE}
                    style={[ss.sumNum, NUM, { fontFamily: fam(lang, "semi") }]}
                  >
                    {sorted.length}
                  </Text>
                  <Text {...DYNAMIC_TYPE} style={[ss.sumCap, { fontFamily: fam(lang, "reg") }]}>
                    {t(
                      sorted.length === 1 ? "tripsCountOne" : "tripsCount",
                      lang,
                      { n: "" },
                    ).trim()}
                  </Text>
                </View>
                <View style={ss.sumCol}>
                  <View style={ss.sumHead}>
                    <Icon name="cigarette" color={V2T.text3} size={15} />
                    <Text {...DYNAMIC_TYPE}
                      style={[ss.sumNum, NUM, { fontFamily: fam(lang, "semi") }]}
                    >
                      {fmtCig(allUg)}
                    </Text>
                  </View>
                  <Text {...DYNAMIC_TYPE} style={[ss.sumCap, { fontFamily: fam(lang, "reg") }]}>
                    {t("breathed", lang)}
                  </Text>
                </View>
                {allEmitKg > 0 && (
                  <View style={ss.sumCol}>
                    <Text {...DYNAMIC_TYPE}
                      style={[ss.sumNum, NUM, { fontFamily: fam(lang, "semi") }]}
                    >
                      ≈{fmtKg(allEmitKg)}
                      <Text {...DYNAMIC_TYPE} style={ss.sumUnit}> kg</Text>
                    </Text>
                    <Text {...DYNAMIC_TYPE} style={[ss.sumCap, { fontFamily: fam(lang, "reg") }]}>
                      {t("putOut", lang)}
                    </Text>
                  </View>
                )}
              </View>
              {/* last-7-days context — "est." rides on the numbers via
                  tripsOutDetail; PROPOSED ledgerEstNote for a standing footnote */}
              {weekTrips > 0 && (
                <View style={ss.weekRow}>
                  <Text {...DYNAMIC_TYPE}
                    style={[ss.weekLabel, { fontFamily: fam(lang, "semi") }]}
                  >
                    {t("ledgerLast7", lang)}
                  </Text>
                  <Text {...DYNAMIC_TYPE}
                    style={[ss.weekLine, NUM, { fontFamily: fam(lang, "reg") }]}
                    numberOfLines={2}
                  >
                    {t(weekTrips === 1 ? "tripsCountOne" : "tripsCount", lang, {
                      n: weekTrips,
                    })}
                    {" · "}
                    {t("tripsCigs", lang, { n: fmtCig(week.weekUg) })}
                    {weekEmitKg > 0
                      ? ` · ${t("tripsOutDetail", lang, { n: fmtKg(weekEmitKg) })}`
                      : ""}
                  </Text>
                  {/* the week's breathing as a shape — bars are real
                      day-sums from saved trips, toned by dose severity;
                      the text line above already carries the numbers,
                      so the strip stays decorative for screen readers */}
                  <View style={ss.barsRow} importantForAccessibility="no" accessibilityElementsHidden>
                    {week.days.map((d, i) => (
                      <View key={i} style={ss.barCol}>
                        <View
                          style={[
                            ss.barFill,
                            {
                              height: d.ug <= 0 ? 3 : 4 + (d.ug / weekMaxUg) * 34,
                              backgroundColor: cigTone(d.ug),
                            },
                          ]}
                        />
                        <Text style={ss.barLbl}>{d.label.slice(0, 1)}</Text>
                      </View>
                    ))}
                  </View>
                </View>
              )}
            </View>
          ) : null
        }
        ListFooterComponent={
          sorted.length > 0 ? (
            <View style={ss.footer}>
              <Text {...DYNAMIC_TYPE} style={[ss.privacy, { fontFamily: fam(lang, "reg") }]}>
                {t("ledgerPrivacy", lang)}
              </Text>
              <Pressable
                onPress={confirmDeleteAll}
                accessibilityRole="button"
                accessibilityLabel={t("ledgerDeleteAll", lang)}
                style={({ pressed }) => [
                  ss.deleteAll,
                  pressed && { opacity: 0.6 },
                ]}
              >
                <Icon name="trash" color={V2T.breath3} size={15} />
                <Text {...DYNAMIC_TYPE}
                  style={[ss.deleteAllTxt, { fontFamily: fam(lang, "med") }]}
                >
                  {t("ledgerDeleteAll", lang)}
                </Text>
              </Pressable>
            </View>
          ) : null
        }
        ListEmptyComponent={loaded ? <EmptyState lang={lang} /> : null}
      />
    </View>
  );
}

/* ---------- public component: <LedgerScreen visible onClose lang/> ---------- */

export function LedgerScreen({
  visible,
  onClose,
  lang = "en",
  onTripsChanged,
}: {
  visible: boolean;
  onClose: () => void;
  lang?: Lang;
  onTripsChanged?: () => void;
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
        {visible ? <LedgerSheet onClose={onClose} lang={lang} onTripsChanged={onTripsChanged} /> : null}
      </View>
    </Modal>
  );
}

export default LedgerScreen;

const ss = StyleSheet.create({
  backdrop: { flex: 1, backgroundColor: V2T.scrim },
  root: {
    flex: 1,

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
    paddingHorizontal: 8,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: V2T.line,
  },
  // ≥44pt touch target on both ends of the bar
  barBtn: {
    width: 44,
    height: 44,
    alignItems: "center",
    justifyContent: "center",
  },
  barTitle: {
    flex: 1,
    textAlign: "center",
    color: V2T.text,
    fontSize: V2Type.body,
  },
  flex: { flex: 1 },
  listContent: { flexGrow: 1, paddingTop: 14 },

  summaryCard: {
    backgroundColor: V2T.surface,
    borderRadius: V2Radius.row,
    borderWidth: 1,
    borderColor: V2T.line,
    paddingHorizontal: 16,
    paddingTop: 16,
    paddingBottom: 14,
    marginHorizontal: 14,
    marginBottom: 14,
  },
  sumRow: { flexDirection: "row" },
  sumCol: { flex: 1 },
  sumHead: { flexDirection: "row", alignItems: "center", gap: 6 },
  sumNum: { color: V2T.text, fontSize: V2Type.title, lineHeight: 30 },
  sumUnit: { color: V2T.text2, fontSize: V2Type.secondary },
  sumCap: { color: V2T.text2, fontSize: V2Type.label, marginTop: 2 },
  weekRow: {
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: V2T.line,
    marginTop: 14,
    paddingTop: 10,
  },
  weekLabel: {
    color: V2T.text3,
    fontSize: V2Type.label,
    letterSpacing: 0.8,
    textTransform: "uppercase",
  },
  weekLine: { color: V2T.text2, fontSize: V2Type.label, marginTop: 4 },
  barsRow: {
    flexDirection: "row",
    alignItems: "flex-end",
    marginTop: 12,
    height: 52,
  },
  barCol: { flex: 1, alignItems: "center", justifyContent: "flex-end" },
  barFill: { width: 10, borderRadius: 5, minHeight: 3 },
  barLbl: { color: V2T.text3, fontSize: 9, marginTop: 4 },

  dayHead: {
    color: V2T.text3,
    fontSize: V2Type.label,
    letterSpacing: 0.4,
    marginHorizontal: 18,
    marginTop: 8,
    marginBottom: 8,
  },

  card: {
    marginHorizontal: 14,
    marginBottom: 8,
    backgroundColor: V2T.surface,
    borderRadius: V2Radius.row,
    borderWidth: 1,
    borderColor: V2T.line,
    overflow: "hidden",
  },
  cardHead: {
    flexDirection: "row",
    alignItems: "center",
    minHeight: 60,
    paddingHorizontal: 12,
    paddingVertical: 10,
    gap: 10,
  },
  modeBox: {
    width: 38,
    height: 38,
    borderRadius: 19,
    backgroundColor: V2T.surface2,
    alignItems: "center",
    justifyContent: "center",
  },
  tripMid: { flex: 1, marginRight: 6 },
  tripRoute: { color: V2T.text, fontSize: V2Type.secondary },
  tripMeta: { color: V2T.text3, fontSize: V2Type.label, marginTop: 1 },
  tripSaved: { color: V2T.text2, fontSize: V2Type.label, marginTop: 2 },
  tripNums: { alignItems: "flex-end", marginRight: 2 },
  cigRow: { flexDirection: "row", alignItems: "center", gap: 5 },
  cigNum: { fontSize: V2Type.secondary },
  outNum: { color: V2T.text3, fontSize: V2Type.label, marginTop: 2 },

  detail: {
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: V2T.line,
    paddingHorizontal: 14,
    paddingTop: 8,
    paddingBottom: 4,
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
    minHeight: 44,
    alignSelf: "flex-start",
    paddingRight: 10,
  },
  dDeleteTxt: { color: V2T.breath3, fontSize: V2Type.label },

  emptyWrap: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: 44,
    paddingBottom: 72,
  },
  emptyBadge: {
    width: 64,
    height: 64,
    borderRadius: 32,
    backgroundColor: V2T.surface,
    borderWidth: 1,
    borderColor: V2T.line,
    alignItems: "center",
    justifyContent: "center",
  },
  emptyTitle: {
    color: V2T.text,
    fontSize: V2Type.title,
    marginTop: 18,
  },
  emptyHint: {
    color: V2T.text2,
    fontSize: V2Type.secondary,
    textAlign: "center",
    lineHeight: 22,
    marginTop: 8,
    maxWidth: 280,
  },
  emptyPrivacy: { color: V2T.text3, fontSize: V2Type.label, marginTop: 12 },

  footer: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginHorizontal: 18,
    marginTop: 14,
  },
  privacy: { color: V2T.text3, fontSize: V2Type.label, flex: 1 },
  deleteAll: {
    flexDirection: "row",
    alignItems: "center",
    gap: 7,
    minHeight: 44,
    paddingHorizontal: 8,
  },
  deleteAllTxt: { color: V2T.breath3, fontSize: V2Type.label },
});
