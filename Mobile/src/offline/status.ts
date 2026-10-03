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
import { onNetEvent, probe } from "./net";
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
  /** pill text for the UI — "" means no pill (we're live) */
  label: string;
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

let wired = false;
function ensureWired(): void {
  if (wired) return;
  wired = true;
  onNetEvent((e) => {
    if (e.type === "up") update({ state: "online", lastOkAt: Date.now(), staleAgeS: null });
    else if (e.type === "stale") update({ state: "stale", staleAgeS: e.ageS });
    else update({ state: "offline" });
  });
  onQueueChange((n) => update({ pending: n }));
  void queueSize()
    .then((n) => update({ pending: n }))
    .catch(() => {});
  wireAutoFlush(); // outbox flushes itself the moment anything gets through
}

function labelFor(s: Snapshot): string {
  if (s.state === "online") return "";
  const pendingBit = s.pending > 0 ? ` · ${s.pending} saved to send` : "";
  if (s.state === "stale") return `offline — showing last known air${pendingBit}`;
  return `offline${pendingBit}`;
}

/** The integrator's pill state. `probeMs` is how often we re-check
 * /health *while offline or serving stale* — no polling when live
 * (requests themselves carry the signal). */
export function useNetStatus(probeMs = 20000): NetStatus {
  ensureWired();
  const s = useSyncExternalStore(subscribe, () => snap);

  useEffect(() => {
    void probe(API); // ground truth once on mount — don't trust the default
    const iv = setInterval(() => {
      if (snap.state !== "online") void probe(API);
    }, probeMs);
    return () => clearInterval(iv);
  }, [probeMs]);

  return { ...s, label: labelFor(s), refresh: () => probe(API) };
}
