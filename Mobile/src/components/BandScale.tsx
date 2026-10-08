/**
 * BandScale — the good→severe comprehension anchor, no words required.
 * The six CPCB bands draw as one continuous washed ramp (each band's
 * colour blending into the next across its boundary), and today's band
 * sits proud as a solid inked segment isolated by a paper seam — the
 * position carries the meaning, never decoration.
 */
import React, { useState } from "react";
import { StyleSheet, View } from "react-native";
import Svg, { Defs, LinearGradient, Rect, Stop } from "react-native-svg";
import { t, type Lang } from "../i18n/strings";
import { BAND_SEG_COUNT, bandEdgeIdx, bandInkIdx, V2T } from "../theme";

/* the subtle-state ramp — each washed band colour (the 40%-edge tone:
   deep enough to scan on the warm base, still whispered) interpolated
   at its segment's centre so neighbours blend smoothly at the seams */
const RAMP = Array.from({ length: BAND_SEG_COUNT }, (_, j) => bandEdgeIdx(j));
/* LinearGradient's children prop is typed ReactElement[] — a plain array */
const STOPS: React.ReactElement[] = [
  <Stop key="l" offset="0" stopColor={RAMP[0]} />,
  ...RAMP.map((c, j) => (
    <Stop key={j} offset={(j + 0.5) / BAND_SEG_COUNT} stopColor={c} />
  )),
  <Stop key="r" offset="1" stopColor={RAMP[BAND_SEG_COUNT - 1]} />,
];

export function BandScale({ idx, lang }: { idx: number; lang: Lang }) {
  const i = Math.max(0, Math.min(BAND_SEG_COUNT - 1, idx));
  const [w, setW] = useState(0);
  const seg = w / BAND_SEG_COUNT;
  return (
    <View
      style={bs.row}
      onLayout={(e) => setW(e.nativeEvent.layout.width)}
      accessible
      accessibilityRole="image"
      accessibilityLabel={t("bandScaleA11y", lang, { b: feltName(i, lang), n: i + 1 })}
    >
      {w > 0 && (
        <Svg width={w} height={9}>
          <Defs>
            <LinearGradient id="bandRamp" x1="0" y1="0" x2="1" y2="0">
              {STOPS}
            </LinearGradient>
          </Defs>
          {/* the resting track — the whole CPCB ramp as a whisper */}
          <Rect x={0} y={2.5} width={w} height={4} rx={2} fill="url(#bandRamp)" />
          {/* the paper seam isolates the live band from the ramp */}
          <Rect x={i * seg - 1} y={0} width={seg + 2} height={9} rx={4.5} fill={V2T.bg} />
          {/* the position — a solid band-inked segment proud of the track */}
          <Rect x={i * seg + 1.5} y={1} width={seg - 3} height={7} rx={3.5}
            fill={bandInkIdx(i) ?? V2T.text} />
        </Svg>
      )}
    </View>
  );
}

function feltName(i: number, lang: Lang): string {
  const keys = ["band_good", "band_satisfactory", "band_moderate", "band_poor", "band_veryPoor", "band_severe"] as const;
  return t(keys[Math.max(0, Math.min(5, i))], lang);
}

const bs = StyleSheet.create({
  row: { flexDirection: "row", alignSelf: "stretch" },
});
