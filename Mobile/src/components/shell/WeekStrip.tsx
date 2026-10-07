/** your week — the calendar-like dose distribution the owner asked for.
 *  Seven day-cells, oldest → today: the weekday letter over a dose bar
 *  (height = the day's counted µg, hue = its severity against the user's
 *  budget — the hero's own tier rule), the cell itself washed in that
 *  day's band the way the days-ahead cells carry theirs. "today" is
 *  labelled, never guessed.
 *
 *  A tap unfolds the day in place — the same hour arc + accumulators the
 *  DayCard serves for today, so the strip is a week of day detail, not
 *  seven dead squares (the days-ahead row's own expander grammar).
 *
 *  Truth rule (unchanged from the inline card this replaced): cells
 *  render only counted dose — the on-device reconstruction over real
 *  ambient reads + logged trips. An uncounted day is a bare stub, never
 *  a claimed zero; when no day in the window counted, the strip unmounts
 *  and the hero's sparse copy already says why.
 *
 *  Mount (HomeScreen):
 *    <WeekStrip week={data.week} budgetUg={budget} lang={lang} />
 */
import React, { useState } from "react";
import {
  LayoutAnimation,
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
import { DYNAMIC_TYPE, useReduceMotion } from "../../a11y";
import { tick } from "../../haptics";
import { bump } from "../../perf";
import { type DayReconstruction } from "../../store/daylog";
import { HourArc } from "./HourArc";

/** One week cell's payload — the flattened `ug` keeps the hero's
 *  mini-bars and the peek dots reading cheaply; `rec` is the day's full
 *  reconstruction for the tap detail (arc, parts, covered minutes). */
export type WeekDay = { day: string; ug: number; rec: DayReconstruction };

function WeekStripInner({ week, budgetUg, lang }: {
  week: WeekDay[]; budgetUg: number; lang: Lang;
}) {
  bump("home.WeekStrip");
  const reduceMotion = useReduceMotion();
  const [openDay, setOpenDay] = useState<string | null>(null);
  const counted = week.some((w) => w.ug > 0);
  if (!counted) return null; // the hero's sparse copy already says it
  const maxW = Math.max(...week.map((w) => w.ug), 1);
  /* today is the last cell by construction (useDayData appends it last)
     — no clock read needed to find it */
  const todayK = week[week.length - 1]?.day;
  const total = week.reduce((s, w) => s + w.ug, 0);
  const open = week.find((w) => w.day === openDay) ?? null;
  const openIsToday = open != null && open.day === todayK;
  const openCovH = open ? Math.floor(open.rec.coveredMin / 60) : 0;
  const openCovM = open ? open.rec.coveredMin % 60 : 0;
  const locale = lang === "hi" ? "hi-IN" : "en-IN";
  return (
    <View style={ss.card}>
      <View style={ss.head}>
        <Text {...DYNAMIC_TYPE} style={[ss.cardTitle, { fontFamily: fam(lang, "semi") }]}>
          {t("weekTitle", lang)}
        </Text>
        <Text {...DYNAMIC_TYPE} style={[ss.total, NUM, { fontFamily: famMono(lang, "med") }]}>
          {t("homeWeek", lang, { n: approx(doseUgRound(total)) })}
        </Text>
      </View>
      <View style={ss.row}>
        {week.map((w) => {
          const isToday = w.day === todayK;
          const sel = openDay === w.day;
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
              onPress={() => {
                tick();
                /* the detail mounts under the strip — ease it like the
                   days-ahead expander (native path) */
                if (!reduceMotion) LayoutAnimation.configureNext(LayoutAnimation.Presets.easeInEaseOut);
                setOpenDay(sel ? null : w.day);
              }}
              accessibilityRole="button"
              accessibilityState={{ expanded: sel }}
              accessibilityLabel={`${letter} ${doseUgRound(w.ug)}`}
              style={({ pressed }) => [
                ss.cell,
                { backgroundColor: cellBg, borderColor: cellEdge },
                sel && ss.cellSel,
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
      {open && (
        <View style={ss.detail}>
          <Text {...DYNAMIC_TYPE} style={[ss.detailHead, { fontFamily: famMonoText(lang, "med") }]}>
            {`${new Date(`${open.day}T12:00:00`).toLocaleDateString(locale, { weekday: "long" })} · ${new Date(`${open.day}T12:00:00`).toLocaleDateString(locale, { day: "numeric", month: "short" })}`}
          </Text>
          {!open.rec.thin ? (
            <>
              {open.rec.coveredMin > 0 && (
                <Text {...DYNAMIC_TYPE} style={[ss.detailNote, NUM, { fontFamily: famMonoText(lang) }]}>
                  {openCovH > 0
                    ? t("dayCovered", lang, { h: openCovH, m: openCovM })
                    : t("dayCoveredMin", lang, { m: openCovM })}
                </Text>
              )}
              <HourArc rec={open.rec} lang={lang} nh={openIsToday ? undefined : -1} />
              {open.rec.parts.length > 0 && (
                <>
                  <Text {...DYNAMIC_TYPE} style={[ss.partsTitle, { fontFamily: fam(lang, "med") }]}>
                    {t("dayPartsTitle", lang)}
                  </Text>
                  {/* each span is a chip — a dose-tinted spine, the span's
                      own words, its µg count (the DayCard's grammar) */}
                  {open.rec.parts.map((p, i) => {
                    const pt = doseTierIdx(p.ug, budgetUg);
                    return (
                      <View key={i} style={ss.partChip}>
                        <View style={[ss.partSpine, { backgroundColor: doseDotColor(p.ug, budgetUg) }]} />
                        <Text {...DYNAMIC_TYPE} style={[ss.partLabel, { fontFamily: fam(lang, "reg") }]}
                          numberOfLines={1}>
                          {p.label}
                        </Text>
                        <Text {...DYNAMIC_TYPE} style={[ss.partUg, NUM, {
                          fontFamily: famMono(lang, "med"),
                          color: pt != null ? bandInkIdx(pt) ?? V2T.text : V2T.text,
                        }]}>
                          {approx(doseUgRound(p.ug))} µg
                        </Text>
                      </View>
                    );
                  })}
                </>
              )}
            </>
          ) : (
            <Text {...DYNAMIC_TYPE} style={[ss.detailNote, { fontFamily: fam(lang, "reg") }]}>
              {t("weekDayThin", lang)}
            </Text>
          )}
        </View>
      )}
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
  total: { color: V2T.text3, fontSize: V2Type.label },
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
  /* the day detail — same hairline-tucked expansion the days-ahead
     card uses under its own cells */
  detail: {
    marginTop: 12, paddingTop: 12,
    borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: V2T.line,
  },
  detailHead: { color: V2T.text3, fontSize: V2Type.micro, letterSpacing: 1.0 },
  detailNote: { color: V2T.text3, fontSize: V2Type.micro, marginTop: 6 },
  partsTitle: {
    color: V2T.text3, fontSize: V2Type.label,
    marginTop: 14, marginBottom: 6,
  },
  partChip: {
    flexDirection: "row", alignItems: "center", gap: 10,
    backgroundColor: V2T.surface2, borderRadius: V2Radius.row,
    paddingHorizontal: 10, paddingVertical: 9, marginTop: 6,
  },
  partSpine: { width: 4, height: 18, borderRadius: 2 },
  partLabel: { color: V2T.text, fontSize: V2Type.secondary, flex: 1 },
  partUg: { color: V2T.text, fontSize: V2Type.label },
});
