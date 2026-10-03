import React, { useCallback, useEffect, useRef, useState } from "react";
import { LogBox, Pressable, Share, StyleSheet, Text, View } from "react-native";
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
import { F, V2Radius, V2T, V2Type } from "./src/theme";
import { DYNAMIC_TYPE } from "./src/a11y";
import { EndpointPin } from "./src/ui";
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
import { API, DELHI, fetchJson } from "./src/components/shell/net";
import {
  DEFAULT_SETTINGS, clearAllData, loadSettings, saveSettings, type ShellSettings,
} from "./src/components/shell/settings";
import { loadTrips } from "./src/store/ledger";
import { getVehicle, type VehicleClass, type VehicleProfile } from "./src/store/vehicle";
import { modeLabel, t } from "./src/i18n/strings";

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
  const insets = useSafeAreaInsets();
  const [settings, setSettings] = useState<ShellSettings>(DEFAULT_SETTINGS);
  const flow = useShellFlow(camRef, settings.share, settings.lang);
  const { phase } = flow;
  const lang = settings.lang;

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
    const ping = () => fetch(`${API}/health`, { keepalive: true })
      .then((r) => setApiOk(r.ok)).catch(() => setApiOk(false));
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
        camRef.current?.flyTo({ center: [pos.coords.longitude, pos.coords.latitude], zoom: 15, duration: 900 });
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
          let name = `${c[1].toFixed(4)}, ${c[0].toFixed(4)}`;
          try { const j = await fetchJson(`${API}/reverse?lat=${c[1]}&lon=${c[0]}`, 6000); if (j.name) name = j.name; } catch {}
          flow.pick({ name, subtitle: "", lat: c[1], lon: c[0] }, "to");
        }}
        onLongPress={async (f) => {
          const c = f.nativeEvent.lngLat;
          if (!c) return;
          let name = `${c[1].toFixed(4)}, ${c[0].toFixed(4)}`;
          try { const j = await fetchJson(`${API}/reverse?lat=${c[1]}&lon=${c[0]}`, 6000); if (j.name) name = j.name; } catch {}
          flow.pick({ name, subtitle: "", lat: c[1], lon: c[0] }, "to");
        }}>
        {/* maxBounds = the dose field's service margin (NCR ±2°), not the
            tight NCR box — a destination in Agra/Jaipur must stay on
            screen or the outside-area notice can't be understood */}
        <Camera ref={camRef} initialViewState={{ center: DELHI, zoom: 11 }} maxBounds={[74.75, 26.15, 79.95, 30.98]}
          trackUserLocation={flow.follow ? "default" : undefined}
          onTrackUserLocationChange={(e) => { if (!e.nativeEvent.trackUserLocation) flow.setFollow(false); }} />
        {/* mounted only while locating — a permanent subscription idles
            the GPS chip + animation loop for nothing (perf-r4) */}
        {hasLoc && (phase === "nav" || flow.follow) && <UserLocation animated accuracy />}
        {layers.corridors && <CorridorLayer corridors={flow.community?.top_corridors ?? null} />}
        <ReportsLayer reports={reports} />
        {layers.fires && <FiresLayer fires={fires} />}
        {layers.spots && <BlackspotsLayer spots={spots} />}
        {/* route-wise AQI gradient on the real /v2/plan polylines — per
            ~250 m chunk from the fetched strips, flat dose-mean until they
            land; selected 6 px on 9 px casing, alternates 3 px at 50 %.
            (<RouteTintSource/> — src/components/RouteTint.tsx contract) */}
        <RouteTintSource
          options={flow.options}
          selected={flow.selected}
          strips={flow.strips}
        />
        {flow.from && phase === "compare" && (
          <Marker lngLat={[flow.from.lon, flow.from.lat]} anchor="center"><EndpointPin kind="origin" /></Marker>
        )}
        {flow.to && (
          <Marker lngLat={[flow.to.lon, flow.to.lat]} anchor="bottom"><EndpointPin kind="dest" /></Marker>
        )}
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
        onClose={() => flow.setPhase(flow.to ? "compare" : "idle")}
        onSelect={async (sel: SearchSelection) => {
          if (sel.type === "place") {
            setMapPickArmed(false);
            flow.pick({ name: sel.place.name, subtitle: sel.place.subtitle ?? "",
              lat: sel.place.lat, lon: sel.place.lon }, "to");
            return;
          }
          if (sel.type === "choose_on_map") {
            flow.setPhase("idle");
            setMapPickArmed(true);       // next map tap picks the destination
            return;
          }
          const pos = await Location.getCurrentPositionAsync(
            { accuracy: Location.Accuracy.Balanced }).catch(() => null);
          if (pos) flow.pick({ name: t("yourLocation", lang), subtitle: "",
            lat: pos.coords.latitude, lon: pos.coords.longitude }, "from");
          else flow.setPhase(flow.to ? "compare" : "idle");
        }} />
      {phase === "idle" && (
        <>
          <View style={[s.locateWrap, { bottom: insets.bottom + 16 }]}>
            <LocateButton active={flow.follow} onPress={() => flow.setFollow(!flow.follow)} lang={lang} />
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
        <Pressable style={[s.offlineWrap, { top: insets.top + 66 }]} onPress={() => void net.refresh()}
          accessibilityRole="button" accessibilityLabel={t("offline", lang)}>
          <Text {...DYNAMIC_TYPE} style={s.offlineTxt}>
            {net.state === "stale" ? t("offlineStale", lang) : t("offline", lang)}
            {net.pending > 0 ? ` · ${t("offlinePending", lang, { n: net.pending })}` : ""}
          </Text>
        </Pressable>
      )}
      {/* freshness chip — real field age on the map screen: the /v2/plan
          field block during compare, else the polled /aqi field block.
          Stale shows as stale; no field → nothing claims freshness. */}
      {phase !== "nav" && mapField && (
        <View style={[s.freshWrap, { top: insets.top + 62 }]} pointerEvents="box-none">
          <FreshnessChip
            ageS={mapField.age_s} stale={mapField.stale}
            sources={fieldSources(mapField)} lang={lang} compact />
        </View>
      )}
      {phase === "compare" && (
        <CompareSheet options={flow.options} selected={flow.selected} onSelect={flow.setSelected}
          depart={flow.depart} departCurve={flow.departCurve} notified={flow.notified}
          onRemind={flow.remind} loading={flow.loadingRoute}
          steps={flow.steps} stepsOpen={flow.stepsOpen} onToggleSteps={() => flow.setStepsOpen(!flow.stepsOpen)}
          onStart={flow.startNav} onClose={flow.clearRoute} lang={lang}
          vehicle={flow.vehicle} onVehiclePress={() => setVehicleOpen(true)}
          onVehicleChange={applyVehicle}
          planError={flow.planError} onRetry={flow.retryPlan}
          fieldAgeS={flow.planField?.age_s} />
      )}
      {phase === "nav" && sel && (
        <NavSession option={sel} options={flow.options} from={flow.from} to={flow.to} steps={flow.steps}
          camRef={camRef} lang={lang} share={settings.share} onExit={flow.exitNav}
          onTripDone={flow.recordTrip} />
      )}

      <Sidebar open={sidebarOpen} onClose={() => setSidebarOpen(false)} trips={flow.trips} lang={lang}
        settings={settings} onSettings={patchSettings} onDeleteData={deleteAll}
        onArmBrief={flow.armDailyBrief} currentDest={flow.to}
        onDelhiToday={() => { setSidebarOpen(false); setDelhiOpen(true); }}
        onTripReceipt={() => { setSidebarOpen(false); setLedgerOpen(true); }}
        onFullSettings={() => { setSidebarOpen(false); setSettingsOpen(true); }}
        onNavigate={(p) => flow.pick({ ...p, subtitle: "" }, "to")}
        onLang={(l) => patchSettings({ lang: l })}
        onShare={() => Share.share({ message: t("shareAppBody", lang) }).catch(() => {})}
        onShareTrip={(tr) => Share.share({
          message: t("shareTripBody", lang, {
            from: tr.from, to: tr.to,
            dose: tr.dose_ug != null ? `~${Math.round(tr.dose_ug)}µg` : "—",
          }),
        }).catch(() => {})} />
      <LayersSheet visible={layersOpen} values={layers} onToggle={toggleLayer}
        onClose={() => setLayersOpen(false)} lang={lang} />
      <DelhiToday visible={delhiOpen} onClose={() => setDelhiOpen(false)} lang={lang} />
      <LedgerScreen visible={ledgerOpen} onClose={() => setLedgerOpen(false)} lang={lang} onTripsChanged={flow.reloadTrips} />
      <SettingsScreen visible={settingsOpen} onClose={() => setSettingsOpen(false)}
        lang={lang} current={settings} onArmBrief={flow.armDailyBrief}
        onDeleteData={deleteAll}
        onChange={(k: string, v?: unknown) => {
          if (k === "editVehicle") { setSettingsOpen(false); setVehicleOpen(true); return; }
          patchSettings({ [k]: v } as Partial<ShellSettings>);
        }} />
      <VehicleSheet visible={vehicleOpen || flow.needsVehicle} lang={lang}
        current={flow.vehicle}
        onDone={(p) => { applyVehicle(p); setVehicleOpen(false); }}
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
  option, options, from, to, steps, camRef, lang, share, onExit, onTripDone,
}: {
  option: V2Option; options: V2Option[]; from: Place | null; to: Place | null; steps: Step[] | null;
  camRef: React.RefObject<CameraRef | null>; lang: "en" | "hi";
  share: boolean; onExit: () => void;
  onTripDone: (t: { label: string; vehicle: string; doseUg: number | null; avoidedUg: number | null }) => void;
}) {
  const [summary, setSummary] = useState<NavSummary | null>(null);
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
      emissionsBreakdown: option.emissions?.breakdown ?? null,
    },
    camRef,
    lang,
    shareEnabled: share,
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
    return () => { navRef.current.stop(); };
  }, []);

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
      <ReceiptSheet data={data} lang={lang} onDone={onExit}
        onShare={() => Share.share({
          message: t("shareTripBody", lang, {
            from: from?.name ?? "?", to: to?.name ?? "?",
            dose: summary.doseUg.mid != null ? `~${Math.round(summary.doseUg.mid)}µg` : "—",
            co2: summary.co2Kg.mid != null ? `~${summary.co2Kg.mid.toFixed(1)}kg CO₂` : "—",
          }),
        }).catch(() => {})} />
    );
  }
  return (
    <NavChrome option={option} steps={steps} doseUg={0}
      nav={nav} onRecenter={nav.recenter}
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
    backgroundColor: V2T.surface2, borderRadius: V2Radius.row, paddingHorizontal: 12, paddingVertical: 6,
    borderWidth: 1, borderColor: V2T.line,
  },
  offlineTxt: { fontFamily: F.med, fontSize: V2Type.label, color: V2T.text2 },
  freshWrap: { position: "absolute", left: 16 },
});
