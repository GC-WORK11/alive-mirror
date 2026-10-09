/** Layers sheet — optional map layers live here, OFF by default
 * (doc 02 delete-list: nothing overlays the rest map until asked). */
import React from "react";
import { Pressable, StyleSheet, Switch, Text, View } from "react-native";
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

function LayersSheetInner({
  visible, values, onToggle, onClose, onAbout, lang,
}: {
  visible: boolean;
  values: Record<LayerKey, boolean>;
  onToggle: (k: LayerKey, v: boolean) => void;
  onClose: () => void;
  /* walk-F6 — native ⓘ ornament renders ~10px and bezel-clipped, so it
     reads as a dead tap; this row gives the same attribution sheet a
     reachable target (App wires it to MapRef.showAttribution). */
  onAbout: () => void;
  lang: Lang;
}) {
  if (!visible) return null;
  /* Sheet self-anchors (absolute bottom detent, elevation 30 — beats the home
     pane's 24 on Android) so this mounts bare: no wrapper that would collapse
     to zero height and dead-zone the sheet's own taps on iOS */
  return (
    <>
      {/* glass-on-glass: this sheet floats over the day card's own glass
          pane, so two 91% whites stack and the card text ghosts through
          (android audit #7) — a near-solid fill keeps rows legible while
          other sheets keep the designed tint */}
      <Sheet detent="half" onClose={onClose} lang={lang}
        style={{ backgroundColor: "rgba(255,255,255,0.97)" }}>
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
        <Pressable style={s.row} onPress={() => { tick(); onAbout(); }}
          accessibilityRole="button" accessibilityLabel={t("aboutMap", lang)}>
          <Icon name="info" color={V2T.text2} size={20} />
          <Text {...DYNAMIC_TYPE} style={[s.rowLabel, { fontFamily: fam(lang, "med") }]}>{t("aboutMap", lang)}</Text>
        </Pressable>
      </Sheet>
    </>
  );
}

export const LayersSheet = React.memo(LayersSheetInner);

const s = StyleSheet.create({
  title: {
    fontSize: V2Type.secondary, color: V2T.text,
    paddingHorizontal: 20, paddingTop: 4, paddingBottom: 8,
  },
  row: {
    flexDirection: "row", alignItems: "center", gap: 14,
    paddingHorizontal: 18, paddingVertical: 10,
  },
  rowLabel: { flex: 1, fontSize: V2Type.secondary, color: V2T.text },
});
