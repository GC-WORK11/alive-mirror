/**
 * ALive-108 map module — v2 dark style, resolver, layer fragments, markers.
 * Handoff: docs/plan/map-style.md. Integration is one line:
 *   <Map mapStyle={v2StyleUrl()} …>
 */
export {
  v2Style,
  v2StyleUrl,
  v2RasterStyle,
  withVectorTiles,
  buildingLayers,
  roadGlowLayers,
  V2_TILES_ENV,
  V2_GLYPHS_ENV,
  V2_PMTILES_NAME,
  type V2MapStyleInput,
} from "./style";
export { DestPin, OriginPin, UserPuck } from "./markers";
