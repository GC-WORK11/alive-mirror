/** Arrival receipt (doc 02 §S7 + doc 10 claims ledger).
 *
 *   You're here. 31 min.
 *   You breathed ≈ 0.12 cigarettes   — 2.8× less than the smokiest option
 *   Your ride put out ≈ 1.4 kg       — the metro would have put out 0.3 kg
 *   [ Done ]   [ How we got this ]
 *
 * Copy rules honoured: cigarette equivalence only via "≈ N cigarettes"
 * (claims ledger), emissions labelled "est. — for vehicles like yours",
 * bands kept {lo,mid,hi} internally and shown where they're honest
 * (fine-particle g range), field age always visible, donation line says
 * what actually happened. No bare numbers: every figure gets a
 * comparison or an "est." tag. Honest empty states — a missing band
 * says so instead of showing 0.
 */
import React from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { NUM, V2Radius, V2T, V2Type, cigOf, fam } from "../../theme";
import { Icon } from "../../icons";
import { t, type Lang } from "../../i18n/strings";
import type { Band } from "../../nav/strip";

export type ReceiptAlt = { label: string; co2KgMid: number | null };

export type ReceiptData = {
  durationMin: number;
  modeLabel?: string | null;
  /** breathed band, µg — null when the strip never arrived */
  doseUg: Band | null;
  /** put-out bands — null when the mode emits nothing we model */
  co2Kg: Band | null;
  pm25G: Band | null;
  /** worst option's planned dose, µg → the "× less" comparison */
  worstDoseUg?: number | null;
  /** label of the worst option, e.g. "Auto" */
  worstLabel?: string | null;
  /** the next-best option on emissions → the "would have put out" line */
  alt?: ReceiptAlt | null;
  /** field freshness, minutes (claims: always visible when known) */
  fieldAgeMin?: number | null;
  /** whether the trip was actually donated to /v2/trip */
  donated?: boolean;
};

const r1 = (n: number) => Math.round(n * 10) / 10;
const r2 = (n: number) => Math.round(n * 100) / 100;

export function ReceiptSheet({
  data, lang, onDone, onHowWeGotThis,
}: {
  data: ReceiptData | null; lang: Lang;
  onDone: () => void; onHowWeGotThis?: (() => void) | null;
}) {
  if (!data) return null;
  const cigs = data.doseUg ? cigOf(data.doseUg.mid) : null;
  const worst = data.worstDoseUg;
  const ratio = cigs != null && worst != null && data.doseUg!.mid > 0.5
    ? Math.round((worst / data.doseUg!.mid) * 10) / 10
    : null;
  const savedCigs = cigs != null && worst != null
    ? cigOf(Math.max(0, worst - (data.doseUg?.mid ?? 0)))
    : null;

  return (
    <View style={s.sheet}>
      <Text style={[s.title, { fontFamily: fam(lang, "semi") }]}>
        {t("arrived_hereIn", lang, { n: Math.max(1, Math.round(data.durationMin)) })}
      </Text>

      {/* breathed */}
      <View style={s.row}>
        <Icon name="cigarette" color={V2T.breath1} size={16} />
        <View style={{ flex: 1 }}>
          <Text style={[s.main, NUM, { fontFamily: fam(lang, "med") }]}>
            {cigs == null
              ? t("receipt_noDose", lang)
              : t("receipt_breathed", lang, { n: cigs > 0 && cigs < 0.01 ? 0.01 : cigs })}
            {cigs != null && <Text style={s.est}>  {t("receipt_estShort", lang)}</Text>}
          </Text>
          {ratio != null && ratio > 1.05 && (
            <Text style={s.sub}>
              {data.worstLabel
                ? t("receipt_lessVs", lang, { n: ratio, m: data.worstLabel })
                : t("receipt_lessVsWorst", lang, { n: ratio })}
            </Text>
          )}
          {savedCigs != null && savedCigs >= 0.02 && (
            <Text style={s.sub}>{t("receiptSaved", lang, { n: savedCigs })}</Text>
          )}
        </View>
      </View>

      {/* put out */}
      <View style={s.row}>
        <Icon name="smoke" color={V2T.out1} size={16} />
        <View style={{ flex: 1 }}>
          {data.co2Kg == null ? null : data.co2Kg.hi <= 0 ? (
            <Text style={[s.main, { fontFamily: fam(lang, "med") }]}>
              {t("receipt_putOutNone", lang)}
            </Text>
          ) : (
            <>
              <Text style={[s.main, NUM, { fontFamily: fam(lang, "med") }]}>
                {t("receipt_putOutKg", lang, { n: r1(Math.max(0.05, data.co2Kg.mid)) })}
                <Text style={s.est}>  {t("receipt_estLike", lang)}</Text>
              </Text>
              {data.co2Kg.hi - data.co2Kg.lo > 0.05 && (
                <Text style={[s.sub, NUM]}>
                  {r1(data.co2Kg.lo)}–{r1(data.co2Kg.hi)} kg
                </Text>
              )}
              {data.pm25G != null && data.pm25G.hi > 0 && (
                <Text style={[s.sub, NUM]}>
                  {t("receipt_pmBand", lang, {
                    lo: r2(data.pm25G.lo), hi: r2(data.pm25G.hi),
                  })}
                </Text>
              )}
              {data.alt && data.alt.co2KgMid != null && (
                <Text style={s.sub}>
                  {t("receipt_altPutOut", lang, {
                    m: data.alt.label, n: r1(Math.max(0, data.alt.co2KgMid)),
                  })}
                </Text>
              )}
            </>
          )}
        </View>
      </View>

      {/* provenance footer */}
      <View style={s.foot}>
        {data.fieldAgeMin != null && (
          <Text style={s.footTxt}>{t("updatedMinAgo", lang, { n: Math.max(0, Math.round(data.fieldAgeMin)) })}</Text>
        )}
        <Text style={s.footTxt}>
          {data.donated ? t("receipt_donated", lang) : t("receipt_private", lang)}
        </Text>
      </View>

      <View style={s.btns}>
        <Pressable onPress={onDone} style={s.done} accessibilityRole="button">
          <Text style={[s.doneTxt, { fontFamily: fam(lang, "semi") }]}>{t("done", lang)}</Text>
        </Pressable>
        {onHowWeGotThis && (
          <Pressable onPress={onHowWeGotThis} hitSlop={8} accessibilityRole="button">
            <Text style={[s.howTxt, { fontFamily: fam(lang, "med") }]}>
              {t("howWeGotThis", lang)}
            </Text>
          </Pressable>
        )}
      </View>
    </View>
  );
}

const s = StyleSheet.create({
  sheet: {
    position: "absolute", left: 12, right: 12, bottom: 28,
    backgroundColor: V2T.surface, borderRadius: V2Radius.sheet,
    borderWidth: 1, borderColor: V2T.line, padding: 18,
    shadowColor: "#000", shadowOpacity: 0.55, shadowRadius: 18,
    shadowOffset: { width: 0, height: 6 }, elevation: 12,
  },
  title: { fontSize: V2Type.title, color: V2T.text },
  row: { flexDirection: "row", gap: 10, marginTop: 14, alignItems: "flex-start" },
  main: { fontSize: V2Type.secondary, color: V2T.text },
  est: { fontSize: V2Type.label, color: V2T.text3 },
  sub: { fontSize: V2Type.label, color: V2T.text2, marginTop: 3 },
  foot: { marginTop: 16, gap: 3, borderTopWidth: 1, borderTopColor: V2T.line, paddingTop: 10 },
  footTxt: { fontSize: 11, color: V2T.text3 },
  btns: { flexDirection: "row", alignItems: "center", gap: 18, marginTop: 16 },
  done: {
    backgroundColor: V2T.accent, borderRadius: V2Radius.pill,
    paddingHorizontal: 22, paddingVertical: 11,
  },
  doneTxt: { fontSize: V2Type.secondary, color: V2T.bg },
  howTxt: { fontSize: V2Type.label, color: V2T.accent },
});
