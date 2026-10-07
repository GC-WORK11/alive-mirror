// Air-event engine — client-side detection over the app's existing GETs
// (docs/lanes/events-notify.md).
//
// Honesty contract (same as the rest of the app — zero fake):
//  - every notification traces to a served field, verbatim:
//      fires       ← /v2/why  evaluated.fires.belt_fires + carrying + feed age
//      band        ← the /aqi poll's own pm25_ambient (the "around you" read)
//      window      ← /v2/day  cleanest_window (via fetchDayCurve's server block)
//      stagnation  ← /v2/why  drivers[] kind=stagnation weight=primary
//      severe      ← /v2/day  grap.equivalent_stage (the server's own "maps to")
//  - jump claims (fires, band) need a baseline — the first observed value is
//    stored silently; only a LATER read can show a change. A baseline older
//    than BASELINE_MAX_AGE can't claim "since last check" and is rebaselined.
//  - a stale fires feed can't claim a live build — feed_age_s must sit inside
//    feed_stale_after_s when the feed reports both.
//  - dedupe is per UTC-day per kind, and "unless it worsens again" means the
//    same kind re-pings only past the level already notified (see fired()).
//
// Baselines persist in events.json (expo-file-system — the house convention;
// the repo carries no AsyncStorage). Everything in it is a count, a band
// index, or a timestamp — no location, nothing personal; "delete my data"
// wipes it like the other stores (settings.ts wipe list + resetEventsStore
// from App's deleteAll).
import { File, Paths } from "expo-file-system";
import { bandIdx } from "../theme";
import { API, fetchJson } from "../components/shell/net";
import { loadSettings } from "../components/shell/settings";
import { fetchDayCurve } from "../api/dayfield";
import { notifyAirEvent, requestPerms, type AirEventKind } from "../notify";
import type { Lang } from "../i18n/strings";

/* ---- thresholds — each mirrors a server-side claim floor so the client
   never applies a weaker bar than the explainer itself (server/v2/why.py). */
/** server's own "the belt isn't a headline" floor (SMOKE_MIN_BELT). */
const BELT_MIN = 10;
/** a build claim needs +15 fires or +50% over the baseline — FIRMS daily
    CSVs re-count a few points on refetch; under this it's feed noise. */
const BELT_JUMP_ABS = 15;
const BELT_JUMP_REL = 0.5;
/** band pings start at CPCB "poor" (idx 3, >90 µg/m³) — "turned moderate"
    isn't a ping. */
const BAND_MIN_IDX = 3;
/** a baseline older than this can't back a "since the last check" claim. */
const BASELINE_MAX_AGE_MS = 18 * 60 * 60 * 1000;
/** clean-window ping fires when IST-now sits inside [start−lead, end). */
const WINDOW_LEAD_MIN = 60;
/** GRAP-equivalent stage at which the day reads "severe" (stage III). */
const SEVERE_MIN_STAGE = 3;
/** stagnation re-pings only when the driver score grew this much (0–1). */
const STAG_SCORE_STEP = 0.2;
/** /v2/why is the heavy read (snapshot history) — cap at one call / 10 min. */
const WHY_MIN_MS = 10 * 60 * 1000;

/* ---- persisted state ---------------------------------------------------- */
type SeenMark = { day: string; level: number };
type AirEventState = {
  /** last burn-belt count + when it was read (jump baseline). */
  beltFires: number | null;
  beltAt: number | null;
  /** last ambient band index + when read (crossing baseline). */
  bandIdx: number | null;
  bandAt: number | null;
  seen: Partial<Record<AirEventKind, SeenMark>>;
};

const EMPTY: AirEventState = {
  beltFires: null, beltAt: null, bandIdx: null, bandAt: null, seen: {},
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

/* ---- dedupe: once per UTC-day per kind, re-ping only when worse ---------- */
const utcDay = (d: Date) => d.toISOString().slice(0, 10);

/** Is `level` worth a ping given what we already notified today? */
function fired(mark: SeenMark | undefined, kind: AirEventKind,
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
    case "window":     // a different start time is a different window
      return level !== mark.level;
  }
}

/* ---- /v2/why — the bits the engine reads (full shape: server/v2/why.py) -- */
type V2WhyDriver = { kind?: string; weight?: string; score?: number };
type V2Why = {
  drivers?: V2WhyDriver[];
  evaluated?: {
    fires?: {
      seen?: boolean;
      belt_fires?: number | null;
      n_fires?: number | null;
      carrying?: boolean | null;
      feed_age_s?: number | null;
      feed_stale_after_s?: number | null;
    } | null;
  } | null;
};

const feedLive = (f: NonNullable<NonNullable<V2Why["evaluated"]>["fires"]>): boolean =>
  f.feed_age_s == null || f.feed_stale_after_s == null
    ? true                                    // feed gave no staleness bounds
    : f.feed_age_s <= f.feed_stale_after_s;

/** IST wall-clock minutes right now (label math mirrors _ist_label). */
const istMinutesNow = (): number => {
  const ist = new Date(Date.now() + 330 * 60 * 1000);
  return ist.getUTCHours() * 60 + ist.getUTCMinutes();
};
const labelToMin = (lab: string | null | undefined): number | null => {
  const m = /^(\d{1,2}):(\d{2})$/.exec(lab ?? "");
  return m ? Number(m[1]) * 60 + Number(m[2]) : null;
};

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
                        vars: Record<string, string | number>): Promise<void> => {
      if (!fired(st.seen[kind], kind, level, day)) return;
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
        await fire("band", idx, { idx, prev, n: Math.round(opts.ambientUg) });
      }
      if (idx != null && idx !== prev) {
        st.bandIdx = idx;
        st.bandAt = now.getTime();
        dirty = true;
      }
    }

    /* ---- remote reads: /v2/why carries the fires feed + the driver list;
       /v2/day carries the served windows + the GRAP-equivalent stage.
       why is throttled; the day curve shares the UI's 15-min cache. ---- */
    const wantWhy = s.alerts_fires || s.alerts_band;
    const wantDay = s.alerts_windows || s.alerts_band;
    let why: V2Why | null = null;
    if (wantWhy && now.getTime() - lastWhyAt >= WHY_MIN_MS) {
      lastWhyAt = now.getTime();         // stamped before the await — a slow
      why = await fetchJson(`${API}/v2/why?lat=${opts.lat}&lon=${opts.lon}`, 9000)
        .then((j) => (j && typeof j === "object" ? (j as V2Why) : null))
        .catch(() => null);
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
          await fire(kind, belt, { a: prev, b: belt });
        }
        if (belt !== prev) {
          st.beltFires = belt;
          st.beltAt = now.getTime();
          dirty = true;
        }
      }
    }

    /* stagnation — the day's pollution isn't dispersing; fires on the
       driver's own admission as PRIMARY, re-pings only if its score grew. */
    if (s.alerts_band && why) {
      const stag = (why.drivers ?? []).find(
        (d) => d.kind === "stagnation" && d.weight === "primary");
      if (stag) {
        const score = typeof stag.score === "number" ? stag.score : 1;
        await fire("stagnation", Math.round(score * 100), {
          f: Math.max(1, Math.round(((stag as { detail?: { factor?: number } })
            .detail?.factor ?? 0))),
        });
      }
    }

    if (wantDay) {
      const dc = await fetchDayCurve(opts.lat, opts.lon).catch(() => null);
      /* severe — the day's own mean maps to GRAP stage III+ on the
         server's CPCB path ("maps to", never "in effect"). */
      if (s.alerts_band && dc?.server?.grapStage != null &&
          dc.server.grapStage >= SEVERE_MIN_STAGE) {
        await fire("severe", dc.server.grapStage, {
          s: ["", "I", "II", "III", "IV"][Math.min(4, Math.max(1, dc.server.grapStage))],
          a: dc.server.grapAqi ?? "",
        });
      }
      /* clean window — the day's lightest run, pinged when IST-now enters
         [start−lead, end). Level = start minute: a revised window start
         is a different event, an unchanged one is not. */
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

    if (dirty) saveState(st);
  } finally {
    checking = false;
  }
}
