import React, { useCallback, useDeferredValue, useEffect, useMemo, useRef, useState } from "react";
import { BackHandler, Linking, LogBox, Pressable, Share, StyleSheet, Text, View, type NativeSyntheticEvent } from "react-native";
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
import * as Notifications from "expo-notifications";
import {
  Camera, Layer, Map, Marker, UserLocation,
  type CameraRef, type MapRef, type ViewStateChangeEvent,
} from "@maplibre/maplibre-react-native";
import { SafeAreaProvider, useSafeAreaInsets } from "react-native-safe-area-context";
import { V2Elev, V2Radius, V2T, V2Type, bandIdx, cigOf, fam } from "./src/theme";
import { DYNAMIC_TYPE } from "./src/a11y";
import { EndpointPin } from "./src/ui";
import { Icon } from "./src/icons";
import type { Place, Step, V2Option } from "./src/components/shell/types";
import {
  gestureLabelLayers, gestureLabelLayersLatin, latinLabels, v2StyleUrl,
} from "./src/map/style";
import { warmBasemap } from "./src/map/tileWarm";
import { warm as warmSearchIndex, localityAt } from "./src/search/t0";
import { afterFirstFrame, noteUserInput } from "./src/startup/idle";
import { camDur } from "./src/map/cam";
import {
  holdMapDraw, noteMapBusy, noteMapIdle, useHeldState, useMapDrawHeld,
  whenMapDrawFree,
} from "./src/map/drawHold";
import { ReportsLayer, reconcileReportSlots, REPORT_POOL, type ReportSlot } from "./src/components/ReportsLayer";
import { FreshnessChip } from "./src/components/FreshnessChip";
import { RouteTintSource } from "./src/components/RouteTint";
import { fieldSources, type FieldStatus } from "./src/api/plan";
import { FiresLayer, BlackspotsLayer } from "./src/components/HazardLayers";
import { CorridorLayer } from "./src/components/CorridorLayer";
import { AirFieldLayer, type AirStation } from "./src/components/AirFieldLayer";
import { AirMapCard } from "./src/components/AirMapCard";
import { TapPin, TapReadout, type TapRead } from "./src/components/TapReadout";
import { fetchAirField, airFieldEpoch, sampleFieldAt } from "./src/api/airfield";
import { SearchBar } from "./src/components/shell/SearchBar";
import { SearchScreen, type SearchSelection } from "./src/screens/SearchScreen";
import { VehicleSheet } from "./src/screens/VehicleSheet";
import { DelhiToday } from "./src/screens/DelhiToday";
import { SettingsScreen } from "./src/screens/SettingsScreen";
import { LedgerScreen } from "./src/screens/LedgerScreen";
import { OnboardingScreen, type SharingChoice } from "./src/screens/OnboardingScreen";
import { loadWelcomeSeen, markWelcomeSeen } from "./src/store/welcome";
import { HomeScreen, DayPeek, useDayData, type AmbientMeta } from "./src/screens/HomeScreen";
import { recordSample, setCheckin } from "./src/store/daylog";
import { loadConsent, saveConsent } from "./src/store/consent";
import { loadTourSeen, markTourSeen } from "./src/store/tour";
import { CoachTour } from "./src/components/shell/CoachTour";
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
import { API, DELHI, fetchJson, inNcr, posNow, reverseName } from "./src/components/shell/net";
import {
  DEFAULT_SETTINGS, PROFILE_BUDGET_UG, clearAllData, loadSettings, saveSettings, type SavedPlace, type ShellSettings,
} from "./src/components/shell/settings";
import { loadTrips, type Trip } from "./src/store/ledger";
import { checkAirEvents, resetEventsStore } from "./src/store/events";
import { cancelDailyBrief } from "./src/notify";
import { getVehicle, type VehicleClass, type VehicleProfile } from "./src/store/vehicle";
import { approx, doseUgRound, modeLabel, placeNameLabel, t, type Lang } from "./src/i18n/strings";
import { tap, tick } from "./src/haptics";
import { PERF_ON, bump, jank, mark, report } from "./src/perf";

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
/* z12.5 so the first frame lands inside the street-mesh regime — the
   basemap's minor roads + locality labels exist from z12 up; opening at
   z11 showed only arterials (the "empty map" complaint, r6). */
const INIT_VIEW = { center: DELHI, zoom: 12.5 } as const;
/* maxBounds = the dose field's service margin (NCR ±2°), not the
   tight NCR box — a destination in Agra/Jaipur must stay on
   screen or the outside-area notice can't be understood */
const MAX_BOUNDS: [number, number, number, number] = [74.75, 26.15, 79.95, 30.98];
/* top-of-map clearance for pills that used to sit under the route bar —
   the AirMapCard owns that slot on the air-map surface now */
const AIR_CARD_CLEARANCE = 76;
/* event payload types derived from the components' own prop signatures —
   never hand-name maplibre event types */
type MapPressEvent = Parameters<NonNullable<React.ComponentProps<typeof Map>["onPress"]>>[0];
type TrackChangeEvent = Parameters<NonNullable<React.ComponentProps<typeof Camera>["onTrackUserLocationChange"]>>[0];

/* hoisted map render-activity hooks (stable identity for the memo) —
   drawHold's cold-boot watch reads the render thread's busy/idle
   through these: a mount commit inside the first tile stream is the
   residual SIGSEGV (drawHold.ts boot-watch comment). */
/** the share text — clauses compose, so a missing estimate never prints
    a bare "—" inside the sentence; nothing to say → the app's own line */
function shareTripMsg(
  lang: Lang, from: string, to: string,
  dose: string | null, co2: string | null,
): string {
  const what = [
    dose != null ? t("shareClauseBreathe", lang, { dose }) : null,
    co2 != null ? t("shareClausePutOut", lang, { co2 }) : null,
  ].filter((x): x is string => x != null).join(" · ");
  return what ? t("shareTripLine", lang, { from, to, what }) : t("shareAppBody", lang);
}

const onMapBusy = () => noteMapBusy();
const onMapIdle = () => { noteMapIdle(); if (PERF_ON) mark("map.rendered"); };

/* the basemap's symbol set — mounted as React layers (not inside the
   style object — src/map/style.ts explains why) so their visibility
   flips while the user drags and returns on rest. Memo'd: every
   Layer's reactStyle diff reaches the native style, so this subtree
   must re-render only on a real gesture/lang flip, never on a poll.
   beforeId seats the block under the place labels, exactly where the
   bundled JSON held them — collision priority is preserved. */
const BasemapLabels = React.memo(function BasemapLabels({
  lang, gesturing,
}: {
  lang: Lang;
  gesturing: boolean;
}) {
  const specs = lang === "hi" ? gestureLabelLayers : gestureLabelLayersLatin;
  /* perf: visibility flips stamp marks so the perf log carries the
     gesture→hide / rest→restore windows around the label drop. */
  useEffect(() => { mark(gesturing ? "labels.hide" : "labels.show"); }, [gesturing]);
  return (
    <>
      {specs.map((spec) => (
        <Layer key={spec.id} {...spec} beforeId="v2-place-neighbourhood"
          layout={{
            ...(spec as { layout?: Record<string, unknown> }).layout,
            visibility: gesturing ? "none" : "visible",
          }} />
      ))}
    </>
  );
});
/* first fully-rendered frame → kick the one-time NCR tile prefetch in the
   background (deduped inside warmBasemap; fires every full render but
   only runs once per launch and once per install). */
const onMapFullyRendered = () => { onMapIdle(); warmBasemap(STYLE_URL); };

/* The whole native map subtree behind one memo boundary: every app-level
   poll (reports 60 s, aqi 60 s, health 15 s, ambient samples) used to
   re-diff the Map + Camera + layers + markers per render. All props are
   stable identities, so unrelated app state no longer touches it. */
const MapTree = React.memo(function MapTree({
  lang, compassPosition, logoPosition, attributionPosition,
  onPress, onLongPress, onPuckPress, camRef, mapRef, drawHeld, covered,
  trackUserLocation, onTrackUserLocationChange,
  hasLoc, corridors, reportSlots, fires, spots, layers,
  field, stations,
  options, selected, strips,
  fromPin, toPin, fromSet, toSet, pinReady,
  tapPin, tapShow, tapLabel, tapBand,
}: {
  lang: Lang;
  compassPosition: { top: number; right: number };
  logoPosition: { bottom: number; left: number };
  attributionPosition: { bottom: number; right: number };
  onPress: (e: MapPressEvent) => void;
  onLongPress: (e: MapPressEvent) => void;
  /* puck tap — the native "You Are Here" a11y label read as a button
     with no action (walk F6): wired to the recenter path in App */
  onPuckPress: () => void;
  camRef: React.RefObject<CameraRef | null>;
  /* Map imperative handle — the native attribution ⓘ button's own
     dialog is JS-callable through showAttribution() (F6 fallback) */
  mapRef: React.RefObject<MapRef | null>;
  trackUserLocation: "default" | undefined;
  onTrackUserLocationChange: (e: TrackChangeEvent) => void;
  hasLoc: boolean;
  corridors: React.ComponentProps<typeof CorridorLayer>["corridors"];
  reportSlots: (ReportSlot | null)[];
  fires: GeoJSON.FeatureCollection | null;
  spots: GeoJSON.FeatureCollection | null;
  layers: Record<LayerKey, boolean>;
  field: GeoJSON.FeatureCollection | null;
  stations: AirStation[] | null;
  options: V2Option[];
  selected: number;
  strips: Parameters<typeof RouteTintSource>[0]["strips"];
  fromPin: [number, number];
  toPin: [number, number];
  fromSet: boolean;
  toSet: boolean;
  pinReady: boolean;
  /* the air map's tap read pin — parked like the endpoint markers:
     always mounted at its last coordinate, hidden by an empty child.
     tapShow/tapLabel/tapBand re-render the marker in place. */
  tapPin: [number, number];
  tapShow: boolean;
  tapLabel: string;
  tapBand: number | null;
  drawHeld: boolean;
  covered: boolean;
}) {
  bump("app.MapTree");
  /* gesture label-drop: hide the basemap symbol set + the field's
     value/station labels while the user drags, pinch-zooms or pitches
     — the label collision pass is the map's dominant per-frame cost
     during camera motion, and every name returns on rest (what Google
     Maps does). onRegionWillChange fires once per camera change with
     userInteraction true only for real finger work — programmatic
     flyTo/track keep their labels, and onRegionIsChanging stays
     unwired so a gesture costs 2 bridge events, not a per-frame
     stream. A 4.5 s backstop restores labels if the idle event is
     lost (app backgrounded mid-drag). */
  const [gesturing, setGesturing] = useState(false);
  const gestureEndRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const onRegionWillChange = useCallback(
    (e: NativeSyntheticEvent<ViewStateChangeEvent>) => {
      if (!e.nativeEvent?.userInteraction) return;
      mark("gest.will");
      setGesturing(true);
      if (gestureEndRef.current) clearTimeout(gestureEndRef.current);
      gestureEndRef.current = setTimeout(() => setGesturing(false), 4500);
    }, []);
  const onRegionDidChange = useCallback(() => {
    mark("gest.did");
    setGesturing(false);
    if (gestureEndRef.current) {
      clearTimeout(gestureEndRef.current);
      gestureEndRef.current = null;
    }
  }, []);
  return (
    <Map ref={mapRef} mapStyle={lang === "hi" ? STYLE_URL : STYLE_EN} style={StyleSheet.absoluteFill}
      /* mount-vs-draw hold (src/map/drawHold.ts): while an overlay
         mounts/unmounts over the map the render pump drops to 2 fps so
         the commit can't intersect a wall of in-flight draws — the
         sim-only SIGSEGV class. `covered` is the hardware steady-state
         counterpart: while an opaque sheet owns the screen the map
         still renders into a void, so its pump caps low (8 fps keeps
         tile warmup + offline progress moving) and scroll/sheet anims
         keep the GPU/CPU. -1 restores the MapLibre default. */
      preferredFramesPerSecond={drawHeld ? 2 : covered ? 8 : -1}
      onRegionWillChange={onRegionWillChange}
      onRegionDidChange={onRegionDidChange}
      /* PERF-gated milestones in the cold-open path: style load is the
         bundled-light parse, rendered-full is first frame incl. tiles
         (hosted OpenFreeMap = network; bundled pmtiles = local) */
      {...(PERF_ON ? {
        onDidFinishLoadingStyle: () => mark("map.style"),
      } : {})}
      /* boot-watch feeds: willStartRenderingMap marks the pump busy
         (tiles streaming / render pass in flight), didFinishRendering-
         MapFully + didFinishLoadingMap mark it idle */
      onWillStartRenderingMap={onMapBusy}
      onDidFinishRenderingMapFully={onMapFullyRendered}
      onDidFinishLoadingMap={onMapIdle}
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
      {hasLoc && <UserLocation animated accuracy onPress={onPuckPress} />}
      {/* all map children stay mounted for the app's life — a mid-draw
          removeSource/removeAnnotation is the upstream sim SIGSEGV;
          the toggles only swap data in and out (see each component) */}
      {/* the air map's own surface — the served PM2.5 field, painted
          under the road/label stack; the band colours + every number
          are the field's real reads, and the rings are the actual
          instrument sites the blend is anchored to */}
      <AirFieldLayer field={field} stations={stations} gesturing={gesturing} />
      <BasemapLabels lang={lang} gesturing={gesturing} />
      <CorridorLayer corridors={corridors} on={layers.corridors} />
      <ReportsLayer slots={reportSlots} />
      <FiresLayer fires={fires} on={layers.fires} />
      <BlackspotsLayer spots={spots} on={layers.spots} />
      {/* route-wise AQI gradient on the real /v2/plan polylines — per
          ~250 m chunk from the fetched strips, flat dose-mean until they
          land; selected 6 px on 9 px casing, alternates 3 px at 50 %.
          (<RouteTintSource/> — src/components/RouteTint.tsx contract) */}
      <RouteTintSource options={options} selected={selected} strips={strips} lang={lang}
        from={fromSet ? fromPin : null} to={toSet ? toPin : null} />
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
      {/* the tap read's own mark — a band-washed µg chip + dot where the
          finger landed; hidden is an empty child, same parked contract
          as the endpoint pins above */}
      <Marker lngLat={tapPin} anchor="bottom">
        {tapShow ? <TapPin label={tapLabel} band={tapBand} /> : <View />}
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
  /* the Map's imperative handle — the native "About this map" ⓘ button
     drives showAttribution() itself; the JS copy stays for the dead-tap
     fallback (walk F6, decided on-device) */
  const mapRef = useRef<MapRef>(null);
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
    options, selected, setSelected, depart, notified, pingDenied, pingQuiet, trips, setTrips, recordTrip,
    community, setCommunity, follow, setFollow, loadingRoute, refining,
    planError, planDegraded, retryPlan, planField, departCurve,
    vehicle, setVehicleProfile, needsVehicle, steps, stepsOpen, setStepsOpen,
    pick, clearRoute, startNav, exitNav, remind, disarmDepart, armDailyBrief, armAirEvents,
    strips, reloadTrips, locNotice, setLocNotice,
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

  /* the air map's tap read — where the finger last landed on the field
     surface. tapPoint is the question; the painted cells answer it
     locally (sampleFieldAt over fieldGeo — the same serve the tint
     draws from, so tap and colour can never disagree), and a point no
     cell reaches falls back to ONE /aqi read carried as the model's
     own. Held state: the marker child swap is a map-side commit.
     Cleared when the surface isn't up so a stale pin never rides a
     fresh open. */
  const [tapPoint, setTapPoint] = useHeldState<{ lat: number; lon: number } | null>(null);
  /* parked marker coordinate — same contract as fromPin/toPin: holds
     the last real position, the child alone decides visibility */
  const [tapPin, setTapPin] = useState<[number, number]>(DELHI);
  useEffect(() => {
    if (!tapPoint) return;
    const c: [number, number] = [tapPoint.lon, tapPoint.lat];
    const t = setTimeout(() => setTapPin(c), 0);
    return () => clearTimeout(t);
  }, [tapPoint]);
  /* the edge fallback — one /aqi read for a tap no painted cell covers
     (a dropped-cell hole or past the grid's edge), keyed to the point
     and the field's own epoch so a fresh serve re-asks honestly */
  const [tapFallback, setTapFallback] = useState<{ key: string; pm25: number | null } | null>(null);

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
  const [locDenied, setLocDenied] = useState(false);
  /* the pick flow's notice lives in locNotice — rendered inside the
     search sheet there. On the idle map it used to be invisible, so a
     rejected/stalled map pick read as a silent dead tap (walk F3). A
     held mirror floats the same line as a pill (draw-hold discipline);
     tap dismisses. */
  const [mapPickNote, setMapPickNote] = useHeldState<string | null>(null);
  useEffect(() => { setMapPickNote(locNotice); }, [locNotice, setMapPickNote]);
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
  /* the served PM2.5 field itself — the air map's painted surface.
     Held in state keyed by the field's own epoch so a 60 s poll tick
     never re-diffuses an identical serve into the native map */
  const [fieldGeo, setFieldGeo] = useState<GeoJSON.FeatureCollection | null>(null);
  /* the day's ambient read — feeds the peek card's "now ~N µg/m³" so the
     idle map feels the air, not just the sampled totals */
  const [ambientUg, setAmbientUg] = useState<number | null>(null);
  /* km to the nearest real instrument reading behind the field at the
     user's cell — the "how accurate at my home" answer, surfaced once
     in settings' numbers explainer (null when the field is model-only) */
  const [nearestKm, setNearestKm] = useState<number | null>(null);
  /* the ambient read's provenance — where it was read (the user's own
     GPS or the Delhi-centre fallback), how far the nearest real
     instrument sat, its AQI equivalent, and whether the point is past
     the field's edge. The home hero's honesty lines render from this
     (home-truth: a number you can't verify reads as a wrong number). */
  const [ambientMeta, setAmbientMeta] = useState<AmbientMeta | null>(null);
  const [introSeen, setIntroSeen] = useHeldState<boolean | null>(null);
  /* coach_tour_seen_v1 — the first-run spotlight walk. Mounts once
     after onboarding while the live home keeps painting under it;
     a null stays null until its file read lands (no tour flashes on a
     repeat launch between consent load and tour load). */
  const [tourSeen, setTourSeen] = useHeldState<boolean | null>(null);
  /* welcome_seen_v1 — the first-breath cinematic is retired (owner:
     "slop I never asked for"); the flag file still writes once per
     install below so its lifecycle stays consistent. */
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
       "can't reach the server" strip — require two consecutive misses.
       The ping MUST be bounded: a bare fetch on a blackholed route never
       resolves, so a stall-type dead net produced zero *completed* misses
       and apiOk could never fail honestly (offline-verify catalogue).
       fetchJson's 8 s abort keeps detection inside the 15 s cadence. */
    let misses = 0;
    const ping = () => fetchJson(`${API}/health`, 8000)
      .then(() => { misses = 0; setApiOk(true); })
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
    /* the air map's surface rides the same warm-at-boot path as /aqi —
       fetched before the door to it is ever tapped, so opening the air
       map never waits on the network. 10 min < the field's own ~15 min
       cadence; a repeated serve with the same epoch is skipped (the
       GeoJSON identity the map memo depends on stays put). */
    const fieldPull = () => fetchAirField().then((r) => {
      if (r.ok && r.data.fc.features.length) {
        const ep = airFieldEpoch(r.data.fc);
        setFieldGeo((prev) => (prev && airFieldEpoch(prev) === ep ? prev : r.data.fc));
        return true;
      }
      return false;
    }).catch(() => false);
    /* boot resilience: one dropped read used to leave the air map bare
       for the full 10 min cadence — the idle map's whole surface. Retry
       a first-miss twice at short gaps before settling into the normal
       pull (the air map is the owner's #1 surface; it must not open
       empty on a flaky first fetch). */
    let fieldBoot = 0;
    let fieldT: ReturnType<typeof setTimeout> | null = null;
    const fieldBootRetry = async () => {
      if (await fieldPull()) return;
      if (++fieldBoot >= 3) return;           // three tries, then the 10-min cadence
      fieldT = setTimeout(fieldBootRetry, 7000);
    };
    void fieldBootRetry();
    const fieldIv = setInterval(fieldPull, 10 * 60 * 1000);
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
        /* same-fix dedupe: a fresh {lat,lon} object every poll would
           re-render the tree for nothing */
        if (pos) setUserPos((p) => (p && p.lat === lat && p.lon === lon ? p : { lat, lon }));
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
          /* nearest live INSTRUMENT — the caption's 'live monitor' is
             literal, so only nearest_station_km may feed it (a model
             fill point is never a monitor). Present-but-null stays null
             honestly; the fallback to nearest_sample_km exists only for
             a pre-update server that doesn't serve the key at all. */
          const nk = j != null && "nearest_station_km" in j
            ? (typeof j.nearest_station_km === "number" && isFinite(j.nearest_station_km)
                ? j.nearest_station_km : null)
            : (typeof j?.nearest_sample_km === "number" && isFinite(j.nearest_sample_km)
                ? j.nearest_sample_km : null);
          setNearestKm((prev) => (prev === nk ? prev : nk));
          const ua = typeof j?.us_aqi === "number" && isFinite(j.us_aqi)
            ? j.us_aqi : null;
          /* WHERE the read is for — the gazetteer locality at the user's
             own fix ('Karol Bagh'), null when t0 can't name it honestly.
             Only at a real fix: the centroid fallback never names a
             locality it didn't query for. */
          const pl = pos != null ? localityAt({ lat, lon }) : null;
          setAmbientMeta((prev) => {
            const nx: AmbientMeta = {
              km: nk, atGps: pos != null, usAqi: ua,
              beyondEdge: j?.beyond_field_edge === true, place: pl,
            };
            return prev != null && prev.km === nx.km && prev.atGps === nx.atGps
              && prev.usAqi === nx.usAqi && prev.beyondEdge === nx.beyondEdge
              && prev.place === nx.place
              ? prev : nx;
          });
          /* same value → no re-render — the 60 s poll usually repeats
             the same ambient sample until the field ticks */
          setAmbientUg((prev) => (prev === amb ? prev : amb));
          if (amb != null || bz != null) {
            /* only re-render the dosimeter surfaces when a sample actually
               lands — the dedupe drops most 60 s polls (~8 min cadence) */
            if (await recordSample({ ts: Date.now(), lat, lon, amb: amb ?? bz!, bz })) {
              /* perf-probe: the dose surface re-assembles on this bump —
                 frames during the re-assemble are the reload-flash test */
              jank("dose.tick", 1200); mark("dose.tick");
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
    loadTourSeen().then(setTourSeen).catch(() => setTourSeen(false));
    /* the welcome film is gone — the flag still lands once per install
       so the file's semantics (welcome_seen_v1.json exists ⇔ this
       install ran its first-open flow) hold for anything reading it */
    loadWelcomeSeen()
      .then((seen) => { if (!seen) void markWelcomeSeen(); })
      .catch(() => {});
    /* search gazetteer: slice-build the 124k-entry index in the
       background once the first frame has painted — by the time a
       search door is tapped the index is already a Map, so the sheet
       opens in ms instead of freezing on a multi-second sync build
       inside its mount effect (the owner's "10 seconds, hung" read).
       The 900 ms delay keeps the slices behind the boot burst. */
    void afterFirstFrame().then(() => setTimeout(() => warmSearchIndex(), 900));
    return () => { clearInterval(iv); clearInterval(healthIv); clearInterval(aqiIv); clearInterval(fieldIv); if (fieldT) clearTimeout(fieldT); };
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
  /* whether the OS location ask may fire when introSeen flips — true on
     the returning-user boot path (consent is already on disk); the
     onboarding permission page's "not now" writes false so declining
     there stays a real decline */
  const [locAskOk, setLocAskOk] = useState(true);
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
    if (introSeen !== true || didAskLoc.current || !locAskOk) return;
    didAskLoc.current = true;
    let cancelled = false;
    void (async () => {
      const r = await Location.requestForegroundPermissionsAsync().catch(() => null);
      if (cancelled) return;
      setHasLoc(!!r?.granted);
      const pos = await posNow();
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
  }, [introSeen, locAskOk, setFrom, settings.lang]);

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

  /* notification taps — before this a ping answered with a dead open on
     whatever surface was last up (lifecycle-drive): air events land on
     the air map (the field the ping is about), the daily brief and the
     departure ping land on Delhi today (the window both narrate).
     getLastNotificationResponseAsync covers the killed-app tap. */
  useEffect(() => {
    const route = (resp: Notifications.NotificationResponse | null) => {
      const id = resp?.notification?.request?.identifier ?? "";
      if (!id) return;
      if (id.startsWith("air-event-")) { setHomeOpen(false); return; }
      if (id === "alive-daily-brief" || id === "alive-departure") {
        setHomeOpen(false);
        setDelhiOpen(true);
      }
    };
    const sub = Notifications.addNotificationResponseReceivedListener(route);
    Notifications.getLastNotificationResponseAsync()
      .then(route)
      .catch(() => {});
    return () => sub.remove();
  }, []);

  const patchSettings = useCallback((p: Partial<ShellSettings>) => {
    setSettings((s) => { const n = { ...s, ...p }; saveSettings(n); return n; });
    // the consent record mirrors the share toggle — it is the canonical
    // donation answer (nav engine + trip submit read it)
    if ("share" in p) {
      saveConsent({ sharing: p.share ? "on" : "off", ts: Date.now() }).catch(() => {});
    }
    /* toggles must reach the OS too — a scheduled ping survives the
       persisted flag, so "off" without the cancel still pings tomorrow */
    if (p.remind === false) disarmDepart();
    if (p.brief === false) void cancelDailyBrief();
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
      /* pending OS pings carry the wiped trip/brief — delete-my-data
         must disarm them, not just the files */
      disarmDepart(); void cancelDailyBrief();
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
  /* the served field block is verbatim-identical between rebuilds — the
     aqiField dedupe holds, this memo never re-runs, and 'air reading:
     N min old' freezes mid-count while wall-clock moves (android-verify
     bug #1; it only LOOKED alive when a fresh field landed). A 30 s tick
     re-derives the age on wall-clock and lets `stale` cross
     stale_after_s on a dead network. */
  const [ageTick, setAgeTick] = useState(0);
  useEffect(() => {
    const iv = setInterval(() => setAgeTick((n) => n + 1), 30000);
    return () => clearInterval(iv);
  }, []);
  const mapField: FieldStatus | null = useMemo(() => planField ?? (aqiField
    ? { ...aqiField.data,
        age_s: aqiField.data.age_s == null
          ? null
          : aqiField.data.age_s + (Date.now() - aqiField.at) / 1000,
        stale: aqiField.data.stale === true ? true
          : aqiField.data.age_s == null ? aqiField.data.stale ?? null
          : (aqiField.data.age_s + (Date.now() - aqiField.at) / 1000)
            > (aqiField.data.stale_after_s ?? 2700) }
    : null), [planField, aqiField, ageTick]);

  /* the field block re-issues every 60 s poll (age_s ticks, so the JSON
     dedupe never holds it) — but the stations list itself only moves
     when the feed actually changes. Memoize by content so MapTree's
     boundary stays honest: same array content, same identity. */
  const stationsJson = aqiField?.data?.stations ? JSON.stringify(aqiField.data.stations) : null;
  const fieldStations = useMemo(
    () => (stationsJson ? (JSON.parse(stationsJson) as AirStation[]) : null),
    [stationsJson]);

  /* the tap read resolved: the painted cell's own value first — local,
     instant, offline-safe; the /aqi edge fallback second; "pending"
     while it answers, "outside" when nothing honest does. fieldGeo in
     the deps is the live part: a re-pulled field re-samples the same
     point and the readout moves with it, no second tap needed. */
  const tapKey = tapPoint
    ? `${tapPoint.lat.toFixed(4)},${tapPoint.lon.toFixed(4)}` : null;
  const tapLocality = useMemo(
    () => (tapPoint ? localityAt(tapPoint) : null), [tapPoint]);
  const tapSample = useMemo(
    () => sampleFieldAt(fieldGeo, tapPoint?.lat ?? NaN, tapPoint?.lon ?? NaN),
    [fieldGeo, tapPoint]);
  const tapRead = useMemo((): TapRead | "pending" | "outside" | null => {
    if (!tapPoint) return null;
    if (tapSample) {
      return { pm25: tapSample.pm25, band: bandIdx(tapSample.pm25) ?? 0,
        conf: tapSample.conf };
    }
    /* a stale-keyed fallback is ignored, not cleared — the memo just
       reads "pending" until the fresh fetch lands */
    if (tapFallback && tapKey && tapFallback.key.startsWith(tapKey)) {
      if (tapFallback.pm25 == null) return "outside";
      return { pm25: tapFallback.pm25, band: bandIdx(tapFallback.pm25) ?? 0,
        conf: "model" };
    }
    return "pending";
  }, [tapPoint, tapSample, tapFallback, tapKey]);
  /* one /aqi read for a tap no painted cell covers (a dropped-cell hole
     or past the grid's edge). The field's epoch rides the key — a new
     serve re-asks the edge answer instead of holding a stale model
     read under a field that may now reach the point. */
  useEffect(() => {
    if (!tapPoint || tapSample || !tapKey) return;
    let cancelled = false;
    const key = `${tapKey}@${fieldGeo ? airFieldEpoch(fieldGeo) ?? "x" : "x"}`;
    fetchJson(`${API}/aqi?lat=${tapPoint.lat}&lon=${tapPoint.lon}`, 8000)
      .then((j) => {
        if (cancelled) return;
        /* ambient first — the cells paint the ambient surface, so the
           fallback speaks the same value the readout compares against */
        const amb =
          typeof j?.pm25_ambient === "number" && Number.isFinite(j.pm25_ambient)
            ? j.pm25_ambient
            : typeof j?.pm25 === "number" && Number.isFinite(j.pm25)
              ? j.pm25 : null;
        setTapFallback({ key, pm25: amb });
      })
      .catch(() => { if (!cancelled) setTapFallback({ key, pm25: null }); });
    return () => { cancelled = true; };
  }, [tapPoint, tapSample, tapKey, fieldGeo]);
  /* the read belongs to the air-map surface — leaving it (home, a
     journey phase, the armed pick) clears the pin so the next open
     starts clean */
  useEffect(() => {
    if (phase === "idle" && !homeOpen) return;
    setTapPoint(null);
  }, [phase, homeOpen, setTapPoint]);

  /* the air map IS this surface — the map under the home sheet is
     browsing, this is the reading */
  const airMapOpen = phase === "idle" && !homeOpen;

  /* the home sheet is a full opaque surface — the same predicate as its
     `visible` prop. While it owns the screen the map renders into a
     void: cap the render pump low so home scroll + sheet springs keep
     the GPU/CPU (the hardware counterpart of the sim's drawHold —
     restored to full rate the frame the sheet starts to lift). */
  const mapCovered = homeOpen && phase === "idle" && !mapPickArmed;

  /* ---- memo'd subtree props: every handler below must keep identity
     across poll renders or the memo boundaries are theatre ---- */
  const compassPosition = useMemo(() => (phase === "nav"
    ? { top: insets.top + 108, right: 12 }
    : { top: insets.top + 76, right: 12 }), [phase, insets.top]);
  const logoPosition = useMemo(() => ({ bottom: insets.bottom + 164, left: 10 }), [insets.bottom]);
  /* the DayPeek card owns the whole strip at bottom+72 (~85 pt tall) —
     the OSM attribution used to sit at the same offset, drowned under
     it and untappable (audit #6). It now floats just above the card;
     when the peek isn't mounted it just reads slightly higher. */
  const attributionPosition = useMemo(() => ({ bottom: insets.bottom + 164, right: 16 }), [insets.bottom]);
  /* search bias is the REAL GPS fix — never 'from', which used to feed
     the bias a fabricated 'central Delhi' fallback and rank results for
     a place the user wasn't in (owner: 'live location ain't working').
     'from' only fills in when no real fix exists yet. */
  const searchUserLoc = useMemo(
    () => (userPos ? { lat: userPos.lat, lon: userPos.lon }
      : from ? { lat: from.lat, lon: from.lon } : null),
    [userPos, from],
  );

  const onMapPress = useCallback(async (f: MapPressEvent) => {
    const c = (f as { nativeEvent?: { lngLat?: [number, number] } }).nativeEvent?.lngLat;
    if (!c) return;
    if (!mapPickArmed) {
      /* the air map's own tap: read the field right where the finger
         landed. Only on the open field surface — under home's sheet or
         inside a journey phase a bare map tap stays inert. The armed
         pick below is the committed gesture and always wins. */
      if (airMapOpen) {
        tap();
        setTapPoint({ lat: c[1], lon: c[0] });
      }
      return;
    }
    setMapPickArmed(false);
    tap();   // the pick landed — same weight as a row tap
    /* the confirm chain takes real seconds offline (reverse-name ≤6 s,
       then pick's origin fix ≤9 s): say the spot is being checked so
       the tap never dies in silence (walk F3). pick() and the slot
       path overwrite or clear it with the true outcome. */
    setLocNotice(t("mapPickChecking", lang));
    const rev = await reverseName(c[1], c[0]);
    if (placePickSlot) {
      // the unset home/work slot asked for this pick ("choose on map")
      setLocNotice(null);
      patchSettings({ [placePickSlot]: { name: rev.name, lat: c[1], lon: c[0] } });
      setPlacePickSlot(null);
      setSidebarOpen(true);
      return;
    }
    /* no explicit "to": the armed slot wins — with "Where from?" open a
       map tap must land in `from`, not silently re-target the
       destination (offline-verify catalogue #1) */
    pick({ name: rev.name, subtitle: rev.subtitle, lat: c[1], lon: c[0] });
  }, [mapPickArmed, placePickSlot, patchSettings, pick, airMapOpen, setTapPoint, setLocNotice, lang]);
  const onMapLongPress = useCallback(async (f: MapPressEvent) => {
    const c = (f as { nativeEvent?: { lngLat?: [number, number] } }).nativeEvent?.lngLat;
    if (!c) return;
    setLocNotice(t("mapPickChecking", lang));
    const rev = await reverseName(c[1], c[0]);
    pick({ name: rev.name, subtitle: rev.subtitle, lat: c[1], lon: c[0] });
  }, [pick, setLocNotice, lang]);
  const onTrackUserLocationChange = useCallback((e: TrackChangeEvent) => {
    if (!e.nativeEvent.trackUserLocation) setFollow(false);
  }, [setFollow]);

  /* the drawer is modal — opening it dismisses the layers sheet, which
     otherwise mounts later in JSX and floats ABOVE the open sidebar
     (testday-ios z-order wart). Mirrors onDelhiTodayOpen/onFullSettings
     closing the drawer beneath their own surface. */
  const openSidebar = useCallback(() => { mark("drawer.tap"); setLayersOpen(false); setSidebarOpen(true); }, []);
  const openSearch = useCallback(() => {
    mark("search.tap");
    setLocNotice(null);
    setEditWhich("to");
    setPhase("search");
  }, [setEditWhich, setPhase, setLocNotice]);
  const closeCompareToHome = useCallback(() => { setHomeOpen(true); clearRoute(); }, [clearRoute]);
  const onSearchClose = useCallback(() => {
    setLocNotice(null);
    if (placePickSlot) { setPlacePickSlot(null); setSidebarOpen(true); }
    setPhase(to ? "compare" : "idle");
  }, [placePickSlot, setPhase, setLocNotice, to]);
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
      /* again the armed slot, not a hardcoded "to" — a typed place pick
         while "Where from?" was armed used to drop into `to` */
      pick({ name: sel.place.name, subtitle: sel.place.subtitle ?? "",
        lat: sel.place.lat, lon: sel.place.lon });
      return;
    }
    if (sel.type === "choose_on_map") {
      setHomeOpen(false);        // the map surface itself
      setPhase("idle");
      setMapPickArmed(true);       // next map tap picks — for the slot
                                   // when placePickSlot is armed
      return;
    }
    const pos = await posNow();
    if (pos && placePickSlot) {
      patchSettings({ [placePickSlot]: { name: t("yourLocation", lang),
        lat: pos.coords.latitude, lon: pos.coords.longitude } });
      setPlacePickSlot(null);
      setPhase("idle");
      setSidebarOpen(true);
    } else if (pos) pick({ name: t("yourLocation", lang), subtitle: "",
      lat: pos.coords.latitude, lon: pos.coords.longitude }, editWhich);
    else {
      /* the failed fix used to close the sheet and show NOTHING (the
         'live location ain't working' silent no-op) — stay open and
         say it failed so typing a place keeps the flow moving. */
      setLocNotice(t("locPickFailed", lang));
      setPhase("search");
    }
  }, [placePickSlot, patchSettings, setPhase, pick, editWhich, lang, to, setLocNotice]);
  const onLocate = useCallback(() => {
    if (follow) { setFollow(false); return; }
    /* warm the fused provider before engaging follow — MapLibre's
       native layer posts a raw error toast when track starts with
       no fix yet (Android forensic find); a one-shot fix primes it */
    posNow()
      .then((pos) => {
        if (pos) { setLocDenied(false); setHasLoc(true); setFollow(true); }
        /* a denied/off location used to dead-tap — press the crosshair,
           nothing answers, no hint why (lifecycle-drive) */
        else setLocDenied(true);
      })
      .catch(() => setLocDenied(true));
  }, [follow, setFollow]);
  /* the puck's native a11y label is "You Are Here" — it read as a
     button with no action (walk F6). A tap recentres on the real fix
     and engages follow; no fix answers with the same honest pill the
     crosshair shows instead of dead silence. */
  const onPuckPress = useCallback(() => {
    posNow().then((pos) => {
      if (pos) {
        setLocDenied(false);
        setHasLoc(true);
        setFollow(true);
        whenMapDrawFree(() => camRef.current?.flyTo({
          center: [pos.coords.longitude, pos.coords.latitude],
          zoom: 15.5, duration: camDur(600),
        }));
      } else setLocDenied(true);
    }).catch(() => setLocDenied(true));
  }, [camRef, setFollow]);
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
  const onFullSettings = useCallback(() => { mark("settings.tap"); setSidebarOpen(false); setSettingsOpen(true); }, []);
  const onNavigate = useCallback((p: SavedPlace) => pick({ ...p, subtitle: "" }, "to"), [pick]);
  const onLangChange = useCallback((l: "en" | "hi") => patchSettings({ lang: l }), [patchSettings]);
  const onShare = useCallback(() => Share.share({ message: t("shareAppBody", lang) }).catch(() => {}), [lang]);
  const onShareTrip = useCallback((tr: Trip) => Share.share({
    message: shareTripMsg(lang, placeNameLabel(tr.from, lang), placeNameLabel(tr.to, lang),
      tr.dose_ug != null
        ? (settings.show_cig
            ? ((cigOf(tr.dose_ug) ?? 0) < 0.01
                ? t("cigsTrace", lang)
                : t("nav_cigs", lang, { n: Math.round((cigOf(tr.dose_ug) ?? 0) * 100) / 100 }))
            : t("doseUg", lang, { n: doseUgRound(tr.dose_ug) }))
        : null,
      tr.emit_kg != null ? t("share_co2", lang, { n: `~${tr.emit_kg.toFixed(1)}` }) : null),
  }).catch(() => {}), [lang, settings.show_cig]);
  const onLayersClose = useCallback(() => setLayersOpen(false), []);
  /* walk-F6 — the map's ⓘ ornament is native MapLibre chrome: it renders
     ~10px and half-clipped at the bezel, so the attribution it stands
     for was effectively unreachable (dead tap). showAttribution opens
     the very same native sheet; the Layers row is the reachable door. */
  const onAboutMap = useCallback(() => {
    setLayersOpen(false);
    mapRef.current?.showAttribution().catch(() => {});
  }, [setLayersOpen]);
  const onTapReadClose = useCallback(() => { tick(); setTapPoint(null); }, [setTapPoint]);
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
  const onOnboardDone = useCallback(({ sharing, askLocation }: { sharing: SharingChoice; askLocation: boolean }) => {
    patchSettings({ share: sharing === "on" });
    setLocAskOk(askLocation);
    setIntroSeen(true);
  }, [patchSettings]);

  /* stable for the tour's unmount detector — an inline lambda would churn
     its done-callback identity every App commit */
  const onTourDone = useCallback(() => setTourSeen(true), [setTourSeen]);

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
      onPuckPress={onPuckPress}
      camRef={camRef}
      mapRef={mapRef}
      trackUserLocation={follow ? "default" : undefined}
      onTrackUserLocationChange={onTrackUserLocationChange}
      hasLoc={hasLoc}
      corridors={community?.top_corridors ?? null}
      reportSlots={reportSlots}
      fires={fires} spots={spots} layers={layers}
      field={fieldGeo} stations={fieldStations}
      options={deferredOptions}
      selected={selected}
      strips={strips}
      fromPin={fromPin} toPin={toPin}
      fromSet={!!from} toSet={!!to}
      pinReady={pinReady}
      tapPin={tapPin}
      tapShow={tapPoint != null}
      tapLabel={tapRead != null && typeof tapRead === "object"
        ? String(Math.round(tapRead.pm25))
        : tapRead === "outside" ? "–" : "…"}
      tapBand={tapRead != null && typeof tapRead === "object" ? tapRead.band : null}
      drawHeld={drawHeld}
      covered={mapCovered} />
  );

  /* mount the map under the splash: the native style parse + tile fetch
     (hosted OpenFreeMap — nothing bundled) used to start only AFTER the
     ~220 ms font gate; now it overlaps it. Splash still covers the tree —
     nothing about the visible order changes. */
  /* onTouchStart on the root: marks every touch-down for the boot-idle
     schedulers (gazetteer warm, tile pack) so their slices yield to real
     input — one handler, zero render cost (src/startup/idle.ts). */
  if (!fontsLoaded)
    return <View style={s.root} onTouchStart={noteUserInput}>{mapTree}</View>;
  return (
    <View style={s.root} onTouchStart={noteUserInput}>
      <StatusBar style="dark" />
      {mapTree}

      {/* the from/to route component has no seat on the air map —
          owner's order ("REMOVE the 'from' component"): this surface is
          the field + the instruments' numbers, not a trip planner.
          The pill survives ONLY inside an active journey (compare)
          where it names the destination and closes the plan; every
          entry point to planning stays on the home sheet's own CTA. */}
      {phase === "compare" && (
        <View style={[s.pillWrap, { top: insets.top + 10 }]}>
          <SearchBar
            label={to ? to.name : undefined}
            lang={lang}
            onMenu={openSidebar}
            onPress={openSearch}
            onClear={closeCompareToHome} />
        </View>
      )}
      <SearchScreen
        visible={phase === "search"}
        lang={lang}
        userLocation={searchUserLoc}
        mode={editWhich}
        notice={locNotice}
        onClose={onSearchClose}
        onSelect={onSearchSelect} />
      {phase === "idle" && (
        <>
          {/* the air map's legend — floats in the slot the route pill
              used to own, tap-through so the field under it still
              answers the pan */}
          {!homeOpen && (
            <View style={[s.airCardWrap, { top: insets.top + 10 }]} pointerEvents="none">
              <AirMapCard lang={lang}
                stations={fieldStations?.length ?? null}
                fieldAgeS={mapField?.age_s ?? null}
                stale={mapField?.stale}
                hasField={!!fieldGeo?.features?.length} />
            </View>
          )}
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
          {/* the tap read — the point's own answer floats just above the
              peek strip (its ✕ is the only touchable inside); before the
              first tap, a quiet hint says the field answers to a touch */}
          {!homeOpen && tapRead != null && (
            <View style={[s.tapReadWrap, { bottom: insets.bottom + 170 }]} pointerEvents="box-none">
              <TapReadout lang={lang} read={tapRead} place={tapLocality} onClose={onTapReadClose} />
            </View>
          )}
          {!homeOpen && tapRead == null && (
            <View style={[s.tapReadWrap, { bottom: insets.bottom + 170 }]} pointerEvents="none">
              <Text {...DYNAMIC_TYPE} numberOfLines={1}
                style={[s.tapHintTxt, { fontFamily: fam(lang, "reg") }]}>
                {t("tapHint", lang)}
              </Text>
            </View>
          )}
        </>
      )}
      {/* SEAM(breath-chip): optional "breathing heavier/lighter" chip while moving
          (doc 02 §S1) — needs a real trailing-30min baseline; not yet wired. */}

      {/* freshness chip — on the compare surface it still names the
          plan field's age; on the air map the same truth lives inside
          the AirMapCard now (no double-telling the field's age) */}
      {phase === "compare" && mapField && (
        <View style={[s.freshWrap, { top: insets.top + 62 }]} pointerEvents="box-none">
          <FreshnessChip
            ageS={mapField.age_s} stale={mapField.stale}
            sources={fieldSources(mapField)} lang={lang} compact />
        </View>
      )}
      {phase === "compare" && (
        <CompareSheet options={options} selected={selected} onSelect={setSelected}
          depart={depart} departCurve={departCurve} notified={notified}
          pingDenied={pingDenied} pingQuiet={pingQuiet}
          onRemind={remind} remindEnabled={settings.remind}
          loading={loadingRoute} refining={refining}
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
          onExit={onNavExit} onHome={onPeekOpen}
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
        <Pressable style={[s.offlineWrap, { top: insets.top + 66 + (airMapOpen ? AIR_CARD_CLEARANCE : 0) }]} onPress={() => { tick(); void net.refresh(); }}
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
            top: insets.top + 66 + (airMapOpen ? AIR_CARD_CLEARANCE : 0)
              + ((net.state !== "online" || apiOk === false) ? 36 : 0),
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

      {/* map-pick notice on the open map — pending while the spot is
          being confirmed, the honest refusal if it can't be (offline
          pick used to die silent here, walk F3). Inside search the
          sheet's own notice slot carries the same locNotice. */}
      {phase === "idle" && !mapPickArmed && mapPickNote && (
        <Pressable
          style={[s.pickHintWrap, {
            top: insets.top + 66 + (airMapOpen ? AIR_CARD_CLEARANCE : 0)
              + ((net.state !== "online" || apiOk === false) ? 36 : 0),
          }]}
          onPress={() => { tick(); setLocNotice(null); }}
          accessibilityRole="button" accessibilityLabel={mapPickNote}
        >
          <Icon name="pin" color={V2T.text2} size={14} />
          <Text {...DYNAMIC_TYPE} style={[s.pickHintTxt, { fontFamily: fam(lang, "med") }]}>
            {mapPickNote}
          </Text>
        </Pressable>
      )}

      {/* locate tapped with location off/denied — the crosshair used to
          answer with silence. Tap opens iOS Settings, where the switch
          actually lives; a later fix or a fresh grant clears it. */}
      {locDenied && !mapPickArmed && (
        <Pressable
          style={[s.pickHintWrap, {
            top: insets.top + 66 + (airMapOpen ? AIR_CARD_CLEARANCE : 0)
              + ((net.state !== "online" || apiOk === false) ? 36 : 0),
          }]}
          onPress={() => { tick(); setLocDenied(false); Linking.openSettings().catch(() => {}); }}
          accessibilityRole="button" accessibilityLabel={t("homeAirCityHint", lang)}
        >
          <Icon name="locate" color={V2T.text2} size={14} />
          <Text {...DYNAMIC_TYPE} style={[s.pickHintTxt, { fontFamily: fam(lang, "med") }]}>
            {t("homeAirCityHint", lang)}
          </Text>
        </Pressable>
      )}

      {/* the dosimeter home — resting surface; covers the idle map and
          yields for the journey phases (search/compare/nav) */}
      <HomeScreen
        visible={homeOpen && phase === "idle" && !mapPickArmed}
        data={dayData} lang={lang} settings={settings} ambientUg={ambientUg}
        ambientMeta={ambientMeta} fieldAgeS={mapField?.age_s} fieldStale={mapField?.stale}
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
        onClose={onLayersClose} onAbout={onAboutMap} lang={lang} />
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
        ambientUg={ambientUg} onDone={onOnboardDone} />
      {/* the first-run coach tour — mounts once after onboarding while
          the live home paints under it (scrim is touch-transparent; only
          the caption card takes presses). The predicate is deliberately
          THIN — introSeen && homeOpen: every gated sheet flag is a
          deferred useHeldState commit, and any one of them flapping for
          a single commit unmounts the tour for good (the seen-flag is
          already on disk at mount, so a transient kill never re-arms).
          Sheets that rise over it are brief — the card floats, taps
          still pass, and real nav-away (the map door, a trip) still
          dismisses through homeOpen. */}
      {tourSeen === false && introSeen === true && homeOpen && phase === "idle" && (
        <CoachTour lang={lang} onDone={onTourDone} />
      )}


    </View>
  );
}

/** Live-trip session: mounts the nav engine exactly for the nav phase —
 *  the hook owns the GNSS watcher + 1 Hz counters + off-route + strip;
 *  we only translate the plan option into its NavRoute and its summary
 *  into the receipt. (src/nav contract — see src/nav/index.ts) */
const NavSession = React.memo(function NavSession({
  option, options, from, to, steps, camRef, lang, share, voice, vehicle, showCig, onExit, onHome, onTripDone,
}: {
  option: V2Option; options: V2Option[]; from: Place | null; to: Place | null; steps: Step[] | null;
  camRef: React.RefObject<CameraRef | null>; lang: "en" | "hi";
  share: boolean; onExit: () => void;
  /* walk-F2 — Done opens the home door at PRESS time; waiting for the
     deferred teardown left a chromeless map for the whole hold window */
  onHome: () => void;
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
      /* sub-gap pauses don't earn a receipt line — the FIX_GAP_S
         floor (45 s) is where the meters admitted they couldn't see */
      pausedMin: summary.pausedS >= 45
        ? Math.max(1, Math.round(summary.pausedS / 60))
        : null,
    };
    return (
      /* Done tears down the whole nav session in one commit; deferring it
         past the sheet's close keeps the heavy unmount off the same frame
         as the press (iOS-sim render-thread race — same class as the
         deferred search focus/close fixes). The trip is OVER the moment
         Done lands — open the home door NOW instead of inside the
         deferred teardown, or the user sits on a chromeless map for the
         hold window (walk F2). onNavExit's own setHomeOpen stays
         idempotent. */
      <ReceiptSheet data={data} lang={lang} showCig={showCig}
        onDone={() => { onHome(); setTimeout(onExit, 280); }}
        onShare={() => Share.share({
          message: shareTripMsg(lang,
            from ? placeNameLabel(from.name, lang) : "?",
            to ? placeNameLabel(to.name, lang) : "?",
            summary.doseUg.mid != null
              ? (showCig
                  ? ((cigOf(summary.doseUg.mid) ?? 0) < 0.01
                      ? t("cigsTrace", lang)
                      : t("nav_cigs", lang, { n: Math.round((cigOf(summary.doseUg.mid) ?? 0) * 100) / 100 }))
                  : t("doseUg", lang, { n: doseUgRound(summary.doseUg.mid) }))
              : null,
            summary.co2Kg.mid != null ? `${t("nav_kg", lang, { n: `~${summary.co2Kg.mid.toFixed(1)}` })} CO₂` : null),
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
  /* the air map's legend — narrow, left-anchored, tap-through */
  airCardWrap: { position: "absolute", left: 16, right: 96, alignItems: "flex-start" },
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
  /* the tap read + its pre-tap hint ride one centred slot just above
     the peek strip (~90 pt tall from bottom+72) */
  tapReadWrap: { position: "absolute", left: 0, right: 0, alignItems: "center" },
  tapHintTxt: {
    fontSize: V2Type.micro, color: V2T.text3,
    backgroundColor: V2T.glassFaint, borderRadius: V2Radius.row,
    borderWidth: StyleSheet.hairlineWidth, borderColor: V2T.glassLine,
    paddingHorizontal: 10, paddingVertical: 5, overflow: "hidden",
  },
});
