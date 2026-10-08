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
 *   5. your week — the last 7 counted days as band-washed cells
 *      (WeekStrip); a tap unfolds that day's own arc + accumulators.
 *   6. the days ahead — /v2/outlook's own fold, ≤5 cells, ghosted past the
 *      live anchor's reach; a dead endpoint hides the card.
 *   7. the symptom lens — breath/eyes/energy single-tap check-in, stored
 *      on this phone only.
 *   8. quiet links — the air map, Delhi today, your trips.
 *   9. your budget — quiet profile ceiling, honest over/under flag.
 *
 *  Copy rule for the whole surface: "same life, cheaper for lungs" — a card
 *  that can't name a cheaper window/mode shows the number plainly, never a
 *  restriction.
 */

import React, { useEffect, useRef, useState } from "react";
import {
  Animated,
  Easing,
  LayoutAnimation,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { StatusBar } from "expo-status-bar";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import Svg, { Circle, Defs, LinearGradient, Path, Rect, Stop } from "react-native-svg";
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
  doseDotColor,
  doseTierIdx,
  fam,
  famMono,
  famMonoText,
  famSerif,
} from "../theme";
import { approx, clockLabel, doseUgRound, feltKeyForBand, hourLabel, t, wireClockLabel, type Lang, type StringKey } from "../i18n/strings";
import { CountUp, FadeIn, Quiet, pressFx } from "../ui";
import { Icon, type Glyph } from "../icons";
import { holdMapDraw } from "../map/drawHold";
import { DYNAMIC_TYPE, useReduceMotion } from "../a11y";
import { tap, tick } from "../haptics";
import { inNcr } from "../components/shell/net";
import { warm as warmSearchIndex } from "../search/t0";
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
import { getDay } from "../store/daysum";
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
import { PROFILE_BUDGET_UG, WHO_DAILY_UG, type ShellSettings } from "../components/shell/settings";
import { fetchCity } from "../api/city";
import { causeNote, type CauseNoteFields } from "../store/events-core";
import { CheckinSheet } from "../components/shell/CheckinSheet";
import { TourTarget, useMeasureTarget, useTourScroller, tourScrolled } from "../components/shell/CoachTour";
import { BandScale } from "../components/BandScale";
import { HourArc } from "../components/shell/HourArc";
import { WeekStrip, type WeekDay } from "../components/shell/WeekStrip";
import { WeekSheet } from "../components/shell/WeekSheet";
import {
  compactHours,
  dayLabel,
  fieldAgeLine,
  outlookCaption,
  shortDate,
} from "../components/shell/daywords";
import { bump, jank } from "../perf";

/* ---------------- the hook: one assemble of the day's data --------------- */

export type DayData = {
  /** today's reconstruction — never null once disk is read */
  rec: DayReconstruction;
  /** last 7 local days (oldest→today) for the week strip: the flattened
      dose for bars/dots, the day's reconstruction for the tap detail */
  week: WeekDay[];
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

      /* week: today's rec is live; the six finished days come from the
         day-sum rollup — each was reconstructed once when its inputs
         last changed and is sealed on disk, instead of every assemble
         re-deriving it from the full sample+trip history (pocket-engine
         lane: this used to cost one reconstructDay per finished day on
         EVERY refresh). */
      const week: DayData["week"] = [];
      for (let i = 6; i >= 0; i--) {
        const d = new Date(now);
        d.setDate(d.getDate() - i);
        const k = dayKey(d.getTime());
        const r = i === 0 ? rec : (await getDay(k, lang)).rec;
        week.push({ day: k, ug: r.totalUg, rec: r });
      }

      // the lens needs a dose per checkin's *previous* day, counted only
      // where coverage was real enough to say so — same rollup: up to
      // ~120 days that used to each rescan every sample+trip on every
      // assemble now read one sealed record each
      const doseByDay: Record<string, number> = {};
      const keys = new Set<string>();
      for (const k of Object.keys(checkins)) {
        const d = new Date(`${k}T00:00:00`);
        d.setDate(d.getDate() - 1);
        keys.add(dayKey(d.getTime()));
      }
      for (const k of keys) {
        const r = (await getDay(k, lang)).rec;
        if (r.coveredMin >= 30 || r.parts.length > 0) doseByDay[k] = r.totalUg;
      }

      const outside = !inNcr(lat, lon);
      if (!live) return;
      /* disk-first paint: the hero + arc are local truths — they must not
         wait on the forecast fetches. On a dead network those take the
         full timeout and the hero would sit as skeleton blocks the whole
         time. Cards that need the field (the move, days ahead) mount
         when it lands — they already treat null as "not yet".
         On re-assembles (a fresh ambient sample, a check-in write, a
         lang switch) the previous field cards stay mounted while their
         refetch is in flight — nulling curve/outlook here used to unmount
         both cards for a beat, collapsing ~600 px of the scroll list and
         visibly reloading the whole surface every few minutes (jank
         lane: the owner's "numbers should update in place" complaint). */
      setData((prev) => ({
        rec, week,
        curve: prev?.curve ?? null,
        outside,
        outlook: prev?.outlook ?? null,
        lens: symptomLens(checkins, doseByDay),
        checkin: checkins[today] ?? null,
        curveAgeS: prev?.curveAgeS ?? null,
      }));
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

/* an absolute wall-clock hour → the shared hour-word label ("9pm" /
   "9 बजे") — the move card's local clock predated the clock helpers */
const fmtHr = (h: number, lang: Lang) => hourLabel(h * 3600000, lang);

/* ---------------- the move (the morning card, promoted) ---------------- */

function SparklineInner({ series, lang }: { series: (number | null)[]; lang: Lang }) {
  bump("home.Sparkline");
  const [w, setW] = useState(0);
  const H = 44, PAD = 8;
  const vals = series.filter((v): v is number => v != null);
  const max = Math.max(...vals, 1), min = 0;
  const span = Math.max(1, max - min);
  const x = (i: number) => PAD + (w - 2 * PAD) * (series.length <= 1 ? 0 : i / (series.length - 1));
  const y = (v: number) => H - 6 - (H - 10) * ((v - min) / span);
  /* one rounded column per hour, band-coloured by its forecast — the
     day reads as a strip of cells; a failed hour is an empty stub,
     never a guess */
  const slot = series.length > 0 ? (w - 2 * PAD) / series.length : 0;
  const bw = Math.max(3, Math.min(10, slot - 4));
  return (
    <View onLayout={(e) => setW(e.nativeEvent.layout.width)}>
      {w > 0 && (
        <Svg width={w} height={H + 14}>
          {series.map((v, i) => {
            const top = v == null ? H - 4 : Math.min(y(v), H - 6);
            return (
              <Rect key={i} x={x(i) - bw / 2} y={top} width={bw} height={H - top}
                rx={bw / 2} fill={v == null ? V2T.surface3 : (bandColor(v) ?? V2T.text4)} />
            );
          })}
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
function SparseAirArcInner({ series, color }: { series: (number | null)[]; color: string }) {
  bump("home.SparseAirArc");
  const [w, setW] = useState(0);
  const H = 64, PAD = 4;
  const vals = series.filter((v): v is number => v != null);
  const max = Math.max(...vals, 1), min = Math.min(...vals, 0);
  const span = Math.max(1, max - min);
  const x = (i: number) => PAD + (w - 2 * PAD) * (series.length <= 1 ? 0 : i / (series.length - 1));
  const y = (v: number) => H - 6 - (H - 16) * ((v - min) / span);
  /* contiguous runs only — a failed hour is a gap, never a guess; each
     run is a smoothed curve (midpoint quadratics) with its own wash */
  const runs: { line: string; area: string }[] = [];
  let pts: [number, number][] = [];
  const flush = () => {
    if (pts.length > 1) {
      let d = `M${pts[0][0].toFixed(1)} ${pts[0][1].toFixed(1)}`;
      for (let k = 1; k < pts.length; k++) {
        const [px, py] = pts[k - 1], [cx, cy] = pts[k];
        const mx = (px + cx) / 2, my = (py + cy) / 2;
        d += ` Q${px.toFixed(1)} ${py.toFixed(1)} ${mx.toFixed(1)} ${my.toFixed(1)}`;
      }
      const last = pts[pts.length - 1];
      d += ` L${last[0].toFixed(1)} ${last[1].toFixed(1)}`;
      runs.push({ line: d, area: `${d} L${last[0].toFixed(1)} ${H} L${pts[0][0].toFixed(1)} ${H} Z` });
    }
    pts = [];
  };
  series.forEach((v, i) => { if (v == null) flush(); else pts.push([x(i), y(v)]); });
  flush();
  const first = series.findIndex((v) => v != null);
  return (
    <View onLayout={(e) => setW(e.nativeEvent.layout.width)} style={ss.sparseArc}>
      {w > 0 && (
        <Svg width={w} height={H}>
          <Defs>
            <LinearGradient id="arcWash" x1="0" y1="0" x2="0" y2="1">
              <Stop offset="0" stopColor={color} stopOpacity={0.16} />
              <Stop offset="1" stopColor={color} stopOpacity={0} />
            </LinearGradient>
          </Defs>
          {runs.map((r, i) => (
            <React.Fragment key={i}>
              <Path d={r.area} fill="url(#arcWash)" />
              <Path d={r.line} stroke={color} strokeWidth={2} strokeLinecap="round" fill="none" opacity={0.75} />
            </React.Fragment>
          ))}
          {first >= 0 && (
            <Circle cx={x(first)} cy={y(series[first] as number)} r={4} fill={color} />
          )}
        </Svg>
      )}
    </View>
  );
}

const SparseAirArc = React.memo(SparseAirArcInner);

/* The CPCB band words live in strings.ts (band_*); index = the band the
 *  client already computes on a mid (theme.bandIdx — same CPCB breaks
 *  the server's districts.cpcb_band applies). */
const MOVE_BAND_KEYS: StringKey[] = [
  "band_good", "band_satisfactory", "band_moderate",
  "band_poor", "band_veryPoor", "band_severe",
];

/** The numeral's baseline — the landing .hnum rule, translated: a fine
 *  band-inked line under the readout that breathes on a slow sine (a
 *  dosimeter is a breathing thing). Reduce Motion: a static whisper. */
function BreathLineInner({ color }: { color: string }) {
  const reduce = useReduceMotion();
  const [v] = useState(() => new Animated.Value(0));
  useEffect(() => {
    if (reduce) return;
    const loop = Animated.loop(Animated.sequence([
      Animated.timing(v, { toValue: 1, duration: 2200, easing: Easing.inOut(Easing.sin), useNativeDriver: true }),
      Animated.timing(v, { toValue: 0, duration: 2200, easing: Easing.inOut(Easing.sin), useNativeDriver: true }),
    ]));
    loop.start();
    return () => loop.stop();
  }, [v, reduce]);
  return (
    <Animated.View style={[ss.breathLine, {
      backgroundColor: color,
      opacity: reduce ? 0.16 : v.interpolate({ inputRange: [0, 1], outputRange: [0.10, 0.32] }),
    }]} />
  );
}

const BreathLine = React.memo(BreathLineInner);

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
      /* served window labels are 24h wire clocks — print them in the
         app's 12h convention ("~6am–9am") */
      const win = wireClockLabel(
        `~${srv.cleanLabel ?? ""}-${srv.cleanEndLabel ?? ""}`, lang);
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
      const b = last == null ? "" : t(MOVE_BAND_KEYS[last], lang);
      /* "~Nh of today left" is only honest when the day itself is nearly
         done — at 11 AM a 2-hour serve is a truncated forecast horizon,
         not a short day, and the line read as a lie (audit #10: it fired
         at 10:56). Gate the phrasing on the real IST clock: when more
         of the day remains than the card can see, name the card's
         reach instead of the day's end. */
      const istHour = (Date.now() / 3600000 + 5.5) % 24;
      const istLeft = 24 - istHour;
      return istLeft <= mids.length + 1.5
        ? t("moveDec_short", lang, { n: mids.length, b })
        : t("moveDec_cardShort", lang, { n: mids.length, b });
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
  /* served window labels arrive as 24h wire clocks — render them in
     the same 12h words the client-computed ones use */
  const heavyF = srv?.heavyLabel
    ? wireClockLabel(srv.heavyLabel, lang)
    : (heavy ? fmtHr(heavy.from + nowHour(), lang) : "");
  const heavyT = srv?.heavyEndLabel
    ? wireClockLabel(srv.heavyEndLabel, lang)
    : (srv?.heavyLabel ? "" : heavy ? fmtHr(heavy.to + nowHour(), lang) : "");
  const cleanF = srv?.cleanLabel
    ? wireClockLabel(srv.cleanLabel, lang)
    : (clean ? fmtHr(clean.from + nowHour(), lang) : "");
  const cleanT = srv?.cleanEndLabel
    ? wireClockLabel(srv.cleanEndLabel, lang)
    : (srv?.cleanLabel ? "" : clean ? fmtHr(clean.to + nowHour(), lang) : "");
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
  /* the card has an opinion — its wash IS the verdict: a real clean
     window tints the whole card that window's band (hopeful); a verdict
     with no window still gets a warm sand whisper; only a card that
     couldn't say anything stays bare paper */
  const cleanIdx = clean != null ? bandIdx(clean.conc) : null;
  const moveBg = cleanIdx != null ? bandWashIdx(cleanIdx)
    : (felt != null || flat ? V2Tint.sand.wash : V2T.surface);
  const moveEdge = cleanIdx != null ? `${bandInkIdx(cleanIdx)}33`
    : (felt != null || flat ? `${V2Tint.sand.ink}30` : V2T.hairline);
  return (
    <View style={[ss.card, { backgroundColor: moveBg, borderColor: moveEdge }]}>
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
            /* the heavy/clean windows — the band lives in the dot only */
            <View style={ss.winChip}>
              <BandDot conc={heavy.conc} />
              <Text {...DYNAMIC_TYPE} style={[ss.winChipTxt, NUM, { fontFamily: mtext(lang) }]}>
                {t(heavyT ? "dayMorningHeavy" : "dayMorningHeavyFrom", lang, {
                  f: heavyF,
                  t: heavyT,
                  c: Math.round(heavy.conc),
                })}
              </Text>
            </View>
          )}
          {clean && (
            <View style={ss.winChip}>
              <BandDot conc={clean.conc} />
              <Text {...DYNAMIC_TYPE} style={[ss.winChipTxt, NUM, { fontFamily: mtext(lang) }]}>
                {t(cleanT ? "dayMorningClean" : "dayMorningCleanFrom", lang, {
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

function DaysAheadCardInner({ outlook, lang }: { outlook: Outlook | null; lang: Lang }) {
  bump("home.DaysAhead");
  const reduceMotion = useReduceMotion();
  const [openKey, setOpenKey] = useState<string | null>(null);
  if (!outlook || outlook.days.length === 0) return null;
  const days = outlook.days.slice(0, 5);
  const open = days.find((d) => d.date_ist === openKey) ?? null;
  const anyLo = days.some((d) => d.confidence === "lo");
  const caption = outlookCaption(outlook, lang);
  /* the hero's air-age line already anchors this field's freshness on
     home — repeat it only when it changes what a plan relies on
     (stale), never as an echo (audit #14's double statement) */
  const ageLine = outlook.fieldStale
    ? fieldAgeLine(outlook.fieldAgeS, outlook.fieldStale, lang) : null;
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
          /* stone cells; the band lives only in the dot and the numeral,
             so five days never read as five pastel tiles */
          const cellBg = sel ? V2T.surface : V2T.surface2;
          /* the numeral owns the cell in full ink — band-ink at 85%
             washed the figure into the tinted fill; the band lives on
             the wash, the dot and the day label instead */
          const midCol = bi != null ? bandInkIdx(bi) ?? V2T.text : V2T.text;
          const dayCol = V2T.text3;
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
                { backgroundColor: cellBg },
                d.confidence === "lo" && { opacity: 0.62 }, // ghosted — past the live anchor's reach
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
            {dayLabel(open.label, lang)} · {shortDate(open.date_ist, lang)}
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
                {t(open.cleanest_window.end_label
                  ? "dayMorningClean" : "dayMorningCleanFrom", lang, {
                  f: wireClockLabel(open.cleanest_window.start_label ?? "", lang),
                  t: wireClockLabel(open.cleanest_window.end_label ?? "", lang),
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
              {t("dayOutlookHeavyHours", lang, { h: compactHours(open.heavy_hours_ist, lang) })}
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

/* the arc itself lives in components/shell/HourArc.tsx — extracted so the
   week strip's tap-a-day detail renders the same day view this card owns
   for today (weekview lane) */

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

/* ---------------- your week ---------------- */

/* the week card lives in components/shell/WeekStrip.tsx — the
   calendar-like day-strip the owner asked for: band-washed day cells,
   tap-a-day detail; same truth rules as the inline card it replaced
   (weekview lane) */

/* ---------------- the symptom lens ---------------- */

/* the check-in card lives in shell/CheckinSheet.tsx (motion-v3 moved it
   out so the sheet components own the pill springs) */

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
          backgroundColor: doseDotColor(totalUg, budget),
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
        {t("budgetProfileQ", lang, { b: budget })}
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
function DayPeekInner({ data, lang, onOpen, ambientUg, budgetUg = PROFILE_BUDGET_UG.general }: {
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
      accessibilityHint={t("peekOpenHint", lang)}
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
  const insets = useSafeAreaInsets();
  /* a clock that tells the time — the header re-reads it each second
     (a 30 s tick let the greeting lag a half-minute after every
     minute's rollover — audit #12) */
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    const iv = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(iv);
  }, []);
  const hr = now.getHours();
  const greetKey: StringKey = hr < 5 || hr >= 21 ? "homeGreetNight"
    : hr < 12 ? "homeGreetMorning" : hr < 17 ? "homeGreetAfternoon" : "homeGreetEvening";
  const greet = t(greetKey, lang);
  const cap = (x: string) => (lang === "en" ? x.charAt(0).toUpperCase() + x.slice(1) : x);
  const title = cap(greet);
  return (
    <View style={[ss.homeHead, { paddingTop: insets.top + 6 }]}>
      <View style={ss.flex}>
        <Text {...DYNAMIC_TYPE} numberOfLines={1} style={[ss.brand, { fontFamily: famSerif(lang, "med") }]}>
          {title}
        </Text>
        <Text {...DYNAMIC_TYPE} style={[ss.brandSub, NUM, { fontFamily: fam(lang, "reg") }]}>
          {t("cityName", lang)} · {cap(dayLabel(WEEKDAY_EN[now.getDay()], lang))} · {clockLabel(now, lang)}
        </Text>
      </View>
      <Pressable onPress={() => { tick(); onMenu(); }} hitSlop={10}
        accessibilityRole="button" accessibilityLabel={t("a11yMenu", lang)}
        style={({ pressed }) => [ss.homeMenuBtn, pressFx(pressed)]}>
        <View style={ss.menuBars}>
          {[0, 1].map((k) => <View key={k} style={ss.menuBar} />)}
        </View>
      </Pressable>
    </View>
  );
}

const HomeHeader = React.memo(HomeHeaderInner);


/** The hero — WHOOP's one-score compression (design-refs §3): ≈N µg
 *  breathed at display scale, coloured by the day's fraction of budget,
 *  with the covered-hours and outside-now reads as tier-2 evidence.
 *  WHO_DAILY_UG (the WHO 2021 24-h PM2.5 denominator behind the
 *  "× WHO" lines) comes from shell/settings — single-sourced. */

/** What the app's /aqi poll knows about the ambient number beyond its
 *  value — the hero's honesty lines are honest only with it. */
export type AmbientMeta = {
  /** km to the nearest real instrument behind the field — the wire's
      nearest_station_km (a NAMED monitor, never a model fill point).
      null = no live instrument fed the field this read */
  km: number | null;
  /** true when the read queried the user's own GPS fix — false means
      the Delhi-centre fallback answered (location off/no fix yet) */
  atGps: boolean;
  /** the US-AQI equivalent of the same air — the number other apps
      quote, served so the figure can prove itself */
  usAqi: number | null;
  /** the point sits past the monitored field's edge — the number is
      the nearest edge's evidence, not a local read */
  beyondEdge: boolean;
  /** the gazetteer locality the read is for (t0 areaNear at the user's
      own fix) — 'Karol Bagh', not just 'your location'. null when the
      index can't name it honestly */
  place?: string | null;
};

function HeroBlockInner({ data, budgetUg, ambientUg, ambientMeta, fieldAgeS, fieldStale, lang }: {
  data: DayData | null; budgetUg: number; ambientUg: number | null; lang: Lang;
  /** provenance of the ambient read — the hero's "where from" lines */
  ambientMeta?: AmbientMeta | null;
  /** the live field's own age/stale verdict (the /aqi block) — the air
      number's 'as of'; null when no read has landed yet */
  fieldAgeS?: number | null;
  fieldStale?: boolean | null;
}) {
  bump("home.HeroBlock");
  /* tour target — the sparse day's "counting up" row is the ledger's
     first-run shape (the real DayCard mounts only once a day counts) */
  const { node: ledgerNode, onLayout: ledgerLayout } = useMeasureTarget("heroLedger");
  if (!data) {
    /* skeleton — blocks morph to content when the disk read lands */
    return (
      <View style={ss.hero}>
        <View style={ss.skelEyebrow} />
        <View style={ss.skelHero} />
        <View style={ss.skelLine} />
      </View>
    );
  }
  const rec = data.rec;
  const ug = rec.totalUg;
  const tier = doseTierIdx(ug, budgetUg);
  /* the number in the eyebrow slot is EITHER the live /aqi point read at
     the device's own position OR the forecast cell's near-term mid —
     never one labelled as the other (home-truth: the owner caught the
     unlabeled forecast fallback reading as "the air around you") */
  const airNow = ambientUg ?? data.curve?.series.find((v) => v != null) ?? null;
  const airSrc = ambientUg != null ? "live"
    : data.curve?.series.some((v) => v != null) ? "forecast" : null;
  const airNowIdx = bandIdx(airNow);
  /* the ambient read's own 'as of' — the /aqi field block's age, not
     the day-curve's cached stamp */
  const airAgeLine = airSrc === "live"
    ? fieldAgeLine(fieldAgeS, fieldStale, lang) : null;
  const h = Math.floor(rec.coveredMin / 60), m = rec.coveredMin % 60;
  const maxW = Math.max(...data.week.map((w) => w.ug), 1);
  const weekCounted = data.week.filter((w) => w.ug > 0).length >= 2;
  /* the hero is a statement, not a card: number → felt word → reference.
     Counted day: your dose, its felt tier, its share of your budget (and
     yesterday when yesterday was counted). Sparse day: the air at your
     cell, its felt band, its multiple of the WHO daily guideline. */
  const counted = !rec.thin;
  const idx = counted ? (tier ?? 0) : airNowIdx;
  const ink = idx != null ? (bandInkIdx(idx) ?? V2T.text) : V2T.text;
  const felt = idx != null ? t(feltKeyForBand(idx), lang) : null;
  const yday = data.week.length >= 2 ? data.week[data.week.length - 2].ug : 0;
  let ref: string | null = null;
  let ref2: string | null = null;
  if (counted) {
    ref = budgetUg > 0 ? t("refBudget", lang, { p: Math.round((ug / budgetUg) * 100) }) : null;
    if (yday > 0) {
      const d = Math.round(ug - yday);
      if (d !== 0) ref2 = t(d > 0 ? "refYesterdayMore" : "refYesterdayLess", lang, { n: Math.abs(d) });
    }
  } else if (airNow != null) {
    const x = airNow / WHO_DAILY_UG;
    ref = x > 1.05
      ? t("refWhoOver", lang, { x: x >= 10 ? Math.round(x) : x.toFixed(1) })
      : t("refWhoUnder", lang);
  }
  /* the instrument's citation — locality, monitor distance and field age
     as ONE dot-separated provenance line under the verdict (the landing's
     statusline), not two stacked footnotes */
  const provBase = !counted && airSrc === "live" && ambientMeta != null
    ? (ambientMeta.atGps === false
        ? t("homeAirCityHint", lang)
        : ambientMeta.beyondEdge
          ? t("homeAirEdge", lang)
          : ambientMeta.km != null
            ? (ambientMeta.place
                ? t("homeAirMetaPlace", lang, { p: ambientMeta.place, k: ambientMeta.km })
                : t("homeAirMeta", lang, { k: ambientMeta.km }))
            : (ambientMeta.place
                ? t("homeAirPlaceModel", lang, { p: ambientMeta.place })
                : t("homeAirModel", lang)))
    : null;
  const provLine = [provBase, airAgeLine].filter(Boolean).join("  ·  ");
  return (
    <View style={ss.hero}>
      <Text {...DYNAMIC_TYPE} style={[ss.heroEyebrow, { fontFamily: fam(lang, "med") }]}>
        {counted ? t("homeBreathed", lang)
          : airSrc === "forecast" ? t("homeAirForecast", lang)
          : ambientMeta?.atGps === false ? t("homeAirNowCity", lang)
          : t("homeAirNowLead", lang)}
      </Text>
      {counted ? (
        <View style={ss.heroNumRow}>
          {/* spec size, not auto-fit: on iOS adjustsFontSizeToFit
              measures against NotoDevanagari's taller glyph box and
              collapses the Hindi hero to the 0.55 floor (~62pt vs the
              112pt spec). numberOfLines=1 alone keeps the anti-wrap the
              prop was added for; a 4-digit dose still fits the row. */}
          <CountUp value={ug} duration={480}
            numberOfLines={1}
            style={[ss.heroNum, NUM, { fontFamily: famSerif(lang, "light"), color: ink }]}
            format={(n) => `${doseUgRound(n)}`} />
          <Text {...DYNAMIC_TYPE} style={[ss.heroUg, { fontFamily: fam(lang, "med") }]} numberOfLines={1}>
            {t("unitUg", lang).split(" ")[0]}
          </Text>
        </View>
      ) : airNow != null ? (
        <View style={ss.heroNumRow}>
          <CountUp value={Math.round(airNow)} duration={480}
            numberOfLines={1}
            style={[ss.heroNum, NUM, { fontFamily: famSerif(lang, "light"), color: ink }]} />
          <Text {...DYNAMIC_TYPE} style={[ss.heroUg, { fontFamily: fam(lang, "med") }]} numberOfLines={1}>
            µg/m³
          </Text>
        </View>
      ) : (
        <Text {...DYNAMIC_TYPE} style={[ss.heroThin, { fontFamily: fam(lang, "reg") }]}>
          {t("daySparseWait", lang)}
        </Text>
      )}
      {/* the breathing baseline — only under a number that exists */
      (counted || airNow != null) && <BreathLine color={ink} />}
      {/* the verdict word carries the band's own square — landing's
          .hnum-band grammar: solid swatch + felt word, position first */
      felt != null && (counted || airNow != null) && (
        <View style={ss.heroFeltRow}>
          <View style={[ss.heroBandSq, { backgroundColor: bandColorIdx(idx) ?? ink }]} />
          <Text {...DYNAMIC_TYPE} style={[ss.heroFelt, { fontFamily: famSerif(lang, "med"), color: ink }]}>
            {felt}
          </Text>
        </View>
      )}
      {/* what the number IS — plain words, so the figure can't be read
          as "AQI or mixed index" (owner's own complaint); the AQI
          equivalent rides along when the server serves one */}
      {!counted && airNow != null && (
        <Text {...DYNAMIC_TYPE} style={[ss.heroRef, NUM, { fontFamily: fam(lang, "reg") }]}>
          {airSrc === "forecast" ? t("homeAirWhatFc", lang)
            : ambientMeta?.usAqi != null
              ? t("homeAirWhatAqi", lang, { a: Math.round(ambientMeta.usAqi) })
              : t("homeAirWhat", lang)}
        </Text>
      )}
      {ref != null && (
        <Text {...DYNAMIC_TYPE} style={[ss.heroRef, NUM, { fontFamily: fam(lang, "reg") }]}>
          {ref}{ref2 ? `  ·  ${ref2}` : ""}
        </Text>
      )}
      {/* the ambient number's provenance — where it was read + how fresh,
          on one citation line (a number you can't verify reads as a
          wrong number) */}
      {provLine !== "" && (
        <Text {...DYNAMIC_TYPE} style={[ss.heroProv, { fontFamily: fam(lang, "reg") }]}>
          {provLine}
        </Text>
      )}
      {airNowIdx != null && (
        /* the good→severe anchor: today's air band as a solid segment on
           the washed CPCB ramp — "what's good, what's bad" answered as a
           position, not a sentence */
        <View style={ss.heroScale}>
          <BandScale idx={airNowIdx} lang={lang} />
        </View>
      )}
      {!counted && !!data.curve?.series.some((v) => v != null) && (
        <SparseAirArc series={data.curve.series} color={ink} />
      )}
      {counted && (
        <View style={ss.heroStatRow}>
          <Text {...DYNAMIC_TYPE} style={[ss.heroStat, NUM, { fontFamily: fam(lang, "reg") }]}>
            {h > 0 ? t("dayCovered", lang, { h, m }) : t("dayCoveredMin", lang, { m })}
          </Text>
          {ambientUg != null && airNowIdx != null && (
            <View style={ss.heroAmb}>
              <BandDot conc={null} color={bandColorIdx(airNowIdx)} />
              <Text {...DYNAMIC_TYPE} style={[ss.heroStat, NUM, { fontFamily: fam(lang, "reg") }]}>
                {t("homeOutsideNow", lang, { n: Math.round(ambientUg), w: t(feltKeyForBand(airNowIdx), lang) })}
              </Text>
            </View>
          )}
        </View>
      )}
      {!counted && (
        /* progress to the first counted day — the same gate the personal
           number answers to, filling as the phone logs real reads.
           The tour's ledger stop points here on a fresh install. */
        <View ref={ledgerNode} onLayout={ledgerLayout}
          style={ss.sparseProgRow}>
          {Array.from({ length: THIN_SAMPLE_MIN }).map((_, i) => (
            <View key={i} style={[ss.progSeg, {
              backgroundColor: i < rec.samplesToday ? ink : V2T.surface3,
            }]} />
          ))}
          <Text {...DYNAMIC_TYPE} style={[ss.sparseProgLbl, NUM, { fontFamily: fam(lang, "reg") }]}>
            {t("daySparseCount", lang)}
          </Text>
        </View>
      )}
      {/* provenance merged into provLine under the refs above; the old
          µg gloss caption was cut — the number no longer explains itself */}
      {weekCounted && (
        <View style={ss.heroWeekRow}>
          {data.week.map((w) => (
            <View key={w.day} style={[ss.weekBar, {
              backgroundColor: w.ug > 0 ? doseDotColor(w.ug, budgetUg) : V2T.surface3,
              height: w.ug > 0 ? 4 + 14 * (w.ug / maxW) : 4,
            }]} />
          ))}
          <Text {...DYNAMIC_TYPE} style={[ss.heroWeekLbl, NUM, { fontFamily: fam(lang, "reg") }]}>
            {t("homeWeek", lang, {
              n: approx(doseUgRound(data.week.reduce((sum, w) => sum + w.ug, 0))),
            })}
          </Text>
        </View>
      )}
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
    <Pressable collapsable={false} onPressIn={() => { holdMapDraw(); warmSearchIndex(); }} onPress={() => { tick(); onGo(); }}
      /* press-in hold: same touch-down coverage as the search pill — the
         tap's native work runs inside the sim draw-hold instead of racing
         the sheet mount (no-op on hardware). */
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

/** Feature doors — the secondary rooms as a grouped list card (docs/20:
 *  iOS grammar beats the icon-in-tile catalogue). One white card,
 *  three rows: bare accent-ink glyph, label, chevron; hairlines only
 *  INSIDE the list. Colour rules unchanged — accent for function,
 *  band hues stay on surfaces that mean air. */
function DoorRowInner({ lang, ambientUg, onMap, onCity, onTrips }: {
  lang: Lang; ambientUg: number | null;
  onMap: () => void; onCity: () => void; onTrips: () => void;
}) {
  bump("home.DoorRow");
  /* tour target — the "Air map" row gets its own spotlight */
  const { node: mapNode, onLayout: mapLayout } = useMeasureTarget("doorMap");
  const doors: { key: StringKey; glyph: Glyph; fn: () => void }[] = [
    { key: "homeLinkMap", glyph: "explore", fn: onMap },
    { key: "homeLinkCity", glyph: "city", fn: onCity },
    { key: "homeLinkTrips", glyph: "history", fn: onTrips },
  ];
  return (
    <View style={ss.doorCard}>
      {doors.map((d, i) => (
        <React.Fragment key={d.key}>
          {i > 0 && <View style={ss.doorListSep} />}
          <Pressable ref={d.key === "homeLinkMap" ? mapNode : undefined}
            onLayout={d.key === "homeLinkMap" ? mapLayout : undefined}
            onPress={() => { tap(); d.fn(); }}
            accessibilityRole="button" accessibilityLabel={t(d.key, lang)}
            style={({ pressed }) => [
              ss.doorListRow,
              pressed && { backgroundColor: V2T.surface2 },
            ]}>
            <Icon name={d.glyph} color={V2T.text2} size={24} filled />
            <Text {...DYNAMIC_TYPE} numberOfLines={1}
              style={[ss.doorListLabel, { fontFamily: fam(lang, "med") }]}>
              {t(d.key, lang)}
            </Text>
            <Icon name="chevron" color={V2T.text4} size={18} />
          </Pressable>
        </React.Fragment>
      ))}
    </View>
  );
}

const DoorRow = React.memo(DoorRowInner);

/** Local pollution incidents — the measured cause_note the "Delhi
 *  today" sheet carries under its hero (GET /v2/city's why block →
 *  belt fires, ventilation, recorded trend; the same fields rebuild
 *  hi without wire English). Sits above the doors so the day's
 *  drivers land before the city view opens — the owner's ask
 *  ("parali and all — before Delhi Today"). fetchCity is the shared
 *  15-min last-good cache, so the card costs no extra wire. Renders
 *  nothing until a real note arrives — no skeleton, no fake. */
function IncidentsCardInner({ lang }: { lang: Lang }) {
  bump("home.Incidents");
  const [line, setLine] = useState<string | null>(null);
  useEffect(() => {
    const ctrl = new AbortController();
    fetchCity(ctrl.signal).then((d) => {
      const w = d.why;
      if (ctrl.signal.aborted) return;
      /* same grammar as DelhiToday's noteLine — BOTH languages rebuild
         from the measured fields (the wire grammar leaks m²/s and
         "city mean"); cause_note stays the no-fields fallback
         (jargon-sweep) */
      setLine(!w ? ""
        : w.cause_note_fields
          ? causeNote(w.cause_note_fields as CauseNoteFields, lang)
          : (w.cause_note ?? ""));
    }).catch(() => setLine(""));
    return () => ctrl.abort();
  }, [lang]);
  if (!line) return null;
  return (
    <View style={ss.incidentCard}>
      <View style={ss.incidentHead}>
        <Icon name="flame" color={V2T.text3} size={15} />
        <Text {...DYNAMIC_TYPE} style={[ss.incidentTitle, { fontFamily: fam(lang, "med") }]}>
          {t("incidentsTitle", lang)}
        </Text>
      </View>
      <Text {...DYNAMIC_TYPE} style={[ss.incidentLine, { fontFamily: fam(lang, "reg") }]}>
        {line}
        <Text style={ss.incidentTag}>{` · ${t("noteMeasured", lang)}`}</Text>
      </Text>
    </View>
  );
}

const IncidentsCard = React.memo(IncidentsCardInner);

/** The screen answers the number: today's band floods the top of the
 *  page and settles into paper. A band change cross-fades (900 ms,
 *  ease-in-out) instead of snapping, and the wash breathes on a slow
 *  5.6 s sine — a dosimeter is a breathing thing. Reduce Motion: a
 *  static field, instant swaps. */
function MoodCanvasInner({ color }: { color: string }) {
  const reduce = useReduceMotion();
  const [pair, setPair] = useState({ prev: color, cur: color });
  const [fade] = useState(() => new Animated.Value(1));
  const [breath] = useState(() => new Animated.Value(1));
  if (pair.cur !== color) setPair({ prev: pair.cur, cur: color });
  useEffect(() => {
    if (reduce) { fade.setValue(1); return; }
    fade.setValue(0);
    const a = Animated.timing(fade, { toValue: 1, duration: 750, easing: Easing.inOut(Easing.cubic), useNativeDriver: true });
    a.start();
    return () => a.stop();
  }, [pair.cur, fade, reduce]);
  useEffect(() => {
    if (reduce) { breath.setValue(1); return; }
    const loop = Animated.loop(Animated.sequence([
      Animated.timing(breath, { toValue: 0.72, duration: 2800, easing: Easing.inOut(Easing.sin), useNativeDriver: true }),
      Animated.timing(breath, { toValue: 1, duration: 2800, easing: Easing.inOut(Easing.sin), useNativeDriver: true }),
    ]));
    loop.start();
    return () => loop.stop();
  }, [breath, reduce]);
  const layer = (c: string, id: string) => (
    <Svg width="100%" height="100%">
      <Defs>
        <LinearGradient id={id} x1="0" y1="0" x2="0" y2="1">
          <Stop offset="0" stopColor={c} />
          <Stop offset="0.26" stopColor={c} stopOpacity={0.62} />
          <Stop offset="0.52" stopColor={c} stopOpacity={0.30} />
          <Stop offset="0.8" stopColor={V2T.bg} />
        </LinearGradient>
      </Defs>
      <Rect x="0" y="0" width="100%" height="100%" fill={V2T.bg} />
      <Rect x="0" y="0" width="100%" height="100%" fill={`url(#${id})`} />
    </Svg>
  );
  return (
    <View style={StyleSheet.absoluteFill} pointerEvents="none">
      <View style={StyleSheet.absoluteFill}>{layer(pair.prev, "moodPrev")}</View>
      <Animated.View style={[StyleSheet.absoluteFill, { opacity: Animated.multiply(fade, breath) }]}>
        {layer(pair.cur, "moodCur")}
      </Animated.View>
    </View>
  );
}

const MoodCanvas = React.memo(MoodCanvasInner);

function HomeSheetInner({ data, lang, settings, ambientUg, ambientMeta, fieldAgeS, fieldStale, onGo, onMenu, onMap, onCity, onTrips, onProfile, onCheckin }: {
  data: DayData | null; lang: Lang; settings: ShellSettings;
  ambientUg: number | null;
  ambientMeta?: AmbientMeta | null;
  fieldAgeS?: number | null;
  fieldStale?: boolean | null;
  onGo: () => void; onMenu: () => void;
  onMap: () => void; onCity: () => void; onTrips: () => void;
  onProfile: (p: ShellSettings["profile"]) => void;
  onCheckin: (c: Omit<Checkin, "ts">) => void;
}) {
  bump("home.HomeSheet");
  const budget = PROFILE_BUDGET_UG[settings.profile];
  /* the lungs' calendar sheet — the week strip's tap target (the picked
     day key; null = closed) */
  const [weekDay, setWeekDay] = useState<string | null>(null);
  const insets = useSafeAreaInsets();
  /* the coach tour's scroller — the scroll view registers itself so a
     stop can pull its target into the viewport; offsets feed liveRect */
  const scrollRef = useRef<ScrollView>(null);
  useTourScroller(scrollRef);
  /* the air is the canvas (docs/20): the whole screen breathes today's
     outside band as a whisper at the top, settling to paper — the
     environment itself is the data, cards float in paper on it */
  const canvasIdx = bandIdx(ambientUg ?? null)
    ?? (data ? doseTierIdx(data.rec.totalUg, budget) : null);
  const canvasTop = canvasIdx != null ? bandWashDeepIdx(canvasIdx) : V2T.bg;
  return (
    <View style={ss.home}>
      <MoodCanvas color={canvasTop} />
      <HomeHeader lang={lang} onMenu={onMenu} />
      {/* the travel verb pinned TOP — the maps-app grammar: the primary
          action is a fixed header row, never the bottom of a component;
          reachable the moment the sheet opens, on every scroll depth,
          and off the scroll/elevation touch-dispatch path that ate
          taps on Android (apk-verify-v8). */}
      <View style={[ss.ctaBar, { paddingBottom: 10 }]}>
        <TourTarget id="cta">
          <TravelCta lang={lang} onGo={onGo} />
        </TourTarget>
      </View>
      <ScrollView ref={scrollRef} style={ss.flex}
        /* perf-probe: rAF frames through each drag — the gfxinfo-style
           jank% for the home scroll is these jank reports. */
        onScrollBeginDrag={() => jank("scroll.home", 1200)}
        /* the tour's spotlight tracks the drag — offset ticks re-derive
           every hole's window position (throttled; cost is a map write) */
        onScroll={(e) => tourScrolled(e.nativeEvent.contentOffset.y)}
        scrollEventThrottle={48}
        /* the audit's occlusion complaint was measured against a ~62 px
           bottom overlay; the CTA is a top header row now, but the 12 px
           bottom pad still sat the last card inside the home-indicator
           zone — the strip the OS reserves for the swipe gesture. Pad
           past the inset so every bottom cell clears it (audit #1). */
        contentContainerStyle={[ss.content, { paddingBottom: insets.bottom + 16 }]}
        showsVerticalScrollIndicator={false}
        /* when a card above the viewport grows (the move's age-line
           landing, a rebuild), the scroll view re-pins the first visible
           item instead of letting the content shove under the finger —
           the days-ahead→move-card yank stays dead even if a future
           card's height jitters. */
        maintainVisibleContentPosition={{ minIndexForVisible: 0 }}>
        {/* the hero lands first; the doors sit under it; content cards
            arrive staggered below. The ONE primary CTA stays out of
            this scroll — it is the fixed header row above. */}
        <FadeIn delay={0}>
          <TourTarget id="hero">
            <HeroBlock data={data} budgetUg={budget} ambientUg={ambientUg}
              ambientMeta={ambientMeta} fieldAgeS={fieldAgeS} fieldStale={fieldStale} lang={lang} />
          </TourTarget>
        </FadeIn>
        <FadeIn delay={70}>
          <IncidentsCard lang={lang} />
        </FadeIn>
        <FadeIn delay={90}>
          <DoorRow lang={lang} ambientUg={ambientUg} onMap={onMap} onCity={onCity} onTrips={onTrips} />
        </FadeIn>
        <FadeIn delay={130}>
          <MoveCard curve={data?.curve ?? null} outside={data?.outside ?? false} lang={lang} />
        </FadeIn>
        {data && !data.rec.thin && (
          <FadeIn delay={170}>
            <TourTarget id="day">
              <DayCard rec={data.rec} budgetUg={budget} lang={lang} />
            </TourTarget>
          </FadeIn>
        )}
        {data && (
          <FadeIn delay={190}>
            <TourTarget id="week">
              <WeekStrip week={data.week} budgetUg={budget} lang={lang} onOpen={setWeekDay} />
            </TourTarget>
          </FadeIn>
        )}
        <FadeIn delay={210}>
          <DaysAheadCard outlook={data?.outlook ?? null} lang={lang} />
        </FadeIn>
        <FadeIn delay={250}>
          <CheckinSheet checkin={data?.checkin ?? null}
            lens={data?.lens ?? { kind: "early", days: 0, need: 7 }} lang={lang} onCheckin={onCheckin} />
        </FadeIn>
        <FadeIn delay={300}>
          <BudgetCard totalUg={data?.rec.totalUg ?? 0} profile={settings.profile}
            lang={lang} onProfile={onProfile} />
        </FadeIn>
      </ScrollView>
      {/* the lungs' calendar — mounted over the scroll so a strip tap
          rises as its own sheet */}
      {weekDay != null && data != null && (
        <WeekSheet day={weekDay} week={data.week} outlook={data.outlook}
          budgetUg={budget} lang={lang} onClose={() => setWeekDay(null)} />
      )}
    </View>
  );
}

const HomeSheet = React.memo(HomeSheetInner);

/** The home surface — the app's resting state. Mounts as a paper sheet
 *  over the always-live map; `visible` false slides it back down and
 *  unmounts after the exit timing (the same JS-driver pattern as the
 *  old day sheet — RN Modal's native present/dismiss segfaults this stack). */
function HomeScreenInner({ visible, data, lang, settings, ambientUg, ambientMeta, fieldAgeS, fieldStale, onGo, onMenu, onMap, onCity, onTrips, onProfile, onCheckin }: {
  visible: boolean;
  data: DayData | null;
  lang: Lang;
  settings: ShellSettings;
  ambientUg: number | null;
  ambientMeta?: AmbientMeta | null;
  fieldAgeS?: number | null;
  fieldStale?: boolean | null;
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
        /* a heavier settle — ζ≈0.9: the sheet lands and stops, no
           rubbery overshoot under the hero */
        Animated.spring(enter, {
          toValue: 1, damping: 26, stiffness: 230, mass: 0.9, useNativeDriver: true,
        }).start();
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
          ambientMeta={ambientMeta} fieldAgeS={fieldAgeS} fieldStale={fieldStale}
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
  brand: { color: V2T.text, fontSize: V2Type.display, letterSpacing: -0.6, lineHeight: 36 },
  brandSub: { color: V2T.text3, fontSize: V2Type.label, marginTop: 1 },
  homeMenuBtn: {
    width: 42, height: 42, borderRadius: 21,
    alignItems: "center", justifyContent: "center",
    backgroundColor: "rgba(22,24,29,0.05)",
  },
  menuBars: { gap: 5 },
  menuBar: { width: 16, height: 2, borderRadius: 1, backgroundColor: V2T.text },
  flex: { flex: 1 },
  content: { paddingHorizontal: 16, paddingTop: 4, gap: 16 },

  /* the hero sits ON the mood canvas — no card, no edge, no shadow:
     a statement in the page, the way a weather app states the sky */
  hero: { paddingHorizontal: 6, paddingTop: 18, paddingBottom: 10 },
  heroEyebrow: { color: V2T.text2, fontSize: V2Type.secondary },
  /* the number IS the home screen — the landing's instrument scale on a
     phone: a huge thin numeral the whole surface arranges around */
  heroNum: { fontSize: 132, lineHeight: 138, letterSpacing: -6, marginLeft: -6 },
  heroNumRow: { flexDirection: "row", alignItems: "flex-end", gap: 10 },
  heroUg: { color: V2T.text3, fontSize: V2Type.label, letterSpacing: 0.5, paddingBottom: 26 },
  breathLine: { height: 2, borderRadius: 1, marginTop: 16 },
  heroFeltRow: { flexDirection: "row", alignItems: "center", gap: 10, marginTop: 12 },
  heroBandSq: { width: 10, height: 10, borderRadius: 2.5 },
  heroFelt: { fontSize: V2Type.display, letterSpacing: -0.4, lineHeight: 34 },
  heroRef: { color: V2T.text2, fontSize: V2Type.secondary, marginTop: 6, lineHeight: 21 },
  /* the provenance/footnote line under a hero number — whispered, never
     competing with the felt word */
  heroProv: { color: V2T.text4, fontSize: V2Type.label, marginTop: 8, lineHeight: 18 },
  heroScale: { marginTop: 16, alignSelf: "stretch" as const, maxWidth: 220 },
  heroThin: { color: V2T.text2, fontSize: V2Type.secondary, lineHeight: 21, marginTop: 8 },
  sparseArc: { marginTop: 18, marginHorizontal: -6 },
  sparseProgRow: { flexDirection: "row", alignItems: "center", gap: 4, marginTop: 14 },
  progSeg: { width: 18, height: 4, borderRadius: 2 },
  sparseProgLbl: { color: V2T.text3, fontSize: V2Type.label, marginLeft: 8, flex: 1 },
  heroStatRow: { flexDirection: "row", alignItems: "center", flexWrap: "wrap", gap: 14, marginTop: 14 },
  heroStat: { color: V2T.text3, fontSize: V2Type.label },
  heroAmb: { flexDirection: "row", alignItems: "center", gap: 6 },
  heroWeekRow: { flexDirection: "row", alignItems: "flex-end", gap: 6, marginTop: 16 },
  heroWeekLbl: { color: V2T.text3, fontSize: V2Type.label, marginLeft: 8 },

  /* skeleton → content morph */
  skelEyebrow: { width: 150, height: 13, borderRadius: 6, backgroundColor: V2T.surface2, marginBottom: 12 },
  skelHero: { width: 200, height: 110, borderRadius: 8, backgroundColor: V2T.surface2 },
  skelLine: { width: "70%", height: 13, borderRadius: 6, backgroundColor: V2T.surface2, marginTop: 14 },

  /* the travel verb — the ONE primary CTA: solid ink pill */
  cta: {
    ...V2Elev.float,
    flexDirection: "row", alignItems: "center", gap: 10,
    backgroundColor: V2T.text,
    borderRadius: V2Radius.pill, height: 56, paddingHorizontal: 20,
  },
  /* its pinned header row — outside the scroll so the verb is always
     reachable, sitting on the canvas like the map's search pill */
  ctaBar: {
    paddingHorizontal: 20, paddingTop: 2,
    backgroundColor: "transparent",
  },
  ctaTxt: { flex: 1, color: V2T.bg, fontSize: V2Type.body, letterSpacing: -0.1 },
  ctaArrow: {
    width: 30, height: 30, borderRadius: 15,
    backgroundColor: "rgba(250,250,247,0.16)",
    alignItems: "center", justifyContent: "center",
  },

  /* feature doors — one grouped list card (iOS grammar): icon, label,
     chevron per row; hairlines live INSIDE the list, never on cards */
  doorCard: {
    ...V2Elev.card,
    backgroundColor: V2T.surface,
    borderRadius: 24, borderCurve: "continuous", overflow: "hidden",
  },
  doorListRow: {
    flexDirection: "row", alignItems: "center", gap: 14,
    paddingHorizontal: 18, paddingVertical: 16,
  },
  doorListSep: { height: StyleSheet.hairlineWidth, backgroundColor: V2T.hairline, marginLeft: 56 },
  doorListLabel: { flex: 1, fontSize: V2Type.body, color: V2T.text },

  /* the incidents card — a paper card like the doors, one quiet
     label + the measured line; no band colour — nothing here
     encodes a band, so colour would only decorate */
  incidentCard: {
    ...V2Elev.card,
    backgroundColor: V2T.surface,
    borderRadius: 24, borderCurve: "continuous",
    paddingHorizontal: 18, paddingTop: 14, paddingBottom: 14,
  },
  incidentHead: { flexDirection: "row", alignItems: "center", gap: 7 },
  incidentTitle: { color: V2T.text3, fontSize: V2Type.label },
  incidentLine: { color: V2T.text2, fontSize: V2Type.secondary, lineHeight: 21, marginTop: 8 },
  incidentTag: { color: V2T.text3, fontSize: V2Type.label },

  card: {
    ...V2Elev.card,
    backgroundColor: V2T.surface,
    borderRadius: 24, borderCurve: "continuous",
    paddingHorizontal: 20, paddingTop: 18, paddingBottom: 18,
  },
  /* the card's own word — a warm label, never an uppercase micro eyebrow */
  cardTitle: {
    color: V2T.text3, fontSize: V2Type.label, marginBottom: 8,
  },
  finePrint: { color: V2T.text3, fontSize: V2Type.micro, marginTop: 10 },

  /* the move — decision felt at serif scale, evidence lives in chips */
  moveLine: { color: V2T.text, fontSize: V2Type.title, lineHeight: 29, marginBottom: 10 },
  sparkLabels: { position: "relative", height: 13, marginTop: 2 },
  sparkHr: { position: "absolute", top: 0, width: 44, color: V2T.text3, fontSize: V2Type.micro, textAlign: "center" },
  winChip: {
    flexDirection: "row", alignItems: "center", gap: 8, marginTop: 8,
    paddingVertical: 4, alignSelf: "flex-start",
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
    flex: 1,
    borderRadius: 15, backgroundColor: V2T.surface2,
    paddingHorizontal: 6, paddingTop: 10, paddingBottom: 9,
    alignItems: "center",
  },
  oaCellSel: { transform: [{ translateY: -3 }], ...V2Elev.card },
  oaDay: { color: V2T.text3, fontSize: V2Type.micro },
  oaMidRow: { flexDirection: "row", alignItems: "center", gap: 5, marginTop: 5 },
  oaMid: { color: V2T.text, fontSize: V2Type.body, lineHeight: 22 },
  oaSub: { color: V2T.text3, fontSize: V2Type.micro, marginTop: 2, minHeight: 14 },
  oaMark: { color: V2T.accentInk, fontSize: V2Type.micro, marginTop: 2, minHeight: 14 },
  oaDetail: {
    marginTop: 14, paddingTop: 2,
  },
  oaDetailHead: { color: V2T.text2, fontSize: V2Type.label },
  oaDetailNote: { color: V2T.text3, fontSize: V2Type.micro, marginTop: 6 },

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

  weekDot: { width: 9, height: 9, borderRadius: 4.5 },
  weekBar: { width: 8, height: 16, borderRadius: 4 },

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
