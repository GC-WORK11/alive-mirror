// Durable outbox for POST /v2/trip donations (docs/plan/offline.md §3).
//
// A trip donation that can't reach the server is NOT lost — it goes to
// <document>/outbox.json and flushes when the network comes back.
// There is no NetInfo in this build, so "reconnect" is inferred:
//   - wireAutoFlush() listens for any successful request (net.ts "up")
//   - flush() is also a plain callable — invoke it from anywhere that
//     learns we're back (a successful search, a manual retry button)
// Bounded: past MAX_QUEUE the oldest items drop and `dropped` counts
// them honestly — the pill can say "2 trips couldn't be saved".
import { purgeJsonDoc, readJsonDoc, writeJsonDoc } from "../store/safefile";
import { onNetEvent } from "./net";

const OUTBOX_NAME = "outbox.json";
export const MAX_QUEUE = 50;
const POST_TIMEOUT_MS = 8000;

/** POST /v2/trip body (server/v2/trip.py) — the server trims, thins,
 * rounds and cell-keys the trajectory; we just must not lose it. */
export type TripDonation = {
  /** opaque device id — contributorId() from src/community.ts */
  device_token?: string;
  summary?: {
    mode?: string;
    distance_km?: number;
    duration_s?: number;
    dose_ug?: number;
    co2_kg_mid?: number;
    pm25_g_mid?: number;
    switched?: boolean;
    /* optional CO2 provenance (grams) — where the ride's tailpipe
       CO2 came from; only present when the option carried a real
       emissions.breakdown */
    co2_moving_g?: number;
    co2_idle_g?: number;
    co2_cold_g?: number;
  };
  /** [{lat,lon}…] or [[lon,lat]…] GeoJSON order — both accepted */
  trajectory?: ({ lat: number; lon: number } | [number, number])[];
};

type OutboxItem = { id: string; queuedAt: number; url: string; body: unknown };
type OutboxData = { items: OutboxItem[]; dropped: number };

/* A shared EMPTY.items array would resurrect wiped items: load() handing
   out `{...EMPTY}` shares the constant's `items` reference, so enqueue's
   push() mutates it — and after clearOutbox deletes the file, the next
   load() returns the wiped items again. Always mint a fresh object. */
const empty = (): OutboxData => ({ items: [], dropped: 0 });

async function load(): Promise<OutboxData> {
  /* atomic+.bak read: the shape check keeps a torn main from shadowing
     the previous good generation — a donation in the outbox is a
     promise the user made; we don't lose it to a bad parse */
  const j = await readJsonDoc(OUTBOX_NAME, (v): v is Partial<OutboxData> =>
    !!v && typeof v === "object" && !Array.isArray(v));
  if (!j) return empty();
  return {
    items: Array.isArray(j.items) ? j.items : [],
    dropped: typeof j.dropped === "number" ? j.dropped : 0,
  };
}

async function save(d: OutboxData): Promise<void> {
  /* atomic + .bak via safefile — a kill mid-write used to leave a torn
     outbox.json and silently lose queued donations */
  writeJsonDoc(OUTBOX_NAME, d);
}

/* ---- change notifications (pill: "N trips will send when back") --------- */

const watch = new Set<(pending: number) => void>();

/** Fires with the queue depth after every mutation. Returns unsubscribe. */
export function onQueueChange(cb: (pending: number) => void): () => void {
  watch.add(cb);
  return () => {
    watch.delete(cb);
  };
}

function notify(d: OutboxData): void {
  for (const cb of [...watch]) {
    try {
      cb(d.items.length);
    } catch {}
  }
}

/* ---- enqueue ------------------------------------------------------------ */

let idSeq = 0;

/* Wipe generation — the same guard cache.ts runs (its cacheSet takes
   `since`). Bump on every clearOutbox so a donation whose POST started
   before delete-my-data can never re-create outbox.json after the wipe
   and auto-flush on the next "up" event — a wiped user must not
   silently re-donate. */
let wipeGen = 0;
export function outboxGeneration(): number {
  return wipeGen;
}

/** Append a POST to the outbox. Over-cap items drop oldest-first and are
 * counted in `droppedNow` (and persisted in `dropped` forever after).
 * `since` = the generation captured when the request started; a wipe in
 * between means this item belongs to the deleted era — don't write. */
export async function enqueue(
  url: string,
  body: unknown,
  since?: number,
): Promise<{ size: number; droppedNow: number }> {
  const d = await load();
  if (since != null && since !== wipeGen) {
    return { size: d.items.length, droppedNow: 0 };
  }
  d.items.push({ id: `${Date.now()}-${idSeq++}`, queuedAt: Date.now(), url, body });
  let droppedNow = 0;
  while (d.items.length > MAX_QUEUE) {
    d.items.shift();
    droppedNow++;
    d.dropped++;
  }
  await save(d);
  notify(d);
  return { size: d.items.length, droppedNow };
}

/** Convenience for the donation path — pass the outboxGeneration()
 * captured when the POST started so a wipe in between drops the item. */
export function enqueueTripDonation(
  api: string,
  donation: TripDonation,
  since?: number,
): Promise<{ size: number; droppedNow: number }> {
  return enqueue(`${api}/v2/trip`, donation, since);
}

/* ---- flush -------------------------------------------------------------- */

export type FlushReport = {
  sent: number;
  /** rejected by the server (4xx) — dropped permanently, never retried */
  rejected: number;
  remaining: number;
  /** false when we stopped because the network is still down */
  networkUp: boolean;
};

let flushing = false;

async function postOne(item: OutboxItem): Promise<"sent" | "reject" | "retry"> {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), POST_TIMEOUT_MS);
  try {
    const res = await fetch(item.url, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(item.body),
      signal: ctrl.signal,
    });
    if (res.ok) return "sent";
    return res.status >= 400 && res.status < 500 ? "reject" : "retry";
  } catch {
    return "retry";
  } finally {
    clearTimeout(timer);
  }
}

/** Send queued items oldest-first. Stops at the first network/5xx
 * failure so ordering holds; 4xx items drop (they will never succeed).
 * Safe to call anytime — no-ops on an empty queue or a running flush. */
export async function flush(): Promise<FlushReport> {
  if (flushing) return { sent: 0, rejected: 0, remaining: await queueSize(), networkUp: false };
  flushing = true;
  let sent = 0;
  let rejected = 0;
  let networkUp = true;
  try {
    for (;;) {
      const d = await load();
      if (d.items.length === 0) {
        notify(d);
        return { sent, rejected, remaining: 0, networkUp };
      }
      const r = await postOne(d.items[0]);
      if (r === "retry") {
        networkUp = false;
        notify(d);
        return { sent, rejected, remaining: d.items.length, networkUp };
      }
      d.items.shift();
      if (r === "reject") rejected++;
      else sent++;
      await save(d);
      notify(d);
    }
  } finally {
    flushing = false;
  }
}

/* ---- reconnect seam ----------------------------------------------------- */

let wired = false;

/** Flush automatically whenever any request succeeds again (net.ts "up"
 * events — our NetInfo-free reconnect signal). Idempotent; returns an
 * unwire function. Call once near app start. */
export function wireAutoFlush(): () => void {
  if (wired) return () => {};
  wired = true;
  const off = onNetEvent((e) => {
    if (e.type === "up") void flush();
  });
  return () => {
    off();
    wired = false;
  };
}

/* ---- introspection ------------------------------------------------------ */

export async function queueSize(): Promise<number> {
  return (await load()).items.length;
}

/** "Delete my data" — queued donations hold device_token + trajectory.
 *  Bumping the generation runs synchronously with the call so an
 *  in-flight enqueue from the pre-wipe era dies before it can write;
 *  then delete the file and drop watchers to zero; the store has no
 *  mirror. */
export async function clearOutbox(): Promise<void> {
  wipeGen++;
  purgeJsonDoc(OUTBOX_NAME); // file + .tmp + .bak — the donation queue
                           // carries trajectory; no residue survives
  notify(empty());
}

/** Total items ever dropped for exceeding the cap — persisted, honest. */
export async function droppedTotal(): Promise<number> {
  return (await load()).dropped;
}
