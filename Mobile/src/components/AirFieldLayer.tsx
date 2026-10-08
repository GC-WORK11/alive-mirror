import React, { useMemo } from "react";
import { GeoJSONSource, Layer } from "@maplibre/maplibre-react-native";
import { V2T, bandInkIdx } from "../theme";

export type AirStation = { lat: number; lon: number; name?: string | null };

/* Source + layers stay mounted for the app's whole life — a mid-draw
   removeSource/removeLayer segfaults the iOS-sim render thread (same
   upstream class as CorridorLayer/RouteTint). Data swaps happen inside
   the mounted source; an empty collection is the "off" state, never an
   unmount. */
const EMPTY: GeoJSON.FeatureCollection = { type: "FeatureCollection", features: [] };

/** The served PM2.5 field painted onto the map — the air map's reason
 *  to exist. Cell polygons tinted by their own CPCB band at an alpha
 *  scaled by the cell's confidence (the same honest texture city.html
 *  paints: unsure cells whisper, sure cells speak — and at the same
 *  strengths the web hero uses: .92/.60/.34 — the audit's .55/.38/.20
 *  tints read as a sepia basemap, not air). Seated under the
 *  road + label stack (`beforeId`) so streets and names stay crisp on
 *  top of the field — the Google-traffic seat, not a film over
 *  everything. The µg/m³ value each cell reports floats on it like
 *  instrument readouts; collisions declutter the density for free.
 *
 *  The numbers are the field's blended read — what the instruments'
 *  kriged blend says the air is there — and the station dots mark where
 *  the real monitors sit. Nothing is invented: no cell, no dot, no
 *  label exists that the server didn't serve.
 */
function AirFieldLayerFn({
  field,
  stations,
  gesturing = false,
  on = true,
}: {
  field: GeoJSON.FeatureCollection | null;
  stations: AirStation[] | null;
  /* true while the user drags/pinches — the two symbol layers (the
     biggest per-frame cost the field adds) drop with the basemap's
     label set and return on rest. The cells' fill + station rings
     stay painted: the field IS the surface. */
  gesturing?: boolean;
  /* the owner's air-gate: the field only paints while air intent is
     active — the air-map surface, a place's air detail, an air answers
     sheet. Every other map surface stays plain basemap. Empty-collection
     swap only (the mounted-source contract); the polled field still
     lands so the next ON paints instantly, stale-free. */
  on?: boolean;
}) {
  const cells = useMemo(() => {
    if (!field?.features?.length) return EMPTY;
    return {
      type: "FeatureCollection" as const,
      features: field.features.map((f) => {
        const p = (f.properties ?? {}) as Record<string, unknown>;
        const v = p.pm25;
        return {
          ...f,
          properties: {
            ...p,
            /* pre-rendered label — a numeric prop through to-string
               loses the decimal the web shows ("89.3" for "89"), and
               reading "89" is honest: the cell's number rounded */
            pm:
              typeof v === "number" && Number.isFinite(v)
                ? String(Math.round(v))
                : "",
          },
        };
      }),
    };
  }, [field]);

  const stGeo = useMemo(() => {
    if (!stations?.length) return EMPTY;
    return {
      type: "FeatureCollection" as const,
      features: stations
        .filter(
          (s) =>
            typeof s?.lat === "number" && typeof s?.lon === "number" &&
            Number.isFinite(s.lat) && Number.isFinite(s.lon),
        )
        .map((s) => ({
          type: "Feature" as const,
          geometry: { type: "Point" as const, coordinates: [s.lon, s.lat] },
          properties: { sname: typeof s.name === "string" ? s.name : "" },
        })),
    };
  }, [stations]);

  return (
    <>
      <GeoJSONSource id="airfield" data={on ? cells : EMPTY}>
        {/* the field itself — band colour per cell, alpha by cell conf;
            beforeId seats it above land/buildings but under every road
            and label (v2-road-tunnel is the first transportation layer)
            so the tint can never mud the street names */}
        <Layer
          id="airfieldCells"
          type="fill"
          beforeId="v2-road-tunnel"
          paint={{
            /* CPCB breaks — the one place band colour is mandatory */
            "fill-color": [
              "step",
              ["get", "pm25"],
              V2T.band0,
              30, V2T.band1,
              60, V2T.band2,
              90, V2T.band3,
              120, V2T.band4,
              250, V2T.band5,
            ],
            /* the web hero's CONF_A verbatim — the field must read as
               air, not as a tinted basemap: hi .92 / med .60 / lo .34 */
            "fill-opacity": [
              "match",
              ["get", "conf"],
              "hi", 0.92,
              "med", 0.60,
              "lo", 0.34,
              0.45,
            ],
          }}
        />
        {/* the mesh itself — each cell edged in its own band's inked hue
            (bandInkIdx = the band colour pulled 15% toward ink, same as
            the app's chips). Even a one-band day keeps the instrument
            grid visible instead of a flat wash, and a band change draws
            a real contour seam between neighbours */}
        <Layer
          id="airfieldEdges"
          type="line"
          beforeId="v2-road-tunnel"
          paint={{
            "line-color": [
              "step",
              ["get", "pm25"],
              bandInkIdx(0),
              30, bandInkIdx(1),
              60, bandInkIdx(2),
              90, bandInkIdx(3),
              120, bandInkIdx(4),
              250, bandInkIdx(5),
            ],
            "line-width": [
              "interpolate",
              ["linear"],
              ["zoom"],
              9, 0.4,
              13, 0.9,
              17, 1.6,
            ],
            "line-opacity": 0.55,
          }}
        />
        {/* each cell's read in µg/m³ — the instruments' numbers, not a
            legend's guess; MapLibre's collision pass thins them at
            lower zooms so they never stack into noise */}
        <Layer
          id="airfieldValues"
          type="symbol"
          beforeId="v2-place-city"
          minzoom={10.5}
          layout={{
            visibility: gesturing ? "none" : "visible",
            "text-field": ["get", "pm"],
            "text-font": ["Noto Sans Regular"],
            "text-size": [
              "interpolate",
              ["linear"],
              ["zoom"],
              10.5, 10,
              14, 13,
              17, 15,
            ],
            "text-padding": 4,
          }}
          paint={{
            "text-color": "#3B362E",
            "text-halo-color": "#F4F2EA",
            "text-halo-width": 1.2,
            "text-halo-blur": 0.4,
          }}
        />
      </GeoJSONSource>
      {/* the instruments themselves — quiet ring markers so a reader can
          see the field is anchored to real monitors, not drawn from air */}
      <GeoJSONSource id="airStations" data={on ? stGeo : EMPTY}>
        <Layer
          id="airStationDots"
          type="circle"
          beforeId="v2-place-city"
          paint={{
            "circle-radius": [
              "interpolate",
              ["linear"],
              ["zoom"],
              10, 2.4,
              14, 3.6,
            ],
            "circle-color": "#FAFAF7",
            "circle-opacity": 0.9,
            "circle-stroke-width": 1.4,
            "circle-stroke-color": "#3B362E",
            "circle-stroke-opacity": 0.7,
          }}
        />
        {/* names only in close — at city zoom they'd be 54 competing
            labels; zoomed to a neighbourhood the instrument names
            itself */}
        <Layer
          id="airStationNames"
          type="symbol"
          beforeId="v2-place-city"
          minzoom={14.5}
          layout={{
            visibility: gesturing ? "none" : "visible",
            "text-field": ["get", "sname"],
            "text-font": ["Noto Sans Regular"],
            "text-size": 10,
            "text-offset": [0, 0.85],
            "text-anchor": "top",
            "text-optional": true,
          }}
          paint={{
            "text-color": "#4A4E57",
            "text-halo-color": "#F4F2EA",
            "text-halo-width": 1.1,
            "text-halo-blur": 0.4,
          }}
        />
      </GeoJSONSource>
    </>
  );
}

/** memoized: the parent re-renders every poll tick; these map children
 *  only earn a commit when their own props move */
export const AirFieldLayer = React.memo(AirFieldLayerFn);
