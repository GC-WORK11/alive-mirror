import React, { useMemo } from "react";
import { StyleSheet, Text, View } from "react-native";
import { GeoJSONSource, Layer, Marker } from "@maplibre/maplibre-react-native";
import { F, V2T } from "../theme";

// NOTE: the city field renders only inside "Delhi today" (doc 03 §map
// styling) — it is not part of the rest map. Kept here ready for the
// city-view lane; the rest shell no longer mounts it.

type Props = { grid: GeoJSON.FeatureCollection | null };
type Coord = { lon: number; lat: number };

/** Confidence → heat contribution. Thin coverage still shows, it just
 * pulls the surface down instead of drawing a patchy gap. */
const CONF_W: Record<string, number> = { hi: 1.0, med: 0.7, lo: 0.45 };

/** PM2.5 (µg/m³) → heatmap weight 0..1. ~280+ saturates — Delhi "very
 * poor"/severe band reads at full depth. */
function pmWeight(pm25: number, conf: string | undefined) {
  const base = Math.min(1, Math.max(0.06, pm25 / 280));
  return Math.min(1, base * (conf ? CONF_W[conf] ?? 0.7 : 0.7));
}

/** Ring centroid (shoelace). Falls back to the vertex average for
 * degenerate cells. */
function centroid(ring: number[][]): [number, number] {
  let a = 0;
  let cx = 0;
  let cy = 0;
  for (let i = 0; i < ring.length - 1; i++) {
    const x1 = ring[i][0];
    const y1 = ring[i][1];
    const x2 = ring[i + 1][0];
    const y2 = ring[i + 1][1];
    const t = x1 * y2 - x2 * y1;
    a += t;
    cx += (x1 + x2) * t;
    cy += (y1 + y2) * t;
  }
  if (Math.abs(a) > 1e-12) return [cx / (3 * a), cy / (3 * a)];
  const n = Math.max(1, ring.length - 1);
  let sx = 0;
  let sy = 0;
  for (let i = 0; i < ring.length - 1; i++) {
    sx += ring[i][0];
    sy += ring[i][1];
  }
  return [sx / n, sy / n];
}

function cellCentroid(g: GeoJSON.Geometry): [number, number] | null {
  if (g.type === "Polygon") return centroid(g.coordinates[0] as number[][]);
  if (g.type === "MultiPolygon" && g.coordinates[0]?.[0])
    return centroid(g.coordinates[0][0] as number[][]);
  if (g.type === "Point") return g.coordinates as [number, number];
  return null;
}

/** Live PM2.5 surface — one continuous translucent bloom over the
 * monochrome basemap, like a radar layer. Centroid points weighted by
 * pm25×confidence feed a heatmap; the raw cells stay underneath as a
 * whisper-faint fill so the field's true footprint stays honest. */
export function FieldLayer({ grid }: Props) {
  const points = useMemo<GeoJSON.FeatureCollection>(() => {
    const feats: GeoJSON.Feature[] = [];
    for (const f of grid?.features ?? []) {
      const c = f.geometry ? cellCentroid(f.geometry) : null;
      if (!c) continue;
      const p = (f.properties ?? {}) as { pm25?: number; conf?: string };
      feats.push({
        type: "Feature",
        properties: { w: pmWeight(typeof p.pm25 === "number" ? p.pm25 : 0, p.conf) },
        geometry: { type: "Point", coordinates: c },
      });
    }
    return { type: "FeatureCollection", features: feats };
  }, [grid]);

  if (!grid || !grid.features.length) return null;
  return (
    <>
      <GeoJSONSource id="fieldGrid" data={grid}>
        <Layer
          id="fieldFill"
          type="fill"
          paint={{
            "fill-color": [
              "interpolate", ["linear"], ["get", "pm25"],
              0, "rgba(138,147,163,0.05)",
              60, "rgba(138,147,163,0.07)",
              130, "rgba(176,118,59,0.10)",
              300, "rgba(138,45,62,0.14)",
            ],
            "fill-opacity": 0.9,
          }}
        />
      </GeoJSONSource>
      <GeoJSONSource id="fieldHeat" data={points}>
        <Layer
          id="fieldBloom"
          type="heatmap"
          paint={{
            "heatmap-weight": ["get", "w"],
            // cells spread apart with zoom — intensity and radius grow so
            // the surface stays continuous instead of separating into dots
            "heatmap-intensity": [
              "interpolate", ["linear"], ["zoom"],
              9, 0.9, 12, 1.4, 15, 2.3,
            ],
            "heatmap-radius": [
              "interpolate", ["linear"], ["zoom"],
              9, 26, 12, 48, 15, 88,
            ],
            "heatmap-opacity": 0.5,
            "heatmap-opacity-transition": { duration: 600 },
            // transparent → warm breath ramp (doc 03), translucent so the
            // basemap's streets and labels read through
            "heatmap-color": [
              "interpolate", ["linear"], ["heatmap-density"],
              0, "rgba(138,147,163,0)",
              0.15, "rgba(138,147,163,0.20)",
              0.35, "rgba(176,118,59,0.34)",
              0.55, "rgba(179,83,85,0.46)",
              0.75, "rgba(138,45,62,0.56)",
              1, "rgba(122,32,52,0.66)",
            ],
          }}
        />
      </GeoJSONSource>
    </>
  );
}

const SLATE = "#1e293b";

function Pin({ letter, color }: { letter: string; color: string }) {
  return (
    <View style={pin.wrap}>
      <View style={[pin.tail, { backgroundColor: color }]} />
      <View style={[pin.head, { backgroundColor: color }]}>
        <Text style={pin.letter}>{letter}</Text>
      </View>
    </View>
  );
}

const pin = StyleSheet.create({
  wrap: { width: 30, height: 34, alignItems: "center" },
  head: {
    width: 28,
    height: 28,
    borderRadius: 14,
    alignItems: "center",
    justifyContent: "center",
    borderWidth: 1.5,
    borderColor: "#ffffff",
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.28,
    shadowRadius: 2,
    elevation: 3,
  },
  // square rotated into a diamond, tucked behind the head → teardrop tail
  tail: {
    position: "absolute",
    left: 8,
    top: 20,
    width: 14,
    height: 14,
    transform: [{ rotate: "45deg" }],
  },
  letter: {
    color: "#ffffff",
    fontFamily: F.semi,
    fontSize: 13,
    includeFontPadding: false,
    marginTop: -1,
  },
});

/** A/B endpoint markers — real teardrop pins like Google Maps (accent A,
 * dark-slate B), drawn with plain Views so no image assets are needed.
 * `anchor="bottom"` drops the tail tip on the coordinate. */
export function EndpointPins({ a, b }: { a: Coord | null; b: Coord | null }) {
  if (!a && !b) return null;
  return (
    <>
      {a && (
        <Marker lngLat={[a.lon, a.lat]} anchor="bottom">
          <Pin letter="A" color={V2T.accent} />
        </Marker>
      )}
      {b && (
        <Marker lngLat={[b.lon, b.lat]} anchor="bottom">
          <Pin letter="B" color={SLATE} />
        </Marker>
      )}
    </>
  );
}
