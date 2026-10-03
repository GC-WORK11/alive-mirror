/** Options sheet (doc 02 §S4) — the hero surface: modes ranked by what
 * you'd breathe AND what the ride puts out. Each option is a solid card:
 * mode glyph, ETA and the inhaled-dose number dominate; distance, arrival
 * and the server's reason line sit subordinate; two micro-bars compare
 * in-dose (warm ramp) and exhaust (cool greys) against the trip's worst
 * option; the honest {lo–hi} band stays visible next to the number.
 * Server tag + recommended render as chips; a one-line legend maps the
 * cigarette/exhaust glyphs above the list.
 *
 * "How we got this" — tap the ⓘ beside the bars, or long-press a row.
 * The panel opens inside the card: bands, bases, confidence, field age —
 * the only place jargon (µg, PM2.5, CO2, basis) is allowed.
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
import { NUM, V2Radius, V2T, V2Type, doseColor, fam } from "../../theme";
import { Icon, vehicleGlyph } from "../../icons";
import { Sheet } from "../../ui";
import { t, type Lang, type StringKey } from "../../i18n/strings";
import { DepartGraph } from "../DepartGraph";
import type { DepartCurve } from "../../api/depart";
import type { PlanError } from "./useShellFlow";
import {
  getVehicle, saveVehicle, vehicleLabel, type VehicleProfile,
} from "../../store/vehicle";
import { VehicleSheet } from "../../screens/VehicleSheet";
import type { Band, Depart, Step, V2Option } from "./types";

const arrivalLabel = (durationMin: number) => {
  const d = new Date(Date.now() + durationMin * 60000);
  return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
};

const hourLabel = (iso: string | null, ahead: number, lang: Lang) => {
  if (iso) {
    const d = new Date(iso.endsWith("Z") ? iso : iso + "Z");
    if (!isNaN(d.getTime())) {
      const ist = new Date(d.getTime() + 5.5 * 3600 * 1000);
      const hh = String(ist.getUTCHours()).padStart(2, "0");
      const today = new Date(Date.now() + 5.5 * 3600 * 1000);
      return `${ist.getUTCDate() !== today.getUTCDate() ? t("departTomorrow", lang) + " " : ""}${hh}:30`;
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

/** in-bar ramp: warm, brighter = heavier dose (absence of colour = light) */
const inTone = (f: number) => (f > 0.66 ? V2T.breath3 : f > 0.33 ? V2T.breath2 : V2T.breath1);
/** out-bar ramp: cool greys, lighter grey = heavier exhaust */
const outTone = (f: number) => (f > 0.66 ? V2T.out1 : f > 0.33 ? V2T.out2 : V2T.out3);

/** One micro-track: fill = this option vs the trip's worst on that axis.
 *  A dimmed empty groove means "no data", distinct from "zero". */
function Track({ frac, tone }: { frac: number | null; tone: "in" | "out" }) {
  if (frac == null) return <View style={[s.track, s.trackNA]} />;
  const f = Math.max(0, Math.min(1, frac));
  return (
    <View style={s.track}>
      <View style={[s.trackFill, { flex: f, backgroundColor: tone === "in" ? inTone(f) : outTone(f) }]} />
      <View style={{ flex: Math.max(0, 1 - f) }} />
    </View>
  );
}

/** The pair of bars on every card — breathe-in (cigarette) over the dose
 *  band, exhaust (plume) over CO2, both relative to the worst option. */
function PairBars({ o, worstIn, worstOut, lang }: {
  o: V2Option; worstIn: number; worstOut: number; lang: Lang;
}) {
  const inFrac = o.dose?.mid != null && worstIn > 0 ? o.dose.mid / worstIn : null;
  const outFrac = o.emissions?.co2_kg?.mid != null && worstOut > 0 ? o.emissions.co2_kg.mid / worstOut : null;
  return (
    <View style={s.bars}>
      <View style={s.barGroup} accessible accessibilityLabel={t("compare_smokeIn", lang)}>
        <Icon name="cigarette" color={V2T.text3} size={11} />
        <Track frac={inFrac} tone="in" />
      </View>
      <View style={s.barGroup} accessible accessibilityLabel={t("compare_smokeOut", lang)}>
        <Icon name="smoke" color={V2T.text3} size={11} />
        <Track frac={outFrac} tone="out" />
      </View>
    </View>
  );
}

/** Tag / recommended chip — server tags fill accent, the fallback "our
 *  pick" stays neutral so the stronger claim reads stronger. */
function Chip({ text, accent, lang }: { text: string; accent?: boolean; lang: Lang }) {
  return (
    <View style={[s.chip, accent ? s.chipAccent : s.chipPlain]}>
      <Text
        style={[s.chipTxt, accent ? s.chipTxtAccent : s.chipTxtPlain, { fontFamily: fam(lang, "med") }]}
        numberOfLines={1}>
        {text}
      </Text>
    </View>
  );
}

/** "How we got this number" — the ONLY place jargon is allowed. Bands,
 *  bases, confidence, field age, all honest and server-sourced. Opens
 *  inside the card under a hairline so the association never gets lost. */
function DetailBlock({ o, fieldAgeS, lang }: { o: V2Option; fieldAgeS?: number | null; lang: Lang }) {
  const d = o.dose, e = o.emissions;
  const cig = d.mid != null ? Math.round((d.mid / 316) * 100) / 100 : null;
  const ageMin = fieldAgeS != null ? Math.max(0, Math.round(fieldAgeS / 60)) : null;
  const emit = [bandTxt(e.co2_kg, "kg CO2"), bandTxt(e.pm25_g, "g PM2.5")].filter(Boolean).join("  ·  ");
  return (
    <View style={s.detail}>
      <Text style={[s.dTitle, { fontFamily: fam(lang, "med") }]}>{t("howWeGotThis", lang)}</Text>
      <View style={s.dRow}>
        <Icon name="cigarette" color={V2T.breath2} size={13} />
        {d.mid != null ? (
          <Text style={[s.dLine, NUM, { fontFamily: fam(lang, "reg") }]}>
            {t("howWe_in", lang, { mid: Math.round(d.mid), lo: Math.round(d.lo ?? d.mid), hi: Math.round(d.hi ?? d.mid) })}
            {cig != null ? `  ·  ${t("howWe_cigs", lang, { n: cig })}` : ""}
          </Text>
        ) : (
          <Text style={[s.dLine, { fontFamily: fam(lang, "reg") }]}>{d.note ?? t("howWe_none", lang)}</Text>
        )}
      </View>
      {d.confidence ? <Text style={[s.dSub, { fontFamily: fam(lang, "reg") }]}>{t("howWe_conf", lang, { c: d.confidence })}</Text> : null}
      {emit ? (
        <View style={s.dRow}>
          <Icon name="smoke" color={V2T.out1} size={13} />
          <Text style={[s.dLine, NUM, { fontFamily: fam(lang, "reg") }]}>{t("howWe_out", lang, { v: emit })}</Text>
        </View>
      ) : null}
      {d.coverage != null && d.coverage < 0.999 ? (
        <Text style={[s.dSub, { fontFamily: fam(lang, "reg") }]}>
          {t("howWe_coverage", lang, { pct: Math.round(d.coverage * 100) })}
        </Text>
      ) : null}
      {(e.label ?? e.basis) ? <Text style={[s.dSub, { fontFamily: fam(lang, "reg") }]}>{e.label ?? e.basis}</Text> : null}
      {e.bs_class && e.bs_class !== "none"
        ? <Text style={[s.dSub, { fontFamily: fam(lang, "reg") }]}>{e.bs_class}{e.bs_options?.length ? ` (${e.bs_options.join("–")})` : ""}</Text>
        : null}
      {e.non_exhaust?.note ? <Text style={[s.dSub, { fontFamily: fam(lang, "reg") }]}>{e.non_exhaust.note}</Text> : null}
      {ageMin != null ? (
        <View style={s.dRow}>
          <Icon name="clock" color={V2T.text3} size={13} />
          <Text style={[s.dRowSub, { fontFamily: fam(lang, "reg") }]}>{t("howWe_fieldAge", lang, { n: ageMin })}</Text>
        </View>
      ) : null}
      <Text style={[s.dFine, { fontFamily: fam(lang, "reg") }]}>{t("cityBasisBand", lang)}</Text>
    </View>
  );
}

/** One ranked option — solid card. Tap selects; the ⓘ beside the bars
 *  (or a long-press anywhere on the card) opens the details panel. */
function OptionCard({ o, i, selected, worstIn, worstOut, showYours, open,
  fieldAgeS, lang, onSelect, onToggleDetail }: {
  o: V2Option; i: number; selected: boolean; worstIn: number; worstOut: number;
  showYours: boolean; open: boolean; fieldAgeS?: number | null; lang: Lang;
  onSelect: (i: number) => void; onToggleDetail: (i: number) => void;
}) {
  const d = o.dose;
  const band = d && (d.lo != null || d.hi != null) && (d.lo !== d.mid || d.hi !== d.mid)
    ? `${d.lo != null ? Math.round(d.lo) : "?"}–${d.hi != null ? Math.round(d.hi) : "?"}`
    : null;
  const doseCol = d?.avg_conc_ugm3 != null ? doseColor(d.avg_conc_ugm3) : V2T.text;
  const meta = `${o.distance_km ?? "?"} ${t("unitsKm", lang)} · ${t("arriveAt", lang, { t: arrivalLabel(o.duration_min) })}`
    + `${o.stations ? ` · ${o.stations.board}→${o.stations.alight}` : ""}`;
  const tag = o.tag ? (TAG_KEY[o.tag.toLowerCase()] ? t(TAG_KEY[o.tag.toLowerCase()], lang) : o.tag) : null;
  return (
    <View style={[s.card, selected && s.cardSel]}>
      <Pressable
        onPress={() => onSelect(i)}
        onLongPress={() => onToggleDetail(i)}
        delayLongPress={400}
        accessibilityRole="button"
        accessibilityState={{ selected }}
        style={({ pressed }) => [s.cardRow, pressed && { opacity: 0.72 }]}>
        <Icon name={vehicleGlyph(o.mode)} color={selected ? V2T.accent : V2T.text2} size={28} filled={selected} />
        <View style={s.cardMid}>
          <View style={s.cardTop}>
            <Text style={[s.optLabel, { fontFamily: fam(lang, "med") }]} numberOfLines={1}>
              {showYours ? `${o.label} · ${t("compare_yours", lang)}` : o.label}
            </Text>
            {tag ? <Chip text={tag} accent lang={lang} />
              : o.recommended ? <Chip text={t("compare_pick", lang)} lang={lang} /> : null}
          </View>
          <Text style={[s.optMeta, { fontFamily: fam(lang, "reg") }]} numberOfLines={1}>{meta}</Text>
          {o.reason_line ? (
            <Text style={[s.optReason, { fontFamily: fam(lang, "reg") }]} numberOfLines={2}>{o.reason_line}</Text>
          ) : null}
          {d?.coverage != null && d.coverage < 0.999 ? (
            <Text style={[s.optCoverage, { fontFamily: fam(lang, "reg") }]} numberOfLines={1}>
              {t("plan_coverage_note", lang)}
            </Text>
          ) : null}
        </View>
        <View style={s.cardRight}>
          <Text style={[s.optEta, NUM, { fontFamily: fam(lang, "semi") }]}>
            {Math.round(o.duration_min)}<Text style={s.optEtaUnit}> {t("minUnit", lang)}</Text>
          </Text>
          {d?.mid != null ? (
            <Text style={[s.optDose, NUM, { fontFamily: fam(lang, "semi"), color: doseCol }]}>
              ≈{Math.round(d.mid)}<Text style={s.optDoseUnit}> µg</Text>
              {band ? <Text style={[s.optBand, { fontFamily: fam(lang, "reg") }]}>  {band}</Text> : null}
            </Text>
          ) : (
            /* TODO(strings): `compare_doseNA` — short "no estimate" marker
               for the dose column; bare dash until the key lands. */
            <Text style={[s.optDose, s.optDoseNA, { fontFamily: fam(lang, "med") }]}>—</Text>
          )}
          <View style={s.barsRow}>
            <PairBars o={o} worstIn={worstIn} worstOut={worstOut} lang={lang} />
            <Pressable
              onPress={() => onToggleDetail(i)}
              hitSlop={16}
              accessibilityRole="button"
              accessibilityLabel={t("howWeGotThis", lang)}
              style={({ pressed }) => [s.infoBtn, pressed && { opacity: 0.5 }]}>
              <Icon name="info" color={open ? V2T.accent : V2T.text3} size={13} />
            </Pressable>
          </View>
        </View>
      </Pressable>
      {open && <DetailBlock o={o} fieldAgeS={fieldAgeS} lang={lang} />}
    </View>
  );
}

export function CompareSheet({
  options, selected, onSelect, depart, departCurve, notified, onRemind,
  loading, steps, stepsOpen, onToggleSteps, onStart, onClose, lang,
  planError = null, onRetry, vehicle, onVehiclePress, onVehicleChange, fieldAgeS,
}: {
  options: V2Option[]; selected: number; onSelect: (i: number) => void;
  depart: Depart; notified: boolean; onRemind: () => void;
  /** full 24h dose curve — mounts the leave-later graph when present */
  departCurve?: DepartCurve | null;
  loading: boolean; steps: Step[] | null; stepsOpen: boolean;
  onToggleSteps: () => void; onStart: () => void; onClose: () => void; lang: Lang;
  /** v2 plan failure — honest retry state, never a silent /decide fallback */
  planError?: PlanError | null;
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
  const anyBars = worstIn > 0 || worstOut > 0;
  const toggleDetail = (i: number) => setDetailIdx((cur) => (cur === i ? null : i));

  const chip = (
    <Pressable
      onPress={() => (onVehiclePress ? onVehiclePress() : setVehOpen(true))}
      hitSlop={8}
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
      <Sheet detent="half" onClose={onClose} lang={lang}>
        {loading ? (
          <View style={s.stateWrap}>
            <ActivityIndicator size="small" color={V2T.accent} />
            <Text style={[s.stateSub, { fontFamily: fam(lang, "reg"), marginTop: 10 }]}>
              {t("checkingRoutes", lang)}
            </Text>
          </View>
        ) : planError ? (
          planError.kind === "outside" ? (
            /* typed outside-coverage answer — a scope notice, not a fault:
               retry can't fix geography, the CTA is 'change the trip' */
            <View style={s.stateWrap}>
              <View style={s.stateIcon}>
                <Icon name="pin" color={V2T.accent} size={20} />
              </View>
              <Text style={[s.stateTitle, { fontFamily: fam(lang, "med") }]}>
                {t("plan_outside_title", lang)}
              </Text>
              <Text style={[s.stateSub, { fontFamily: fam(lang, "reg") }]} numberOfLines={4}>
                {t("plan_outside_body", lang)}
              </Text>
              <Pressable onPress={onClose} style={s.retryBtn} accessibilityRole="button"
                accessibilityLabel={t("plan_outside_cta", lang)}>
                <Text style={[s.retryTxt, { fontFamily: fam(lang, "med") }]}>{t("plan_outside_cta", lang)}</Text>
              </Pressable>
            </View>
          ) : (
          <View style={s.stateWrap}>
            <View style={s.stateIcon}>
              <Icon name="info" color={V2T.accent} size={20} />
            </View>
            <Text style={[s.stateTitle, { fontFamily: fam(lang, "med") }]}>
              {t(planError.kind === "network" ? "plan_failed" : "plan_failed_server", lang)}
            </Text>
            {planError.detail ? (
              <Text style={[s.stateSub, { fontFamily: fam(lang, "reg") }]} numberOfLines={3}>
                {planError.detail}
              </Text>
            ) : null}
            {onRetry && (
              <Pressable onPress={onRetry} style={s.retryBtn} accessibilityRole="button"
                accessibilityLabel={t("plan_retry", lang)}>
                <Text style={[s.retryTxt, { fontFamily: fam(lang, "med") }]}>{t("plan_retry", lang)}</Text>
              </Pressable>
            )}
          </View>
          )
        ) : options.length > 0 ? (
          <>
            <ScrollView style={s.scroll} contentContainerStyle={s.scrollContent}
              showsVerticalScrollIndicator={false}>
              {chip}
              {depart?.ug_saved_vs_now != null && depart.ug_saved_vs_now > 8 && (
                <Pressable onPress={onRemind} style={({ pressed }) => [s.departRow, pressed && { opacity: 0.7 }]}
                  accessibilityRole="button">
                  <Icon name={notified ? "bell" : "clock"} color={V2T.accent} size={16} filled={notified} />
                  <Text style={[s.departTxt, { fontFamily: fam(lang, "med") }]}>
                    {notified
                      ? t("wellPing", lang)
                      : t("leaveAtBreatheLess", lang, {
                          time: hourLabel(depart.best.start, depart.best.hours_ahead, lang),
                          n: Math.round(depart.ug_saved_vs_now),
                        })}
                  </Text>
                </Pressable>
              )}
              {departCurve?.slots?.length ? (
                <View style={{ marginTop: 10, marginBottom: 4 }}>
                  <DepartGraph data={departCurve.slots}
                    bestHour={departCurve.best?.hour ?? 0} lang={lang} />
                </View>
              ) : null}
              {anyBars && (
                <View style={s.legend}>
                  <View style={s.legendItem}>
                    <Icon name="cigarette" color={V2T.text3} size={11} />
                    <Text style={[s.legendTxt, { fontFamily: fam(lang, "reg") }]}>{t("compare_smokeIn", lang)}</Text>
                  </View>
                  <View style={s.legendItem}>
                    <Icon name="smoke" color={V2T.text3} size={11} />
                    <Text style={[s.legendTxt, { fontFamily: fam(lang, "reg") }]}>{t("compare_smokeOut", lang)}</Text>
                  </View>
                </View>
              )}
              {options.map((o, i) => (
                <OptionCard
                  key={`${o.mode}-${i}`}
                  o={o} i={i}
                  selected={i === selected}
                  worstIn={worstIn} worstOut={worstOut}
                  showYours={!!o.your_vehicle && veh != null}
                  open={detailIdx === i}
                  fieldAgeS={fieldAgeS}
                  lang={lang}
                  onSelect={onSelect}
                  onToggleDetail={toggleDetail}
                />
              ))}
              {stepsOpen && steps && (
                <View style={s.stepsList}>
                  {sel?.mode === "metro" && sel.stations ? (
                    <Text style={[s.stepTxt, { fontFamily: fam(lang, "reg") }]}>
                      {t("boardMetro", lang, { a: sel.stations.board, b: sel.stations.alight })}
                    </Text>
                  ) : steps.map((st, i) => (
                    <View key={i} style={s.stepRow}>
                      <View style={s.stepRail}>
                        <View style={s.stepDot} />
                        {i < steps.length - 1 && <View style={s.stepLine} />}
                      </View>
                      <Text style={[s.stepTxt, { fontFamily: fam(lang, "reg") }]}>{st.instruction}</Text>
                      <Text style={[s.stepDist, NUM, { fontFamily: fam(lang, "reg") }]}>
                        {st.distance_m >= 1000 ? `${(st.distance_m / 1000).toFixed(1)} km` : `${Math.round(st.distance_m)} m`}
                      </Text>
                    </View>
                  ))}
                </View>
              )}
              {stepsOpen && sel?.mode !== "metro" && !steps && (
                <Text style={[s.stepTxt, s.stepsEmpty, { fontFamily: fam(lang, "reg") }]}>
                  {t("roadModesOnly", lang)}
                </Text>
              )}
            </ScrollView>
            {sel && (
              <View style={s.footer}>
                <Pressable onPress={onToggleSteps}
                  style={({ pressed }) => [s.ghostBtn, stepsOpen && s.ghostBtnOn, pressed && { opacity: 0.65 }]}
                  accessibilityRole="button">
                  <Text style={[s.ghostTxt, stepsOpen && s.ghostTxtOn, { fontFamily: fam(lang, "med") }]}>
                    {stepsOpen ? t("hideTurns", lang) : t("turnByTurn", lang)}
                  </Text>
                </Pressable>
                <Pressable onPress={onStart}
                  style={({ pressed }) => [s.goBtn, pressed && { opacity: 0.8 }]}
                  accessibilityRole="button">
                  <Text style={[s.goBtnTxt, { fontFamily: fam(lang, "semi") }]}>{t("start", lang)}</Text>
                </Pressable>
              </View>
            )}
          </>
        ) : (
          <View style={s.stateWrap}>
            <View style={s.stateIcon}>
              <Icon name="search" color={V2T.text3} size={20} />
            </View>
            <Text style={[s.stateSub, { fontFamily: fam(lang, "reg") }]}>{t("noRoutes", lang)}</Text>
          </View>
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

  /* ---- list ---- */
  scroll: { flexShrink: 1, flexGrow: 0 },
  scrollContent: { paddingBottom: 10 },
  vehChip: {
    flexDirection: "row", alignItems: "center", gap: 6, alignSelf: "flex-start",
    marginHorizontal: 14, marginTop: 4, marginBottom: 2, minHeight: 34,
    paddingHorizontal: 11, paddingVertical: 6,
    backgroundColor: V2T.surface2, borderRadius: V2Radius.pill,
    borderWidth: 1, borderColor: V2T.line,
  },
  vehChipTxt: { fontSize: V2Type.label, color: V2T.text2, maxWidth: 220 },
  departRow: {
    flexDirection: "row", alignItems: "center", gap: 8,
    marginHorizontal: 14, marginTop: 6, marginBottom: 2, minHeight: 44,
    paddingHorizontal: 12, paddingVertical: 9, borderRadius: V2Radius.row,
    backgroundColor: V2T.accentTint,
    borderWidth: 1, borderColor: V2T.accent,
  },
  departTxt: { fontSize: V2Type.label, color: V2T.accent, flex: 1 },
  legend: {
    flexDirection: "row", justifyContent: "flex-end", alignItems: "center",
    gap: 14, marginHorizontal: 28, marginTop: 7, marginBottom: 1,
  },
  legendItem: { flexDirection: "row", alignItems: "center", gap: 5 },
  legendTxt: { fontSize: V2Type.label, color: V2T.text3 },

  /* ---- option card ---- */
  card: {
    marginHorizontal: 14, marginTop: 7, borderRadius: V2Radius.row,
    backgroundColor: V2T.surface2, borderWidth: 1, borderColor: V2T.line,
    overflow: "hidden",
  },
  cardSel: { borderColor: V2T.accent, backgroundColor: V2T.accentTint },
  cardRow: {
    flexDirection: "row", alignItems: "center", gap: 12,
    paddingVertical: 12, paddingHorizontal: 14, minHeight: 64,
  },
  cardMid: { flex: 1 },
  cardTop: { flexDirection: "row", alignItems: "center", flexWrap: "wrap" },
  optLabel: { fontSize: V2Type.secondary, color: V2T.text, flexShrink: 1 },
  chip: {
    borderRadius: V2Radius.pill, paddingHorizontal: 7, paddingVertical: 2,
    marginLeft: 8,
  },
  chipAccent: { backgroundColor: V2T.accentTint },
  chipPlain: { backgroundColor: V2T.bg, borderWidth: 1, borderColor: V2T.line },
  chipTxt: { fontSize: V2Type.label },
  chipTxtAccent: { color: V2T.accent },
  chipTxtPlain: { color: V2T.text2 },
  optMeta: { fontSize: V2Type.label, color: V2T.text3, marginTop: 2 },
  optReason: { fontSize: V2Type.label, color: V2T.text3, marginTop: 3 },
  optCoverage: { fontSize: V2Type.label, color: V2T.breath2, marginTop: 3 },
  cardRight: { alignItems: "flex-end" },
  optEta: { fontSize: V2Type.body, color: V2T.text },
  optEtaUnit: { fontSize: V2Type.label, color: V2T.text2 },
  optDose: { fontSize: V2Type.secondary, marginTop: 3 },
  optDoseUnit: { fontSize: V2Type.label, color: V2T.text3 },
  optDoseNA: { color: V2T.text3 },
  optBand: { fontSize: V2Type.label, color: V2T.text3 },
  barsRow: { flexDirection: "row", alignItems: "center", marginTop: 6, gap: 10 },
  bars: { flexDirection: "row", alignItems: "center", gap: 8 },
  barGroup: { flexDirection: "row", alignItems: "center", gap: 4 },
  track: {
    width: 30, height: 5, borderRadius: 2.5, backgroundColor: V2T.bg,
    flexDirection: "row", overflow: "hidden",
  },
  trackNA: { opacity: 0.35 },
  trackFill: { borderRadius: 2.5 },
  infoBtn: { padding: 2 },

  /* ---- in-card details ---- */
  detail: {
    borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: V2T.line,
    paddingHorizontal: 14, paddingTop: 9, paddingBottom: 11, gap: 5,
  },
  dTitle: { fontSize: V2Type.label, color: V2T.text3, marginBottom: 1 },
  dRow: { flexDirection: "row", alignItems: "flex-start", gap: 8 },
  dLine: { flex: 1, fontSize: V2Type.label, color: V2T.text },
  dRowSub: { flex: 1, fontSize: V2Type.label, color: V2T.text3 },
  dSub: { fontSize: V2Type.label, color: V2T.text3, marginLeft: 21 },
  dFine: {
    fontSize: V2Type.label, color: V2T.text3,
    borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: V2T.line,
    paddingTop: 8, marginTop: 4,
  },

  /* ---- steps ---- */
  stepsList: { paddingHorizontal: 16, paddingTop: 8 },
  stepRow: { flexDirection: "row", alignItems: "flex-start", paddingVertical: 5, gap: 10 },
  stepRail: { width: 7, alignItems: "center", alignSelf: "stretch" },
  stepDot: { width: 7, height: 7, borderRadius: 3.5, backgroundColor: V2T.accent, marginTop: 5 },
  stepLine: { width: 1, flex: 1, backgroundColor: V2T.line, marginTop: 2 },
  stepTxt: { flex: 1, fontSize: V2Type.secondary, color: V2T.text, paddingBottom: 4 },
  stepDist: { fontSize: V2Type.label, color: V2T.text3, marginTop: 2 },
  stepsEmpty: { paddingHorizontal: 16, paddingTop: 8 },

  /* ---- pinned footer ---- */
  footer: {
    flexDirection: "row", alignItems: "center", justifyContent: "flex-end",
    gap: 10, paddingHorizontal: 16, paddingVertical: 10,
    borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: V2T.line,
  },
  ghostBtn: {
    minHeight: 44, justifyContent: "center", borderRadius: V2Radius.pill,
    paddingHorizontal: 16, borderWidth: 1, borderColor: V2T.line,
  },
  ghostBtnOn: { borderColor: V2T.accent, backgroundColor: V2T.accentTint },
  ghostTxt: { fontSize: V2Type.secondary, color: V2T.text2 },
  ghostTxtOn: { color: V2T.accent },
  goBtn: {
    minHeight: 44, justifyContent: "center", alignItems: "center",
    backgroundColor: V2T.accent, borderRadius: V2Radius.pill, paddingHorizontal: 34,
  },
  goBtnTxt: { fontSize: V2Type.body, color: V2T.bg },   // light on accent pill (V2T.bg ≈7:1 on accent)

  /* ---- states ---- */
  stateWrap: { paddingVertical: 24, paddingHorizontal: 24, alignItems: "center" },
  stateIcon: {
    width: 42, height: 42, borderRadius: 21, marginBottom: 10,
    backgroundColor: V2T.surface2, borderWidth: 1, borderColor: V2T.line,
    alignItems: "center", justifyContent: "center",
  },
  stateTitle: { fontSize: V2Type.secondary, color: V2T.text, textAlign: "center" },
  stateSub: { fontSize: V2Type.label, color: V2T.text3, textAlign: "center", marginTop: 6 },
  retryBtn: {
    marginTop: 14, minHeight: 44, justifyContent: "center",
    backgroundColor: V2T.accent, borderRadius: V2Radius.pill,
    paddingHorizontal: 26, paddingVertical: 12,
  },
  retryTxt: { fontSize: V2Type.secondary, color: V2T.bg }, // accent pill → light text
});
