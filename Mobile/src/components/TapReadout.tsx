/** TapReadout — the air map's tap answer: what the field says right
 *  where the finger landed.
 *
 *  The tap samples the SAME painted cells the layer draws
 *  (api/airfield.sampleFieldAt — local, instant, offline-safe); taps a
 *  painted cell can't answer fall back to one /aqi read and carry the
 *  model qualifier, so the map's colour and the readout never tell
 *  different stories.
 *
 *  Honesty contract: no served answer → the "outside" line, never a
 *  guess; locality comes from the bundled gazetteer (localityAt) or
 *  stays silent; lo-confidence and edge answers are labelled, not
 *  dressed up. One band word, one colour — the register's minimal
 *  meaning layer, same law as the legend card.
 *
 *  TapPin is the map-side half: a band-washed µg chip + the dot that
 *  marks the exact point, rendered inside the always-mounted Marker
 *  (App.tsx parks it like the endpoint pins — the child swaps, the
 *  annotation never unmounts mid-draw).
 */
import React from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import {
  bandColorIdx, bandEdgeIdx, bandInkIdx, bandWashIdx,
  fam, famMonoText, NUM, V2Elev, V2Radius, V2T, V2Type,
} from "../theme";
import { DYNAMIC_TYPE } from "../a11y";
import { Icon } from "../icons";
import { t, type Lang, type StringKey } from "../i18n/strings";

export type TapRead = {
  /** served µg/m³ at the tapped point — the painted cell's own value,
   *  or the /aqi answer when the field's cells don't reach */
  pm25: number;
  /** CPCB band index 0–5 (the caller applies theme.bandIdx) */
  band: number;
  /** the cell's conf grade ("hi"|"med"|"lo"), or "model" for the /aqi
   *  edge answer — the caption qualifier keys off this, not the value */
  conf: string | null;
};

const BAND_KEYS: StringKey[] = [
  "band_good", "band_satisfactory", "band_moderate",
  "band_poor", "band_veryPoor", "band_severe",
];

export function TapReadout({
  lang,
  read,
  place,
  onClose,
}: {
  lang: Lang;
  /** the resolved read, "pending" while the /aqi edge fallback is
      still out, "outside" when neither the field nor the model
      reaches the point */
  read: TapRead | "pending" | "outside";
  /** the gazetteer locality at the tap — rides every state (an outside
      answer still names where it was asked); null stays silent */
  place: string | null;
  onClose: () => void;
}) {
  const resolved = typeof read === "object";
  const a11y = resolved
    ? t("tapAqiA11y", lang, {
        n: Math.round(read.pm25),
        band: t(BAND_KEYS[read.band], lang),
        place: place ?? t("tapHere", lang),
      })
    : read === "pending"
      ? t("tapReading", lang)
      : t("tapOutside", lang);
  const qualifier =
    resolved && (read.conf === "lo" || read.conf === "model")
      ? t("srcModel", lang)
      : null;
  const caption = [place ?? (resolved ? t("tapHere", lang) : null), qualifier]
    .filter(Boolean).join(" · ");
  return (
    <View style={ts.card}>
      <View style={ts.row}>
        {/* the read groups for VoiceOver; the ✕ stays its own target —
            an `accessible` card would swallow the button inside it */}
        <View style={ts.read} accessible accessibilityRole="text" accessibilityLabel={a11y}>
          {resolved ? (
            <>
              <View
                style={[ts.dot, {
                  backgroundColor: bandColorIdx(read.band) ?? V2T.text3,
                }]}
              />
              <Text {...DYNAMIC_TYPE} numberOfLines={1}
                style={[ts.num, NUM, {
                  fontFamily: famMonoText(lang, "med"),
                  color: bandInkIdx(read.band),
                }]}>
                {Math.round(read.pm25)}
                <Text style={[ts.unit, { fontFamily: fam(lang, "reg") }]}>
                  {" µg/m³"}
                </Text>
                <Text style={[ts.band, {
                  fontFamily: fam(lang, "med"), color: bandInkIdx(read.band),
                }]}>
                  {" — "}{t(BAND_KEYS[read.band], lang)}
                </Text>
              </Text>
            </>
          ) : (
            <Text {...DYNAMIC_TYPE} numberOfLines={1}
              style={[ts.plain, { fontFamily: fam(lang, "med") }]}>
              {read === "pending" ? t("tapReading", lang) : t("tapOutside", lang)}
            </Text>
          )}
        </View>
        <Pressable onPress={onClose} hitSlop={12}
          accessibilityRole="button" accessibilityLabel={t("a11yClear", lang)}
          style={({ pressed }) => [ts.x, pressed && { opacity: 0.6 }]}>
          <Icon name="close" color={V2T.text3} size={12} />
        </Pressable>
      </View>
      {caption !== "" && (
        <Text {...DYNAMIC_TYPE} numberOfLines={1}
          style={[ts.caption, { fontFamily: fam(lang, "reg") }]}>
          {caption}
        </Text>
      )}
    </View>
  );
}

/** The map-side marker: the read pinned where it was taken — a small
 *  band-washed µg chip riding above a dot at the exact tapped point.
 *  band=null (pending/no answer) renders the neutral ink chip. */
export function TapPin({ label, band }: { label: string; band: number | null }) {
  const i = band == null ? null : Math.max(0, Math.min(5, band));
  const fg = i == null ? V2T.text : bandInkIdx(i);
  return (
    <View style={ts.pinCol} pointerEvents="none">
      <View style={[ts.pinChip, {
        backgroundColor: i == null ? V2T.surface : bandWashIdx(i),
        borderColor: i == null ? V2T.hairline : bandEdgeIdx(i),
      }]}>
        <Text {...DYNAMIC_TYPE} numberOfLines={1}
          style={[ts.pinNum, NUM, { fontFamily: famMonoText("en", "med"), color: fg }]}>
          {label}
        </Text>
      </View>
      <View style={[ts.pinDot, { backgroundColor: fg }]} />
    </View>
  );
}

const ts = StyleSheet.create({
  card: {
    ...V2Elev.float,
    backgroundColor: V2T.glassFaint,
    borderRadius: V2Radius.card - 4,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: V2T.glassLine,
    paddingLeft: 12,
    paddingRight: 7,
    paddingVertical: 9,
    gap: 3,
    maxWidth: 320,
  },
  row: { flexDirection: "row", alignItems: "center", gap: 8 },
  read: { flexDirection: "row", alignItems: "center", gap: 8, flexShrink: 1 },
  dot: { width: 9, height: 9, borderRadius: 5 },
  num: { fontSize: V2Type.body, color: V2T.text },
  unit: { fontSize: V2Type.label, color: V2T.text3 },
  band: { fontSize: V2Type.body },
  plain: { fontSize: V2Type.label, color: V2T.text2 },
  x: { paddingLeft: 8, paddingVertical: 2 },
  caption: { fontSize: V2Type.micro, color: V2T.text3, paddingLeft: 17 },
  pinCol: { alignItems: "center" },
  pinChip: {
    paddingHorizontal: 7,
    paddingVertical: 3,
    borderRadius: 9,
    borderWidth: StyleSheet.hairlineWidth,
  },
  pinNum: { fontSize: V2Type.micro },
  pinDot: { width: 5, height: 5, borderRadius: 3, marginTop: 1.5 },
});
