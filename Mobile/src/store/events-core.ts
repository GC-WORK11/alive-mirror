// Air-event detectors — the pure half of the events engine
// (checkAirEvents in ./events.ts is the wiring: files, fetches, settings).
//
// Every detector reads only fields the server already admits:
//   trend    ← /v2/why  drivers[kind=trend] + evaluated.trend — the
//              server's own recorded-build admission (≥3 builds, ≥1 h
//              span, newest ≤2.5 h, |Δ| ≥ 12 µg) reaches us pre-vetted
//   grap     ← /v2/day  grap.equivalent_stage — the server's "maps to"
//              read; transitions either direction are the claim
//   outlook  ← /v2/outlook day fold — tomorrow vs today at the server's
//              own "meaningful difference" floor (max 15 µg, 15%)
//   reflect  ← the on-device ledger — yesterday's real logged trips
//   feed     ← feed_age_s vs feed_stale_after_s — diagnostics only
//
// Dedupe (`fired`) is per UTC-day per kind; "re-ping only if worsening"
// rules live here so the tests can pin them without a fetch.
import { t, type Lang, type StringKey } from "../i18n/strings";
import type { Trip } from "./ledger";

/* ---- thresholds — each mirrors a served-side floor so the client never
   applies a weaker bar than the explainer itself (server/v2/why.py,
   server/v2/day.py, server/v2/outlook.py). */
/** server's "the belt isn't a headline" floor (SMOKE_MIN_BELT). */
export const BELT_MIN = 10;
/** a build claim needs +15 fires or +50% over the baseline — FIRMS daily
    CSVs re-count a few points on refetch; under this it's feed noise. */
export const BELT_JUMP_ABS = 15;
export const BELT_JUMP_REL = 0.5;
/** band pings start at CPCB "poor" (idx 3, >90 µg/m³). */
export const BAND_MIN_IDX = 3;
/** a baseline older than this can't back a "since the last check" claim. */
export const BASELINE_MAX_AGE_MS = 18 * 60 * 60 * 1000;
/** clean-window ping fires when IST-now sits inside [start−lead, end). */
export const WINDOW_LEAD_MIN = 60;
/** a revised clean-window start re-pings only on a real move — a 10:30→
    10:35 wobble is the same event, not a new window. */
export const WINDOW_REPING_MIN = 30;
/** GRAP-equivalent stage at which the day reads "severe" (stage III). */
export const SEVERE_MIN_STAGE = 3;
/** stagnation pings need factor ≥ this (VC < ~2000 vs ~3000 typical) —
    below it "barely mixing" is a stretch most winter days would trip
    (audit fix: admission alone used to ping at any marginal factor). */
export const STAG_FACTOR_PING = 1.5;
/** stagnation re-pings only when the driver score grew this much (0–1). */
export const STAG_SCORE_STEP = 0.2;
/** /v2/why is the heavy read (snapshot history) — cap at one call / 10 min. */
export const WHY_MIN_MS = 10 * 60 * 1000;
/** trend re-pings at +12 µg of recorded delta — the server's own
    TREND_MIN_DELTA_UG, kept in step so a re-ping is a new admission. */
export const TREND_REPING_UG = 12;
/** the tomorrow digest is an evening read — "tomorrow" at 9am is trivia. */
export const OUTLOOK_EVE_FROM_IST = 17;
export const OUTLOOK_EVE_TO_IST = 22;
/** a tomorrow row needs ≥6 served hours to claim "tomorrow's air" —
    the fold's sliver day (horizon tail) stays honest silence. */
export const OUTLOOK_MIN_HOURS = 6;
/** the fold re-pings only on a real revision, not a ±2 µg wobble. */
export const OUTLOOK_REPING_UG = 15;
/** the fold's own "no meaningful difference" floor (server _FLAT_UG /
    _FLAT_REL) — a delta under it is noise, not news. */
export const OUTLOOK_SHIFT_UG = 15;
export const OUTLOOK_SHIFT_REL = 0.15;
/** reflection compares to the nearest earlier trip-day inside a week. */
export const REFLECT_LOOKBACK_DAYS = 7;
/** "heavier than Tuesday" needs ±15% — under it the honest word is "about
    the same" (same flat floor the fold uses). */
export const REFLECT_CMP_REL = 0.15;

/* ---- dedupe: once per UTC-day per kind, re-ping only when worse ------- */
export const utcDay = (d: Date) => d.toISOString().slice(0, 10);
export type SeenMark = { day: string; level: number };
/** the kinds the persisted marks cover — a string so a shared mark
    (e.g. the fires ladder) can sit under one key without pretending to
    be a notification kind */
export type SeenKind = string;

/** Is `level` worth a ping given what we already notified today? */
export function fired(mark: SeenMark | undefined, kind: SeenKind,
                      level: number, day: string): boolean {
  if (!mark || mark.day !== day) return true;
  switch (kind) {
    case "fires":
    case "fires_nc":   // belt builds carry the same severity ladder either way
      return level >= mark.level + Math.max(BELT_JUMP_ABS, mark.level * BELT_JUMP_REL);
    case "band":       // every higher band is a new claim (poor→very poor→severe)
    case "severe":     // stage III → IV is a new claim
      return level > mark.level;
    case "stagnation": // score 0–100 → +20 is +0.2 on the wire score
      return level >= mark.level + STAG_SCORE_STEP * 100;
    case "trend_up":
    case "trend_down": // a bigger recorded move is a new claim
      return level >= mark.level + TREND_REPING_UG;
    case "window":     // a different start time is a different window —
                       // but only a real revision (≥30 min) is
      return Math.abs(level - mark.level) >= WINDOW_REPING_MIN;
    case "grap_up":
    case "grap_down":
    case "grap_clear": // a different stage under this arrow is a new claim
      return level !== mark.level;
    case "outlook_heavy":
    case "outlook_light": // only a real forecast revision re-pings
      return Math.abs(level - mark.level) >= OUTLOOK_REPING_UG;
    case "reflect":    // the day's look-back is said once, full stop
      return false;
    default:
      return true;
  }
}

/* ---- /v2/why — the bits the detectors read (shape: server/v2/why.py) -- */
export type V2WhyDriver = {
  kind?: string;
  weight?: string;
  score?: number;
  direction?: string;
  detail?: { factor?: number; wind_from_deg?: number; belt_fires?: number };
};
/** the note's raw ingredients — server composes it in why.py alongside
    cause_note; the app re-localizes from this, never from the English. */
export type CauseNoteFields = {
  basis?: string | null;
  belt_fires?: number | null;
  belt_delta?: number | null;
  belt_delta_h?: number | null;
  carrying?: boolean | null;
  wind_from_deg?: number | null;
  wind_kmh?: number | null;
  vc_m2s?: number | null;
  stag_factor?: number | null;
  trend_from?: number | null;
  trend_to?: number | null;
  trend_span_h?: number | null;
};
export type V2Why = {
  drivers?: V2WhyDriver[];
  evaluated?: {
    fires?: {
      seen?: boolean;
      belt_fires?: number | null;
      n_fires?: number | null;
      carrying?: boolean | null;
      feed_status?: string | null;
      feed_age_s?: number | null;
      feed_stale_after_s?: number | null;
    } | null;
    ventilation?: {
      vc_m2s?: number | null;
      factor?: number | null;
    } | null;
    trend?: {
      delta_ug?: number | null;
      from_pm25?: number | null;
      to_pm25?: number | null;
      span_h?: number | null;
      window_h?: number | null;
      newest_age_s?: number | null;
    } | null;
  } | null;
  /** the served boundary wind — {from_deg,speed_kmh,age_s,source,known} */
  wind?: { from_deg?: number | null; speed_kmh?: number | null; known?: boolean } | null;
  /** the driver sparkline — per recorded build belt/pm2.5/vc (why.py
      _history); the belt series backs the note's "jumped" delta */
  history?: {
    window_h?: number;
    points?: {
      t?: number;
      pm25?: number | null;
      vc_m2s?: number | null;
      belt_fires?: number | null;
    }[] | null;
  } | null;
  /** server-composed English news line (cause_note) + its ingredients —
      consumers rephrase via causeNote() on the fields, not this text */
  cause_note?: string | null;
  cause_note_fields?: CauseNoteFields | null;
};

export const feedLive = (f: NonNullable<NonNullable<V2Why["evaluated"]>["fires"]>): boolean =>
  f.feed_age_s == null || f.feed_stale_after_s == null
    ? true                                    // feed gave no staleness bounds
    : f.feed_age_s <= f.feed_stale_after_s;

/* ---- trend — the recorded city mean moving, with its named cause ----- */
export type TrendShift = {
  dir: "up" | "down";
  /** µg/m³ city-mean endpoints over the recorded window */
  from: number;
  to: number;
  spanH: number;
  /** |Δ| µg/m³ — the level the re-ping ladder climbs on */
  delta: number;
};

export function trendShift(why: V2Why | null | undefined): TrendShift | null {
  const d = (why?.drivers ?? []).find((x) => x.kind === "trend");
  const ev = why?.evaluated?.trend;
  const delta = ev?.delta_ug;
  if (!d || typeof delta !== "number" || !Number.isFinite(delta)) return null;
  /* direction is the server's word — sign-of-delta is only a tiebreak
     that never gets used (the driver only exists when a direction does) */
  const dir: TrendShift["dir"] | null =
    d.direction === "rising" ? "up" : d.direction === "falling" ? "down" : null;
  if (!dir) return null;
  const from = typeof ev?.from_pm25 === "number" ? ev.from_pm25 : NaN;
  const to = typeof ev?.to_pm25 === "number" ? ev.to_pm25 : NaN;
  if (!Number.isFinite(from) || !Number.isFinite(to)) return null;
  const spanH = typeof ev?.span_h === "number" ? ev.span_h
    : typeof ev?.window_h === "number" ? ev.window_h : 0;
  return { dir, from, to, spanH, delta: Math.abs(delta) };
}

/* ---- the cause clause — names only drivers the server admitted -------- */

const _CARRY_WORDS: [number, string][] = [
  [337.5, "N"], [292.5, "NW"], [247.5, "W"], [202.5, "SW"],
  [157.5, "S"], [112.5, "SE"], [67.5, "E"], [22.5, "NE"],
];
/** same compass bucketing as the server's _compass — the whyDir_* string
    keys carry the localized words */
const compass = (deg: number | null | undefined): string => {
  if (deg == null || !Number.isFinite(deg)) return "NW";
  const d = ((deg % 360) + 360) % 360;
  for (const [top, name] of _CARRY_WORDS) if (d >= top) return name;
  return "N";
};

/** The live causes a ping may name — the top drivers minus the claim
    itself (a "trend is rising" ping names smoke/stagnation behind it,
    never "the trend caused the trend"). Only admitted kinds reach copy;
    an empty string means "say the number without a fake cause". */
export function causeClause(
  why: V2Why | null | undefined,
  lang: Lang,
  exclude: string[] = [],
): string {
  const kinds = (why?.drivers ?? [])
    .map((d) => d.kind)
    .filter((k): k is string => !!k && !exclude.includes(k));
  const smoke = kinds.includes("stubble_smoke");
  const stag = kinds.includes("stagnation");
  if (!smoke && !stag) return "";
  const dirDeg = (why?.drivers ?? []).find((d) => d.kind === "stubble_smoke")
    ?.detail?.wind_from_deg ?? why?.wind?.from_deg ?? null;
  const dir = t(`whyDir_${compass(dirDeg)}` as StringKey, lang);
  const key: StringKey = smoke && stag ? "notifyCauseSmokeStag"
    : smoke ? "notifyCauseSmoke" : "notifyCauseStag";
  return t(key, lang, { dir });
}

/* ---- the cause_note — the parali/news line, re-localized ------------
   Server composes the canonical English in why.py and ships the raw
   ingredients as cause_note_fields; the app re-renders the same
   grammar through i18n so Hindi never shows wire English. Every gate
   below mirrors the server's own admission floors — the note names
   nothing the explainer wouldn't. */

/** server STAG_FACTOR_MIN — below it "barely mixing" isn't claimed. */
export const NOTE_STAG_MIN = 1.25;
/** server HISTORY_MIN_SPAN_S — the belt "jumped" read needs ≥3h of
    recorded builds behind it. */
export const NOTE_BELT_SPAN_MIN_S = 3 * 3600;
/** under this a belt move could be FIRMS re-count noise (why.py). */
export const NOTE_DELTA_MIN = 5;

/** Normalize a /v2/why payload (or the city's cause_note_fields) to
    the note's ingredient set. The belt delta is re-derived from the
    served history series — live count vs the oldest in-window build —
    so the note works against a server that predates the fields key. */
export function causeFieldsFromWhy(why: V2Why | null | undefined): CauseNoteFields {
  const ev = why?.evaluated ?? {};
  const f = ev.fires ?? {};
  const v = ev.ventilation ?? {};
  const tr = ev.trend ?? {};
  const belt = typeof f.belt_fires === "number" && Number.isFinite(f.belt_fires)
    ? f.belt_fires : null;
  /* belt "jumped" — the served history's own belt series, oldest build
     vs the live count; only while the feed itself is live (a recorded
     fallback vs a recorded build compares the same number twice) */
  let beltDelta: number | null = null;
  let beltDeltaH: number | null = null;
  /* strict "live" — same gate as the server: no feed_status word means
     the "jumped" read can't be claimed (a recorded count vs a recorded
     build would compare the same number twice) */
  if (belt != null && f.feed_status === "live" && feedLive(f)) {
    const rows = (why?.history?.points ?? []).filter(
      (p): p is { t: number; belt_fires: number } =>
        typeof p?.t === "number" && typeof p?.belt_fires === "number");
    if (rows.length >= 2) {
      const span = rows[rows.length - 1].t - rows[0].t;
      const d = belt - rows[0].belt_fires;
      if (span >= NOTE_BELT_SPAN_MIN_S && Math.abs(d) >= NOTE_DELTA_MIN) {
        beltDelta = d;
        beltDeltaH = Math.round((span / 3600) * 10) / 10;
      }
    }
  }
  const stagF = typeof v.factor === "number" ? v.factor : null;
  const stag = stagF != null && stagF >= NOTE_STAG_MIN;
  const d = typeof tr.delta_ug === "number" ? tr.delta_ug : null;
  const trendAdm = d != null && Math.abs(d) >= TREND_REPING_UG
    && typeof tr.from_pm25 === "number" && typeof tr.to_pm25 === "number";
  return {
    basis: "measured",
    belt_fires: belt,
    belt_delta: beltDelta,
    belt_delta_h: beltDeltaH,
    carrying: f.carrying ?? null,
    wind_from_deg: why?.wind?.from_deg ?? null,
    wind_kmh: why?.wind?.speed_kmh ?? null,
    vc_m2s: stag ? (v.vc_m2s ?? null) : null,
    stag_factor: stag ? stagF : null,
    trend_from: trendAdm ? tr.from_pm25 ?? null : null,
    trend_to: trendAdm ? tr.to_pm25 ?? null : null,
    trend_span_h: trendAdm ? (tr.span_h ?? tr.window_h ?? null) : null,
  };
}

/** The plain-words news line — "44 fires in the Punjab–Haryana belt,
    up from 20 over ~5h — a NW wind at 9 km/h is carrying it toward
    Delhi · air barely mixing…". Built only from admitted fields; the
    honest empty answer is "local background". `skip` drops clauses a
    caller already said (the fires ping narrates its own belt+carry). */
export function causeNote(
  fields: CauseNoteFields | null | undefined,
  lang: Lang,
  opts?: { skip?: string[] },
): string {
  if (!fields) return "";
  const skip = new Set(opts?.skip ?? []);
  const bits: string[] = [];
  const belt = typeof fields.belt_fires === "number" ? fields.belt_fires : null;
  if (belt != null && !skip.has("belt")) {
    if (belt >= BELT_MIN) {
      let bit = t("noteBelt", lang, { n: belt });
      if (fields.belt_delta != null && fields.belt_delta_h != null &&
          Math.abs(fields.belt_delta) >= NOTE_DELTA_MIN) {
        bit += t(fields.belt_delta > 0 ? "noteBeltUp" : "noteBeltDown",
                 lang, {
                   a: Math.round(belt - fields.belt_delta),
                   h: Math.round(fields.belt_delta_h * 10) / 10 });
      }
      if (!skip.has("carry")) {
        const dir = t(`whyDir_${compass(fields.wind_from_deg)}` as StringKey, lang);
        bit += fields.carrying === true
          ? (fields.wind_kmh != null
             ? t("noteCarryYes", lang, { dir, kmh: fields.wind_kmh })
             : t("noteCarryYesNoKmh", lang, { dir }))
          : fields.carrying === false
          ? t("noteCarryNo", lang)
          : t("noteCarryUnknown", lang);
      }
      bits.push(bit);
    } else {
      bits.push(belt > 0
        ? t("noteBeltQuiet", lang, { n: belt })
        : t("noteBeltQuiet0", lang));
    }
  }
  if (fields.stag_factor != null && !skip.has("stag")) {
    bits.push(fields.vc_m2s != null
      ? t("noteStagVc", lang, { vc: Math.round(fields.vc_m2s).toLocaleString("en-IN") })
      : t("noteStag", lang));
  }
  const rising = fields.trend_from != null && fields.trend_to != null &&
    fields.trend_to > fields.trend_from;
  if (fields.trend_from != null && fields.trend_to != null && !skip.has("trend")) {
    bits.push(t("noteTrend", lang, {
      a: Math.round(fields.trend_from * 10) / 10,
      b: Math.round(fields.trend_to * 10) / 10,
      h: Math.round((fields.trend_span_h ?? 0) * 10) / 10,
    }));
  }
  /* the verdict tail — only what the physics itself backs: inflow
     meeting still air, or an admitted climb still on */
  if (fields.carrying === true && fields.stag_factor != null) {
    bits.push(t("noteTailInflow", lang));
  } else if (rising) {
    bits.push(t("noteTailClimb", lang));
  }
  return bits.length ? bits.join(" · ") : t("noteBackground", lang);
}

/* ---- GRAP-equivalent stage transitions --------------------------------
   The served stage is a "maps to" read (never "declared"). A move either
   way is the claim — except an arrival INTO ≥III, which is `severe`'s
   stronger ping and stays there so one move can't double-notify. */
export type GrapMove = "severe" | "up" | "down" | "clear";
export function grapMove(prev: number | null, cur: number | null): GrapMove | null {
  if (prev == null || cur == null || cur === prev) return null;
  if (cur > prev && cur >= SEVERE_MIN_STAGE) return "severe";
  if (cur > prev) return "up";
  return cur === 0 ? "clear" : "down";
}

/* ---- tomorrow's fold vs today ------------------------------------------ */
export type OutlookDayLite = {
  pm25_mid: number;
  n_hours?: number;
  confidence?: string;
  cleanest_window?: { start_label?: string; end_label?: string | null } | null;
};

/** heavy | light | null — the fold's own difference bar; a lo-confidence
    tomorrow (past the live anchor's reach, the fold's own note) is an
    honest silence, and so is a sliver of a day. */
export function outlookMove(
  todayMid: number | null | undefined,
  tmw: OutlookDayLite | null | undefined,
): "heavy" | "light" | null {
  if (todayMid == null || !Number.isFinite(todayMid) || todayMid <= 0) return null;
  if (!tmw || !Number.isFinite(tmw.pm25_mid)) return null;
  if ((tmw.n_hours ?? 0) < OUTLOOK_MIN_HOURS) return null;
  if (tmw.confidence === "lo") return null;
  const delta = tmw.pm25_mid - todayMid;
  const thr = Math.max(OUTLOOK_SHIFT_UG, OUTLOOK_SHIFT_REL * todayMid);
  if (delta >= thr) return "heavy";
  if (delta <= -thr) return "light";
  return null;
}

/** the evening window (IST hour) in which "tomorrow" is advice. */
export const outlookWindowOpen = (istMinutes: number): boolean =>
  istMinutes >= OUTLOOK_EVE_FROM_IST * 60 && istMinutes < OUTLOOK_EVE_TO_IST * 60;

/* ---- yesterday on the road — the ledger's own rows --------------------- */
export type ReflectSummary = {
  /** trips logged yesterday (local day) */
  n: number;
  /** summed real logged dose, µg */
  ug: number;
  /** nearest earlier trip-day inside the lookback — the honest compare */
  cmp: { dir: "heavier" | "lighter" | "same"; dayTs: number; ug: number } | null;
};

const localDay = (ts: number): string => {
  const d = new Date(ts);
  return `${d.getFullYear()}-${d.getMonth() + 1}-${d.getDate()}`;
};

export function reflectSummary(trips: Trip[], now: number): ReflectSummary | null {
  const DAY = 24 * 3600 * 1000;
  const todayK = localDay(now);
  const yK = localDay(now - DAY);
  const byDay = new Map<string, { n: number; ug: number }>();
  for (const tr of trips) {
    if (!(tr.dose_ug > 0)) continue;
    const k = localDay(tr.ts);
    if (k === todayK) continue;            // the look-back never touches today
    const acc = byDay.get(k) ?? { n: 0, ug: 0 };
    acc.n += 1;
    acc.ug += tr.dose_ug;
    byDay.set(k, acc);
  }
  const y = byDay.get(yK);
  if (!y || y.n === 0) return null;
  /* nearest earlier trip-day — "heavier than tuesday" only when a real
     tuesday exists to carry it */
  let cmp: ReflectSummary["cmp"] = null;
  for (let d = 2; d <= REFLECT_LOOKBACK_DAYS; d++) {
    const c = byDay.get(localDay(now - d * DAY));
    if (c && c.n > 0) {
      const dir = y.ug > c.ug * (1 + REFLECT_CMP_REL) ? "heavier"
        : y.ug < c.ug * (1 - REFLECT_CMP_REL) ? "lighter" : "same";
      cmp = { dir, dayTs: now - d * DAY, ug: c.ug };
      break;
    }
  }
  return { n: y.n, ug: y.ug, cmp };
}
