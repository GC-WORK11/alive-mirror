/** Shared bits for the two dedicated stay & play components —
 *  the warm head (glyph well + serif title + area line + honest
 *  disclosure + the sibling door), and the quiet honesty states
 *  both sheets speak in (reading / thin / unrated). */
import React from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { V2T, fam, famSerif } from "../../theme";
import { DYNAMIC_TYPE } from "../../a11y";
import { Icon, type Glyph } from "../../icons";
import { BackChip } from "../../ui";
import { t, type Lang } from "../../i18n/strings";

/** day word for the rolling horizon — 'today' / 'tomorrow' /
 *  'in N days' as standalone words (the window-in-words lines). */
export const dayWordSolo = (off: number, lang: Lang) =>
  off <= 0 ? t("exploreToday", lang)
    : off === 1 ? t("exploreTomorrow", lang)
    : t("exploreInDays", lang, { n: off });

/** A window readout in words — 'today 08:30–18:30' or, when the run
 *  crosses midnight, 'today 21:30 – tomorrow 06:30'. Server labels are
 *  IST clock times; day words are ours and localized. */
export function windowWords(w: {
  start_label?: string; end_label?: string | null;
  start_day_offset: number; end_day_offset: number;
}, lang: Lang): string {
  const start = w.start_label ?? "";
  const end = w.end_label ?? "…";
  const d0 = dayWordSolo(w.start_day_offset, lang);
  const d1 = dayWordSolo(w.end_day_offset, lang);
  return w.end_day_offset === w.start_day_offset
    ? `${d0} ${start}–${end}`
    : `${d0} ${start} – ${d1} ${end}`;
}

export function ExploreHead({ lang, glyph, title, sub, disclosure, siblingLabel, onSibling, onClose }: {
  lang: Lang;
  glyph: Glyph;
  title: string;
  sub: string;
  disclosure?: string;
  siblingLabel: string;
  onSibling: () => void;
  onClose: () => void;
}) {
  return (
    <View style={hs.head}>
      <View style={hs.pinWell}>
        <Icon name={glyph} color={V2T.accent} size={15} />
      </View>
      <View style={{ flex: 1 }}>
        <Text {...DYNAMIC_TYPE} style={[hs.title, { fontFamily: famSerif(lang, "med") }]}
          numberOfLines={1}>
          {title}
        </Text>
        <Text {...DYNAMIC_TYPE} style={[hs.sub, { fontFamily: fam(lang, "reg") }]}
          numberOfLines={1}>{sub}</Text>
        {disclosure ? (
          <Text {...DYNAMIC_TYPE} style={[hs.disc, { fontFamily: fam(lang, "reg") }]}
            numberOfLines={2}>{disclosure}</Text>
        ) : null}
        {/* the doors, inside the head's text column — 'back' is the
            labelled exit (the grabber drag + corner X stay secondary),
            the sibling surface is one tap away at the same anchor.
            Controls live here, never the top-right dead zone where the
            status-bar cluster sits. */}
        <View style={hs.doorRow}>
          <BackChip onPress={onClose} lang={lang} />
          <Pressable
            onPress={onSibling}
            accessibilityRole="button"
            accessibilityLabel={siblingLabel}
            style={({ pressed }) => [hs.sibling, pressed && { opacity: 0.55 }]}
            hitSlop={10}
          >
            <Text {...DYNAMIC_TYPE}
              style={[hs.siblingTxt, { fontFamily: fam(lang, "med") }]}
              numberOfLines={1}>
              {siblingLabel}
            </Text>
            <Icon name="navigate" color={V2T.accentInk} size={11} />
          </Pressable>
        </View>
      </View>
    </View>
  );
}

export function HonestLine({ text, lang }: { text: string; lang: Lang }) {
  return (
    <View style={hs.honestWrap}>
      <Text {...DYNAMIC_TYPE}
        style={[hs.honestTxt, { fontFamily: fam(lang, "reg") }]}>
        {text}
      </Text>
    </View>
  );
}

export function HonestChip({ text, lang }: { text: string; lang: Lang }) {
  return (
    <View style={hs.chip}>
      <Text {...DYNAMIC_TYPE}
        style={[hs.chipTxt, { fontFamily: fam(lang, "reg") }]}>
        {text}
      </Text>
    </View>
  );
}

const hs = StyleSheet.create({
  head: { flexDirection: "row", alignItems: "flex-start", marginBottom: 4 },
  pinWell: {
    width: 30, height: 30, borderRadius: 15,
    backgroundColor: V2T.accentWash,
    alignItems: "center", justifyContent: "center",
    marginRight: 10, marginTop: 2,
  },
  title: { fontSize: 20, color: V2T.text, letterSpacing: -0.3 },
  sub: { fontSize: 12.5, color: V2T.text3, marginTop: 1 },
  disc: { fontSize: 11, color: V2T.text4, marginTop: 4, lineHeight: 15 },
  doorRow: {
    flexDirection: "row", alignItems: "center", gap: 8,
    marginTop: 8, marginBottom: 2,
  },
  sibling: {
    alignSelf: "flex-start", flexDirection: "row", alignItems: "center",
    gap: 5,
    paddingHorizontal: 12, paddingVertical: 6,
    borderRadius: 999, borderWidth: StyleSheet.hairlineWidth,
    borderColor: V2T.ink10,
  },
  siblingTxt: { fontSize: 12.5, color: V2T.accentInk },
  honestWrap: { paddingVertical: 30, alignItems: "center" },
  honestTxt: { fontSize: 13.5, color: V2T.text3, textAlign: "center" },
  chip: {
    alignSelf: "flex-start", borderRadius: 999,
    backgroundColor: V2T.accentWash,
    paddingHorizontal: 10, paddingVertical: 4,
    marginTop: 4, marginBottom: 6,
  },
  chipTxt: { fontSize: 11.5, color: V2T.accentInk },
});
