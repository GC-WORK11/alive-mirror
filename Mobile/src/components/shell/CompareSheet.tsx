/** Options sheet (doc 02 §S4) — modes ranked by what you'd breathe AND
 * what the ride puts out. Two 4-step bars per row: in-bar = dose.mid as
 * a fraction of the worst option's dose.mid; out-bar = emissions
 * co2_kg.mid the same way. Tags + recommended + reason_line are the
 * server's doc-06 §4 ranking, localized. Jargon (µg, PM2.5, CO2, basis)
 * stays inside the per-option "how we got this" expander — long-press
 * any row, or tap the link on the selected row.
 *
 * Vehicle chip (doc 02 §S8): re-openable pill at the top of the list.
 *   Wire it from the integrator as:
 *     <CompareSheet …
 *       vehicle={flow.vehicle}
 *       onVehiclePress={() => setVehOpen(true)}      // opens <VehicleSheet/>
 *       onVehicleChange={flow.setVehicleProfile}      // persist + re-plan
 *       planError={flow.planError} onRetry={flow.retryPlan}
 *       fieldAgeS={flow.planField?.age_s} />
 *   If onVehiclePress is omitted the chip opens an internal VehicleSheet
 *   and persists via saveVehicle — works standalone, but the flow only
 *   re-plans with the new vehicle when onVehicleChange is wired.
 * SEAM(compare): the screens lane may replace this with src/screens S4. */
import React, { useEffect, useState } from "react";
import { ActivityIndicator, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { F, NUM, V2Radius, V2T, V2Type, fam } from "../../theme";
import { Icon, vehicleGlyph } from "../../icons";
import { ModeRow, Sheet } from "../../ui";
import { t, type Lang, type StringKey } from "../../i18n/strings";
import {
  getVehicle, saveVehicle, vehicleLabel, type VehicleProfile,
} from "../../store/vehicle";
import { VehicleSheet } from "../../screens/VehicleSheet";
import type { Band, Depart, Step, V2Option } from "./types";

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

/** server tag string → string-table key (tags are fixed by rank_options) */
const TAG_KEY: Record<string, StringKey> = {
  "lightest on both": "lightestOnBoth",
  "lightest for you": "lightestForYou",
  "lightest for delhi": "lightestForDelhi",
};

const bandTxt = (b: Band | null | undefined, unit: string) =>
  b && (b.lo != null || b.hi != null)
    ? `${b.lo ?? "?"}–${b.hi ?? "?"}${unit ? ` ${unit}` : ""}`
    : null;

/** "How we got this number" — the ONLY place jargon is allowed. Bands,
 *  bases, confidence, field age, all honest and server-sourced. */
function DetailBlock({ o, fieldAgeS, lang }: { o: V2Option; fieldAgeS?: number | null; lang: Lang }) {
  const d = o.dose, e = o.emissions;
  const cig = d.mid != null ? Math.round((d.mid / 316) * 100) / 100 : null;
  const ageMin = fieldAgeS != null ? Math.max(0, Math.round(fieldAgeS / 60)) : null;
  return (
    <View style={s.detail}>
      {d.mid != null ? (
        <Text style={[s.dLine, NUM]}>
          {t("howWe_in", lang, { mid: Math.round(d.mid), lo: Math.round(d.lo ?? d.mid), hi: Math.round(d.hi ?? d.mid) })}
          {cig != null ? `  ·  ${t("howWe_cigs", lang, { n: cig })}` : ""}
        </Text>
      ) : (
        <Text style={s.dLine}>{d.note ?? t("howWe_none", lang)}</Text>
      )}
      {d.confidence ? <Text style={s.dSub}>{t("howWe_conf", lang, { c: d.confidence })}</Text> : null}
      {e.co2_kg || e.pm25_g ? (
        <Text style={[s.dLine, NUM]}>
          {t("howWe_out", lang, {
            v: [bandTxt(e.co2_kg, "kg CO2"), bandTxt(e.pm25_g, "g PM2.5")]
              .filter(Boolean).join("  ·  "),
          })}
        </Text>
      ) : null}
      {(e.label ?? e.basis) ? <Text style={s.dSub}>{e.label ?? e.basis}</Text> : null}
      {e.bs_class && e.bs_class !== "none" ? <Text style={s.dSub}>{e.bs_class}{e.bs_options?.length ? ` (${e.bs_options.join("–")})` : ""}</Text> : null}
      {e.non_exhaust?.note ? <Text style={s.dSub}>{e.non_exhaust.note}</Text> : null}
      {ageMin != null ? <Text style={s.dSub}>{t("howWe_fieldAge", lang, { n: ageMin })}</Text> : null}
    </View>
  );
}

export function CompareSheet({
  options, selected, onSelect, depart, notified, onRemind,
  loading, steps, stepsOpen, onToggleSteps, onStart, onClose, lang,
  planError = null, onRetry, vehicle, onVehiclePress, onVehicleChange, fieldAgeS,
}: {
  options: V2Option[]; selected: number; onSelect: (i: number) => void;
  depart: Depart; notified: boolean; onRemind: () => void;
  loading: boolean; steps: Step[] | null; stepsOpen: boolean;
  onToggleSteps: () => void; onStart: () => void; onClose: () => void; lang: Lang;
  /** v2 plan failure — honest retry state, never a silent /decide fallback */
  planError?: string | null;
  onRetry?: () => void;
  /** S8 profile; leave undefined to let the sheet load the store itself */
  vehicle?: VehicleProfile | null;
  /** chip → open <VehicleSheet/> (integrator mounts it — see header) */
  onVehiclePress?: () => void;
  /** fired after the internal sheet saves; wire to flow.setVehicleProfile */
  onVehicleChange?: (p: VehicleProfile) => void;
  /** field.age_s from the /v2/plan payload, for the details expander */
  fieldAgeS?: number | null;
}) {
  const sel = options[selected];
  const [detailIdx, setDetailIdx] = useState<number | null>(null);
  const [vehSelf, setVehSelf] = useState<VehicleProfile | null>(null);
  const [vehOpen, setVehOpen] = useState(false);

  /* self-load the profile only when the integrator didn't pass one */
  useEffect(() => {
    if (vehicle === undefined) getVehicle().then(setVehSelf).catch(() => {});
  }, [vehicle]);
  const veh = vehicle !== undefined ? vehicle : vehSelf;

  const worstIn = Math.max(...options.map((o) => o.dose?.mid ?? 0), 0);
  const worstOut = Math.max(...options.map((o) => o.emissions?.co2_kg?.mid ?? 0), 0);

  const chip = (
    <Pressable
      onPress={() => (onVehiclePress ? onVehiclePress() : setVehOpen(true))}
      style={({ pressed }) => [s.vehChip, pressed && { opacity: 0.6 }]}
      accessibilityRole="button" accessibilityLabel={t("sidebarMyVehicle", lang)}>
      <Icon name={vehicleGlyph(veh?.cls ?? "car")} color={V2T.text2} size={15} />
      <Text style={[s.vehChipTxt, { fontFamily: fam(lang, "reg") }]} numberOfLines={1}>
        {veh ? vehicleLabel(veh, lang) : t("vehicle_likeYours", lang)}
      </Text>
      <Icon name="chevron" color={V2T.text3} size={11} />
    </Pressable>
  );

  return (
    <View style={s.wrap}>
      <Sheet detent="half" onClose={onClose}>
        {loading ? (
          <View style={{ paddingVertical: 26, alignItems: "center" }}>
            <ActivityIndicator size="small" color={V2T.accent} />
            <Text style={s.loadingTxt}>{t("checkingRoutes", lang)}</Text>
          </View>
        ) : planError ? (
          <View style={{ paddingVertical: 22, alignItems: "center", paddingHorizontal: 24 }}>
            <Text style={s.noResults}>{t("plan_failed", lang)}</Text>
            {onRetry && (
              <Pressable onPress={onRetry} style={s.retryBtn} accessibilityRole="button">
                <Text style={[s.retryTxt, { fontFamily: fam(lang, "med") }]}>{t("plan_retry", lang)}</Text>
              </Pressable>
            )}
          </View>
        ) : options.length > 0 ? (
          <ScrollView showsVerticalScrollIndicator={false}>
            {chip}
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
              <View key={`${o.mode}-${i}`}>
                <ModeRow
                  vehicle={o.mode}
                  label={o.your_vehicle && veh != null ? `${o.label} · ${t("compare_yours", lang)}` : o.label}
                  etaMin={Math.round(o.duration_min)}
                  meta={`${o.distance_km ?? "?"} ${t("unitsKm", lang)} · ${t("arriveAt", lang, { t: arrivalLabel(o.duration_min) })}${o.stations ? ` · ${o.stations.board}→${o.stations.alight}` : ""}`}
                  inFrac={o.dose?.mid != null && worstIn > 0 ? o.dose.mid / worstIn : null}
                  outFrac={o.emissions?.co2_kg?.mid != null && worstOut > 0 ? o.emissions.co2_kg.mid / worstOut : null}
                  tag={o.tag ? (TAG_KEY[o.tag.toLowerCase()] ? t(TAG_KEY[o.tag.toLowerCase()], lang) : o.tag) : undefined}
                  recommended={o.recommended}
                  reasonLine={o.reason_line || undefined}
                  selected={i === selected}
                  onPress={() => onSelect(i)}
                  onLongPress={() => setDetailIdx(detailIdx === i ? null : i)}
                  lang={lang}
                />
                {detailIdx === i && <DetailBlock o={o} fieldAgeS={fieldAgeS} lang={lang} />}
              </View>
            ))}
            {sel && (
              <View style={s.startRow}>
                <Pressable onPress={() => setDetailIdx(detailIdx === selected ? null : selected)} style={s.stepsBtn}>
                  <Text style={[s.stepsBtnTxt, { fontFamily: fam(lang, "reg") }]}>{t("howWeGotThis", lang)}</Text>
                </Pressable>
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
                {sel?.mode === "metro" && sel.stations ? (
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
            {stepsOpen && sel?.mode !== "metro" && !steps && (
              <Text style={s.stepTxt}>{t("roadModesOnly", lang)}</Text>
            )}
          </ScrollView>
        ) : (
          <Text style={s.noResults}>{t("noRoutes", lang)}</Text>
        )}
      </Sheet>
      {/* fallback: when the integrator doesn't wire onVehiclePress the chip
          still works — own VehicleSheet persists via saveVehicle, and
          onVehicleChange (if wired) lets the flow re-plan. */}
      {!onVehiclePress && (
        <VehicleSheet
          visible={vehOpen}
          lang={lang}
          current={veh}
          onDone={(p) => {
            saveVehicle(p).catch(() => {});
            setVehSelf(p);
            setVehOpen(false);
            onVehicleChange?.(p);
          }}
          onClose={() => setVehOpen(false)}
        />
      )}
    </View>
  );
}

const s = StyleSheet.create({
  wrap: { position: "absolute", bottom: 0, left: 0, right: 0 },
  loadingTxt: { fontFamily: F.reg, fontSize: V2Type.label, color: V2T.text3, marginTop: 8 },
  vehChip: {
    flexDirection: "row", alignItems: "center", gap: 6, alignSelf: "flex-start",
    marginHorizontal: 16, marginTop: 4, marginBottom: 4,
    paddingHorizontal: 11, paddingVertical: 6,
    backgroundColor: V2T.surface2, borderRadius: V2Radius.pill,
    borderWidth: 1, borderColor: V2T.line,
  },
  vehChipTxt: { fontSize: V2Type.label, color: V2T.text2, maxWidth: 220 },
  departRow: {
    flexDirection: "row", alignItems: "center", gap: 8,
    marginHorizontal: 16, marginTop: 6, marginBottom: 2,
    paddingHorizontal: 12, paddingVertical: 9, borderRadius: V2Radius.row,
    backgroundColor: "rgba(76,141,255,0.12)",
  },
  departTxt: { fontFamily: F.med, fontSize: V2Type.label, color: V2T.accent },
  detail: {
    marginHorizontal: 16, marginBottom: 8, paddingHorizontal: 12, paddingVertical: 10,
    backgroundColor: V2T.surface2, borderRadius: V2Radius.row,
    borderWidth: 1, borderColor: V2T.line, gap: 4,
  },
  dLine: { fontFamily: F.reg, fontSize: V2Type.label, color: V2T.text },
  dSub: { fontFamily: F.reg, fontSize: V2Type.label, color: V2T.text3 },
  startRow: {
    flexDirection: "row", alignItems: "center", justifyContent: "space-between",
    paddingHorizontal: 16, paddingVertical: 10,
  },
  stepsBtn: { paddingVertical: 8, paddingHorizontal: 8 },
  stepsBtnTxt: { fontSize: V2Type.label, color: V2T.text2 },
  goBtn: { backgroundColor: V2T.accent, borderRadius: V2Radius.pill, paddingHorizontal: 34, paddingVertical: 11 },
  goBtnTxt: { fontSize: V2Type.body, color: V2T.text },
  stepsList: { paddingHorizontal: 16, paddingBottom: 10 },
  stepRow: { flexDirection: "row", alignItems: "flex-start", paddingVertical: 5, gap: 10 },
  stepDot: { width: 6, height: 6, borderRadius: 3, backgroundColor: V2T.accent, marginTop: 6 },
  stepTxt: { flex: 1, fontFamily: F.reg, fontSize: V2Type.secondary, color: V2T.text, paddingBottom: 4, paddingHorizontal: 16 },
  stepDist: { fontFamily: F.reg, fontSize: V2Type.label, color: V2T.text3 },
  retryBtn: {
    marginTop: 12, backgroundColor: V2T.surface2, borderRadius: V2Radius.pill,
    paddingHorizontal: 22, paddingVertical: 9, borderWidth: 1, borderColor: V2T.line,
  },
  retryTxt: { fontSize: V2Type.secondary, color: V2T.accent },
  noResults: { fontFamily: F.reg, fontSize: V2Type.label, color: V2T.text3, padding: 16, textAlign: "center" },
});
