/** your lungs' calendar — the calendar-like dose strip: seven day-cells,
 *  oldest → today, each washed in its dose severity against the user's
 *  daily limit (the hero's own tier rule). "today" is labelled, never
 *  guessed.
 *
 *  A tap — cell or header — opens the WeekSheet: the full lungs'
 *  calendar surface (the week as a real calendar + the picked day's
 *  story + the air ahead). The strip itself is the preview, not the
 *  detail (home-truth lane: the owner asked for the tap to open the
 *  weekly component).
 *
 *  Truth rule (unchanged): cells render only counted dose — the
 *  on-device reconstruction over real ambient reads + logged trips. An
 *  uncounted day is a bare stub, never a claimed zero; when no day in
 *  the window counted, the strip unmounts and the hero's sparse copy
 *  already says why.
 *
 *  Mount (HomeScreen):
 *    <WeekStrip week={data.week} budgetUg={budget} lang={lang}
 *      onOpen={setWeekDay} />
 */
import React from "react";
import {
  Pressable,
  StyleSheet,
  Text,
  View,
} from "react-native";
import {
  NUM,
  V2Elev,
  V2Radius,
  V2T,
  V2Type,
  bandEdgeIdx,
  bandInkIdx,
  bandWashDeepIdx,
  doseDotColor,
  doseTierIdx,
  fam,
  famMono,
  famMonoText,
} from "../../theme";
import { approx, doseUgRound, t, type Lang } from "../../i18n/strings";
import { DYNAMIC_TYPE } from "../../a11y";
import { tick } from "../../haptics";
import { bump } from "../../perf";
import { type DayReconstruction } from "../../store/daylog";
import { Icon } from "../../icons";

/** One week cell's payload — the flattened `ug` keeps the hero's
 *  mini-bars and the peek dots reading cheaply; `rec` is the day's full
 *  reconstruction for the sheet's day detail (arc, parts, covered
 *  minutes). */
export type WeekDay = { day: string; ug: number; rec: DayReconstruction };

function WeekStripInner({ week, budgetUg, lang, onOpen }: {
  week: WeekDay[]; budgetUg: number; lang: Lang;
  /** a cell or the header tapped — the parent mounts the WeekSheet on
      that day key (today when the header asked) */
  onOpen?: (day: string) => void;
}) {
  bump("home.WeekStrip");
  const counted = week.some((w) => w.ug > 0);
  if (!counted) return null; // the hero's sparse copy already says it
  const maxW = Math.max(...week.map((w) => w.ug), 1);
  /* today is the last cell by construction (useDayData appends it last)
     — no clock read needed to find it */
  const todayK = week[week.length - 1]?.day;
  const total = week.reduce((s, w) => s + w.ug, 0);
  const locale = lang === "hi" ? "hi-IN" : "en-IN";
  return (
    <View style={ss.card}>
      <Pressable onPress={() => { if (onOpen && todayK) { tick(); onOpen(todayK); } }}
        accessibilityRole="button" accessibilityLabel={t("weekOpen", lang)}
        style={({ pressed }) => [ss.head, pressed && { opacity: 0.7 }]}>
        <Text {...DYNAMIC_TYPE} style={[ss.cardTitle, { fontFamily: fam(lang, "semi") }]}>
          {t("weekTitle", lang)}
        </Text>
        <View style={ss.headRight}>
          <Text {...DYNAMIC_TYPE} style={[ss.total, NUM, { fontFamily: famMono(lang, "med") }]}>
            {t("homeWeek", lang, { n: approx(doseUgRound(total)) })}
          </Text>
          <Icon name="chevron" color={V2T.text4} size={15} />
        </View>
      </Pressable>
      <View style={ss.row}>
        {week.map((w) => {
          const isToday = w.day === todayK;
          /* the band IS the scan cue — the day-cell wears its dose
             severity the way the days-ahead cells wear the day's air:
             deep wash, band-inked label; a quiet day stays neutral */
          const tier = doseTierIdx(w.ug, budgetUg);
          const cellBg = tier != null ? bandWashDeepIdx(tier) : V2T.surface2;
          const cellEdge = tier != null ? bandEdgeIdx(tier) : "transparent";
          const dayCol = isToday
            ? V2T.accentInk
            : (tier != null ? bandInkIdx(tier) ?? V2T.text3 : V2T.text3);
          /* midday anchor dodges DST/edge hours in the weekday read;
             today's cell speaks its name instead of a bare letter */
          const letter = isToday
            ? t("dayLbl_today", lang)
            : new Date(`${w.day}T12:00:00`).toLocaleDateString(locale, { weekday: "narrow" });
          return (
            <Pressable key={w.day}
              onPress={() => { tick(); onOpen?.(w.day); }}
              accessibilityRole="button"
              accessibilityLabel={`${letter} ${doseUgRound(w.ug)}`}
              style={({ pressed }) => [
                ss.cell,
                { backgroundColor: cellBg, borderColor: cellEdge },
                pressed && { transform: [{ scale: 0.96 }] },
              ]}>
              <Text {...DYNAMIC_TYPE} numberOfLines={1} adjustsFontSizeToFit minimumFontScale={0.7}
                style={[ss.day, { fontFamily: famMonoText(lang), color: dayCol }]}>
                {letter}
              </Text>
              <View style={ss.barCol}>
                <View style={[ss.bar, {
                  height: w.ug > 0 ? 4 + 30 * (w.ug / maxW) : 4,
                  backgroundColor: w.ug > 0 ? doseDotColor(w.ug, budgetUg) : V2T.surface3,
                  opacity: w.ug > 0 ? 0.55 + 0.45 * (w.ug / maxW) : 0.9,
                }]} />
              </View>
              <Text {...DYNAMIC_TYPE} numberOfLines={1} adjustsFontSizeToFit minimumFontScale={0.7}
                style={[ss.ug, NUM, { fontFamily: famMono(lang) }, isToday && { color: V2T.text }]}>
                {w.ug > 0 ? `${approx(doseUgRound(w.ug))}` : " "}
              </Text>
            </Pressable>
          );
        })}
      </View>
      <Text {...DYNAMIC_TYPE} style={[ss.hint, { fontFamily: fam(lang, "reg") }]}>
        {t("weekSheetFine", lang)}
      </Text>
    </View>
  );
}

export const WeekStrip = React.memo(WeekStripInner);

const ss = StyleSheet.create({
  card: {
    ...V2Elev.card,
    backgroundColor: V2T.surface,
    borderRadius: V2Radius.card,
    paddingHorizontal: 16, paddingTop: 16, paddingBottom: 16,
  },
  cardTitle: { color: V2T.text, fontSize: V2Type.secondary, marginBottom: 10 },
  head: { flexDirection: "row", alignItems: "baseline", justifyContent: "space-between" },
  headRight: { flexDirection: "row", alignItems: "center", gap: 4 },
  total: { color: V2T.text3, fontSize: V2Type.label },
  /* one quiet line under the cells — why a blank day is a blank day */
  hint: { color: V2T.text4, fontSize: V2Type.micro, marginTop: 10 },
  /* the cells — the days-ahead row's grammar: chunky band-washed tiles */
  row: { flexDirection: "row", gap: 6 },
  cell: {
    flex: 1,
    borderRadius: 15, backgroundColor: V2T.surface2,
    paddingHorizontal: 4, paddingTop: 9, paddingBottom: 8,
    alignItems: "center",
  },
  cellSel: { borderColor: V2T.accent, borderWidth: 1.5 },
  day: { color: V2T.text3, fontSize: V2Type.micro },
  barCol: { height: 34, justifyContent: "flex-end", marginTop: 4 },
  bar: { width: 8, borderRadius: 4 },
  ug: { color: V2T.text3, fontSize: V2Type.micro, marginTop: 4, height: 13 },
});
