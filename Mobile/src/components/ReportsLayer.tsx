import React from "react";
import { StyleSheet, View } from "react-native";
import { Marker } from "@maplibre/maplibre-react-native";
import { Icon, reportGlyph } from "../icons";
import { T } from "../theme";

/** Community hazard reports — each report renders as ITS pictograph
 * (dust swirl / smoke plume / flame / leaf), never a generic dot.
 * Reports carry a 6h TTL server-side. */
export function ReportsLayer({ reports }: { reports: GeoJSON.FeatureCollection | null }) {
  if (!reports?.features?.length) return null;
  return (
    <>
      {reports.features.map((f, i) => {
        if (f.geometry?.type !== "Point") return null;
        const [lon, lat] = f.geometry.coordinates as [number, number];
        const kind = (f.properties?.kind as string) ?? "dust";
        const severe = kind === "burning";
        return (
          <Marker key={`${lon},${lat},${i}`} lngLat={[lon, lat]} anchor="center">
            <View style={[st.wrap, severe && st.wrapSevere]}>
              <Icon name={reportGlyph(kind)} color={severe ? T.doseOver : T.ink} size={18} />
            </View>
          </Marker>
        );
      })}
    </>
  );
}

const st = StyleSheet.create({
  wrap: {
    width: 30, height: 30, borderRadius: 15,
    backgroundColor: T.surface, alignItems: "center", justifyContent: "center",
    borderWidth: StyleSheet.hairlineWidth, borderColor: T.hairline,
    shadowColor: "#000", shadowOpacity: 0.12, shadowRadius: 3, shadowOffset: { width: 0, height: 1 },
    elevation: 3,
  },
  wrapSevere: { borderColor: T.doseOver, borderWidth: 1 },
});
