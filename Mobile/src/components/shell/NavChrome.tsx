/** Live-trip chrome (doc 02 §S6): next-turn banner, off-route pill,
 * the two live counters (smoke you breathe / smoke your ride puts out),
 * ETA + distance-left bar, recenter + exit.
 *
 * Consumes useNavEngine output via the optional `nav` prop; without it
 * the legacy props (option/steps/doseUg) still render a working chrome
 * so the pre-integration call site keeps compiling. Bands stay intact
 * in `nav` — the counters render the mid with "≈" per copy rules. */
import React from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { F, NUM, V2Radius, V2T, V2Type, cigOf, fam } from "../../theme";
import { Icon } from "../../icons";
import { t, type Lang } from "../../i18n/strings";
import type { Band } from "../../nav/strip";
import type { CompareOption, Step } from "./types";

/** The slice of the engine the chrome needs (subset of useNavEngine's
 *  return — pass the whole object, it satisfies this shape). */
export type NavView = {
  dose: Band;            // µg inhaled
  co2: Band;             // kg put out
  pm25?: Band;           // g put out (banner detail only)
  etaS: number;
  distRemainingM: number;
  offRoute: boolean;
  stripOk?: boolean;       // false → /v2/strip failed, counters frozen
  running?: boolean;
  nextStep?: { instruction: string; distM: number } | null;
  snapped?: [number, number] | null;
};

const clock = (etaS: number) => {
  const d = new Date(Date.now() + Math.max(0, etaS) * 1000);
  return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
};

const kmLeft = (m: number) =>
  m >= 950 ? `${(m / 1000).toFixed(1)}` : `${Math.max(0, Math.round(m / 10) * 10)} m`;

export function NavChrome({
  option, steps, doseUg, onExit, lang, nav, onRecenter,
}: {
  option: CompareOption; steps: Step[] | null; doseUg: number;
  onExit: () => void; lang: Lang;
  nav?: NavView | null; onRecenter?: (() => void) | null;
}) {
  const min = Math.max(0, Math.round((nav?.etaS ?? option.duration_min * 60) / 60));
  const leftM = nav?.distRemainingM ?? (option.distance_km ?? 0) * 1000;
  const banner = nav?.nextStep?.instruction
    ?? steps?.[0]?.instruction
    ?? (option.vehicle === "metro" && option.stations
      ? t("boardMetro", lang, { a: option.stations.board, b: option.stations.alight })
      : t("followRoute", lang));
  const cigs = nav ? cigOf(nav.dose.mid) : cigOf(doseUg);
  const outKg = nav ? Math.round(Math.max(0, nav.co2.mid) * 10) / 10 : null; // kg, 1dp
  const showOut = nav != null && nav.co2.hi > 0;

  return (
    <>
      <View style={s.banner}>
        <View style={{ flex: 1 }}>
          <Text style={[s.instr, { fontFamily: fam(lang, "semi") }]} numberOfLines={2}>
            {banner}
          </Text>
          <Text style={[s.meta, NUM]}>
            {nav
              ? t("nav_left", lang, { min, km: kmLeft(leftM) })
              : `${Math.round(option.duration_min)} ${t("minUnit", lang)} · ${option.distance_km} ${t("unitsKm", lang)}`}
            {" · "}{t("arriveAt", lang, { t: clock(nav?.etaS ?? option.duration_min * 60) })}
          </Text>
        </View>
        {onRecenter && (
          <Pressable onPress={onRecenter} hitSlop={10} style={s.x}
            accessibilityRole="button" accessibilityLabel={t("nav_recenter", lang)}>
            <Icon name="locate" color={V2T.text} size={18} />
          </Pressable>
        )}
        <Pressable onPress={onExit} hitSlop={10} style={s.x}
          accessibilityRole="button" accessibilityLabel={t("end", lang)}>
          <Icon name="close" color={V2T.text} size={18} />
        </Pressable>
      </View>

      {nav?.offRoute && (
        <View style={s.pill}>
          <Text style={[s.pillTxt, { fontFamily: fam(lang, "med") }]}>
            {t("findingNewWay", lang)}
          </Text>
        </View>
      )}
      {nav?.stripOk === false && !nav.offRoute && (
        <View style={s.pill}>
          <Text style={[s.pillTxt, { fontFamily: fam(lang, "med") }]}>
            {t("strip_unavailable", lang)}
          </Text>
        </View>
      )}

      <View style={s.counters}>
        <View style={s.counter}>
          <Icon name="cigarette" color={V2T.breath1} size={15} />
          <View>
            <Text style={[s.counterLbl, { fontFamily: fam(lang, "reg") }]}>
              {t("nav_breathe", lang)}
            </Text>
            <Text style={[s.counterTxt, NUM, { fontFamily: fam(lang, "med") }]}>
              {cigs == null ? t("nav_noSignal", lang)
                : t("nav_cigs", lang, { n: cigs > 0 && cigs < 0.01 ? 0.01 : cigs })}
            </Text>
          </View>
        </View>
        {showOut && outKg != null && (
          <View style={s.counter}>
            <Icon name="smoke" color={V2T.out1} size={15} />
            <View>
              <Text style={[s.counterLbl, { fontFamily: fam(lang, "reg") }]}>
                {t("nav_putOut", lang)}
              </Text>
              <Text style={[s.counterTxt, NUM, { fontFamily: fam(lang, "med") }]}>
                {t("nav_kg", lang, { n: outKg })}
              </Text>
            </View>
          </View>
        )}
      </View>
    </>
  );
}

const s = StyleSheet.create({
  banner: {
    position: "absolute", top: 50, left: 12, right: 12,
    flexDirection: "row", alignItems: "center",
    backgroundColor: V2T.surface, borderRadius: V2Radius.row + 4, padding: 14,
    borderWidth: 1, borderColor: V2T.line,
    shadowColor: "#000", shadowOpacity: 0.5, shadowRadius: 14, shadowOffset: { width: 0, height: 4 },
    elevation: 10,
  },
  instr: { fontSize: V2Type.body, color: V2T.text },
  meta: { fontFamily: F.reg, fontSize: V2Type.label, color: V2T.text3, marginTop: 3 },
  x: { marginLeft: 10, padding: 6 },
  pill: {
    position: "absolute", top: 118, alignSelf: "center",
    backgroundColor: V2T.surface2, borderRadius: V2Radius.pill,
    paddingHorizontal: 14, paddingVertical: 8,
    borderWidth: 1, borderColor: V2T.line,
  },
  pillTxt: { fontSize: V2Type.label, color: V2T.text2 },
  counters: {
    position: "absolute", bottom: 44, left: 16, right: 16,
    flexDirection: "row", gap: 10, flexWrap: "wrap",
  },
  counter: {
    flexDirection: "row", alignItems: "center", gap: 8,
    backgroundColor: V2T.surface, borderRadius: V2Radius.pill,
    paddingHorizontal: 14, paddingVertical: 9,
    borderWidth: 1, borderColor: V2T.line,
    shadowColor: "#000", shadowOpacity: 0.4, shadowRadius: 8, shadowOffset: { width: 0, height: 3 },
    elevation: 6,
  },
  counterLbl: { fontSize: 11, color: V2T.text3 },
  counterTxt: { fontSize: V2Type.secondary, color: V2T.text },
});
