import React from "react";
import { GeoJSONSource, Layer } from "@maplibre/maplibre-react-native";

/** Community hazard reports — dust / smoke / burning / clean.
 * Muted earth tones; reports carry a 6h TTL server-side. */
export function ReportsLayer({ reports }: { reports: GeoJSON.FeatureCollection | null }) {
  if (!reports?.features?.length) return null;
  return (
    <GeoJSONSource id="reports" data={reports}>
      <Layer
        id="reportDots"
        type="circle"
        paint={{
          "circle-radius": 7,
          "circle-color": [
            "match", ["get", "kind"],
            "dust", "#b45309",
            "smoke", "#78716c",
            "burning", "#b91c1c",
            "#0f766e",
          ],
          "circle-opacity": 0.85,
          "circle-stroke-width": 2,
          "circle-stroke-color": "#ffffff",
        }}
      />
    </GeoJSONSource>
  );
}
