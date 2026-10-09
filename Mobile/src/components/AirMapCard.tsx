/** AirMapCard — the air map's own voice: what the colours mean and
 *  what stands behind them.
 *
 *  The field IS the map — this card is only its legend, not chrome
 *  covering it: it never eats a gesture (pointerEvents="none" rides on
 *  the wrapper in App.tsx too, belt and suspenders for the Android
 *  z-order quirk where pointerEvents on a styled parent can still
 *  shadow children).
 *
 *  Honesty contract: the station count is the served field's own
 *  `stations` array length (instruments the blend is anchored to right
 *  now — never the fleet's total); the age line is the served field's
 *  own age/stale verdict. No field at all → the card says so instead
 *  of explaining a field that isn't painted.
 */
import React from "react";
import { StyleSheet, Text, View } from "react-native";
import { bandFieldIdx, fam, famMonoText, NUM, V2Elev, V2Radius, V2T, V2Type } from "../theme";
import { DYNAMIC_TYPE } from "../a11y";
import { t, type Lang } from "../i18n/strings";

/* the swatches wear the field's real on-map tone — each band at its
   painted alpha over the basemap land (bandFieldIdx), not the raw
   chips, so the legend honestly previews what's lying on the streets */
const BAND_HEX = [0, 1, 2, 3, 4, 5].map(bandFieldIdx);

export function AirMapCard({
  lang,
  stations,
  fieldAgeS,
  stale,
  hasField,
}: {
  lang: Lang;
  /** count of live instruments the served field is anchored to;
   *  null = the field block hasn't landed yet — the row stays quiet
   *  rather than claiming instruments it can't name */
  stations: number | null;
  /** served field age in seconds (the grid's own epoch), null when
   *  the serve carries no stamp */
  fieldAgeS: number | null;
  /** the server/cache stale verdict — older data is said, not hidden */
  stale?: boolean | null;
  /** anything painted at all — controls whether the legend row
      claims a field exists */
  hasField: boolean;
}) {
  const min =
    fieldAgeS != null && Number.isFinite(fieldAgeS)
      ? Math.max(0, Math.floor(fieldAgeS / 60))
      : null;
  const ageLine = !hasField
    ? t("cityNoField", lang)
    : stale === true || (min != null && min >= 30)
      ? `${t("cityStale", lang)}${min != null ? ` · ${min} ${t("minUnit", lang)}` : ""}`
      : min != null
        ? t("howWe_fieldAge", lang, { n: min })
        : null;

  const a11y = [
    t("airmapTitle", lang),
    t("airmapLine", lang),
    stations != null && stations > 0
      ? `${stations} ${t("srcStations", lang)}`
      : null,
    ageLine,
  ]
    .filter(Boolean)
    .join(" — ");

  return (
    <View style={cs.card} accessible accessibilityRole="text" accessibilityLabel={a11y}>
      <View style={cs.head}>
        <Text {...DYNAMIC_TYPE} numberOfLines={1}
          style={[cs.title, { fontFamily: fam(lang, "med") }]}>
          {t("airmapTitle", lang)}
        </Text>
        {stations != null && stations > 0 && (
          <Text {...DYNAMIC_TYPE} numberOfLines={1}
            style={[cs.stations, NUM, { fontFamily: famMonoText(lang, "reg") }]}>
            {stations} {t("srcStations", lang)}
          </Text>
        )}
      </View>
      <Text {...DYNAMIC_TYPE} numberOfLines={2}
        style={[cs.line, { fontFamily: fam(lang, "reg") }]}>
        {t("airmapLine", lang)}
      </Text>
      <View style={cs.foot}>
        <View style={cs.dots}>
          {BAND_HEX.map((c) => (
            <View key={c} style={[cs.dot, { backgroundColor: c }]} />
          ))}
        </View>
        <Text {...DYNAMIC_TYPE} numberOfLines={1}
          style={[cs.scale, { fontFamily: fam(lang, "reg") }]}>
          {t("band_good", lang)} → {t("band_severe", lang)}
        </Text>
        {ageLine ? (
          <Text {...DYNAMIC_TYPE} numberOfLines={1}
            style={[cs.age, NUM, { fontFamily: famMonoText(lang, "reg") }]}>
            {" · "}{ageLine}
          </Text>
        ) : null}
      </View>
    </View>
  );
}

const cs = StyleSheet.create({
  card: {
    ...V2Elev.float,
    alignSelf: "flex-start",
    backgroundColor: V2T.glassFaint,
    borderRadius: V2Radius.card - 4,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: V2T.glassLine,
    paddingHorizontal: 12,
    paddingVertical: 9,
    gap: 4,
  },
  head: {
    flexDirection: "row",
    alignItems: "baseline",
    justifyContent: "space-between",
    gap: 14,
  },
  title: { fontSize: V2Type.label, color: V2T.text },
  stations: { fontSize: V2Type.micro, color: V2T.text3, flexShrink: 1 },
  line: { fontSize: V2Type.label, color: V2T.text2 },
  foot: { flexDirection: "row", alignItems: "center", gap: 8 },
  dots: { flexDirection: "row", gap: 3 },
  dot: { width: 8, height: 8, borderRadius: 4 },
  scale: { fontSize: V2Type.micro, color: V2T.text3 },
  age: { fontSize: V2Type.micro, color: V2T.text3, flexShrink: 1 },
});
