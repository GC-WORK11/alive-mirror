/**
 * ALive-108 v2 light map style — OpenMapTiles schema, Google Maps palette
 * (pixel-sampled light palette: grey land, cyan water, green parks, yellow
 * arterials, white streets; docs/plan/map-style.md).
 *
 * Basemap chain (env → local → hosted → raster):
 *   1. `EXPO_PUBLIC_TILES_URL` — vector tiles the sibling lane is building for
 *      Delhi. Accepts a TileJSON URL ("https://…/tiles.json"), a PMTiles URL
 *      ("pmtiles://https://…/delhi.pmtiles"), a local file
 *      ("pmtiles://file:///…/delhi.pmtiles" or plain "file://…"), or an
 *      {z}/{x}/{y}.pbf tile template.
 *   2. Local `delhi.pmtiles` in the document dir (downloaded/OBB copy) or in the
 *      app bundle — wired into the same style via the pmtiles:// protocol.
 *   3. The bundled `v2-light.json` itself, whose source defaults to the hosted
 *      OpenFreeMap planet tiles — identical data to the style the app already
 *      renders today, so this is a drop-in upgrade, not a regression.
 *   4. `v2RasterStyle` — last-resort raster style for the integrator to swap in
 *      when every vector endpoint fails (e.g. onDidFailLoadingMap / offline
 *      detection). Documented in map-style.md; not auto-selected since the
 *      resolver can't observe network failure synchronously.
 *
 * `EXPO_PUBLIC_GLYPHS_URL` overrides the glyphs template for fully-offline
 * bundles (the only remote dependency left in the JSON — see map-style.md).
 */
import { File, Paths } from "expo-file-system";
import type { LayerSpecification, StyleSpecification } from "@maplibre/maplibre-react-native";
import v2LightJson from "./v2-light.json";

/* Gesture-drop label set — the basemap's expensive symbol layers. They
   stay in v2-light.json (the style's single source of truth, and what
   the served /v2-light.json + offline-pack style_url describe) but are
   STRIPPED from the mounted style object here and re-added by App.tsx
   as React <Layer> children — only a React-mounted layer's visibility
   can flip without a full style reload, and hiding the label set while
   the user drags removes MapLibre's per-frame collision/text-layout
   pass (the dominant gesture cost on mid hardware). Geometry — every
   road, casing, building, park fill — stays painted during the gesture;
   the names return the frame the camera rests. Selection: all symbol
   layers EXCEPT the place-* set (cities/neighbourhoods are the
   orientation anchors a reader tracks while panning — Google keeps
   them too) and except the app's own overlays. */
const GESTURE_LABEL_IDS = new Set([
  "v2-water-name", "v2-waterway-name",
  "v2-oneway", "v2-housenumber", "v2-park-label",
  "v2-aeroway-label", "v2-peak",
  "v2-road-label-major", "v2-road-label-minor",
  "v2-poi-transit", "v2-poi-civic", "v2-poi-services",
  "v2-poi-gate", "v2-poi-text",
]);

const allLayers = v2LightJson.layers as unknown as LayerSpecification[];

/** The self-contained v2 light style minus the gesture-drop label set.
 *  Valid MapLibre style spec v8 object — pass straight to
 *  `<Map mapStyle={…}>` (MLRN accepts objects or URLs). */
export const v2Style = {
  ...(v2LightJson as unknown as StyleSpecification),
  layers: allLayers.filter((l) => !GESTURE_LABEL_IDS.has(l.id)),
};

/* MLRN divergence: a few spec-scalar layout props are array-typed on the
   React side (`iconPadding: number[]` — the Android setter reads a float
   array and FATALs on a bare Double: UnexpectedNativeTypeException at
   first map mount, offline-verify Android crash). The bundled JSON keeps
   the spec scalar (correct — the served style + native parser want it);
   the React-mounted copies wrap it so the same value reaches the layer. */
const RN_ARRAY_LAYOUT_PROPS = new Set([
  "icon-padding", "icon-text-fit-padding",
  "icon-offset", "icon-translate", "text-offset", "text-translate",
]);
const rnSpec = (l: LayerSpecification): LayerSpecification => {
  const layout = (l as { layout?: Record<string, unknown> }).layout;
  if (!layout) return l;
  let out: Record<string, unknown> | null = null;
  for (const k of RN_ARRAY_LAYOUT_PROPS) {
    const v = layout[k];
    if (typeof v === "number") (out ??= { ...layout })[k] = [v];
  }
  return out ? ({ ...l, layout: out } as LayerSpecification) : l;
};

/** The stripped set, mounted by the map tree as React layers so their
 *  visibility can flip mid-session. Original JSON order preserved —
 *  collision priority among them is unchanged. */
export const gestureLabelLayers: LayerSpecification[] =
  allLayers.filter((l) => GESTURE_LABEL_IDS.has(l.id)).map(rnSpec);

export type V2MapStyleInput = string | StyleSpecification;

/** Env var the Delhi-PMTiles lane sets to point the style at its tiles. */
export const V2_TILES_ENV = "EXPO_PUBLIC_TILES_URL";
/** Env var overriding the remote glyph server (offline bundles). */
export const V2_GLYPHS_ENV = "EXPO_PUBLIC_GLYPHS_URL";
/** File name the tiles lane drops into Paths.document / Paths.bundle. */
export const V2_PMTILES_NAME = "delhi.pmtiles";

/** Layer-spec fragments the integrator composes into any MapLibre styleJSON
 *  on the OpenMapTiles schema (they reference `source: "openmaptiles"`).
 *
 *  `buildingLayers`: flat building fill (z≥14) + fill-extrusion (z≥15,
 *  #E5E2D9/#DDDAD1, height from `render_height`/`height`, base
 *  `render_min_height`, extrusion opacity 0.55 — docs/plan/map-style-r4.md).
 */
export const buildingLayers: LayerSpecification[] = v2Style.layers.filter((l) =>
  l.id === "v2-building-flat" || l.id === "v2-building-extrusion");

/** `roadGlowLayers`: the arterial emphasis trio — soft glow halo + dark casing
 *  + bright inner for motorway/trunk. Insert before (below) the rest of the
 *  road stack when composing into another styleJSON. When transplanting onto a
 *  non-OMT source (e.g. Amazon Location's themed sources), re-point
 *  `layer.source` / `layer["source-layer"]` — see map-style.md. */
export const roadGlowLayers: LayerSpecification[] = v2Style.layers.filter((l) =>
  l.id === "v2-road-arterial-glow" ||
  l.id === "v2-road-motorway-casing" ||
  l.id === "v2-road-motorway");

/** Emergency raster fallback — lightly desaturated OSM tiles on the Google
 *  land tone. Swap in via `<Map mapStyle={v2RasterStyle}>` when the vector
 *  chain is unreachable. */
export const v2RasterStyle: StyleSpecification = {
  version: 8,
  name: "ALive-108 raster fallback",
  sources: {
    osm: {
      type: "raster",
      tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
      tileSize: 256,
      maxzoom: 19,
      attribution: "© OpenStreetMap contributors",
    },
  },
  layers: [
    { id: "raster-bg", type: "background", paint: { "background-color": "#F2F1EE" } },
    {
      id: "raster-osm",
      type: "raster",
      source: "osm",
      paint: {
        // pull OSM's saturated cartography toward Google's quieter light look
        "raster-saturation": -0.25,
        "raster-contrast": -0.05,
      },
    },
  ],
};

/**
 * Returns a copy of `v2Style` re-pointed at `tilesUrl`.
 *  - `pmtiles://…` or a `file://…pmtiles` URI → `source.url` (MapLibre Native
 *    resolves the pmtiles:// protocol itself).
 *  - `…/{z}/{x}/{y}…` template → `source.tiles`.
 *  - anything else → `source.url` (TileJSON endpoint).
 */
export function withVectorTiles(tilesUrl: string, glyphsUrl?: string): StyleSpecification {
  const style = JSON.parse(JSON.stringify(v2Style)) as StyleSpecification;
  const src = (style.sources as Record<string, { type: string; url?: string; tiles?: string[] }>)
    .openmaptiles;
  if (/^pmtiles:\/\//i.test(tilesUrl) || /\.pmtiles(\?|$)/i.test(tilesUrl)) {
    delete src.tiles;
    src.url = tilesUrl.startsWith("pmtiles://") ? tilesUrl : `pmtiles://${tilesUrl}`;
  } else if (tilesUrl.includes("{z}")) {
    delete src.url;
    src.tiles = [tilesUrl];
  } else {
    delete src.tiles;
    src.url = tilesUrl;
  }
  // direct member access required — Expo inlines EXPO_PUBLIC_* at build time
  const glyphs = glyphsUrl ?? process.env.EXPO_PUBLIC_GLYPHS_URL;
  if (glyphs) style.glyphs = glyphs;
  return style;
}

/**
 * Resolves what to pass to `<Map mapStyle={…}>`.
 * Chain: `EXPO_PUBLIC_TILES_URL` → local `delhi.pmtiles` → bundled style
 * (hosted OpenFreeMap tiles). Never throws; worst case returns `v2Style`.
 */
export function v2StyleUrl(): V2MapStyleInput {
  const env = process.env.EXPO_PUBLIC_TILES_URL;
  if (env) return withVectorTiles(env);
  for (const base of [Paths.document, Paths.bundle]) {
    try {
      const f = new File(base, V2_PMTILES_NAME);
      if (f.exists) return withVectorTiles(`pmtiles://${f.uri}`);
    } catch {
      // path not readable on this platform — fall through to next candidate
    }
  }
  return v2Style;
}

const LATIN_NAME = ["coalesce", ["get", "name:latin"], ["get", "name_en"], ["get", "name"], ["get", "ref"]];

/* per-layer latin collapse — shared by latinLabels (whole style) and
   gestureLabelLayersLatin (the React-mounted set) */
const latinLayer = (l: LayerSpecification): LayerSpecification => {
  const layout = (l as { layout?: Record<string, unknown> }).layout;
  const tf = layout?.["text-field"];
  if (!layout || tf == null || !JSON.stringify(tf).includes("name:hi")) return l;
  return { ...l, layout: { ...layout, "text-field": LATIN_NAME } } as LayerSpecification;
};

/** English-default labels: every bilingual (latin + name:hi) text-field
 *  collapses to its latin name, so no Devanagari reaches the English map.
 *  URL inputs pass through untouched (nothing to rewrite client-side). */
export function latinLabels(input: V2MapStyleInput): V2MapStyleInput {
  if (typeof input === "string") return input;
  return {
    ...input,
    layers: input.layers.map(latinLayer),
  };
}

/** The gesture set's EN variant — the same name:hi collapse the mounted
 *  style gets (3 of the 14 reference name:hi). */
export const gestureLabelLayersLatin: LayerSpecification[] =
  gestureLabelLayers.map(latinLayer);
