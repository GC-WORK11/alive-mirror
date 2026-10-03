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
import { CigStrip, EndpointPin } from "./src/ui";
import { ReportsLayer } from "./src/components/ReportsLayer";
import { FiresLayer, BlackspotsLayer } from "./src/components/HazardLayers";
import { CorridorLayer } from "./src/components/CorridorLayer";
import { SearchBar } from "./src/components/shell/SearchBar";
import { SearchSheet } from "./src/components/shell/SearchSheet";
import { CompareSheet } from "./src/components/shell/CompareSheet";
import { NavChrome } from "./src/components/shell/NavChrome";
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
    setIntroSeen(new File(Paths.document, "intro_seen.txt").exists);
    return () => { clearInterval(iv); clearInterval(healthIv); };
  }, [setFrom, setTrips]);

  const patchSettings = useCallback((p: Partial<ShellSettings>) => {
    setSettings((s) => { const n = { ...s, ...p }; saveSettings(n); return n; });
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
  const dismissIntro = useCallback(() => {
    setIntroSeen(true);
    try { new File(Paths.document, "intro_seen.txt").write("1"); } catch {}
  }, []);

  if (!fontsLoaded) return null;
  const sel = flow.options[flow.selected];

  return (
    <View style={s.root}>
      <StatusBar style="light" />
      <Map mapStyle={STYLE_URL} style={StyleSheet.absoluteFill}
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
            value={phase === "search" ? flow.query : ""}
            placeholder={phase === "compare" && flow.to ? flow.to.name : undefined}
            searching={flow.searching} lang={lang}
            onMenu={() => setSidebarOpen(true)}
            onFocus={() => { if (phase !== "search") { flow.setEditWhich("to"); flow.setQuery(""); flow.setPhase("search"); } }}
            onChange={(q) => { flow.setQuery(q); flow.doSearch(q); }}
            onClear={phase === "compare" ? flow.clearRoute : undefined} />
          {phase === "search" && (
            <SearchSheet query={flow.query} results={flow.results} searching={flow.searching}
              recents={flow.recents} editWhich={flow.editWhich} from={flow.from} lang={lang}
              onToggleWhich={() => flow.setEditWhich(flow.editWhich === "from" ? "to" : "from")}
              onPick={flow.pick} />
          )}
        </View>
      )}
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
          onStart={flow.startNav} onClose={flow.clearRoute} lang={lang} />
      )}
      {phase === "nav" && sel && (
        <NavChrome option={sel} steps={flow.steps} doseUg={flow.navDose} onExit={flow.exitNav} lang={lang} />
      )}
      {flow.receipt && phase === "compare" && (
        <View style={s.receipt}>
          <Text style={[s.receiptTitle, { fontFamily: fam(lang, "semi") }]}>{t("tripDone", lang)}</Text>
          <View style={{ flexDirection: "row", alignItems: "center", gap: 10, marginTop: 4 }}>
            <CigStrip ug={flow.receipt.doseUg} size={18} color={V2T.text} />
            <Text style={[s.receiptNum, NUM]}>{Math.round(flow.receipt.doseUg * 10) / 10}</Text>
          </View>
          {flow.receipt.savedUg > 2 && (
            <Text style={s.receiptSub}>{t("receiptSaved", lang, { n: Math.round(flow.receipt.savedUg) })}</Text>
          )}
          <Pressable onPress={() => flow.setReceipt(null)} hitSlop={8} style={{ marginTop: 8 }}>
            <Text style={{ fontFamily: fam(lang, "med"), fontSize: V2Type.label, color: V2T.accent }}>{t("done", lang)}</Text>
          </Pressable>
        </View>
      )}

      <Sidebar open={sidebarOpen} onClose={() => setSidebarOpen(false)} trips={flow.trips} lang={lang}
        settings={settings} onSettings={patchSettings} onDeleteData={deleteAll}
        onArmBrief={flow.armDailyBrief} currentDest={flow.to}
        onNavigate={(p) => flow.pick({ ...p, subtitle: "" }, "to")} />
      <LayersSheet visible={layersOpen} values={layers} onToggle={toggleLayer}
        onClose={() => setLayersOpen(false)} lang={lang} />

      {introSeen === false && (
        <View style={s.intro}>
          <Text style={[s.introTitle, { fontFamily: fam(lang, "semi") }]}>{t("introTitle", lang)}</Text>
          <Text style={[s.introBody, { fontFamily: fam(lang, "reg") }]}>{t("introBody", lang)}</Text>
          <Pressable onPress={dismissIntro} style={s.introBtn}>
            <Text style={[s.introBtnTxt, { fontFamily: fam(lang, "semi") }]}>{t("introGotIt", lang)}</Text>
          </Pressable>
        </View>
      )}
    </View>
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
