/**
 * Basemap prefetch — warms the offline tile store once per install so panning
 * the service area is instant instead of streaming tiles over the live
 * network (and the demo map keeps working if venue connectivity dies).
 *
 * How: the resolved style object is written to the cache dir and handed to
 * `OfflineManager.createPack` as a file:// style URL; MapLibre then fetches
 * every tile the pack covers in the background. The pack is the OpenFreeMap
 * planet source the app already renders — same tiles, just moved to disk.
 *
 * Sizing (measured 7 Oct 2026, OFM central-Delhi tiles ≈85–165 KB):
 *   NCR bbox z9–z13 ≈ ~630 tiles ≈ 40–55 MB worst case (outer-NCR tiles are
 *   sparse, real figure is lower). z14 is deliberately excluded — that level
 *   alone is ~1.7k tiles/~200 MB; z14+ detail streams live and sticks in the
 *   ambient cache like today. Ambient ceiling is raised to 160 MB so the
 *   pack plus everyday browsing can't evict each other.
 *
 * Fails silently: if the offline DB or download errors, the app is exactly
 * as before — the map streams from the hosted source.
 */
import { File, Paths } from "expo-file-system";
import { OfflineManager } from "@maplibre/maplibre-react-native";
import type { V2MapStyleInput } from "./style";

const PACK_NAME = "delhi-ncr-z9-13-r1";
/** NCR service bbox — same as v2/deps.NCR_BBOX / tiles.py _BOUNDS. */
const NCR_BOUNDS: [number, number, number, number] = [76.8, 28.2, 77.9, 28.95];
const MIN_ZOOM = 9;
const MAX_ZOOM = 13;
const STYLE_FILE = "alive-v2-style.json";
const AMBIENT_MAX_BYTES = 160 * 1024 * 1024;

let started = false;

/** Fire-and-forget from App once the map has settled. Runs once per launch;
 *  a second launch sees the stored pack and does nothing. */
export function warmBasemap(style: V2MapStyleInput): void {
  if (started || typeof style === "string") return;
  started = true;
  void warm(style).catch(() => {});
}

async function warm(style: V2MapStyleInput): Promise<void> {
  try {
    await OfflineManager.setMaximumAmbientCacheSize(AMBIENT_MAX_BYTES);
  } catch {
    // ambient size is a nicety — keep going without it
  }
  try {
    const f = new File(Paths.cache, STYLE_FILE);
    if (!f.exists) f.create({ intermediates: true });
    f.write(JSON.stringify(style));
    const mapStyle = f.uri.startsWith("file://") ? f.uri : `file://${f.uri}`;
    const packs = await OfflineManager.getPacks();
    const existing = packs.find((p) => p.metadata?.name === PACK_NAME);
    if (existing) {
      try {
        const st = await existing.status();
        if (st.state === "inactive") await existing.resume();
      } catch {
        // status() unsupported/stale pack — leave it
      }
      return;
    }
    await OfflineManager.createPack(
      {
        mapStyle,
        bounds: NCR_BOUNDS,
        minZoom: MIN_ZOOM,
        maxZoom: MAX_ZOOM,
        metadata: { name: PACK_NAME },
      },
      () => {},
      () => {},
    );
  } catch {
    // offline DB unavailable (e.g. fresh sim, stripped native lib) — the
    // basemap still streams from the network; nothing else to do.
  }
}
