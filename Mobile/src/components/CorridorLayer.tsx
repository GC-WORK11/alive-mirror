import React, { useMemo } from "react";
import { GeoJSONSource, Layer } from "@maplibre/maplibre-react-native";
import { V2T } from "../theme";

type Corridor = { lon: number; lat: number; samples: number; avg_dose_ug: number; top_mode: string };

/* Source + layers stay mounted for the app's whole life — a mid-draw
   removeSource segfaults the iOS-sim render thread (same upstream class
   as RouteTint). The toggle swaps in an empty FeatureCollection instead
   of unmounting. */
const EMPTY: GeoJSON.FeatureCollection = { type: "FeatureCollection", features: [] };

/** Streets the community has actually measured — a faint veil that grows
 * denser where more traversals landed. Optional layer: `on` from the
 * layers sheet (doc 02 §S1 — off by default). */
function CorridorLayerFn({ corridors, on = true }: { corridors: Corridor[] | null; on?: boolean }) {
  const geo = useMemo(() => {
    if (!corridors?.length) return EMPTY;
    const max = Math.max(...corridors.map((c) => c.samples), 1);
    return {
      type: "FeatureCollection" as const,
      features: corridors.map((c) => ({
        type: "Feature" as const,
        geometry: { type: "Point" as const, coordinates: [c.lon, c.lat] },
        properties: { w: c.samples / max, mode: c.top_mode },
      })),
    };
  }, [corridors]);

  return (
    <GeoJSONSource id="corridors" data={on ? geo : EMPTY}>
      <Layer
        id="corridorGlow"
        type="circle"
        paint={{
          "circle-radius": ["interpolate", ["linear"], ["zoom"], 10, ["*", 26, ["get", "w"]], 15, ["*", 60, ["get", "w"]]],
          "circle-color": V2T.accent,
          "circle-opacity": 0.12,
          "circle-blur": 0.9,
        }}
      />
      <Layer
        id="corridorDots"
        type="circle"
        minzoom={12.5}
        paint={{
          "circle-radius": ["interpolate", ["linear"], ["zoom"], 12.5, 2.5, 15, 5],
          "circle-color": V2T.accent,
          "circle-opacity": 0.5,
          "circle-stroke-width": 1,
          "circle-stroke-color": V2T.surface,
        }}
      />
    </GeoJSONSource>
  );
}

/** memoized: the parent re-renders every poll tick; these
 *  map children only earn a commit when their own props move */
export const CorridorLayer = React.memo(CorridorLayerFn);
