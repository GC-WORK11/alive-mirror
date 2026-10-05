/** Layers sheet — optional map layers live here, OFF by default
 * (doc 02 delete-list: nothing overlays the rest map until asked). */
import React from "react";
import { StyleSheet, Switch, Text, View } from "react-native";
import { V2T, V2Type, fam } from "../../theme";
import { DYNAMIC_TYPE } from "../../a11y";
import { tick } from "../../haptics";
import { Icon, type Glyph } from "../../icons";
import { Sheet } from "../../ui";
import { t, type Lang } from "../../i18n/strings";

export type LayerKey = "fires" | "spots" | "corridors";

const ROWS: { key: LayerKey; label: Parameters<typeof t>[0]; glyph: Glyph }[] = [
  { key: "fires", label: "layerFires", glyph: "flame" },
  { key: "spots", label: "layerBlackspots", glyph: "pin" },
  { key: "corridors", label: "layerCorridors", glyph: "smoke" },
];

export function LayersSheet({
  visible, values, onToggle, onClose, lang,
}: {
  visible: boolean;
  values: Record<LayerKey, boolean>;
  onToggle: (k: LayerKey, v: boolean) => void;
  onClose: () => void;
  lang: Lang;
}) {
  if (!visible) return null;
  return (
    <View style={s.wrap}>
      <Sheet detent="half" onClose={onClose} lang={lang}>
        <Text {...DYNAMIC_TYPE} style={[s.title, { fontFamily: fam(lang, "semi") }]}>{t("layers", lang)}</Text>
        {ROWS.map((r) => (
          <View key={r.key} style={s.row}>
            <Icon name={r.glyph} color={V2T.text2} size={20} />
            <Text {...DYNAMIC_TYPE} style={[s.rowLabel, { fontFamily: fam(lang, "med") }]}>{t(r.label, lang)}</Text>
            <Switch
              value={values[r.key]}
              onValueChange={(v) => { tick(); onToggle(r.key, v); }}
              accessibilityLabel={t(r.label, lang)}
              trackColor={{ false: V2T.line, true: V2T.accent }}
              thumbColor={V2T.surface}
            />
          </View>
        ))}
      </Sheet>
    </View>
  );
}

const s = StyleSheet.create({
  /* elevation must beat HomeScreen's 24 — Android dispatches sibling touches
     by z before mount order, so the still-mounted home scroll swallowed this
     sheet's drags. iOS ignores it. */
  wrap: { position: "absolute", bottom: 0, left: 0, right: 0, elevation: 30 },
  title: {
    fontSize: V2Type.secondary, color: V2T.text3,
    paddingHorizontal: 18, paddingTop: 2, paddingBottom: 6,
    textTransform: "uppercase", letterSpacing: 0.8,
  },
  row: {
    flexDirection: "row", alignItems: "center", gap: 14,
    paddingHorizontal: 18, paddingVertical: 10,
  },
  rowLabel: { flex: 1, fontSize: V2Type.secondary, color: V2T.text },
});
