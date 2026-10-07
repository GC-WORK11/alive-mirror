import React, { useCallback, useDeferredValue, useEffect, useMemo, useRef, useState } from "react";
import { BackHandler, LogBox, Pressable, Share, StyleSheet, Text, View } from "react-native";
import { StatusBar } from "expo-status-bar";
import * as SplashScreen from "expo-splash-screen";
import { useFonts, Inter_400Regular, Inter_500Medium, Inter_600SemiBold } from "@expo-google-fonts/inter";
import {
  Fraunces_400Regular, Fraunces_400Regular_Italic, Fraunces_500Medium, Fraunces_600SemiBold,
} from "@expo-google-fonts/fraunces";
import {
  IBMPlexMono_400Regular, IBMPlexMono_500Medium, IBMPlexMono_600SemiBold,
} from "@expo-google-fonts/ibm-plex-mono";
import {
  NotoSansDevanagari_400Regular, NotoSansDevanagari_500Medium, NotoSansDevanagari_600SemiBold,
} from "@expo-google-fonts/noto-sans-devanagari";
import * as Location from "expo-location";
import {
  Camera, Map, Marker, UserLocation, type CameraRef,
} from "@maplibre/maplibre-react-native";
import { SafeAreaProvider, useSafeAreaInsets } from "react-native-safe-area-context";
import { V2Elev, V2Radius, V2T, V2Type, cigOf, fam } from "./src/theme";
import { DYNAMIC_TYPE } from "./src/a11y";
import { EndpointPin } from "./src/ui";
import { Icon } from "./src/icons";
import type { Place, Step, V2Option } from "./src/components/shell/types";
import { latinLabels, v2StyleUrl } from "./src/map/style";
import { camDur } from "./src/map/cam";
import { holdMapDraw, useHeldState, useMapDrawHeld } from "./src/map/drawHold";
import { ReportsLayer, reconcileReportSlots, REPORT_POOL, type ReportSlot } from "./src/components/ReportsLayer";
import { FreshnessChip } from "./src/components/FreshnessChip";
import { RouteTintSource } from "./src/components/RouteTint";
import { fieldSources, type FieldStatus } from "./src/api/plan";
import { FiresLayer, BlackspotsLayer } from "./src/components/HazardLayers";
import { CorridorLayer } from "./src/components/CorridorLayer";
import { SearchBar } from "./src/components/shell/SearchBar";
import { SearchScreen, type SearchSelection } from "./src/screens/SearchScreen";
import { VehicleSheet } from "./src/screens/VehicleSheet";
import { DelhiToday } from "./src/screens/DelhiToday";
import { SettingsScreen } from "./src/screens/SettingsScreen";
import { LedgerScreen } from "./src/screens/LedgerScreen";
import { OnboardingScreen, type SharingChoice } from "./src/screens/OnboardingScreen";
import { WelcomeScreen } from "./src/screens/WelcomeScreen";
import { loadWelcomeSeen, markWelcomeSeen } from "./src/store/welcome";
import { HomeScreen, DayPeek, useDayData } from "./src/screens/HomeScreen";
import { recordSample, setCheckin } from "./src/store/daylog";
import { loadConsent, saveConsent } from "./src/store/consent";
import { contributorId } from "./src/community";
import { CompareSheet } from "./src/components/shell/CompareSheet";
import { NavChrome } from "./src/components/shell/NavChrome";
import { ReceiptSheet, type ReceiptData } from "./src/components/shell/ReceiptSheet";
import { useNavEngine, type NavSummary, type NavStep } from "./src/nav";
import { useNetStatus } from "./src/offline";
import { LocateButton } from "./src/components/shell/LocateButton";
import { LayersButton } from "./src/components/shell/LayersButton";
import { LayersSheet, type LayerKey } from "./src/components/shell/LayersSheet";
import { Sidebar } from "./src/components/shell/Sidebar";
import { useShellFlow } from "./src/components/shell/useShellFlow";
import { API, DELHI, fetchJson, inNcr, reverseName } from "./src/components/shell/net";
import {
  DEFAULT_SETTINGS, PROFILE_BUDGET_UG, clearAllData, loadSettings, saveSettings, type SavedPlace, type ShellSettings,
} from "./src/components/shell/settings";
import { loadTrips, type Trip } from "./src/store/ledger";
import { checkAirEvents, resetEventsStore } from "./src/store/events";
import { getVehicle, type VehicleClass, type VehicleProfile } from "./src/store/vehicle";
import { approx, modeLabel, placeNameLabel, t, type Lang } from "./src/i18n/strings";
import { tap, tick } from "./src/haptics";
import { PERF_ON, bump, mark, report } from "./src/perf";

mark("app.eval");
SplashScreen.preventAutoHideAsync().catch(() => {});

// Bundled light style — resolves local delhi.pmtiles / EXPO_PUBLIC_TILES_URL,
// else hosted OpenFreeMap vector tiles through the same light style object.
const STYLE_URL = v2StyleUrl();
const STYLE_EN = latinLabels(STYLE_URL);

// liberty ships a few vector tiles MLRN can't parse — a native dev-only
// console warning; nothing in our layers is involved
LogBox.ignoreLogs(["Invalid geometry in line layer"]);

// The S8 profile (vehicle.json) and the drawer's coarse class
// (settings.vehicle) are two surfaces of one answer — kept in sync in
// App so "My vehicle" can never read "not set" after the sheet saved.
const CLS2DRAWER: Record<VehicleClass, string> = {
  car: "car", auto: "auto", bike: "bike",
  bus: "transit", metro: "transit", walk: "walk", cycle: "walk",
};
const DRAWER2CLS: Record<string, VehicleClass> = {
  bike: "bike", car: "car", auto: "auto",
  cab: "car", transit: "bus", walk: "walk",
};

/* hoisted so the memo'd map tree sees stable prop identity — fresh array/
   object literals each render used to defeat the memo boundary anyway */
const INIT_VIEW = { center: DELHI, zoom: 11 } as const;
/* maxBounds = the dose field's service margin (NCR ±2°), not the
   tight NCR box — a destination in Agra/Jaipur must stay on
   screen or the outside-area notice can't be understood */
const MAX_BOUNDS: [number, number, number, number] = [74.75, 26.15, 79.95, 30.98];
/* event payload types derived from the components' own prop signatures —
   never hand-name maplibre event types */
type MapPressEvent = Parameters<NonNullable<React.ComponentProps<typeof Map>["onPress"]>>[0];
type TrackChangeEvent = Parameters<NonNullable<React.ComponentProps<typeof Camera>["onTrackUserLocationChange"]>>[0];

/* The whole native map subtree behind one memo boundary: every app-level
   poll (reports 60 s, aqi 60 s, health 15 s, ambient samples) used to
   re-diff the Map + Camera + layers + markers per render. All props are
   stable identities, so unrelated app state no longer touches it. */
const MapTree = React.memo(function MapTree({
  lang, compassPosition, logoPosition, attributionPosition,
  onPress, onLongPress, camRef, drawHeld,
  trackUserLocation, onTrackUserLocationChange,
  hasLoc, corridors, reportSlots, fires, spots, layers,
  options, selected, strips,
  fromPin, toPin, fromSet, toSet, pinReady,
}: {
  lang: Lang;
  compassPosition: { top: number; right: number };
  logoPosition: { bottom: number; left: number };
  attributionPosition: { bottom: number; right: number };
  onPress: (e: MapPressEvent) => void;
  onLongPress: (e: MapPressEvent) => void;
  camRef: React.RefObject<CameraRef | null>;
  trackUserLocation: "default" | undefined;
  onTrackUserLocationChange: (e: TrackChangeEvent) => void;
  hasLoc: boolean;
  corridors: React.ComponentProps<typeof CorridorLayer>["corridors"];
  reportSlots: (ReportSlot | null)[];
  fires: GeoJSON.FeatureCollection | null;
  spots: GeoJSON.FeatureCollection | null;
  layers: Record<LayerKey, boolean>;
  options: V2Option[];
  selected: number;
  strips: Parameters<typeof RouteTintSource>[0]["strips"];
  fromPin: [number, number];
  toPin: [number, number];
  fromSet: boolean;
  toSet: boolean;
  pinReady: boolean;
  drawHeld: boolean;
}) {
  bump("app.MapTree");
  return (
    <Map mapStyle={lang === "hi" ? STYLE_URL : STYLE_EN} style={StyleSheet.absoluteFill}
      /* mount-vs-draw hold (src/map/drawHold.ts): while an overlay
         mounts/unmounts over the map the render pump drops to 2 fps so
         the commit can't intersect a wall of in-flight draws — the
         sim-only SIGSEGV class; -1 restores the MapLibre default on
         hardware and outside every window. */
      preferredFramesPerSecond={drawHeld ? 2 : -1}
      /* PERF-gated milestones in the cold-open path: style load is the
         bundled-light parse, rendered-full is first frame incl. tiles
         (hosted OpenFreeMap = network; bundled pmtiles = local) */
      {...(PERF_ON ? {
        onDidFinishLoadingStyle: () => mark("map.style"),
        onDidFinishRenderingMapFully: () => mark("map.rendered"),
      } : {})}
      /* the compass clears the chrome: search bar at rest, the taller
         maneuver banner in nav (was clipped behind it at top-right) */
      compassPosition={compassPosition}
      /* ornaments ride above the FABs — the stock bottom-edge spots
         clip against the home-indicator bezel + the FAB shadows */
      logoPosition={logoPosition}
      attributionPosition={attributionPosition}
      onPress={onPress}
      onLongPress={onLongPress}>
      <Camera ref={camRef} initialViewState={INIT_VIEW} maxBounds={MAX_BOUNDS}
        trackUserLocation={trackUserLocation}
        onTrackUserLocationChange={onTrackUserLocationChange} />
      {/* mounted once we have a fix and left mounted — unmounting the
          location puck pulls its native layer mid-draw (same upstream
          sim crash class as route sources/markers). The small idle-GPS
          cost beats a remove-during-render race; always-on dot matches
          normal map UX anyway. */}
      {hasLoc && <UserLocation animated accuracy />}
      {/* all map children stay mounted for the app's life — a mid-draw
          removeSource/removeAnnotation is the upstream sim SIGSEGV;
          the toggles only swap data in and out (see each component) */}
      <CorridorLayer corridors={corridors} on={layers.corridors} />
      <ReportsLayer slots={reportSlots} />
      <FiresLayer fires={fires} on={layers.fires} />
      <BlackspotsLayer spots={spots} on={layers.spots} />
      {/* route-wise AQI gradient on the real /v2/plan polylines — per
          ~250 m chunk from the fetched strips, flat dose-mean until they
          land; selected 6 px on 9 px casing, alternates 3 px at 50 %.
          (<RouteTintSource/> — src/components/RouteTint.tsx contract) */}
      <RouteTintSource options={options} selected={selected} strips={strips} />
      {/* endpoint annotations stay mounted at their last coordinates —
          unmounting a MarkerView mid-draw is the same upstream
          remove-during-render class as the route sources. Hidden is an
          empty child; the pin never teleports because the ref holds the
          last real coordinate. */}
      <Marker lngLat={fromPin} anchor="center">
        {fromSet && pinReady ? <EndpointPin kind="origin" /> : <View />}
      </Marker>
      <Marker lngLat={toPin} anchor="bottom">
        {toSet && pinReady ? <EndpointPin kind="dest" /> : <View />}
      </Marker>
    </Map>
  );
});

export default function App() {
  return (
    <SafeAreaProvider>
      <AppInner />
    </SafeAreaProvider>
  );
}

function AppInner() {
  bump("app.AppInner");
  const camRef = useRef<CameraRef>(null);
  /* last real endpoint coords — the always-mounted markers park here when
     hidden (see the Marker block below). State not a ref: lint bans
     refs-in-render, and the marker needs the value at render anyway. */
  const [fromPin, setFromPin] = useState<[number, number]>(DELHI);
  const [toPin, setToPin] = useState<[number, number]>(DELHI);
  const insets = useSafeAreaInsets();
  const [settings, setSettings] = useState<ShellSettings>(DEFAULT_SETTINGS);
  const flow = useShellFlow(camRef, settings.share, settings.lang);
  /* flow's return object is a fresh identity every render — using it as a
     hook dep or prop recreates every downstream callback and defeats memo
     on the screens below. All members are stable (useState setters +
     useCallbacks), so destructure once and depend on them directly. */
  const {
    phase, setPhase, from, setFrom, to, setTo, editWhich, setEditWhich,
    options, selected, setSelected, depart, notified, trips, setTrips, recordTrip,
    community, setCommunity, follow, setFollow, loadingRoute, refining,
    planError, planDegraded, retryPlan, planField, departCurve,
    vehicle, setVehicleProfile, needsVehicle, steps, stepsOpen, setStepsOpen,
    pick, clearRoute, startNav, exitNav, remind, armDailyBrief, armAirEvents,
    strips, reloadTrips,
  } = flow;
  useEffect(() => {
    if (!from) return;
    const c: [number, number] = [from.lon, from.lat];
    const t = setTimeout(() => setFromPin(c), 0);
    return () => clearTimeout(t);
  }, [from]);
  useEffect(() => {
    if (!to) return;
    const c: [number, number] = [to.lon, to.lat];
    const t = setTimeout(() => setToPin(c), 0);
    return () => clearTimeout(t);
  }, [to]);
  // route-tint shape sources mount at lower priority — keeps the compare
  // sheet's entrance animation from sharing a frame with the chunk build
  const deferredOptions = useDeferredValue(options);
  const lang = settings.lang;

  /* Endpoint-pin child swaps are map-side commits — they must land clear
     of every phase flip. pinReady lags "compare" by 450 ms BOTH ways so
     a pin never appears/disappears inside a sheet mount/unmount frame
     (receipt-Done teardown = residual-SIGSEGV hot spot, 3× on ci15). */
  const [pinReady, setPinReady] = useState(false);
  useEffect(() => {
    const t = setTimeout(() => setPinReady(phase === "compare"), 450);
    return () => clearTimeout(t);
  }, [phase]);

  /* the draw-hold windows: phase flips and overlay flags are held at
     their setters (useHeldState / the wrapped setPhase), this net
     catches what setters can't see — option rows / the error state
     landing on fetch completion mid-sheet. The prop feeds MapTree's
     preferredFramesPerSecond. */
  const drawHeld = useMapDrawHeld();
  const optionsCount = options.length;
  useEffect(() => { holdMapDraw(); }, [phase, optionsCount]);

  const [reportSlots, setReportSlots] = useState<(ReportSlot | null)[]>(
    () => Array<ReportSlot | null>(REPORT_POOL).fill(null));
  const [fires, setFires] = useState<GeoJSON.FeatureCollection | null>(null);
  const [spots, setSpots] = useState<GeoJSON.FeatureCollection | null>(null);
  const [layers, setLayers] = useState<Record<LayerKey, boolean>>({ fires: false, spots: false, corridors: false });
  /* overlay mount/unmount flags — every setter commits inside a
     draw-hold so the map's pump is throttled before the sheet it
     precedes lands (drawHold.ts; plain useState for data, useHeldState
     for anything that mounts a view over the map) */
  const [sidebarOpen, setSidebarOpen] = useHeldState(false);
  const [layersOpen, setLayersOpen] = useHeldState(false);
  const [mapPickArmed, setMapPickArmed] = useHeldState(false);
  const [vehicleOpen, setVehicleOpen] = useHeldState(false);
  /* needsVehicle flips inside the same commit as the first option rows —
     mounting the wizard there makes its enter-spring share a frame with
     RouteTint + the camera fit (the sim's documented render-thread
     SIGSEGV window). Arm it once the one camera move per plan has run
     out (options+500 ms start + 700 ms anim + margin). */
  const [wizArmed, setWizArmed] = useHeldState(false);
  useEffect(() => {
    if (!needsVehicle) return;
    const t = setTimeout(() => setWizArmed(true), 1350);
    return () => { clearTimeout(t); setWizArmed(false); };
  }, [needsVehicle]);
  const [delhiOpen, setDelhiOpen] = useHeldState(false);
  const [settingsOpen, setSettingsOpen] = useHeldState(false);
  const [placePickSlot, setPlacePickSlot] = useState<"home" | "work" | null>(null);
  const [ledgerOpen, setLedgerOpen] = useHeldState(false);
  /* home IS the dosimeter: the app rests on the day surface; the map +
     journey is a destination reached through the "where to?" bar. homeOpen
     = the day covers the idle map; false = the user is browsing the map
     surface itself (the peek card + BACK are the doors home). dayNonce
     re-assembles the local reconstruction each time a fresh ambient read
     lands. */
  const [homeOpen, setHomeOpen] = useHeldState(true);
  const [dayNonce, setDayNonce] = useState(0);
  const [userPos, setUserPos] = useState<{ lat: number; lon: number } | null>(null);
  const [hasLoc, setHasLoc] = useState(false);
  const [apiOk, setApiOk] = useState<boolean | null>(null);
  /* the polled field block carries its own age — stamp it so the chip
     can keep counting after the polls start failing (frozen age_s on a
     dead network lies "9 min" forever) */
  const [aqiField, setAqiField] = useState<{ data: FieldStatus; at: number } | null>(null);
  /* the day's ambient read — feeds the peek card's "now ~N µg/m³" so the
     idle map feels the air, not just the sampled totals */
  const [ambientUg, setAmbientUg] = useState<number | null>(null);
  /* km to the nearest real instrument reading behind the field at the
     user's cell — the "how accurate at my home" answer, surfaced once
     in settings' numbers explainer (null when the field is model-only) */
  const [nearestKm, setNearestKm] = useState<number | null>(null);
  const [introSeen, setIntroSeen] = useHeldState<boolean | null>(null);
  /* welcome_seen_v1 — the first-breath cinematic; null until the flag
     reads so a returning user never flashes the overlay for a frame */
  const [welcomeSeen, setWelcomeSeen] = useHeldState<boolean | null>(null);
  const net = useNetStatus();

  const [fontsLoaded] = useFonts({
    Inter_400Regular, Inter_500Medium, Inter_600SemiBold,
    NotoSansDevanagari_400Regular, NotoSansDevanagari_500Medium, NotoSansDevanagari_600SemiBold,
    // display voice — Satoshi (ITF Free Font License, embedded as assets);
    // Fraunces retired per docs/20 (the AI-template signature font)
    "Satoshi-Light": require("./assets/fonts/Satoshi-Light.ttf"),
    "Satoshi-Regular": require("./assets/fonts/Satoshi-Regular.ttf"),
    "Satoshi-Medium": require("./assets/fonts/Satoshi-Medium.ttf"),
    "Satoshi-Bold": require("./assets/fonts/Satoshi-Bold.ttf"),
    "Satoshi-Black": require("./assets/fonts/Satoshi-Black.ttf"),
    IBMPlexMono_400Regular, IBMPlexMono_500Medium, IBMPlexMono_600SemiBold,
  });

  useEffect(() => { mark("app.mounted"); }, []);

  useEffect(() => {
    if (fontsLoaded) { mark("fonts.ready"); SplashScreen.hideAsync().catch(() => {}); }
  }, [fontsLoaded]);

  /* ---- boot: warm the API, load trips/settings, resolve location ---- */
  useEffect(() => {
    /* one flaky ping while a 25 s plan krige is in flight flashed a false
       "can't reach the server" strip — require two consecutive misses */
    let misses = 0;
    const ping = () => fetch(`${API}/health`, { keepalive: true })
      .then((r) => { misses = r.ok ? 0 : misses + 1; if (!misses) setApiOk(true); else if (misses >= 2) setApiOk(false); })
      .catch(() => { misses += 1; if (misses >= 2) setApiOk(false); });
    ping();
    const healthIv = setInterval(ping, 15000);
    /* slot assignment happens in the poll handler (event context), so the
       Marker pool only ever mutates lngLat+child — never mounts/unmounts
       mid-draw (the upstream iOS-sim SIGSEGV class). */
    const poll = () => fetchJson(`${API}/reports`).then((r) => {
      setReportSlots((prev) => reconcileReportSlots(prev, r));
    }).catch(() => {});
    poll();
    const iv = setInterval(poll, 60000);
    /* the map-screen freshness chip reads the served field's own status
       block — GET /aqi's `field` IS FIELD.status() verbatim (same keys
       the /v2/plan `field` block carries): real age_s or honestly absent,
       never a guessed number. It also keeps the field warm (aqi triggers
       a server-side refresh). */
    loadTrips().then(setTrips).catch(() => {});
    loadSettings().then(setSettings).catch(() => {});
    /* the OS permission dialog no longer fires at boot — on a cold install
       it landed on top of the first open before any value or context, and
       it still waited behind consent. It lives in the introSeen-gated
       effect below instead. */
    /* the /aqi poll does two jobs now: the freshness chip's field block,
       AND the dosimeter's foreground ambient sample — each read lands in
       daylog.json (on-device only; the dedupe keeps the file sparse). The
       read happens at the user's own position when the OS has one; the
       Delhi centroid is the fallback the chip has always used. */
    const aqiPoll = (freshGps = true) => {
      void (async () => {
        /* position for the sample: last-known fix is free — only burn a
           real GPS request when there's no fix or it's >15 min old (the
           dedupe windows are ~450 m / 8 min, so a cached fix loses nothing).
           The boot call passes freshGps=false: on a cold install there is
           no last-known fix and no permission yet, so a GPS request would
           only stall the first real number — read the Delhi centroid
           (the field is city-wide anyway) and upgrade once positioned. */
        let pos = await Location.getLastKnownPositionAsync().catch(() => null);
        /* a cached fix can be continents stale (emulator seed, travel
           since the last open) — an out-of-NCR last-known buys only a
           guaranteed out-of-area read and a bogus userPos; the centroid
           serves the real city field until a fresh fix lands
           (testday-android finding #2). */
        if (pos && !inNcr(pos.coords.latitude, pos.coords.longitude)) pos = null;
        if (freshGps && (!pos || Date.now() - pos.timestamp > 15 * 60 * 1000)) {
          pos = await Location.getCurrentPositionAsync(
            { accuracy: Location.Accuracy.Balanced }).catch(() => null);
        }
        const lat = pos?.coords.latitude ?? DELHI[1];
        const lon = pos?.coords.longitude ?? DELHI[0];
        if (pos) setUserPos({ lat, lon });
        try {
          const j = await fetchJson(`${API}/aqi?lat=${lat}&lon=${lon}`, 8000);
          const nf = j?.field && typeof j.field === "object" ? (j.field as FieldStatus) : null;
          /* the field ticks at ~140 s but we poll at 60 — skip the whole-app
             re-render when the block is verbatim the same */
          setAqiField((prev) =>
            JSON.stringify(prev?.data) === JSON.stringify(nf) ? prev
              : nf == null ? null : { data: nf, at: Date.now() });
          const bz = typeof j?.pm25 === "number" ? j.pm25 : null;
          const amb = typeof j?.pm25_ambient === "number" ? j.pm25_ambient : bz;
          const nk = typeof j?.nearest_sample_km === "number" && isFinite(j.nearest_sample_km)
            ? j.nearest_sample_km : null;
          setNearestKm((prev) => (prev === nk ? prev : nk));
          /* same value → no re-render — the 60 s poll usually repeats
             the same ambient sample until the field ticks */
          setAmbientUg((prev) => (prev === amb ? prev : amb));
          if (amb != null || bz != null) {
            /* only re-render the dosimeter surfaces when a sample actually
               lands — the dedupe drops most 60 s polls (~8 min cadence) */
            if (await recordSample({ ts: Date.now(), lat, lon, amb: amb ?? bz!, bz })) {
              setDayNonce((n) => n + 1);
            }
          }
          /* air alerts — real-event detection piggybacks this same 60 s
             tick (foreground only, honest "while the app is open"); the
             engine self-throttles its own /v2/why + /v2/day reads and
             drops every check when the settings say so. fire-and-forget:
             a slow /v2/why must never hold the dosimeter sample. */
          void checkAirEvents({ lat, lon, ambientUg: amb ?? bz });
        } catch {}
      })();
    };
    aqiPoll(false);
    const aqiIv = setInterval(() => aqiPoll(), 60000);
    aqiPollRef.current = () => aqiPoll(true);
    // first-run gate is the consent record now (supersedes intro_seen.txt)
    loadConsent().then((c) => setIntroSeen(c.seen)).catch(() => setIntroSeen(false));
    loadWelcomeSeen().then(setWelcomeSeen).catch(() => setWelcomeSeen(true));
    return () => { clearInterval(iv); clearInterval(healthIv); clearInterval(aqiIv); };
  }, [setFrom, setTrips, settings.lang]);

  /* first-open ordering: the consent sheet is required on every cold
     install, but it doesn't get to stand in front of the first real
     number — the ambient read gets a beat of visibility first, then the
     sheet slides in and stays required. The 9 s fallback keeps the gate
     honest when the field can't answer (offline cold open): value-first
     is a preference, consent is a requirement, and nothing consent-free
     may gate the value moment either way. Donation can't fire in the
     gap — POST /v2/trip only runs on trip arrival, gated by
     settings.share, which this sheet itself writes. */
  const [gateReady, setGateReady] = useHeldState(false);
  useEffect(() => {
    if (gateReady || introSeen !== false) return;
    const t = setTimeout(() => setGateReady(true), ambientUg != null ? 4000 : 9000);
    return () => clearTimeout(t);
  }, [gateReady, introSeen, ambientUg]);

  /* the OS location ask follows the consent answer — before it, the dialog
     is a wall over the first value and reads as a data-grab with no
     context. Returning users already have consent on disk, so this fires
     at boot exactly like the old code path. After a real fix lands, take
     the positioned /aqi read immediately instead of waiting out the 60 s
     interval (the boot read used the centroid). */
  const aqiPollRef = useRef<(() => void) | null>(null);
  const didAskLoc = useRef(false);
  useEffect(() => {
    if (introSeen !== true || didAskLoc.current) return;
    didAskLoc.current = true;
    let cancelled = false;
    void (async () => {
      const r = await Location.requestForegroundPermissionsAsync().catch(() => null);
      if (cancelled) return;
      setHasLoc(!!r?.granted);
      const pos = await Location.getCurrentPositionAsync({ accuracy: Location.Accuracy.Balanced }).catch(() => null);
      if (pos && !cancelled) {
        setUserPos({ lat: pos.coords.latitude, lon: pos.coords.longitude });
        /* prev ?? — a fast user can type a real place inside the ~1-2 s
           permission→fix window on a warm boot; the GPS answer must not
           clobber a from the user already chose */
        setFrom((prev) => prev ?? { name: t("placeCurrentLocation", settings.lang), subtitle: "", lat: pos.coords.latitude, lon: pos.coords.longitude });
        // wait for the initial style/tile load to settle before animating —
        // flyTo during first-load is a render-thread spike on the iOS sim
        setTimeout(() => camRef.current?.flyTo({ center: [pos.coords.longitude, pos.coords.latitude], zoom: 15, duration: camDur(900) }), 600);
        aqiPollRef.current?.();
      }
    })();
    return () => { cancelled = true; };
  }, [introSeen, setFrom, settings.lang]);

  /* the layers sheet is idle-phase chrome — leaving idle (search, compare,
     nav) must close it or it bleeds through stacked behind the next surface
     (reproduced: its toggles rendered under the compare sheet) */
  useEffect(() => {
    if (phase === "idle") return;
    const t = setTimeout(() => setLayersOpen(false), 0);
    return () => clearTimeout(t);
  }, [phase]);

  /* Android hardware BACK closes the topmost open surface — every overlay
     here is a plain View (no Modal onRequestClose), so without a dispatcher
     BACK fell through and exited the app (Android forensic find on the
     drawer). Checked topmost-first, matching JSX mount order; SearchScreen
     and Sidebar keep their own local handlers — registered later, they win
     the race for the same press. needsVehicle (the forced first-pick)
     is intentionally NOT dismissable this way. */
  useEffect(() => {
    const sub = BackHandler.addEventListener("hardwareBackPress", () => {
      if (vehicleOpen) { setVehicleOpen(false); return true; }
      if (settingsOpen) { setSettingsOpen(false); return true; }
      if (ledgerOpen) { setLedgerOpen(false); return true; }
      if (delhiOpen) { setDelhiOpen(false); return true; }
      if (layersOpen) { setLayersOpen(false); return true; }
      if (sidebarOpen) { setSidebarOpen(false); return true; }
      if (mapPickArmed) { setMapPickArmed(false); return true; }
      /* phases: BACK on compare = its X (clearRoute); BACK inside nav
         must never kill the app mid-trip — the explicit end-early
         button is the honest exit. Search handles its own press.
         BACK on the idle map returns home — the day surface is root. */
      if (phase === "compare") { setHomeOpen(true); clearRoute(); return true; }
      if (phase === "nav") return true;
      if (phase === "idle" && !homeOpen) { setHomeOpen(true); return true; }
      return false;
    });
    return () => sub.remove();
  }, [vehicleOpen, settingsOpen, ledgerOpen, delhiOpen, layersOpen, sidebarOpen, mapPickArmed, homeOpen, phase, clearRoute]);

  const patchSettings = useCallback((p: Partial<ShellSettings>) => {
    setSettings((s) => { const n = { ...s, ...p }; saveSettings(n); return n; });
    // the consent record mirrors the share toggle — it is the canonical
    // donation answer (nav engine + trip submit read it)
    if ("share" in p) {
      saveConsent({ sharing: p.share ? "on" : "off", ts: Date.now() }).catch(() => {});
    }
    // drawer chip -> profile: a coarse pick that changes BUCKET starts a
    // fresh profile (fuel/year are class-specific, honestly unknown).
    // A profile already inside the same bucket is left alone — otherwise
    // applyVehicle's own mirror (metro -> "transit") round-trips through
    // DRAWER2CLS as "bus" and clobbers the wizard's finer pick.
    if (p.vehicle != null) {
      const cls = DRAWER2CLS[p.vehicle];
      if (cls) {
        getVehicle().then((cur) => {
          if (cur == null || CLS2DRAWER[cur.cls] !== p.vehicle) {
            setVehicleProfile({ cls, fuel: null, year: null });
          }
        }).catch(() => {});
      }
    }
  }, [setVehicleProfile]);

  /** Sheet/compare answer: persist the profile AND mirror its class
   *  into the drawer so both surfaces show the same vehicle. */
  const applyVehicle = useCallback((p: VehicleProfile) => {
    setVehicleProfile(p);
    patchSettings({ vehicle: CLS2DRAWER[p.cls] });
  }, [setVehicleProfile, patchSettings]);

  /* boot sync: a profile saved in a previous run backfills the drawer's
   *  coarse class (drawer chip -> profile sync lives in patchSettings). */
  useEffect(() => {
    if (!settings.vehicle && vehicle) {
      /* react-hooks/set-state-in-effect: defer the sync out of the
         effect body — it writes settings, not an external system */
      queueMicrotask(() => patchSettings({ vehicle: CLS2DRAWER[vehicle!.cls] }));
    }
  }, [vehicle, settings.vehicle, patchSettings]);

  const deleteAll = useCallback(() => {
    // server half first — the raw device token dies with contributor.txt,
    // so the DELETE must carry the CURRENT id before the wipe removes it.
    // contributorId() resolves from its file fast; a hung read must not
    // hold the wipe hostage, hence the 800 ms cap.
    void (async () => {
      const tok = await Promise.race([
        contributorId(),
        new Promise<string | null>((r) => setTimeout(() => r(null), 800)),
      ]);
      if (tok) {
        // header, not ?token= — a query-string token lands in access
        // logs and any future Referer; headers don't
        void fetch(`${API}/v2/ledger`, {
          method: "DELETE",
          headers: { "X-Device-Token": tok },
        }).catch(() => {});
      }
      clearAllData();
      resetEventsStore();   // events.json baselines + dedupe — same wipe
      setTrips([]); setVehicleProfile(null);
      /* dayNonce bumps so the mounted home re-assembles its (now empty)
         reconstruction instead of holding pre-wipe totals — the wipe
         invalidates the day, same as a fresh ambient read does */
      setDayNonce((n) => n + 1);
      setSettings((s) => ({ ...DEFAULT_SETTINGS, lang: s.lang }));
      /* closing the sheet IS the acknowledgment — the user lands back on
         a clean map; the consent gate re-arms itself on next launch */
      setSettingsOpen(false); setSidebarOpen(false);
    })();
  }, [setTrips, setVehicleProfile]);
  const toggleLayer = useCallback((k: LayerKey, v: boolean) => {
    setLayers((l) => ({ ...l, [k]: v }));
    if (!v) return;                                     // lazy: fetch on first enable
    if (k === "fires" && !fires) fetchJson(`${API}/fires`).then(setFires).catch(() => {});
    if (k === "spots" && !spots) fetchJson(`${API}/blackspots`).then(setSpots).catch(() => {});
    if (k === "corridors" && !community) fetchJson(`${API}/community`).then(setCommunity).catch(() => {});
  }, [fires, spots, community, setCommunity]);
  /* hooks before any early return — the dosimeter hook must run on the
     font-gate frame too or the hook order flips when fonts land */
  const dayPos = userPos ?? { lat: DELHI[1], lon: DELHI[0] };
  /* withCurve only once the stack is open — the peek never needs the
     12-payload forecast, so it isn't fetched on cold start */
  const dayData = useDayData(dayPos.lat, dayPos.lon, trips, dayNonce, homeOpen, lang);
  useEffect(() => { if (dayData) { mark("daydata.first"); report("boot"); } }, [dayData != null]);
  const sel = options[selected];
  const mapField: FieldStatus | null = useMemo(() => planField ?? (aqiField
    ? { ...aqiField.data,
        age_s: aqiField.data.age_s == null
          ? null
          : aqiField.data.age_s + (Date.now() - aqiField.at) / 1000,
        stale: aqiField.data.stale === true ? true
          : aqiField.data.age_s == null ? aqiField.data.stale ?? null
          : (aqiField.data.age_s + (Date.now() - aqiField.at) / 1000)
            > (aqiField.data.stale_after_s ?? 2700) }
    : null), [planField, aqiField]);

  /* ---- memo'd subtree props: every handler below must keep identity
     across poll renders or the memo boundaries are theatre ---- */
  const compassPosition = useMemo(() => (phase === "nav"
    ? { top: insets.top + 108, right: 12 }
    : { top: insets.top + 76, right: 12 }), [phase, insets.top]);
  const logoPosition = useMemo(() => ({ bottom: insets.bottom + 72, left: 10 }), [insets.bottom]);
  const attributionPosition = useMemo(() => ({ bottom: insets.bottom + 72, right: 10 }), [insets.bottom]);
  const searchUserLoc = useMemo(() => (from ? { lat: from.lat, lon: from.lon } : null), [from]);

  const onMapPress = useCallback(async (f: MapPressEvent) => {
    if (!mapPickArmed) return;
    setMapPickArmed(false);
    const c = (f as { nativeEvent?: { lngLat?: [number, number] } }).nativeEvent?.lngLat;
    if (!c) return;
    tap();   // the pick landed — same weight as a row tap
    const rev = await reverseName(c[1], c[0]);
    if (placePickSlot) {
      // the unset home/work slot asked for this pick ("choose on map")
      patchSettings({ [placePickSlot]: { name: rev.name, lat: c[1], lon: c[0] } });
      setPlacePickSlot(null);
      setSidebarOpen(true);
      return;
    }
    pick({ name: rev.name, subtitle: rev.subtitle, lat: c[1], lon: c[0] }, "to");
  }, [mapPickArmed, placePickSlot, patchSettings, pick]);
  const onMapLongPress = useCallback(async (f: MapPressEvent) => {
    const c = (f as { nativeEvent?: { lngLat?: [number, number] } }).nativeEvent?.lngLat;
    if (!c) return;
    const rev = await reverseName(c[1], c[0]);
    pick({ name: rev.name, subtitle: rev.subtitle, lat: c[1], lon: c[0] }, "to");
  }, [pick]);
  const onTrackUserLocationChange = useCallback((e: TrackChangeEvent) => {
    if (!e.nativeEvent.trackUserLocation) setFollow(false);
  }, [setFollow]);

  /* the drawer is modal — opening it dismisses the layers sheet, which
     otherwise mounts later in JSX and floats ABOVE the open sidebar
     (testday-ios z-order wart). Mirrors onDelhiTodayOpen/onFullSettings
     closing the drawer beneath their own surface. */
  const openSidebar = useCallback(() => { setLayersOpen(false); setSidebarOpen(true); }, []);
  const openSearch = useCallback(() => { setEditWhich("to"); setPhase("search"); }, [setEditWhich, setPhase]);
  const closeCompareToHome = useCallback(() => { setHomeOpen(true); clearRoute(); }, [clearRoute]);
  const onSearchClose = useCallback(() => {
    if (placePickSlot) { setPlacePickSlot(null); setSidebarOpen(true); }
    setPhase(to ? "compare" : "idle");
  }, [placePickSlot, setPhase, to]);
  const onSearchSelect = useCallback(async (sel: SearchSelection) => {
    if (sel.type === "place") {
      if (placePickSlot) {
        // sidebar's unset home/work slot asked for a search pick —
        // land the place in settings and return to the drawer
        patchSettings({ [placePickSlot]: {
          name: sel.place.name, lat: sel.place.lat, lon: sel.place.lon } });
        setPlacePickSlot(null);
        setPhase("idle");
        setSidebarOpen(true);
        return;
      }
      setMapPickArmed(false);
      setHomeOpen(false);        // the journey lives on the map surface
      pick({ name: sel.place.name, subtitle: sel.place.subtitle ?? "",
        lat: sel.place.lat, lon: sel.place.lon }, "to");
      return;
    }
    if (sel.type === "choose_on_map") {
      setHomeOpen(false);        // the map surface itself
      setPhase("idle");
      setMapPickArmed(true);       // next map tap picks — for the slot
                                   // when placePickSlot is armed
      return;
    }
    const pos = await Location.getCurrentPositionAsync(
      { accuracy: Location.Accuracy.Balanced }).catch(() => null);
    if (pos && placePickSlot) {
      patchSettings({ [placePickSlot]: { name: t("yourLocation", lang),
        lat: pos.coords.latitude, lon: pos.coords.longitude } });
      setPlacePickSlot(null);
      setPhase("idle");
      setSidebarOpen(true);
    } else if (pos) pick({ name: t("yourLocation", lang), subtitle: "",
      lat: pos.coords.latitude, lon: pos.coords.longitude }, "from");
    else setPhase(to ? "compare" : "idle");
  }, [placePickSlot, patchSettings, setPhase, pick, lang, to]);
  const onLocate = useCallback(() => {
    if (follow) { setFollow(false); return; }
    /* warm the fused provider before engaging follow — MapLibre's
       native layer posts a raw error toast when track starts with
       no fix yet (Android forensic find); a one-shot fix primes it */
    Location.getCurrentPositionAsync({ accuracy: Location.Accuracy.Balanced })
      .then((pos) => { if (pos) { setHasLoc(true); setFollow(true); } })
      .catch(() => {});
  }, [follow, setFollow]);
  const openLayers = useCallback(() => setLayersOpen(true), []);
  const onPeekOpen = useCallback(() => setHomeOpen(true), []);
  const onToggleSteps = useCallback(() => setStepsOpen(!stepsOpen), [stepsOpen, setStepsOpen]);
  const onVehiclePress = useCallback(() => setVehicleOpen(true), []);
  const onNavExit = useCallback(() => { setHomeOpen(true); exitNav(); }, [exitNav]);
  const onHomeMap = useCallback(() => setHomeOpen(false), []);
  const onHomeCity = useCallback(() => setDelhiOpen(true), []);
  const onHomeTrips = useCallback(() => setLedgerOpen(true), []);
  const onHomeProfile = useCallback((p: string) => patchSettings({ profile: p } as Partial<ShellSettings>), [patchSettings]);
  const onCheckin = useCallback((c: Parameters<typeof setCheckin>[1]) => {
    void setCheckin(Date.now(), c).then(() => setDayNonce((n) => n + 1));
  }, []);
  const onSidebarClose = useCallback(() => setSidebarOpen(false), []);
  const onPickPlace = useCallback((slot: "home" | "work") => {
    setPlacePickSlot(slot);
    setSidebarOpen(false);
    setPhase("search");
  }, [setPhase]);
  const onDelhiTodayOpen = useCallback(() => { setSidebarOpen(false); setDelhiOpen(true); }, []);
  const onTripReceipt = useCallback(() => { setSidebarOpen(false); setLedgerOpen(true); }, []);
  const onFullSettings = useCallback(() => { setSidebarOpen(false); setSettingsOpen(true); }, []);
  const onNavigate = useCallback((p: SavedPlace) => pick({ ...p, subtitle: "" }, "to"), [pick]);
  const onLangChange = useCallback((l: "en" | "hi") => patchSettings({ lang: l }), [patchSettings]);
  const onShare = useCallback(() => Share.share({ message: t("shareAppBody", lang) }).catch(() => {}), [lang]);
  const onShareTrip = useCallback((tr: Trip) => Share.share({
    message: t("shareTripBody", lang, {
      from: placeNameLabel(tr.from, lang), to: placeNameLabel(tr.to, lang),
      // cigarette figure only with show_cig on; µg is the default
      dose: tr.dose_ug != null
        ? (settings.show_cig ? t("nav_cigs", lang, { n: approx(cigOf(tr.dose_ug) ?? 0) }) : `~${Math.round(tr.dose_ug)}µg`)
        : "—",
      // co2 was never passed — the template printed a literal "{co2}"
      co2: tr.emit_kg != null ? t("share_co2", lang, { n: `~${tr.emit_kg.toFixed(1)}` }) : "—",
    }),
  }).catch(() => {}), [lang, settings.show_cig]);
  const onLayersClose = useCallback(() => setLayersOpen(false), []);
  const onDelhiClose = useCallback(() => setDelhiOpen(false), []);
  const onLedgerClose = useCallback(() => setLedgerOpen(false), []);
  const onSettingsClose = useCallback(() => setSettingsOpen(false), []);
  const onSettingsChange = useCallback((k: string, v?: unknown) => {
    if (k === "editVehicle") { setSettingsOpen(false); setVehicleOpen(true); return; }
    patchSettings({ [k]: v } as Partial<ShellSettings>);
  }, [patchSettings]);
  const onVehicleDone = useCallback((p: VehicleProfile) => {
    setVehicleOpen(false);
    /* re-plan commit must not share the sheet-close frame — the
       close anim + options/RouteTint landing together is the
       residual-SIGSEGV trigger on the virtualized-GPU sim */
    setTimeout(() => applyVehicle(p), 80);
  }, [applyVehicle]);
  /* the sheet's own skip/✕ must honour the armed path too — clearing only
     vehicleOpen left the wizard-mounted sheet undismissable (dead row,
     Android audit #1). needsVehicle stays true so the plan keeps its
     estimate; the effect won't re-arm since its dep never changed. */
  const onVehicleClose = useCallback(() => {
    setVehicleOpen(false);
    setWizArmed(false);
  }, []);
  const onOnboardDone = useCallback(({ sharing }: { sharing: SharingChoice }) => {
    patchSettings({ share: sharing === "on" });
    setIntroSeen(true);
  }, [patchSettings]);

  const mapTree = (
    /* key pins the instance across the fontsLoaded tree-shape flip —
       without it the map unmounts/remounts and the tile load restarts */
    <MapTree key="map"
      lang={lang}
      compassPosition={compassPosition}
      logoPosition={logoPosition}
      attributionPosition={attributionPosition}
      onPress={onMapPress}
      onLongPress={onMapLongPress}
      camRef={camRef}
      trackUserLocation={follow ? "default" : undefined}
      onTrackUserLocationChange={onTrackUserLocationChange}
      hasLoc={hasLoc}
      corridors={community?.top_corridors ?? null}
      reportSlots={reportSlots}
      fires={fires} spots={spots} layers={layers}
      options={deferredOptions}
      selected={selected}
      strips={strips}
      fromPin={fromPin} toPin={toPin}
      fromSet={!!from} toSet={!!to}
      pinReady={pinReady}
      drawHeld={drawHeld} />
  );

  /* mount the map under the splash: the native style parse + tile fetch
     (hosted OpenFreeMap — nothing bundled) used to start only AFTER the
     ~220 ms font gate; now it overlaps it. Splash still covers the tree —
     nothing about the visible order changes. */
  if (!fontsLoaded) return <View style={s.root}>{mapTree}</View>;
  return (
    <View style={s.root}>
      <StatusBar style="dark" />
      {mapTree}

      {/* rest state chrome: search bar + locate + layers (doc 02 §S1).
          The pill yields while the home sheet is open — it renders before
          HomeScreen in tree order, so under the hero it sat occluded:
          looked alive, answered no taps (android-drive finding). The
          home screen's own "go somewhere" CTA covers search there. */}
      {phase !== "nav" && !(phase === "idle" && homeOpen) && (
        <View style={[s.pillWrap, { top: insets.top + 10 }]}>
          <SearchBar
            label={phase === "compare" && to ? to.name : undefined}
            lang={lang}
            onMenu={openSidebar}
            onPress={openSearch}
            onClear={phase === "compare" ? closeCompareToHome : undefined} />
        </View>
      )}
      <SearchScreen
        visible={phase === "search"}
        lang={lang}
        userLocation={searchUserLoc}
        onClose={onSearchClose}
        onSelect={onSearchSelect} />
      {phase === "idle" && (
        <>
          <View style={[s.locateWrap, { bottom: insets.bottom + 16 }]}>
            <LocateButton active={follow} onPress={onLocate} lang={lang} />
          </View>
          <View style={[s.layersWrap, { bottom: insets.bottom + 16 }]}>
            <LayersButton anyOn={Object.values(layers).some(Boolean)} onPress={openLayers} lang={lang} />
          </View>
          {/* the peek card is the door home — floats above the corner
              FABs while the user browses the map surface. Hides itself
              before disk is read. */}
          {dayData && !homeOpen && (
            <View style={[s.peekWrap, { bottom: insets.bottom + 72 }]} pointerEvents="box-none">
              <DayPeek data={dayData} lang={lang} onOpen={onPeekOpen}
                ambientUg={ambientUg} budgetUg={PROFILE_BUDGET_UG[settings.profile]} />
            </View>
          )}
        </>
      )}
      {/* SEAM(breath-chip): optional "breathing heavier/lighter" chip while moving
          (doc 02 §S1) — needs a real trailing-30min baseline; not yet wired. */}

      {/* freshness chip — real field age on the map screen: the /v2/plan
          field block during compare, else the polled /aqi field block.
          Stale shows as stale; no field → nothing claims freshness. */}
      {phase !== "nav" && phase !== "search" && !homeOpen && mapField && (
        <View style={[s.freshWrap, { top: insets.top + 62 }]} pointerEvents="box-none">
          <FreshnessChip
            ageS={mapField.age_s} stale={mapField.stale}
            sources={fieldSources(mapField)} lang={lang} compact />
        </View>
      )}
      {phase === "compare" && (
        <CompareSheet options={options} selected={selected} onSelect={setSelected}
          depart={depart} departCurve={departCurve} notified={notified}
          onRemind={remind} loading={loadingRoute} refining={refining}
          steps={steps} stepsOpen={stepsOpen} onToggleSteps={onToggleSteps}
          onStart={startNav} onClose={closeCompareToHome} lang={lang}
          vehicle={vehicle} onVehiclePress={onVehiclePress}
          onVehicleChange={applyVehicle}
          planError={planError} onRetry={retryPlan} degraded={planDegraded}
          fieldAgeS={planField?.age_s}
          showCig={settings.show_cig} />
      )}
      {phase === "nav" && sel && (
        <NavSession option={sel} options={options} from={from} to={to} steps={steps}
          camRef={camRef} lang={lang} share={settings.share} voice={settings.voice}
          onExit={onNavExit}
          vehicle={vehicle} showCig={settings.show_cig} onTripDone={recordTrip} />
      )}

      {/* offline/stale pill — real request outcomes drive it (offline/
          status.ts): live data → no pill; last-good or nothing → labelled,
          pending trip donations counted, tap re-probes. apiOk kept as the
          belt-and-suspenders health check from before.
          Mounts AFTER NavSession: z-order on this stack is sibling
          mount-order (iOS) and elevation-then-mount-order (Android —
          the D1 finding), so this slot puts the pill above the nav turn
          card (same V2Elev.float rung, later mount) while every sheet
          below still beats it — "above map chrome, below sheets". The
          overlap with the turn card's lower edge is deliberate: during
          nav the +92 slot belongs to the engine's own status pills
          (reroute / outside-field / strip-unavailable). */}
      {(net.state !== "online" || apiOk === false) && (
        <Pressable style={[s.offlineWrap, { top: insets.top + 66 }]} onPress={() => { tick(); void net.refresh(); }}
          accessibilityRole="button" accessibilityLabel={t("offline", lang)}>
          <Text {...DYNAMIC_TYPE} style={[s.offlineTxt, { fontFamily: fam(lang, "med") }]}>
            {net.state === "stale" ? t("offlineStale", lang) : t("offline", lang)}
            {net.state === "stale" && net.staleAgeS != null
              ? ` · ${t("updatedMinAgo", lang, { n: Math.max(1, Math.round(net.staleAgeS / 60)) })}`
              : ""}
            {net.pending > 0 ? ` · ${t("offlinePending", lang, { n: net.pending })}` : ""}
          </Text>
        </Pressable>
      )}
      {/* "choose on map" armed state — without this the pick was
          invisible: the sheet closed and the next map tap just did
          something the user never asked it to. Tapping the hint
          disarms; BACK does too (the dispatcher). Slides under the
          offline pill when both happen to be up. */}
      {mapPickArmed && (
        <Pressable
          style={[s.pickHintWrap, {
            top: insets.top + 66 + ((net.state !== "online" || apiOk === false) ? 36 : 0),
          }]}
          onPress={() => { tick(); setMapPickArmed(false); }}
          accessibilityRole="button" accessibilityLabel={t("mapPickHint", lang)}
        >
          <Icon name="pin" color={V2T.text2} size={14} />
          <Text {...DYNAMIC_TYPE} style={[s.pickHintTxt, { fontFamily: fam(lang, "med") }]}>
            {t("mapPickHint", lang)}
          </Text>
        </Pressable>
      )}

      {/* the dosimeter home — resting surface; covers the idle map and
          yields for the journey phases (search/compare/nav) */}
      <HomeScreen
        visible={homeOpen && phase === "idle" && !mapPickArmed}
        data={dayData} lang={lang} settings={settings} ambientUg={ambientUg}
        onMenu={openSidebar}
        onGo={openSearch}
        onMap={onHomeMap}
        onCity={onHomeCity}
        onTrips={onHomeTrips}
        onProfile={onHomeProfile}
        onCheckin={onCheckin} />
      <Sidebar open={sidebarOpen} onClose={onSidebarClose} trips={trips} lang={lang}
        settings={settings} onSettings={patchSettings} onDeleteData={deleteAll}
        onPickPlace={onPickPlace}
        onArmBrief={armDailyBrief} currentDest={to}
        onDelhiToday={onDelhiTodayOpen}
        onTripReceipt={onTripReceipt}
        onFullSettings={onFullSettings}
        onNavigate={onNavigate}
        onLang={onLangChange}
        onShare={onShare}
        onShareTrip={onShareTrip} />
      <LayersSheet visible={layersOpen} values={layers} onToggle={toggleLayer}
        onClose={onLayersClose} lang={lang} />
      <DelhiToday visible={delhiOpen} onClose={onDelhiClose} lang={lang} showCig={settings.show_cig} />
      <LedgerScreen visible={ledgerOpen} onClose={onLedgerClose} lang={lang} showCig={settings.show_cig} onTripsChanged={reloadTrips} />
      <SettingsScreen visible={settingsOpen} onClose={onSettingsClose}
        lang={lang} current={settings} onArmBrief={armDailyBrief}
        onArmAlerts={armAirEvents}
        onDeleteData={deleteAll} nearestKm={nearestKm}
        onChange={onSettingsChange} />
      <VehicleSheet visible={vehicleOpen || wizArmed} lang={lang}
        current={vehicle}
        onDone={onVehicleDone}
        onClose={onVehicleClose} />

      <OnboardingScreen visible={introSeen === false && gateReady} lang={lang}
        onDone={onOnboardDone} />

      {/* the first-breath cinematic — once per install (welcome_seen_v1),
          mounted last so it sits above every sheet incl. the consent
          gate; on a fresh install it exits INTO the armed onboarding
          sheet. It fetches /v2/city itself and falls back to the boot
          ambient read — a real number or honestly nothing. */}
      <WelcomeScreen
        visible={welcomeSeen === false}
        lang={lang}
        ambientUg={ambientUg}
        onDone={() => { markWelcomeSeen().catch(() => {}); setWelcomeSeen(true); }} />
    </View>
  );
}

/** Live-trip session: mounts the nav engine exactly for the nav phase —
 *  the hook owns the GNSS watcher + 1 Hz counters + off-route + strip;
 *  we only translate the plan option into its NavRoute and its summary
 *  into the receipt. (src/nav contract — see src/nav/index.ts) */
const NavSession = React.memo(function NavSession({
  option, options, from, to, steps, camRef, lang, share, voice, vehicle, showCig, onExit, onTripDone,
}: {
  option: V2Option; options: V2Option[]; from: Place | null; to: Place | null; steps: Step[] | null;
  camRef: React.RefObject<CameraRef | null>; lang: "en" | "hi";
  share: boolean; onExit: () => void;
  /** S8 profile — the donation marks puc_calibrated from it on
      private-motor trips only */
  vehicle?: VehicleProfile | null;
  /** turn-guidance voice — settings.voice; the engine defaults to silent
     *  without it, which left every cue dead until this was wired */
  voice: boolean;
  /** cigarette-equivalence framing — off by default (settings.show_cig) */
  showCig?: boolean;
  onTripDone: (t: {
    label: string; vehicle: string; doseUg: number | null; avoidedUg: number | null;
    emitKg?: number | null; doseLoUg?: number | null; doseHiUg?: number | null;
  }) => void;
}) {
  const [summary, setSummary] = useState<NavSummary | null>(null);
  /* the arrival swap is two commits, not one: NavChrome unmounts on its
     own frame, then the receipt mounts next frame — a remove+add swap
     against the map's draw is the residual-SIGSEGV class (ci15). */
  const [receiptReady, setReceiptReady] = useState(false);
  useEffect(() => {
    if (!summary) return;
    holdMapDraw();   // the receipt mount lands inside the hold window
    const raf = requestAnimationFrame(() => setReceiptReady(true));
    return () => cancelAnimationFrame(raf);
  }, [summary]);
  /* "× less than by X" compares against the smokiest *other* option —
     when the taken mode was itself the worst-dose plan the line would
     read as a nonsense self-comparison ("56× less than by On foot" on a
     walk trip). Options array is the same objects the sheet picked from,
     so identity holds. */
  const worstDose = Math.max(
    ...options.filter((o) => o !== option).map((o) => o.dose?.mid ?? 0), 0);
  const worstOpt = worstDose > 0
    ? options.find((o) => o !== option && (o.dose?.mid ?? 0) === worstDose) : undefined;
  const altEmit = options
    .filter((o) => o !== option && (o.emissions?.co2_kg?.mid ?? 0) > 0)
    .sort((a, b) => (a.emissions.co2_kg?.mid ?? 0) - (b.emissions.co2_kg?.mid ?? 0))[0];
  /* heaviest OTHER option's CO2 mid — the co2_avoided counterfactual,
     same excluded-self rule as worstDose */
  const worstCo2 = Math.max(
    ...options.filter((o) => o !== option).map((o) => o.emissions?.co2_kg?.mid ?? 0), 0);
  /* puc_calibrated is a property of the emissions estimate — it only
     exists on private-motor trips; on metro/walk/cycle the key stays
     out of the donation entirely */
  const PRIVATE_MOTOR = ["car", "car_open", "bike", "auto"];
  const pucCalibrated = PRIVATE_MOTOR.includes(option.mode ?? "")
    ? vehicle?.puc != null
    : null;
  const nav = useNavEngine({
    route: {
      route_id: option.route_id ?? "",
      geometry: option.geometry ?? undefined,
      eta_s: option.eta_s,
      mode: option.mode,
      distance_km: option.distance_km,
      to: to ? { lat: to.lat, lon: to.lon } : undefined,
      steps: ((option.steps ?? steps) as NavStep[] | null) ?? null,
      alternatives: options.map((o) => ({
        label: o.label,
        doseUgMid: o.dose?.mid ?? null,
        co2KgMid: o.emissions?.co2_kg?.mid ?? null,
      })),
      worstDoseUg: worstDose > 0 ? worstDose : null,
      worstCo2Kg: worstCo2 > 0 ? worstCo2 : null,
      pucCalibrated,
      emissionsBreakdown: option.emissions?.breakdown ?? null,
    },
    camRef,
    lang,
    shareEnabled: share,
    speech: voice,
    onArrive: (s) => {
      setSummary(s);
      onTripDone({   // ledger entry exists only for a trip actually travelled
        label: option.label, vehicle: s.mode,
        doseUg: s.doseUg.mid, avoidedUg: worstDose - (s.doseUg.mid ?? 0),
        emitKg: s.co2Kg?.mid ?? null,
        doseLoUg: s.doseUg?.lo ?? null, doseHiUg: s.doseUg?.hi ?? null,
      });
    },
  });
  // start once per nav session; callbacks are stable inside the engine
  const navRef = useRef(nav);
  useEffect(() => { navRef.current = nav; });   // refs update in effects, never during render
  useEffect(() => {
    navRef.current.start();
    /* teardown must not run inside the unmount commit — tearing the GNSS
       watcher down while the receipt->compare flip is on the draw thread
       is the same crash class as stopping inside the location callback. */
    return () => { const n = navRef.current; setTimeout(() => n.stop(), 250); };
  }, []);

  if (summary && !receiptReady) return null;   // chrome's own remove commit
  if (summary) {
    const data: ReceiptData = {
      durationMin: summary.durationS / 60,
      modeLabel: modeLabel(option.mode, option.label, lang),
      doseUg: nav.stripOk === false ? null : summary.doseUg,
      co2Kg: summary.co2Kg,
      pm25G: summary.pm25G,
      distanceKm: summary.distanceKm,
      mode: option.mode,
      worstDoseUg: worstDose > 0 ? worstDose : null,
      worstLabel: worstOpt ? modeLabel(worstOpt.mode, worstOpt.label, lang) : null,
      worstMode: worstOpt?.mode ?? null,
      alt: altEmit
        ? { label: modeLabel(altEmit.mode, altEmit.label, lang), co2KgMid: altEmit.emissions?.co2_kg?.mid ?? null }
        : null,
      fieldAgeMin: nav.fieldAgeMin,
      donated: summary.donated,
      endedEarly: summary.endedEarly,
    };
    return (
      /* Done tears down the whole nav session in one commit; deferring it
         past the sheet's close keeps the heavy unmount off the same frame
         as the press (iOS-sim render-thread race — same class as the
         deferred search focus/close fixes). */
      <ReceiptSheet data={data} lang={lang} showCig={showCig} onDone={() => setTimeout(onExit, 280)}
        onShare={() => Share.share({
          message: t("shareTripBody", lang, {
            from: from ? placeNameLabel(from.name, lang) : "?",
            to: to ? placeNameLabel(to.name, lang) : "?",
            // cigarette figure only with show_cig on; µg is the default
            dose: summary.doseUg.mid != null
              ? (showCig ? t("nav_cigs", lang, { n: approx(cigOf(summary.doseUg.mid) ?? 0) }) : `~${Math.round(summary.doseUg.mid)}µg`)
              : "—",
            co2: summary.co2Kg.mid != null ? `${t("nav_kg", lang, { n: `~${summary.co2Kg.mid.toFixed(1)}` })} CO₂` : "—",
          }),
        }).catch(() => {})} />
    );
  }
  return (
    <NavChrome option={option} steps={steps} doseUg={0}
      nav={nav} onRecenter={nav.recenter} showCig={showCig}
      onExit={() => nav.arrive(false)} lang={lang} />
  );
});

const s = StyleSheet.create({
  root: { flex: 1, backgroundColor: V2T.bg },
  // top/bottom come from useSafeAreaInsets inline — status bar, notch and
  // the gesture pill differ per device (no fixed 54/40 on real hardware)
  pillWrap: { position: "absolute", left: 16, right: 16 },
  locateWrap: { position: "absolute", right: 14 },
  layersWrap: { position: "absolute", left: 14 },
  offlineWrap: {
    position: "absolute", alignSelf: "center",
    ...V2Elev.float,
    backgroundColor: V2T.glassFaint, borderRadius: V2Radius.row, paddingHorizontal: 12, paddingVertical: 6,
  },
  offlineTxt: { fontSize: V2Type.label, color: V2T.text2 },
  pickHintWrap: {
    position: "absolute", alignSelf: "center",
    flexDirection: "row", alignItems: "center", gap: 6,
    ...V2Elev.float,
    backgroundColor: V2T.surface, borderRadius: V2Radius.row,
    paddingHorizontal: 12, paddingVertical: 7,
  },
  pickHintTxt: { fontSize: V2Type.label, color: V2T.text },
  freshWrap: { position: "absolute", left: 16 },
  peekWrap: { position: "absolute", left: 0, right: 0 },
});
