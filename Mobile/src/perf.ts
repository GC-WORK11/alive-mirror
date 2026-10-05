/** perf lane instrumentation (docs/lanes/perf-fps.md).
 *
 *  Everything here is a no-op unless PERF_ON is true — flip it locally to
 *  measure, keep it false in commits. Two sinks: console (dev client →
 *  Metro / `log stream`) and a JSONL file (release .app — pull it from
 *  the app container):
 *
 *    xcrun simctl get_app_container <udid> com.anonymous.app data
 *      → Documents/perf_log.jsonl
 *
 *  bump("tag")          — count a render/commit site
 *  mark("name")         — timestamped boot/frame point
 *  report("tag")        — dump counters since the last report
 *  jank("label", ms)    — rAF probe: frames >1.5× budgeted gap = dropped
 */
import { File, Paths } from "expo-file-system";

export const PERF_ON = false;

const LOG = new File(Paths.document, "perf_log.jsonl");
const counts = new Map<string, number>();
const t0 = performance.now();

/* windowed render-count dumps — pull the JSONL after a drive and diff
   adjacent `auto` buckets for per-gesture render deltas */
if (PERF_ON) setInterval(() => report("auto"), 20000);
let sinkReady = false;
const pending: string[] = [];

const emit = (kind: string, payload: Record<string, unknown>) => {
  const line = JSON.stringify({ k: kind, t: +(performance.now() - t0).toFixed(1), ...payload });
  // console.log reaches Metro in dev and the device log stream in release
  console.log(`[PERF] ${line}`);
  try {
    if (!LOG.exists) LOG.create();
    LOG.write(line + "\n", { append: true });
  } catch {
    pending.push(line);
  }
  if (!sinkReady) sinkReady = true;
};

/** Count a render site. Cheap enough to leave in at PERF_ON=false. */
export function bump(tag: string) {
  if (!PERF_ON) return;
  counts.set(tag, (counts.get(tag) ?? 0) + 1);
}

/** Timestamped point — module eval, font gate, first fetch, first paint. */
export function mark(name: string) {
  if (!PERF_ON) return;
  emit("mark", { name });
}

/** Dump counters + reset — call on an interval or from a probe. */
export function report(tag = "tick") {
  if (!PERF_ON) return;
  emit("renders", {
    tag,
    counts: Object.fromEntries(counts),
    total: [...counts.values()].reduce((a, b) => a + b, 0),
  });
  counts.clear();
}

/** rAF jank probe: for `winMs`, count rAF ticks and the ones arriving
 *  >1.5 frames late. Runs the probe OFF the measured tree (mount it as a
 *  sibling) so it measures JS-thread starvation, not its own render. */
export function jank(label: string, winMs = 1200, cb?: (r: JankResult) => void) {
  if (!PERF_ON) return;
  const res: JankResult = { label, ticks: 0, dropped: 0, maxGapMs: 0, sumGapMs: 0 };
  let last = performance.now();
  const stop = last + winMs;
  let raf = 0;
  const step = () => {
    const now = performance.now();
    const gap = now - last;
    last = now;
    res.ticks += 1;
    res.sumGapMs += gap;
    if (gap > res.maxGapMs) res.maxGapMs = gap;
    if (gap > 25) res.dropped += 1; // >1.5 frames @60fps — a visibly late frame
    if (now < stop) raf = requestAnimationFrame(step);
    else {
      res.avgGapMs = +(res.sumGapMs / Math.max(1, res.ticks)).toFixed(2);
      emit("jank", res);
      cb?.(res);
    }
  };
  raf = requestAnimationFrame(step);
  return () => cancelAnimationFrame(raf);
}

export type JankResult = {
  label: string; ticks: number; dropped: number; maxGapMs: number;
  sumGapMs: number; avgGapMs?: number;
};

/* boot marks — eval'd once when this module first loads (PERF_ON-gated) */
if (PERF_ON) emit("mark", { name: "perf.eval" });
