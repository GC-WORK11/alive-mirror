/** PlaceSheet — the SETTLE surface of the rebuilt where-to flow
 *  (Google's register, honestly): a search pick doesn't route, it
 *  lands — the camera flies to the pin and this half-sheet names what
 *  arrived. One action commits to a trip: Directions.
 *
 *  What's on it, top to bottom — every line earned, none invented:
 *   · the place's name + locality (subtitle the match carried)
 *   · an HONEST substitute label when the hit wasn't the exact ask —
 *     a category row standing in for an unmapped name says so, an
 *     area standing in for an unmapped unit says so, a near-ask names
 *     its anchor (honesty-cluster metadata, never implied exact)
 *   · the live field read AT that spot — the local field cells, the
 *     same serve the route tint paints from; absent cells say "no
 *     field read", never a guessed number
 *   · the flow's locNotice slot (a failed fix / too-close reads out
 *     loud instead of dead-ending the tap)
 *   · [Directions] — during the origin resolve it reads "locating…"
 *     and the tap is dead on purpose: claiming a fix you don't have
 *     is the bug this rebuild kills. */

import React, { useEffect } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { V2Radius, V2T, bandColor, fam } from "../../theme";
import { DYNAMIC_TYPE } from "../../a11y";
import { Icon } from "../../icons";
import { BackChip, Sheet } from "../../ui";
import { PressSpring } from "../PressSpring";
import { mark } from "../../perf";
import { localizeKind, t, type Lang } from "../../i18n/strings";
import type { Place } from "./types";
import type { PlaceHint } from "./useShellFlow";

export function PlaceSheet({
  place, meta, airUg, locating, notice, onDirections, onClose, lang,
}: {
  place: Place;
  meta: PlaceHint | null;
  /** live field PM2.5 at the pinned spot — null = no cell covers it */
  airUg: number | null;
  /** origin resolve in flight — the button narrates it */
  locating: boolean;
  /** flow's honest one-liner (fix failed / too-close) */
  notice: string | null;
  onDirections: () => void;
  onClose: () => void;
  lang: Lang;
}) {
  useEffect(() => { mark("place.show"); }, []);

  /* the substitute disclosure — keyed off the match metadata the row
     carried, in the matcher's own vocabulary (never a guessed answer):
       category → the kind that stood in for an unmapped name
       area     → the area that stood in for an unmapped unit
       place    → a near-ask resolves beside its anchor */
  const subst =
    meta?.match === "category"
      ? t("placeSubstCat", lang, { kind: meta.kind ?? place.name })
      : meta?.match === "area"
        ? t("placeSubstArea", lang, { area: place.name })
        : meta?.match === "place" && meta.anchor
          ? t("placeNearAnchor", lang, { anchor: meta.anchor })
          : null;

  const airCol = airUg != null ? (bandColor(airUg) ?? V2T.text3) : V2T.text3;

  return (
    <Sheet detent="half" onClose={onClose} lang={lang} style={s.sheet}>
      <View style={s.head}>
        <View style={s.pinWell}>
          <Icon name="pin" color={V2T.accent} size={15} />
        </View>
        <View style={{ flex: 1 }}>
          <Text {...DYNAMIC_TYPE} style={[s.name, { fontFamily: fam(lang, "semi") }]}
            numberOfLines={2}>{place.name}</Text>
          {place.subtitle ? (
            <Text {...DYNAMIC_TYPE} style={[s.sub, { fontFamily: fam(lang, "reg") }]}
              numberOfLines={1}>{localizeKind(place.subtitle, lang)}</Text>
          ) : null}
          {/* the labelled way back lives inside the head's text column —
              the grabber drag + corner X stay the quiet secondary */}
          <View style={s.backRow}>
            <BackChip onPress={onClose} lang={lang} />
          </View>
        </View>
      </View>

      {subst ? (
        <View style={s.substRow}>
          <Icon name="info" color={V2T.text3} size={12} />
          <Text {...DYNAMIC_TYPE} style={[s.substTxt, { fontFamily: fam(lang, "reg") }]}>
            {subst}</Text>
        </View>
      ) : null}

      <View style={s.airRow}>
        <View style={[s.airDot, { backgroundColor: airCol }]} />
        <Text {...DYNAMIC_TYPE} style={[s.airTxt, { fontFamily: fam(lang, "reg") }]}>
          {airUg != null
            ? t("placeAirNow", lang, { n: Math.round(airUg) })
            : t("placeAirNone", lang)}</Text>
      </View>

      {notice ? (
        <View style={s.noteRow}>
          <Icon name="warn" color={V2T.out1} size={12} />
          <Text {...DYNAMIC_TYPE} style={[s.noteTxt, { fontFamily: fam(lang, "reg") }]}>
            {notice}</Text>
        </View>
      ) : null}

      <PressSpring style={s.ctaWrap}>
        <Pressable
          onPress={onDirections}
          disabled={locating}
          accessibilityRole="button"
          accessibilityState={{ busy: locating, disabled: locating }}
          style={[s.cta, locating && { opacity: 0.65 }]}>
          <Icon name="navigate" color="#fff" size={15} />
          <Text {...DYNAMIC_TYPE} style={[s.ctaTxt, { fontFamily: fam(lang, "semi") }]}>
            {locating ? t("locating", lang) : t("directions", lang)}</Text>
        </Pressable>
      </PressSpring>
    </Sheet>
  );
}

const s = StyleSheet.create({
  sheet: { paddingTop: 4 },
  head: { flexDirection: "row", alignItems: "flex-start", gap: 10 },
  pinWell: {
    width: 30, height: 30, borderRadius: 15, marginTop: 2,
    backgroundColor: V2T.surface3, alignItems: "center", justifyContent: "center",
  },
  name: { fontSize: 21, lineHeight: 26, color: V2T.text },
  sub: { fontSize: 13, color: V2T.text3, marginTop: 3 },
  substRow: {
    flexDirection: "row", alignItems: "center", gap: 6, marginTop: 14,
    paddingHorizontal: 10, paddingVertical: 8,
    backgroundColor: V2T.surface3, borderRadius: V2Radius.row,
  },
  substTxt: { flex: 1, fontSize: 12.5, color: V2T.text2, lineHeight: 17 },
  backRow: { flexDirection: "row", marginTop: 10 },
  airRow: { flexDirection: "row", alignItems: "center", gap: 8, marginTop: 12 },
  airDot: { width: 9, height: 9, borderRadius: 4.5 },
  airTxt: { fontSize: 13, color: V2T.text2 },
  noteRow: { flexDirection: "row", alignItems: "center", gap: 6, marginTop: 10 },
  noteTxt: { flex: 1, fontSize: 12.5, color: V2T.out1, lineHeight: 17 },
  ctaWrap: { marginTop: 22 },
  cta: {
    flexDirection: "row", alignItems: "center", justifyContent: "center",
    gap: 8, backgroundColor: V2T.accent, borderRadius: V2Radius.row,
    paddingVertical: 14,
  },
  ctaTxt: { fontSize: 15, color: "#fff" },
});
