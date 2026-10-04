import React, { useCallback, useDeferredValue, useEffect, useRef, useState } from "react";
import { BackHandler, LogBox, Pressable, Share, StyleSheet, Text, View } from "react-native";
import { StatusBar } from "expo-status-bar";
import * as SplashScreen from "expo-splash-screen";
import { useFonts, Inter_400Regular, Inter_500Medium, Inter_600SemiBold } from "@expo-google-fonts/inter";
import {
  NotoSansDevanagari_400Regular, NotoSansDevanagari_500Medium, NotoSansDevanagari_600SemiBold,
} from "@expo-google-fonts/noto-sans-devanagari";
import * as Location from "expo-location";
import {
  Camera, Map, Marker, UserLocation, type CameraRef,
} from "@maplibre/maplibre-react-native";
import { SafeAreaProvider, useSafeAreaInsets } from "react-native-safe-area-context";
import { V2Radius, V2T, V2Type, cigOf, fam } from "./src/theme";
import { DYNAMIC_TYPE } from "./src/a11y";
import { EndpointPin } from "./src/ui";
import { Icon } from "./src/icons";
import type { Place, Step, V2Option } from "./src/components/shell/types";
import { v2StyleUrl } from "./src/map/style";
import { ReportsLayer } from "./src/components/ReportsLayer";
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
import { OnboardingScreen } from "./src/screens/OnboardingScreen";
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
import { API, DELHI, fetchJson, reverseName } from "./src/components/shell/net";
import {
  DEFAULT_SETTINGS, clearAllData, loadSettings, saveSettings, type ShellSettings,
} from "./src/components/shell/settings";
import { loadTrips } from "./src/store/ledger";
import { getVehicle, type VehicleClass, type VehicleProfile } from "./src/store/vehicle";
import { modeLabel, placeNameLabel, t } from "./src/i18n/strings";
import { tap, tick } from "./src/haptics";

SplashScreen.preventAutoHideAsync().catch(() => {});

// Bundled light style — resolves local delhi.pmtiles / EXPO_PUBLIC_TILES_URL,
// else hosted OpenFreeMap vector tiles through the same light style object.
const STYLE_URL = v2StyleUrl();

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

export default function App() {
  return (
    <SafeAreaProvider>
      <AppInner />
    </SafeAreaProvider>
  );
}

function AppInner() {
  const camRef = useRef<CameraRef>(null);
  /* last real endpoint coords — the always-mounted markers park here when
     hidden (see the Marker block below) */
  const fromPin = useRef<[number, number]>(DELHI);
  const toPin = useRef<[number, number]>(DELHI);
  const insets = useSafeAreaInsets();
  const [settings, setSettings] = useState<ShellSettings>(DEFAULT_SETTINGS);
  const flow = useShellFlow(camRef, settings.share, settings.lang);
  if (flow.from) fromPin.current = [flow.from.lon, flow.from.lat];
  if (flow.to) toPin.current = [flow.to.lon, flow.to.lat];
  const { phase } = flow;
  // route-tint shape sources mount at lower priority — keeps the compare
  // sheet's entrance animation from sharing a frame with the chunk build
  const deferredOptions = useDeferredValue(flow.options);
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

  const [reports, setReports] = useState<GeoJSON.FeatureCollection | null>(null);
  const [fires, setFires] = useState<GeoJSON.FeatureCollection | null>(null);
  const [spots, setSpots] = useState<GeoJSON.FeatureCollection | null>(null);
  const [layers, setLayers] = useState<Record<LayerKey, boolean>>({ fires: false, spots: false, corridors: false });
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [layersOpen, setLayersOpen] = useState(false);
  const [mapPickArmed, setMapPickArmed] = useState(false);
  const [vehicleOpen, setVehicleOpen] = useState(false);
  const [delhiOpen, setDelhiOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [placePickSlot, setPlacePickSlot] = useState<"home" | "work" | null>(null);
  const [ledgerOpen, setLedgerOpen] = useState(false);
  const [hasLoc, setHasLoc] = useState(false);
  const [apiOk, setApiOk] = useState<boolean | null>(null);
  const [aqiField, setAqiField] = useState<FieldStatus | null>(null);
  const [introSeen, setIntroSeen] = useState<boolean | null>(null);
  const net = useNetStatus();

  const [fontsLoaded] = useFonts({
    Inter_400Regular, Inter_500Medium, Inter_600SemiBold,
    NotoSansDevanagari_400Regular, NotoSansDevanagari_500Medium, NotoSansDevanagari_600SemiBold,
  });
  useEffect(() => { if (fontsLoaded) SplashScreen.hideAsync().catch(() => {}); }, [fontsLoaded]);

  /* ---- boot: warm the API, load trips/settings, resolve location ---- */
  const { setFrom, setTrips } = flow;
  useEffect(() => {
    /* one flaky ping while a 25 s plan krige is in flight flashed a false
       "can't reach the server" strip — require two consecutive misses */
    let misses = 0;
    const ping = () => fetch(`${API}/health`, { keepalive: true })
      .then((r) => { misses = r.ok ? 0 : misses + 1; if (!misses) setApiOk(true); else if (misses >= 2) setApiOk(false); })
      .catch(() => { misses += 1; if (misses >= 2) setApiOk(false); });
    ping();
    const healthIv = setInterval(ping, 15000);
    const poll = () => fetchJson(`${API}/reports`).then(setReports).catch(() => {});
    poll();
    const iv = setInterval(poll, 60000);
    /* the map-screen freshness chip reads the served field's own status
       block — GET /aqi's `field` IS FIELD.status() verbatim (same keys
       the /v2/plan `field` block carries): real age_s or honestly absent,
       never a guessed number. It also keeps the field warm (aqi triggers
       a server-side refresh). */
    loadTrips().then(setTrips).catch(() => {});
    loadSettings().then(setSettings).catch(() => {});
    (async () => {
      const r = await Location.requestForegroundPermissionsAsync().catch(() => null);
      setHasLoc(!!r?.granted);
      const pos = await Location.getCurrentPositionAsync({ accuracy: Location.Accuracy.Balanced }).catch(() => null);
      if (pos) {
        setFrom({ name: t("placeCurrentLocation", settings.lang), subtitle: "", lat: pos.coords.latitude, lon: pos.coords.longitude });
        // wait for the initial style/tile load to settle before animating —
        // flyTo during first-load is a render-thread spike on the iOS sim
        setTimeout(() => camRef.current?.flyTo({ center: [pos.coords.longitude, pos.coords.latitude], zoom: 15, duration: 900 }), 600);
      }
    })();
    const aqiPoll = () =>
      fetchJson(`${API}/aqi?lat=${DELHI[1]}&lon=${DELHI[0]}`, 8000)
        .then((j) => setAqiField(
          j?.field && typeof j.field === "object" ? (j.field as FieldStatus) : null))
        .catch(() => {});
    aqiPoll();
    const aqiIv = setInterval(aqiPoll, 60000);
    // first-run gate is the consent record now (supersedes intro_seen.txt)
    loadConsent().then((c) => setIntroSeen(c.seen)).catch(() => setIntroSeen(false));
    return () => { clearInterval(iv); clearInterval(healthIv); clearInterval(aqiIv); };
  }, [setFrom, setTrips, settings.lang]);

  /* the layers sheet is idle-phase chrome — leaving idle (search, compare,
     nav) must close it or it bleeds through stacked behind the next surface
     (reproduced: its toggles rendered under the compare sheet) */
  useEffect(() => { if (phase !== "idle") setLayersOpen(false); }, [phase]);

  /* Android hardware BACK closes the topmost open surface — every overlay
     here is a plain View (no Modal onRequestClose), so without a dispatcher
     BACK fell through and exited the app (Android forensic find on the
     drawer). Checked topmost-first, matching JSX mount order; SearchScreen
     and Sidebar keep their own local handlers — registered later, they win
     the race for the same press. flow.needsVehicle (the forced first-pick)
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
         button is the honest exit. Search handles its own press. */
      if (phase === "compare") { flow.clearRoute(); return true; }
      if (phase === "nav") return true;
      return false;
    });
    return () => sub.remove();
  }, [vehicleOpen, settingsOpen, ledgerOpen, delhiOpen, layersOpen, sidebarOpen, mapPickArmed, phase, flow]);

  const patchSettings = useCallback((p: Partial<ShellSettings>) => {
    setSettings((s) => { const n = { ...s, ...p }; saveSettings(n); return n; });
    // the consent record mirrors the share toggle — it is the canonical
    // donation answer (nav engine + trip submit read it)
    if ("share" in p) {
      saveConsent({ sharing: p.share ? "on" : "off", ts: Date.now() }).catch(() => {});
    }
    // drawer chip -> profile: a coarse pick that changes class starts a
    // fresh profile (fuel/year are class-specific, honestly unknown)
    if (p.vehicle != null) {
      const cls = DRAWER2CLS[p.vehicle];
      if (cls) {
        getVehicle().then((cur) => {
          if (cur?.cls !== cls) flow.setVehicleProfile({ cls, fuel: null, year: null });
        }).catch(() => {});
      }
    }
  }, [flow]);

  /** Sheet/compare answer: persist the profile AND mirror its class
   *  into the drawer so both surfaces show the same vehicle. */
  const applyVehicle = useCallback((p: VehicleProfile) => {
    flow.setVehicleProfile(p);
    patchSettings({ vehicle: CLS2DRAWER[p.cls] });
  }, [flow, patchSettings]);

  /* boot sync: a profile saved in a previous run backfills the drawer's
   *  coarse class (drawer chip -> profile sync lives in patchSettings). */
  useEffect(() => {
    if (!settings.vehicle && flow.vehicle) {
      /* react-hooks/set-state-in-effect: defer the sync out of the
         effect body — it writes settings, not an external system */
      queueMicrotask(() => patchSettings({ vehicle: CLS2DRAWER[flow.vehicle!.cls] }));
    }
  }, [flow.vehicle, settings.vehicle, patchSettings]);

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
        void fetch(
          `${API}/v2/ledger?token=${encodeURIComponent(tok)}`,
          { method: "DELETE" },
        ).catch(() => {});
      }
      clearAllData();
      flow.setTrips([]); flow.setVehicleProfile(null);
      setSettings((s) => ({ ...DEFAULT_SETTINGS, lang: s.lang }));
      /* closing the sheet IS the acknowledgment — the user lands back on
         a clean map; the consent gate re-arms itself on next launch */
      setSettingsOpen(false); setSidebarOpen(false);
    })();
  }, [flow]);
  const toggleLayer = useCallback((k: LayerKey, v: boolean) => {
    setLayers((l) => ({ ...l, [k]: v }));
    if (!v) return;                                     // lazy: fetch on first enable
    if (k === "fires" && !fires) fetchJson(`${API}/fires`).then(setFires).catch(() => {});
    if (k === "spots" && !spots) fetchJson(`${API}/blackspots`).then(setSpots).catch(() => {});
    if (k === "corridors" && !flow.community) fetchJson(`${API}/community`).then(flow.setCommunity).catch(() => {});
  }, [fires, spots, flow]);
  if (!fontsLoaded) return null;
  const sel = flow.options[flow.selected];
  const mapField = flow.planField ?? aqiField;

  return (
    <View style={s.root}>
      <StatusBar style="dark" />
      <Map mapStyle={STYLE_URL} style={StyleSheet.absoluteFill}
        /* the compass clears the chrome: search bar at rest, the taller
           maneuver banner in nav (was clipped behind it at top-right) */
        compassPosition={phase === "nav"
          ? { top: insets.top + 108, right: 12 }
          : { top: insets.top + 76, right: 12 }}
        /* ornaments ride above the FABs — the stock bottom-edge spots
           clip against the home-indicator bezel + the FAB shadows */
        logoPosition={{ bottom: insets.bottom + 72, left: 10 }}
        attributionPosition={{ bottom: insets.bottom + 72, right: 10 }}
        onPress={async (f) => {
          if (!mapPickArmed) return;
          setMapPickArmed(false);
          const c = f.nativeEvent.lngLat;
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
          flow.pick({ name: rev.name, subtitle: rev.subtitle, lat: c[1], lon: c[0] }, "to");
        }}
        onLongPress={async (f) => {
          const c = f.nativeEvent.lngLat;
          if (!c) return;
          const rev = await reverseName(c[1], c[0]);
          flow.pick({ name: rev.name, subtitle: rev.subtitle, lat: c[1], lon: c[0] }, "to");
        }}>
        {/* maxBounds = the dose field's service margin (NCR ±2°), not the
            tight NCR box — a destination in Agra/Jaipur must stay on
            screen or the outside-area notice can't be understood */}
        <Camera ref={camRef} initialViewState={{ center: DELHI, zoom: 11 }} maxBounds={[74.75, 26.15, 79.95, 30.98]}
          trackUserLocation={flow.follow ? "default" : undefined}
          onTrackUserLocationChange={(e) => { if (!e.nativeEvent.trackUserLocation) flow.setFollow(false); }} />
        {/* mounted once we have a fix and left mounted — unmounting the
            location puck pulls its native layer mid-draw (same upstream
            sim crash class as route sources/markers). The small idle-GPS
            cost beats a remove-during-render race; always-on dot matches
            normal map UX anyway. */}
        {hasLoc && <UserLocation animated accuracy />}
        {layers.corridors && <CorridorLayer corridors={flow.community?.top_corridors ?? null} />}
        <ReportsLayer reports={reports} />
        {layers.fires && <FiresLayer fires={fires} />}
        {layers.spots && <BlackspotsLayer spots={spots} />}
        {/* route-wise AQI gradient on the real /v2/plan polylines — per
            ~250 m chunk from the fetched strips, flat dose-mean until they
            land; selected 6 px on 9 px casing, alternates 3 px at 50 %.
            (<RouteTintSource/> — src/components/RouteTint.tsx contract) */}
        <RouteTintSource
          options={deferredOptions}
          selected={flow.selected}
          strips={flow.strips}
        />
        {/* endpoint annotations stay mounted at their last coordinates —
            unmounting a MarkerView mid-draw is the same upstream
            remove-during-render class as the route sources. Hidden is an
            empty child; the pin never teleports because the ref holds the
            last real coordinate. */}
        <Marker lngLat={fromPin.current} anchor="center">
          {flow.from && pinReady ? <EndpointPin kind="origin" /> : <View />}
        </Marker>
        <Marker lngLat={toPin.current} anchor="bottom">
          {flow.to && pinReady ? <EndpointPin kind="dest" /> : <View />}
        </Marker>
      </Map>

      {/* rest state chrome: search bar + locate + layers (doc 02 §S1) */}
      {phase !== "nav" && (
        <View style={[s.pillWrap, { top: insets.top + 10 }]}>
          <SearchBar
            label={phase === "compare" && flow.to ? flow.to.name : undefined}
            lang={lang}
            onMenu={() => setSidebarOpen(true)}
            onPress={() => { flow.setEditWhich("to"); flow.setPhase("search"); }}
            onClear={phase === "compare" ? flow.clearRoute : undefined} />
        </View>
      )}
      <SearchScreen
        visible={phase === "search"}
        lang={lang}
        userLocation={flow.from ? { lat: flow.from.lat, lon: flow.from.lon } : null}
        onClose={() => {
          if (placePickSlot) { setPlacePickSlot(null); setSidebarOpen(true); }
          flow.setPhase(flow.to ? "compare" : "idle");
        }}
        onSelect={async (sel: SearchSelection) => {
          if (sel.type === "place") {
            if (placePickSlot) {
              // sidebar's unset home/work slot asked for a search pick —
              // land the place in settings and return to the drawer
              patchSettings({ [placePickSlot]: {
                name: sel.place.name, lat: sel.place.lat, lon: sel.place.lon } });
              setPlacePickSlot(null);
              flow.setPhase("idle");
              setSidebarOpen(true);
              return;
            }
            setMapPickArmed(false);
            flow.pick({ name: sel.place.name, subtitle: sel.place.subtitle ?? "",
              lat: sel.place.lat, lon: sel.place.lon }, "to");
            return;
          }
          if (sel.type === "choose_on_map") {
            flow.setPhase("idle");
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
            flow.setPhase("idle");
            setSidebarOpen(true);
          } else if (pos) flow.pick({ name: t("yourLocation", lang), subtitle: "",
            lat: pos.coords.latitude, lon: pos.coords.longitude }, "from");
          else flow.setPhase(flow.to ? "compare" : "idle");
        }} />
      {phase === "idle" && (
        <>
          <View style={[s.locateWrap, { bottom: insets.bottom + 16 }]}>
            <LocateButton active={flow.follow} onPress={() => {
              if (flow.follow) { flow.setFollow(false); return; }
              /* warm the fused provider before engaging follow — MapLibre's
                 native layer posts a raw error toast when track starts with
                 no fix yet (Android forensic find); a one-shot fix primes it */
              Location.getCurrentPositionAsync({ accuracy: Location.Accuracy.Balanced })
                .then((pos) => { if (pos) { setHasLoc(true); flow.setFollow(true); } })
                .catch(() => {});
            }} lang={lang} />
          </View>
          <View style={[s.layersWrap, { bottom: insets.bottom + 16 }]}>
            <LayersButton anyOn={Object.values(layers).some(Boolean)} onPress={() => setLayersOpen(true)} lang={lang} />
          </View>
        </>
      )}
      {/* SEAM(breath-chip): optional "breathing heavier/lighter" chip while moving
          (doc 02 §S1) — needs a real trailing-30min baseline; not yet wired. */}

      {/* offline/stale pill — real request outcomes drive it (offline/
          status.ts): live data → no pill; last-good or nothing → labelled,
          pending trip donations counted, tap re-probes. apiOk kept as the
          belt-and-suspenders health check from before. */}
      {(net.state !== "online" || apiOk === false) && (
        <Pressable style={[s.offlineWrap, { top: insets.top + 66 }]} onPress={() => { tick(); void net.refresh(); }}
          accessibilityRole="button" accessibilityLabel={t("offline", lang)}>
          <Text {...DYNAMIC_TYPE} style={[s.offlineTxt, { fontFamily: fam(lang, "med") }]}>
            {net.state === "stale" ? t("offlineStale", lang) : t("offline", lang)}
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
          <Icon name="pin" color={V2T.accent} size={14} />
          <Text {...DYNAMIC_TYPE} style={[s.pickHintTxt, { fontFamily: fam(lang, "med") }]}>
            {t("mapPickHint", lang)}
          </Text>
        </Pressable>
      )}
      {/* freshness chip — real field age on the map screen: the /v2/plan
          field block during compare, else the polled /aqi field block.
          Stale shows as stale; no field → nothing claims freshness. */}
      {phase !== "nav" && phase !== "search" && mapField && (
        <View style={[s.freshWrap, { top: insets.top + 62 }]} pointerEvents="box-none">
          <FreshnessChip
            ageS={mapField.age_s} stale={mapField.stale}
            sources={fieldSources(mapField)} lang={lang} compact />
        </View>
      )}
      {phase === "compare" && (
        <CompareSheet options={flow.options} selected={flow.selected} onSelect={flow.setSelected}
          depart={flow.depart} departCurve={flow.departCurve} notified={flow.notified}
          onRemind={flow.remind} loading={flow.loadingRoute} refining={flow.refining}
          steps={flow.steps} stepsOpen={flow.stepsOpen} onToggleSteps={() => flow.setStepsOpen(!flow.stepsOpen)}
          onStart={flow.startNav} onClose={flow.clearRoute} lang={lang}
          vehicle={flow.vehicle} onVehiclePress={() => setVehicleOpen(true)}
          onVehicleChange={applyVehicle}
          planError={flow.planError} onRetry={flow.retryPlan} degraded={flow.planDegraded}
          fieldAgeS={flow.planField?.age_s}
          showCig={settings.show_cig} />
      )}
      {phase === "nav" && sel && (
        <NavSession option={sel} options={flow.options} from={flow.from} to={flow.to} steps={flow.steps}
          camRef={camRef} lang={lang} share={settings.share} voice={settings.voice} onExit={flow.exitNav}
          vehicle={flow.vehicle} showCig={settings.show_cig} onTripDone={flow.recordTrip} />
      )}

      <Sidebar open={sidebarOpen} onClose={() => setSidebarOpen(false)} trips={flow.trips} lang={lang}
        settings={settings} onSettings={patchSettings} onDeleteData={deleteAll}
        onPickPlace={(slot) => {
          setPlacePickSlot(slot);
          setSidebarOpen(false);
          flow.setPhase("search");
        }}
        onArmBrief={flow.armDailyBrief} currentDest={flow.to}
        onDelhiToday={() => { setSidebarOpen(false); setDelhiOpen(true); }}
        onTripReceipt={() => { setSidebarOpen(false); setLedgerOpen(true); }}
        onFullSettings={() => { setSidebarOpen(false); setSettingsOpen(true); }}
        onNavigate={(p) => flow.pick({ ...p, subtitle: "" }, "to")}
        onLang={(l) => patchSettings({ lang: l })}
        onShare={() => Share.share({ message: t("shareAppBody", lang) }).catch(() => {})}
        onShareTrip={(tr) => Share.share({
          message: t("shareTripBody", lang, {
            from: placeNameLabel(tr.from, lang), to: placeNameLabel(tr.to, lang),
            // cigarette figure only with show_cig on; µg is the default
            dose: tr.dose_ug != null
              ? (settings.show_cig ? `≈${cigOf(tr.dose_ug)} cigarettes` : `~${Math.round(tr.dose_ug)}µg`)
              : "—",
            // co2 was never passed — the template printed a literal "{co2}"
            co2: tr.emit_kg != null ? `~${tr.emit_kg.toFixed(1)}kg CO₂` : "—",
          }),
        }).catch(() => {})} />
      <LayersSheet visible={layersOpen} values={layers} onToggle={toggleLayer}
        onClose={() => setLayersOpen(false)} lang={lang} />
      <DelhiToday visible={delhiOpen} onClose={() => setDelhiOpen(false)} lang={lang} showCig={settings.show_cig} />
      <LedgerScreen visible={ledgerOpen} onClose={() => setLedgerOpen(false)} lang={lang} showCig={settings.show_cig} onTripsChanged={flow.reloadTrips} />
      <SettingsScreen visible={settingsOpen} onClose={() => setSettingsOpen(false)}
        lang={lang} current={settings} onArmBrief={flow.armDailyBrief}
        onDeleteData={deleteAll}
        onChange={(k: string, v?: unknown) => {
          if (k === "editVehicle") { setSettingsOpen(false); setVehicleOpen(true); return; }
          patchSettings({ [k]: v } as Partial<ShellSettings>);
        }} />
      <VehicleSheet visible={vehicleOpen || flow.needsVehicle} lang={lang}
        current={flow.vehicle}
        onDone={(p) => {
          setVehicleOpen(false);
          /* re-plan commit must not share the sheet-close frame — the
             close anim + options/RouteTint landing together is the
             residual-SIGSEGV trigger on the virtualized-GPU sim */
          setTimeout(() => applyVehicle(p), 80);
        }}
        onClose={() => setVehicleOpen(false)} />

      <OnboardingScreen visible={introSeen === false} lang={lang}
        onDone={({ sharing }) => {
          patchSettings({ share: sharing === "on" });
          setIntroSeen(true);
        }} />
    </View>
  );
}

/** Live-trip session: mounts the nav engine exactly for the nav phase —
 *  the hook owns the GNSS watcher + 1 Hz counters + off-route + strip;
 *  we only translate the plan option into its NavRoute and its summary
 *  into the receipt. (src/nav contract — see src/nav/index.ts) */
function NavSession({
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
  onTripDone: (t: { label: string; vehicle: string; doseUg: number | null; avoidedUg: number | null }) => void;
}) {
  const [summary, setSummary] = useState<NavSummary | null>(null);
  /* the arrival swap is two commits, not one: NavChrome unmounts on its
     own frame, then the receipt mounts next frame — a remove+add swap
     against the map's draw is the residual-SIGSEGV class (ci15). */
  const [receiptReady, setReceiptReady] = useState(false);
  useEffect(() => {
    if (!summary) return;
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
              ? (showCig ? `≈${cigOf(summary.doseUg.mid)} cigarettes` : `~${Math.round(summary.doseUg.mid)}µg`)
              : "—",
            co2: summary.co2Kg.mid != null ? `~${summary.co2Kg.mid.toFixed(1)}kg CO₂` : "—",
          }),
        }).catch(() => {})} />
    );
  }
  return (
    <NavChrome option={option} steps={steps} doseUg={0}
      nav={nav} onRecenter={nav.recenter} showCig={showCig}
      onExit={() => nav.arrive(false)} lang={lang} />
  );
}

const s = StyleSheet.create({
  root: { flex: 1, backgroundColor: V2T.bg },
  // top/bottom come from useSafeAreaInsets inline — status bar, notch and
  // the gesture pill differ per device (no fixed 54/40 on real hardware)
  pillWrap: { position: "absolute", left: 16, right: 16 },
  locateWrap: { position: "absolute", right: 14 },
  layersWrap: { position: "absolute", left: 14 },
  offlineWrap: {
    position: "absolute", alignSelf: "center",
    backgroundColor: V2T.glassFaint, borderRadius: V2Radius.row, paddingHorizontal: 12, paddingVertical: 6,
    borderWidth: 1, borderColor: V2T.glassLine,
  },
  offlineTxt: { fontSize: V2Type.label, color: V2T.text2 },
  pickHintWrap: {
    position: "absolute", alignSelf: "center",
    flexDirection: "row", alignItems: "center", gap: 6,
    backgroundColor: V2T.glassFaint, borderRadius: V2Radius.pill,
    paddingHorizontal: 12, paddingVertical: 7,
    borderWidth: 1, borderColor: V2T.accent,
    shadowColor: "#000", shadowOpacity: 0.10, shadowRadius: 8,
    shadowOffset: { width: 0, height: 2 }, elevation: 5,
  },
  pickHintTxt: { fontSize: V2Type.label, color: V2T.text },
  freshWrap: { position: "absolute", left: 16 },
});
