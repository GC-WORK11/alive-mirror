import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  ActivityIndicator,
  Keyboard,
  Platform,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import { StatusBar } from "expo-status-bar";
import { BlurView } from "expo-blur";
import {
  Camera,
  GeoJSONSource,
  Layer,
  Map,
  type CameraRef,
} from "@maplibre/maplibre-react-native";

// EXPO_PUBLIC_API_URL overrides (e.g. deployed backend or LAN IP for a real
// device); otherwise the Android emulator reaches the host via 10.0.2.2.
const API =
  process.env.EXPO_PUBLIC_API_URL ??
  Platform.select({
    android: "http://10.0.2.2:8000",
    default: "http://localhost:8000",
  });

const STYLE_URL = "https://tiles.openfreemap.org/styles/positron";
const DELHI: [number, number] = [77.209, 28.6139];

type Place = { name: string; subtitle: string; lat: number; lon: number };
type Which = "from" | "to";
type Route = { distance_km: number; duration_min: number; geometry: GeoJSON.Geometry };
type Mode = "driving" | "cycling" | "walking";

const MODES: { key: Mode; label: string }[] = [
  { key: "driving", label: "Drive" },
  { key: "cycling", label: "Cycle" },
  { key: "walking", label: "Walk" },
];

export default function App() {
  const camRef = useRef<CameraRef>(null);
  const [from, setFrom] = useState<Place | null>(null);
  const [to, setTo] = useState<Place | null>(null);
  const [fromText, setFromText] = useState("");
  const [toText, setToText] = useState("");
  const [active, setActive] = useState<Which | null>(null);
  const [results, setResults] = useState<Place[]>([]);
  const [searching, setSearching] = useState(false);
  const [routes, setRoutes] = useState<Route[]>([]);
  const [mode, setMode] = useState<Mode>("driving");
  const [loadingRoute, setLoadingRoute] = useState(false);
  const [apiOk, setApiOk] = useState<boolean | null>(null);
  const debounce = useRef<ReturnType<typeof setTimeout> | null>(null);
  const searchSeq = useRef(0);

  useEffect(() => {
    fetch(`${API}/health`)
      .then((r) => setApiOk(r.ok))
      .catch(() => setApiOk(false));
  }, []);

  const doSearch = useCallback((text: string) => {
    if (debounce.current) clearTimeout(debounce.current);
    if (text.trim().length < 2) {
      setResults([]);
      setSearching(false);
      return;
    }
    setSearching(true);
    const seq = ++searchSeq.current;
    debounce.current = setTimeout(async () => {
      try {
        const r = await fetch(`${API}/search?q=${encodeURIComponent(text)}&limit=8`);
        const j = await r.json();
        if (seq !== searchSeq.current) return;
        setResults(j.results ?? []);
      } catch {
        if (seq === searchSeq.current) setResults([]);
      } finally {
        if (seq === searchSeq.current) setSearching(false);
      }
    }, 180);
  }, []);

  const pick = useCallback(
    (p: Place) => {
      if (active === "from") {
        setFrom(p);
        setFromText(p.name);
      } else if (active === "to") {
        setTo(p);
        setToText(p.name);
      }
      setActive(null);
      setResults([]);
      Keyboard.dismiss();
      camRef.current?.flyTo({ center: [p.lon, p.lat], zoom: 14, duration: 900 });
    },
    [active]
  );

  const swap = useCallback(() => {
    const f = from;
    const ft = fromText;
    setFrom(to);
    setFromText(toText);
    setTo(f ?? null);
    setToText(ft);
  }, [from, to, fromText, toText]);

  // fetch routes when both endpoints set or mode changes
  useEffect(() => {
    if (!from || !to) return;
    let cancelled = false;
    const load = async () => {
      setLoadingRoute(true);
      try {
        const r = await fetch(
          `${API}/route?from_lat=${from.lat}&from_lon=${from.lon}&to_lat=${to.lat}&to_lon=${to.lon}&profile=${mode}`
        );
        const j = await r.json();
        if (cancelled) return;
        const rs: Route[] = j.routes ?? [];
        setRoutes(rs);
        if (rs[0]?.geometry?.type === "LineString") {
          const coords = (rs[0].geometry as GeoJSON.LineString).coordinates;
          const lons = coords.map((c) => c[0]);
          const lats = coords.map((c) => c[1]);
          camRef.current?.fitBounds(
            [Math.min(...lons), Math.min(...lats), Math.max(...lons), Math.max(...lats)],
            { padding: { top: 230, bottom: 170, left: 60, right: 60 }, duration: 700 }
          );
        }
      } catch {
        if (!cancelled) setRoutes([]);
      } finally {
        if (!cancelled) setLoadingRoute(false);
      }
    };
    load();
    return () => {
      cancelled = true;
    };
  }, [from, to, mode]);

  const routeFeature = useMemo<GeoJSON.Feature | null>(() => {
    if (!routes[0]) return null;
    return {
      type: "Feature",
      properties: {},
      geometry: routes[0].geometry,
    };
  }, [routes]);

  const markers = useMemo<GeoJSON.FeatureCollection>(() => {
    const feats: GeoJSON.Feature[] = [];
    if (from)
      feats.push({
        type: "Feature",
        properties: { kind: "from" },
        geometry: { type: "Point", coordinates: [from.lon, from.lat] },
      });
    if (to)
      feats.push({
        type: "Feature",
        properties: { kind: "to" },
        geometry: { type: "Point", coordinates: [to.lon, to.lat] },
      });
    return { type: "FeatureCollection", features: feats };
  }, [from, to]);

  return (
    <View style={s.root}>
      <StatusBar style="dark" />
      <Map mapStyle={STYLE_URL} style={StyleSheet.absoluteFill}>
        <Camera
          ref={camRef}
          initialViewState={{ center: DELHI, zoom: 11 }}
          maxBounds={[76.75, 28.15, 77.95, 28.98]}
        />
        <GeoJSONSource id="route" data={routeFeature ?? { type: "FeatureCollection", features: [] }}>
          <Layer
            id="route-casing"
            type="line"
            paint={{ "line-color": "#0f766e", "line-width": 7, "line-opacity": 0.22 }}
            layout={{ "line-cap": "round", "line-join": "round" }}
          />
          <Layer
            id="route-line"
            type="line"
            paint={{ "line-color": "#0d9488", "line-width": 4 }}
            layout={{ "line-cap": "round", "line-join": "round" }}
          />
        </GeoJSONSource>
        <GeoJSONSource id="markers" data={markers}>
          <Layer
            id="endpoint"
            type="circle"
            paint={{
              "circle-radius": 8,
              "circle-color": ["match", ["get", "kind"], "from", "#0d9488", "#e11d48"],
              "circle-stroke-width": 3,
              "circle-stroke-color": "#ffffff",
            }}
          />
        </GeoJSONSource>
      </Map>

      {/* search card */}
      <View style={s.cardWrap}>
        <BlurView intensity={60} tint="light" style={s.card}>
          <View style={s.row}>
            <View style={[s.dot, { backgroundColor: "#0d9488" }]} />
            <TextInput
              style={s.input}
              placeholder="From — anywhere in Delhi NCR"
              placeholderTextColor="#94a3b8"
              autoCorrect={false}
              autoCapitalize="none"
              value={fromText}
              onFocus={() => setActive("from")}
              onChangeText={(t) => {
                setFromText(t);
                setFrom(null);
                setRoutes([]);
                setActive("from");
                doSearch(t);
              }}
              returnKeyType="search"
              clearButtonMode="while-editing"
            />
            <Pressable onPress={swap} style={s.swap} hitSlop={8}>
              <Text style={s.swapTxt}>⇅</Text>
            </Pressable>
          </View>
          <View style={s.div} />
          <View style={s.row}>
            <View style={[s.dot, { backgroundColor: "#e11d48" }]} />
            <TextInput
              style={s.input}
              placeholder="To — anywhere in Delhi NCR"
              placeholderTextColor="#94a3b8"
              autoCorrect={false}
              autoCapitalize="none"
              value={toText}
              onFocus={() => setActive("to")}
              onChangeText={(t) => {
                setToText(t);
                setTo(null);
                setRoutes([]);
                setActive("to");
                doSearch(t);
              }}
              returnKeyType="search"
              clearButtonMode="while-editing"
            />
            {searching && <ActivityIndicator size="small" color="#64748b" />}
          </View>
        </BlurView>

        {active && results.length > 0 && (
          <BlurView intensity={70} tint="light" style={[s.card, { marginTop: 8 }]}>
            {results.map((p, i) => (
              <Pressable
                key={`${p.lat},${p.lon},${i}`}
                onPress={() => pick(p)}
                style={({ pressed }) => [s.result, pressed && { opacity: 0.6 }]}
              >
                <Text style={s.pin}>◉</Text>
                <View style={{ flex: 1 }}>
                  <Text style={s.rname} numberOfLines={1}>{p.name}</Text>
                  {!!p.subtitle && (
                    <Text style={s.rsub} numberOfLines={1}>{p.subtitle}</Text>
                  )}
                </View>
              </Pressable>
            ))}
          </BlurView>
        )}
      </View>

      {/* status chip */}
      <View style={s.statusWrap} pointerEvents="none">
        <View style={s.statusChip}>
          <View
            style={[
              s.statusDot,
              { backgroundColor: apiOk === null ? "#f59e0b" : apiOk ? "#22c55e" : "#ef4444" },
            ]}
          />
          <Text style={s.statusTxt}>
            {apiOk === null ? "connecting" : apiOk ? "live Delhi data" : "server offline"}
          </Text>
        </View>
      </View>

      {/* route summary + mode chips */}
      {(from && to) && (
        <View style={s.bottomWrap}>
          <BlurView intensity={60} tint="light" style={s.chipRow}>
            {MODES.map((m) => (
              <Pressable
                key={m.key}
                onPress={() => setMode(m.key)}
                style={[s.mchip, mode === m.key && s.mchipOn]}
              >
                <Text style={[s.mchipTxt, mode === m.key && s.mchipTxtOn]}>{m.label}</Text>
              </Pressable>
            ))}
          </BlurView>
          <BlurView intensity={60} tint="light" style={s.summary}>
            {loadingRoute ? (
              <ActivityIndicator size="small" color="#0f766e" />
            ) : routes[0] ? (
              <View style={{ alignItems: "center" }}>
                <Text style={s.summaryMain}>
                  {routes[0].duration_min} min · {routes[0].distance_km} km
                </Text>
                <Text style={s.summarySub}>
                  {routes.length > 1 ? `${routes.length} routes found · ` : ""}real OSM road graph
                </Text>
              </View>
            ) : (
              <Text style={s.summarySub}>no route found</Text>
            )}
          </BlurView>
        </View>
      )}
    </View>
  );
}

const s = StyleSheet.create({
  root: { flex: 1, backgroundColor: "#f1f5f9" },
  cardWrap: {
    position: "absolute",
    top: Platform.select({ ios: 60, android: 40 }),
    left: 16,
    right: 16,
  },
  card: {
    borderRadius: 22,
    overflow: "hidden",
    backgroundColor: "rgba(255,255,255,0.55)",
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: "rgba(15,23,42,0.08)",
  },
  row: { flexDirection: "row", alignItems: "center", paddingHorizontal: 16, paddingVertical: 13 },
  dot: { width: 10, height: 10, borderRadius: 5, marginRight: 12 },
  input: { flex: 1, fontSize: 16, color: "#0f172a", padding: 0 },
  swap: { marginLeft: 8, padding: 4 },
  swapTxt: { fontSize: 17, color: "#64748b" },
  div: { height: StyleSheet.hairlineWidth, backgroundColor: "rgba(15,23,42,0.12)", marginHorizontal: 16 },
  result: {
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: 16,
    paddingVertical: 11,
    gap: 10,
  },
  pin: { color: "#0d9488", fontSize: 13 },
  rname: { fontSize: 15, fontWeight: "600", color: "#0f172a" },
  rsub: { fontSize: 12, color: "#64748b", marginTop: 1 },
  statusWrap: { position: "absolute", top: Platform.select({ ios: 108, android: 88 }), alignSelf: "center" },
  statusChip: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    backgroundColor: "rgba(255,255,255,0.8)",
    paddingHorizontal: 10,
    paddingVertical: 5,
    borderRadius: 999,
  },
  statusDot: { width: 7, height: 7, borderRadius: 4 },
  statusTxt: { fontSize: 11, color: "#475569", fontWeight: "600", letterSpacing: 0.2 },
  bottomWrap: { position: "absolute", bottom: 34, left: 16, right: 16, gap: 10 },
  chipRow: {
    flexDirection: "row",
    borderRadius: 999,
    overflow: "hidden",
    backgroundColor: "rgba(255,255,255,0.55)",
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: "rgba(15,23,42,0.08)",
    padding: 4,
  },
  mchip: { flex: 1, paddingVertical: 9, borderRadius: 999, alignItems: "center" },
  mchipOn: { backgroundColor: "#0f172a" },
  mchipTxt: { fontSize: 13, fontWeight: "600", color: "#475569" },
  mchipTxtOn: { color: "#fff" },
  summary: {
    borderRadius: 20,
    overflow: "hidden",
    backgroundColor: "rgba(255,255,255,0.6)",
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: "rgba(15,23,42,0.08)",
    paddingVertical: 14,
    paddingHorizontal: 16,
  },
  summaryMain: { fontSize: 20, fontWeight: "700", color: "#0f172a", fontVariant: ["tabular-nums"] },
  summarySub: { fontSize: 12, color: "#64748b", marginTop: 2 },
});
