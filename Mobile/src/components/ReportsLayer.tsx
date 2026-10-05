import React from "react";
import { StyleSheet, View } from "react-native";
import { Marker } from "@maplibre/maplibre-react-native";
import { Icon, reportGlyph } from "../icons";
import { V2T } from "../theme";
import { DELHI } from "./shell/net";

export const REPORT_POOL = 40;
const PARKED = DELHI as [number, number];

export type ReportSlot = { coord: [number, number]; kind: string };

/** Assign the live reports to fixed marker slots — a PURE reducer called
 *  where the poll result is handled (a setState updater, event context —
 *  never during render). A coordinate keeps its slot across polls; dead
 *  ones free their slot for reuse; overflow is dropped, never faked. */
export function reconcileReportSlots(
  prev: (ReportSlot | null)[], reports: GeoJSON.FeatureCollection | null,
): (ReportSlot | null)[] {
  const alive = new Map<string, string>();
  for (const f of reports?.features ?? []) {
    if (f.geometry?.type !== "Point") continue;
    const [lon, lat] = f.geometry.coordinates as [number, number];
    if (!Number.isFinite(lon) || !Number.isFinite(lat)) continue;
    alive.set(`${lon.toFixed(5)},${lat.toFixed(5)}`, (f.properties?.kind as string) ?? "dust");
  }
  const byCoord = new Map<string, number>();
  const next = prev.map((s, i) => {
    if (!s) return null;
    const key = `${s.coord[0].toFixed(5)},${s.coord[1].toFixed(5)}`;
    if (alive.has(key)) { byCoord.set(key, i); return s; }
    return null;
  });
  const reserved = new Set(byCoord.values());
  let changed = next.some((s, i) => s !== prev[i]);
  for (const [key, kind] of alive) {
    let i = byCoord.get(key);
    if (i == null) {
      i = next.findIndex((s, j) => s == null && !reserved.has(j));
      if (i === -1) break;                     // pool exhausted — drop, never fake
      byCoord.set(key, i);
      reserved.add(i);
      const [lon, lat] = key.split(",").map(Number);
      next[i] = { coord: [lon, lat], kind };
      changed = true;
    } else if (next[i]!.kind !== kind) {
      next[i] = { ...next[i]!, kind };
      changed = true;
    }
  }
  return changed ? next : prev;
}

/** Community hazard reports posted by other riders — each renders as ITS
 * pictograph (dust swirl / smoke plume / flame / leaf), never a dot.
 * Reports carry a 6h TTL server-side.
 *
 * CRASH-GUARD (same class as the endpoint pins in App.tsx): mounting or
 * unmounting a <Marker> issues add/removeAnnotation mid-draw on the iOS-
 * sim render thread — the residual SIGSEGV that kept killing the app at
 * the 60 s poll and at sheet commits. So REPORT_POOL Marker slots mount
 * ONCE at the map's first paint and never unmount: an assignment only
 * mutates a slot's lngLat + child, computed by reconcileReportSlots where
 * the poll lands. Dead slots render an empty child parked at Delhi. */
export function ReportsLayer({ slots }: { slots: (ReportSlot | null)[] }) {
  return (
    <>
      {slots.map((s, i) => (
        <Marker key={`rep-${i}`} lngLat={s?.coord ?? PARKED} anchor="center">
          {s ? (
            <View style={[st.wrap, s.kind === "burning" && st.wrapSevere]}>
              <Icon name={reportGlyph(s.kind)} color={s.kind === "burning" ? V2T.breath3 : V2T.text2} size={18} />
            </View>
          ) : (
            <View />
          )}
        </Marker>
      ))}
    </>
  );
}

const st = StyleSheet.create({
  wrap: {
    width: 30, height: 30, borderRadius: 15,
    backgroundColor: V2T.surface, alignItems: "center", justifyContent: "center",
    borderWidth: 1, borderColor: V2T.line,
  },
  wrapSevere: { borderColor: V2T.breath3 },
});
