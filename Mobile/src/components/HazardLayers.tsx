import React from "react";
import { GeoJSONSource, Layer } from "@maplibre/maplibre-react-native";
import { T } from "../theme";

/** Real fire pixels (NASA FIRMS VIIRS/MODIS, NCR + 150km ring, 6h cache).
 * Hollow-seasonal: renders only when satellites see something burn.
 * Radius follows fire-radiative-power; alpha follows confidence. */
export function FiresLayer({ fires }: { fires: GeoJSON.FeatureCollection | null }) {
  if (!fires?.features?.length) return null;
  return (
    <GeoJSONSource id="fires" data={fires}>
      <Layer
        id="firesHalo"
        type="circle"
        paint={{
          "circle-radius": [
            "interpolate", ["linear"], ["get", "frp"],
            0, 7, 60, 14, 200, 20,
          ],
          "circle-color": T.doseOver,
          "circle-opacity": 0.10,
          "circle-blur": 1,
        }}
      />
      <Layer
        id="firesCore"
        type="circle"
        paint={{
          "circle-radius": [
            "interpolate", ["linear"], ["zoom"],
            8, 2.5, 14, 5,
          ],
          "circle-color": T.doseOver,
          "circle-opacity": [
            "interpolate", ["linear"], ["get", "confidence_score"],
            0, 0.35, 0.7, 0.85, 1, 1,
          ],
        }}
      />
    </GeoJSONSource>
  );
}

/** Delhi Traffic Police crash-prone zones (official Crash Report zones,
 * geo'd from public lists). Kept out of the rest view — appears when you
 * zoom into street level, the same altitude where the risk applies. */
export function BlackspotsLayer({ spots }: { spots: GeoJSON.FeatureCollection | null }) {
  if (!spots?.features?.length) return null;
  return (
    <GeoJSONSource id="blackspots" data={spots}>
      <Layer
        id="blackspotsDot"
        type="circle"
        minzoom={11.5}
        paint={{
          "circle-radius": [
            "interpolate", ["linear"], ["zoom"],
            11.5, 3, 15, 6,
          ],
          "circle-color": [
            "match", ["get", "severity"],
            "high", T.doseOver,
            "medium", T.ink,
            T.paper,
          ],
          "circle-stroke-color": [
            "match", ["get", "severity"],
            "high", T.doseOver,
            T.ink,
          ],
          "circle-stroke-width": 1.5,
          "circle-opacity": 0.85,
        }}
      />
    </GeoJSONSource>
  );
}
