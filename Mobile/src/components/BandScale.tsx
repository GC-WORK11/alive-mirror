/**
 * BandScale — the good→severe comprehension anchor, no words required.
 * Six muted CPCB segments in a row; today's air band renders solid while
 * the rest stay washed — a stranger reads "where on the scale we are"
 * at a glance. Position, not colour alone, carries the meaning.
 */
import React from "react";
import { StyleSheet, View } from "react-native";
import { t, type Lang } from "../i18n/strings";
import { BAND_SEG_COUNT, bandInkIdx, bandWashDeepIdx } from "../theme";

export function BandScale({ idx, lang }: { idx: number; lang: Lang }) {
  const i = Math.max(0, Math.min(BAND_SEG_COUNT - 1, idx));
  return (
    <View
      style={bs.row}
      accessible
      accessibilityRole="image"
      accessibilityLabel={t("bandScaleA11y", lang, { b: feltName(i, lang), n: i + 1 })}
    >
      {Array.from({ length: BAND_SEG_COUNT }).map((_, j) => (
        <View
          key={j}
          style={[
            bs.seg,
            j === 0 && bs.segL,
            j === BAND_SEG_COUNT - 1 && bs.segR,
            { backgroundColor: j === i ? bandInkIdx(i) : bandWashDeepIdx(j) },
            j === i && bs.segOn,
          ]}
        />
      ))}
    </View>
  );
}

function feltName(i: number, lang: Lang): string {
  const keys = ["band_good", "band_satisfactory", "band_moderate", "band_poor", "band_veryPoor", "band_severe"] as const;
  return t(keys[Math.max(0, Math.min(5, i))], lang);
}

const bs = StyleSheet.create({
  row: { flexDirection: "row", gap: 3, alignSelf: "stretch" },
  seg: { flex: 1, height: 4, borderRadius: 2, opacity: 0.75 },
  segL: { borderTopLeftRadius: 4, borderBottomLeftRadius: 4 },
  segR: { borderTopRightRadius: 4, borderBottomRightRadius: 4 },
  segOn: { opacity: 1, height: 5, marginTop: -0.5 },
});
