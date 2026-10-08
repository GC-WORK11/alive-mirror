/// <reference types="node" />
/**
 * F4 (honesty-cluster) — 'today' is the server's own stamped UTC-day
 * bucket, never the last POPULATED day from the days map.
 *
 * pins:
 *   - trips.today present → that exact bucket
 *   - zero-trip day (today null, yesterday populated) → null, NOT the
 *     stale bucket relabelled 'today'  (the midnight/no-bucket regression)
 *   - no trips block at all → null
 *
 * Run: cd Mobile && node src/api/test-runner.mjs
 */
import { describe, it } from "node:test";
import assert from "node:assert/strict";

import { cityToday, type CityPayload, type CityDayTotals } from "./city";

const day = (trips: number): CityDayTotals => ({
  trips,
  km: 9.2,
  dose_ug: 44,
  co2_kg_mid: 1.1,
  pm25_g_mid: 0.2,
  switched: 1,
  modes: { bike: trips },
});

describe("cityToday — the server's stamped bucket or nothing (F4)", () => {
  it("returns the bucket the server stamped 'today'", () => {
    const d: CityPayload = {
      ts: 0,
      cached_s: 0,
      breath: null,
      field_age_s: null,
      trips: {
        today_key: "2026-10-08",
        today: day(3),
        days: { "2026-10-07": day(9), "2026-10-08": day(3) },
      },
    };
    assert.equal(cityToday(d)?.trips, 3);
  });

  it("zero-trip day: null — never yesterday's bucket under a 'today' title", () => {
    // the F4 regression: sort().pop() over days[] paints 10-07 as today
    const d: CityPayload = {
      ts: 0,
      cached_s: 0,
      breath: null,
      field_age_s: null,
      trips: {
        today_key: "2026-10-08",
        today: null,
        days: { "2026-10-06": day(5), "2026-10-07": day(9) },
      },
    };
    assert.equal(cityToday(d), null);
  });

  it("fresh store with no buckets at all → null", () => {
    const d: CityPayload = {
      ts: 0,
      cached_s: 0,
      breath: null,
      field_age_s: null,
      trips: { today_key: "2026-10-08", today: null, days: {} },
    };
    assert.equal(cityToday(d), null);
  });

  it("payload with no trips block → null, never a guess", () => {
    const d: CityPayload = { ts: 0, cached_s: 0, breath: null, field_age_s: null };
    assert.equal(cityToday(d), null);
  });
});
