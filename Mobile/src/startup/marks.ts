// Startup perf marks — a tiny ring of { name, t } stamped with
// performance.now() offsets from this module's eval (t0). index.ts imports
// it before anything else, so t0 is the earliest line we own.
//
// Read them in dev from the console/LogBox line `[perf] <name> @ <ms>` or
// programmatically: `(globalThis as any).__alivePerf.dump()`.
//
// Marks emitted by the startup lane:
//   perf:t0               module eval here (≈ start of our bundle window)
//   index:eval            index.ts body ran — the whole import tree is up
//   index:registered      registerRootComponent returned
//   app:didMount          root wrapper effect — App committed
//   app:firstFrame        first rAF after mount — ≈ first painted frame
//   plan:first            first /v2/plan response observed (fetch tap below)
//
// Docs: docs/plan/perf-r4-start.md
export type PerfMark = { name: string; t: number };

const t0 = performance.now();
const marks: PerfMark[] = [];
const seen = new Set<string>();

const isDev =
  typeof __DEV__ !== "undefined" ? __DEV__ : process.env.NODE_ENV !== "production";

export function mark(name: string): void {
  const t = performance.now() - t0;
  marks.push({ name, t });
  if (isDev) console.log(`[perf] ${name} @ ${t.toFixed(0)}ms`);
}

/** Same as mark() but only the first call with a given name lands —
 *  for marks that should fire once per launch (didMount, first plan). */
export function markOnce(name: string): void {
  if (seen.has(name)) return;
  seen.add(name);
  mark(name);
}

export function dumpMarks(): string {
  return marks.map((m) => `${m.name}=${m.t.toFixed(0)}ms`).join(" ");
}

/* ---- fetch tap: stamp the first /v2/plan response without touching the
   plan/api modules (they're owned by other lanes). Observation only — the
   Response passes through untouched; failures simply don't mark. Wrapped
   once, at module eval, before App's import tree runs its first fetch. ---- */
let planMarked = false;
const realFetch = globalThis.fetch;
if (typeof realFetch === "function") {
  globalThis.fetch = ((...args: Parameters<typeof fetch>) => {
    let isPlan = false;
    let tag: string | null = null;
    try {
      const input = args[0];
      const url = typeof input === "string" ? input : (input as { url?: string } | null)?.url;
      isPlan = typeof url === "string" && url.includes("/v2/plan");
      /* boot-path fetch taps (perf-size lane): /aqi feeds the home numeral,
         /grid feeds the air field — both are read-only timestamps. */
      if (typeof url === "string") {
        if (url.includes("/aqi?")) tag = "aqi";
        else if (url.includes("/grid?")) tag = "grid";
        else if (url.includes("/v2/day?")) tag = "daycurve";
      }
      if (isPlan) mark("plan:req");
      if (tag) mark(`${tag}:req`);
    } catch {
      /* observation must never break a request */
    }
    const p = realFetch(...args);
    try {
      if (isPlan) {
        if (!planMarked) {
          planMarked = true;
          Promise.resolve(p).then(() => markOnce("plan:first")).catch(() => {});
        }
        Promise.resolve(p).then(() => mark("plan:resp"), () => mark("plan:fail")).catch(() => {});
      }
      if (tag) {
        const t = tag;
        Promise.resolve(p)
          .then(() => mark(`${t}:resp`), () => mark(`${t}:fail`))
          .catch(() => {});
      }
    } catch {
      /* observation must never break a request */
    }
    return p;
  }) as typeof fetch;
}

(globalThis as { __alivePerf?: unknown }).__alivePerf = {
  marks,
  sinceBootMs: () => performance.now() - t0,
  dump: dumpMarks,
};

mark("perf:t0");
