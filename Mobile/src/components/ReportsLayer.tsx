import React from "react";
import { StyleSheet, View } from "react-native";
import { Marker } from "@maplibre/maplibre-react-native";
import { Icon, reportGlyph } from "../icons";
import { V2T } from "../theme";

/** Community hazard reports posted by other riders — each renders as ITS
 * pictograph (dust swirl / smoke plume / flame / leaf), never a dot.
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
              <Icon name={reportGlyph(kind)} color={severe ? V2T.breath3 : V2T.text2} size={18} />
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
    backgroundColor: V2T.surface, alignItems: "center", justifyContent: "center",
    borderWidth: 1, borderColor: V2T.line,
    shadowColor: "#000", shadowOpacity: 0.16, shadowRadius: 3, shadowOffset: { width: 0, height: 1 },
    elevation: 3,
  },
  wrapSevere: { borderColor: V2T.breath3 },
});
