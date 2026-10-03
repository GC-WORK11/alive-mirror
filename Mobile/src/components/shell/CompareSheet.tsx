/** Options sheet (doc 02 §S4) — modes ranked by what you'd breathe.
 * Two bars per row in the spec (in / out); only the in-bar renders until
 * the options payload carries per-ride emissions — nothing without data.
 * SEAM(compare): the screens lane may replace this with src/screens S4. */
import React from "react";
import { ActivityIndicator, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { F, NUM, V2Radius, V2T, V2Type, fam } from "../../theme";
import { Icon } from "../../icons";
import { ModeRow, Sheet } from "../../ui";
import { t, type Lang } from "../../i18n/strings";
import type { CompareOption, Depart, Step } from "./types";

const arrivalLabel = (durationMin: number) => {
  const d = new Date(Date.now() + durationMin * 60000);
  return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
};

const hourLabel = (iso: string | null, ahead: number) => {
  if (iso) {
    const d = new Date(iso.endsWith("Z") ? iso : iso + "Z");
    if (!isNaN(d.getTime())) {
      const ist = new Date(d.getTime() + 5.5 * 3600 * 1000);
      const hh = String(ist.getUTCHours()).padStart(2, "0");
      const today = new Date(Date.now() + 5.5 * 3600 * 1000);
      return `${ist.getUTCDate() !== today.getUTCDate() ? "tomorrow " : ""}${hh}:30`;
    }
  }
  return `+${ahead}h`;
};

export function CompareSheet({
  options, selected, onSelect, depart, notified, onRemind,
  loading, steps, stepsOpen, onToggleSteps, onStart, onClose, lang,
}: {
  options: CompareOption[]; selected: number; onSelect: (i: number) => void;
  depart: Depart; notified: boolean; onRemind: () => void;
  loading: boolean; steps: Step[] | null; stepsOpen: boolean;
  onToggleSteps: () => void; onStart: () => void; onClose: () => void; lang: Lang;
}) {
  const sel = options[selected];
  const worst = Math.max(...options.map((o) => o.exposure?.dose_ug ?? 0), 0);
  const bestIdx = options.reduce((b, o, i) =>
    (o.exposure?.dose_ug ?? Infinity) < (options[b]?.exposure?.dose_ug ?? Infinity) ? i : b, 0);
  return (
    <View style={s.wrap}>
      <Sheet detent="half" onClose={onClose}>
        {loading ? (
          <View style={{ paddingVertical: 26, alignItems: "center" }}>
            <ActivityIndicator size="small" color={V2T.accent} />
            <Text style={s.loadingTxt}>{t("checkingRoutes", lang)}</Text>
          </View>
        ) : options.length > 0 ? (
          <ScrollView showsVerticalScrollIndicator={false}>
            {depart?.ug_saved_vs_now != null && depart.ug_saved_vs_now > 8 && (
              <Pressable onPress={onRemind} style={s.departRow}>
                <Icon name={notified ? "bell" : "clock"} color={V2T.accent} size={16} filled={notified} />
                <Text style={s.departTxt}>
                  {notified
                    ? t("wellPing", lang)
                    : t("leaveAtBreatheLess", lang, {
                        time: hourLabel(depart.best.start, depart.best.hours_ahead),
                        n: Math.round(depart.ug_saved_vs_now),
                      })}
                </Text>
              </Pressable>
            )}
            {options.map((o, i) => (
              <ModeRow
                key={`${o.vehicle}-${i}`}
                vehicle={o.vehicle}
                label={o.label}
                etaMin={Math.round(o.duration_min)}
                meta={`${o.distance_km} ${t("unitsKm", lang)} · ${t("arriveAt", lang, { t: arrivalLabel(o.duration_min) })}${o.stations ? ` · ${o.stations.board}→${o.stations.alight}` : ""}`}
                inFrac={o.exposure?.dose_ug != null && worst > 0 ? o.exposure.dose_ug / worst : null}
                tag={i === bestIdx && worst > 0 ? t("lightestForYou", lang) : undefined}
                selected={i === selected}
                onPress={() => onSelect(i)}
                lang={lang}
              />
            ))}
            {sel && (
              <View style={s.startRow}>
                <Pressable onPress={onToggleSteps} style={s.stepsBtn}>
                  <Text style={[s.stepsBtnTxt, { fontFamily: fam(lang, "med") }]}>
                    {stepsOpen ? t("hideTurns", lang) : t("turnByTurn", lang)}
                  </Text>
                </Pressable>
                <Pressable onPress={onStart} style={s.goBtn}>
                  <Text style={[s.goBtnTxt, { fontFamily: fam(lang, "semi") }]}>{t("start", lang)}</Text>
                </Pressable>
              </View>
            )}
            {stepsOpen && steps && (
              <View style={s.stepsList}>
                {sel?.vehicle === "metro" && sel.stations ? (
                  <Text style={s.stepTxt}>{t("boardMetro", lang, { a: sel.stations.board, b: sel.stations.alight })}</Text>
                ) : steps.map((st, i) => (
                  <View key={i} style={s.stepRow}>
                    <View style={s.stepDot} />
                    <Text style={s.stepTxt}>{st.instruction}</Text>
                    <Text style={[s.stepDist, NUM]}>
                      {st.distance_m >= 1000 ? `${(st.distance_m / 1000).toFixed(1)} km` : `${Math.round(st.distance_m)} m`}
                    </Text>
                  </View>
                ))}
              </View>
            )}
            {stepsOpen && sel?.vehicle !== "metro" && !steps && (
              <Text style={s.stepTxt}>{t("roadModesOnly", lang)}</Text>
            )}
          </ScrollView>
        ) : (
          <Text style={s.noResults}>{t("noRoutes", lang)}</Text>
        )}
      </Sheet>
    </View>
  );
}

const s = StyleSheet.create({
  wrap: { position: "absolute", bottom: 0, left: 0, right: 0 },
  loadingTxt: { fontFamily: F.reg, fontSize: V2Type.label, color: V2T.text3, marginTop: 8 },
  departRow: {
    flexDirection: "row", alignItems: "center", gap: 8,
    marginHorizontal: 16, marginTop: 6, marginBottom: 2,
    paddingHorizontal: 12, paddingVertical: 9, borderRadius: V2Radius.row,
    backgroundColor: "rgba(76,141,255,0.12)",
  },
  departTxt: { fontFamily: F.med, fontSize: V2Type.label, color: V2T.accent },
  startRow: {
    flexDirection: "row", alignItems: "center", justifyContent: "space-between",
    paddingHorizontal: 16, paddingVertical: 10,
  },
  stepsBtn: { paddingVertical: 8, paddingHorizontal: 14 },
  stepsBtnTxt: { fontSize: V2Type.secondary, color: V2T.text2 },
  goBtn: { backgroundColor: V2T.accent, borderRadius: V2Radius.pill, paddingHorizontal: 34, paddingVertical: 11 },
  goBtnTxt: { fontSize: V2Type.body, color: V2T.text },
  stepsList: { paddingHorizontal: 16, paddingBottom: 10 },
  stepRow: { flexDirection: "row", alignItems: "flex-start", paddingVertical: 5, gap: 10 },
  stepDot: { width: 6, height: 6, borderRadius: 3, backgroundColor: V2T.accent, marginTop: 6 },
  stepTxt: { flex: 1, fontFamily: F.reg, fontSize: V2Type.secondary, color: V2T.text, paddingBottom: 4, paddingHorizontal: 16 },
  stepDist: { fontFamily: F.reg, fontSize: V2Type.label, color: V2T.text3 },
  noResults: { fontFamily: F.reg, fontSize: V2Type.label, color: V2T.text3, padding: 16, textAlign: "center" },
});
