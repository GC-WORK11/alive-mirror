/** your lungs' calendar — the weekly sheet the owner asked for (the home
 *  strip's tap target): the last 7 counted days drawn as a real calendar
 *  — weekday letter over a serif date numeral over the day's dose — then
 *  the picked day's own story (arc + accumulators, the same truth the
 *  strip's inline detail carried), then the air AHEAD as a second,
 *  ghosted row so the week reads past→future in one surface.
 *
 *  Truth rules (unchanged from the strip):
 *   - dose cells colour by the day's severity against YOUR daily limit
 *     (doseTierIdx — the hero's own rule); forecast cells colour by the
 *     day's air band (CPCB). Two different meanings, two different
 *     sections — never one rainbow.
 *   - an uncounted day is an empty stub, never a claimed zero; the
 *     footer says so in plain words.
 *   - forecast days carry the server's own fields verbatim (band, mid,
 *     partial-hours, cleanest window) — nothing derived client-side
 *     beyond dayLabel localisation.
 *
 *  Motion: the receipt's own grammar — a bottom sheet that rises + fades
 *  (enter spring), section fade-ins staggered, reduce-motion jumps to
 *  final. Mount inside the home surface:
 *
 *    {weekDay != null && (
 *      <WeekSheet day={weekDay} week={data.week} outlook={data.outlook}
 *        budgetUg={budget} lang={lang} onClose={() => setWeekDay(null)} />
 *    )}
 */
import React, { useEffect, useState } from "react";
import {
  Animated,
  LayoutAnimation,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import {
  NUM,
  V2Elev,
  V2Radius,
  V2T,
  V2Type,
  bandColorIdx,
  bandEdgeIdx,
  bandIdx,
  bandInkIdx,
  bandWashDeepIdx,
  doseDotColor,
  doseTierIdx,
  fam,
  famMono,
  famMonoText,
  famSerif,
} from "../../theme";
import { approx, doseUgRound, t, type Lang } from "../../i18n/strings";
import { CLEAN_UG, bandIdxForName, type Outlook } from "../../api/outlook";
import { DYNAMIC_TYPE, useReduceMotion } from "../../a11y";
import { tick } from "../../haptics";
import { bump, jank } from "../../perf";
import { Icon } from "../../icons";
import { FadeIn, Quiet } from "../../ui";
import { dayLabel, fieldAgeLine, outlookCaption } from "./daywords";
import { HourArc } from "./HourArc";
import type { WeekDay } from "./WeekStrip";

function WeekSheetInner({ day, week, outlook, budgetUg, profileSet, lang, onClose }: {
  /** the day the strip opened on (yyyy-mm-dd, the week's own keys) */
  day: string;
  /** the 7-day window, oldest → today (WeekStrip's payload) */
  week: WeekDay[];
  /** the folded days ahead — null keeps the section out entirely */
  outlook: Outlook | null;
  budgetUg: number;
  /** false → the % line under a day reads 'of the suggested limit', not
      'of your limit' — the ceiling is a shipped default until picked (F7) */
  profileSet?: boolean;
  lang: Lang;
  onClose: () => void;
}) {
  bump("home.WeekSheet");
  const insets = useSafeAreaInsets();
  const reduceMotion = useReduceMotion();
  const [sel, setSel] = useState(day);
  /* the receipt's own enter — a bottom sheet that rises + settles */
  const [enter] = useState(() => new Animated.Value(0));
  const [enterTy] = useState(() =>
    enter.interpolate({ inputRange: [0, 1], outputRange: [42, 0] }));
  useEffect(() => {
    if (reduceMotion) { enter.setValue(1); return; }
    jank("enter.weekSheet");
    Animated.spring(enter, {
      toValue: 1, damping: 26, stiffness: 220, useNativeDriver: true,
    }).start();
  }, [enter, reduceMotion]);

  const todayK = week[week.length - 1]?.day;
  const open = week.find((w) => w.day === sel) ?? week[week.length - 1] ?? null;
  const openIsToday = open != null && open.day === todayK;
  const maxW = Math.max(...week.map((w) => w.ug), 1);
  const total = week.reduce((s, w) => s + w.ug, 0);
  const countedN = week.filter((w) => w.ug > 0).length;
  const openCovH = open ? Math.floor(open.rec.coveredMin / 60) : 0;
  const openCovM = open ? open.rec.coveredMin % 60 : 0;
  const openPct = open != null && budgetUg > 0
    ? Math.round((open.ug / budgetUg) * 100) : 0;
  const locale = lang === "hi" ? "hi-IN" : "en-IN";
  const days = outlook?.days.slice(0, 5) ?? [];
  const caption = outlook ? outlookCaption(outlook, lang) : "";
  const ageLine = outlook
    ? fieldAgeLine(outlook.fieldAgeS, outlook.fieldStale, lang) : null;

  const pick = (d: string) => {
    tick();
    /* the detail panel swaps — ease it like the strip's own expander */
    if (!reduceMotion) LayoutAnimation.configureNext(LayoutAnimation.Presets.easeInEaseOut);
    setSel(d);
  };

  return (
    <View style={ws.wrap}>
      {/* warm scrim — the surface dims, never blackens; tap dismisses,
          but it's not a control (the X owns the Done affordance) */}
      <Pressable style={ws.scrim} onPress={() => { tick(); onClose(); }}
        accessible={false} />
      <Animated.View style={[ws.sheet, {
        paddingBottom: insets.bottom + 16,
        opacity: enter, transform: [{ translateY: enterTy }],
      }]}>
        {/* grab handle — the sheet's own affordance */}
        <View style={ws.grab} />
        <View style={ws.head}>
          <View style={ws.flex}>
            <Text {...DYNAMIC_TYPE} style={[ws.title, { fontFamily: famSerif(lang, "semi") }]}>
              {t("weekTitle", lang)}
            </Text>
            <Text {...DYNAMIC_TYPE} style={[ws.sub, { fontFamily: fam(lang, "reg") }]}>
              {t("weekSheetSub", lang)}
            </Text>
          </View>
          <Pressable onPress={() => { tick(); onClose(); }} hitSlop={12}
            accessibilityRole="button" accessibilityLabel={t("done", lang)}
            style={({ pressed }) => [ws.closeBtn, pressed && { opacity: 0.55 }]}>
            <Icon name="close" color={V2T.text3} size={16} />
          </Pressable>
        </View>
        <Text {...DYNAMIC_TYPE} style={[ws.weekTotal, NUM, { fontFamily: fam(lang, "med") }]}>
          {t("homeWeek", lang, { n: approx(doseUgRound(total)) })}
          <Text style={[ws.weekTotalSub, { fontFamily: fam(lang, "reg") }]}>
            {`  ·  ${t("weekCountedFine", lang, { n: countedN, m: 7 })}`}
          </Text>
        </Text>

        <ScrollView showsVerticalScrollIndicator={false}>
          {/* ── the calendar ── */}
          <View style={ws.calRow}>
            {week.map((w) => {
              const isToday = w.day === todayK;
              const isSel = open != null && w.day === open.day;
              const tier = doseTierIdx(w.ug, budgetUg);
              const cellBg = tier != null ? bandWashDeepIdx(tier) : V2T.surface2;
              const cellEdge = isSel ? V2T.accent
                : tier != null ? bandEdgeIdx(tier) : "transparent";
              const dt = new Date(`${w.day}T12:00:00`);
              const letter = isToday ? t("dayLbl_today", lang)
                : dt.toLocaleDateString(locale, { weekday: "narrow" });
              return (
                <Pressable key={w.day} onPress={() => pick(w.day)}
                  accessibilityRole="button" accessibilityState={{ selected: isSel }}
                  /* the strip's grammar: the unit rides the number —
                     'monday ≈42 µg', not a bare 'monday 42' (numbers-sweep) */
                  accessibilityLabel={`${letter}, ${w.ug > 0 ? `${approx(doseUgRound(w.ug))} µg` : t("weekNoReads", lang)}`}
                  style={({ pressed }) => [
                    ws.calCell,
                    { backgroundColor: cellBg, borderColor: cellEdge },
                    pressed && { transform: [{ scale: 0.95 }] },
                  ]}>
                  <Text {...DYNAMIC_TYPE} numberOfLines={1} adjustsFontSizeToFit minimumFontScale={0.7}
                    style={[ws.calDay, { fontFamily: famMonoText(lang), color: V2T.text3 }]}>
                    {letter}
                  </Text>
                  <Text {...DYNAMIC_TYPE}
                    style={[ws.calDate, NUM, { fontFamily: famSerif(lang, "semi"),
                      color: tier != null ? bandInkIdx(tier) ?? V2T.text : V2T.text2 }]}>
                    {dt.getDate()}
                  </Text>
                  <View style={ws.calBarCol}>
                    <View style={[ws.calBar, {
                      height: w.ug > 0 ? 4 + 26 * (w.ug / maxW) : 4,
                      backgroundColor: w.ug > 0 ? doseDotColor(w.ug, budgetUg) : V2T.surface3,
                    }]} />
                  </View>
                  <Text {...DYNAMIC_TYPE} numberOfLines={1} adjustsFontSizeToFit minimumFontScale={0.7}
                    style={[ws.calUg, NUM, { fontFamily: famMono(lang) }]}>
                    {w.ug > 0 ? `${approx(doseUgRound(w.ug))}` : " "}
                  </Text>
                </Pressable>
              );
            })}
          </View>

          {/* ── the picked day ── */}
          {open && (
            <FadeIn delay={0}>
              <View style={ws.dayBlock}>
                <Text {...DYNAMIC_TYPE} style={[ws.dayHead, { fontFamily: famMonoText(lang, "med") }]}>
                  {`${new Date(`${open.day}T12:00:00`).toLocaleDateString(locale, { weekday: "long" })} · ${new Date(`${open.day}T12:00:00`).toLocaleDateString(locale, { day: "numeric", month: "short" })}`}
                </Text>
                {!open.rec.thin ? (
                  <>
                    <Text {...DYNAMIC_TYPE} style={[ws.dayDose, NUM, { fontFamily: famSerif(lang, "med"),
                      color: doseDotColor(open.ug, budgetUg) }]}>
                      {t("weekDayDose", lang, { n: approx(doseUgRound(open.ug)) })}
                    </Text>
                    {openPct > 0 && (
                      <Text {...DYNAMIC_TYPE} style={[ws.dayPct, NUM, { fontFamily: fam(lang, "reg") }]}>
                        {t(profileSet ? "weekDayPct" : "weekDayPctSugg", lang, { p: openPct })}
                      </Text>
                    )}
                    {open.rec.coveredMin > 0 && (
                      <Text {...DYNAMIC_TYPE} style={[ws.dayNote, NUM, { fontFamily: famMonoText(lang) }]}>
                        {openCovH > 0
                          ? t("dayCovered", lang, { h: openCovH, m: openCovM })
                          : t("dayCoveredMin", lang, { m: openCovM })}
                      </Text>
                    )}
                    <HourArc rec={open.rec} lang={lang} nh={openIsToday ? undefined : -1} />
                    {open.rec.parts.length > 0 && (
                      <>
                        <Text {...DYNAMIC_TYPE} style={[ws.partsTitle, { fontFamily: fam(lang, "med") }]}>
                          {t("dayPartsTitle", lang)}
                        </Text>
                        {open.rec.parts.map((p, i) => {
                          const pt = doseTierIdx(p.ug, budgetUg);
                          return (
                            <View key={i} style={ws.partChip}>
                              <View style={[ws.partSpine, { backgroundColor: doseDotColor(p.ug, budgetUg) }]} />
                              <Text {...DYNAMIC_TYPE} style={[ws.partLabel, { fontFamily: fam(lang, "reg") }]}
                                numberOfLines={1}>
                                {p.label}
                              </Text>
                              <Text {...DYNAMIC_TYPE} style={[ws.partUg, NUM, {
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
                  <Quiet glyph="dust" title={t("weekDayThin", lang)} lang={lang} />
                )}
              </View>
            </FadeIn>
          )}

          {/* ── the air ahead — the forecast, honestly labelled ── */}
          {days.length > 0 && (
            <FadeIn delay={60}>
              <View style={ws.aheadBlock}>
                <Text {...DYNAMIC_TYPE} style={[ws.aheadTitle, { fontFamily: fam(lang, "semi") }]}>
                  {t("weekAheadTitle", lang)}
                </Text>
                <Text {...DYNAMIC_TYPE} style={[ws.aheadSub, { fontFamily: fam(lang, "reg") }]}>
                  {t("weekAheadSub", lang)}
                </Text>
                <View style={ws.aheadRow}>
                  {days.map((d) => {
                    const best = outlook?.best_day?.date_ist === d.date_ist;
                    const bi = bandIdxForName(d.band) ?? bandIdx(d.pm25_mid);
                    const dot = bandColorIdx(bi) ?? V2T.text4;
                    const bg = bi != null ? bandWashDeepIdx(bi) : V2T.surface2;
                    return (
                      <View key={d.date_ist}
                        style={[ws.aCell, { backgroundColor: bg },
                          d.confidence === "lo" && { opacity: 0.62 }]}>
                        <Text {...DYNAMIC_TYPE} numberOfLines={1} adjustsFontSizeToFit minimumFontScale={0.7}
                          style={[ws.aDay, { fontFamily: famMonoText(lang), color: V2T.text3 }]}>
                          {dayLabel(d.label, lang)}
                        </Text>
                        <View style={ws.aDotRow}>
                          <View style={[ws.aDot, { backgroundColor: dot }]} />
                          <Text {...DYNAMIC_TYPE} style={[ws.aMid, NUM, {
                            fontFamily: famMono(lang, "med"),
                            color: bi != null ? bandInkIdx(bi) ?? V2T.text : V2T.text,
                          }]}>
                            {Math.round(d.pm25_mid)}
                          </Text>
                        </View>
                        <Text {...DYNAMIC_TYPE} numberOfLines={1}
                          style={[ws.aSub, { fontFamily: famMono(lang) }]}>
                          {d.partial ? t("hourTickTilde", lang, { n: d.n_hours }) : " "}
                        </Text>
                        <Text {...DYNAMIC_TYPE} numberOfLines={1} adjustsFontSizeToFit minimumFontScale={0.7}
                          style={[ws.aMark, { fontFamily: fam(lang, "med") }]}>
                          {best ? t(d.pm25_mid > CLEAN_UG ? "dayOutlookLeastBad" : "dayOutlookCleanest", lang) : " "}
                        </Text>
                      </View>
                    );
                  })}
                </View>
                {!!caption && (
                  <Text {...DYNAMIC_TYPE} style={[ws.aheadVerdict, { fontFamily: fam(lang, "med") }]}>
                    {caption}
                  </Text>
                )}
                <Text {...DYNAMIC_TYPE} style={[ws.aheadUnit, { fontFamily: famMono(lang) }]}>
                  {t("weekAheadUnit", lang)}
                </Text>
              </View>
            </FadeIn>
          )}

          {/* ── the honesty footer ── */}
          <Text {...DYNAMIC_TYPE} style={[ws.fine, { fontFamily: fam(lang, "reg") }]}>
            {t("weekSheetFine", lang)}
          </Text>
          {ageLine ? (
            <Text {...DYNAMIC_TYPE} style={[ws.fine, { fontFamily: fam(lang, "reg") }]}>
              {ageLine}
            </Text>
          ) : null}
        </ScrollView>
      </Animated.View>
    </View>
  );
}

export const WeekSheet = React.memo(WeekSheetInner);

const ws = StyleSheet.create({
  /* rides over the home surface's own backdrop (elevation 24) */
  wrap: { ...StyleSheet.absoluteFill, elevation: 30, zIndex: 30 },
  scrim: { ...StyleSheet.absoluteFill, backgroundColor: "rgba(59,52,35,0.28)" },
  sheet: {
    position: "absolute", left: 0, right: 0, bottom: 0,
    maxHeight: "88%",
    ...V2Elev.sheet,
    backgroundColor: V2T.surface,
    borderTopLeftRadius: V2Radius.sheet, borderTopRightRadius: V2Radius.sheet,
    paddingHorizontal: 18, paddingTop: 10,
  },
  grab: {
    alignSelf: "center", width: 36, height: 4, borderRadius: 2,
    backgroundColor: V2T.hairline, marginBottom: 10,
  },
  head: { flexDirection: "row", alignItems: "flex-start", gap: 10 },
  flex: { flex: 1 },
  title: { color: V2T.text, fontSize: 24, lineHeight: 29 },
  sub: { color: V2T.text3, fontSize: V2Type.label, marginTop: 3 },
  closeBtn: {
    width: 30, height: 30, borderRadius: 15,
    backgroundColor: V2T.surface2, alignItems: "center", justifyContent: "center",
    marginTop: 2,
  },
  weekTotal: { color: V2T.text2, fontSize: V2Type.secondary, marginTop: 8, marginBottom: 12 },
  weekTotalSub: { color: V2T.text3, fontSize: V2Type.label },

  /* the calendar — each cell a real day: letter, date numeral, dose bar */
  calRow: { flexDirection: "row", gap: 5 },
  calCell: {
    flex: 1, borderRadius: 14, borderWidth: 1.5,
    paddingHorizontal: 2, paddingTop: 8, paddingBottom: 7,
    alignItems: "center",
  },
  calDay: { fontSize: V2Type.micro },
  calDate: { fontSize: 21, marginTop: 2 },
  calBarCol: { height: 30, justifyContent: "flex-end", marginTop: 4 },
  calBar: { width: 8, borderRadius: 4 },
  calUg: { color: V2T.text3, fontSize: V2Type.micro, marginTop: 4, height: 13 },

  /* the picked day — a hairline-tucked panel, same grammar as the day card */
  dayBlock: {
    marginTop: 14, paddingTop: 12,
    borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: V2T.line,
  },
  dayHead: { color: V2T.text3, fontSize: V2Type.micro, letterSpacing: 1.0 },
  dayDose: { fontSize: 30, lineHeight: 36, marginTop: 8 },
  dayPct: { color: V2T.text3, fontSize: V2Type.label, marginTop: 2 },
  dayNote: { color: V2T.text3, fontSize: V2Type.micro, marginTop: 8 },
  partsTitle: { color: V2T.text3, fontSize: V2Type.label, marginTop: 14, marginBottom: 6 },
  partChip: {
    flexDirection: "row", alignItems: "center", gap: 10,
    backgroundColor: V2T.surface2, borderRadius: V2Radius.row,
    paddingHorizontal: 10, paddingVertical: 9, marginTop: 6,
  },
  partSpine: { width: 4, height: 18, borderRadius: 2 },
  partLabel: { color: V2T.text, fontSize: V2Type.secondary, flex: 1 },
  partUg: { color: V2T.text, fontSize: V2Type.label },

  /* the air ahead — forecast cells wear the day's air band */
  aheadBlock: {
    marginTop: 16, paddingTop: 12,
    borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: V2T.line,
  },
  aheadTitle: { color: V2T.text, fontSize: V2Type.secondary },
  aheadSub: { color: V2T.text3, fontSize: V2Type.label, marginTop: 2, marginBottom: 10 },
  aheadRow: { flexDirection: "row", gap: 5 },
  aCell: {
    flex: 1, borderRadius: 14,
    paddingHorizontal: 2, paddingTop: 8, paddingBottom: 7,
    alignItems: "center",
  },
  aDay: { fontSize: V2Type.micro },
  aDotRow: { flexDirection: "row", alignItems: "center", gap: 4, marginTop: 4 },
  aDot: { width: 6, height: 6, borderRadius: 3 },
  aMid: { fontSize: V2Type.label },
  aSub: { color: V2T.text3, fontSize: V2Type.micro, marginTop: 3, height: 13 },
  aMark: { color: V2T.text3, fontSize: V2Type.micro, height: 13 },
  aheadVerdict: { color: V2T.text2, fontSize: V2Type.label, marginTop: 10 },
  aheadUnit: { color: V2T.text4, fontSize: V2Type.micro, marginTop: 4 },

  fine: { color: V2T.text3, fontSize: V2Type.micro, marginTop: 12 },
});
