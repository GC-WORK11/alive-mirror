import React, { useMemo } from "react";
import { GeoJSONSource, Layer } from "@maplibre/maplibre-react-native";
import { V2T } from "../theme";

type Corridor = { lon: number; lat: number; samples: number; avg_dose_ug: number; top_mode: string };

/** Streets the community has actually measured — a faint veil that grows
 * denser where more traversals landed. Optional layer: rendered only when
 * the layers sheet switches it on (doc 02 §S1 — off by default). */
export function CorridorLayer({ corridors }: { corridors: Corridor[] | null }) {
  const geo = useMemo(() => {
    if (!corridors?.length) return null;
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

  if (!geo) return null;
  return (
    <GeoJSONSource id="corridors" data={geo}>
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
