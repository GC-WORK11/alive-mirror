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
import { ActivityIndicator, Animated, Linking, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { NUM, V2Elev, V2Radius, V2T, V2Type, bandColor, doseColor, fam, famMono, famMonoText } from "../../theme";
import { DYNAMIC_TYPE, useReduceMotion } from "../../a11y";
import { Icon, vehicleGlyph, type Glyph } from "../../icons";
import { CountUp, Sheet } from "../../ui";
import { PressSpring } from "../PressSpring";
import { approx, clockLabel, doseUgRound, modeLabel, t, type Lang, type StringKey } from "../../i18n/strings";

import { departSavedPct, type DepartCurve } from "../../api/depart";
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
import { bump, mark } from "../../perf";

/* arrival wall-time — the app's one 12h clock convention */
const arrivalLabel = (durationMin: number, lang: Lang) =>
  clockLabel(Date.now() + durationMin * 60000, lang);

/* naive-UTC `start` → device-local clock — every other clock in the app
   (arrival, ETA chip) renders device-local too, so the strip stays in the
   same frame on a non-IST phone (IST users see identical labels). The old
   +5.5h shift forced IST and hardcoded ":30" minutes. */
const hourLabel = (iso: string | null, ahead: number, lang: Lang) => {
  if (iso) {
    const d = new Date(iso.endsWith("Z") ? iso : iso + "Z");
    if (!isNaN(d.getTime())) {
      const clk = clockLabel(d, lang);
      return `${d.getDate() !== new Date().getDate() ? t("departTomorrow", lang) + " " : ""}${clk}`;
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

export const reasonTxt = (n: string, lang: Lang): string => {
  const m = n.match(SLOWER_RE);
  const base = m ? n.slice(0, -m[0].length) : n;
  const key = REASON_KEY[base];
  const out = key ? t(key, lang) : base;
  return m ? out + t("reason_slowerSuffix", lang, { m: m[1] }) : out;
};

const bandTxt = (b: Band | null | undefined, unit: string, dp = 2) => {
  if (!b || (b.lo == null && b.hi == null)) return null;
  const r = (v: number | null) => (v == null ? null : Number(v.toFixed(dp)));
  const lo = r(b.lo ?? b.mid), hi = r(b.hi ?? b.mid);
  if (lo == null && hi == null) return null;
  /* a band that collapses at display precision prints one number —
     "0–0" and "1.2–1.2" are slop, not spans (audit #21) */
  if (lo === hi || lo == null || hi == null) return `${lo ?? hi}${unit ? ` ${unit}` : ""}`;
  return `${lo}–${hi}${unit ? ` ${unit}` : ""}`;
};

/** true when the whole band is zero at display precision — a "0–0 kg CO2"
 *  row on walk/cycle says nothing the non_exhaust note doesn't already */
const zeroBand = (b: Band | null | undefined, dp: number) =>
  !!b &&
  Number((b.lo ?? b.mid ?? 0).toFixed(dp)) === 0 &&
  Number((b.hi ?? b.mid ?? 0).toFixed(dp)) === 0;

/** in-bar ramp: warm, brighter = heavier dose (absence of colour = light) */
const inTone = (f: number) => (f > 0.66 ? V2T.breath3 : f > 0.33 ? V2T.breath2 : V2T.breath1);

/** One micro-track: fill = this option vs the trip's worst. A dimmed
 *  empty groove means "no data", distinct from "zero". */
function Track({ frac }: { frac: number | null }) {
  if (frac == null) return <View style={[s.track, s.trackNA]} />;
  const f = Math.max(0, Math.min(1, frac));
  return (
    <View style={s.track}>
      <View style={[s.trackFill, { flex: f, backgroundColor: inTone(f) }]} />
      <View style={{ flex: Math.max(0, 1 - f) }} />
    </View>
  );
}

/** The one bar per card — smoke inhaled vs the trip's worst option. The
 *  two-track in/out pair read as "complex graphs nobody understands"
 *  (owner); one track + the felt gap line carries the comparison, and
 *  the exhaust numbers stay honest inside "how we got this". */
function DoseBar({ o, worstIn, lang }: {
  o: V2Option; worstIn: number; lang: Lang;
}) {
  const inFrac = o.dose?.mid != null && worstIn > 0 ? o.dose.mid / worstIn : null;
  return (
    <View style={s.bars}>
      <View style={s.barGroup} accessible accessibilityLabel={t("compare_smokeIn", lang)}>
        <Icon name="dust" color={V2T.text3} size={11} />
        <Track frac={inFrac} />
      </View>
    </View>
  );
}

/** short mode word for the felt comparison line — "metro", "auto",
 *  "on foot". Falls back to the full label for unfamiliar modes. */
const MODE_WORD: Record<string, StringKey> = {
  car: "vehicle_car", car_open: "vehicle_car", bike: "vehicle_bike",
  auto: "vehicle_auto", bus: "vehicle_bus", metro: "vehicle_metro",
  "metro+walk": "vehicle_metro", cycle: "vehicle_cycle", walk: "vehicle_walk",
};
const modeWord = (o: V2Option, lang: Lang): string => {
  const k = MODE_WORD[o.mode];
  return k ? t(k, lang) : modeLabel(o.mode, o.label, lang);
};

/** The day ribbon — replaces the candlestick depart graph: one flat cell
 *  per hour tinted by that hour's own field band (band colors = data,
 *  design law), the lightest hour under-bracketed in accent. One glance —
 *  no axis, no bars to decode. Colours are the served values, never a
 *  forecast-invented hue; a slot with no reading paints a neutral cell.
 *  The caption quotes the lightest hour's real dose. */
function DayStrip({ data, bestHour, lang }: {
  data: DepartCurve["slots"]; bestHour: number; lang: Lang;
}) {
  const rows = data
    .filter((d) => Number.isFinite(d.dose_mid))
    .slice()
    .sort((a, b) => a.hour - b.hour);
  if (!rows.length) return null;
  const last = rows[rows.length - 1];
  const best = rows.find((d) => d.hour === bestHour) ?? null;
  return (
    <View
      accessible
      accessibilityLabel={
        t("depart_airByHour", lang)
        + (best ? `. ${t("depart_bestLine", lang, {
            time: hourLabel(best.start, best.hour, lang), n: doseUgRound(best.dose_mid),
          })}` : "")
      }>
      <Text {...DYNAMIC_TYPE} style={[s.stripCap, { fontFamily: fam(lang, "reg") }]}>
        {t("depart_airByHour", lang)}
      </Text>
      <View style={s.strip} importantForAccessibility="no-hide-descendants">
        {rows.map((d) => (
          <View key={d.hour} style={s.stripCell}>
            <View style={[s.stripFill, {
              backgroundColor: bandColor(d.avg_conc_ugm3 ?? d.dose_mid) ?? V2T.surface3,
            }]} />
            <View style={[s.stripTick, d.hour === bestHour ? s.stripTickOn : null]} />
          </View>
        ))}
      </View>
      <View style={s.stripAxis} importantForAccessibility="no-hide-descendants">
        <Text {...DYNAMIC_TYPE} style={[s.stripAxisTxt, { fontFamily: fam(lang, "reg") }]}>
          {t("departNow", lang)}
        </Text>
        <Text {...DYNAMIC_TYPE} style={[s.stripAxisTxt, { fontFamily: famMonoText(lang, "reg") }]}>
          {`+${last.hour}h`}
        </Text>
      </View>
      {best ? (
        <Text {...DYNAMIC_TYPE} style={[s.stripBestTxt, { fontFamily: fam(lang, "reg") }]}
          numberOfLines={1}>
          {t("depart_bestLine", lang, {
            time: hourLabel(best.start, best.hour, lang), n: doseUgRound(best.dose_mid),
          })}
        </Text>
      ) : null}
    </View>
  );
}

/** Tag / recommended chip — server tags fill accent, the fallback "our
 *  pick" stays neutral so the stronger claim reads stronger. `glyph`
 *  puts a small icon beside the text (the least-smoky leaf). */
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

/** The "estimated for a {year fuel class} (…)" provenance line — the
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
  /* hide meaningless zero-rows: a non-motorized option's exhaust is all
     zero bands, and printing "0–0 kg CO2 · 0–0 g PM2.5" was audit slop;
     the non_exhaust note underneath still carries the honest "zero" */
  const emit = [
    zeroBand(e.co2_kg, 1) ? null : bandTxt(e.co2_kg, "kg CO2", 1),
    zeroBand(e.pm25_g, 2) ? null : bandTxt(e.pm25_g, "g PM2.5", 2),
  ].filter(Boolean).join("  ·  ");
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
function OptionCard({ o, i, selected, worstIn, minDose, lightestWord, showYours, open,
  fieldAgeS, showCig, safest, veh, lang, onSelect, onToggleDetail }: {
  o: V2Option; i: number; selected: boolean; worstIn: number;
  /** the lightest dose in the set — the gap line is computed against it,
      and lightestWord names that option ("metro") so the gap reads like
      a sentence instead of a chip of numbers */
  minDose: number; lightestWord: string;
  showYours: boolean; open: boolean; fieldAgeS?: number | null;
  showCig: boolean; safest: boolean; veh: VehicleProfile | null; lang: Lang;
  onSelect: (i: number) => void; onToggleDetail: (i: number) => void;
}) {
  /* selection crossfades in — the card never snaps accent-on. The overlay
     carries the accentWash wash only; the glyph well's accentTint is the
     edge colour — nothing border-shaped swaps, so deselecting can't jump
     a border out either.
     spring on opacity: the pick "arrives" rather than flipping (doc 20 §6) */
  const reduce = useReduceMotion();
  const [selV] = useState(() => new Animated.Value(selected ? 1 : 0));
  useEffect(() => {
    if (reduce) { selV.setValue(selected ? 1 : 0); return; }
    Animated.spring(selV, {
      toValue: selected ? 1 : 0, damping: 18, stiffness: 260, mass: 0.7,
      /* JS driver — this spring also fires on auto-select when the plan
         options land, i.e. inside the mount window; keep it off the
         native anim graph like every other in-sheet spring. */
      useNativeDriver: false,
    }).start();
  }, [selected, selV, reduce]);
  const d = o.dose;
  /* the honest band — a missing end reads as "{lo}+"/"up to {hi}",
     never a bare "?" in the range; and a two-ended span only prints
     when the rounded ends actually differ — "≈0 µg (0–0)" read as a
     bug. */
  const bandLoR = d?.lo != null ? Math.round(d.lo) : null;
  const bandHiR = d?.hi != null ? Math.round(d.hi) : null;
  const band = d && (d.lo != null || d.hi != null) && (d.lo !== d.mid || d.hi !== d.mid)
    ? d.lo != null && d.hi != null
      ? (bandLoR !== bandHiR ? `${bandLoR}–${bandHiR}` : null)
      : d.lo != null
        ? `${bandLoR}+`
        : t("bandUpTo", lang, { n: bandHiR ?? 0 })
    : null;
  const doseCol = d?.avg_conc_ugm3 != null ? doseColor(d.avg_conc_ugm3) : V2T.text;
  /* the felt gap line — the sheet's emotional payload. "~2.4× more
     inhaled than metro" is the number that makes a person pick the
     metro; below 2× the honest µg gap reads better ("+14 µg more than
     metro"). Invisible on the lightest card itself. */
  const doseGap = d?.mid != null && minDose < Infinity && d.mid - minDose >= 0.5
    ? Math.round(d.mid - minDose) : null;
  const felt = doseGap != null && d?.mid != null
    ? (minDose > 0 && d.mid / minDose >= 2
        ? t("compare_feltMore", lang, {
            x: (d.mid / minDose).toFixed(1).replace(/\.0$/, ""), m: lightestWord,
          })
        : t("compare_moreVs", lang, { n: doseGap, m: lightestWord }))
    : null;
  const meta = (o.distance_km != null ? `${o.distance_km} ${t("unitsKm", lang)} · ` : "")
    + t("arriveAt", lang, { t: arrivalLabel(o.duration_min, lang) })
    + (o.stations ? ` · ${o.stations.board}→${o.stations.alight}` : "");
  const tag = o.tag ? (TAG_KEY[o.tag.toLowerCase()] ? t(TAG_KEY[o.tag.toLowerCase()], lang) : o.tag) : null;
  /* the mode label carries a wire suffix (" · least-smoke alt 2",
     " · your usual") that a single-line flexShrink truncated mid-word to
     "· y…" — split it into a dimmed qualifier run and let the line wrap
     to two: full qualifier, never a meaningless fragment */
  const lbl = modeLabel(o.mode, o.label, lang);
  const lblCut = lbl.lastIndexOf(" · ");
  const lblBase = lblCut > 0 ? lbl.slice(0, lblCut) : lbl;
  const lblQual = (lblCut > 0 ? lbl.slice(lblCut) : "")
    + (showYours ? ` · ${t("compare_yours", lang)}` : "");
  return (
    <PressSpring style={s.card}>
      <Animated.View pointerEvents="none"
        style={[StyleSheet.absoluteFill, s.selFill, { opacity: selV }]} />
      <Pressable
        onPress={() => { tick(); onSelect(i); }}
        onLongPress={() => { tick(); onToggleDetail(i); }}
        delayLongPress={400}
        accessibilityRole="button"
        accessibilityState={{ selected }}
        style={s.cardRow}>
        {/* the mode glyph is neutral ink; only the selected option takes
            the forest accent */}
        <View style={[s.modeWell, {
          backgroundColor: selected ? V2T.accentTint : "transparent",
        }]}>
          <Icon name={vehicleGlyph(o.mode)}
            color={selected ? V2T.accent : V2T.text2}
            size={24} filled />
        </View>
        <View style={s.cardMid}>
          <View style={s.cardTop}>
            <Text {...DYNAMIC_TYPE} style={[s.optLabel, { fontFamily: fam(lang, "med") }]} numberOfLines={2}>
              {lblBase}
              {lblQual ? (
                <Text {...DYNAMIC_TYPE} style={[s.optQual, { fontFamily: fam(lang, "reg") }]}>{lblQual}</Text>
              ) : null}
            </Text>
            {/* the least-inhalation route leads: "least smoky" (the
                server's safest_path flag, or the dose-min option when
                no flag was sent) sits ahead of the server tag, which is
                demoted to plain while the headline chip is up */}
            {safest ? <Chip text={t("compare_safest", lang)} accent glyph="leaf" lang={lang} /> : null}
            {tag ? <Chip text={tag} accent={!safest} lang={lang} />
              : o.recommended && !safest ? <Chip text={t("compare_pick", lang)} lang={lang} /> : null}
          </View>
          <Text {...DYNAMIC_TYPE} style={[s.optMeta, { fontFamily: fam(lang, "reg") }]}
            numberOfLines={1} adjustsFontSizeToFit minimumFontScale={0.75}>{meta}</Text>
          {felt ? (
            <Text {...DYNAMIC_TYPE} style={[s.optFelt, { fontFamily: fam(lang, "med") }]}
              numberOfLines={2}>{felt}</Text>
          ) : null}
          {o.reason_line ? (
            /* Devanagari runs longer per sentence — 3 lines keeps the
               benefit line whole instead of truncating "—…" (audit #5) */
            <Text {...DYNAMIC_TYPE} style={[s.optReason, { fontFamily: fam(lang, "reg") }]} numberOfLines={3}>{reasonTxt(o.reason_line, lang)}</Text>
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
              </Text>
            </>
          ) : (
            <Text {...DYNAMIC_TYPE} style={[s.optDose, s.optDoseNA, { fontFamily: fam(lang, "med") }]} numberOfLines={1}>{t("compare_doseNA", lang)}</Text>
          )}
          <Text {...DYNAMIC_TYPE} style={[s.optEta, NUM, { fontFamily: famMonoText(lang, "reg") }]} numberOfLines={1}>
            {Math.round(o.duration_min)}<Text {...DYNAMIC_TYPE} style={s.optEtaUnit}> {t("minUnit", lang)}</Text>
          </Text>
          <View style={s.barsRow}>
            <DoseBar o={o} worstIn={worstIn} lang={lang} />
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
    </PressSpring>
  );
}

function CompareSheetInner({
  options, selected, onSelect, depart, departCurve, notified, onRemind,
  pingDenied = false,
  pingQuiet = false,
  remindEnabled = true,
  loading, steps, stepsOpen, onToggleSteps, onStart, onClose, lang,
  planError = null, onRetry, vehicle, onVehiclePress, onVehicleChange, fieldAgeS,
  showCig = false, refining = false, degraded,
}: {
  options: V2Option[]; selected: number; onSelect: (i: number) => void;
  depart: Depart; notified: boolean; onRemind: () => void;
  /** OS denied notification perms — the bell's row turns into the honest
      "notifications are off" line instead of a dead tap (lifecycle-drive) */
  pingDenied?: boolean;
  /** quiet-hours refusal — the best window sits too deep inside 22→7 to
      ping honestly; the row says why instead of a silent dead tap */
  pingQuiet?: boolean;
  /** settings.remind — the master switch; off hides the offer row so a
      disabled preference can't ghost-offer a ping (App.tsx wiring) */
  remindEnabled?: boolean;
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
  /* perf: options landing while mounted = the chooser's first real rows —
     pair with plan:req/plan:resp for request→chooser latency. */
  useEffect(() => { if (options.length > 0) mark("plan.chooser"); }, [options]);
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
  const anyBars = worstIn > 0;
  const toggleDetail = (i: number) => setDetailIdx((cur) => (cur === i ? null : i));

  /* The "least smoky" headline: an explicit server `safest_path` flag
   * wins wherever it appears; with no flag, the first option at the
   * lowest dose carries it — the least-inhalation path is always obvious. */
  const flaggedSafest = options.some((o) => o.safest_path === true);
  const minDose = Math.min(...options.map((o) => o.dose?.mid ?? Infinity));
  const lightestOpt = minDose < Infinity
    ? (options.find((o) => o.dose?.mid != null && o.dose.mid === minDose) ?? null)
    : null;
  const isSafest = (o: V2Option) =>
    o.safest_path === true ||
    (!flaggedSafest && o.dose?.mid != null && o.dose.mid === minDose && minDose < Infinity);

  /* the leave-later saving is a served PERCENT — pct_less_vs_now is the
     honest key (ug_saved_vs_now the legacy alias); read it verbatim via
     departSavedPct, never as µg (the >8 gate stays on the raw value). */
  const departSaved = departSavedPct(depart);

  const chip = (
    <PressSpring style={{ alignSelf: "flex-start" }}>
    <Pressable
      onPress={() => { tick(); if (onVehiclePress) onVehiclePress(); else setVehOpen(true); }}
      hitSlop={8}
      style={s.vehChip}
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
    </PressSpring>
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
                <Icon name="pin" color={V2T.text2} size={20} />
              </View>
              <Text {...DYNAMIC_TYPE} style={[s.stateTitle, { fontFamily: fam(lang, "med") }]}>
                {t("plan_outside_title", lang)}
              </Text>
              <Text {...DYNAMIC_TYPE} style={[s.stateSub, { fontFamily: fam(lang, "reg") }]} numberOfLines={4}>
                {t("plan_outside_body", lang)}
              </Text>
              <PressSpring><Pressable onPress={onClose} style={s.retryBtn} accessibilityRole="button"
                accessibilityLabel={t("plan_outside_cta", lang)}>
                <Text {...DYNAMIC_TYPE} style={[s.retryTxt, { fontFamily: fam(lang, "med") }]}>{t("plan_outside_cta", lang)}</Text>
              </Pressable></PressSpring>
            </View>
          ) : (
          <View style={s.stateWrap}>
            <View style={s.stateIcon}>
              <Icon name="info" color={V2T.text2} size={20} />
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
              <PressSpring><Pressable onPress={onRetry} style={s.retryBtn} accessibilityRole="button"
                accessibilityLabel={t("plan_retry", lang)}>
                <Text {...DYNAMIC_TYPE} style={[s.retryTxt, { fontFamily: fam(lang, "med") }]}>{t("plan_retry", lang)}</Text>
              </Pressable></PressSpring>
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
              {/* a trip measured in metres doesn't have a 'when to
                  leave' — under ~500 m the depart surface would read
                  like the choice matters (audit #23's 50 m pin) */}
              {(() => {
                const km = sel?.distance_km;
                return km == null || km >= 0.5;
              })() && (
                <>
              {remindEnabled && depart && departSaved != null && departSaved > 8 && (
                <PressSpring><Pressable
                  onPress={() => {
                    tap();
                    /* denied perms can't arm the ping — the row used to
                       dead-tap; now it says so and offers the switch */
                    if (pingDenied) Linking.openSettings().catch(() => {});
                    /* quiet-hours refusal is terminal — the line already
                       carries the reason; tapping again would re-lie */
                    else if (!pingQuiet) onRemind();
                  }} style={s.departRow}
                  accessibilityRole="button">
                  <Icon name={notified ? "bell" : "clock"} color={V2T.text2} size={16} filled={notified} />
                  <Text {...DYNAMIC_TYPE} style={[s.departTxt, { fontFamily: fam(lang, "med") }]}>
                    {pingDenied
                      ? t("notifDenied", lang)
                      : pingQuiet
                      ? t("notifTooLate", lang)
                      : notified
                      ? t("wellPing", lang)
                      : t("leaveAtBreatheLess", lang, {
                          time: hourLabel(depart.best.start, depart.best.hours_ahead, lang),
                          n: Math.round(departSaved),
                        })}
                  </Text>
                </Pressable></PressSpring>
              )}
              {departCurve?.slots?.length ? (
                <View style={{ marginTop: 10, marginBottom: 4 }}>
                  <DayStrip data={departCurve.slots}
                    bestHour={departCurve.best?.hour ?? 0} lang={lang} />
                </View>
              ) : null}
                </>
              )}
              {anyBars && (
                <View style={s.legend}>
                  <View style={s.legendItem}>
                    <Icon name="dust" color={V2T.text3} size={11} />
                    <Text {...DYNAMIC_TYPE} style={[s.legendTxt, { fontFamily: fam(lang, "reg") }]}>{t("compare_smokeIn", lang)}</Text>
                  </View>
                </View>
              )}
              {options.map((o, i) => (
                <OptionCard
                  key={`${o.mode}-${i}`}
                  o={o} i={i}
                  selected={i === selected}
                  worstIn={worstIn}
                  minDose={minDose}
                  lightestWord={lightestOpt ? modeWord(lightestOpt, lang) : ""}
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
                        {st.distance_m >= 1000 ? `${(st.distance_m / 1000).toFixed(1)} ${t("unitsKm", lang)}` : `${Math.round(st.distance_m)} ${t("unitsM", lang)}`}
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
                <PressSpring><Pressable onPress={() => { tick(); onToggleSteps(); }}
                  style={[s.ghostBtn, stepsOpen && s.ghostBtnOn]}
                  accessibilityRole="button">
                  <Text {...DYNAMIC_TYPE} style={[s.ghostTxt, stepsOpen && s.ghostTxtOn, { fontFamily: fam(lang, "med") }]}>
                    {stepsOpen ? t("hideTurns", lang) : t("turnByTurn", lang)}
                  </Text>
                </Pressable></PressSpring>
                <PressSpring><Pressable onPress={() => { confirm(); onStart(); }}
                  style={s.goBtn}
                  accessibilityRole="button">
                  <Text {...DYNAMIC_TYPE} style={[s.goBtnTxt, { fontFamily: fam(lang, "semi") }]}>{t("start", lang)}</Text>
                </Pressable></PressSpring>
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
    paddingHorizontal: 12, paddingVertical: 7,
    backgroundColor: V2T.surface2, borderRadius: V2Radius.pill,
  },
  vehChipTxt: { fontSize: V2Type.label, color: V2T.text2, maxWidth: 220 },
  /* "PUC" badge — marks a profile carrying the pollution certificate */
  pucBadge: {
    borderRadius: V2Radius.row, paddingHorizontal: 5, paddingVertical: 1,
    backgroundColor: V2T.glassSel,
  },
  pucBadgeTxt: { fontSize: V2Type.micro, color: V2T.accent, letterSpacing: 0.4 },
  departRow: {
    flexDirection: "row", alignItems: "center", gap: 8,
    marginHorizontal: 14, marginTop: 8, marginBottom: 2, minHeight: 46,
    paddingHorizontal: 13, paddingVertical: 10, borderRadius: V2Radius.row,
    backgroundColor: V2T.accentWash,
  },
  departTxt: { fontSize: V2Type.label, color: V2T.accentInk, flex: 1 },
  refineRow: { flexDirection: "row", alignItems: "center", marginTop: 8, marginBottom: 2 },
  degradedRow: { flexDirection: "row", alignItems: "center", marginTop: 8, marginBottom: 2,
    paddingVertical: 5, paddingHorizontal: 10, borderRadius: V2Radius.row,
    backgroundColor: V2T.accentWash },
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
    marginHorizontal: 14, marginTop: 8, borderRadius: V2Radius.card,
    backgroundColor: V2T.surface,
    overflow: "hidden",
  },
  /* the animated selected paint (was `cardSel` — same colours, now a
     crossfading overlay so picking a card lands instead of snapping) */
  selFill: {
    borderRadius: V2Radius.card - 1,
    backgroundColor: V2T.accentWash,
  },
  cardRow: {
    flexDirection: "row", alignItems: "center", gap: 12,
    paddingVertical: 13, paddingHorizontal: 14, minHeight: 68,
  },
  modeWell: {
    width: 44, height: 44, borderRadius: 15,
    alignItems: "center", justifyContent: "center",
  },
  cardMid: { flex: 1 },
  cardTop: { flexDirection: "row", alignItems: "center", flexWrap: "wrap" },
  optLabel: { fontSize: V2Type.secondary, color: V2T.text, flexShrink: 1 },
  optQual: { fontSize: V2Type.label, color: V2T.text3 },
  chip: {
    borderRadius: V2Radius.row, paddingHorizontal: 7, paddingVertical: 2,
    marginLeft: 8,
  },
  chipAccent: { backgroundColor: V2T.accentWash },
  chipPlain: { backgroundColor: V2T.surface2 },
  chipTxt: { fontSize: V2Type.label },
  chipTxtAccent: { color: V2T.accentInk },
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
  optGap: { fontSize: V2Type.label, color: V2T.breath2 },
  optFelt: { fontSize: V2Type.label, color: V2T.breath2, marginTop: 2 },
  /* day strip — flat band-tinted cells, the lightest hour under-bracketed */
  stripWrap: { marginTop: 2 },
  stripCap: { fontSize: V2Type.label, color: V2T.text3, marginBottom: 6 },
  strip: { flexDirection: "row", gap: 1.5 },
  stripCell: { flex: 1 },
  stripFill: { height: 10, borderRadius: 2 },
  stripTick: { height: 2.5, borderRadius: 1.5, marginTop: 2, backgroundColor: "transparent" },
  stripTickOn: { backgroundColor: V2T.accent },
  stripAxis: {
    flexDirection: "row", justifyContent: "space-between", marginTop: 5,
  },
  stripAxisTxt: { fontSize: V2Type.micro, color: V2T.text3 },
  stripBestTxt: { fontSize: V2Type.label, color: V2T.accentInk, marginTop: 6 },
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
    minHeight: 44, justifyContent: "center", borderRadius: V2Radius.pill,
    paddingHorizontal: 16,
    backgroundColor: V2T.surface,
  },
  ghostBtnOn: { backgroundColor: V2T.accentWash },
  ghostTxt: { fontSize: V2Type.secondary, color: V2T.text2 },
  ghostTxtOn: { color: V2T.accent },
  goBtn: {
    ...V2Elev.float,
    minHeight: 48, justifyContent: "center", alignItems: "center",
    backgroundColor: V2T.text, borderRadius: V2Radius.pill, paddingHorizontal: 36,
  },
  goBtnTxt: { fontSize: V2Type.body, color: V2T.bg },   // light on the accent fill (V2T.bg ≈7:1 on accent)

  /* ---- states ---- */
  stateWrap: { paddingVertical: 24, paddingHorizontal: 24, alignItems: "center" },
  stateIcon: {
    width: 52, height: 52, borderRadius: 26, marginBottom: 10,
    backgroundColor: V2T.surface2,
    alignItems: "center", justifyContent: "center",
  },
  stateTitle: { fontSize: V2Type.secondary, color: V2T.text, textAlign: "center" },
  stateSub: { fontSize: V2Type.label, color: V2T.text3, textAlign: "center", marginTop: 6 },
  retryBtn: {
    marginTop: 14, minHeight: 44, justifyContent: "center",
    backgroundColor: V2T.text, borderRadius: V2Radius.card,
    paddingHorizontal: 26, paddingVertical: 12,
  },
  retryTxt: { fontSize: V2Type.secondary, color: V2T.bg }, // accent fill → light text
});
