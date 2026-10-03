/**
 * ALive-108 map markers — pin + user puck (doc 03 §icons/map pins).
 * Vector-drawn in-repo on react-native-svg (no bundled PNGs, no unlicensed
 * assets). Reference .svg sources live in Mobile/assets/map/ for design
 * review; these components are the runtime copies.
 *
 * Use inside `<Marker lngLat={…}>` children — the same pattern App.tsx
 * already uses for EndpointPin. Drop-in replacements:
 *   origin  → <OriginPin />   (white ring + accent dot)
 *   dest    → <DestPin />     (red pinlet #E5484D, anchor="bottom")
 *   user    → <UserPuck />    (if a custom puck is wanted over <UserLocation>)
 */
import React from "react";
import Svg, { Circle, G, Path } from "react-native-svg";
import { V2T } from "../theme";

// Markers render ON the map surface — these are map-context constants,
// not app-theme tokens. The basemap is light: knock-outs read as paper,
// rings read as white (industry-standard puck/pin convention).
const ONMAP_FILL = "#FDFDFB";  // pin knock-outs = paper-white
const ONMAP_RING = "#FFFFFF";  // ring strokes — white puck ring convention

/** Destination pinlet — rounded teardrop with a knocked-out hole.
 *  Anchor at bottom tip: use <Marker anchor="bottom">. */
export function DestPin({ size = 34, color = V2T.pinDest }: { size?: number; color?: string }) {
  return (
    <Svg width={size} height={size * 1.375} viewBox="0 0 32 44">
      <Path
        fill={color}
        d="M16 1.5C8.6 1.5 2.5 7.6 2.5 15c0 10.2 13.5 27.5 13.5 27.5S29.5 25.2 29.5 15C29.5 7.6 23.4 1.5 16 1.5z"
      />
      <Circle cx={16} cy={15} r={5.5} fill={ONMAP_FILL} />
    </Svg>
  );
}

/** Origin marker — light ring, accent dot (doc 03: "origin white ring"). */
export function OriginPin({ size = 22 }: { size?: number }) {
  return (
    <Svg width={size} height={size} viewBox="0 0 22 22">
      <Circle cx={11} cy={11} r={9.2} fill={ONMAP_FILL} stroke="#3D4452" strokeWidth={1.8} />
      <Circle cx={11} cy={11} r={3.6} fill={V2T.accent} />
    </Svg>
  );
}

/** User-location puck — soft halo, rotating heading beam, light-ring accent
 *  dot. `heading` is degrees clockwise from north (GNSS course >2 m/s,
 *  compass otherwise — doc 04 §4). Halo is always upright; only the beam
 *  rotates. */
export function UserPuck({ size = 48, heading = 0 }: { size?: number; heading?: number }) {
  return (
    <Svg width={size} height={size} viewBox="0 0 48 48">
      <Circle cx={24} cy={24} r={21} fill={V2T.accent} opacity={0.16} />
      {/* heading beam — 60° wedge pointing up, rotated by course */}
      <G rotation={heading} origin="24, 24">
        <Path d="M24 24 L15 8.4 A18 18 0 0 1 33 8.4 Z" fill={V2T.accent} opacity={0.35} />
      </G>
      <Circle cx={24} cy={24} r={8.5} fill={V2T.accent} stroke={ONMAP_RING} strokeWidth={3} />
    </Svg>
  );
}
