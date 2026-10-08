/// <reference types="node" />
/**
 * Events-engine detectors (notify-v2, docs/lanes/notify-v2.md).
 *
 * Pure coverage over ./events-core — the detectors are deliberately
 * free of fetches so the fire/silence rules pin down without a server:
 *
 *   trendShift     /v2/why drivers[trend] + evaluated.trend
 *   grapMove       /v2/day grap.equivalent_stage transitions
 *   outlookMove    /v2/outlook tomorrow fold vs today (server flat floor)
 *   reflectSummary the ledger's own yesterday rows
 *   fired          per-day dedupe + re-ping ladders (incl. audit fixes)
 *   causeClause    names only admitted drivers, localized
 *
 * Run: cd Mobile && node src/store/test-runner.mjs
 */
import { describe, it } from "node:test";
import assert from "node:assert/strict";
import {
  causeClause, causeFieldsFromWhy, causeNote, feedLive, fired, grapMove,
  outlookMove, outlookWindowOpen, reflectSummary, trendShift,
  type V2Why,
} from "./events-core";
import type { Trip } from "./ledger";

const DAY = "2026-10-07";
const NOON = new Date(2026, 9, 7, 12, 0).getTime(); // local noon, away from day edges

const trip = (ts: number, dose_ug = 10): Trip => ({
  ts, label: "Auto-rickshaw", vehicle: "auto", dose_ug,
  avoided_ug: 0, from: "A", to: "B",
});

const why = (over: Partial<V2Why> = {}): V2Why => ({ drivers: [], ...over });

/* ---------------------------------------------------------------- trend */
describe("trendShift — the recorded city mean moving", () => {
  it("rising driver + served endpoints → up", () => {
    const w = why({
      drivers: [{ kind: "trend", direction: "rising", score: 0.8 }],
      evaluated: { trend: { delta_ug: 32.1, from_pm25: 91.2, to_pm25: 123.3, span_h: 4.5 } },
    });
    assert.deepEqual(trendShift(w),
      { dir: "up", from: 91.2, to: 123.3, spanH: 4.5, delta: 32.1 });
  });

  it("falling → down", () => {
    const w = why({
      drivers: [{ kind: "trend", direction: "falling", score: 0.4 }],
      evaluated: { trend: { delta_ug: -16.2, from_pm25: 140, to_pm25: 123.8, span_h: 5.1 } },
    });
    const t = trendShift(w);
    assert.equal(t?.dir, "down");
    assert.equal(t?.delta, 16.2);
  });

  it("no driver → silence even if evaluated.trend has a delta", () => {
    /* a sub-floor move (|Δ|<12) still lands in evaluated.trend on the
       wire — only the driver's presence is the admission */
    const w = why({ evaluated: { trend: { delta_ug: 8, from_pm25: 90, to_pm25: 98, span_h: 3 } } });
    assert.equal(trendShift(w), null);
  });

  it("driver without served endpoints → silence (never invent numbers)", () => {
    const w = why({
      drivers: [{ kind: "trend", direction: "rising" }],
      evaluated: { trend: { delta_ug: 20 } },
    });
    assert.equal(trendShift(w), null);
  });

  it("driver with a non-direction → silence", () => {
    const w = why({
      drivers: [{ kind: "trend", score: 0.5 }],
      evaluated: { trend: { delta_ug: 20, from_pm25: 90, to_pm25: 110 } },
    });
    assert.equal(trendShift(w), null);
  });
});

/* ------------------------------------------------------------- grapMove */
describe("grapMove — stage transitions, severe kept separate", () => {
  it("1→2 is 'up'; 0→1 is 'up'", () => {
    assert.equal(grapMove(1, 2), "up");
    assert.equal(grapMove(0, 1), "up");
  });
  it("arrivals into ≥III are severe's claim, not ours", () => {
    assert.equal(grapMove(2, 3), "severe");
    assert.equal(grapMove(0, 4), "severe");
  });
  it("3→2 and 4→3 are 'down'; drops to 0 are 'clear'", () => {
    assert.equal(grapMove(3, 2), "down");
    assert.equal(grapMove(4, 3), "down");
    assert.equal(grapMove(2, 0), "clear");
    assert.equal(grapMove(4, 0), "clear");
  });
  it("no baseline or no move → silence", () => {
    assert.equal(grapMove(null, 2), null);   // first read is silent — no claim
    assert.equal(grapMove(2, null), null);
    assert.equal(grapMove(2, 2), null);
  });
});

/* ---------------------------------------------------------- outlookMove */
describe("outlookMove — the fold's own difference bar", () => {
  const tmw = (pm25_mid: number, over = {}) =>
    ({ pm25_mid, n_hours: 20, confidence: "med", ...over });

  it("tomorrow +30% → heavy; −30% → light", () => {
    assert.equal(outlookMove(100, tmw(130)), "heavy");
    assert.equal(outlookMove(100, tmw(70)), "light");
  });
  it("under the flat floor (max 15µg, 15%) → silence", () => {
    assert.equal(outlookMove(100, tmw(112)), null);   // +12 < 15
    assert.equal(outlookMove(200, tmw(228)), null);   // +28 < 30 (15%)
    assert.equal(outlookMove(100, tmw(86)), null);    // −14 < 15
  });
  it("a sliver tomorrow (<6 served hours) can't claim a day", () => {
    assert.equal(outlookMove(100, tmw(200, { n_hours: 4 })), null);
  });
  it("a lo-confidence tomorrow is the fold saying 'raw model only' — silent", () => {
    assert.equal(outlookMove(100, tmw(200, { confidence: "lo" })), null);
  });
  it("missing rows → silence", () => {
    assert.equal(outlookMove(null, tmw(200)), null);
    assert.equal(outlookMove(100, null), null);
    assert.equal(outlookMove(0, tmw(200)), null);
  });
  it("the evening gate: IST 17:00–22:00 only", () => {
    assert.equal(outlookWindowOpen(17 * 60), true);
    assert.equal(outlookWindowOpen(21 * 60 + 59), true);
    assert.equal(outlookWindowOpen(16 * 60 + 59), false);
    assert.equal(outlookWindowOpen(22 * 60), false);
    assert.equal(outlookWindowOpen(9 * 60), false);
  });
});

/* -------------------------------------------------------- reflectSummary */
describe("reflectSummary — yesterday's own ledger rows", () => {
  const at = (d: number, h = 10) => new Date(2026, 9, d, h, 0).getTime();

  it("sums yesterday's real trips; comparison names the nearest trip-day", () => {
    const trips = [
      trip(at(6, 8), 40), trip(at(6, 19), 44),      // yesterday 84µg
      trip(at(4), 60),                               // two days back 60µg
      trip(at(2), 5),                                // four days back
    ];
    const r = reflectSummary(trips, NOON)!;
    assert.equal(r.n, 2);
    assert.equal(r.ug, 84);
    assert.equal(r.cmp?.dir, "heavier");             // 84 > 60×1.15=69
    assert.equal(r.cmp?.ug, 60);
  });

  it("skips empty days to find the real compare day", () => {
    const trips = [trip(at(6), 50), trip(at(1), 50)]; // yesterday 50, Oct-1 50, gap in between
    const r = reflectSummary(trips, NOON)!;
    assert.equal(r.cmp?.dir, "same");                // 50 vs 50 → honest tie
  });

  it("no yesterday trips → silence; today's trips are never 'yesterday'", () => {
    assert.equal(reflectSummary([trip(NOON - 3600e3, 30)], NOON), null);
    assert.equal(reflectSummary([], NOON), null);
  });

  it("no earlier trip-day → still fires, but no compare clause", () => {
    const r = reflectSummary([trip(at(6), 30)], NOON)!;
    assert.equal(r.n, 1);
    assert.equal(r.cmp, null);
  });

  it("zero-dose rows don't count as a day", () => {
    /* yesterday's only row carried no dose → the day doesn't exist;
       an earlier real day stays a compare candidate, never the claim */
    assert.equal(reflectSummary([trip(at(6), 0), trip(at(5), 20)], NOON), null);
    assert.equal(reflectSummary([trip(at(6), 0)], NOON), null);
  });
});

/* ---------------------------------------------------------- causeClause */
describe("causeClause — names only admitted drivers", () => {
  const smoke = { kind: "stubble_smoke", weight: "primary", detail: { wind_from_deg: 315 } };
  const stag = { kind: "stagnation", weight: "secondary" };
  const trend = { kind: "trend", direction: "rising" };

  it("smoke + stag → both named, compass localized", () => {
    const c = causeClause(why({ drivers: [smoke, stag, trend] }), "en", ["trend"]);
    assert.match(c, /stubble smoke/);
    assert.match(c, /north-west/);
    assert.match(c, /barely moving/);
  });
  it("smoke only / stag only", () => {
    assert.match(causeClause(why({ drivers: [smoke, trend] }), "en", ["trend"]), /stubble smoke/);
    assert.doesNotMatch(causeClause(why({ drivers: [smoke, trend] }), "en", ["trend"]), /barely moving/);
    assert.match(causeClause(why({ drivers: [stag, trend] }), "en", ["trend"]), /barely moving/);
  });
  it("no admitted cause → empty string, never a guessed driver", () => {
    assert.equal(causeClause(why({ drivers: [trend] }), "en", ["trend"]), "");
    assert.equal(causeClause(why(), "en", []), "");
  });
  it("hindi copy renders Devanagari, not the English key", () => {
    const c = causeClause(why({ drivers: [smoke] }), "hi", []);
    assert.match(c, /पराली/);
    assert.match(c, /उत्तर-पश्चिम/);
  });
});

/* --------------------------------------------------------------- dedupe */
describe("fired — per-day re-ping ladders", () => {
  const mark = (level: number, day = DAY) => ({ day, level });

  it("fires: 4→20 is honest (+16 ≥ max(15, 2)); 19→20 is noise", () => {
    assert.equal(fired(mark(4), "fires", 20, DAY), true);
    assert.equal(fired(mark(19), "fires", 20, DAY), false);
    assert.equal(fired(mark(20), "fires_nc", 34, DAY), false); // +14 < +15
    assert.equal(fired(mark(20), "fires_nc", 36, DAY), true);  // +16 ≥ +15
  });
  it("a new UTC day resets every kind", () => {
    assert.equal(fired(mark(19, "2026-10-06"), "fires", 20, DAY), true);
    assert.equal(fired(mark(4, "2026-10-06"), "band", 3, DAY), true);
  });
  it("window: a revised start re-pings only ≥30 min (audit fix)", () => {
    assert.equal(fired(mark(630), "window", 645, DAY), false); // 15-min wobble
    assert.equal(fired(mark(630), "window", 660, DAY), true);  // 30-min move
    assert.equal(fired(mark(660), "window", 630, DAY), true);  // earlier too
  });
  it("stagnation re-pings at +0.2 score (20 on the stored scale)", () => {
    assert.equal(fired(mark(50), "stagnation", 65, DAY), false);
    assert.equal(fired(mark(50), "stagnation", 70, DAY), true);
  });
  it("trend re-pings only on a new recorded admission (+12µg)", () => {
    assert.equal(fired(mark(30), "trend_up", 40, DAY), false);
    assert.equal(fired(mark(30), "trend_up", 42, DAY), true);
  });
  it("grap arrows: a different stage under the same arrow is a new claim", () => {
    assert.equal(fired(mark(2), "grap_up", 2, DAY), false);   // same claim
    assert.equal(fired(mark(2), "grap_down", 1, DAY), true);  // eased to I
  });
  it("outlook re-pings only on a real forecast revision (±15µg)", () => {
    assert.equal(fired(mark(140), "outlook_heavy", 150, DAY), false);
    assert.equal(fired(mark(140), "outlook_heavy", 160, DAY), true);
  });
  it("reflect fires once a day, full stop", () => {
    assert.equal(fired(undefined, "reflect", 1, DAY), true);
    assert.equal(fired(mark(1), "reflect", 1, DAY), false);
  });
});

/* -------------------------------------------------------------- feedLive */
describe("feedLive — a stale feed can't back a live claim", () => {
  it("age within the feed's own bound → live", () => {
    assert.equal(feedLive({ feed_age_s: 300, feed_stale_after_s: 900 }), true);
  });
  it("age past it → not live (the fires ping gates on this)", () => {
    assert.equal(feedLive({ feed_age_s: 901, feed_stale_after_s: 900 }), false);
  });
  it("no staleness bounds reported → can't call it stale", () => {
    assert.equal(feedLive({}), true);
    assert.equal(feedLive({ feed_age_s: 99999 }), true);
  });
});

/* --------------------------------------------------------- causeNote --- */
describe("causeFieldsFromWhy + causeNote — the parali/news line", () => {
  const beltPts = (rows: [number, number][], now = NOON) =>
    ({ window_h: 6, points: rows.map(([h, b]) =>
        ({ t: now - h * 3600_000 / 1000, belt_fires: b })) });

  it("carrying build → belt + jump + carry + stillness + tail", () => {
    const w = why({
      evaluated: {
        fires: { belt_fires: 44, carrying: true, feed_status: "live" },
        ventilation: { factor: 1.86, vc_m2s: 1612 },
        trend: { delta_ug: -15.6, from_pm25: 64.8, to_pm25: 49.2, span_h: 6 },
      },
      wind: { from_deg: 315, speed_kmh: 9 },
      history: beltPts([[5, 20], [1, 40]]),
    });
    const f = causeFieldsFromWhy(w);
    assert.equal(f.belt_delta, 24);
    assert.equal(f.basis, "measured");
    const s = causeNote(f, "en");
    assert.match(s, /44 fires in the Punjab–Haryana belt/);
    assert.match(s, /up from 20 4h ago/);
    assert.match(s, /north-west wind at 9 km\/h is carrying it our way/);
    assert.match(s, /the air is barely moving/);
    // plain frame: pace percent (1.86× stiller → ~54%) + whole µg endpoints
    assert.match(s, /~54% of its usual pace/);
    assert.match(s, /average eased 65 → 49 µg\/m³/);
    assert.match(s, /smoke coming in while the air sits still$/);
  });

  it("wind not carrying → says so plainly", () => {
    const w = why({
      evaluated: { fires: { belt_fires: 44, carrying: false, feed_status: "live" } },
      wind: { from_deg: 150, speed_kmh: 9 },
      history: beltPts([[5, 20], [1, 40]]),
    });
    const s = causeNote(causeFieldsFromWhy(w), "en");
    assert.match(s, /carrying it away from us/);
  });

  it("cold feed → count still reads, 'jumped' never claimed", () => {
    const w = why({
      evaluated: { fires: { belt_fires: 44, carrying: true, feed_status: "cold" } },
      wind: { from_deg: 315, speed_kmh: 9 },
      history: beltPts([[5, 20], [1, 40]]),
    });
    const f = causeFieldsFromWhy(w);
    assert.equal(f.belt_delta, null);        // recorded vs recorded = same number twice
    const s = causeNote(f, "en");
    assert.match(s, /44 fires/);
    assert.doesNotMatch(s, /up from|down from/);
  });

  it("below the bars → quiet words or honest background", () => {
    const quiet = causeNote(causeFieldsFromWhy(why({
      evaluated: { fires: { belt_fires: 3, feed_status: "live" } },
      history: beltPts([[5, 3], [1, 3]]),
    })), "en");
    assert.match(quiet, /the belt is quiet — 3 fires/);
    const empty = causeNote(causeFieldsFromWhy(why({ evaluated: {} })), "en");
    assert.match(empty, /the usual local air/);
  });

  it("re-count floor: |Δbelt|<5 is FIRMS noise, not a 'jump'", () => {
    const f = causeFieldsFromWhy(why({
      evaluated: { fires: { belt_fires: 44, feed_status: "live" } },
      history: beltPts([[5, 42], [1, 43]]),   // Δ=+2 vs oldest build
    }));
    assert.equal(f.belt_delta, null);
    const s = causeNote(f, "en");
    assert.doesNotMatch(s, /up from|down from/);
  });

  it("skip drops a clause the ping already narrated", () => {
    const w = why({
      evaluated: {
        fires: { belt_fires: 44, carrying: true, feed_status: "live" },
        ventilation: { factor: 1.86, vc_m2s: 1612 },
      },
      wind: { from_deg: 315, speed_kmh: 9 },
      history: beltPts([[5, 20], [1, 40]]),
    });
    const s = causeNote(causeFieldsFromWhy(w), "en", { skip: ["belt"] });
    assert.doesNotMatch(s, /fires|carrying/);
    assert.match(s, /the air is barely moving/);
  });

  it("hi renders localized — no wire English leaks", () => {
    const w = why({
      evaluated: { fires: { belt_fires: 44, carrying: true, feed_status: "live" } },
      wind: { from_deg: 315, speed_kmh: 9 },
      history: beltPts([[5, 20], [1, 40]]),
    });
    const s = causeNote(causeFieldsFromWhy(w), "hi");
    assert.match(s, /पंजाब–हरियाणा बेल्ट में 44 आग/);
    assert.doesNotMatch(s, /[a-zA-Z] fires|carrying|Delhi/);
  });

  it("null fields → empty string (a notification never pads)", () => {
    assert.equal(causeNote(null, "en"), "");
    assert.equal(causeNote(undefined, "hi"), "");
  });
});
