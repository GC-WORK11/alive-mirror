/** Rest-map search bar — ☰ inside the left edge, "Where to?" field.
 * Rest state is a pressable pill; focusing turns it into the live input
 * that drives the search overlay (SEAM(search): src/screens/search lane). */
import React from "react";
import { Pressable, StyleSheet, Text, TextInput, View } from "react-native";
import { F, V2Radius, V2T, V2Type, fam } from "../../theme";
import { Icon } from "../../icons";
import { t, type Lang } from "../../i18n/strings";

export function SearchBar({
  value, placeholder, searching, lang,
  onMenu, onFocus, onChange, onClear,
}: {
  value: string;
  placeholder?: string;            // e.g. destination name during compare
  searching?: boolean;
  lang: Lang;
  onMenu: () => void;
  onFocus: () => void;
  onChange: (q: string) => void;
  onClear?: () => void;            // compare-phase X — clears the route
}) {
  return (
    <View style={s.bar}>
      <Pressable onPress={onMenu} hitSlop={10} style={s.menuBtn}
        accessibilityRole="button" accessibilityLabel={t("a11yMenu", lang)}>
        <Icon name="menu" color={V2T.text2} size={20} />
      </Pressable>
      <TextInput
        style={[s.input, { fontFamily: fam(lang, "med") }]}
        placeholder={placeholder ?? t("searchPlaceholder", lang)}
        placeholderTextColor={V2T.text3}
        autoCorrect={false}
        autoCapitalize="none"
        value={value}
        onFocus={onFocus}
        onChangeText={onChange}
        returnKeyType="search"
        clearButtonMode="while-editing"
      />
      {searching ? <Text style={s.hint}>{t("searchingLabel", lang)}</Text> : null}
      {onClear ? (
        <Pressable onPress={onClear} hitSlop={10} style={s.clearBtn} accessibilityRole="button">
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
    backgroundColor: V2T.surface, borderRadius: V2Radius.pill, height: 52,
    paddingHorizontal: 8, paddingRight: 16,
    borderWidth: 1, borderColor: V2T.line,
    shadowColor: "#000", shadowOpacity: 0.4, shadowRadius: 10, shadowOffset: { width: 0, height: 3 },
    elevation: 6,
  },
  menuBtn: {
    width: 38, height: 38, borderRadius: 19,
    alignItems: "center", justifyContent: "center", marginRight: 2,
  },
  input: { flex: 1, fontSize: V2Type.body, color: V2T.text, paddingVertical: 0, paddingHorizontal: 6 },
  hint: { fontFamily: F.reg, fontSize: V2Type.label, color: V2T.text3, maxWidth: 90 },
  clearBtn: { width: 30, height: 30, borderRadius: 15, alignItems: "center", justifyContent: "center" },
});
