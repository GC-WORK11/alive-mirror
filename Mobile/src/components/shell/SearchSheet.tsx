/** Search overlay — results sheet under the bar.
 * SEAM(search): the spec S2 full-screen search (keyboard-first, Home/Work
 * rows, "Choose on map" / "Your location", on-device index <16ms) lands
 * with the src/screens + src/search lanes. This keeps the existing
 * behaviour: local gazetteer hits instantly, remote results merge in. */
import React from "react";
import { ActivityIndicator, Pressable, StyleSheet, Text, View } from "react-native";
import { F, V2Radius, V2T, V2Type, fam } from "../../theme";
import { Icon } from "../../icons";
import { t, type Lang } from "../../i18n/strings";
import type { Place } from "./types";

export function SearchSheet({
  query, results, searching, recents, editWhich, from, onToggleWhich, onPick, lang,
}: {
  query: string;
  results: Place[] | null;
  searching: boolean;
  recents: Place[];
  editWhich: "to" | "from";
  from: Place | null;
  onToggleWhich: () => void;
  onPick: (p: Place) => void;
  lang: Lang;
}) {
  const list = results ?? (query.trim().length < 2 ? recents : []);
  return (
    <View>
      {/* origin row — quiet; tap to switch which endpoint is being edited */}
      <Pressable style={s.originRow} onPress={onToggleWhich}>
        <View style={s.originDot} />
        <Text style={s.originTxt} numberOfLines={1}>
          {t("fromLabel", lang)}: <Text style={{ color: V2T.text }}>{from?.name ?? t("yourLocation", lang)}</Text>
        </Text>
        <Text style={s.originEdit}>{editWhich === "from" ? t("editingLabel", lang) : t("changeLabel", lang)}</Text>
      </Pressable>
      {editWhich === "from" && <Text style={s.searchHint}>{t("fromHint", lang)}</Text>}

      <View style={s.resultsSheet}>
        {list.map((p, i) => (
          <Pressable key={`${p.lat},${p.lon},${i}`} onPress={() => onPick(p)}
            style={({ pressed }) => [s.result, pressed && { opacity: 0.55 }]}>
            <Icon name="pin" color={V2T.text3} size={16} />
            <View style={{ flex: 1, marginLeft: 10 }}>
              <Text style={[s.rname, { fontFamily: fam(lang, "med") }]} numberOfLines={1}>{p.name}</Text>
              {!!p.subtitle && <Text style={s.rsub} numberOfLines={1}>{p.subtitle}</Text>}
            </View>
            {p.outside_ncr && <Text style={s.outsideTag}>{t("outsideDelhi", lang)}</Text>}
          </Pressable>
        ))}
        {results && results.length === 0 && !searching && (
          <Text style={s.noResults}>{t("noResults", lang)}</Text>
        )}
        {searching && !results?.length && (
          <View style={{ paddingVertical: 14, alignItems: "center" }}>
            <ActivityIndicator size="small" color={V2T.accent} />
          </View>
        )}
      </View>
    </View>
  );
}

const s = StyleSheet.create({
  originRow: {
    flexDirection: "row", alignItems: "center", marginTop: 6,
    backgroundColor: V2T.surface, borderRadius: V2Radius.row,
    paddingHorizontal: 14, paddingVertical: 9,
    borderWidth: 1, borderColor: V2T.line,
  },
  originDot: { width: 8, height: 8, borderRadius: 4, borderWidth: 2, borderColor: V2T.accent, marginRight: 8 },
  originTxt: { flex: 1, fontFamily: F.reg, fontSize: V2Type.label, color: V2T.text2 },
  originEdit: { fontFamily: F.med, fontSize: V2Type.label, color: V2T.accent },
  searchHint: { fontFamily: F.reg, fontSize: V2Type.label, color: V2T.text3, marginTop: 6, marginLeft: 6 },
  resultsSheet: {
    marginTop: 6, backgroundColor: V2T.surface, borderRadius: V2Radius.row,
    borderWidth: 1, borderColor: V2T.line,
    shadowColor: "#000", shadowOpacity: 0.4, shadowRadius: 10, shadowOffset: { width: 0, height: 3 },
    elevation: 6, overflow: "hidden",
  },
  result: {
    flexDirection: "row", alignItems: "center",
    paddingHorizontal: 14, paddingVertical: 12,
    borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: V2T.line,
  },
  rname: { fontSize: V2Type.secondary, color: V2T.text },
  rsub: { fontFamily: F.reg, fontSize: V2Type.label, color: V2T.text3, marginTop: 1 },
  outsideTag: { fontFamily: F.med, fontSize: 10, color: V2T.text3, marginLeft: 8, flexShrink: 1 },
  noResults: { fontFamily: F.reg, fontSize: V2Type.label, color: V2T.text3, padding: 16, textAlign: "center" },
});
