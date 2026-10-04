/** Rest-map search bar — ☰ inside the left edge, "Where to?" pill.
 * The bar is a button, not an input: pressing opens the S2 full-screen
 * search (src/screens/SearchScreen) which owns the keyboard and query
 * (docs/plan/02 §S1–S2). */
import React from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { V2Radius, V2T, V2Type, fam } from "../../theme";
import { DYNAMIC_TYPE } from "../../a11y";
import { tick } from "../../haptics";
import { Icon } from "../../icons";
import { t, type Lang } from "../../i18n/strings";

export function SearchBar({
  label, lang,
  onMenu, onPress, onClear,
}: {
  label?: string;                   // e.g. destination name during compare
  lang: Lang;
  onMenu: () => void;
  onPress: () => void;
  onClear?: () => void;             // compare-phase X — clears the route
}) {
  return (
    <View style={s.bar}>
      <Pressable onPress={() => { tick(); onMenu(); }} hitSlop={10} style={s.menuBtn}
        accessibilityRole="button" accessibilityLabel={t("a11yMenu", lang)}>
        <Icon name="menu" color={V2T.text2} size={20} />
      </Pressable>
      <Pressable onPress={() => { tick(); onPress(); }} style={s.field}
        accessibilityRole="button" accessibilityLabel={label ?? t("searchPlaceholder", lang)}>
        <Text {...DYNAMIC_TYPE} numberOfLines={1}
          style={[s.input, { fontFamily: fam(lang, "med") }, !label && { color: V2T.text3 }]}>
          {label ?? t("searchPlaceholder", lang)}
        </Text>
      </Pressable>
      {onClear ? (
        <Pressable onPress={() => { tick(); onClear(); }} hitSlop={10} style={s.clearBtn} accessibilityRole="button"
          accessibilityLabel={t("a11yClear", lang)}>
          <Icon name="close" color={V2T.text3} size={16} />
        </Pressable>
      ) : (
        <Icon name="search" color={V2T.text3} size={18} />
      )}
    </View>
  );
}

const s = StyleSheet.create({
  bar: {
    flexDirection: "row", alignItems: "center",
    backgroundColor: V2T.glassFaint, borderRadius: V2Radius.pill, height: 52,
    paddingHorizontal: 8, paddingRight: 16,
    borderWidth: 1, borderColor: V2T.glassLine,
    shadowColor: "#000", shadowOpacity: 0.11, shadowRadius: 12, shadowOffset: { width: 0, height: 3 },
    elevation: 6,
  },
  menuBtn: {
    width: 38, height: 38, borderRadius: 19,
    alignItems: "center", justifyContent: "center", marginRight: 2,
  },
  field: { flex: 1, justifyContent: "center", alignSelf: "stretch", paddingHorizontal: 6 },
  input: { fontSize: V2Type.body, color: V2T.text },
  clearBtn: { width: 30, height: 30, borderRadius: 15, alignItems: "center", justifyContent: "center" },
});
