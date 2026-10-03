/** Live-trip chrome (doc 02 §S6): next-turn banner + the breathed counter.
 * The "put out" counter stays a seam — the ledger has no emissions field.
 * SEAM(live-trip): follow-mode camera, snap-to-route, voice cues and the
 * second counter land with the nav/screens lane. */
import React from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { F, NUM, V2Radius, V2T, V2Type, cigOf, fam } from "../../theme";
import { Icon } from "../../icons";
import { t, type Lang } from "../../i18n/strings";
import type { CompareOption, Step } from "./types";

const arrivalLabel = (durationMin: number) => {
  const d = new Date(Date.now() + durationMin * 60000);
  return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
};

export function NavChrome({
  option, steps, doseUg, onExit, lang,
}: {
  option: CompareOption; steps: Step[] | null; doseUg: number;
  onExit: () => void; lang: Lang;
}) {
  return (
    <>
      <View style={s.banner}>
        <View style={{ flex: 1 }}>
          <Text style={[s.instr, { fontFamily: fam(lang, "semi") }]} numberOfLines={2}>
            {option.vehicle === "metro" && option.stations
              ? t("boardMetro", lang, { a: option.stations.board, b: option.stations.alight })
              : steps?.[0]?.instruction ?? t("followRoute", lang)}
          </Text>
          <Text style={[s.meta, NUM]}>
            {Math.round(option.duration_min)} {t("minUnit", lang)} · {option.distance_km} {t("unitsKm", lang)}
            {" · "}{t("arriveAt", lang, { t: arrivalLabel(option.duration_min) })}
          </Text>
        </View>
        <Pressable onPress={onExit} hitSlop={10} style={s.x} accessibilityRole="button">
          <Icon name="close" color={V2T.text} size={18} />
        </Pressable>
      </View>
      <View style={s.counter}>
        <Icon name="cigarette" color={V2T.text} size={16} />
        <Text style={[s.counterTxt, NUM, { fontFamily: fam(lang, "med") }]}>
          {t("breathedSoFar", lang, { n: cigOf(doseUg) ?? 0 })}
        </Text>
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
  counter: {
    position: "absolute", bottom: 44, left: 16,
    flexDirection: "row", alignItems: "center", gap: 7,
    backgroundColor: V2T.surface, borderRadius: V2Radius.pill,
    paddingHorizontal: 14, paddingVertical: 10,
    borderWidth: 1, borderColor: V2T.line,
    shadowColor: "#000", shadowOpacity: 0.4, shadowRadius: 8, shadowOffset: { width: 0, height: 3 },
    elevation: 6,
  },
  counterTxt: { fontSize: V2Type.secondary, color: V2T.text },
});
