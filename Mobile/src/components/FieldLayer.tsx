import React from "react";
import { GeoJSONSource, Layer } from "@maplibre/maplibre-react-native";

type Props = { grid: GeoJSON.FeatureCollection | null };

/** Live PM2.5 surface — cells from GET /grid (or /grid?h=N for the
 * forecast horizon). Heat-bloom ramp on the dark canvas; fill opacity
 * follows the cell's confidence so thin coverage fades honestly. */
export function FieldLayer({ grid }: Props) {
  if (!grid || !grid.features.length) return null;
  return (
    <GeoJSONSource id="fieldGrid" data={grid}>
      <Layer
        id="fieldFill"
        type="fill"
        paint={{
          "fill-color": [
            "interpolate", ["linear"], ["get", "pm25"],
            0, "rgba(148,163,184,0.05)",
            60, "rgba(148,163,184,0.09)",
            130, "rgba(251,113,133,0.22)",
            300, "rgba(225,29,72,0.34)",
          ],
          "fill-opacity": ["match", ["get", "conf"], "hi", 1.0, "med", 0.55, 0.3],
        }}
      />
    </GeoJSONSource>
  );
}
