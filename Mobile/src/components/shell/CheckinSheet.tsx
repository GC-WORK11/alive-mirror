/** Symptom check-in (doc 02 — "the symptom lens"): breath / eyes / energy,
 *  each answered good·meh·rough with a single tap. Extracted from
 *  HomeScreen.tsx by the motion-v3 lane — the markup, copy and styling are
 *  the same card that lived there; only the FEEL changed (docs/20 §6):
 *  every pill dips through PressSpring and the selected state fills by
 *  crossfade (an accentWash+accent overlay fading in), never a snap.
 *  Nothing here re-colours or re-lays out the card — springs only.
 *
 *  Mount (HomeScreen):
 *    <CheckinSheet checkin={data?.checkin ?? null}
 *      lens={data?.lens ?? { kind: "early", days: 0, need: 7 }}
 *      lang={lang} onCheckin={onCheckin} />
 */
import React, { useEffect, useState } from "react";
import { Animated, Pressable, StyleSheet, Text, View } from "react-native";
import { V2Elev, V2Radius, V2T, V2Type, fam } from "../../theme";
import { DYNAMIC_TYPE, useReduceMotion } from "../../a11y";
import { t, type Lang } from "../../i18n/strings";
import { tap } from "../../haptics";
import { bump } from "../../perf";
import type { Checkin, LensVerdict } from "../../store/daylog";
import { PressSpring } from "../PressSpring";

const FACETS = [
  { key: "breath", labelKey: "lensBreath" },
  { key: "eyes", labelKey: "lensEyes" },
  { key: "energy", labelKey: "lensEnergy" },
] as const;
const OPTS = ["lensGood", "lensMeh", "lensRough"] as const;

/** One facet option — the selected fill is an overlay that fades in
 *  (accentWash wash + accent edge, same paint as the old `optSel`), so
 *  picking an answer reads as the pill filling, not flipping. The base
 *  hairline stays underneath; reduce-motion jumps the overlay to final. */
function Pill({ label, a11yLabel, selected, lang, onPress }: {
  label: string; a11yLabel: string; selected: boolean; lang: Lang;
  onPress: () => void;
}) {
  const reduce = useReduceMotion();
  const [fill] = useState(() => new Animated.Value(selected ? 1 : 0));
  useEffect(() => {
    if (reduce) { fill.setValue(selected ? 1 : 0); return; }
    Animated.spring(fill, {
      toValue: selected ? 1 : 0, damping: 16, stiffness: 240, mass: 0.7,
      useNativeDriver: true,
    }).start();
  }, [selected, fill, reduce]);
  return (
    <PressSpring>
      <Pressable
        onPress={() => { tap(); onPress(); }}
        accessibilityRole="button"
        accessibilityLabel={a11yLabel}
        accessibilityState={{ selected }}
        style={cs.opt}>
        <Animated.View pointerEvents="none"
          style={[StyleSheet.absoluteFill, cs.optFill, { opacity: fill }]} />
        <Text {...DYNAMIC_TYPE}
          style={[cs.optTxt, { fontFamily: fam(lang, "reg") }, selected && cs.optTxtSel]}>
          {label}
        </Text>
      </Pressable>
    </PressSpring>
  );
}

function CheckinSheetInner({ checkin, lens, lang, onCheckin }: {
  checkin: Checkin | null; lens: LensVerdict; lang: Lang;
  onCheckin: (c: Omit<Checkin, "ts">) => void;
}) {
  bump("home.LensCard");
  const val = { breath: checkin?.breath ?? -1, eyes: checkin?.eyes ?? -1, energy: checkin?.energy ?? -1 };
  return (
    <View style={cs.card}>
      <Text {...DYNAMIC_TYPE} style={[cs.cardTitle, { fontFamily: fam(lang, "semi") }]}>
        {t("lensTitle", lang)}
      </Text>
      <Text {...DYNAMIC_TYPE} style={[cs.lensSub, { fontFamily: fam(lang, "reg") }]}>
        {t("lensSub", lang)}
      </Text>
      {FACETS.map((f) => (
        <View key={f.key} style={cs.facetRow}>
          <Text {...DYNAMIC_TYPE} style={[cs.facetLabel, { fontFamily: fam(lang, "med") }]}>
            {t(f.labelKey, lang)}
          </Text>
          <View style={cs.facetOpts}>
            {OPTS.map((ok, v) => (
              <Pill key={ok}
                label={t(ok, lang)}
                a11yLabel={`${t(f.labelKey, lang)}: ${t(ok, lang)}`}
                selected={val[f.key] === v}
                lang={lang}
                onPress={() => onCheckin({
                  breath: val.breath, eyes: val.eyes, energy: val.energy,
                  [f.key]: v,
                })} />
            ))}
          </View>
        </View>
      ))}
      <Text {...DYNAMIC_TYPE} style={[cs.finePrint, { fontFamily: fam(lang, "reg") }]}>
        {t("lensPrivacy", lang)}
      </Text>
      {/* the verdict earns its line honestly */}
      <Text {...DYNAMIC_TYPE} style={[cs.verdict, { fontFamily: fam(lang, "med") }]}>
        {lens.kind === "early" ? t("lensEarly", lang)
          : lens.kind === "flat" ? t("lensFlat", lang, { n: lens.days, dayNoun: t(lens.days === 1 ? "dayNounOne" : "dayNounMany", lang) })
          : t("lensLink", lang, {
              f: t(lens.facet === "eyes" ? "lensFacetEyes"
                    : lens.facet === "energy" ? "lensFacetEnergy" : "lensFacetBreath", lang),
            })}
      </Text>
    </View>
  );
}

export const CheckinSheet = React.memo(CheckinSheetInner);

/* the card shell styles are the same tokens HomeScreen's `ss` carried —
   copied verbatim so this card renders identically (card/cardTitle/
   finePrint are the shared card grammar; the rest are the lens block's) */
const cs = StyleSheet.create({
  card: {
    ...V2Elev.card,
    backgroundColor: V2T.surface,
    borderRadius: V2Radius.card,
    paddingHorizontal: 16, paddingTop: 16, paddingBottom: 16,
  },
  /* the card's own word — a warm label, never an uppercase micro eyebrow */
  cardTitle: {
    color: V2T.text, fontSize: V2Type.secondary, marginBottom: 10,
  },
  finePrint: { color: V2T.text3, fontSize: V2Type.micro, marginTop: 10 },

  /* lens — facets answer in chunky pills */
  lensSub: { color: V2T.text2, fontSize: V2Type.label, marginBottom: 10, lineHeight: 19 },
  facetRow: {
    flexDirection: "row", alignItems: "center", justifyContent: "space-between",
    paddingVertical: 7,
  },
  facetLabel: { color: V2T.text, fontSize: V2Type.secondary },
  facetOpts: { flexDirection: "row", gap: 6 },
  opt: {
    paddingHorizontal: 12, paddingVertical: 9,
    borderRadius: V2Radius.row,
    backgroundColor: V2T.surface2, overflow: "hidden",
  },
  /* the animated selected fill — identical paint to the old optSel */
  optFill: {
    borderRadius: V2Radius.row - 1,
    backgroundColor: V2T.accentWash, borderWidth: 1.5, borderColor: V2T.accent,
  },
  optTxt: { color: V2T.text2, fontSize: V2Type.label },
  optTxtSel: { color: V2T.accentInk },
  verdict: { color: V2T.text2, fontSize: V2Type.label, marginTop: 12 },
});
