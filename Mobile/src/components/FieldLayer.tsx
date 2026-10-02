import React from "react";
import { GeoJSONSource, Layer } from "@maplibre/maplibre-react-native";

type Props = { grid: GeoJSON.FeatureCollection | null };

/** Live PM2.5 surface — cells from GET /grid, single-hue ramp,
 * alpha kept low so the base map stays readable. */
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
            0, "rgba(100,116,139,0.06)",
            60, "rgba(100,116,139,0.10)",
            130, "rgba(194,65,92,0.15)",
            300, "rgba(127,29,29,0.22)",
          ],
          "fill-outline-color": "rgba(255,255,255,0.15)",
        }}
      />
    </GeoJSONSource>
  );
}
