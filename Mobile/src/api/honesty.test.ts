/// <reference types="node" />
/**
 * F7 + F8 (honesty-cluster) — the copy contracts behind the fixes.
 *
 * pins:
 *   - F7: the suggested-limit strings exist in BOTH languages, disclose
 *     the WHO anchor + assumed volume, and never claim 'you set'
 *   - F7: the set-only strings ('a line you set', 'your daily limit')
 *     still exist for the post-pick state
 *   - F8: the app's UTC-day qualifier exists in both languages
 *   - F8: the public HTML pages print the UTC qualification where the
 *     'today' counters render (checked on the real served files, not a
 *     copy — file paths are repo-relative)
 *
 * Run: cd Mobile && node src/api/test-runner.mjs
 */
import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { t } from "../i18n/strings";

const SERVER = fileURLToPath(new URL("../../../server/", import.meta.url));

describe("F7 — suggested-limit copy, en + hi", () => {
  it("every profile's suggested line discloses the WHO anchor + volume", () => {
    for (const key of ["budgetQGeneralSugg", "budgetQSensitiveSugg", "budgetQChildSugg"] as const) {
      const en = t(key, "en", { b: 216 });
      const hi = t(key, "hi", { b: 216 });
      assert.match(en, /suggested/i, "suggestion disclosed (en)");
      assert.match(hi, /सुझा/, "suggestion disclosed (hi)");
      for (const s of [en, hi]) {
        assert.match(s, /WHO/, "WHO anchor disclosed");
        assert.match(s, /µg\/m³/, "anchor units disclosed");
        assert.match(s, /m³/, "assumed breathing volume disclosed");
      }
      assert.doesNotMatch(en, /you set|you want/i, "suggested copy must not claim user-set");
      assert.doesNotMatch(hi, /तय|ख़ुद की लकीर/, "hi suggested copy must not claim user-set");
    }
  });

  it("the suggested title/within/over never say 'your'/'you set'", () => {
    const keys = ["budgetTitleSugg", "budgetWithinSugg", "budgetOverSugg",
      "refBudgetSugg", "weekDayPctSugg"] as const;
    for (const key of keys) {
      const en = t(key, "en", { r: 10, b: 216, o: 5, p: 40 });
      const hi = t(key, "hi", { r: 10, b: 216, o: 5, p: 40 });
      assert.doesNotMatch(en, /\byour\b/i, `${key} (en) claims ownership`);
      assert.doesNotMatch(hi, /आपकी/, `${key} (hi) claims ownership`);
    }
  });

  it("the 'you set' claim survives ONLY on the post-pick strings", () => {
    assert.match(t("budgetProfileQ", "en", { b: 216 }), /a line you set/);
    assert.match(t("budgetTitle", "en"), /your/i);
    assert.match(t("budgetWithin", "en", { r: 10, b: 216 }), /your/i);
  });
});

describe("F8 — the UTC-day qualification is visible where counters print", () => {
  it("the app's own 'today' counter carries the UTC qualifier, en + hi", () => {
    assert.match(t("cityTodayUtc", "en"), /utc day/i);
    assert.match(t("cityTodayUtc", "en"), /05:30/);
    assert.match(t("cityTodayUtc", "hi"), /utc/i);
    assert.match(t("cityTodayUtc", "hi"), /05:30/);
  });

  it("community.html prints the UTC qualifier with its today counters", () => {
    const html = readFileSync(`${SERVER}community.html`, "utf8");
    assert.match(html, /utc day/i);
    assert.match(html, /05:30\s*ist/i);
  });

  it("city.html's ticker labels today-counters as the utc day", () => {
    const html = readFileSync(`${SERVER}city.html`, "utf8");
    assert.match(html, /shared trips · utc day/i);
    assert.match(html, /utc midnight — 05:30 ist/i);
  });
});
