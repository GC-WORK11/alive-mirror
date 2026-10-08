/**
 * src/nav — Phase-4 live navigation engine + arrival receipt (ALive-108).
 *
 * EXPORT CONTRACT (integrator notes)
 * ----------------------------------
 *   const nav = useNavEngine({
 *     route: {
 *       route_id,                       // from /v2/plan (required)
 *       geometry | route_geojson,       // GeoJSON LineString|MultiLineString
 *       eta_s, mode, distance_km,       // plan fields (mode drives ME/VE)
 *       to: {lat, lon},                 // optional; default = last route pt
 *       steps,                          // optional → banner + speech cues
 *       alternatives, worstDoseUg,      // optional → receipt comparisons
 *     },
 *     camRef,                           // MapLibre CameraRef — follow cam
 *     lang,                             // "en" | "hi" — cues + speech tag
 *     onArrive: (s: NavSummary) => {},  // receipt data + donation status
 *     shareEnabled,                     // POST /v2/trip on arrival iff true
 *     speech,                           // voice cues — default OFF
 *     apiBase, autoStart,               // defaults: shell net.ts API, false
 *   });
 *
 *   nav = {
 *     running, start(), stop(), arrive(),   // arrive() = "End" button path
 *     dose, co2, pm25,          // {lo,mid,hi} — µg / kg / g, never collapse
 *     progress,                 // 0..1 along-route
 *     distRemainingM, etaS,
 *     offRoute,                 // true while a reroute request is in flight
 *     arrived, snapped,         // snapped = [lon,lat] puck position
 *     nextStep,                 // {instruction, distM} or null
 *     stripOk,                  // false when /v2/strip failed (no fake data)
 *     stripAge,                 // {ageMin, at} — strip's serve-time field
 *                               // age + fetch stamp; receipt derives the
 *                               // printed age at render so it counts the
 *                               // trip's own elapsed
 *     summary,                  // NavSummary post-arrival
 *   };
 *
 * The engine owns its location watcher (1 s / 5 m, BestForNavigation) and
 * a 1 Hz ticker; all counter math is local — no per-second network.
 * Components: NavChrome renders `nav`; ReceiptSheet renders `nav.summary`
 * plus the comparison context from the chosen NavRoute.
 */
export { useNavEngine } from "./engine";
export type { NavEngine, NavEngineOpts, NavRoute, NavSummary, NextStep } from "./engine";
export { LiveCounters, ME_VE, COLD_UPLIFT, REST_VE_LPM } from "./counters";
export {
  ArrivalTracker, flattenCoords, havM, OffRouteTracker, polylineLengthM,
  snapToPolyline, ARRIVE_FIXES, ARRIVE_M, OFF_ROUTE_FIXES, OFF_ROUTE_M,
} from "./offroute";
export { fieldAtAlongM, stripCumM } from "./strip";
export type { Band, EmissionCurve, RouteStrip, StripSample } from "./strip";
export { CueTracker, speakCue, stopCues } from "./speech";
export type { NavStep } from "./speech";
