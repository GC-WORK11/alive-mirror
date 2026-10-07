// Air-event engine — client-side detection over the app's existing GETs
// (docs/lanes/events-notify.md; notify-v2 adds cause-aware kinds).
//
// Honesty contract (same as the rest of the app — zero fake):
//  - every notification traces to a served field, verbatim:
//      fires       ← /v2/why  evaluated.fires.belt_fires + carrying + feed age
//      band        ← the /aqi poll's own pm25_ambient (the "around you" read)
//      window      ← /v2/day  cleanest_window (via fetchDayCurve's server block)
//      stagnation  ← /v2/why  drivers[] kind=stagnation weight=primary, factor
//      severe      ← /v2/day  grap.equivalent_stage (the server's own "maps to")
//      trend       ← /v2/why  drivers[kind=trend] + evaluated.trend (recorded
//                    builds — the server's own admission, cause-named)
//      grap shift  ← /v2/day  grap.equivalent_stage vs its stored baseline,
//                    transitions either way below the severe arrival
//      outlook     ← /v2/outlook tomorrow's fold vs today, evening IST
//      reflect     ← the on-device ledger's own rows (yesterday's trips)
//      feed stall  ← feed_age_s vs feed_stale_after_s — recorded to
//                    events.json for the diagnostics surface, never pinged
//  - jump claims (fires, band, grap) need a baseline — the first observed
//    value is stored silently; only a LATER read can show a change. A
//    baseline older than BASELINE_MAX_AGE can't claim "since last check"
//    and is rebaselined.
//  - a stale fires feed can't claim a live build — feed_age_s must sit
//    inside feed_stale_after_s when the feed reports both.
//  - dedupe is per UTC-day per kind, and "unless it worsens again" means
//    the same kind re-pings only past the level already notified (see
//    fired() in ./events-core — fires/fires_nc share one ladder so a
//    wind-source flip can't double-ping the same build).
//
// Baselines persist in events.json (expo-file-system — the house
// convention; the repo carries no AsyncStorage). Everything in it is a
// count, a band index, a stage, or a timestamp — no location, nothing
// personal; "delete my data" wipes it like the other stores (settings.ts
// wipe list + resetEventsStore from App's deleteAll).
//
// Detectors live in ./events-core.ts — pure functions over served
// fields, unit-tested in ./events.test.ts without a fetch.
import { File, Paths } from "expo-file-system";
import { bandIdx } from "../theme";
import { API, fetchJson } from "../components/shell/net";
import { loadSettings } from "../components/shell/settings";
import { fetchDayCurve } from "../api/dayfield";
import { fetchOutlook } from "../api/outlook";
import { notifyAirEvent, requestPerms, type AirEventKind } from "../notify";
import { t, type Lang } from "../i18n/strings";
import { loadTrips } from "./ledger";
import {
  BASELINE_MAX_AGE_MS, BAND_MIN_IDX, BELT_JUMP_ABS, BELT_JUMP_REL,
  BELT_MIN, SEVERE_MIN_STAGE, STAG_FACTOR_PING,
  WHY_MIN_MS, WINDOW_LEAD_MIN,
  causeClause, causeFieldsFromWhy, causeNote, feedLive, fired, grapMove,
  outlookMove, outlookWindowOpen, reflectSummary, trendShift, utcDay,
  type SeenMark, type V2Why,
} from "./events-core";

/* release builds must not write feed diagnostics to the device log —
   dev-only, same convention as startup/marks.ts */
const _IS_DEV =
  typeof __DEV__ !== "undefined" ? __DEV__ : process.env.NODE_ENV !== "production";

/* ---- persisted state ---------------------------------------------------- */
type FeedHealth = {
  /** when the record was written */
  at: number;
  /** a served feed past its own staleness bound right now */
  stalled: boolean;
  /** which served read is stale — "fires" feed / "field" / both */
  which: string | null;
};

type AirEventState = {
  /** last burn-belt count + when it was read (jump baseline). */
  beltFires: number | null;
  beltAt: number | null;
  /** last ambient band index + when read (crossing baseline). */
  bandIdx: number | null;
  bandAt: number | null;
  /** last GRAP-equivalent stage + when read (transition baseline). */
  grapStage: number | null;
  grapAt: number | null;
  /** diagnostics only — feed stall record, never a notification. */
  feedHealth: FeedHealth | null;
  seen: Partial<Record<string, SeenMark>>;
};

const EMPTY: AirEventState = {
  beltFires: null, beltAt: null, bandIdx: null, bandAt: null,
  grapStage: null, grapAt: null, feedHealth: null, seen: {},
};

const FILE = new File(Paths.document, "events.json");
let mem: AirEventState | null = null;
let inflight: Promise<AirEventState> | null = null;
let writeTail: Promise<unknown> = Promise.resolve();

async function loadState(): Promise<AirEventState> {
  if (mem) return { ...mem, seen: { ...mem.seen } };
  let p = inflight;
  if (!p) {
    p = (async (): Promise<AirEventState> => {
      try {
        if (FILE.exists) {
          const j = JSON.parse(await FILE.text());
          const s: AirEventState = { ...EMPTY, ...(j ?? {}) };
          mem = s;
          return s;
        }
      } catch {}
      const s: AirEventState = mem ?? { ...EMPTY, seen: {} };
      mem = s;
      return s;
    })();
    inflight = p;
  }
  return p.then((s) => ({ ...s, seen: { ...s.seen } }));
}

function saveState(st: AirEventState): void {
  mem = { ...st, seen: { ...st.seen } };
  writeTail = writeTail
    .then(() => {
      if (mem === null) return; // wiped — don't resurrect
      try {
        if (!FILE.exists) FILE.create();
        FILE.write(JSON.stringify(mem));
      } catch {}
    })
    .catch(() => {});
}

/** "delete my data" — App's deleteAll calls this alongside clearAllData so
 *  the mirror can't resurrect the wiped file on the next check. */
export function resetEventsStore(): void {
  mem = null;
  inflight = null;
}

/** IST wall-clock minutes right now (label math mirrors _ist_label). */
const istMinutesNow = (): number => {
  const ist = new Date(Date.now() + 330 * 60 * 1000);
  return ist.getUTCHours() * 60 + ist.getUTCMinutes();
};
const labelToMin = (lab: string | null | undefined): number | null => {
  const m = /^(\d{1,2}):(\d{2})$/.exec(lab ?? "");
  return m ? Number(m[1]) * 60 + Number(m[2]) : null;
};

const GRAP_ROMAN = ["", "I", "II", "III", "IV"];
const grapRoman = (stage: number): string =>
  GRAP_ROMAN[Math.min(4, Math.max(1, stage))];

/* ---- the check — one call per ambient poll (~60 s, foreground only).
   Single-flight: a slow /v2/why must never stack a second detector that
   double-fires the same event. */
let checking = false;
let lastWhyAt = 0;

export async function checkAirEvents(opts: {
  lat: number;
  lon: number;
  /** freshest ambient µg/m³ the /aqi poll just read at this point. */
  ambientUg: number | null;
}): Promise<void> {
  if (checking) return;
  checking = true;
  try {
    const s = await loadSettings();
    if (!s.alerts) return;
    const st = await loadState();
    const now = new Date();
    const day = utcDay(now);
    const lang: Lang = s.lang === "hi" ? "hi" : "en";
    let dirty = false;

    const fire = async (kind: AirEventKind, level: number,
                        vars: Record<string, string | number>,
                        mark?: SeenMark): Promise<void> => {
      /* mark override: the fires ladder is shared across fires/fires_nc —
         the same build worded by a flipped wind read is one event, and the
         highest level already notified is the bar to clear */
      if (!fired(mark ?? st.seen[kind], kind, level, day)) return;
      /* ask only when there's something real to say: the system dialog
         arrives with a reason instead of at boot. A user who already
         answered "no" just never hears the ping (requestPerms re-reads
         the OS state — it can't re-open a settled dialog). */
      if (!(await requestPerms())) return;
      if (await notifyAirEvent(kind, lang, vars)) {
        st.seen[kind] = { day, level };
        dirty = true;
      }
    };

    /* ---- remote reads: /v2/why carries the fires feed + the driver list;
       /v2/day carries the served windows + the GRAP-equivalent stage;
       /v2/outlook carries tomorrow's fold. why is throttled and runs
       FIRST so every ping below can carry the news note; the day
       curve + outlook share the 15-min last-good cache. ---- */
    const wantWhy = s.alerts_fires || s.alerts_band;
    const wantDay = s.alerts_windows || s.alerts_band;
    let why: V2Why | null = null;
    if (wantWhy && now.getTime() - lastWhyAt >= WHY_MIN_MS) {
      lastWhyAt = now.getTime();         // stamped before the await — a slow
      why = await fetchJson(`${API}/v2/why?lat=${opts.lat}&lon=${opts.lon}`, 9000)
        .then((j) => (j && typeof j === "object" ? (j as V2Why) : null))
        .catch(() => null);
    }

    /* the cause_note — the parali/news line appended to a ping as
       {note}: every figure a measured field (belt detections, carry
       wind, ventilation, recorded city mean — never a news feed).
       Empty when the explainer didn't run this poll: a notification
       never pads with nothing. `skip` drops clauses the ping's own
       body already narrates. */
    const noteFor = (skip: string[]): string => {
      if (!why) return "";
      const s = causeNote(causeFieldsFromWhy(why), lang, { skip });
      return s ? ` · ${s}` : "";
    };

    /* ---- band worsens: the ambient read around the user crossed a CPCB
       threshold upward since the last read (poor and worse). The baseline
       is the previous bandIdx, refreshed every poll — no baseline, no
       claim; an ancient baseline rebaselines silently. ---- */
    if (s.alerts_band && opts.ambientUg != null && opts.ambientUg > 0) {
      const idx = bandIdx(opts.ambientUg);
      const prev = st.bandIdx;
      const fresh = st.bandAt != null && now.getTime() - st.bandAt <= BASELINE_MAX_AGE_MS;
      if (idx != null && prev != null && fresh && idx > prev && idx >= BAND_MIN_IDX) {
        /* idx/prev go over verbatim — notify.ts names them through
           feltKeyForBand so the felt words stay single-sourced. */
        await fire("band", idx, {
          idx, prev, n: Math.round(opts.ambientUg), note: noteFor([]),
        });
      }
      if (idx != null && idx !== prev) {
        st.bandIdx = idx;
        st.bandAt = now.getTime();
        dirty = true;
      }
    }

    /* fires spike — the NW burn belt lit up vs the stored baseline. The
       served `carrying` gate decides whether the wind brings it here:
       both claims are real, they just read differently. */
    if (s.alerts_fires && why) {
      const f = why.evaluated?.fires;
      const belt = f && typeof f.belt_fires === "number" && Number.isFinite(f.belt_fires)
        ? f.belt_fires : null;
      if (f && f.seen !== false && belt != null && feedLive(f)) {
        const prev = st.beltFires;
        const fresh = st.beltAt != null && now.getTime() - st.beltAt <= BASELINE_MAX_AGE_MS;
        if (belt >= BELT_MIN && prev != null && fresh &&
            belt >= prev + Math.max(BELT_JUMP_ABS, prev * BELT_JUMP_REL)) {
          const kind: AirEventKind = f.carrying === true ? "fires" : "fires_nc";
          /* shared ladder: the highest fires/fires_nc level already
             pinged today is the bar — a carrying-flip can't re-claim the
             same build in different words */
          const shared = [st.seen.fires, st.seen.fires_nc]
            .filter((m): m is SeenMark => !!m && m.day === day)
            .sort((a, b) => b.level - a.level)[0];
          /* "belt" is the ping's own count clause — the note adds the
             rest of the picture (stillness, trend, the verdict tail). */
          await fire(kind, belt, {
            a: prev, b: belt, note: noteFor(["belt"]) }, shared);
        }
        if (belt !== prev) {
          st.beltFires = belt;
          st.beltAt = now.getTime();
          dirty = true;
        }
      }
    }

    if (s.alerts_band && why) {
      /* stagnation — the day's pollution isn't dispersing; fires on the
         driver's own admission as PRIMARY, re-pings only if its score
         grew. Factor floor keeps a marginal stillness off the shade:
         below 1.5× "barely mixing" is a stretch most winter days trip. */
      const stag = (why.drivers ?? []).find(
        (d) => d.kind === "stagnation" && d.weight === "primary");
      if (stag) {
        const factor = typeof stag.detail?.factor === "number" ? stag.detail.factor : 0;
        if (factor >= STAG_FACTOR_PING) {
          const score = typeof stag.score === "number" ? stag.score : 1;
          /* "stag" is the ping's own clause — the note adds belt+trend. */
          await fire("stagnation", Math.round(score * 100), {
            f: Math.max(1, Math.round(factor)),
            note: noteFor(["stag"]),
          });
        }
      }

      /* trend — the recorded city mean climbing or easing, with the
         admitted driver(s) named as the cause. The server admits the
         driver only past its own recorded-build bars; the client never
         re-derives a trend from raw data. */
      const tr = trendShift(why);
      if (tr) {
        await fire(tr.dir === "up" ? "trend_up" : "trend_down",
          Math.round(tr.delta), {
            a: Math.round(tr.from),
            b: Math.round(tr.to),
            h: Math.round(tr.spanH * 10) / 10,
            cause: causeClause(why, lang, ["trend"]),
            note: noteFor(["trend"]),
          });
      }
    }

    let dcFieldStale: boolean | null = null;
    if (wantDay) {
      const dc = await fetchDayCurve(opts.lat, opts.lon).catch(() => null);
      dcFieldStale = dc?.fieldStale ?? null;
      /* severe — the day's own mean maps to GRAP stage III+ on the
         server's CPCB path ("maps to", never "in effect"). */
      if (s.alerts_band && dc?.server?.grapStage != null &&
          dc.server.grapStage >= SEVERE_MIN_STAGE) {
        await fire("severe", dc.server.grapStage, {
          s: grapRoman(dc.server.grapStage),
          a: dc.server.grapAqi ?? "",
          note: noteFor([]),
        });
      }
      /* grap stage moves — a shift either way is its own claim (into
         ≥III stays `severe`'s above; below it and every de-escalation is
         this ladder's). Baseline rebases on every read change, like the
         band baseline — a real previous value is what makes "moved"
         honest. */
      if (s.alerts_band && dc?.server?.grapStage != null) {
        const stage = dc.server.grapStage;
        const prev = st.grapStage;
        const fresh = st.grapAt != null &&
          now.getTime() - st.grapAt <= BASELINE_MAX_AGE_MS;
        if (prev != null && fresh && stage !== prev) {
          const move = grapMove(prev, stage);
          if (move === "up" || move === "down" || move === "clear") {
            const kind: AirEventKind = move === "up" ? "grap_up"
              : move === "clear" ? "grap_clear" : "grap_down";
            await fire(kind, stage, {
              s: stage > 0 ? grapRoman(stage) : "",
              a: dc.server.grapAqi ?? "",
              note: noteFor([]),
            });
          }
        }
        if (stage !== prev) {
          st.grapStage = stage;
          st.grapAt = now.getTime();
          dirty = true;
        }
      }
      /* clean window — the day's lightest run, pinged when IST-now enters
         [start−lead, end). Level = start minute: a revised window start
         is a different event only past the revision floor. */
      if (s.alerts_windows && dc?.server?.clean && dc.server.cleanLabel) {
        const startM = labelToMin(dc.server.cleanLabel);
        const endM = labelToMin(dc.server.cleanEndLabel) ?? (startM != null ? startM + 180 : null);
        const nowM = istMinutesNow();
        if (startM != null && endM != null &&
            nowM >= startM - WINDOW_LEAD_MIN && nowM < endM) {
          await fire("window", startM, {
            win: `${dc.server.cleanLabel}–${dc.server.cleanEndLabel ?? ""}`,
            n: Math.round(dc.server.clean.conc),
          });
        }
      }
    }

    /* tomorrow's fold — the evening digest. Inside IST 17–22 "tomorrow"
       is advice; the fold's own flat floor and low-anchor note are the
       honest silences. Causes name only drivers the server admitted
       right now — present tense, never a forecast of tomorrow's met. */
    if (s.alerts_windows && outlookWindowOpen(istMinutesNow())) {
      const ol = await fetchOutlook(opts.lat, opts.lon).catch(() => null);
      const todayRow = ol?.days?.find((d) => d.label === "today");
      const tmwRow = ol?.days?.find((d) => d.label === "tomorrow");
      const move = outlookMove(todayRow?.pm25_mid ?? null, tmwRow ?? null);
      if (move && tmwRow && todayRow) {
        const kind: AirEventKind =
          move === "heavy" ? "outlook_heavy" : "outlook_light";
        const win = tmwRow.cleanest_window?.start_label
          ? t("notifyOutlookWin", lang, {
              w: `${tmwRow.cleanest_window.start_label}–${tmwRow.cleanest_window.end_label ?? ""}`,
            })
          : "";
        await fire(kind, Math.round(tmwRow.pm25_mid), {
          a: Math.round(todayRow.pm25_mid),
          b: Math.round(tmwRow.pm25_mid),
          cause: why ? causeClause(why, lang, ["trend"]) : "",
          win,
          note: noteFor(["trend"]),
        });
      }
    }

    /* yesterday on the road — the ledger's own rows, once a day. No
       server involved: a look-back can't be invented when it only
       reports what was logged. */
    if (s.alerts_reflect && st.seen.reflect?.day !== day) {
      const trips = await loadTrips().catch(() => []);
      const r = reflectSummary(trips, now.getTime());
      if (r) {
        const cmp = r.cmp
          ? t(r.cmp.dir === "heavier" ? "notifyReflectCmpHeavy"
              : r.cmp.dir === "lighter" ? "notifyReflectCmpLight"
              : "notifyReflectCmpSame", lang, {
                d: new Date(r.cmp.dayTs).toLocaleDateString(
                  lang === "hi" ? "hi-IN" : "en-IN", { weekday: "long" }),
                u: Math.round(r.cmp.ug),
              })
          : "";
        await fire("reflect", 1, {
          n: r.n,
          tr: t(r.n === 1 ? "tripNounOne" : "tripNounMany", lang),
          u: Math.round(r.ug),
          cmp,
        });
      }
    }

    /* feed stall — recorded for the diagnostics surface, never a
       notification. "No alert" is only honest when "the feed couldn't
       even be checked" is told apart from "the feed says quiet". The
       record sits in events.json next to the dedupe marks and changes
       only when a stall starts or clears (no write churn per poll). */
    const f0 = why?.evaluated?.fires;
    const stalls: string[] = [];
    if (f0 && !feedLive(f0)) stalls.push("fires");
    if (dcFieldStale === true) stalls.push("field");
    const which = stalls.length ? stalls.join("+") : null;
    const prevHealth = st.feedHealth;
    if ((prevHealth?.stalled ?? false) !== (stalls.length > 0) ||
        (prevHealth?.which ?? null) !== which) {
      if (prevHealth && _IS_DEV) {
        console.debug(
          `[events] feed ${which ? `stall: ${which}` : "recovered"}` +
          (f0?.feed_age_s != null
            ? ` — fires feed age ${Math.round(f0.feed_age_s)}s vs ` +
              `${f0.feed_stale_after_s ?? "?"}s allowed`
            : ""));
      }
      st.feedHealth = { at: now.getTime(), stalled: stalls.length > 0, which };
      dirty = true;
    }

    if (dirty) saveState(st);
  } finally {
    checking = false;
  }
}
