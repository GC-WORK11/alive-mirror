/// <reference types="node" />
/**
 * normalizeOutlook — the days-ahead card's render-safety boundary.
 * Malformed wire fields must degrade to a hidden card/marker, never a
 * render-time TypeError (the card reads heavy_hours_ist.length and
 * best_day.label.trim() unconditionally). Run: node src/api/test-runner.mjs
 */
import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { normalizeOutlook, type OutlookDay } from "./outlook";

const day = (over: Partial<OutlookDay> = {}): OutlookDay => ({
  date_ist: "2026-10-06",
  label: "tomorrow",
  partial: false,
  n_hours: 24,
  pm25_mid: 120,
  pm25_lo: 90,
  pm25_hi: 160,
  band: "poor",
  heavy_hours_ist: ["21:30", "22:30"],
  cleanest_window: null,
  confidence: "med",
  ...over,
});

describe("normalizeOutlook", () => {
  it("passes a well-formed payload through", () => {
    const o = normalizeOutlook({
      days: [day(), day({ date_ist: "2026-10-07", label: "wednesday" })],
      best_day: {
        date_ist: "2026-10-07", label: "wednesday", pm25_mid: 80,
        n_hours: 24, partial: false, delta_vs_mean: -40, line: "x",
      },
      flat: false,
      verdict: "wednesday is your cleanest day",
    });
    assert.equal(o.days.length, 2);
    assert.equal(o.best_day?.label, "wednesday");
    assert.equal(o.verdict, "wednesday is your cleanest day");
  });

  it("coerces a missing heavy_hours_ist to [] instead of crashing the detail", () => {
    const d = day();
    // @ts-expect-error simulate a wire payload missing the field
    delete d.heavy_hours_ist;
    const o = normalizeOutlook({ days: [d] });
    assert.deepEqual(o.days[0].heavy_hours_ist, []);
  });

  it("drops non-string entries inside heavy_hours_ist", () => {
    const d = day({ heavy_hours_ist: ["21:30", null, 7, "23:30"] as unknown as string[] });
    const o = normalizeOutlook({ days: [d] });
    assert.deepEqual(o.days[0].heavy_hours_ist, ["21:30", "23:30"]);
  });

  it("nulls a malformed best_day instead of crashing the Hindi caption", () => {
    const o = normalizeOutlook({
      days: [day()],
      // @ts-expect-error label missing on the wire
      best_day: { date_ist: "2026-10-06", pm25_mid: 80 },
    });
    assert.equal(o.best_day, null);
  });

  it("keeps a numeric best_day with defaults for the optional fields", () => {
    const o = normalizeOutlook({
      days: [day()],
      // @ts-expect-error minimal wire best_day
      best_day: { label: "tuesday", pm25_mid: 55 },
    });
    assert.equal(o.best_day?.delta_vs_mean, 0);
    assert.equal(o.best_day?.n_hours, 0);
    assert.equal(o.best_day?.partial, false);
  });

  it("drops days without a numeric pm25_mid or string label", () => {
    const o = normalizeOutlook({
      days: [
        day(),
        // @ts-expect-error malformed wire day
        { date_ist: "2026-10-07", label: "wednesday", pm25_mid: "high" },
        day({ date_ist: "2026-10-08" }),
      ],
    });
    assert.equal(o.days.length, 2);
    assert.equal(o.days[1].date_ist, "2026-10-08");
  });

  it("throws on a payload with no usable days → hides the card", () => {
    assert.throws(() => normalizeOutlook({ days: [] }));
    assert.throws(() => normalizeOutlook({ days: [{ pm25_mid: 1 } as unknown as OutlookDay] }));
  });

  it("is idempotent on its own output (stale-cache re-pass)", () => {
    const once = normalizeOutlook({ days: [day()] });
    const twice = normalizeOutlook(once);
    assert.deepEqual(twice, once);
  });
});
