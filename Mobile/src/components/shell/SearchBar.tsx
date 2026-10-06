/** Rest-map search bar — ☰ inside the left edge, "Where to?" pill.
 * The bar is a button, not an input: pressing opens the S2 full-screen
 * search (src/screens/SearchScreen) which owns the keyboard and query
 * (docs/plan/02 §S1–S2). */
import React from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { V2Elev, V2Radius, V2T, V2Type, fam } from "../../theme";
import { DYNAMIC_TYPE } from "../../a11y";
import { tick } from "../../haptics";
import { Icon } from "../../icons";
import { t, type Lang } from "../../i18n/strings";

function SearchBarInner({
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
      <Pressable onPress={() => { tick(); onMenu(); }} hitSlop={10}
        accessibilityRole="button" accessibilityLabel={t("a11yMenu", lang)}
        style={({ pressed }) => [s.menuBtn, pressed && { opacity: 0.55 }]}>
        <Icon name="menu" color={V2T.text2} size={20} />
      </Pressable>
      <Pressable onPress={() => { tick(); onPress(); }} accessibilityRole="button"
        accessibilityLabel={label ?? t("searchPlaceholder", lang)}
        style={({ pressed }) => [s.field, pressed && { opacity: 0.65 }]}>
        <Text {...DYNAMIC_TYPE} numberOfLines={1} adjustsFontSizeToFit minimumFontScale={0.75}
          style={[s.input, { fontFamily: fam(lang, "med") }, !label && { color: V2T.text3 }]}>
          {label ?? t("searchPlaceholder", lang)}
        </Text>
      </Pressable>
      {onClear ? (
        <Pressable onPress={() => { tick(); onClear(); }} hitSlop={10} accessibilityRole="button"
          accessibilityLabel={t("a11yClear", lang)}
          style={({ pressed }) => [s.clearBtn, pressed && { opacity: 0.55 }]}>
          <Icon name="close" color={V2T.text3} size={16} />
        </Pressable>
      ) : (
        <Icon name="search" color={V2T.text3} size={18} />
      )}
    </View>
  );
}

export const SearchBar = React.memo(SearchBarInner);

const s = StyleSheet.create({
  bar: {
    ...V2Elev.float,
    flexDirection: "row", alignItems: "center",
    backgroundColor: V2T.glassDeep, borderRadius: V2Radius.pill, height: 54,
    paddingHorizontal: 8, paddingRight: 16,
  },
  menuBtn: {
    width: 38, height: 38, borderRadius: V2Radius.pill,
    alignItems: "center", justifyContent: "center", marginRight: 2,
  },
  field: { flex: 1, justifyContent: "center", alignSelf: "stretch", paddingHorizontal: 6 },
  input: { fontSize: V2Type.body, color: V2T.text },
  clearBtn: { width: 30, height: 30, borderRadius: V2Radius.row, alignItems: "center", justifyContent: "center" },
});
