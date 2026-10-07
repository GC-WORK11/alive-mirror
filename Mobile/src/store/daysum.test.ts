/// <reference types="node" />
/**
 * Day-sum rollup — the on-device analytics engine (docs/lanes/pocket-engine).
 *
 * Covers: honest empty, seal-once semantics, mutation-driven invalidation
 * (logTrip/deleteTrip/recordSample fire through the store hooks — no
 * caller involvement), the persisted dirty set, checksummed envelope,
 * .bak fallback, retention/arc pruning, lang re-seal, and the
 * delete-my-data wipe path.
 *
 * Run: cd Mobile && node src/store/test-runner.mjs
 */
import { describe, it, beforeEach } from "node:test";
import assert from "node:assert/strict";
import { fnv1a, readJsonDoc, writeJsonDoc } from "./safefile";
import {
  logTrip, loadTrips, deleteTrip, resetLedgerCache, type Trip,
} from "./ledger";
import {
  recordSample, allSamples, dayKey, resetDaylogCache, type AmbientSample,
} from "./daylog";
import { getDay, getDays, invalidateDay, resetDaySum } from "./daysum";
import { clearAllData } from "../components/shell/settings";

/* the stub fs map the runner installs — assertion surface for what
   actually landed on "disk" */
const FS = () =>
  (globalThis as { __storetest_fs?: Map<string, string> }).__storetest_fs!;
const DOC = (name: string) => `/storetest-docs/${name}`;

/* let the serialized writeTails drain */
const flush = async () => {
  for (let i = 0; i < 4; i++) await new Promise((r) => setImmediate(r));
};

/* a day safely outside every other fixture's window (and inside the
   21-day sample keep window) */
const DAY_TS = Date.now() - 10 * 24 * 3600 * 1000;
const DAY = dayKey(DAY_TS);
const atHour = (h: number, m = 0) => {
  const d = new Date(DAY_TS);
  d.setHours(h, m, 0, 0);
  return d.getTime();
};

const samp = (ts: number, amb = 60, bz = 66): AmbientSample =>
  ({ ts, lat: 29.5, lon: 77.0, amb, bz });
const trip = (ts: number, dose_ug: number, vehicle = "auto"): Trip => ({
  ts, label: "Auto-rickshaw", vehicle, dose_ug, avoided_ug: 5,
  from: "Alpha", to: "Beta",
});

async function wipe(): Promise<void> {
  resetDaySum();
  resetDaylogCache();
  resetLedgerCache();
  const s = FS();
  for (const k of [...s.keys()]) {
    if (/daysum|ledger|daylog/.test(k)) s.delete(k);
  }
}

describe("daysum — sealed day aggregates", () => {
  beforeEach(wipe);

  it("a day with no inputs reads honest empty — never a fabricated dose", async () => {
    const s = await getDay(DAY, "en");
    assert.equal(s.rec.totalUg, 0);
    assert.equal(s.trips, 0);
    assert.equal(s.trip_ug, 0);
    assert.equal(s.rec.thin, true);
    assert.deepEqual(s.modes, {});
  });

  it("seals real dose from real samples + trips, once", async () => {
    await recordSample(samp(atHour(10, 0)));
    await recordSample(samp(atHour(10, 30))); // 30-min covered span, 66 bz
    await logTrip(trip(atHour(12, 0), 17.6));
    const s1 = await getDay(DAY, "en");
    // stay: 66 µg/m³ × 0.6 m³/h × 0.5 h = 19.8; trip 17.6 → 37.4
    assert.equal(s1.rec.totalUg, 37.4);
    assert.equal(s1.trip_ug, 17.6);
    assert.equal(s1.stay_ug, 19.8);
    assert.equal(s1.trips, 1);
    assert.equal(s1.modes.auto.n, 1);
    assert.equal(s1.modes.auto.ug, 17.6);
    const s2 = await getDay(DAY, "en");
    assert.strictEqual(s2, s1, "sealed day must not recompute on a clean read");
  });

  it("a new trip marks only its own day dirty", async () => {
    const other = dayKey(DAY_TS - 24 * 3600 * 1000);
    await logTrip(trip(atHour(9), 10));
    const s1 = await getDay(DAY, "en");
    const o1 = await getDay(other, "en");
    await logTrip(trip(atHour(14), 5));       // same day → invalidate DAY
    const s2 = await getDay(DAY, "en");
    const o2 = await getDay(other, "en");
    assert.equal(s2.rec.totalUg, 15, "DAY re-sealed with both trips");
    assert.notStrictEqual(s2, s1);
    assert.strictEqual(o2, o1, "untouched day stays sealed");
  });

  it("deleteTrip re-seals the day without the removed trip", async () => {
    await logTrip(trip(atHour(9), 10));
    await logTrip(trip(atHour(10), 5));
    await getDay(DAY, "en");
    await deleteTrip({
      ts: atHour(9), from: "Alpha", to: "Beta", vehicle: "auto",
    });
    const s = await getDay(DAY, "en");
    assert.equal(s.rec.totalUg, 5);
    assert.equal(s.trips, 1);
  });

  it("recordSample arrival dirties the day through the hook", async () => {
    const s1 = await getDay(DAY, "en");
    assert.equal(s1.rec.totalUg, 0);
    await recordSample(samp(atHour(8, 0)));
    await recordSample(samp(atHour(8, 40))); // 40-min gap ≤ 45 → covered
    const s2 = await getDay(DAY, "en");
    assert.equal(s2.rec.coveredMin, 40);
    assert.ok(s2.rec.totalUg > 0);
  });

  it("lang flip re-seals so stored labels re-render", async () => {
    await logTrip(trip(atHour(9), 10));
    const en = await getDay(DAY, "en");
    const hi = await getDay(DAY, "hi");
    assert.equal(hi.lang, "hi");
    assert.notStrictEqual(hi, en);
  });

  it("persists a checksummed envelope; dirty marks survive", async () => {
    await getDay(DAY, "en");
    invalidateDay(DAY);
    await flush();
    const raw = FS().get(DOC("daysum.json"));
    assert.ok(raw, "daysum.json written");
    const env = JSON.parse(raw!) as { v: number; sum: string; d: { days: Record<string, unknown>; dirty: string[] } };
    assert.equal(env.v, 1);
    assert.equal(env.sum, fnv1a(JSON.stringify(env.d)), "checksum verifies");
    assert.ok(env.d.dirty.includes(DAY), "dirty mark persisted");
    assert.ok(env.d.days[DAY], "day record sealed");
  });

  it("corrupt main → falls back to .bak; corrupt both → honest empty", async () => {
    writeJsonDoc("daysum.json", { days: { X: { marker: true } }, dirty: [] }, { checksum: true });
    const good = FS().get(DOC("daysum.json"))!;
    FS().set(DOC("daysum.json.bak"), good);   // previous good generation
    FS().set(DOC("daysum.json"), "garbage{{{not json");
    type EnvelopeData = { days: Record<string, { marker?: boolean }>; dirty: string[] };
    const j = await readJsonDoc<EnvelopeData>("daysum.json",
      (v): v is EnvelopeData =>
        v != null && typeof v === "object" &&
        typeof (v as EnvelopeData).days === "object" &&
        Array.isArray((v as EnvelopeData).dirty),
      { checksum: true });
    assert.ok(j && j.days.X, "served the .bak generation");
    FS().set(DOC("daysum.json.bak"), "also garbage");
    const j2 = await readJsonDoc<EnvelopeData>("daysum.json",
      (v): v is EnvelopeData =>
        v != null && typeof v === "object" &&
        typeof (v as EnvelopeData).days === "object" &&
        Array.isArray((v as EnvelopeData).dirty),
      { checksum: true });
    assert.equal(j2, null);
  });

  it("a mid-day sealed record re-seals final once the day ends", async () => {
    const yesterday = dayKey(Date.now() - 24 * 3600 * 1000);
    const yStart = new Date(`${yesterday}T00:00:00`).getTime();
    writeJsonDoc("daysum.json", {
      days: {
        [yesterday]: {
          rec: { day: yesterday, arc: [], totalUg: 3, coveredMin: 30,
                 parts: [], thin: false, samplesToday: 4 },
          trip_ug: 0, stay_ug: 3, trips: 0, modes: {}, lang: "en",
          at: yStart + 12 * 3600 * 1000,      // sealed at midday
          partial: true,
        },
      },
      dirty: [],
    }, { checksum: true });
    const s = await getDay(yesterday, "en");
    assert.equal(s.partial, false, "day over → final seal");
    assert.ok(s.at > yStart + 12 * 3600 * 1000);
  });

  it("retention: ≤400 day keys, arcs pruned past 14 days", async () => {
    const days: Record<string, unknown> = {};
    for (let i = 0; i < 410; i++) {
      const k = dayKey(Date.now() - i * 24 * 3600 * 1000);
      days[k] = {
        rec: { day: k, arc: [{ hour: 9, conc: 50, dose_ug: 1, covered: true, trip_marks: 0 }],
               totalUg: 1, coveredMin: 10, parts: [], thin: false, samplesToday: 1 },
        trip_ug: 0, stay_ug: 1, trips: 0, modes: {}, lang: "en",
        at: Date.now(), partial: false,
      };
    }
    writeJsonDoc("daysum.json", { days, dirty: [] }, { checksum: true });
    const probe = dayKey(Date.now() - 3 * 24 * 3600 * 1000);
    /* load (prunes in mem) then a fresh-day seal to force the pruned
       state out to the file */
    await getDay(dayKey(Date.now() + 2 * 24 * 3600 * 1000), "en");
    await getDay(probe, "en");
    await flush();
    const env = JSON.parse(FS().get(DOC("daysum.json"))!) as
      { d: { days: Record<string, { arcPruned?: boolean; rec: { arc: unknown[] } }> } };
    const keys = Object.keys(env.d.days);
    assert.ok(keys.length <= 400, `bounded: ${keys.length} ≤ 400`);
    const old = env.d.days[dayKey(Date.now() - 30 * 24 * 3600 * 1000)];
    if (old) assert.equal(old.rec.arc.length, 0, "old arc pruned");
    const recent = env.d.days[probe];
    assert.ok(recent.rec.arc.length > 0, "recent arc kept");
  });

  it("getDays batch-reads a set", async () => {
    await logTrip(trip(atHour(9), 10));
    const other = dayKey(DAY_TS - 24 * 3600 * 1000);
    const m = await getDays([DAY, other], "en");
    assert.equal(m[DAY].rec.totalUg, 10);
    assert.equal(m[other].rec.totalUg, 0);
  });
});

describe("delete my data — wipe completeness", () => {
  it("clearAllData removes daysum + safefile artifacts and all mirrors", async () => {
    await recordSample(samp(atHour(10, 0)));
    await logTrip(trip(atHour(12, 0), 9));
    await getDay(DAY, "en");
    await flush();
    const s = FS();
    assert.ok(s.get(DOC("daysum.json")), "rollup exists pre-wipe");
    assert.ok(s.get(DOC("ledger.json")), "ledger exists pre-wipe");

    clearAllData();

    for (const k of [...s.keys()]) {
      assert.ok(
        !/^\/storetest-docs\/(daysum|ledger|daylog)\.json/.test(k),
        `${k} survived the wipe`,
      );
    }
    /* and nothing resurrects: mirrors dropped, next reads are honestly
       empty (the daylog mirror used to re-write its wiped file) */
    assert.equal((await loadTrips()).length, 0);
    assert.equal((await allSamples()).length, 0);
    const d = await getDay(DAY, "en");
    assert.equal(d.rec.totalUg, 0);
    assert.equal(d.trips, 0);
  });
});
