// useNetStatus — the one honest answer to "are we live right now?"
// (docs/plan/offline.md §4).
//
//   "online"  — the last request landed: show numbers normally
//   "stale"   — the screen is showing last-known data: pill says so
//   "offline" — nothing to show: pill says offline, no fake numbers
//
// No NetInfo dependency in this build — state is inferred from real
// request outcomes (net.ts events) plus a small /health probe that runs
// only while we're not online, to catch the network coming back.
import { useEffect, useSyncExternalStore } from "react";
import { API } from "../components/shell/net";
import { onNetEvent, probe, type NetEvent } from "./net";
import { onQueueChange, queueSize, wireAutoFlush } from "./queue";

export type NetState = "online" | "stale" | "offline";

export type NetStatus = {
  state: NetState;
  /** epoch ms of last confirmed server contact, null if never */
  lastOkAt: number | null;
  /** age in seconds of the last-known copy being shown (stale only) */
  staleAgeS: number | null;
  /** trip donations waiting to send */
  pending: number;
  /** kick a reachability probe (e.g. a "retry" tap) */
  refresh: () => Promise<boolean>;
};

type Snapshot = {
  state: NetState;
  lastOkAt: number | null;
  staleAgeS: number | null;
  pending: number;
};

let snap: Snapshot = { state: "online", lastOkAt: null, staleAgeS: null, pending: 0 };
const subs = new Set<() => void>();

function subscribe(cb: () => void): () => void {
  subs.add(cb);
  return () => {
    subs.delete(cb);
  };
}

function update(next: Partial<Snapshot>): void {
  snap = { ...snap, ...next };
  for (const cb of [...subs]) {
    try {
      cb();
    } catch {}
  }
}

/* one dropped request used to flash "offline — showing last known air"
   on a working connection (component-audit #24). The pill may only claim
   a dead network after FAILS_BEFORE_OFFLINE consecutive failed reads —
   a single flap inside a burst of healthy polls stays silent. */
const FAILS_BEFORE_OFFLINE = 3;
let failStreak = 0;

/* the live /health probe — swappable so the debounce contract can be
   exercised headless in tests (status.test.ts) without a socket. */
let probeImpl: (api?: string, timeoutMs?: number) => Promise<boolean> = probe;

export function handleNetEvent(e: NetEvent): void {
  if (e.type === "up") {
    failStreak = 0;
    update({ state: "online", lastOkAt: Date.now(), staleAgeS: null });
    return;
  }
  failStreak += 1;
  if (failStreak < FAILS_BEFORE_OFFLINE) return;
  if (e.type === "stale") update({ state: "stale", staleAgeS: e.ageS });
  else update({ state: "offline" });
  /* re-check on recovery — the moment we go non-online, probe once so
     a false flap corrects itself inside ~4 s instead of waiting for
     the next request or the 20 s interval */
  if (failStreak === FAILS_BEFORE_OFFLINE) void probeImpl(API);
}

/** Test seam — read the pill state and stub the probe; production
 * callers only ever see `useNetStatus`. */
export function statusForTest(stub?: typeof probe): Snapshot & { failStreak: number } {
  if (stub) probeImpl = stub;
  return { ...snap, failStreak };
}

let wired = false;
function ensureWired(): void {
  if (wired) return;
  wired = true;
  onNetEvent(handleNetEvent);
  onQueueChange((n) => update({ pending: n }));
  void queueSize()
    .then((n) => update({ pending: n }))
    .catch(() => {});
  wireAutoFlush(); // outbox flushes itself the moment anything gets through
}

/** The integrator's pill state. `probeMs` is how often we re-check
 * /health *while offline or serving stale* — no polling when live
 * (requests themselves carry the signal). */
export function useNetStatus(probeMs = 20000): NetStatus {
  ensureWired();
  const s = useSyncExternalStore(subscribe, () => snap);

  useEffect(() => {
    void probe(API); // ground truth once on mount — don't trust the default
    /* cold boot on a dead network: the mount probe alone brings the
       streak to 1 and — because silent fetches (shell fetchJson) don't
       emit net events — nothing ever pushes it to the threshold, so the
       pill used to sit hidden forever on exactly the surface it exists
       for (e2e-residual: offline film's missing pill). While a streak is
       accumulating but not yet tripped, keep probing on a short leash —
       each failed probe emits "down", feeding the streak until the pill
       earns its say or a real "up" clears it. */
    let retry: ReturnType<typeof setTimeout> | null = null;
    const kick = () => {
      if (retry) return;
      retry = setTimeout(() => {
        retry = null;
        if (snap.state === "online" && failStreak > 0) void probe(API);
      }, 4000);
    };
    const off = onNetEvent((e) => { if (e.type !== "up") kick(); });
    const iv = setInterval(() => {
      if (snap.state !== "online" || failStreak > 0) void probe(API);
    }, probeMs);
    return () => {
      clearInterval(iv);
      if (retry) clearTimeout(retry);
      off();
    };
  }, [probeMs]);

  return { ...s, refresh: () => probe(API) };
}
