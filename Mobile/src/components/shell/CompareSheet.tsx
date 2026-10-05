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
import { NUM, V2Elev, V2Radius, V2T, V2Type, doseColor, fam, famMono, famMonoText } from "../../theme";
import { DYNAMIC_TYPE } from "../../a11y";
import { Icon, vehicleGlyph, type Glyph } from "../../icons";
import { CountUp, Sheet, pressFx } from "../../ui";
import { approx, modeLabel, t, type Lang, type StringKey } from "../../i18n/strings";
import { DepartGraph } from "../DepartGraph";
import type { DepartCurve } from "../../api/depart";
import type { PlanError } from "./useShellFlow";
import { confirm, tap, tick } from "../../haptics";
import { localizeStep } from "../../nav/instructions";
import {
  className, fuelName, getVehicle, saveVehicle, vehicleLabel,
  type VehicleProfile,
} from "../../store/vehicle";
import { VehicleSheet } from "../../screens/VehicleSheet";
import { isTransit } from "./types";
import type { Band, Depart, Emissions, Step, V2Option } from "./types";
import { bump } from "../../perf";

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

/** degraded arm → row detector + string key. The banner lists only arms
 *  that left a real gap on screen: an arm whose rows survived anyway
 *  (e.g. engine-first paint merged in) is not "unavailable" to the user,
 *  and an empty arm that never had rows is not a loss either. */
const ARM_KEY: Record<string, StringKey> = {
  engine: "degradedEngine",
  transit: "degradedTransit",
  motor: "degradedMotor",
  slow: "degradedSlow",
};
const ARM_PRESENT: Record<string, (o: V2Option) => boolean> = {
  engine: (o) => o.engine != null,
  transit: (o) => isTransit(o),
  motor: (o) => !isTransit(o) && o.mode !== "cycle" && o.mode !== "walk",
  slow: (o) => o.mode === "cycle" || o.mode === "walk",
};

/** server reason_line (server/v2/plan.py rank_options) is a fixed set of
 * English templates — translate verbatim so the card stays in the user's
 * language. The trailing " +N min vs fastest." gets re-composed locally.
 * Unknown text passes through untouched — additive future lines still show. */
const REASON_KEY: Record<string, StringKey> = {
  "Least smoke for you — no emissions estimate for this set.": "reason_noEmis",
  "Least smoke for you and lowest emissions — the easy pick.": "reason_easyPick",
  "Least smoke for you, but heavier for Delhi.": "reason_heavierDelhi",
  "Lowest emissions of the options — but you'd breathe more.": "reason_lowestEmis",
  "Within ~10% of the lightest dose and the lightest exhaust of those — a fair trade.":
    "reason_fairTrade",
};
const SLOWER_RE = / \+(\d+) min vs fastest\.$/;

/** server non_exhaust.note strings — same verbatim-match treatment. */
const NE_KEY: Record<string, StringKey> = {
  "non-exhaust (resuspended dust + brakes/tyres), reported separately — ~86% of Delhi traffic PM10 is non-exhaust (Sahu et al. 2020, docs/26); never folded into tailpipe numbers": "ne_road",
  "rail — no road resuspension": "ne_rail",
  "zero — non-motorized mode": "ne_zero",
};
const neNoteTxt = (n: string, lang: Lang): string => {
  const key = NE_KEY[n];
  return key ? t(key, lang) : n;
};

/** emissions.py's two fixed metro provenance sentences — the payload
 *  carries no structured fields for these, so they map verbatim. */
const EMLBL_KEY: Record<string, StringKey> = {
  "metro per passenger-km (incl. electricity)": "emit_metroShort",
  "metro per passenger-km, incl. electricity (11–25 g CO2e/pkm — DMRC + CEA grid EF, docs/31 §3)": "emit_metroLong",
};

/** plan.py dose-note strings — rendered when dose can't estimate. */
const DOSE_NOTE_KEY: Record<string, StringKey> = {
  "dose engine unavailable": "doseNote_engineDown",
  "dose engine error": "doseNote_engineError",
  "field unavailable": "doseNote_fieldDown",
};
const doseNoteTxt = (n: string, lang: Lang): string => {
  const key = DOSE_NOTE_KEY[n];
  return key ? t(key, lang) : n;
};

const reasonTxt = (n: string, lang: Lang): string => {
  const m = n.match(SLOWER_RE);
  const base = m ? n.slice(0, -m[0].length) : n;
  const key = REASON_KEY[base];
  const out = key ? t(key, lang) : base;
  return m ? out + t("reason_slowerSuffix", lang, { m: m[1] }) : out;
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

/** The pair of bars on every card — breathe-in (dust/cigarette glyph) over
 *  the dose band, exhaust (plume) over CO2, both relative to the worst
 *  option. The cigarette equivalence lives in the detail block below —
 *  never as a primary glyph on the bars. */
function PairBars({ o, worstIn, worstOut, lang }: {
  o: V2Option; worstIn: number; worstOut: number; lang: Lang;
}) {
  const inFrac = o.dose?.mid != null && worstIn > 0 ? o.dose.mid / worstIn : null;
  const outFrac = o.emissions?.co2_kg?.mid != null && worstOut > 0 ? o.emissions.co2_kg.mid / worstOut : null;
  return (
    <View style={s.bars}>
      <View style={s.barGroup} accessible accessibilityLabel={t("compare_smokeIn", lang)}>
        <Icon name="dust" color={V2T.text3} size={11} />
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
 *  pick" stays neutral so the stronger claim reads stronger. `glyph`
 *  puts a small icon beside the text (the "safest route" leaf). */
function Chip({ text, accent, glyph, lang }: {
  text: string; accent?: boolean; glyph?: Glyph; lang: Lang;
}) {
  return (
    <View style={[s.chip, accent ? s.chipAccent : s.chipPlain]}>
      {glyph ? (
        <Icon name={glyph} color={accent ? V2T.accent : V2T.text2} size={10} />
      ) : null}
      <Text {...DYNAMIC_TYPE}
        style={[s.chipTxt, accent ? s.chipTxtAccent : s.chipTxtPlain, { fontFamily: fam(lang, "med") }]}
        numberOfLines={1}>
        {text}
      </Text>
    </View>
  );
}

/* server/emissions.py:_BS_NAME — BS stages stay Latin even in Hindi
   (that's how the standard's written in Hindi media too). */
const BS_NAME: Record<string, string> = {
  bs2: "BS-II", bs3: "BS-III", bs4: "BS-IV", bs6: "BS-VI",
};
const bsName = (b: string) => BS_NAME[b] ?? b.toUpperCase();

/* _label()'s year words, keyed by the CLIENT YearBand — the bucket the
   server resolved is recoverable because we sent it. */
const YEAR_TXT: Record<string, { en: string; hi: string }> = {
  pre_2010: { en: "pre-2010", hi: "2010 से पहले" },
  y2010_2016: { en: "2010–2016", hi: "2010–2016" },
  y2017_2020: { en: "2017–2019", hi: "2017–2019" },   // maps to server bucket 2017_2019
  y2021_plus: { en: "2020+", hi: "2020+" },
};

/** dose confidence — the server ships an enum word; read it in the
 *  user's language, unknown values pass through honestly. */
const confTxt = (c: string, lang: Lang): string => {
  const k = c === "high" ? "conf_high" : c === "medium" ? "conf_medium" : c === "low" ? "conf_low" : null;
  return k ? t(k, lang) : c;
};

/** basis enums → words; human-string bases (labelled fallback table)
 *  pass through as the server wrote them. */
const basisTxt = (b: string | null | undefined, lang: Lang): string | null => {
  if (!b) return null;
  if (b === "per_vkm") return t("emit_basisPerVkm", lang);
  if (b === "per_pax_km") return t("emit_basisPerPaxKm", lang);
  return b;
};

/** The "estimated for vehicles like yours (…)" provenance line — the
 *  server composes it in English; we rebuild it in the user's language
 *  from the structured fields it also ships (fuel, class, bs range,
 *  occupancy, puc), with the same grammar as _label(). English keeps
 *  the server's own sentence; payload flavours without fuel/class
 *  (metro, labelled fallbacks) keep it too — never a guessed rebuild. */
function emissionsLabel(e: Emissions, yours: boolean, veh: VehicleProfile | null, lang: Lang): string | null {
  if (e.label && EMLBL_KEY[e.label]) return t(EMLBL_KEY[e.label], lang);
  if (lang !== "hi" || !e.fuel || !e.class || !e.bs_class) {
    return e.label ?? basisTxt(e.basis, lang);
  }
  const opts = (e.bs_options ?? []).filter((x) => x !== "none");
  const bsTxt = opts.length <= 1 ? bsName(e.bs_class)
    : `${bsName(opts[0])}–${bsName(opts[opts.length - 1])}`;
  const cname = className(e.class, lang);
  const inner = e.fuel === "electric"
    ? t("emit_innerEv", lang, { c: cname })
    : (yours && veh?.year && veh.year !== "not_sure")
      ? t("emit_innerYear", lang, {
          y: YEAR_TXT[veh.year]?.[lang] ?? veh.year,
          f: fuelName(e.fuel, lang), c: cname, b: bsTxt,
        })
      : t("emit_innerFleet", lang, { f: fuelName(e.fuel, lang), c: cname, b: bsTxt });
  return t("emit_est", lang) + " (" + inner + ")"
    + (e.occupancy != null && e.occupancy > 1 ? t("emit_perPax", lang, { o: e.occupancy }) : "")
    + (e.puc_calibrated ? t("emit_pucTuned", lang) : "");
}

/** "How we got this number" — the ONLY place jargon is allowed. Bands,
 *  bases, confidence, field age, all honest and server-sourced. Opens
 *  inside the card under a hairline so the association never gets lost. */
function DetailBlock({ o, fieldAgeS, showCig, veh, lang }: { o: V2Option; fieldAgeS?: number | null; showCig: boolean; veh: VehicleProfile | null; lang: Lang }) {
  const d = o.dose, e = o.emissions;
  const cig = showCig && d.mid != null ? Math.round((d.mid / 316) * 100) / 100 : null;
  const ageMin = fieldAgeS != null ? Math.max(0, Math.round(fieldAgeS / 60)) : null;
  const emit = [bandTxt(e.co2_kg, "kg CO2"), bandTxt(e.pm25_g, "g PM2.5")].filter(Boolean).join("  ·  ");
  return (
    <View style={s.detail}>
      <Text {...DYNAMIC_TYPE} style={[s.dTitle, { fontFamily: fam(lang, "med") }]}>{t("howWeGotThis", lang)}</Text>
      <View style={s.dRow}>
        <Icon name="dust" color={V2T.breath2} size={13} />
        {d.mid != null ? (
          <Text {...DYNAMIC_TYPE} style={[s.dLine, NUM, { fontFamily: famMonoText(lang, "reg") }]}>
            {t("howWe_in", lang, { mid: Math.round(d.mid), lo: Math.round(d.lo ?? d.mid), hi: Math.round(d.hi ?? d.mid) })}
            {cig != null ? `  ·  ${t("howWe_cigs", lang, { n: approx(cig) })}` : ""}
          </Text>
        ) : (
          <Text {...DYNAMIC_TYPE} style={[s.dLine, { fontFamily: fam(lang, "reg") }]}>{d.note ? doseNoteTxt(d.note, lang) : t("howWe_none", lang)}</Text>
        )}
      </View>
      {d.confidence ? <Text {...DYNAMIC_TYPE} style={[s.dSub, { fontFamily: fam(lang, "reg") }]}>{t("howWe_conf", lang, { c: confTxt(d.confidence, lang) })}</Text> : null}
      {emit ? (
        <View style={s.dRow}>
          <Icon name="smoke" color={V2T.out1} size={13} />
          <Text {...DYNAMIC_TYPE} style={[s.dLine, NUM, { fontFamily: famMonoText(lang, "reg") }]}>{t("howWe_out", lang, { v: emit })}</Text>
        </View>
      ) : null}
      {d.coverage != null && d.coverage < 0.999 ? (
        <Text {...DYNAMIC_TYPE} style={[s.dSub, { fontFamily: fam(lang, "reg") }]}>
          {t("howWe_coverage", lang, { pct: Math.round(d.coverage * 100) })}
        </Text>
      ) : null}
      {(() => {
        const lbl = emissionsLabel(e, !!o.your_vehicle, veh, lang);
        return lbl ? <Text {...DYNAMIC_TYPE} style={[s.dSub, { fontFamily: fam(lang, "reg") }]}>{lbl}</Text> : null;
      })()}
      {e.bs_class && e.bs_class !== "none"
        ? <Text {...DYNAMIC_TYPE} style={[s.dSub, { fontFamily: fam(lang, "reg") }]}>
            {bsName(e.bs_class)}{(e.bs_options?.length ?? 0) > 1
              ? ` (${(e.bs_options ?? []).map(bsName).join("–")})` : ""}
          </Text>
        : null}
      {e.non_exhaust?.note ? <Text {...DYNAMIC_TYPE} style={[s.dSub, { fontFamily: fam(lang, "reg") }]}>{neNoteTxt(e.non_exhaust.note, lang)}</Text> : null}
      {ageMin != null ? (
        <View style={s.dRow}>
          <Icon name="clock" color={V2T.text3} size={13} />
          <Text {...DYNAMIC_TYPE} style={[s.dRowSub, { fontFamily: fam(lang, "reg") }]}>{t("howWe_fieldAge", lang, { n: ageMin })}</Text>
        </View>
      ) : null}
      <Text {...DYNAMIC_TYPE} style={[s.dFine, { fontFamily: fam(lang, "reg") }]}>{t("cityBasisBand", lang)}</Text>
    </View>
  );
}

/** One ranked option — solid card. Tap selects; the ⓘ beside the bars
 *  (or a long-press anywhere on the card) opens the details panel. */
function OptionCard({ o, i, selected, worstIn, worstOut, minDose, showYours, open,
  fieldAgeS, showCig, safest, veh, lang, onSelect, onToggleDetail }: {
  o: V2Option; i: number; selected: boolean; worstIn: number; worstOut: number;
  /** the lightest dose in the set — the gap line is computed against it */
  minDose: number;
  showYours: boolean; open: boolean; fieldAgeS?: number | null;
  showCig: boolean; safest: boolean; veh: VehicleProfile | null; lang: Lang;
  onSelect: (i: number) => void; onToggleDetail: (i: number) => void;
}) {
  const d = o.dose;
  const band = d && (d.lo != null || d.hi != null) && (d.lo !== d.mid || d.hi !== d.mid)
    ? `${d.lo != null ? Math.round(d.lo) : "?"}–${d.hi != null ? Math.round(d.hi) : "?"}`
    : null;
  const doseCol = d?.avg_conc_ugm3 != null ? doseColor(d.avg_conc_ugm3) : V2T.text;
  /* the dose-gap line — the sheet's emotional payload. "+6 vs lightest"
     is the number that makes a person pick the metro. µg-gap against the
     set's minimum; invisible on the lightest card itself. */
  const doseGap = d?.mid != null && minDose < Infinity && d.mid - minDose >= 0.5
    ? Math.round(d.mid - minDose) : null;
  const meta = `${o.distance_km ?? "?"} ${t("unitsKm", lang)} · ${t("arriveAt", lang, { t: arrivalLabel(o.duration_min) })}`
    + `${o.stations ? ` · ${o.stations.board}→${o.stations.alight}` : ""}`;
  const tag = o.tag ? (TAG_KEY[o.tag.toLowerCase()] ? t(TAG_KEY[o.tag.toLowerCase()], lang) : o.tag) : null;
  return (
    <View style={[s.card, selected && s.cardSel]}>
      <Pressable
        onPress={() => { tick(); onSelect(i); }}
        onLongPress={() => { tick(); onToggleDetail(i); }}
        delayLongPress={400}
        accessibilityRole="button"
        accessibilityState={{ selected }}
        style={({ pressed }) => [s.cardRow, pressFx(pressed)]}>
        <Icon name={vehicleGlyph(o.mode)} color={selected ? V2T.accent : V2T.text2} size={28} filled={selected} />
        <View style={s.cardMid}>
          <View style={s.cardTop}>
            <Text {...DYNAMIC_TYPE} style={[s.optLabel, { fontFamily: fam(lang, "med") }]} numberOfLines={1}>
              {showYours
                ? `${modeLabel(o.mode, o.label, lang)} · ${t("compare_yours", lang)}`
                : modeLabel(o.mode, o.label, lang)}
            </Text>
            {/* the least-inhalation route leads: "safest route" (the
                server's safest_path flag, or the dose-min option when
                no flag was sent) sits ahead of the server tag, which is
                demoted to plain while the headline chip is up */}
            {safest ? <Chip text={t("compare_safest", lang)} accent glyph="leaf" lang={lang} /> : null}
            {tag ? <Chip text={tag} accent={!safest} lang={lang} />
              : o.recommended && !safest ? <Chip text={t("compare_pick", lang)} lang={lang} /> : null}
          </View>
          <Text {...DYNAMIC_TYPE} style={[s.optMeta, { fontFamily: fam(lang, "reg") }]} numberOfLines={1}>{meta}</Text>
          {o.reason_line ? (
            <Text {...DYNAMIC_TYPE} style={[s.optReason, { fontFamily: fam(lang, "reg") }]} numberOfLines={2}>{reasonTxt(o.reason_line, lang)}</Text>
          ) : null}
          {o.via_names && o.via_names.length ? (
            <Text {...DYNAMIC_TYPE} style={[s.optReason, { fontFamily: fam(lang, "reg") }]} numberOfLines={1}>
              {t("viaStreets", lang, { streets: o.via_names.slice(0, 2).join(" → ") + (o.via_names.length > 2 ? "…" : "") })}
            </Text>
          ) : null}
          {d?.coverage != null && d.coverage < 0.999 ? (
            <Text {...DYNAMIC_TYPE} style={[s.optCoverage, { fontFamily: fam(lang, "reg") }]} numberOfLines={1}>
              {t("plan_coverage_note", lang)}
            </Text>
          ) : null}
        </View>
        <View style={s.cardRight}>
          {/* hierarchy flip: the dose owns the right column now (the
              number this app exists for), ETA recedes to a muted
              sub-line — a traveller reads "≈34µg · 47 min", not the
              reverse */}
          {d?.mid != null ? (
            <>
              <CountUp value={d.mid} duration={520}
                style={[s.optDose, NUM, { fontFamily: famMono(lang, "semi"), color: doseCol }]}
                format={(n) => `≈${Math.round(n)}`} />
              <Text {...DYNAMIC_TYPE} style={[s.optDoseSub, NUM, { fontFamily: famMono(lang, "reg") }]} numberOfLines={1}>
                <Text {...DYNAMIC_TYPE} style={s.optDoseUnit}>µg</Text>
                {band ? ` ${band}` : ""}
                {doseGap != null ? (
                  <Text {...DYNAMIC_TYPE} style={[s.optGap, { fontFamily: fam(lang, "med") }]}>
                    {"  "}{t("compare_vsLightest", lang, { n: doseGap })}
                    {/* the felt multiple — "2.4×" lands harder than "+82"
                        when the gap is big; under 2× the µg reads truer */}
                    {minDose > 0 && d?.mid != null && d.mid / minDose >= 2
                      ? ` · ${(d.mid / minDose).toFixed(1)}×` : ""}
                  </Text>
                ) : null}
              </Text>
            </>
          ) : (
            <Text {...DYNAMIC_TYPE} style={[s.optDose, s.optDoseNA, { fontFamily: fam(lang, "med") }]} numberOfLines={1}>{t("compare_doseNA", lang)}</Text>
          )}
          <Text {...DYNAMIC_TYPE} style={[s.optEta, NUM, { fontFamily: famMonoText(lang, "reg") }]} numberOfLines={1}>
            {Math.round(o.duration_min)}<Text {...DYNAMIC_TYPE} style={s.optEtaUnit}> {t("minUnit", lang)}</Text>
          </Text>
          <View style={s.barsRow}>
            <PairBars o={o} worstIn={worstIn} worstOut={worstOut} lang={lang} />
            <Pressable
              onPress={() => { tick(); onToggleDetail(i); }}
              hitSlop={16}
              accessibilityRole="button"
              accessibilityLabel={t("howWeGotThis", lang)}
              style={({ pressed }) => [s.infoBtn, pressed && { opacity: 0.5 }]}>
              <Icon name="info" color={open ? V2T.accent : V2T.text3} size={13} />
            </Pressable>
          </View>
        </View>
      </Pressable>
      {open && <DetailBlock o={o} fieldAgeS={fieldAgeS} showCig={showCig} veh={veh} lang={lang} />}
    </View>
  );
}

function CompareSheetInner({
  options, selected, onSelect, depart, departCurve, notified, onRemind,
  loading, steps, stepsOpen, onToggleSteps, onStart, onClose, lang,
  planError = null, onRetry, vehicle, onVehiclePress, onVehicleChange, fieldAgeS,
  showCig = false, refining = false, degraded,
}: {
  options: V2Option[]; selected: number; onSelect: (i: number) => void;
  depart: Depart; notified: boolean; onRemind: () => void;
  /** full 24h dose curve — mounts the leave-later graph when present */
  departCurve?: DepartCurve | null;
  loading: boolean; steps: Step[] | null; stepsOpen: boolean;
  onToggleSteps: () => void; onStart: () => void; onClose: () => void; lang: Lang;
  /** cigarette-equivalence framing — off by default (settings.show_cig) */
  showCig?: boolean;
  /** engine rows shown; router/transit rows still landing */
  refining?: boolean;
  /** planner arms the /v2/plan response lost — names which kind of route
      is absent so the sheet reads as incomplete, not complete-and-empty */
  degraded?: string[];
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
  bump("shell.Compare");
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

  /* The "safest route" headline: an explicit server `safest_path` flag
   * wins wherever it appears; with no flag, the first option at the
   * lowest dose carries it — the least-inhalation path is always obvious. */
  const flaggedSafest = options.some((o) => o.safest_path === true);
  const minDose = Math.min(...options.map((o) => o.dose?.mid ?? Infinity));
  const isSafest = (o: V2Option) =>
    o.safest_path === true ||
    (!flaggedSafest && o.dose?.mid != null && o.dose.mid === minDose && minDose < Infinity);

  const chip = (
    <Pressable
      onPress={() => { tick(); if (onVehiclePress) onVehiclePress(); else setVehOpen(true); }}
      hitSlop={8}
      style={({ pressed }) => [s.vehChip, pressFx(pressed)]}
      accessibilityRole="button" accessibilityLabel={t("sidebarMyVehicle", lang)}>
      <Icon name={vehicleGlyph(veh?.cls ?? "car")} color={V2T.text2} size={15} />
      <Text {...DYNAMIC_TYPE} style={[s.vehChipTxt, { fontFamily: fam(lang, "reg") }]} numberOfLines={1}>
        {veh ? vehicleLabel(veh, lang) : t("vehicle_likeYours", lang)}
      </Text>
      {veh?.puc ? (
        <View style={s.pucBadge}>
          <Text {...DYNAMIC_TYPE} style={[s.pucBadgeTxt, { fontFamily: fam(lang, "semi") }]}>
            {t("puc_badge", lang)}
          </Text>
        </View>
      ) : null}
      <Icon name="chevron" color={V2T.text3} size={11} />
    </Pressable>
  );

  return (
    <View style={s.wrap}>
      <Sheet detent="half" onClose={onClose} lang={lang}>
        {loading ? (
          <View style={s.stateWrap}>
            <ActivityIndicator size="small" color={V2T.accent} />
            <Text {...DYNAMIC_TYPE} style={[s.stateSub, { fontFamily: fam(lang, "reg"), marginTop: 10 }]}>
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
              <Text {...DYNAMIC_TYPE} style={[s.stateTitle, { fontFamily: fam(lang, "med") }]}>
                {t("plan_outside_title", lang)}
              </Text>
              <Text {...DYNAMIC_TYPE} style={[s.stateSub, { fontFamily: fam(lang, "reg") }]} numberOfLines={4}>
                {t("plan_outside_body", lang)}
              </Text>
              <Pressable onPress={onClose} style={s.retryBtn} accessibilityRole="button"
                accessibilityLabel={t("plan_outside_cta", lang)}>
                <Text {...DYNAMIC_TYPE} style={[s.retryTxt, { fontFamily: fam(lang, "med") }]}>{t("plan_outside_cta", lang)}</Text>
              </Pressable>
            </View>
          ) : (
          <View style={s.stateWrap}>
            <View style={s.stateIcon}>
              <Icon name="info" color={V2T.accent} size={20} />
            </View>
            <Text {...DYNAMIC_TYPE} style={[s.stateTitle, { fontFamily: fam(lang, "med") }]}>
              {t(planError.kind === "network" ? "plan_failed" : "plan_failed_server", lang)}
            </Text>
            {planError.detail ? (
              <Text {...DYNAMIC_TYPE} style={[s.stateSub, { fontFamily: fam(lang, "reg") }]} numberOfLines={3}>
                {planError.detail}
              </Text>
            ) : null}
            {onRetry && (
              <Pressable onPress={onRetry} style={s.retryBtn} accessibilityRole="button"
                accessibilityLabel={t("plan_retry", lang)}>
                <Text {...DYNAMIC_TYPE} style={[s.retryTxt, { fontFamily: fam(lang, "med") }]}>{t("plan_retry", lang)}</Text>
              </Pressable>
            )}
          </View>
          )
        ) : options.length > 0 ? (
          <>
            <ScrollView style={s.scroll} contentContainerStyle={s.scrollContent}
              showsVerticalScrollIndicator={false}>
              {chip}
              {(() => {
                const missing = (degraded ?? []).filter((a) => {
                  const det = ARM_PRESENT[a];
                  return det ? !options.some(det) : true;   /* unknown arms flag honestly */
                });
                return missing.length ? (
                  <View style={s.degradedRow} accessibilityLiveRegion="polite">
                    <Icon name="info" color={V2T.text3} size={13} />
                    <Text {...DYNAMIC_TYPE} style={[s.legendTxt, { fontFamily: fam(lang, "reg"), marginLeft: 8, flexShrink: 1 }]}>
                      {missing.map((a) => t(ARM_KEY[a] ?? "degradedGeneric", lang)).join(" · ")}
                    </Text>
                  </View>
                ) : null;
              })()}
              {refining && (
                <View style={s.refineRow} accessibilityLiveRegion="polite">
                  <ActivityIndicator size="small" color={V2T.accent} />
                  <Text {...DYNAMIC_TYPE} style={[s.legendTxt, { fontFamily: fam(lang, "reg"), marginLeft: 8, flexShrink: 1 }]}>
                    {t("compare_refining", lang)}
                  </Text>
                </View>
              )}
              {depart?.ug_saved_vs_now != null && depart.ug_saved_vs_now > 8 && (
                <Pressable onPress={() => { tap(); onRemind(); }} style={({ pressed }) => [s.departRow, pressFx(pressed)]}
                  accessibilityRole="button">
                  <Icon name={notified ? "bell" : "clock"} color={V2T.accent} size={16} filled={notified} />
                  <Text {...DYNAMIC_TYPE} style={[s.departTxt, { fontFamily: fam(lang, "med") }]}>
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
                  {/* a tapped column brightens + the caption quotes that
                      slot's dose — real reading, not decoration */}
                  <DepartGraph data={departCurve.slots}
                    bestHour={departCurve.best?.hour ?? 0} lang={lang}
                    onSelectHour={() => tick()} />
                </View>
              ) : null}
              {anyBars && (
                <View style={s.legend}>
                  <View style={s.legendItem}>
                    <Icon name="dust" color={V2T.text3} size={11} />
                    <Text {...DYNAMIC_TYPE} style={[s.legendTxt, { fontFamily: fam(lang, "reg") }]}>{t("compare_smokeIn", lang)}</Text>
                  </View>
                  <View style={s.legendItem}>
                    <Icon name="smoke" color={V2T.text3} size={11} />
                    <Text {...DYNAMIC_TYPE} style={[s.legendTxt, { fontFamily: fam(lang, "reg") }]}>{t("compare_smokeOut", lang)}</Text>
                  </View>
                </View>
              )}
              {options.map((o, i) => (
                <OptionCard
                  key={`${o.mode}-${i}`}
                  o={o} i={i}
                  selected={i === selected}
                  worstIn={worstIn} worstOut={worstOut}
                  minDose={minDose}
                  showYours={!!o.your_vehicle && veh != null}
                  open={detailIdx === i}
                  fieldAgeS={fieldAgeS}
                  showCig={showCig}
                  safest={isSafest(o)}
                  veh={veh}
                  lang={lang}
                  onSelect={onSelect}
                  onToggleDetail={toggleDetail}
                />
              ))}
              {/* transit rows have no fetched steps — the container must
                  not gate on `steps` or the board→alight line never shows */}
              {stepsOpen && (steps || sel?.stations) && (
                <View style={s.stepsList}>
                  {sel?.stations ? (
                    /* transit options carry {board, alight} stations —
                       the road-step list would describe walking legs as
                       generic maneuvers ("continue 18.8 km" for the ride
                       itself), which reads wrong; the station line is the
                       honest instruction. mode is "metro+walk"/"bus…" so
                       match on stations, not the mode string. */
                    <Text {...DYNAMIC_TYPE} style={[s.stepTxt, { fontFamily: fam(lang, "reg") }]}>
                      {t("boardMetro", lang, { a: sel.stations.board, b: sel.stations.alight })}
                      {sel.lines?.length ? `  ·  ${sel.lines.join(", ")}` : ""}
                    </Text>
                  ) : (steps ?? []).map((st, i) => (
                    <View key={i} style={s.stepRow}>
                      <View style={s.stepRail}>
                        <View style={s.stepDot} />
                        {i < (steps?.length ?? 0) - 1 && <View style={s.stepLine} />}
                      </View>
                      <Text {...DYNAMIC_TYPE} style={[s.stepTxt, { fontFamily: fam(lang, "reg") }]}>
                        {localizeStep(st, lang)}
                      </Text>
                      <Text {...DYNAMIC_TYPE} style={[s.stepDist, NUM, { fontFamily: famMono(lang, "reg") }]}>
                        {st.distance_m >= 1000 ? `${(st.distance_m / 1000).toFixed(1)} km` : `${Math.round(st.distance_m)} m`}
                      </Text>
                    </View>
                  ))}
                </View>
              )}
              {stepsOpen && sel && !isTransit(sel) && !steps && (
                <Text {...DYNAMIC_TYPE} style={[s.stepTxt, s.stepsEmpty, { fontFamily: fam(lang, "reg") }]}>
                  {t("roadModesOnly", lang)}
                </Text>
              )}
            </ScrollView>
            {sel && (
              <View style={s.footer}>
                <Pressable onPress={() => { tick(); onToggleSteps(); }}
                  style={({ pressed }) => [s.ghostBtn, stepsOpen && s.ghostBtnOn, pressFx(pressed)]}
                  accessibilityRole="button">
                  <Text {...DYNAMIC_TYPE} style={[s.ghostTxt, stepsOpen && s.ghostTxtOn, { fontFamily: fam(lang, "med") }]}>
                    {stepsOpen ? t("hideTurns", lang) : t("turnByTurn", lang)}
                  </Text>
                </Pressable>
                <Pressable onPress={() => { confirm(); onStart(); }}
                  style={({ pressed }) => [s.goBtn, pressed && { opacity: 0.85, transform: [{ scale: 0.98 }] }]}
                  accessibilityRole="button">
                  <Text {...DYNAMIC_TYPE} style={[s.goBtnTxt, { fontFamily: fam(lang, "semi") }]}>{t("start", lang)}</Text>
                </Pressable>
              </View>
            )}
          </>
        ) : (
          <View style={s.stateWrap}>
            <View style={s.stateIcon}>
              <Icon name="search" color={V2T.text3} size={20} />
            </View>
            <Text {...DYNAMIC_TYPE} style={[s.stateSub, { fontFamily: fam(lang, "reg") }]}>{t("noRoutes", lang)}</Text>
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
            /* same close-frame guard — re-plan lands a beat after the
               sheet's own unmount commit (virtualized-GPU SIGSEGV class) */
            setTimeout(() => onVehicleChange?.(p), 80);
          }}
          onClose={() => setVehOpen(false)}
        />
      )}
    </View>
  );
}

export const CompareSheet = React.memo(CompareSheetInner);

const s = StyleSheet.create({
  wrap: { position: "absolute", bottom: 0, left: 0, right: 0 },

  /* ---- list ---- */
  scroll: { flexShrink: 1, flexGrow: 0 },
  /* last row's (i) hitSlop extends 16 px below its bounds — without this
     clearance that strip lands inside the footer's hit zone and taps meant
     for "how we got this" fire Start instead (Android forensic find) */
  scrollContent: { paddingBottom: 22 },
  vehChip: {
    flexDirection: "row", alignItems: "center", gap: 6, alignSelf: "flex-start",
    marginHorizontal: 14, marginTop: 4, marginBottom: 2, minHeight: 34,
    paddingHorizontal: 11, paddingVertical: 6,
    backgroundColor: V2T.glassSoft, borderRadius: V2Radius.row,
    borderWidth: 1, borderColor: V2T.glassLine,
  },
  vehChipTxt: { fontSize: V2Type.label, color: V2T.text2, maxWidth: 220 },
  /* "PUC" badge — marks a profile carrying the pollution certificate */
  pucBadge: {
    borderRadius: V2Radius.row, paddingHorizontal: 5, paddingVertical: 1,
    backgroundColor: V2T.glassSel,
  },
  pucBadgeTxt: { fontSize: 9, color: V2T.accent, letterSpacing: 0.4 },
  departRow: {
    flexDirection: "row", alignItems: "center", gap: 8,
    marginHorizontal: 14, marginTop: 6, marginBottom: 2, minHeight: 44,
    paddingHorizontal: 12, paddingVertical: 9, borderRadius: V2Radius.row,
    backgroundColor: V2T.glassSel,
    borderWidth: 1, borderColor: V2T.accent,
  },
  departTxt: { fontSize: V2Type.label, color: V2T.accent, flex: 1 },
  refineRow: { flexDirection: "row", alignItems: "center", marginTop: 8, marginBottom: 2 },
  degradedRow: { flexDirection: "row", alignItems: "center", marginTop: 8, marginBottom: 2,
    paddingVertical: 5, paddingHorizontal: 10, borderRadius: V2Radius.row,
    backgroundColor: V2T.accentWash, borderWidth: StyleSheet.hairlineWidth, borderColor: V2T.hairline },
  legend: {
    flexDirection: "row", justifyContent: "flex-end", alignItems: "center",
    gap: 14, marginHorizontal: 28, marginTop: 7, marginBottom: 1,
  },
  legendItem: { flexDirection: "row", alignItems: "center", gap: 5 },
  legendTxt: { fontSize: V2Type.label, color: V2T.text3 },

  /* ---- option card — solid tile resting on the milk pane (the frost
     dissolved the row edges into noise; real cards carry a shadow) ---- */
  card: {
    ...V2Elev.card,
    marginHorizontal: 14, marginTop: 7, borderRadius: V2Radius.card,
    backgroundColor: V2T.surface, borderWidth: 1, borderColor: V2T.glassLine,
    overflow: "hidden",
  },
  cardSel: { borderColor: V2T.accent, borderWidth: 1.5, backgroundColor: V2T.accentWash },
  cardRow: {
    flexDirection: "row", alignItems: "center", gap: 12,
    paddingVertical: 12, paddingHorizontal: 14, minHeight: 64,
  },
  cardMid: { flex: 1 },
  cardTop: { flexDirection: "row", alignItems: "center", flexWrap: "wrap" },
  optLabel: { fontSize: V2Type.secondary, color: V2T.text, flexShrink: 1 },
  chip: {
    borderRadius: V2Radius.row, paddingHorizontal: 7, paddingVertical: 2,
    marginLeft: 8,
  },
  chipAccent: { backgroundColor: V2T.glassSel },
  chipPlain: { backgroundColor: V2T.glassSoft, borderWidth: 1, borderColor: V2T.glassLine },
  chipTxt: { fontSize: V2Type.label },
  chipTxtAccent: { color: V2T.accent },
  chipTxtPlain: { color: V2T.text2 },
  optMeta: { fontSize: V2Type.label, color: V2T.text3, marginTop: 2 },
  optReason: { fontSize: V2Type.label, color: V2T.text3, marginTop: 3 },
  optCoverage: { fontSize: V2Type.label, color: V2T.breath2, marginTop: 3 },
  cardRight: { alignItems: "flex-end" },
  /* dose hero — larger than everything else on the row; ETA is the
     muted sub under it (was the other way around: "7 min" outsized the
     number the whole app exists to report) */
  optEta: { fontSize: V2Type.label, color: V2T.text2, marginTop: 4 },
  optEtaUnit: { fontSize: V2Type.micro, color: V2T.text3 },
  optDose: { fontSize: 26, marginTop: 1, includeFontPadding: false },
  optDoseSub: { fontSize: V2Type.micro, color: V2T.text3, marginTop: 1 },
  optDoseUnit: { fontSize: V2Type.micro, color: V2T.text3 },
  optDoseNA: { color: V2T.text3 },
  optGap: { fontSize: V2Type.micro, color: V2T.breath2 },
  barsRow: { flexDirection: "row", alignItems: "center", marginTop: 6, gap: 10 },
  bars: { flexDirection: "row", alignItems: "center", gap: 8 },
  barGroup: { flexDirection: "row", alignItems: "center", gap: 4 },
  track: {
    width: 30, height: 5, borderRadius: 2.5, backgroundColor: "rgba(20,24,31,0.08)",
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
    minHeight: 44, justifyContent: "center", borderRadius: V2Radius.card,
    paddingHorizontal: 16, borderWidth: 1, borderColor: V2T.glassLine,
    backgroundColor: V2T.glassSoft,
  },
  ghostBtnOn: { borderColor: V2T.accent, backgroundColor: V2T.glassSel },
  ghostTxt: { fontSize: V2Type.secondary, color: V2T.text2 },
  ghostTxtOn: { color: V2T.accent },
  goBtn: {
    ...V2Elev.float,
    minHeight: 44, justifyContent: "center", alignItems: "center",
    backgroundColor: V2T.accent, borderRadius: V2Radius.card, paddingHorizontal: 34,
  },
  goBtnTxt: { fontSize: V2Type.body, color: V2T.bg },   // light on the accent fill (V2T.bg ≈7:1 on accent)

  /* ---- states ---- */
  stateWrap: { paddingVertical: 24, paddingHorizontal: 24, alignItems: "center" },
  stateIcon: {
    width: 52, height: 52, borderRadius: 26, marginBottom: 10,
    backgroundColor: V2T.surface, borderWidth: 1, borderColor: V2T.glassLine,
    alignItems: "center", justifyContent: "center",
  },
  stateTitle: { fontSize: V2Type.secondary, color: V2T.text, textAlign: "center" },
  stateSub: { fontSize: V2Type.label, color: V2T.text3, textAlign: "center", marginTop: 6 },
  retryBtn: {
    marginTop: 14, minHeight: 44, justifyContent: "center",
    backgroundColor: V2T.accent, borderRadius: V2Radius.card,
    paddingHorizontal: 26, paddingVertical: 12,
  },
  retryTxt: { fontSize: V2Type.secondary, color: V2T.bg }, // accent fill → light text
});
