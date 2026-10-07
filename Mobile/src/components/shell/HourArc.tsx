/** The day's 24-slot hour arc — a scrubbable heat strip of counted dose.
 *  Extracted from HomeScreen.tsx by the weekview lane so the week strip's
 *  tap-a-day detail renders the same day view DayCard serves for today;
 *  markup, gestures, copy and styling are identical — only the "now" hour
 *  is a prop (`nh`), because a past day's arc has no live hour to light.
 *
 *  Mount:
 *    <HourArc rec={rec} lang={lang} />          // today — live hour lit
 *    <HourArc rec={rec} lang={lang} nh={-1} />  // a past day — no "now"
 */
import React, { useCallback, useEffect, useRef, useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { NUM, V2T, V2Type, bandColor, famMono } from "../../theme";
import { doseUgRound, t, type Lang } from "../../i18n/strings";
import { DYNAMIC_TYPE } from "../../a11y";
import { tick } from "../../haptics";
import { bump } from "../../perf";
import type { DayReconstruction } from "../../store/daylog";

function HourArcInner({ rec, lang, nh }: {
  rec: DayReconstruction; lang: Lang;
  /** the local hour to mark live; -1 marks none (a day already over) */
  nh?: number;
}) {
  bump("home.HourArc");
  const max = Math.max(...rec.arc.map((h) => h.dose_ug), 0.5);
  const nowH = nh ?? new Date().getHours();
  /* the arc is scrubbable — a horizontal drag lights the hour under the
     finger and reads its number, honestly: counted dose where the day
     was counted, the field's air where it wasn't, nothing where there
     is nothing. Vertical scrolling is untouched — the gesture only
     claims strongly-horizontal moves. */
  const [scrubH, setScrubH] = useState<number | null>(null);
  const lastH = useRef<number | null>(null);
  const anchor = useRef<{ x: number; y: number } | null>(null);
  const arcW = useRef(0);
  const originX = useRef(0);
  const arcRef = useRef<View>(null);
  const hideT = useRef<ReturnType<typeof setTimeout> | null>(null);
  useEffect(() => () => { if (hideT.current) clearTimeout(hideT.current); }, []);
  /* locationX is relative to the touched child column (14pt wide), not
     the strip — it would map every touch to hour 0. pageX is absolute,
     so the strip's window origin is measured once and subtracted. */
  const scrubTo = useCallback((pageX: number) => {
    if (hideT.current) { clearTimeout(hideT.current); hideT.current = null; }
    if (arcW.current <= 0) return;
    const x = pageX - originX.current;
    const h = Math.max(0, Math.min(23, Math.floor((x / arcW.current) * 24)));
    if (h !== lastH.current) { lastH.current = h; setScrubH(h); tick(); }
  }, []);
  /* the readout lingers after the finger lifts, then fades on its own —
     tap-to-inspect, not modal state. */
  const scheduleHide = useCallback(() => {
    anchor.current = null;
    if (hideT.current) clearTimeout(hideT.current);
    hideT.current = setTimeout(() => { lastH.current = null; setScrubH(null); }, 5000);
  }, []);
  const scrub = scrubH != null ? rec.arc.find((h) => h.hour === scrubH) : null;
  const scrubLine = scrub == null ? " "
    : scrub.covered && scrub.dose_ug > 0
      ? t("dayArcDose", lang, { n: doseUgRound(scrub.dose_ug), h: scrub.hour })
      : scrub.conc != null
        ? t("dayArcAir", lang, { c: Math.round(scrub.conc), h: scrub.hour })
        : t("dayArcFlat", lang, { h: scrub.hour });
  return (
    <View>
      <View ref={arcRef} style={ss.arcWrap}
        onLayout={(e) => {
          arcW.current = e.nativeEvent.layout.width;
          arcRef.current?.measureInWindow((x) => { originX.current = x; });
        }}
        onTouchStart={(e) => {
          anchor.current = { x: e.nativeEvent.pageX, y: e.nativeEvent.pageY };
          scrubTo(e.nativeEvent.pageX);
          scheduleHide();
        }}
        onMoveShouldSetResponder={(e) => {
          const st = anchor.current;
          if (!st) return false;
          const dx = Math.abs(e.nativeEvent.pageX - st.x);
          const dy = Math.abs(e.nativeEvent.pageY - st.y);
          return dx > 8 && dx > dy;
        }}
        onResponderGrant={(e) => scrubTo(e.nativeEvent.pageX)}
        onResponderMove={(e) => scrubTo(e.nativeEvent.pageX)}
        onResponderRelease={scheduleHide}
        onResponderTerminate={scheduleHide}>
        {rec.arc.map((h) => {
          const isNow = h.hour === nowH;
          const press = () => {
            if (hideT.current) { clearTimeout(hideT.current); hideT.current = null; }
            lastH.current = h.hour;
            setScrubH(h.hour);
            tick();
            scheduleHide();
          };
          /* the arc is a heat strip: the bar's height is the dose that hour
             added, its colour is the band of the air breathed — the day
             reads as weather before it reads as numbers */
          const lit = scrubH === h.hour;
          /* the bar wears its hour's air band; the selected/now hour is
             told by full opacity, never by switching to black */
          const barCol = bandColor(h.conc) ?? V2T.text3;
          return (
            <Pressable key={h.hour} style={ss.arcCol} onPress={press}
              accessibilityRole="button" accessibilityLabel={`hour ${h.hour}`}>
              <View style={ss.arcBarCol}>
                {h.covered && h.dose_ug > 0 ? (
                  <View style={[ss.arcBar, {
                    height: 4 + 44 * (h.dose_ug / max),
                    backgroundColor: barCol,
                    opacity: scrubH == null || lit ? 1 : 0.45,
                  }]} />
                ) : h.conc != null ? (
                  /* uncovered hour — the band dot keeps the field visible
                     without claiming dose we didn't count */
                  <View style={[ss.arcDot, {
                    backgroundColor: bandColor(h.conc) ?? V2T.hairline,
                    opacity: scrubH == null || lit ? 1 : 0.4,
                  }]} />
                ) : null}
                {h.trip_marks > 0 && <View style={ss.arcTrip} />}
              </View>
              <Text {...DYNAMIC_TYPE}
                style={[ss.arcHr, { fontFamily: famMono(lang) },
                  (isNow || lit) && { color: V2T.text }]}>
                {h.hour % 3 === 0 || lit ? `${h.hour}` : ""}
              </Text>
            </Pressable>
          );
        })}
      </View>
      <Text {...DYNAMIC_TYPE} numberOfLines={1}
        style={[ss.arcScrub, NUM, { fontFamily: famMono(lang, "med"), opacity: scrubH == null ? 0 : 1 }]}>
        {scrubLine}
      </Text>
    </View>
  );
}

export const HourArc = React.memo(HourArcInner);

const ss = StyleSheet.create({
  /* day arc — a heat strip, bars wear the hour's band */
  arcWrap: { flexDirection: "row", alignItems: "flex-end", marginTop: 12 },
  arcCol: { flex: 1, alignItems: "center" },
  arcBarCol: { height: 54, alignItems: "center", justifyContent: "flex-end" },
  arcDot: { width: 5, height: 5, borderRadius: 2.5, marginBottom: 3 },
  arcBar: { width: 6, borderRadius: 3 },
  arcTrip: {
    width: 5, height: 5, marginTop: 3, borderRadius: 1.5,
    backgroundColor: V2T.accent,
  },
  arcHr: { color: V2T.text3, fontSize: V2Type.micro, marginTop: 4, height: 14 },
  arcScrub: { color: V2T.text, fontSize: V2Type.label, textAlign: "center", marginTop: 6, height: 17 },
});
