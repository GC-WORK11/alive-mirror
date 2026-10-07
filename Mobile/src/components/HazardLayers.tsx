import React from "react";
import { GeoJSONSource, Layer } from "@maplibre/maplibre-react-native";
import { V2T } from "../theme";

/* Sources + layers stay mounted for the app's whole life: unmounting a
   GeoJSONSource issues removeSource/removeLayer on the native style, and
   when that lands mid-draw on the iOS-sim render thread it segfaults
   (same upstream MapLibre class as RouteTint and the markers). The layer
   switch and empty data alike swap in an empty FeatureCollection — one
   no-op native call, draws nothing, removes nothing. */
const EMPTY: GeoJSON.FeatureCollection = { type: "FeatureCollection", features: [] };

/** Real fire pixels (NASA FIRMS VIIRS/MODIS, NCR + 150km ring, 6h cache).
 * Optional layer — `on` from the layers sheet decides visibility.
 * Radius follows fire-radiative-power; alpha follows confidence. */
function FiresLayerFn({ fires, on = true }: { fires: GeoJSON.FeatureCollection | null; on?: boolean }) {
  return (
    <GeoJSONSource id="fires" data={on && fires ? fires : EMPTY}>
      <Layer
        id="firesHalo"
        type="circle"
        paint={{
          "circle-radius": [
            "interpolate", ["linear"], ["get", "frp"],
            0, 7, 60, 14, 200, 20,
          ],
          "circle-color": V2T.breath3,
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
          "circle-color": V2T.breath3,
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
 * geo'd from public lists). Optional layer — `on` from the layers sheet;
 * fades in at street level where the risk applies. */
function BlackspotsLayerFn({ spots, on = true }: { spots: GeoJSON.FeatureCollection | null; on?: boolean }) {
  return (
    <GeoJSONSource id="blackspots" data={on && spots ? spots : EMPTY}>
      <Layer
        id="blackspotsDot"
        type="circle"
        minzoom={11.5}
        paint={{
          /* audit #4: 3–6 px dots read as sub-pixel noise on a city
             view — bump into the tappable-looking range */
          "circle-radius": [
            "interpolate", ["linear"], ["zoom"],
            11.5, 4.5, 15, 8,
          ],
          "circle-color": [
            "match", ["get", "severity"],
            "high", V2T.breath3,
            "medium", V2T.text2,
            V2T.text3,
          ],
          "circle-stroke-color": [
            "match", ["get", "severity"],
            "high", V2T.breath3,
            V2T.bg,
          ],
          "circle-stroke-width": 1.5,
          "circle-opacity": 0.85,
        }}
      />
    </GeoJSONSource>
  );
}

/** memoized: the parent re-renders every poll tick; these
 *  map children only earn a commit when their own props move */
export const FiresLayer = React.memo(FiresLayerFn);

/** memoized: the parent re-renders every poll tick; these
 *  map children only earn a commit when their own props move */
export const BlackspotsLayer = React.memo(BlackspotsLayerFn);
