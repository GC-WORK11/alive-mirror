/** useShellFlow — the trip-flow state machine behind the shell:
 * search → pick → PLACE (settle: fly-to-pin + place sheet) → compare →
 * nav → receipt, plus the on-device ledger. Kept out of App.tsx so the
 * composition root stays declarative.
 *
 * /v2 migration: options come from POST /v2/plan (dose + emissions bands,
 * doc-06 §4 tags/reason_line computed server-side). Legacy /depart and
 * /directions remain — /v2/plan carries no turn steps yet. */
import { useCallback, useEffect, useRef, useState, type RefObject, type SetStateAction } from "react";
import { Dimensions, Keyboard, Platform, UIManager } from "react-native";
import type { CameraRef } from "@maplibre/maplibre-react-native";
import { requestPerms, scheduleDeparture, scheduleDailyBrief, cancelDeparture } from "../../notify";
import { loadTrips, logTrip, type Trip } from "../../store/ledger";
import type { CommunityTotals } from "../../community";
import {
  getVehicle, saveVehicle, clearVehicle, planVehicle, planVehicleProfile, type VehicleProfile,
} from "../../store/vehicle";
import { planEngineFirst, planOptions, type FieldStatus } from "../../api/plan";
import { fetchStrip } from "../../api/strip";
import { camDur } from "../../map/cam";
import { holdMapDrawThen, whenMapDrawFree } from "../../map/drawHold";
import { departCurveResult, departSavedPct, type DepartCurve } from "../../api/depart";
import type { RouteStrip } from "../../nav/strip";
import { flattenCoords, havM } from "../../nav/offroute";
import { t } from "../../i18n/strings";
import { API, DELHI, fetchJson, inNcr, posNow, posNowDetailed, type PosFix } from "./net";
import { pickTailGate } from "./pickGate";
import { localityAt } from "../../search/t0";
import { mark } from "../../perf";
import { isTransit, preserveIdx } from "./types";
import type { Depart, Place, Step, V2Option } from "./types";
import { tap } from "../../haptics";

/* Old-arch Android needs the flag once; Fabric (RN 0.86) animates layout
   natively and its setter is a no-op stub that still logs a dev warning —
   skip the call entirely when the Fabric UIManager is live. */
const setLayoutAnimExp = (UIManager as { setLayoutAnimationEnabledExperimental?: (b: boolean) => void })
  .setLayoutAnimationEnabledExperimental;
const isFabric = Boolean((global as { nativeFabricUIManager?: unknown }).nativeFabricUIManager);
if (Platform.OS === "android" && setLayoutAnimExp && !isFabric) setLayoutAnimExp(true);

/* Engine→full swap commits WITHOUT LayoutAnimation: configureNext is
   global-next-commit, so whatever layout change rides in the same commit
   (vehicle wizard's step swap, a strip tint landing, the keyboard) gets
   easeInEaseOut applied to views the sheet's Animated.Value is already
   driving — the native-detach SIGSEGV this stack keeps hitting. The
   sheet's own enter spring already covers the visual handoff; rows just
   appear in place. */

export type Phase = "idle" | "search" | "place" | "compare" | "nav" | "explore";
export type Which = "to" | "from";
/** honesty-cluster match metadata the search rows carry — shown on the
 *  place sheet as the substitute label, never implied to be exact. */
export type PlaceHint = {
  match?: "name" | "place" | "category" | "area";
  anchor?: string;
  compound?: boolean;
  /** gazetteer/server category of the shown row — a 'category' match
      labels the kind that stood in for the unnamed place */
  kind?: string;
};
/** a picked destination previewed before Directions commits to routing */
export type PlacePreview = { p: Place; meta: PlaceHint | null };
/* honest origin naming (hunter flagged the boot labelling stale
   last-known as GPS): a fresh GNSS read is "Your location"; a cached
   fix is real but is NEVER called that — it names the locality it sits
   in, or discloses its own age when no locality answers. */
export const fixName = (fix: PosFix, lang: "en" | "hi"): string => {
  if (fix.fresh) return t("yourLocation", lang);
  const loc = localityAt({ lat: fix.pos.coords.latitude, lon: fix.pos.coords.longitude });
  if (loc) return t("placeNearLocality", lang, { place: loc });
  return t("placeLastKnown", lang, { m: Math.max(1, Math.round(fix.ageS / 60)) });
};
/** network = we never got an answer (offline/timeout/http); server =
 *  /v2/plan answered with an `error` reason; outside = the typed
 *  both-ends-outside-NCR answer — different blame, the sheet labels
 *  each honestly instead of blaming the connection. */
export type PlanError = { kind: "network" | "server" | "outside"; detail?: string };

export function useShellFlow(camRef: RefObject<CameraRef | null>, shareEnabled: boolean, lang: "en" | "hi" = "en") {
  const [phase, setPhaseState] = useState<Phase>("idle");
  /* phaseRef mirrors the last phase anyone ASKED for, written before the
     deferred commit — on sim/emulator holdMapDrawThen delays setState, so
     a pick's async tail reading `phase` sees the surface that was up when
     its chain started, not where the flow actually went. Async tails gate
     every journey write on it (the pick-race bounce: a late locPickFailed
     tail reopening an empty Where-to after compare already mounted). */
  const phaseRef = useRef<Phase>("idle");
  /* every phase flip mounts or unmounts an overlay over the map — the
     setter commits inside a draw-hold so the map's pump is throttled
     before the sheet it precedes lands (mount-vs-draw SIGSEGV class;
     src/map/drawHold.ts). One wrap covers every caller. */
  const setPhase = useCallback((p: SetStateAction<Phase>) => {
    const next = typeof p === "function" ? p(phaseRef.current) : p;
    phaseRef.current = next;
    holdMapDrawThen(() => setPhaseState(next));
  }, []);
  /* the soft keyboard belongs to the search phase only — on Android the
     IME can outlive the pick's async dismiss and sit over the next
     sheet's bottom rows, eating back/skip taps until manually dismissed
     (testday-android finding #1; VehicleSheet's own edge-guard covers
     the wizard specifically, this covers every other overlay). */
  useEffect(() => {
    if (phase !== "search") Keyboard.dismiss();
  }, [phase]);
  const [from, setFrom] = useState<Place | null>(null);
  const [to, setTo] = useState<Place | null>(null);
  /* the settle phase's picked place — set by a 'to' pick, consumed by
     goDirections (which writes `to` when routing actually commits). */
  const [place, setPlace] = useState<PlacePreview | null>(null);
  /* true while goDirections waits on a real fix — the sheet's Directions
     button reads 'locating…' so the wait is never a dead tap */
  const [locating, setLocating] = useState(false);
  const [editWhich, setEditWhich] = useState<Which>("to");
  /* pick-race guards (demo-vid-android): a pick's confirm chain spans
     seconds of async work (dismiss ≤500 ms + posNow ≤9 s + deferred
     phase commits) while the sheet stays mounted and tappable. pickSeq
     = the latest selection's generation — a superseded pick's tail is
     dead and writes nothing. pickDone counts resolutions — the sheet
     unlatches its rows on it (its own commit latch holds the window
     between the tap and the flow settling). invalidatePicks kills any
     in-flight tail when the user deliberately re-opens a surface — a
     stale tail must never yank the journey forward over that choice. */
  const pickSeq = useRef(0);
  const [pickDone, setPickDone] = useState(0);
  const invalidatePicks = useCallback(() => { pickSeq.current += 1; }, []);
  const bumpPickDone = useCallback(() => setPickDone((n) => n + 1), []);
  /* honest one-line notice on the search sheet (e.g. a failed GPS fix).
     Set when a location attempt dies; cleared on close or a real pick. */
  const [locNotice, setLocNotice] = useState<string | null>(null);
  const [options, setOptionsState] = useState<V2Option[]>([]);
  const [selected, setSelectedState] = useState(0);
  /* The pick lives in refs written synchronously at the call site —
     mirroring them in an effect loses any tap that lands between the
     state commit and the effect run, and a /v2/plan payload can land in
     exactly that window (the nav-start-pick flag: the pick was reset to
     the recommended card, which Start then launched). */
  const pickRef = useRef<{ opts: V2Option[]; sel: number }>({ opts: [], sel: 0 });
  const setOptions = useCallback((opts: V2Option[]) => {
    pickRef.current = { ...pickRef.current, opts };
    setOptionsState(opts);
  }, []);
  const setSelected = useCallback((i: SetStateAction<number>) => {
    pickRef.current = {
      ...pickRef.current,
      sel: typeof i === "function" ? i(pickRef.current.sel) : i,
    };
    setSelectedState(i);
  }, []);
  const [depart, setDepart] = useState<Depart>(null);
  const [trips, setTrips] = useState<Trip[]>([]);
  const [community, setCommunity] = useState<CommunityTotals | null>(null);
  const [follow, setFollow] = useState(false);
  const [loadingRoute, setLoadingRoute] = useState(false);
  /** engine rows painted; the full option set is still landing */
  const [refining, setRefining] = useState(false);
  const [planError, setPlanError] = useState<PlanError | null>(null);
  /* planner arms the full plan lost to timeout/cancel/raise — surfaced
     so a sheet missing its engine rows reads as incomplete, not done */
  const [planDegraded, setPlanDegraded] = useState<string[]>([]);
  const [planNonce, setPlanNonce] = useState(0);
  const [planField, setPlanField] = useState<FieldStatus | null>(null);
  const [strips, setStrips] = useState<Record<string, RouteStrip>>({});
  const [departCurve, setDepartCurve] = useState<DepartCurve | null>(null);
  const [vehicle, setVehicle] = useState<VehicleProfile | null>(null);
  const [vehicleLoaded, setVehicleLoaded] = useState(false);
  const [notified, setNotified] = useState(false);
  /* the OS said no to notifications — the bell's honest answer instead
     of the dead tap it used to be (lifecycle-drive) */
  const [pingDenied, setPingDenied] = useState(false);
  /* the ping CAN'T be armed either — the best window sits deep inside
     quiet hours, so scheduleDeparture refuses (a ping hours after the
     window would be a lie). The row must say so, not dead-tap. */
  const [pingQuiet, setPingQuiet] = useState(false);
  const [steps, setSteps] = useState<Step[] | null>(null);
  const [stepsOpen, setStepsOpen] = useState(false);
  const [navDose] = useState(0); // kept: NavChrome's legacy prop path (engine's `nav` supersedes)

  // SEAM(trip-submit): anonymous traversal donation lives in the nav
  // engine (src/nav/engine.ts donate() → POST /v2/trip, outbox on
  // failure) and reads `shareEnabled` there. Kept referenced so the
  // prop stays meaningful for App.tsx.
  void shareEnabled;

  /* the S8 vehicle answer — loaded once, drives the /v2/plan `vehicle`
     param (which option is flagged `your_vehicle`). */
  useEffect(() => {
    getVehicle()
      .then((v) => { setVehicle(v); setVehicleLoaded(true); })
      .catch(() => setVehicleLoaded(true));
  }, []);

  /** Persist a new S8 answer; changing it re-plans (vehicle is a dep of
   *  the compare effect below). null = wiped (delete-my-data) — clear
   *  the store instead of resurrecting a file. */
  const planHoldMs = useRef(0);
  const setVehicleProfile = useCallback((p: VehicleProfile | null) => {
    if (p == null) {
      clearVehicle().catch(() => {});
      setVehicle(null);
      return;
    }
    saveVehicle(p).catch(() => {});
    // the picker sheet is animating out right now — hold the next plan
    // fetch well past its close animation so options+tint mount on a
    // settled screen (sim render-thread spike otherwise)
    planHoldMs.current = 1400;
    setVehicle(p);
  }, []);

  /* search itself lives in src/screens/SearchScreen (S2: T0 on-device +
     cancellable server tiers); this hook owns the phases around it. */
  const pick = useCallback(async (p: Place, which?: Which, meta?: PlaceHint | null) => {
    const seq = ++pickSeq.current;
    Keyboard.dismiss();
    /* the confirm path can stall for seconds (an unbounded GNSS fix used
       to hang here forever — walk F3's silent offline pick). While it
       runs the notice says the spot is being confirmed; every exit below
       overwrites it with the real outcome or clears it on success. The
       notice shows on the idle map (App) or inside the search sheet. */
    setLocNotice(t("mapPickChecking", lang));
    /* only "search" may be steered by a pick tail: once the flow has
       moved on, a late continuation writing setPhase("search") remounts
       the sheet EMPTY — the demo-vid-android bounce — and a "compare"
       write over a map-pick-armed idle would hijack a newer input.
       "compare" counts as in-flight too: the journey already advanced
       in this pick's own direction, so the advance write is a no-op. */
    try {
      if ((which ?? editWhich) === "from") {
        /* a start within a street of the destination has no route to
           compare (audit #19/#20's 50 m pins) — say so, stay in search */
        if (to) {
          const d = havM(p.lat, p.lon, to.lat, to.lon);
          if (d < 50) {
            setLocNotice(t("pickTooClose", lang, { n: Math.max(10, Math.round(d)) }));
            return;
          }
        }
        setFrom(p);
        setLocNotice(null);
        /* a pending place preview survives an origin pick — after the
           failed fix sent the user to type a 'from', landing here returns
           them to the settle sheet where Directions now has its start */
        setPhase(to ? "compare" : place ? "place" : "search");
        setEditWhich("to");
        return;
      }
      /* SETTLE before routing (the Google register the owner timed:
         tap → camera flies to the pin + a place sheet; Directions is
         what commits to a trip). The origin resolve + the too-close
         check live in goDirections — running them here priced a plan
         (and stalled on a GNSS fix) for a preview the user may never
         have wanted. This is also what kills the "minutes" open: the
         pick path is synchronous, no await. */
      setPlace({ p, meta: meta ?? null });
      setLocNotice(null);
      /* mapPickArmed/long-press picks fire from "idle" — a live tap
         there IS the pick (this path is synchronous: no await between
         the tap and this write, so no stale tail can interleave — the
         advance gate's idle exclusion guards async tails, not taps).
         Only "nav" is off-limits: never yank a live trip. */
      if (phaseRef.current !== "nav") setPhase("place");
    } finally {
      /* tell the sheet its commit window is over — a failed pick leaves
         it mounted and its rows must tap again; a superseded tail bumps
         nothing (the newer pick still owns the latch) */
      if (seq === pickSeq.current) setPickDone((n) => n + 1);
    }
  }, [editWhich, to, place, lang, setPhase]);

  /* the settle beat's single camera move: fly to the pin as the place
     sheet rises (Google: tap a row → the camera settles on it). The
     earlier no-pick-time-flyTo rule covered pick→plan, where the
     fitBounds in show() is the only move; the settle IS its own phase
     so this fly is alone in its window — still deferred a beat so the
     sheet-mount commit lands first (mount-vs-draw SIGSEGV class). */
  useEffect(() => {
    if (phase !== "place" || !place) return;
    const tm = setTimeout(() => {
      if (phaseRef.current !== "place") return;
      whenMapDrawFree(() => {
        camRef.current?.flyTo({ center: [place.p.lon, place.p.lat], zoom: 15, duration: camDur(700) });
      });
    }, 120);
    return () => clearTimeout(tm);
  }, [phase, place, camRef]);

  /** Directions — the commit: resolve a REAL origin (never fabricated,
   *  never a stale fix labelled as GPS), run the 50 m no-route check
   *  the pick path used to run, then hand from+to to the plan effect. */
  const goDirections = useCallback(async () => {
    const pv = place;
    if (!pv || phaseRef.current !== "place" || locating) return;
    const tailMayAdvance = () => pickTailGate(phaseRef.current, "advance");
    mark("dir.tap");
    const seq = pickSeq.current;
    setLocating(true);
    try {
      let origin = from;
      if (!origin) {
        const fix = await posNowDetailed();
        /* superseded or closed while the fix was in flight — write nothing */
        if (seq !== pickSeq.current || phaseRef.current !== "place") return;
        mark("loc.fix");
        if (!fix) {
          /* NEVER fabricate an origin — the old 'Central Delhi' fallback
             routed from a made-up point. The from slot arms on the search
             sheet with the failure said out loud; the preview survives
             so a typed 'from' returns straight to this sheet. */
          if (!pickTailGate(phaseRef.current, "stay")) { setLocNotice(null); return; }
          setLocNotice(t("locPickFailed", lang));
          setEditWhich("from");
          setPhase("search");
          return;
        }
        const c = fix.pos.coords;
        origin = { name: fixName(fix, lang), subtitle: "", lat: c.latitude, lon: c.longitude };
      }
      /* a destination within a street of the start has no route to
         compare (audit #19/#20's 50 m pins) — say so, stay on the sheet */
      const d = havM(origin.lat, origin.lon, pv.p.lat, pv.p.lon);
      if (d < 50) {
        setLocNotice(t("pickTooClose", lang, { n: Math.max(10, Math.round(d)) }));
        return;
      }
      setLocNotice(null);
      setFrom(origin);
      setTo(pv.p);
      setPlace(null);
      if (tailMayAdvance()) setPhase("compare");
    } finally {
      setLocating(false);
    }
  }, [place, from, locating, lang, setPhase]);

  /** settle-sheet close — back to wherever the journey was. A pending
      directions() fix tail is killed by invalidating pick seqs. */
  const closePlace = useCallback(() => {
    invalidatePicks();
    setPlace(null);
    setLocNotice(null);
    setPhase(to ? "compare" : "idle");
  }, [to, setPhase, invalidatePicks]);

  /* ---- routes: destination+origin set → /v2/plan + legacy /depart ---- */
  useEffect(() => {
    if (phase !== "compare" || !from || !to || !vehicleLoaded) return;
    let cancelled = false;
    (async () => {
      setNotified(false);
      setSteps(null); setStepsOpen(false);
      setLoadingRoute(true);
      setPlanError(null);
      setPlanDegraded([]);
      try {
        if (planHoldMs.current > 0) {
          const hold = planHoldMs.current;
          planHoldMs.current = 0;
          await new Promise((r) => setTimeout(r, hold));
          if (cancelled) return;
        }
        const req = {
          from: { lat: from.lat, lon: from.lon },
          to: { lat: to.lat, lon: to.lon },
          vehicle: planVehicle(vehicle),
          vehicle_profile: planVehicleProfile(vehicle),
        };
        let painted = false;      // engine-first rows already on screen
        let paintedEngine: V2Option[] = [];   // kept if the full plan's engine arm dies
        let fullDone = false;
        const show = (opts: V2Option[], field: FieldStatus | null | undefined) => {
          /* keep the user's pick across the swap — by option identity,
             never route_id (the server mints a fresh UUID per /v2/plan
             response, so id-matching reset every pick to the recommended
             card the moment the full plan landed). preserveIdx falls
             back to 0 = ranked first = the recommended default. */
          const j = preserveIdx(pickRef.current.opts[pickRef.current.sel], opts);
          setOptions(opts); setSelected(j);
          setPlanField(field ?? null);
          // per-route PM2.5 strips → the gradient tint resolves from flat
          // dose-mean into real along-route colour as each lands (cached
          // 15 min, failures leave the flat tint — never faked)
          for (const o of opts) {
            if (!o.route_id) continue;
            fetchStrip(o.route_id).then((st) => {
              if (!cancelled) setStrips((m) => (m[o.route_id!] ? m : { ...m, [o.route_id!]: st }));
            }).catch(() => {});
          }
          /* camera fits ALL drawable candidates, not just opts[0] — the
             chooser stages them as equals and the frame must hold every
             contender before the settle. Re-runs per show() since the
             full plan's union can grow past the engine-first rows. */
          {
            let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
            for (const o of opts) {
              for (const [x, y] of flattenCoords(o.geometry)) {
                if (x < x0) x0 = x; if (y < y0) y0 = y;
                if (x > x1) x1 = x; if (y > y1) y1 = y;
              }
            }
            if (x0 <= x1 && y0 <= y1) {
              const bounds: [number, number, number, number] = [x0, y0, x1, y1];
              // let the compare sheet's enter spring finish before the
              // camera move — a camera anim inside a sheet-mount frame
              // is the same render-thread spike class
              /* the compare sheet anchors bottom at detent "half" —
                 reserve its real footprint so every staged candidate +
                 endpoint ring draws in the visible band; the old fixed
                 340 under-reserved ~100 pt and the chooser's lower half
                 drew under the sheet (ios-vid nit). */
              const bottom = Math.round(Dimensions.get("window").height * 0.5) + 24;
              setTimeout(() => {
                if (!cancelled) whenMapDrawFree(() => {
                  if (!cancelled) camRef.current?.fitBounds(bounds, { padding: { top: 200, bottom, left: 50, right: 50 }, duration: camDur(700) });
                });
              }, 500);
            }
          }
        };
        setStrips({});
        setRefining(false);
        // least-smoke engine rows paint in ~engine time; the full set
        // (public router + transit + engine) replaces them when it lands
        planEngineFirst(req).then((fj) => {
          if (cancelled || fullDone || fj.options.length === 0) return;
          painted = true;
          paintedEngine = fj.options.filter((o) => o.engine != null);
          show(fj.options, fj.field);
          setLoadingRoute(false);
          setRefining(true);
        }).catch(() => {});
        let pj;
        try {
          pj = await planOptions(req, 30000);   // far-route plans krige per query — measured >25 s on CP→Pataudi
        } catch (e) {
          fullDone = true;
          if (painted) { if (!cancelled) setRefining(false); return; }  // engine rows stand
          throw e;
        }
        // (no swap LayoutAnimation — see the comment at the top of this file)
        fullDone = true;
        if (cancelled) return;
        setRefining(false);
        /* engine rows already on screen → the full set lands in place.
           The haptic says "your options are ready". */
        if (painted) tap();
        if (pj.error && pj.options.length === 0) {
          if (painted) return;   // keep the real engine rows over an empty full set
          setOptions([]); setDepart(null);
          // typed outside-coverage answer → its own notice (retry can't
          // fix a geography problem; the sheet offers 'change the trip')
          const outside = pj.code === "outside_service_area"
            || /outside service area/i.test(pj.error);
          setPlanError({ kind: outside ? "outside" : "server", detail: pj.error });
          return;
        }
        /* a degraded engine arm would silently drop the least-inhalation
           rows — the feature that is the product. The engine-first paint
           already holds real engine rows: keep them in front of whatever
           survived, and flag the gap on the sheet rather than pretend
           the option set is complete. */
        const opts = (paintedEngine.length && pj.degraded?.includes("engine"))
          ? [...paintedEngine, ...pj.options]
          : pj.options;
        setPlanDegraded(pj.degraded ?? []);
        show(opts, pj.field);
      } catch {
        if (!cancelled) {
          setOptions([]); setDepart(null);
          setPlanError({ kind: "network" });   // honest retry state — no silent /decide fallback
        }
      } finally { if (!cancelled) setLoadingRoute(false); }
    })();
    return () => { cancelled = true; setRefining(false); };
  }, [phase, from, to, vehicle, vehicleLoaded, planNonce, camRef, setOptions, setSelected]);

  /** Error retry — re-runs the compare effect. */
  const retryPlan = useCallback(() => setPlanNonce((n) => n + 1), []);

  /* ---- leave-time window follows the SELECTED mode (was hardcoded
     vehicle=auto — claims audit: the window must model the chosen ride).
     Full 24h curve via departCurveResult (fetchCached → last-good +
     stale label free); `depart` stays the legacy best-slot shape. ---- */
  useEffect(() => {
    const mode = options[selected]?.mode;
    if (phase !== "compare" || !from || !to || !mode) return;
    let cancelled = false;
    departCurveResult(
      { from: { lat: from.lat, lon: from.lon }, to: { lat: to.lat, lon: to.lon }, vehicle: mode })
      .then((r) => {
        if (cancelled) return;
        const c = r.ok ? r.data : null;
        setDepartCurve(c?.slots?.length ? c : null);
        setDepart(c?.best
          ? { best: { hours_ahead: c.best.hour, start: c.best.start, dose_ug: c.best.dose_mid },
              ug_saved_vs_now: c.ug_saved_vs_now,
              pct_less_vs_now: c.pct_less_vs_now }
          : null);
      })
      .catch(() => { if (!cancelled) { setDepartCurve(null); setDepart(null); } });
    return () => { cancelled = true; };
  }, [phase, from, to, options, selected]);

  /* ---- turn-by-turn steps for the selected (road) option ----
     /v2/plan options carry no steps yet → legacy /directions stays. */
  useEffect(() => {
    const o = options[selected];
    let cancelled = false;
    // deferred one tick — setState directly inside an effect cascades renders
    Promise.resolve().then(() => { if (!cancelled) setSteps(null); });
    // transit rows carry stations → board→alight line; the station-less
    // "bus" option gets road-steps that read like car maneuvers — both are
    // dishonest, so neither fetches /directions here
    if (!o || !from || !to || isTransit(o) || o.mode === "bus") return () => { cancelled = true; };
    if (Array.isArray(o.steps) && o.steps.length) {   // inlined steps win when they exist
      const inline = o.steps;
      Promise.resolve().then(() => { if (!cancelled) setSteps(inline); });
      return () => { cancelled = true; };
    }
    const profile = o.mode === "cycle" ? "cycling" : o.mode === "walk" ? "walking" : "driving";
    fetchJson(
      `${API}/directions?from_lat=${from.lat}&from_lon=${from.lon}` +
        `&to_lat=${to.lat}&to_lon=${to.lon}&profile=${profile}&vehicle=${o.mode}`, 10000)
      .then((j) => { if (!cancelled && Array.isArray(j.steps)) setSteps(j.steps); })
      .catch(() => {});
    return () => { cancelled = true; };
  }, [selected, options, from, to]);

  const clearRoute = useCallback(() => {
    setPlace(null);
    setTo(null); setOptions([]); setDepart(null); setDepartCurve(null);
    setSteps(null); setStepsOpen(false); setStrips({});
    setPlanError(null); setPlanField(null); setPlanDegraded([]);
    setPhase("idle"); setFollow(false);
  }, [setOptions, setPhase]);

  /* ---- navigation phase transitions; the live engine (src/nav) owns
     the watcher, strip, counters, off-route + arrival — nothing here
     ticks or polls during nav anymore. ---- */
  const startNav = useCallback(async () => {
    const o = options[selected];
    if (!o || !from || !to) return;
    setPhase("nav");
    Keyboard.dismiss();
    const pos = await posNow();
    setFollow(!!(pos && inNcr(pos.coords.latitude, pos.coords.longitude)));
    /* the sheet-unmount and the camera commits must not land in the same
       frame — back-to-back render commits are the residual-SIGSEGV trigger
       class on the virtualized-GPU iOS sim (ci15 telemetry). Defer the
       camera work a beat so the close commit lands alone. */
    setTimeout(() => {
      whenMapDrawFree(() => {
        camRef.current?.flyTo({ center: [from.lon, from.lat], zoom: 15.5, duration: camDur(700) });
        camRef.current?.setStop({ pitch: 55, duration: camDur(800) });
      });
    }, 80);
  }, [options, selected, from, to, camRef, setPhase]);

  const exitNav = useCallback(() => {
    /* arrival-Done (and the nav X) means the trip is OVER — going back to
       "compare" re-opened the options sheet on the just-traveled OD
       (android-drive: every trip ended in a phantom re-plan, often the
       degenerate dest→dest pair once `from` had drifted to the arrival
       fix). "idle" lands on home with the completed trace still on the
       map; nothing re-plans until the user asks. */
    setPhase("idle");
    /* an ended trip leaves no live route context: the OD pair is stale
       the moment the engine stops — yet `to`/`from` used to linger, so
       the next "Where to?" reopened on the finished destination AND
       closing the sheet silently re-entered compare on it
       (offline-verify catalogue #2). Fresh slate: the trip was already
       logged by the engine before Done. */
    setFrom(null); setTo(null); setPlace(null);
    setOptions([]); setSelected(0); setDepart(null); setDepartCurve(null);
    setSteps(null); setStepsOpen(false); setStrips({});
    setPlanError(null); setPlanField(null); setPlanDegraded([]);
    /* the flip frame already carries receipt-unmount + chrome remount —
       every map-side commit rides staggered later, ~one per frame-budget,
       so nothing piles inside the teardown window (ci15: the last
       residual-SIGSEGV hot spot, 3× at Done). */
    setTimeout(() => setFollow(false), 300);
    setTimeout(() => whenMapDrawFree(() =>
      camRef.current?.setStop({ pitch: 0, duration: camDur(700) })), 400);
  }, [camRef, setPhase, setOptions, setSelected]);

  /* ---- ledger: only a COMPLETED trip is logged (claims audit — logging
     on option view fabricated trips + inflated every avoided-µg total).
     The nav session calls this with its real arrival summary. ---- */
  const recordTrip = useCallback(async (t: {
    label: string; vehicle: string; doseUg: number | null; avoidedUg: number | null;
    emitKg?: number | null; doseLoUg?: number | null; doseHiUg?: number | null;
  }) => {
    if (!from || !to) return;
    try {
      setTrips(await logTrip({
        ts: Date.now(), label: t.label, vehicle: t.vehicle,
        dose_ug: Math.round((t.doseUg ?? 0) * 10) / 10,
        avoided_ug: Math.max(0, Math.round((t.avoidedUg ?? 0) * 10) / 10),
        /* emit_kg powers the drawer's "put out kg" twin tile + ledger sums;
           null on modes with no emissions model — readers treat it as
           optional, never fabricate 0. */
        emit_kg: t.emitKg == null ? undefined : Math.max(0, Math.round(t.emitKg * 10) / 10),
        /* dose band readers (ledger "likely between") — only written when
           the nav summary really carried the σ band; never fabricated. */
        dose_lo_ug: t.doseLoUg == null ? undefined : Math.max(0, Math.round(t.doseLoUg * 10) / 10),
        dose_hi_ug: t.doseHiUg == null ? undefined : Math.max(0, Math.round(t.doseHiUg * 10) / 10),
        from: from.name, to: to.name,
        fromLat: from.lat, fromLon: from.lon, toLat: to.lat, toLon: to.lon,
      }));
    } catch { /* ledger write is best-effort */ }
  }, [from, to]);

  /* route polylines tinted per ~250 m by field PM2.5 — the derivation
     moved inside <RouteTintSource/> (App.tsx); we just hand the strips
     through so each option's flat dose-mean tint resolves into the real
     along-route gradient as its strip lands. */

  const armDailyBrief = useCallback(async (): Promise<boolean> => {
    if (!(await requestPerms())) return false;
    const p = to ?? from ?? { lat: DELHI[1], lon: DELHI[0] };
    const j = await fetchJson(`${API}/today?lat=${p.lat}&lon=${p.lon}`).catch(() => null);
    const h: number[] | undefined = j?.hours_ist;
    if (!Array.isArray(h) || h.length < 24) return false;
    let best = 0;
    for (let i = 0; i <= 21; i++) if (h[i] + h[i + 1] + h[i + 2] < h[best] + h[best + 1] + h[best + 2]) best = i;
    const drop = Math.max(0, Math.round((1 - ((h[best] + h[best + 1] + h[best + 2]) / 3) / (h.reduce((a, b) => a + b, 0) / 24)) * 100));
    return (await scheduleDailyBrief({ startHour: best, endHour: (best + 3) % 24, dropPct: drop })) != null;
  }, [from, to]);

  /* Air alerts (store/events.ts): arming is just the OS permission —
     the engine needs no scheduling; pings fire live off the ambient poll
     whenever a real field crosses its rule. Returns whether the OS lets
     notifications through so the toggle only stays on when pings can
     actually reach the shade. */
  const armAirEvents = useCallback(async (): Promise<boolean> => {
    return await requestPerms();
  }, []);

  const remind = useCallback(async () => {
    if (!depart?.best?.start || notified) return;
    if (!(await requestPerms())) { setPingDenied(true); return; }
    const fire = new Date(depart.best.start.endsWith("Z") ? depart.best.start : depart.best.start + "Z");
    /* /depart serves the saving as a PERCENT already — pct_less_vs_now is
       the honest name (ug_saved_vs_now is the legacy alias for the same
       percent, not µg). Reading it as µg and recomputing a percent off it
       overstated the claim ~2.5× in the scheduled copy (13% true read
       32%). Take the served percent verbatim (depart.test.ts pins this). */
    const pct = Math.max(0, Math.round(departSavedPct(depart) ?? 0));
    if (await scheduleDeparture({ fireAt: fire, savedPct: pct })) setNotified(true);
    else setPingQuiet(true);
  }, [depart, notified]);

  /* the master switch (settings.remind) off — the OS ping must die AND
     the armed indicator reset, or a later re-on would claim a cancelled
     ping is still coming */
  const disarmDepart = useCallback(() => {
    void cancelDeparture();
    setNotified(false);
  }, []);

  const reloadTrips = useCallback(() => { loadTrips().then(setTrips).catch(() => {}); }, []);

  /* doc 02 §S5: the vehicle question belongs on first private-mode pick —
     the integrator opens <VehicleSheet/> when this flips true. */
  const sel = options[selected];
  const needsVehicle =
    vehicleLoaded && vehicle == null &&
    (sel?.mode === "car" || sel?.mode === "car_open" || sel?.mode === "bike");

  return {
    phase, setPhase, from, setFrom, to, setTo,
    editWhich, setEditWhich, options, selected, setSelected,
    depart, notified, pingDenied, pingQuiet, trips, setTrips, recordTrip, community, setCommunity, follow, setFollow,
    loadingRoute, refining, planError, planDegraded, retryPlan, planField, departCurve,
    vehicle, setVehicleProfile, needsVehicle,
    steps, stepsOpen, setStepsOpen, navDose,
    pick, clearRoute, startNav, exitNav, remind, disarmDepart, armDailyBrief, armAirEvents,
    strips, reloadTrips, locNotice, setLocNotice,
    place, locating, goDirections, closePlace,
    phaseRef, pickDone, invalidatePicks, bumpPickDone,
  };
}
