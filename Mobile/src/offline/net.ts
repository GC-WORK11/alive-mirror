// fetchCached — network-first, last-good fallback (docs/plan/offline.md §2).
//
//   try network (6 s timeout)
//     → success: persist to the TTL cache, return fresh
//     → failure: return the cached copy with { stale:true, ageS }
//                so the UI can label it; nothing cached → honest null
//
// Also owns the app's network event bus — there is no NetInfo in this
// build, so connectivity is *inferred from our own requests*: every
// success/failure here (and every probe()) is how the pill and the
// outbox learn the network came back. Never claim online on guesswork.
import { API } from "../components/shell/net";
import { cacheGeneration, cachePeek, cacheSet } from "../api/cache";

export const NET_TIMEOUT_MS = 6000;

/** Discriminated so the UI can't show a number without knowing its age. */
export type NetResult<T> =
  | { ok: true; data: T; stale: false; ageS: 0 }
  | { ok: true; data: T; stale: true; ageS: number; expired: boolean }
  | { ok: false; data: null };

export type FetchCachedOpts<T> = {
  /** freshness window stored with the entry; past it, a served copy is
   * flagged `expired` so the UI can dim harder — last-good still serves */
  ttlMs: number;
  /** cache key; defaults to url. Supply one for POSTs where the body
   * (not the URL) identifies the resource — e.g. cacheKeys.plan(...) */
  key?: string;
  /** overrides the default GET-json fetch — pass for POST/headers.
   * Receives the abort signal; use it. */
  fetcher?: (signal: AbortSignal) => Promise<T>;
  /** default NET_TIMEOUT_MS (6 s) */
  timeoutMs?: number;
};

/* ---- network event bus -------------------------------------------------- */

export type NetEvent =
  | { type: "up" }                                   // a request landed
  | { type: "stale"; key: string; ageS: number }     // serving last-good
  | { type: "down" };                                // failed, nothing cached

const listeners = new Set<(e: NetEvent) => void>();

/** Subscribe to inferred connectivity. Returns unsubscribe. */
export function onNetEvent(cb: (e: NetEvent) => void): () => void {
  listeners.add(cb);
  return () => {
    listeners.delete(cb);
  };
}

function emit(e: NetEvent): void {
  for (const cb of [...listeners]) {
    try {
      cb(e);
    } catch {}
  }
}

/* ---- fetchCached -------------------------------------------------------- */

const inflight = new Map<string, Promise<NetResult<unknown>>>();

/** Two abort signals fused into one: the request dies on EITHER — the
 * caller's unmount/cancel AND fetchCached's timeout. (AbortSignal.any
 * isn't in every Hermes build.) Use wherever a fetcher overrides the
 * signal it was handed — the timeout must never be silently dropped. */
export function linkSignals(caller: AbortSignal | undefined | null, inner: AbortSignal): AbortSignal {
  if (!caller) return inner;
  if (caller.aborted) return caller;
  const c = new AbortController();
  const fire = () => c.abort();
  caller.addEventListener("abort", fire, { once: true });
  inner.addEventListener("abort", fire, { once: true });
  return c.signal;
}

async function defaultFetcher<T>(url: string, signal: AbortSignal): Promise<T> {
  const res = await fetch(url, { signal });
  if (!res.ok) throw new Error(`http ${res.status}`);
  return (await res.json()) as T;
}

/** The one call every network-backed read should go through when the
 * feature can degrade. Never throws — failure is data, not an exception. */
export function fetchCached<T>(url: string, opts: FetchCachedOpts<T>): Promise<NetResult<T>> {
  const key = opts.key ?? url;
  const pending = inflight.get(key);
  if (pending) return pending as Promise<NetResult<T>>;

  const run = (async (): Promise<NetResult<T>> => {
    /* generation captured at request start — delete-my-data bumps it, so
       a late resolve after the wipe must not resurrect the file (S2:
       route-GPS coords surviving an honest delete). */
    const gen = cacheGeneration();
    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), opts.timeoutMs ?? NET_TIMEOUT_MS);
    try {
      const data = opts.fetcher
        ? await opts.fetcher(ctrl.signal)
        : await defaultFetcher<T>(url, ctrl.signal);
      await cacheSet(key, data, opts.ttlMs, gen);
      emit({ type: "up" });
      return { ok: true, data, stale: false, ageS: 0 };
    } catch {
      const hit = await cachePeek<T>(key);
      if (hit) {
        emit({ type: "stale", key, ageS: hit.ageS });
        return { ok: true, data: hit.value, stale: true, ageS: hit.ageS, expired: !hit.fresh };
      }
      emit({ type: "down" });
      return { ok: false, data: null };
    } finally {
      clearTimeout(timer);
    }
  })().finally(() => {
    inflight.delete(key);
  });

  inflight.set(key, run);
  return run;
}

/** Cheap reachability check — GET /health with a short timeout. This is
 * our NetInfo substitute: call it to detect recovery while offline.
 * Emits up/down so subscribers (pill, outbox) react. */
export async function probe(api: string = API, timeoutMs = 4000): Promise<boolean> {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), timeoutMs);
  try {
    const res = await fetch(`${api}/health`, { signal: ctrl.signal });
    const up = res.ok;
    emit(up ? { type: "up" } : { type: "down" });
    return up;
  } catch {
    emit({ type: "down" });
    return false;
  } finally {
    clearTimeout(timer);
  }
}
