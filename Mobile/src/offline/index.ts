// Offline lane — one import for the integrator (docs/plan/offline.md).
export {
  fetchCached,
  probe,
  onNetEvent,
  NET_TIMEOUT_MS,
  type NetResult,
  type NetEvent,
  type FetchCachedOpts,
} from "./net";
export {
  enqueue,
  enqueueTripDonation,
  flush,
  wireAutoFlush,
  onQueueChange,
  queueSize,
  droppedTotal,
  MAX_QUEUE,
  type TripDonation,
  type FlushReport,
} from "./queue";
export { useNetStatus, type NetStatus, type NetState } from "./status";
