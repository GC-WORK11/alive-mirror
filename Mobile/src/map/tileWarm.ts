/**
 * Basemap prefetch — warms the offline tile store once per install so panning
 * the service area is instant instead of streaming tiles over the live
 * network (and the demo map keeps working if venue connectivity dies).
 *
 * How: `OfflineManager.createPack` is handed the SAME v2-light style the map
 * renders, but as an http(s) URL — `${API_BASE}/v2-light.json`, served by
 * the API (server/static/v2-light.json is byte-identical to the bundled
 * Mobile/src/map/v2-light.json). The earlier rev wrote the style to the
 * cache dir and passed a file:// URL, which iOS tolerated but Android's
 * Mbgl-HttpRequest rejected outright ("Unable to parse resourceUrl
 * file://…") — the region row existed forever with region_tiles=0 and the
 * pack never downloaded (docs/lanes/offline-walk-report.md).
 *
 * The pack is the OpenFreeMap planet source the app already renders — same
 * tiles, just moved to disk. Warming is gated on the bundled style: if a
 * `EXPO_PUBLIC_TILES_URL` env or a local delhi.pmtiles resolves the map to
 * a different source, the served style would warm the wrong tiles, so the
 * pack is skipped (ambient cache still works like before).
 *
 * Sizing (measured 7 Oct 2026, OFM central-Delhi tiles ≈85–165 KB):
 *   NCR bbox z9–z13 ≈ ~630 tiles ≈ 40–55 MB worst case (outer-NCR tiles are
 *   sparse, real figure is lower). z14 is deliberately excluded — that level
 *   alone is ~1.7k tiles/~200 MB; z14+ detail streams live and sticks in the
 *   ambient cache like today. Ambient ceiling is raised to 160 MB so the
 *   pack plus everyday browsing can't evict each other.
 *
 * Fails silently: if the style endpoint, offline DB or download errors, the
 * app is exactly as before — the map streams from the hosted source.
 */
import { OfflineManager } from "@maplibre/maplibre-react-native";
import { API_BASE } from "../search/client";
import { NCR_BOUNDS } from "../search/t0";
import { v2Style, type V2MapStyleInput } from "./style";

const PACK_NAME = "delhi-ncr-z9-13-r2";
/** The file://-style pack rev. Its region row sits empty in the offline DB
 *  (0 tiles, unfetchable style_url) — deleted on sight so a device that ran
 *  the old build doesn't keep the dead row and skip the working pack. */
const LEGACY_PACK_NAME = "delhi-ncr-z9-13-r1";
/* NCR_BOUNDS imported from search/t0 — single-sourced to the server's
   v2/deps.NCR_BBOX / tiles.py _BOUNDS (the region row below already
   carried exactly this box). */
const MIN_ZOOM = 9;
const MAX_ZOOM = 13;
const STYLE_PATH = "/v2-light.json";
const AMBIENT_MAX_BYTES = 160 * 1024 * 1024;

let started = false;

/** Fire-and-forget from App once the map has settled. Runs once per launch;
 *  a second launch sees the stored pack and does nothing. */
export function warmBasemap(style: V2MapStyleInput): void {
  // Only the bundled default style can warm the pack — it is the style the
  // server hosts byte-for-byte. Any env/pmtiles override resolves to a
  // different object and the served style would warm the wrong source.
  if (started || style !== v2Style || !API_BASE.startsWith("http")) return;
  started = true;
  void warm().catch(() => {});
}

async function warm(): Promise<void> {
  try {
    await OfflineManager.setMaximumAmbientCacheSize(AMBIENT_MAX_BYTES);
  } catch {
    // ambient size is a nicety — keep going without it
  }
  try {
    const packs = await OfflineManager.getPacks();
    const legacy = packs.find((p) => p.metadata?.name === LEGACY_PACK_NAME);
    if (legacy) {
      try {
        await OfflineManager.deletePack(legacy.id);
      } catch {
        // dead row stays — harmless: the r2 pack installs beside it
      }
    }
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
        mapStyle: `${API_BASE}${STYLE_PATH}`,
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
