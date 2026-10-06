/** HOME — the lifestyle dosimeter's resting surface (docs/plan/design-refs).
 *
 *  The app opens on "your day" — what Delhi has done to your lungs so far
 *  and the one decision that changes the rest of it. The map+journey is a
 *  feature reached through the "where to?" bar; on the idle map the DayPeek
 *  card is the door back here.
 *
 *  What's on it, top to bottom:
 *   0. the header — wordmark + IST clock line + menu (sidebar).
 *   1. the hero — ≈N µg breathed (Fraunces display, dose-coloured) + the
 *      dose gauge ring filling toward the day's budget (Oura/Apple ring
 *      pattern — WHOOP's one-score compression, design-refs §3). Skeleton
 *      blocks morph to content once the disk read lands.
 *   2. "where to?" — the travel verb: one search-shaped bar that opens the
 *      journey (Uber homescreen pattern, design-refs §2).
 *   3. the move — the day's decision at felt scale (serif), with the
 *      field's own h-series sparkline + heavy/clean windows as evidence
 *      (GET /v2/day, grid fallback). A flat day says it's flat.
 *   4. your day — the on-device reconstruction (daylog.ts): the 24-slot
 *      hour arc, top accumulators. Covered spans only.
 *   5. the days ahead — /v2/outlook's own fold, ≤5 cells, ghosted past the
 *      live anchor's reach; a dead endpoint hides the card.
 *   6. the symptom lens — breath/eyes/energy single-tap check-in, stored
 *      on this phone only.
 *   7. quiet links — the air map, Delhi today, your trips.
 *   8. your budget — quiet profile ceiling, honest over/under flag.
 *
 *  Copy rule for the whole surface: "same life, cheaper for lungs" — a card
 *  that can't name a cheaper window/mode shows the number plainly, never a
 *  restriction.
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
import { StatusBar } from "expo-status-bar";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import Svg, { Circle, Path } from "react-native-svg";
import {
  NUM,
  V2Elev,
  V2Radius,
  V2T,
  V2Tint,
  V2Type,
  bandColor,
  bandColorIdx,
  bandEdgeIdx,
  bandIdx,
  bandInkIdx,
  bandWashDeepIdx,
  bandWashIdx,
  bandWashMidIdx,
  fam,
  famMono,
  famMonoText,
  famSerif,
} from "../theme";
import { approx, doseUgRound, t, type Lang, type StringKey } from "../i18n/strings";
import { CountUp, FadeIn, Quiet, pressFx } from "../ui";
import { Icon, type Glyph } from "../icons";
import { freshnessTone } from "../components/FreshnessChip";
import { DYNAMIC_TYPE, useReduceMotion } from "../a11y";
import { tap, tick } from "../haptics";
import { inNcr } from "../components/shell/net";
import {
  allSamples,
  dayKey,
  getCheckins,
  reconstructDay,
  symptomLens,
  THIN_SAMPLE_MIN,
  type Checkin,
  type DayReconstruction,
  type LensVerdict,
} from "../store/daylog";
import type { Trip } from "../store/ledger";
import {
  fetchDayCurve,
  morningAnswers,
  type DayCurve,
} from "../api/dayfield";
import {
  CLEAN_UG,
  bandIdxForName,
  fetchOutlook,
  type Outlook,
} from "../api/outlook";
import { PROFILE_BUDGET_UG, type ShellSettings } from "../components/shell/settings";
import { bump, jank } from "../perf";

/* ---------------- the hook: one assemble of the day's data --------------- */

export type DayData = {
  /** today's reconstruction — never null once disk is read */
  rec: DayReconstruction;
  /** last 7 local days' totals (oldest→today) for the week dots */
  week: { day: string; ug: number }[];
  /** the field's hourly curve at the user's cell (null = no fetch yet) */
  curve: DayCurve | null;
  /** true while position is outside the served window */
  outside: boolean;
  lens: LensVerdict;
  checkin: Checkin | null;
  /** seconds since the curve was last fetched fresh — for the stale line */
  curveAgeS: number | null;
  /** the folded days ahead — null hides the card (dead endpoint, outside) */
  outlook: Outlook | null;
};

/** Assemble everything the stack needs. `nonce` is a cheap re-render
 *  signal — bump it when a new ambient read lands (the aqi poll does).
 *  lat/lon select the forecast cell; DELHI centroid when no fix exists —
 *  the same fallback the freshness chip has always used. */
export function useDayData(
  lat: number, lon: number, trips: Trip[], nonce: number,
  /** fetch the 12-payload forecast curve — the peek card doesn't need it,
      so cold-start doesn't pay 12 /grid requests for a card it may never open */
  withCurve = true,
  /** parts labels re-render in this language (stored labels are
      save-time English by design) */
  lang: Lang = "en",
): DayData | null {
  const [data, setData] = useState<DayData | null>(null);
  // ~500 m rounding — the grid cell is ~10 km wide; drifting by a street
  // must not refetch 12 hourly payloads
  const rl = `${lat.toFixed(2)},${lon.toFixed(2)}`;
  useEffect(() => {
    let live = true;
    void (async () => {
      const [samples, checkins] = await Promise.all([allSamples(), getCheckins()]);
      const now = Date.now();
      const today = dayKey(now);
      const rec = reconstructDay(today, samples, trips, now, lang);

      // week: one reconstruction per day — cheap at this volume, and
      // honest (a day with no samples reads 0, not an invented number)
      const week: DayData["week"] = [];
      for (let i = 6; i >= 0; i--) {
        const d = new Date(now);
        d.setDate(d.getDate() - i);
        const k = dayKey(d.getTime());
        week.push({ day: k, ug: i === 0 ? rec.totalUg : reconstructDay(k, samples, trips, d.getTime(), lang).totalUg });
      }

      // the lens needs a dose per checkin's *previous* day, counted only
      // where coverage was real enough to say so
      const doseByDay: Record<string, number> = {};
      const keys = new Set<string>();
      for (const k of Object.keys(checkins)) {
        const d = new Date(`${k}T00:00:00`);
        d.setDate(d.getDate() - 1);
        keys.add(dayKey(d.getTime()));
      }
      for (const k of keys) {
        const r = reconstructDay(k, samples, trips, new Date(`${k}T23:59:59`).getTime(), lang);
        if (r.coveredMin >= 30 || r.parts.length > 0) doseByDay[k] = r.totalUg;
      }

      const outside = !inNcr(lat, lon);
      if (!live) return;
      /* disk-first paint: the hero + arc are local truths — they must not
         wait on the forecast fetches. On a dead network those take the
         full timeout and the hero would sit as skeleton blocks the whole
         time. Cards that need the field (the move, days ahead) mount
         when it lands — they already treat null as "not yet". */
      setData({
        rec, week, curve: null, outside, outlook: null,
        lens: symptomLens(checkins, doseByDay),
        checkin: checkins[today] ?? null,
        curveAgeS: null,
      });
      if (outside || !withCurve) return;
      const [curve, outlook] = await Promise.all([fetchDayCurve(lat, lon), fetchOutlook(lat, lon)]);
      if (!live) return;
      setData((prev) => (prev ? { ...prev, curve, outlook } : prev));
    })();
    return () => { live = false; };
  }, [rl, nonce, trips, withCurve, lang]); // eslint-disable-line react-hooks/exhaustive-deps
  return data;
}

/* ---------------- shared atoms ---------------- */

const mono = (lang: Lang, w: "reg" | "med" | "semi" = "reg") => famMono(lang, w);
/* mono-styled slots that carry localized text — Plex Mono has no
   Devanagari, so hi falls back to Noto; pure-number cells keep mono() */
const mtext = (lang: Lang, w: "reg" | "med" | "semi" = "reg") => famMonoText(lang, w);

/** A CPCB band dot — the only colour that means data. null → empty ring.
 *  `color` overrides for payloads that carry the band itself. */
function BandDot({ conc, color, size = 7 }: { conc: number | null; color?: string | null; size?: number }) {
  const c = color !== undefined ? color : bandColor(conc);
  return (
    <View style={{
      width: size, height: size, borderRadius: size / 2,
      backgroundColor: c ?? "transparent",
      borderWidth: c ? 0 : 1, borderColor: V2T.hairline,
    }} />
  );
}

/** A dose dot — colour comes from the day's fraction of the user's budget,
 *  not ambient bands (µg inhaled isn't µg/m³ air). Lighter reads quieter. */
function doseDotColor(ug: number, budgetUg: number): string {
  const r = budgetUg > 0 ? ug / budgetUg : 1;
  if (ug <= 0) return "transparent";
  if (r < 0.34) return V2T.text3;
  if (r < 0.67) return V2T.band2;
  if (r <= 1) return V2T.band3;
  return V2T.band4;
}

/* en keeps the am/pm Delhiites write; hi gets "बजे" so the move-card
   window labels never leak Latin letters into a Devanagari card */
const fmtHr = (h: number, lang: Lang) =>
  lang === "hi"
    ? `${((h + 11) % 12) + 1} बजे`
    : `${((h + 11) % 12) + 1}${h % 24 < 12 ? "am" : "pm"}`;

/* ---------------- the move (the morning card, promoted) ---------------- */

function SparklineInner({ series, lang }: { series: (number | null)[]; lang: Lang }) {
  bump("home.Sparkline");
  const [w, setW] = useState(0);
  const H = 44, PAD = 8;
  const vals = series.filter((v): v is number => v != null);
  const max = Math.max(...vals, 1), min = Math.min(...vals, 0);
  const span = Math.max(1, max - min);
  const x = (i: number) => PAD + (w - 2 * PAD) * (series.length <= 1 ? 0 : i / (series.length - 1));
  const y = (v: number) => H - 14 - (H - 24) * ((v - min) / span);
  /* contiguous runs only — a failed hour is a gap in the stroke, not a
     line drawn through a guess */
  const runs: string[] = [];
  let cur = "";
  series.forEach((v, i) => {
    if (v == null) { if (cur) runs.push(cur); cur = ""; return; }
    cur += `${cur ? " L" : "M"}${x(i).toFixed(1)} ${y(v).toFixed(1)}`;
  });
  if (cur) runs.push(cur);
  return (
    <View onLayout={(e) => setW(e.nativeEvent.layout.width)}>
      {w > 0 && (
        <Svg width={w} height={H + 14}>
          {runs.map((d, i) => (
            <Path key={i} d={d} stroke={V2T.text3} strokeWidth={1} fill="none" />
          ))}
          {series.map((v, i) => (
            <Circle key={i} cx={x(i)} cy={y(v ?? min)} r={2.2}
              fill={bandColor(v) ?? V2T.hairline} opacity={v == null ? 0.4 : 1} />
          ))}
        </Svg>
      )}
      {w > 0 && (
        <View style={ss.sparkLabels}>
          {series.map((v, i) => {
            const label = i === 0 ? t("dayNow", lang) : i % 3 === 0 ? t("hourTick", lang, { n: i }) : "";
            if (!label) return null;
            /* one label per marked hour, centred on its dot — wide enough
               that "+21h" never wraps (it did, flexing 1/25 of the row) */
            const cx = Math.min(Math.max(x(i), 18), w - 18);
            return (
              <Text key={i} {...DYNAMIC_TYPE} numberOfLines={1}
                style={[ss.sparkHr, { fontFamily: mtext(lang), left: cx - 20 }]}>
                {label}
              </Text>
            );
          })}
        </View>
      )}
    </View>
  );
}

const Sparkline = React.memo(SparklineInner);

/** The sparse hero's ambient arc — the day's served pm2.5 curve at the
 *  device's cell, drawn faint where the personal number can't stand yet:
 *  the truth we HAVE (the field) labelled, never a fake personal count
 *  (docs/lanes/hero-sparse). Same hole-not-a-guess rule as the move
 *  sparkline — a failed hour is a gap in the stroke. */
function SparseAirArcInner({ series }: { series: (number | null)[] }) {
  bump("home.SparseAirArc");
  const [w, setW] = useState(0);
  const H = 46, PAD = 10;
  const vals = series.filter((v): v is number => v != null);
  const max = Math.max(...vals, 1), min = Math.min(...vals, 0);
  const span = Math.max(1, max - min);
  const x = (i: number) => PAD + (w - 2 * PAD) * (series.length <= 1 ? 0 : i / (series.length - 1));
  const y = (v: number) => H - 8 - (H - 18) * ((v - min) / span);
  const runs: string[] = [];
  let cur = "";
  series.forEach((v, i) => {
    if (v == null) { if (cur) runs.push(cur); cur = ""; return; }
    cur += `${cur ? " L" : "M"}${x(i).toFixed(1)} ${y(v).toFixed(1)}`;
  });
  if (cur) runs.push(cur);
  return (
    <View onLayout={(e) => setW(e.nativeEvent.layout.width)} style={ss.sparseArc}>
      {w > 0 && (
        <Svg width={w} height={H}>
          {runs.map((d, i) => (
            <Path key={i} d={d} stroke={V2T.text3} strokeWidth={1} fill="none" opacity={0.5} />
          ))}
          {series.map((v, i) => (
            <Circle key={i} cx={x(i)} cy={y(v ?? min)} r={3}
              fill={bandColor(v) ?? V2T.hairline} opacity={v == null ? 0.3 : 0.85} />
          ))}
        </Svg>
      )}
    </View>
  );
}

const SparseAirArc = React.memo(SparseAirArcInner);

/** the 'as of' line the forecast cards share: the served field's own
 *  age in the freshness chip's tone language — stale says stale, fresh
 *  states the age, unknown says nothing (a card must not imply
 *  freshness it can't show). */
function fieldAgeLine(
  ageS: number | null | undefined,
  stale: boolean | null | undefined,
  lang: Lang,
): string | null {
  const tone = freshnessTone(ageS, stale);
  if (tone === "unknown") return null;
  const n = Math.max(0, Math.floor((ageS ?? 0) / 60));
  return tone === "stale"
    ? t("dayMorningStale", lang, { n })
    : t("howWe_fieldAge", lang, { n });
}

/* The CPCB band words live in strings.ts (band_*); index = the band the
 *  client already computes on a mid (theme.bandIdx — same CPCB breaks
 *  the server's districts.cpcb_band applies). */
const MOVE_BAND_KEYS: StringKey[] = [
  "band_good", "band_satisfactory", "band_moderate",
  "band_poor", "band_veryPoor", "band_severe",
];

/** The served decision line, localized. English keeps the wire text —
 *  it is already the card's own voice. Hindi rebuilds the sentence from
 *  the label + served windows + the hour series, mirroring
 *  server/v2/day.py:_decisions (its mids ARE our series' non-null
 *  cells, so means/extrema line up exactly); an unexpected label or a
 *  shape we can't rebuild falls back to the served line untouched. */
function decisionLine(
  d: { label: string; line: string },
  srv: NonNullable<DayCurve["server"]>,
  series: (number | null)[],
  lang: Lang,
): string {
  if (lang === "en") return d.line;
  const mids = series.filter((v): v is number => v != null);
  if (!mids.length) return d.line;
  const lo = Math.min(...mids), hi = Math.max(...mids);
  const mean = mids.reduce((s, x) => s + x, 0) / mids.length;
  const modalBand = (): string => {
    const counts = [0, 0, 0, 0, 0, 0];
    for (const m of mids) { const i = bandIdx(m); if (i != null) counts[i]++; }
    let best = 0;
    for (let i = 1; i < 6; i++) if (counts[i] > counts[best]) best = i;
    return t(MOVE_BAND_KEYS[best], lang);
  };
  if (d.label === "outdoor exercise") {
    if (srv.clean) {
      /* the server's 'cleanest'/'least-bad' word — same 60 µg/m³ cut the
         outlook caption already applies */
      const w = t(srv.clean.conc > CLEAN_UG ? "dayOutlookLeastBad" : "dayOutlookCleanest", lang);
      const win = `~${srv.cleanLabel ?? ""}-${srv.cleanEndLabel ?? ""}`;
      return t("moveDec_cleanWindow", lang, {
        w, win, c: Math.round(srv.clean.conc), m: Math.round(mean),
      });
    }
    /* served label "outdoor exercise" with no clean window =
       the no-clean-slot line; day_min is the series' own minimum */
    return t("moveDec_noClean", lang, { n: Math.round(lo) });
  }
  if (d.label === "today") {
    /* three 'today' sentences exist — re-derive which one the server's
       same thresholds picked (<3h card, flat day, jagged remainder) */
    if (mids.length < 3) {
      const last = bandIdx(mids[mids.length - 1]);
      return t("moveDec_short", lang, {
        n: mids.length,
        b: last == null ? "" : t(MOVE_BAND_KEYS[last], lang),
      });
    }
    if (hi - lo <= Math.max(15, 0.15 * mean)) {
      return t("moveDec_flat", lang, {
        b: modalBand(), lo: Math.round(lo), hi: Math.round(hi),
      });
    }
    return t("moveDec_jagged", lang, { lo: Math.round(lo), hi: Math.round(hi) });
  }
  return d.line;
}

function MoveCardInner({ curve, outside, lang }: {
  curve: DayCurve | null; outside: boolean; lang: Lang;
}) {
  bump("home.MoveCard");
  if (outside) {
    return (
      <View style={ss.card}>
        <Text {...DYNAMIC_TYPE} style={[ss.cardTitle, { fontFamily: fam(lang, "semi") }]}>
          {t("moveTitle", lang)}
        </Text>
        <Quiet glyph="pin" title={t("dayOutsideDelhi", lang)} lang={lang} />
      </View>
    );
  }
  if (!curve) return null; // still loading — the card mounts when it can say something
  if (!curve.covered) {
    return (
      <View style={ss.card}>
        <Text {...DYNAMIC_TYPE} style={[ss.cardTitle, { fontFamily: fam(lang, "semi") }]}>
          {t("moveTitle", lang)}
        </Text>
        <Quiet glyph="pin" title={t("dayMorningNoCell", lang)} lang={lang} />
      </View>
    );
  }
  const srv = curve.server;
  const a = morningAnswers(curve.series);
  // prefer the server's own windows/decisions when /v2/day answered —
  // it folds the same horizon /depart and /grid?h= serve, and a null
  // window there is an honest "no meaningful run", not missing data
  const heavy = srv ? srv.heavy : a.heavy;
  const clean = srv ? srv.clean : a.clean;
  const flat = srv ? (!srv.heavy && !srv.clean) : a.flat;
  const heavyF = srv?.heavyLabel ?? (heavy ? fmtHr(heavy.from + nowHour(), lang) : "");
  const heavyT = srv?.heavyEndLabel ??
    (srv?.heavyLabel ? "" : heavy ? fmtHr(heavy.to + nowHour(), lang) : "");
  const cleanF = srv?.cleanLabel ?? (clean ? fmtHr(clean.from + nowHour(), lang) : "");
  const cleanT = srv?.cleanEndLabel ??
    (srv?.cleanLabel ? "" : clean ? fmtHr(clean.to + nowHour(), lang) : "");
  const dec = srv?.decisions?.[0] ?? null;
  /* the felt decision — the served line localized (wire English must not
     leak into the hi UI); when the server named none, derive from the
     swing ("same plan at X breathes ~N× lighter than at Y") */
  const felt = dec && srv
    ? decisionLine(dec, srv, curve.series, lang)
    : (!flat && clean && heavy && a.ratio != null && a.ratio >= 1.2
      ? t("dayMorningMove", lang, { f: cleanF, g: heavyF, x: a.ratio.toFixed(1) })
      : null);
  const ageLine = fieldAgeLine(curve.fieldAgeS, curve.fieldStale, lang);
  return (
    <View style={ss.card}>
      <Text {...DYNAMIC_TYPE} style={[ss.cardTitle, { fontFamily: fam(lang, "semi") }]}>
        {t("moveTitle", lang)}
      </Text>
      {/* the decision is the hero of this card — serif at title scale so
          the multiplier is felt, not read (design-refs §5) */}
      {felt ? (
        <Text {...DYNAMIC_TYPE} style={[ss.moveLine, { fontFamily: famSerif(lang, "med") }]}>
          {felt}
        </Text>
      ) : flat ? (
        <Text {...DYNAMIC_TYPE} style={[ss.moveLine, { fontFamily: famSerif(lang, "med") }]}>
          {t("dayMorningFlat", lang)}
        </Text>
      ) : null}
      <Sparkline series={curve.series} lang={lang} />
      {!flat && (
        <>
          {heavy && (
            /* window chips — the heavy/clean evidence as tinted pills,
               each washed in its own band so the card's two facts read
               as components, not fine print */
            <View style={[ss.winChip, {
              backgroundColor: bandWashIdx(bandIdx(heavy.conc) ?? 0),
              borderColor: `${bandInkIdx(bandIdx(heavy.conc) ?? 0)}2E`,
            }]}>
              <BandDot conc={heavy.conc} />
              <Text {...DYNAMIC_TYPE} style={[ss.winChipTxt, NUM, { fontFamily: mtext(lang) }]}>
                {t("dayMorningHeavy", lang, {
                  f: heavyF,
                  t: heavyT,
                  c: Math.round(heavy.conc),
                })}
              </Text>
            </View>
          )}
          {clean && (
            <View style={[ss.winChip, {
              backgroundColor: bandWashIdx(bandIdx(clean.conc) ?? 0),
              borderColor: `${bandInkIdx(bandIdx(clean.conc) ?? 0)}2E`,
            }]}>
              <BandDot conc={clean.conc} />
              <Text {...DYNAMIC_TYPE} style={[ss.winChipTxt, NUM, { fontFamily: mtext(lang) }]}>
                {t("dayMorningClean", lang, {
                  f: cleanF,
                  t: cleanT,
                  c: Math.round(clean.conc),
                })}
              </Text>
            </View>
          )}
        </>
      )}
      {curve.conf === "lo" && (
        <Text {...DYNAMIC_TYPE} style={[ss.finePrint, { fontFamily: fam(lang, "reg") }]}>
          {t("howWe_conf", lang, { c: t("conf_low", lang) })}
        </Text>
      )}
      {/* the card's 'as of' — the served field's own build age */}
      {ageLine ? (
        <Text {...DYNAMIC_TYPE} style={[ss.finePrint, { fontFamily: fam(lang, "reg") }]}>
          {ageLine}
        </Text>
      ) : null}
    </View>
  );
}

const MoveCard = React.memo(MoveCardInner);

const nowHour = () => new Date().getHours();

/* ---------------- the days ahead ---------------- */

/** Served day label ("today" | "tomorrow" | weekday) → localized key.
 *  Unknown labels pass through — a name is honest even untranslated. */
const DAY_LABEL_KEYS: Record<string, StringKey> = {
  today: "dayLbl_today",
  tomorrow: "dayLbl_tomorrow",
  monday: "dayLbl_monday",
  tuesday: "dayLbl_tuesday",
  wednesday: "dayLbl_wednesday",
  thursday: "dayLbl_thursday",
  friday: "dayLbl_friday",
  saturday: "dayLbl_saturday",
  sunday: "dayLbl_sunday",
};
const dayLabel = (label: string, lang: Lang): string => {
  const k = DAY_LABEL_KEYS[label.trim().toLowerCase()];
  return k ? t(k, lang) : label;
};

/** Compact the served heavy-hour labels ("21:30" hourly starts) into
 *  ranges: ["21:30","22:30","23:30"] → "21:30–00:30"; singles stay raw.
 *  A day's hours never wrap midnight, so h+1 always means the next slot. */
function compactHours(labels: string[]): string {
  const hrs = labels
    .map((l) => (/^\d{1,2}:\d{2}/.test(l) ? { h: parseInt(l, 10), raw: l } : null))
    .filter((x): x is { h: number; raw: string } => x !== null);
  if (!hrs.length) return "";
  const out: string[] = [];
  let i = 0;
  while (i < hrs.length) {
    let j = i;
    while (j + 1 < hrs.length && hrs[j + 1].h === hrs[j].h + 1) j++;
    if (j > i) {
      const endH = `${(hrs[j].h + 1) % 24}`.padStart(2, "0");
      out.push(`${hrs[i].raw}–${endH}:${hrs[j].raw.slice(3)}`);
    } else {
      out.push(hrs[i].raw);
    }
    i = j + 1;
  }
  return out.join(", ");
}

/** The card's caption. English gets the wire line verbatim — it is already
 *  honest about partial days and flat weeks. Hindi rebuilds the same
 *  sentence from the served fields so wire English doesn't leak; anything
 *  unexpected falls back to the served text untouched. */
function outlookCaption(o: Outlook, lang: Lang): string {
  if (!o.verdict) return "";
  if (lang === "en") return o.verdict;
  if (o.best_day) {
    const b = o.best_day;
    const w = t(b.pm25_mid > CLEAN_UG ? "dayOutlookLeastBad" : "dayOutlookCleanest", lang);
    const s = t("dayOutlookVerdict", lang, {
      d: dayLabel(b.label, lang), w,
      c: Math.round(b.pm25_mid),
      g: Math.round(b.pm25_mid - b.delta_vs_mean),
    });
    return b.n_hours < 12 ? s + t("dayOutlookVerdictPartial", lang, { n: b.n_hours }) : s;
  }
  if (o.flat && o.days.length) {
    const mean = Math.round(o.days.reduce((s, d) => s + d.pm25_mid, 0) / o.days.length);
    return t("dayOutlookFlatVerdict", lang, { c: mean, n: o.days.length });
  }
  return o.verdict;
}

function DaysAheadCardInner({ outlook, lang }: { outlook: Outlook | null; lang: Lang }) {
  bump("home.DaysAhead");
  const reduceMotion = useReduceMotion();
  const [openKey, setOpenKey] = useState<string | null>(null);
  if (!outlook || outlook.days.length === 0) return null;
  const days = outlook.days.slice(0, 5);
  const open = days.find((d) => d.date_ist === openKey) ?? null;
  const anyLo = days.some((d) => d.confidence === "lo");
  const caption = outlookCaption(outlook, lang);
  const ageLine = fieldAgeLine(outlook.fieldAgeS, outlook.fieldStale, lang);
  return (
    <View style={ss.card}>
      <View style={ss.oaHead}>
        <Text {...DYNAMIC_TYPE} style={[ss.cardTitle, { fontFamily: fam(lang, "semi"), marginBottom: 0 }]}>
          {t("dayOutlookTitle", lang)}
        </Text>
        <Text {...DYNAMIC_TYPE} style={[ss.oaUnit, { fontFamily: mono(lang) }]}>µg/m³</Text>
      </View>
      <View style={ss.oaRow}>
        {days.map((d) => {
          const best = outlook.best_day?.date_ist === d.date_ist;
          const sel = openKey === d.date_ist;
          const dot = bandColorIdx(bandIdxForName(d.band)) ?? bandColor(d.pm25_mid);
          const bi = bandIdxForName(d.band) ?? bandIdx(d.pm25_mid);
          /* the band IS the scan cue — a deeper wash + band-inked day
             label so worst/best reads at a glance (five 10% washes were
             indistinguishable paper) */
          const cellBg = bi != null ? bandWashDeepIdx(bi) : V2T.surface;
          const cellEdge = bi != null ? bandEdgeIdx(bi) : V2T.hairline;
          /* the numeral owns the cell in full ink — band-ink at 85%
             washed the figure into the tinted fill; the band lives on
             the wash, the dot and the day label instead */
          const midCol = V2T.text;
          const dayCol = bi != null ? bandInkIdx(bi) ?? V2T.text3 : V2T.text3;
          return (
            <Pressable key={d.date_ist}
              onPress={() => {
                tick();
                /* the detail mounts under the row — ease it like the
                   settings/ledger expanders (native path) */
                if (!reduceMotion) LayoutAnimation.configureNext(LayoutAnimation.Presets.easeInEaseOut);
                setOpenKey(sel ? null : d.date_ist);
              }}
              accessibilityRole="button"
              accessibilityState={{ expanded: sel }}
              accessibilityLabel={`${dayLabel(d.label, lang)} ${Math.round(d.pm25_mid)}`}
              style={({ pressed }) => [
                ss.oaCell,
                { backgroundColor: cellBg, borderColor: cellEdge },
                d.confidence === "lo" && { opacity: 0.45 }, // ghosted — past the live anchor's reach
                sel && ss.oaCellSel,
                pressed && { transform: [{ scale: 0.96 }] },
              ]}>
              <Text {...DYNAMIC_TYPE} numberOfLines={1} adjustsFontSizeToFit minimumFontScale={0.7}
                style={[ss.oaDay, { fontFamily: mtext(lang), color: dayCol }]}>
                {dayLabel(d.label, lang)}
              </Text>
              <View style={ss.oaMidRow}>
                <BandDot conc={null} color={dot} />
                <Text {...DYNAMIC_TYPE} style={[ss.oaMid, NUM, { fontFamily: mono(lang, "med"), color: midCol }]}>
                  {Math.round(d.pm25_mid)}
                </Text>
              </View>
              <Text {...DYNAMIC_TYPE} numberOfLines={1} adjustsFontSizeToFit minimumFontScale={0.7}
                style={[ss.oaSub, { fontFamily: mono(lang) }]}>
                {d.partial ? t("hourTickTilde", lang, { n: d.n_hours }) : " "}
              </Text>
              <Text {...DYNAMIC_TYPE} numberOfLines={1} adjustsFontSizeToFit minimumFontScale={0.7}
                style={[ss.oaMark, { fontFamily: fam(lang, "med") }]}>
                {best ? t(d.pm25_mid > CLEAN_UG ? "dayOutlookLeastBad" : "dayOutlookCleanest", lang) : " "}
              </Text>
            </Pressable>
          );
        })}
      </View>
      {open && (
        <View style={ss.oaDetail}>
          <Text {...DYNAMIC_TYPE} style={[ss.oaDetailHead, { fontFamily: mtext(lang, "med") }]}>
            {dayLabel(open.label, lang)} · {open.date_ist}
          </Text>
          {open.partial && (
            <Text {...DYNAMIC_TYPE} style={[ss.oaDetailNote, { fontFamily: fam(lang, "reg") }]}>
              {open.label === "today"
                ? t("dayOutlookTodayPartial", lang, { n: open.n_hours })
                : t("dayOutlookPartial", lang, { n: open.n_hours })}
            </Text>
          )}
          {open.cleanest_window ? (
            <View style={ss.mRow}>
              <BandDot conc={open.cleanest_window.pm25_mid ?? null} />
              <Text {...DYNAMIC_TYPE} style={[ss.mLine, NUM, { fontFamily: mtext(lang) }]}>
                {t("dayMorningClean", lang, {
                  f: open.cleanest_window.start_label ?? "",
                  t: open.cleanest_window.end_label ?? "—",
                  c: Math.round(open.cleanest_window.pm25_mid ?? 0),
                })}
              </Text>
            </View>
          ) : (
            <Text {...DYNAMIC_TYPE}
              style={[ss.mLine, { fontFamily: fam(lang, "reg"), marginTop: 6 }]}>
              {open.heavy_hours_ist.length > 0
                ? t("dayOutlookAllDayHeavy", lang)
                : t("dayMorningFlat", lang)}
            </Text>
          )}
          {open.cleanest_window && open.heavy_hours_ist.length > 0 && (
            <Text {...DYNAMIC_TYPE} style={[ss.oaDetailNote, NUM, { fontFamily: mtext(lang) }]}>
              {t("dayOutlookHeavyHours", lang, { h: compactHours(open.heavy_hours_ist) })}
            </Text>
          )}
          {open.pm25_lo != null && open.pm25_hi != null && (
            <Text {...DYNAMIC_TYPE} style={[ss.oaDetailNote, NUM, { fontFamily: mtext(lang) }]}>
              {t("dayOutlookRange", lang, { lo: Math.round(open.pm25_lo), hi: Math.round(open.pm25_hi) })}
            </Text>
          )}
        </View>
      )}
      {!!caption && (
        <Text {...DYNAMIC_TYPE} style={[ss.noteLine, { fontFamily: fam(lang, "med") }]}>
          {caption}
        </Text>
      )}
      {anyLo && (
        <Text {...DYNAMIC_TYPE} style={[ss.finePrint, { fontFamily: fam(lang, "reg") }]}>
          {t("dayOutlookLoNote", lang)}
        </Text>
      )}
      {/* today's basis 'as of' — the live field behind the fold */}
      {ageLine ? (
        <Text {...DYNAMIC_TYPE} style={[ss.finePrint, { fontFamily: fam(lang, "reg") }]}>
          {ageLine}
        </Text>
      ) : null}
    </View>
  );
}

const DaysAheadCard = React.memo(DaysAheadCardInner);

/* ---------------- your day: the arc ---------------- */

function HourArcInner({ rec, lang }: { rec: DayReconstruction; lang: Lang }) {
  bump("home.HourArc");
  const max = Math.max(...rec.arc.map((h) => h.dose_ug), 0.5);
  const nh = nowHour();
  return (
    <View style={ss.arcWrap}>
      {rec.arc.map((h) => {
        const isNow = h.hour === nh;
        /* the arc is a heat strip: the bar's height is the dose that hour
           added, its colour is the band of the air breathed — the day
           reads as weather before it reads as numbers */
        const barCol = isNow ? V2T.text : (bandColor(h.conc) ?? V2T.text3);
        return (
          <View key={h.hour} style={ss.arcCol}>
            <View style={ss.arcBarCol}>
              {h.covered && h.dose_ug > 0 ? (
                <View style={[ss.arcBar, {
                  height: 4 + 44 * (h.dose_ug / max),
                  backgroundColor: barCol,
                }]} />
              ) : h.conc != null ? (
                /* uncovered hour — the band dot keeps the field visible
                   without claiming dose we didn't count */
                <View style={[ss.arcDot, { backgroundColor: bandColor(h.conc) ?? V2T.hairline }]} />
              ) : null}
              {h.trip_marks > 0 && <View style={ss.arcTrip} />}
            </View>
            <Text {...DYNAMIC_TYPE}
              style={[ss.arcHr, { fontFamily: mono(lang) }, isNow && { color: V2T.text }]}>
              {h.hour % 3 === 0 ? `${h.hour}` : ""}
            </Text>
          </View>
        );
      })}
    </View>
  );
}

const HourArc = React.memo(HourArcInner);

function DayCardInner({ rec, budgetUg, lang }: {
  rec: DayReconstruction; budgetUg: number; lang: Lang;
}) {
  bump("home.DayCard");
  if (rec.thin) return null; // the hero already carries the honest-empty line
  return (
    <View style={ss.card}>
      <Text {...DYNAMIC_TYPE} style={[ss.cardTitle, { fontFamily: fam(lang, "semi") }]}>
        {t("dayTitle", lang)}
      </Text>
      <HourArc rec={rec} lang={lang} />
      {rec.parts.length > 0 && (
        <>
          <Text {...DYNAMIC_TYPE} style={[ss.partsTitle, { fontFamily: fam(lang, "med") }]}>
            {t("dayPartsTitle", lang)}
          </Text>
          {/* each span is a chip — a dose-tinted spine, the span's own
              words, its µg count; a row of components, not a table */}
          {rec.parts.map((p, i) => {
            const pt = doseTierIdx(p.ug, budgetUg);
            return (
              <View key={i} style={ss.partChip}>
                <View style={[ss.partSpine, { backgroundColor: doseDotColor(p.ug, budgetUg) }]} />
                <Text {...DYNAMIC_TYPE} style={[ss.partLabel, { fontFamily: fam(lang, "reg") }]}
                  numberOfLines={1}>
                  {p.label}
                </Text>
                <Text {...DYNAMIC_TYPE} style={[ss.partUg, NUM, { fontFamily: mono(lang, "med"),
                  color: pt != null ? bandInkIdx(pt) ?? V2T.text : V2T.text }]}>
                  {approx(doseUgRound(p.ug))} µg
                </Text>
              </View>
            );
          })}
        </>
      )}
    </View>
  );
}

const DayCard = React.memo(DayCardInner);

/* ---------------- the symptom lens ---------------- */

const FACETS = [
  { key: "breath", labelKey: "lensBreath" },
  { key: "eyes", labelKey: "lensEyes" },
  { key: "energy", labelKey: "lensEnergy" },
] as const;
const OPTS = ["lensGood", "lensMeh", "lensRough"] as const;

function LensCardInner({ checkin, lens, lang, onCheckin }: {
  checkin: Checkin | null; lens: LensVerdict; lang: Lang;
  onCheckin: (c: Omit<Checkin, "ts">) => void;
}) {
  bump("home.LensCard");
  const val = { breath: checkin?.breath ?? -1, eyes: checkin?.eyes ?? -1, energy: checkin?.energy ?? -1 };
  return (
    <View style={ss.card}>
      <Text {...DYNAMIC_TYPE} style={[ss.cardTitle, { fontFamily: fam(lang, "semi") }]}>
        {t("lensTitle", lang)}
      </Text>
      <Text {...DYNAMIC_TYPE} style={[ss.lensSub, { fontFamily: fam(lang, "reg") }]}>
        {t("lensSub", lang)}
      </Text>
      {FACETS.map((f) => (
        <View key={f.key} style={ss.facetRow}>
          <Text {...DYNAMIC_TYPE} style={[ss.facetLabel, { fontFamily: fam(lang, "med") }]}>
            {t(f.labelKey, lang)}
          </Text>
          <View style={ss.facetOpts}>
            {OPTS.map((ok, v) => {
              const sel = val[f.key] === v;
              return (
                <Pressable key={ok}
                  onPress={() => { tap(); onCheckin({ breath: val.breath, eyes: val.eyes, energy: val.energy, [f.key]: v }); }}
                  accessibilityRole="button"
                  accessibilityLabel={`${t(f.labelKey, lang)}: ${t(ok, lang)}`}
                  style={({ pressed }) => [ss.opt, sel && ss.optSel, pressFx(pressed)]}>
                  <Text {...DYNAMIC_TYPE}
                    style={[ss.optTxt, { fontFamily: fam(lang, "reg") }, sel && ss.optTxtSel]}>
                    {t(ok, lang)}
                  </Text>
                </Pressable>
              );
            })}
          </View>
        </View>
      ))}
      <Text {...DYNAMIC_TYPE} style={[ss.finePrint, { fontFamily: fam(lang, "reg") }]}>
        {t("lensPrivacy", lang)}
      </Text>
      {/* the verdict earns its line honestly */}
      <Text {...DYNAMIC_TYPE} style={[ss.verdict, { fontFamily: fam(lang, "med") }]}>
        {lens.kind === "early" ? t("lensEarly", lang)
          : lens.kind === "flat" ? t("lensFlat", lang, { n: lens.days })
          : t("lensLink", lang, {
              f: t(lens.facet === "eyes" ? "lensFacetEyes"
                    : lens.facet === "energy" ? "lensFacetEnergy" : "lensFacetBreath", lang),
            })}
      </Text>
    </View>
  );
}

const LensCard = React.memo(LensCardInner);

/* ---------------- the budget ---------------- */

const PROFILES = [
  { k: "general", labelKey: "profileGeneral" },
  { k: "sensitive", labelKey: "profileSensitive" },
  { k: "child", labelKey: "profileChild" },
] as const;

function BudgetCardInner({ totalUg, profile, lang, onProfile }: {
  totalUg: number; profile: ShellSettings["profile"]; lang: Lang;
  onProfile: (p: ShellSettings["profile"]) => void;
}) {
  bump("home.BudgetCard");
  const budget = PROFILE_BUDGET_UG[profile];
  const over = totalUg - budget;
  const frac = Math.max(0, Math.min(1, totalUg / budget));
  return (
    <View style={ss.card}>
      <Text {...DYNAMIC_TYPE} style={[ss.cardTitle, { fontFamily: fam(lang, "semi") }]}>
        {t("budgetTitle", lang)}
      </Text>
      <View style={ss.budgetBar}>
        <View style={[ss.budgetFill, {
          width: `${frac * 100}%`,
          backgroundColor: over > 0 ? V2T.breath2 : V2T.accent,
        }]} />
      </View>
      <Text {...DYNAMIC_TYPE} style={[ss.budgetLine, NUM, { fontFamily: mtext(lang) }]}>
        {over > 0
          ? t("budgetOver", lang, { o: doseUgRound(over), p: t(`profile${profile[0].toUpperCase()}${profile.slice(1)}` as never, lang) })
          : t("budgetWithin", lang, { r: doseUgRound(-over), b: budget })}
      </Text>
      <View style={ss.profileRow}>
        {PROFILES.map((p) => {
          const sel = profile === p.k;
          return (
            /* the profile is a segment row — the picked segment fills ink
               so the choice reads as state, not as one more outlined pill */
            <Pressable key={p.k} onPress={() => { tap(); onProfile(p.k); }}
              accessibilityRole="button" accessibilityLabel={t(p.labelKey, lang)}
              accessibilityState={{ selected: sel }}
              style={({ pressed }) => [ss.segOpt, sel && ss.segOptSel, pressed && !sel && { opacity: 0.6 }]}>
              <Text {...DYNAMIC_TYPE}
                style={[ss.segTxt, { fontFamily: fam(lang, "med") }, sel && ss.segTxtSel]}>
                {t(p.labelKey, lang)}
              </Text>
            </Pressable>
          );
        })}
      </View>
      <Text {...DYNAMIC_TYPE} style={[ss.finePrint, { fontFamily: fam(lang, "reg") }]}>
        {t("budgetProfileQ", lang)}
      </Text>
    </View>
  );
}

const BudgetCard = React.memo(BudgetCardInner);

/* ---------------- the peek card (idle map — the door back home) ------- */

/** The idle-map card — one glance: today µg, the week's dots, the ambient
 *  read. Tap returns home (the dosimeter surface). An empty day says so in
 *  one line and still opens home — the move + check-in are useful before
 *  the arc fills. */
function DayPeekInner({ data, lang, onOpen, ambientUg, budgetUg = 216 }: {
  data: DayData | null; lang: Lang; onOpen: () => void;
  /** latest ambient PM2.5 read — the "outside right now" line; the aqi
      poll hands it over so the peek feels the air, not just states it */
  ambientUg?: number | null;
  /** the profile's daily budget — the same ceiling the hero gauges
      against, or the peek would colour a different day than home does */
  budgetUg?: number;
}) {
  bump("home.DayPeek");
  if (!data) return null;
  /* the card breathes the band it reports: band-washed fill + band-edge
     hairline + inked number — a severe day feels severe before any tap */
  const ambIdx = bandIdx(ambientUg ?? null);
  const doseCol = doseDotColor(data.rec.totalUg, budgetUg);
  return (
    <Pressable onPress={() => { tap(); onOpen(); }}
      accessibilityRole="button" accessibilityLabel={t("peekTitle", lang)}
      style={({ pressed }) => [
        ss.peek,
        ambIdx != null && {
          backgroundColor: bandWashIdx(ambIdx),
          borderColor: bandEdgeIdx(ambIdx),
        },
        pressed && { opacity: 0.9, transform: [{ scale: 0.99 }] },
      ]}>
      <View style={ss.peekTop}>
        <Text {...DYNAMIC_TYPE} style={[ss.peekEyebrow, { fontFamily: mtext(lang, "med") }]}>
          {t("peekTitle", lang)}
        </Text>
        <View style={ss.peekTopRight}>
          {ambIdx != null && ambientUg != null && (
            <Text {...DYNAMIC_TYPE} style={[ss.peekAmb, NUM, {
              fontFamily: mtext(lang, "med"), color: bandInkIdx(ambIdx),
            }]}>
              {t("peekAmbient", lang, { n: Math.round(ambientUg) })}
            </Text>
          )}
          <Icon name="chevron" color={V2T.text3} size={14} />
        </View>
      </View>
      {data.rec.thin ? (
        <Text {...DYNAMIC_TYPE} style={[ss.peekEmpty, { fontFamily: fam(lang, "reg") }]}>
          {t("peekEmpty", lang)}
        </Text>
      ) : (
        <View style={ss.peekRow}>
          <Text {...DYNAMIC_TYPE} style={[ss.peekNum, NUM, {
            fontFamily: famSerif(lang, "semi"), color: doseCol,
          }]}>
            ≈{doseUgRound(data.rec.totalUg)}
          </Text>
          {/* the FIRST-use gloss — "µg (micrograms)" whole; the strip
             was supposed to live only on the dense hero slot below
             (apk-rebuild-v7 fail: gloss rendered nowhere) */}
          <Text {...DYNAMIC_TYPE} numberOfLines={1} adjustsFontSizeToFit minimumFontScale={0.8}
            style={[ss.peekUnit, { fontFamily: mono(lang), flexShrink: 1 }]}>{t("unitUg", lang)}</Text>
          <View style={ss.peekDots}>
            {data.week.map((w) => (
              <View key={w.day} style={[ss.weekDot, {
                backgroundColor: w.ug > 0 ? doseDotColor(w.ug, budgetUg) : "transparent",
                borderWidth: w.ug > 0 ? 0 : 1, borderColor: V2T.hairline,
              }]} />
            ))}
          </View>
        </View>
      )}
    </Pressable>
  );
}

export const DayPeek = React.memo(DayPeekInner);

/* ---------------- the home surface ---------------- */

const WEEKDAY_EN = ["sunday", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday"];

function HomeHeaderInner({ lang, onMenu }: { lang: Lang; onMenu: () => void }) {
  bump("home.HomeHeader");
  const insets = useSafeAreaInsets();
  const now = new Date();
  const hh = `${now.getHours()}`.padStart(2, "0");
  const mm = `${now.getMinutes()}`.padStart(2, "0");
  return (
    <View style={[ss.homeHead, { paddingTop: insets.top + 8 }]}>
      <View>
        <Text {...DYNAMIC_TYPE} style={[ss.brand, { fontFamily: famSerif(lang, "semi") }]}>
          ALive-108
        </Text>
        <Text {...DYNAMIC_TYPE} style={[ss.brandSub, { fontFamily: mtext(lang) }]}>
          {dayLabel(WEEKDAY_EN[now.getDay()], lang)} · {hh}:{mm} · {t("cityTag", lang)}
        </Text>
      </View>
      <Pressable onPress={() => { tick(); onMenu(); }} hitSlop={10}
        accessibilityRole="button" accessibilityLabel={t("a11yMenu", lang)}
        style={({ pressed }) => [ss.homeMenuBtn, pressed && { opacity: 0.55 }]}>
        <View style={ss.menuBars}>
          {[0, 1, 2].map((i) => <View key={i} style={ss.menuBar} />)}
        </View>
      </Pressable>
    </View>
  );
}

const HomeHeader = React.memo(HomeHeaderInner);

/** The dose gauge — one ring filling toward the day's budget. Oura/Apple
 *  ring grammar: fraction filled + colour does the work, no axes. Over
 *  budget keeps a full ring and turns the percent line honest. */
function DoseGaugeInner({ frac, color, lang }: { frac: number; color: string; lang: Lang }) {
  const R = 30, S = 76, SW = 7;
  const f = Math.max(0, Math.min(1, frac));
  const cx = S / 2, cy = S / 2;
  const a0 = -Math.PI / 2;
  const a1 = a0 + 2 * Math.PI * Math.min(f, 0.9999);
  const x0 = cx + R * Math.cos(a0), y0 = cy + R * Math.sin(a0);
  const x1 = cx + R * Math.cos(a1), y1 = cy + R * Math.sin(a1);
  return (
    <View style={ss.gaugeWrap}>
      <Svg width={S} height={S}>
        <Circle cx={cx} cy={cy} r={R} stroke={V2T.line} strokeWidth={SW} fill="none" />
        {f > 0.004 && (
          <Path
            d={`M${x0.toFixed(2)} ${y0.toFixed(2)} A${R} ${R} 0 ${f > 0.5 ? 1 : 0} 1 ${x1.toFixed(2)} ${y1.toFixed(2)}`}
            stroke={color} strokeWidth={SW} fill="none" strokeLinecap="round" />
        )}
      </Svg>
      <View style={ss.gaugeCenter}>
        <Text {...DYNAMIC_TYPE} style={[ss.gaugePct, NUM, { fontFamily: mono(lang, "med"), color }]}>
          {Math.round(f * 100)}%
        </Text>
      </View>
    </View>
  );
}

const DoseGauge = React.memo(DoseGaugeInner);

/** The hero — WHOOP's one-score compression (design-refs §3): ≈N µg
 *  breathed at display scale, coloured by the day's fraction of budget,
 *  with the covered-hours and outside-now reads as tier-2 evidence. */
/** Which CPCB band the day's dose-fraction whispers on the hero card —
 *  the same thresholds doseDotColor uses, returned as an index so the
 *  card can take a pastel wash + edge. null = a quiet day stays paper. */
function doseTierIdx(ug: number, budgetUg: number): number | null {
  const r = budgetUg > 0 ? ug / budgetUg : 1;
  if (ug <= 0 || r < 0.34) return null;
  if (r < 0.67) return 2;
  if (r <= 1) return 3;
  return 4;
}

function HeroBlockInner({ data, budgetUg, ambientUg, lang }: {
  data: DayData | null; budgetUg: number; ambientUg: number | null; lang: Lang;
}) {
  bump("home.HeroBlock");
  if (!data) {
    /* skeleton — blocks morph to content when the disk read lands */
    return (
      <View style={ss.heroCard}>
        <View style={ss.skelEyebrow} />
        <View style={ss.skelHero} />
        <View style={ss.skelLine} />
      </View>
    );
  }
  const rec = data.rec;
  const ug = rec.totalUg;
  /* the hero card is a tinted object: the day's dose severity washes the
     surface (18% band) while the numeral keeps full band-ink — colour ON
     the component, never a repaint of the pane */
  const tier = doseTierIdx(rec.totalUg, budgetUg);
  const ambHeroIdx = bandIdx(ambientUg ?? null);
  const sparseWash = ambHeroIdx != null ? bandWashMidIdx(ambHeroIdx) : null;
  const heroBg = tier != null ? bandWashMidIdx(tier) : (sparseWash ?? V2T.surface);
  const heroEdge = tier != null
    ? `${bandInkIdx(tier)}38`
    : (sparseWash != null ? `${bandInkIdx(ambHeroIdx!)}33` : V2T.hairline);
  const col = tier != null ? (bandInkIdx(tier) ?? V2T.text) : doseDotColor(rec.totalUg, budgetUg);
  const ambIdx = bandIdx(ambientUg ?? null);
  const h = Math.floor(rec.coveredMin / 60), m = rec.coveredMin % 60;
  const maxW = Math.max(...data.week.map((w) => w.ug), 1);
  /* the sparse hero's ambient truth: the poll's own read first, then the
     curve's now-slot — whichever the device actually has (never a guess) */
  const airNow = ambientUg ?? data.curve?.series.find((v) => v != null) ?? null;
  const airNowIdx = bandIdx(airNow);
  const weekCounted = data.week.some((w) => w.ug > 0);
  const cityDays = data.outlook?.days.slice(0, 7) ?? [];
  return (
    <View style={[ss.heroCard, { backgroundColor: heroBg, borderColor: heroEdge }]}>
      <Text {...DYNAMIC_TYPE} style={[ss.heroEyebrow, { fontFamily: fam(lang, "semi") }]}>
        {t("homeBreathed", lang)}
      </Text>
      {rec.thin ? (
        /* designed sparse (docs/lanes/hero-sparse) — the field at the
           device's cell IS known, so show it labelled and faint inside
           the hero zone; what's missing is only the personal count, and
           the meter says how far the phone is from its first counted
           day. Never a fake personal number. */
        <>
          {airNow != null && (
            <>
              {!!data.curve?.series.some((v) => v != null) && (
                <SparseAirArc series={data.curve.series} />
              )}
              <View style={ss.sparseAmbRow}>
                <BandDot conc={null} color={bandColor(airNow)} />
                <Text {...DYNAMIC_TYPE} style={[ss.sparseAmb, NUM, {
                  fontFamily: mtext(lang, "med"),
                  color: airNowIdx != null ? bandInkIdx(airNowIdx) ?? V2T.text3 : V2T.text3,
                }]}>
                  {t("daySparseAir", lang, { n: Math.round(airNow) })}
                </Text>
              </View>
            </>
          )}
          {airNow == null && (
            <Text {...DYNAMIC_TYPE} style={[ss.heroThin, { fontFamily: fam(lang, "reg") }]}>
              {t("daySparseWait", lang)}
            </Text>
          )}
          <Text {...DYNAMIC_TYPE} style={[ss.heroThin, { fontFamily: fam(lang, "reg") }]}>
            {t("daySparseCount", lang)}
          </Text>
          {/* progress to the first counted day — the same 3-sample gate
              the hero number answers to, shown as it fills */}
          <View style={ss.sparseProgRow}>
            {Array.from({ length: THIN_SAMPLE_MIN }).map((_, i) => (
              <View key={i} style={[ss.weekDot, {
                backgroundColor: i < rec.samplesToday ? V2T.text3 : "transparent",
                borderWidth: i < rec.samplesToday ? 0 : 1,
                borderColor: V2T.hairline,
              }]} />
            ))}
            <Text {...DYNAMIC_TYPE} style={[ss.sparseProgLbl, NUM, { fontFamily: mtext(lang) }]}>
              {t("daySparseSamples", lang, {
                n: Math.min(rec.samplesToday, THIN_SAMPLE_MIN),
                m: THIN_SAMPLE_MIN,
              })}
            </Text>
          </View>
        </>
      ) : (
        <View style={ss.heroMainRow}>
          <View style={ss.heroNumRow}>
            <CountUp value={ug} duration={620}
              style={[ss.heroNum, { fontFamily: famSerif(lang, "semi"), color: col }]}
              format={(n) => `≈${doseUgRound(n)}`} />
            {/* bare "µg" — the register's number+unit pair; the
                "(micrograms)" gloss lives on the peek card, not here */}
            <Text {...DYNAMIC_TYPE} style={[ss.heroUg, { fontFamily: mono(lang, "med") }]}
              numberOfLines={1}>
              {t("unitUg", lang).split(" ")[0]}
            </Text>
          </View>
          <View style={ss.heroGaugeCol}>
            <DoseGauge frac={budgetUg > 0 ? rec.totalUg / budgetUg : 0} color={col} lang={lang} />
            <Text {...DYNAMIC_TYPE} style={[ss.heroOfBudget, NUM, { fontFamily: mtext(lang) }]}>
              {t("homeOfBudget", lang, { b: budgetUg })}
            </Text>
          </View>
        </View>
      )}
      {/* the stat row carries the covered-hours read in the counted
          state; in the sparse state the ambient read lives inside the
          hero zone itself (labelled as the field, not as your dose) */}
      {!rec.thin && (
        <View style={ss.heroStatRow}>
          <Text {...DYNAMIC_TYPE} style={[ss.heroStat, NUM, { fontFamily: mtext(lang) }]}>
            {h > 0 ? t("dayCovered", lang, { h, m }) : t("dayCoveredMin", lang, { m })}
          </Text>
          {ambientUg != null && ambIdx != null && (
            <View style={ss.heroAmb}>
              <BandDot conc={null} color={bandColorIdx(ambIdx)} />
              <Text {...DYNAMIC_TYPE} style={[ss.heroStat, NUM, {
                fontFamily: mtext(lang), color: bandInkIdx(ambIdx) ?? V2T.text3,
              }]}>
                {t("homeOutsideNow", lang, { n: Math.round(ambientUg) })}
              </Text>
            </View>
          )}
        </View>
      )}
      {/* the week — last 7 local days as dose dots (reconstruction, not
          ambition); a quiet trend under the hero, not a chart. With no
          day counted yet the personal arc can't stand — the city's own
          forecast days stand in, dimmed and named as Delhi's, never
          read as yours ('0µg' + empty dots reads broken, not honest). */}
      <View style={ss.heroWeekRow}>
        {weekCounted ? (
          <>
            {data.week.map((w) => (
              <View key={w.day} style={[ss.weekDot, {
                backgroundColor: w.ug > 0 ? doseDotColor(w.ug, budgetUg) : "transparent",
                borderWidth: w.ug > 0 ? 0 : 1, borderColor: V2T.hairline,
                opacity: w.ug > 0 ? 0.5 + 0.5 * (w.ug / maxW) : 1,
              }]} />
            ))}
            <Text {...DYNAMIC_TYPE} style={[ss.heroWeekLbl, NUM, { fontFamily: mtext(lang) }]}>
              {t("homeWeek", lang, {
                n: approx(doseUgRound(data.week.reduce((s, w) => s + w.ug, 0))),
              })}
            </Text>
          </>
        ) : (
          <>
            {cityDays.length > 0
              ? cityDays.map((d) => {
                  const bi = bandIdxForName(d.band) ?? bandIdx(d.pm25_mid);
                  return (
                    <View key={d.date_ist} style={[ss.weekDot, {
                      backgroundColor: bi != null ? bandColorIdx(bi) ?? "transparent" : "transparent",
                      borderWidth: bi != null ? 0 : 1, borderColor: V2T.hairline,
                      opacity: 0.4,
                    }]} />
                  );
                })
              : data.week.map((w) => (
                  <View key={w.day} style={[ss.weekDot, {
                    backgroundColor: "transparent",
                    borderWidth: 1, borderColor: V2T.hairline,
                  }]} />
                ))}
            <Text {...DYNAMIC_TYPE} style={[ss.heroWeekLbl, { fontFamily: mtext(lang) }]}>
              {cityDays.length > 0
                ? `${t("homeWeekCity", lang)} · ${t("homeWeekSparse", lang)}`
                : t("homeWeekSparse", lang)}
            </Text>
          </>
        )}
      </View>
    </View>
  );
}

const HeroBlock = React.memo(HeroBlockInner);

/** The travel verb — THE primary CTA of the home surface (the register's
 *  one-primary-pill rule): a solid ink pill, search glyph, the question,
 *  navigate arrow. The map lives behind it, never resident. */
function TravelCtaInner({ lang, onGo }: { lang: Lang; onGo: () => void }) {
  bump("home.TravelCta");
  return (
    /* collapsable={false}: Android can flatten a Pressable's parent chain
       and drop it from the touch map — the pill read as visible-but-dead
       on device (apk-verify-v8). Cheap insurance on the primary action. */
    <Pressable collapsable={false} onPress={() => { tick(); onGo(); }}
      accessibilityRole="button" accessibilityLabel={t("goLabel", lang)}
      style={({ pressed }) => [ss.cta, pressFx(pressed)]}>
      <Icon name="search" color={V2T.bg} size={19} />
      <Text {...DYNAMIC_TYPE} style={[ss.ctaTxt, { fontFamily: fam(lang, "semi") }]}>
        {t("searchPlaceholder", lang)}
      </Text>
      <View style={ss.ctaArrow}>
        <Icon name="navigate" color={V2T.bg} size={16} />
      </View>
    </Pressable>
  );
}

const TravelCta = React.memo(TravelCtaInner);

/** Feature doors — the secondary rooms as chunky icon tiles (the
 *  register's Swiggy-pattern feature doors). Paper tiles: identity
 *  colour lives INSIDE the glyph chip — a row of different pastel
 *  floods reads as a cheap hue parade (owner callout, Oct 6). The
 *  city chip still wears the live ambient band so the tile carries
 *  today's read, just not as a flood. */
function DoorRowInner({ lang, ambientUg, onMap, onCity, onTrips }: {
  lang: Lang; ambientUg: number | null;
  onMap: () => void; onCity: () => void; onTrips: () => void;
}) {
  bump("home.DoorRow");
  const ambIdx = bandIdx(ambientUg ?? null);
  const doors: { key: StringKey; glyph: Glyph; fn: () => void; chip: string; ink: string }[] = [
    { key: "homeLinkMap", glyph: "explore", fn: onMap, chip: V2Tint.forest.wash, ink: V2Tint.forest.ink },
    /* the city chip breathes today's band — band wash + band ink when the
       ambient read exists, the neutral slate well when it doesn't */
    {
      key: "homeLinkCity", glyph: "city", fn: onCity,
      chip: ambIdx != null ? bandWashDeepIdx(ambIdx) : V2Tint.sky.wash,
      ink: ambIdx != null ? (bandInkIdx(ambIdx) ?? V2Tint.sky.ink) : V2Tint.sky.ink,
    },
    { key: "homeLinkTrips", glyph: "history", fn: onTrips, chip: V2Tint.clay.wash, ink: V2Tint.clay.ink },
  ];
  return (
    <View style={ss.doorRow}>
      {doors.map((d) => (
        <Pressable key={d.key} onPress={() => { tap(); d.fn(); }}
          accessibilityRole="button" accessibilityLabel={t(d.key, lang)}
          style={({ pressed }) => [
            ss.door,
            { backgroundColor: V2T.surface, borderColor: V2T.hairline },
            pressed && { opacity: 0.85, transform: [{ scale: 0.97 }] },
          ]}>
          <View style={[ss.doorWell, { backgroundColor: d.chip }]}>
            <Icon name={d.glyph} color={d.ink} size={22} filled />
          </View>
          <Text {...DYNAMIC_TYPE} numberOfLines={1}
            style={[ss.doorLabel, { fontFamily: fam(lang, "semi"), color: V2T.text }]}>
            {t(d.key, lang)}
          </Text>
        </Pressable>
      ))}
    </View>
  );
}

const DoorRow = React.memo(DoorRowInner);

function HomeSheetInner({ data, lang, settings, ambientUg, onGo, onMenu, onMap, onCity, onTrips, onProfile, onCheckin }: {
  data: DayData | null; lang: Lang; settings: ShellSettings;
  ambientUg: number | null;
  onGo: () => void; onMenu: () => void;
  onMap: () => void; onCity: () => void; onTrips: () => void;
  onProfile: (p: ShellSettings["profile"]) => void;
  onCheckin: (c: Omit<Checkin, "ts">) => void;
}) {
  bump("home.HomeSheet");
  const insets = useSafeAreaInsets();
  const budget = PROFILE_BUDGET_UG[settings.profile];
  return (
    <View style={ss.home}>
      <HomeHeader lang={lang} onMenu={onMenu} />
      <ScrollView style={ss.flex}
        contentContainerStyle={[ss.content, { paddingBottom: 12 }]}
        showsVerticalScrollIndicator={false}>
        {/* the hero lands first; the doors sit under it; content cards
            arrive staggered below. The ONE primary CTA is NOT in the
            scroll — it lives pinned in the footer bar below (the
            daily-driver grammar: the verb never scrolls away), which
            also takes it out of the scroll/elevation touch-dispatch
            path that ate taps on Android (apk-verify-v8). */}
        <FadeIn delay={0}>
          <HeroBlock data={data} budgetUg={budget} ambientUg={ambientUg} lang={lang} />
        </FadeIn>
        <FadeIn delay={90}>
          <DoorRow lang={lang} ambientUg={ambientUg} onMap={onMap} onCity={onCity} onTrips={onTrips} />
        </FadeIn>
        <FadeIn delay={130}>
          <MoveCard curve={data?.curve ?? null} outside={data?.outside ?? false} lang={lang} />
        </FadeIn>
        {data && !data.rec.thin && (
          <FadeIn delay={170}>
            <DayCard rec={data.rec} budgetUg={budget} lang={lang} />
          </FadeIn>
        )}
        <FadeIn delay={210}>
          <DaysAheadCard outlook={data?.outlook ?? null} lang={lang} />
        </FadeIn>
        <FadeIn delay={250}>
          <LensCard checkin={data?.checkin ?? null}
            lens={data?.lens ?? { kind: "early", days: 0, need: 7 }} lang={lang} onCheckin={onCheckin} />
        </FadeIn>
        <FadeIn delay={300}>
          <BudgetCard totalUg={data?.rec.totalUg ?? 0} profile={settings.profile}
            lang={lang} onProfile={onProfile} />
        </FadeIn>
      </ScrollView>
      {/* the pinned verb — the dosimeter's one outbound action, always
          reachable (rides the sheet's own slide, not the map's space) */}
      <View style={[ss.ctaBar, { paddingBottom: insets.bottom + 10 }]}>
        <TravelCta lang={lang} onGo={onGo} />
      </View>
    </View>
  );
}

const HomeSheet = React.memo(HomeSheetInner);

/** The home surface — the app's resting state. Mounts as a paper sheet
 *  over the always-live map; `visible` false slides it back down and
 *  unmounts after the exit timing (the same JS-driver pattern as the
 *  old day sheet — RN Modal's native present/dismiss segfaults this stack). */
function HomeScreenInner({ visible, data, lang, settings, ambientUg, onGo, onMenu, onMap, onCity, onTrips, onProfile, onCheckin }: {
  visible: boolean;
  data: DayData | null;
  lang: Lang;
  settings: ShellSettings;
  ambientUg: number | null;
  onGo: () => void;
  onMenu: () => void;
  onMap: () => void;
  onCity: () => void;
  onTrips: () => void;
  onProfile: (p: ShellSettings["profile"]) => void;
  onCheckin: (c: Omit<Checkin, "ts">) => void;
}) {
  bump("home.HomeScreen");
  const reduceMotion = useReduceMotion();
  const [show, setShow] = useState(visible);
  const [enter] = useState(() => new Animated.Value(visible ? 1 : 0));
  const [enterTy] = useState(() => enter.interpolate({ inputRange: [0, 1], outputRange: [44, 0] }));
  /* mount is render-phase derived state (React's sanctioned adjust-during-
     render): the exit unmount happens inside the timing callback, async. */
  if (visible && !show) setShow(true);
  useEffect(() => {
    if (visible) {
      enter.setValue(reduceMotion ? 1 : 0);
      if (!reduceMotion) {
        jank("enter.home");
        Animated.spring(enter, { toValue: 1, damping: 24, stiffness: 240, useNativeDriver: true }).start();
      }
      return;
    }
    /* exit: a short settle-down, then unmount — the sheet pattern inverted */
    const anim = Animated.timing(enter, {
      toValue: 0, duration: reduceMotion ? 0 : 150, useNativeDriver: true,
    });
    anim.start(({ finished }) => { if (finished) setShow(false); });
    return () => anim.stop();
  }, [visible, enter, reduceMotion]);

  if (!show) return null;
  return (
    <View style={ss.backdrop}>
      <StatusBar style="dark" />
      <Animated.View style={{ flex: 1, opacity: enter, transform: [{ translateY: enterTy }] }}>
        <HomeSheet data={data} lang={lang} settings={settings} ambientUg={ambientUg}
          onGo={onGo} onMenu={onMenu} onMap={onMap} onCity={onCity} onTrips={onTrips}
          onProfile={onProfile} onCheckin={onCheckin} />
      </Animated.View>
    </View>
  );
}

export const HomeScreen = React.memo(HomeScreenInner);

export default HomeScreen;

const ss = StyleSheet.create({
  /* Android honours elevation over sibling order — without this the map's
     floating chrome (freshness chip, FABs, search bar) pokes through the
     paper. 24 sits above V2Elev.sheet(12)/pop(18); iOS ignores it. */
  backdrop: { ...StyleSheet.absoluteFill, backgroundColor: "transparent", elevation: 24 },
  home: {
    flex: 1,
    backgroundColor: V2T.bg,
  },
  homeHead: {
    flexDirection: "row", alignItems: "center", justifyContent: "space-between",
    paddingHorizontal: 20, paddingBottom: 6,
  },
  brand: { color: V2T.text, fontSize: 21, letterSpacing: 0.2 },
  brandSub: {
    color: V2T.text3, fontSize: V2Type.micro, letterSpacing: 1.4,
    textTransform: "uppercase", marginTop: 3,
  },
  homeMenuBtn: {
    width: 40, height: 40, borderRadius: V2Radius.row,
    alignItems: "center", justifyContent: "center",
    backgroundColor: V2T.surface, borderWidth: 1, borderColor: V2T.hairline,
  },
  menuBars: { gap: 4 },
  menuBar: { width: 18, height: 2, borderRadius: 1, backgroundColor: V2T.text2 },
  flex: { flex: 1 },
  content: { paddingHorizontal: 16, paddingTop: 6, gap: 14 },

  /* the hero — a chunky tinted card that owns the screen. The surface
     itself carries the day's dose severity at 18% (quiet days stay paper);
     everything inside is components, not lines. */
  heroCard: {
    ...V2Elev.card,
    backgroundColor: V2T.surface,
    borderWidth: 1, borderColor: V2T.hairline,
    borderRadius: 24,
    paddingHorizontal: 18, paddingTop: 18, paddingBottom: 16,
  },
  heroEyebrow: {
    color: V2T.text2, fontSize: V2Type.label, marginBottom: 6,
  },
  heroNum: { fontSize: 88, lineHeight: 92, letterSpacing: -2 },
  heroNumRow: { flexDirection: "row", alignItems: "flex-end", gap: 6, flex: 1 },
  heroUg: { color: V2T.text2, fontSize: V2Type.title, paddingBottom: 14 },
  heroMainRow: { flexDirection: "row", alignItems: "flex-end", justifyContent: "space-between" },
  heroGaugeCol: { alignItems: "center", paddingBottom: 8 },
  gaugeWrap: { width: 76, height: 76 },
  gaugeCenter: { ...StyleSheet.absoluteFill, alignItems: "center", justifyContent: "center" },
  gaugePct: { fontSize: 11, color: V2T.text2 },
  heroOfBudget: { color: V2T.text2, fontSize: 10, marginTop: 6, letterSpacing: 0.3 },
  heroThin: { color: V2T.text2, fontSize: V2Type.secondary, lineHeight: 21, marginTop: 8 },
  /* the sparse hero — the ambient truth where the personal number can't
     stand yet: faint field arc, labelled read, count progress */
  sparseArc: { opacity: 0.62, marginTop: 4, marginBottom: 6 },
  sparseAmbRow: { flexDirection: "row", alignItems: "center", gap: 8, marginTop: 6 },
  sparseAmb: { color: V2T.text2, fontSize: V2Type.label },
  sparseProgRow: { flexDirection: "row", alignItems: "center", gap: 5, marginTop: 12 },
  sparseProgLbl: { color: V2T.text2, fontSize: 10, marginLeft: 6, letterSpacing: 0.3 },
  heroStatRow: { flexDirection: "row", alignItems: "center", gap: 14, marginTop: 12 },
  heroStat: { color: V2T.text2, fontSize: V2Type.label },
  heroAmb: { flexDirection: "row", alignItems: "center", gap: 6 },
  heroWeekRow: { flexDirection: "row", alignItems: "center", gap: 5, marginTop: 14 },
  heroWeekLbl: { color: V2T.text2, fontSize: 10, marginLeft: 6, letterSpacing: 0.3 },

  /* skeleton → content morph */
  skelEyebrow: { width: 150, height: 13, borderRadius: 6, backgroundColor: V2T.surface2, marginBottom: 12 },
  skelHero: { width: 230, height: 88, borderRadius: 8, backgroundColor: V2T.surface2 },
  skelLine: { width: "70%", height: 13, borderRadius: 6, backgroundColor: V2T.surface2, marginTop: 14 },

  /* the travel verb — the ONE primary CTA: solid ink pill */
  cta: {
    ...V2Elev.card,
    flexDirection: "row", alignItems: "center", gap: 10,
    backgroundColor: V2T.text,
    borderRadius: V2Radius.pill, height: 56, paddingHorizontal: 20,
  },
  /* its pinned footer bar — outside the scroll so the verb is always
     reachable; a whisper of a divider, not a rail */
  ctaBar: {
    paddingHorizontal: 20, paddingTop: 10,
    backgroundColor: V2T.bg,
    borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: V2T.line,
  },
  ctaTxt: { flex: 1, color: V2T.bg, fontSize: V2Type.body },
  ctaArrow: {
    width: 30, height: 30, borderRadius: 15,
    backgroundColor: "rgba(250,250,247,0.16)",
    alignItems: "center", justifyContent: "center",
  },

  /* feature doors — the icon-tile row into the other rooms */
  doorRow: { flexDirection: "row", gap: 10 },
  door: {
    flex: 1, borderRadius: 18, borderWidth: 1,
    paddingHorizontal: 12, paddingVertical: 12, gap: 9,
    minHeight: 84, justifyContent: "space-between",
  },
  doorWell: {
    width: 34, height: 34, borderRadius: 12,
    alignItems: "center", justifyContent: "center",
  },
  doorLabel: { fontSize: V2Type.label, letterSpacing: 0.1 },

  card: {
    ...V2Elev.card,
    backgroundColor: V2T.surface,
    borderWidth: 1, borderColor: V2T.hairline,
    borderRadius: V2Radius.card,
    paddingHorizontal: 16, paddingTop: 16, paddingBottom: 16,
  },
  /* the card's own word — a warm label, never an uppercase micro eyebrow */
  cardTitle: {
    color: V2T.text, fontSize: V2Type.secondary, marginBottom: 10,
  },
  finePrint: { color: V2T.text3, fontSize: V2Type.micro, marginTop: 10 },

  /* the move — decision felt at serif scale, evidence lives in chips */
  moveLine: { color: V2T.text, fontSize: 21, lineHeight: 28, marginBottom: 10 },
  sparkLabels: { position: "relative", height: 13, marginTop: 2 },
  sparkHr: { position: "absolute", top: 0, width: 40, color: V2T.text3, fontSize: 9, textAlign: "center" },
  winChip: {
    flexDirection: "row", alignItems: "center", gap: 8, marginTop: 8,
    borderRadius: V2Radius.row, borderWidth: 1,
    paddingHorizontal: 10, paddingVertical: 8, alignSelf: "flex-start",
  },
  winChipTxt: { color: V2T.text, fontSize: V2Type.label },
  mRow: { flexDirection: "row", alignItems: "center", gap: 8, marginTop: 6 },
  mLine: { color: V2T.text2, fontSize: V2Type.secondary },
  noteLine: { color: V2T.text2, fontSize: V2Type.secondary, lineHeight: 21, marginTop: 8 },

  /* the days ahead — chunky band-washed cells */
  oaHead: {
    flexDirection: "row", alignItems: "center", justifyContent: "space-between",
    marginBottom: 10,
  },
  oaUnit: { color: V2T.text3, fontSize: V2Type.label },
  oaRow: { flexDirection: "row", gap: 8 },
  oaCell: {
    flex: 1, borderWidth: 1, borderColor: V2T.hairline,
    borderRadius: 15, backgroundColor: V2T.surface,
    paddingHorizontal: 6, paddingTop: 10, paddingBottom: 9,
    alignItems: "center",
  },
  oaCellSel: { borderColor: V2T.accent, borderWidth: 1.5 },
  oaDay: { color: V2T.text3, fontSize: 10 },
  oaMidRow: { flexDirection: "row", alignItems: "center", gap: 5, marginTop: 5 },
  oaMid: { color: V2T.text, fontSize: V2Type.body, lineHeight: 22 },
  oaSub: { color: V2T.text3, fontSize: 9, marginTop: 2, minHeight: 12 },
  oaMark: { color: V2T.accentInk, fontSize: 9, marginTop: 2, minHeight: 12 },
  oaDetail: {
    marginTop: 12, paddingTop: 12,
    borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: V2T.line,
  },
  oaDetailHead: { color: V2T.text3, fontSize: V2Type.micro, letterSpacing: 1.0 },
  oaDetailNote: { color: V2T.text3, fontSize: V2Type.micro, marginTop: 6 },

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
  arcHr: { color: V2T.text3, fontSize: 9, marginTop: 4, height: 12 },
  partsTitle: {
    color: V2T.text3, fontSize: V2Type.label,
    marginTop: 16, marginBottom: 6,
  },
  partChip: {
    flexDirection: "row", alignItems: "center", gap: 10,
    backgroundColor: V2T.surface2, borderRadius: V2Radius.row,
    paddingHorizontal: 10, paddingVertical: 9, marginTop: 6,
  },
  partSpine: { width: 4, height: 18, borderRadius: 2 },
  partLabel: { color: V2T.text, fontSize: V2Type.secondary, flex: 1 },
  partUg: { color: V2T.text, fontSize: V2Type.label },

  /* lens — facets answer in chunky pills */
  lensSub: { color: V2T.text2, fontSize: V2Type.label, marginBottom: 10, lineHeight: 19 },
  facetRow: {
    flexDirection: "row", alignItems: "center", justifyContent: "space-between",
    paddingVertical: 7,
  },
  facetLabel: { color: V2T.text, fontSize: V2Type.secondary },
  facetOpts: { flexDirection: "row", gap: 6 },
  opt: {
    paddingHorizontal: 12, paddingVertical: 9,
    borderRadius: V2Radius.row, borderWidth: 1, borderColor: V2T.hairline,
    backgroundColor: V2T.surface,
  },
  optSel: { backgroundColor: V2T.accentWash, borderColor: V2T.accent, borderWidth: 1.5 },
  optTxt: { color: V2T.text2, fontSize: V2Type.label },
  optTxtSel: { color: V2T.accentInk },
  verdict: { color: V2T.text2, fontSize: V2Type.label, marginTop: 12 },

  weekDot: { width: 9, height: 9, borderRadius: 4.5 },

  /* budget — a real track, a segment row for the profile */
  budgetBar: {
    height: 8, borderRadius: 4, backgroundColor: V2T.surface2,
    overflow: "hidden", marginBottom: 10,
  },
  budgetFill: { height: 8, borderRadius: 4 },
  budgetLine: { color: V2T.text, fontSize: V2Type.secondary },
  profileRow: {
    flexDirection: "row", gap: 4, marginTop: 14,
    backgroundColor: V2T.surface2, borderRadius: V2Radius.pill, padding: 3,
  },
  segOpt: { flex: 1, alignItems: "center", paddingVertical: 9, borderRadius: V2Radius.pill },
  segOptSel: { backgroundColor: V2T.text },
  segTxt: { color: V2T.text2, fontSize: V2Type.label },
  segTxtSel: { color: V2T.bg },

  /* the peek card on the idle map — the door back home */
  peek: {
    ...V2Elev.float,
    marginHorizontal: 16,
    backgroundColor: V2T.glassDeep,
    borderWidth: 1, borderColor: V2T.hairline,
    borderRadius: V2Radius.card,
    paddingHorizontal: 16, paddingTop: 12, paddingBottom: 13,
  },
  peekTop: { flexDirection: "row", alignItems: "center", justifyContent: "space-between" },
  peekTopRight: { flexDirection: "row", alignItems: "center", gap: 8 },
  peekAmb: { fontSize: V2Type.label },
  peekEyebrow: {
    color: V2T.text2, fontSize: V2Type.label,
  },
  peekEmpty: { color: V2T.text2, fontSize: V2Type.label, marginTop: 6 },
  peekRow: { flexDirection: "row", alignItems: "flex-end", gap: 8, marginTop: 4 },
  peekNum: { color: V2T.text, fontSize: 40, lineHeight: 44 },
  peekUnit: { color: V2T.text2, fontSize: V2Type.label, paddingBottom: 5 },
  peekDots: { flexDirection: "row", gap: 4, flex: 1, justifyContent: "flex-end", paddingBottom: 9 },
});
