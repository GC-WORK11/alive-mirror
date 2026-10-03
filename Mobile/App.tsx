import React, { useCallback, useEffect, useRef, useState } from "react";
import { LogBox, Pressable, StyleSheet, Text, View } from "react-native";
import { StatusBar } from "expo-status-bar";
import * as SplashScreen from "expo-splash-screen";
import { useFonts, Inter_400Regular, Inter_500Medium, Inter_600SemiBold } from "@expo-google-fonts/inter";
import {
  NotoSansDevanagari_400Regular, NotoSansDevanagari_500Medium, NotoSansDevanagari_600SemiBold,
} from "@expo-google-fonts/noto-sans-devanagari";
import * as Location from "expo-location";
import { File, Paths } from "expo-file-system";
import {
  Camera, GeoJSONSource, Layer, Map, Marker, UserLocation, type CameraRef,
} from "@maplibre/maplibre-react-native";
import { F, NUM, V2Radius, V2T, V2Type, fam } from "./src/theme";
import { EndpointPin } from "./src/ui";
import type { Place, Step, V2Option } from "./src/components/shell/types";
import { ReportsLayer } from "./src/components/ReportsLayer";
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
import { CompareSheet } from "./src/components/shell/CompareSheet";
import { NavChrome } from "./src/components/shell/NavChrome";
import { ReceiptSheet, type ReceiptData } from "./src/components/shell/ReceiptSheet";
import { useNavEngine, type NavSummary, type NavStep } from "./src/nav";
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
import { t } from "./src/i18n/strings";

SplashScreen.preventAutoHideAsync().catch(() => {});

const STYLE_URL = "https://tiles.openfreemap.org/styles/dark"; // OpenMapTiles dark-matter fork

// liberty ships a few vector tiles MLRN can't parse — a native dev-only
// console warning; nothing in our layers is involved
LogBox.ignoreLogs(["Invalid geometry in line layer"]);

export default function App() {
  const camRef = useRef<CameraRef>(null);
  const [settings, setSettings] = useState<ShellSettings>(DEFAULT_SETTINGS);
  const flow = useShellFlow(camRef, settings.share);
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
  const [introSeen, setIntroSeen] = useState<boolean | null>(null);

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
    loadTrips().then(setTrips).catch(() => {});
    loadSettings().then(setSettings).catch(() => {});
    (async () => {
      const r = await Location.requestForegroundPermissionsAsync().catch(() => null);
      setHasLoc(!!r?.granted);
      const pos = await Location.getCurrentPositionAsync({ accuracy: Location.Accuracy.Balanced }).catch(() => null);
      if (pos) {
        setFrom({ name: "current location", subtitle: "", lat: pos.coords.latitude, lon: pos.coords.longitude });
        camRef.current?.flyTo({ center: [pos.coords.longitude, pos.coords.latitude], zoom: 12.5, duration: 900 });
      }
    })();
    // first-run gate is the consent record now (supersedes intro_seen.txt)
    loadConsent().then((c) => setIntroSeen(c.seen)).catch(() => setIntroSeen(false));
    return () => { clearInterval(iv); clearInterval(healthIv); };
  }, [setFrom, setTrips]);

  const patchSettings = useCallback((p: Partial<ShellSettings>) => {
    setSettings((s) => { const n = { ...s, ...p }; saveSettings(n); return n; });
    // the consent record mirrors the share toggle — it is the canonical
    // donation answer (nav engine + trip submit read it)
    if ("share" in p) {
      saveConsent({ sharing: p.share ? "on" : "off", ts: Date.now() }).catch(() => {});
    }
  }, []);
  const deleteAll = useCallback(() => {
    clearAllData();
    flow.setTrips([]); setSettings((s) => ({ ...DEFAULT_SETTINGS, lang: s.lang }));
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

  return (
    <View style={s.root}>
      <StatusBar style="light" />
      <Map mapStyle={STYLE_URL} style={StyleSheet.absoluteFill}
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
        <Camera ref={camRef} initialViewState={{ center: DELHI, zoom: 11 }} maxBounds={[76.75, 28.15, 77.95, 28.98]}
          trackUserLocation={flow.follow ? "default" : undefined}
          onTrackUserLocationChange={(e) => { if (!e.nativeEvent.trackUserLocation) flow.setFollow(false); }} />
        {hasLoc && <UserLocation animated accuracy />}
        {layers.corridors && <CorridorLayer corridors={flow.community?.top_corridors ?? null} />}
        <ReportsLayer reports={reports} />
        {layers.fires && <FiresLayer fires={fires} />}
        {layers.spots && <BlackspotsLayer spots={spots} />}
        <Layer id="buildings3d" type="fill-extrusion" source="openmaptiles" source-layer="building" minzoom={15}
          paint={{ "fill-extrusion-color": V2T.mapBuilding,
            "fill-extrusion-height": ["coalesce", ["get", "render_height"], ["get", "height"], 10],
            "fill-extrusion-opacity": 0.6 }} />
        <GeoJSONSource id="alts" data={flow.altSegs}>
          <Layer id="alts-line" type="line"
            paint={{ "line-color": V2T.text3, "line-width": 2.5, "line-opacity": 0.4, "line-dasharray": [2, 2] }}
            layout={{ "line-cap": "round", "line-join": "round" }} />
        </GeoJSONSource>
        <GeoJSONSource id="route" data={flow.routeSegs}>
          <Layer id="route-casing" type="line"
            paint={{ "line-color": V2T.bg, "line-width": 9 }} layout={{ "line-cap": "round", "line-join": "round" }} />
          <Layer id="route-line" type="line"
            paint={{ "line-color": ["get", "color"], "line-width": 6 }} layout={{ "line-cap": "round", "line-join": "round" }} />
        </GeoJSONSource>
        {flow.from && phase === "compare" && (
          <Marker lngLat={[flow.from.lon, flow.from.lat]} anchor="center"><EndpointPin kind="origin" /></Marker>
        )}
        {flow.to && (
          <Marker lngLat={[flow.to.lon, flow.to.lat]} anchor="bottom"><EndpointPin kind="dest" /></Marker>
        )}
      </Map>

      {/* rest state chrome: search bar + locate + layers (doc 02 §S1) */}
      {phase !== "nav" && (
        <View style={s.pillWrap}>
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
          <View style={s.locateWrap}>
            <LocateButton active={flow.follow} onPress={() => flow.setFollow(!flow.follow)} lang={lang} />
          </View>
          <View style={s.layersWrap}>
            <LayersButton anyOn={Object.values(layers).some(Boolean)} onPress={() => setLayersOpen(true)} lang={lang} />
          </View>
        </>
      )}
      {/* SEAM(breath-chip): optional "breathing heavier/lighter" chip while moving
          (doc 02 §S1) — needs a real trailing-30min baseline; not yet wired. */}

      {apiOk === false && (
        <View style={s.offlineWrap} pointerEvents="none">
          <Text style={s.offlineTxt}>{t("offline", lang)}</Text>
        </View>
      )}
      {phase === "compare" && (
        <CompareSheet options={flow.options} selected={flow.selected} onSelect={flow.setSelected}
          depart={flow.depart} notified={flow.notified} onRemind={flow.remind} loading={flow.loadingRoute}
          steps={flow.steps} stepsOpen={flow.stepsOpen} onToggleSteps={() => flow.setStepsOpen(!flow.stepsOpen)}
          onStart={flow.startNav} onClose={flow.clearRoute} lang={lang}
          vehicle={flow.vehicle} onVehiclePress={() => setVehicleOpen(true)}
          onVehicleChange={flow.setVehicleProfile}
          planError={flow.planError} onRetry={flow.retryPlan}
          fieldAgeS={flow.planField?.age_s} />
      )}
      {phase === "nav" && sel && (
        <NavSession option={sel} options={flow.options} to={flow.to} steps={flow.steps}
          camRef={camRef} lang={lang} share={settings.share} onExit={flow.exitNav}
          onTripDone={flow.recordTrip} />
      )}

      <Sidebar open={sidebarOpen} onClose={() => setSidebarOpen(false)} trips={flow.trips} lang={lang}
        settings={settings} onSettings={patchSettings} onDeleteData={deleteAll}
        onArmBrief={flow.armDailyBrief} currentDest={flow.to}
        onDelhiToday={() => { setSidebarOpen(false); setDelhiOpen(true); }}
        onTripReceipt={() => { setSidebarOpen(false); setLedgerOpen(true); }}
        onFullSettings={() => { setSidebarOpen(false); setSettingsOpen(true); }}
        onNavigate={(p) => flow.pick({ ...p, subtitle: "" }, "to")} />
      <LayersSheet visible={layersOpen} values={layers} onToggle={toggleLayer}
        onClose={() => setLayersOpen(false)} lang={lang} />
      <DelhiToday visible={delhiOpen} onClose={() => setDelhiOpen(false)} lang={lang} />
      <LedgerScreen visible={ledgerOpen} onClose={() => setLedgerOpen(false)} lang={lang} />
      <SettingsScreen visible={settingsOpen} onClose={() => setSettingsOpen(false)}
        lang={lang} current={settings} onArmBrief={flow.armDailyBrief}
        onChange={(k: string, v?: unknown) => {
          if (k === "editVehicle") { setSettingsOpen(false); setVehicleOpen(true); return; }
          patchSettings({ [k]: v } as Partial<ShellSettings>);
        }} />
      <VehicleSheet visible={vehicleOpen || flow.needsVehicle} lang={lang}
        current={flow.vehicle}
        onDone={(p) => { flow.setVehicleProfile(p); setVehicleOpen(false); }}
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
  option, options, to, steps, camRef, lang, share, onExit, onTripDone,
}: {
  option: V2Option; options: V2Option[]; to: Place | null; steps: Step[] | null;
  camRef: React.RefObject<CameraRef | null>; lang: "en" | "hi";
  share: boolean; onExit: () => void;
  onTripDone: (t: { label: string; vehicle: string; doseUg: number | null; avoidedUg: number | null }) => void;
}) {
  const [summary, setSummary] = useState<NavSummary | null>(null);
  const worstDose = Math.max(...options.map((o) => o.dose?.mid ?? 0), 0);
  const worstOpt = worstDose > 0
    ? options.find((o) => (o.dose?.mid ?? 0) === worstDose) : undefined;
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
  navRef.current = nav;
  useEffect(() => {
    navRef.current.start();
    return () => { navRef.current.stop(); };
  }, []);

  if (summary) {
    const data: ReceiptData = {
      durationMin: summary.durationS / 60,
      modeLabel: option.label,
      doseUg: nav.stripOk === false ? null : summary.doseUg,
      co2Kg: summary.co2Kg,
      pm25G: summary.pm25G,
      worstDoseUg: worstDose > 0 ? worstDose : null,
      worstLabel: worstOpt?.label ?? null,
      alt: altEmit
        ? { label: altEmit.label, co2KgMid: altEmit.emissions?.co2_kg?.mid ?? null }
        : null,
      fieldAgeMin: nav.fieldAgeMin,
      donated: summary.donated,
    };
    return <ReceiptSheet data={data} lang={lang} onDone={onExit} />;
  }
  return (
    <NavChrome option={option} steps={steps} doseUg={0}
      nav={nav} onExit={() => nav.arrive()} lang={lang} />
  );
}

const s = StyleSheet.create({
  root: { flex: 1, backgroundColor: V2T.bg },
  pillWrap: { position: "absolute", top: 54, left: 16, right: 16 },
  locateWrap: { position: "absolute", right: 14, bottom: 40 },
  layersWrap: { position: "absolute", left: 14, bottom: 40 },
  offlineWrap: {
    position: "absolute", top: 112, alignSelf: "center",
    backgroundColor: V2T.surface2, borderRadius: V2Radius.row, paddingHorizontal: 12, paddingVertical: 6,
    borderWidth: 1, borderColor: V2T.line,
  },
  offlineTxt: { fontFamily: F.med, fontSize: V2Type.label, color: V2T.text2 },
  receipt: {
    position: "absolute", top: 116, alignSelf: "center",
    backgroundColor: V2T.surface, borderRadius: V2Radius.sheet, padding: 16,
    borderWidth: 1, borderColor: V2T.line, minWidth: 220,
    shadowColor: "#000", shadowOpacity: 0.5, shadowRadius: 16, shadowOffset: { width: 0, height: 4 },
    elevation: 10,
  },
  receiptTitle: { fontSize: V2Type.secondary, color: V2T.text },
  receiptNum: { fontFamily: F.semi, fontSize: V2Type.title, color: V2T.text },
  receiptSub: { fontFamily: F.reg, fontSize: V2Type.label, color: V2T.text2, marginTop: 4, maxWidth: 240 },
  intro: {
    position: "absolute", top: 0, bottom: 0, left: 0, right: 0,
    backgroundColor: "rgba(11,13,16,0.86)", alignItems: "center", justifyContent: "center", padding: 32,
  },
  introTitle: { fontSize: 26, color: V2T.text, textAlign: "center" },
  introBody: { fontSize: V2Type.secondary, color: V2T.text2, textAlign: "center", marginTop: 14, lineHeight: 22 },
  introBtn: { marginTop: 26, backgroundColor: V2T.accent, borderRadius: V2Radius.pill, paddingHorizontal: 30, paddingVertical: 12 },
  introBtnTxt: { fontSize: V2Type.body, color: V2T.text },
});
