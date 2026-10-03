/** Arrival receipt (doc 02 §S7 + doc 10 claims ledger).
 *
 *   You're here.                                        [ Auto ]
 *   ─────────────────────────────────────────────────────────────
 *   🚬 YOU BREATHED
 *   ≈ 0.12 cigarettes  est.
 *   est. 35–52 µg                       (the honest band, when it spreads)
 *   [████▏▏ ▏ ▏  ◯───────────────]🚬    dose ruler: 0 → 1 cigarette,
 *                                        ◯ = smokiest planned option
 *   2.8× less than by auto
 *   ─────────────────────────────────────────────────────────────
 *   ≈ 1.4 kg          6.2 km          31 min
 *   put out           distance        time
 *   est. — for vehicles like yours · 1.1–1.6 kg
 *   incl. 0.02–0.04 g of fine particles
 *   metro would have put out ≈ 0.3 kg
 *   ─────────────────────────────────────────────────────────────
 *   updated 4 min ago · kept on this phone only
 *   [        Done        ]   [ Share ]
 *   How we got this                    save
 *
 * Copy rules honoured: cigarette equivalence only via "≈ N cigarettes"
 * (claims ledger), emissions labelled "est. — for vehicles like yours",
 * bands kept {lo,mid,hi} internally and shown where they're honest
 * (dose µg range + fine-particle g range), field age always visible,
 * donation line says what actually happened. No bare numbers: every
 * figure gets a comparison or an "est." tag. Honest empty states —
 * a missing band says so instead of showing 0.
 *
 * ── PROPOSED strings.ts keys (strings.ts owned by the i18n lane — do
 *    not edit here; LOCAL below carries interim en+hi strings with the
 *    same interpolation contract, swap to t() once the keys land) ──
 *    receipt_distance:   "distance"          / "दूरी"
 *    receipt_duration:   "time"              / "समय"
 *    receipt_doseUgBand: "est. {lo}–{hi} µg" / "अनुमान {lo}–{hi} µg"
 *    receipt_save:       "save"              / "सहेजें"
 */
import React from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { CIG_UG, NUM, V2Radius, V2T, V2Type, cigOf, fam } from "../../theme";
import { Icon, vehicleGlyph } from "../../icons";
import { t, type Lang } from "../../i18n/strings";
import { DYNAMIC_TYPE, a11y, slop } from "../../a11y";
import type { Band } from "../../nav/strip";

export type ReceiptAlt = { label: string; co2KgMid: number | null };

export type ReceiptData = {
  durationMin: number;
  modeLabel?: string | null;
  /** raw mode key (e.g. "auto", "metro") — drives the chip glyph when the
   *  caller knows it; the chip is text-only when only modeLabel exists */
  mode?: string | null;
  /** trip length actually travelled, km (NavSummary.distanceKm) — the
   *  stats row drops the distance cell honestly when it's absent */
  distanceKm?: number | null;
  /** breathed band, µg — null when the strip never arrived */
  doseUg: Band | null;
  /** put-out bands — null when the mode emits nothing we model */
  co2Kg: Band | null;
  pm25G: Band | null;
  /** worst option's planned dose, µg → the "× less" comparison + ruler mark */
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

type LocalKey =
  | "receipt_distance" | "receipt_duration"
  | "receipt_doseUgBand" | "receipt_save";
/** Interim strings for the proposed keys above — same t() contract. */
const LOCAL: Record<Lang, Record<LocalKey, string>> = {
  en: {
    receipt_distance: "distance",
    receipt_duration: "time",
    receipt_doseUgBand: "est. {lo}–{hi} µg",
    receipt_save: "save",
  },
  hi: {
    receipt_distance: "दूरी",
    receipt_duration: "समय",
    receipt_doseUgBand: "अनुमान {lo}–{hi} µg",
    receipt_save: "सहेजें",
  },
};
const lt = (key: LocalKey, lang: Lang, vars?: Record<string, string | number>) => {
  let s = LOCAL[lang][key] ?? LOCAL.en[key];
  if (vars) for (const [k, v] of Object.entries(vars)) s = s.replaceAll(`{${k}}`, String(v));
  return s;
};

const r1 = (n: number) => Math.round(n * 10) / 10;
const r2 = (n: number) => Math.round(n * 100) / 100;

/** Dose ruler — this trip's band on the 0 → 1 cigarette scale
 *  (`CIG_UG` = 316 µg inhaled PM2.5, the Berkeley Earth rule —
 *  docs/plan/06-science.md §1, doc 10; same constant the cigarette
 *  strings already use, so the visual can never contradict the copy).
 *  Solid fill = mid estimate; whisker ticks = the honest lo/hi band;
 *  hollow ring = the smokiest planned option (prop, not invented);
 *  upright tick + the cigarette glyph mark where one cigarette sits.
 *  The scale extends past one cigarette on genuinely heavy trips —
 *  the tick keeps the 1 🚬 point calibrated instead of clamping. */
function DoseScale({ dose, worstUg, a11yLabel }: {
  dose: Band; worstUg?: number | null; a11yLabel: string;
}) {
  const scaleMax = Math.max(CIG_UG, dose.hi, worstUg ?? 0, 1);
  const pct = (v: number): `${number}%` =>
    `${Math.max(0, Math.min(100, (v / scaleMax) * 100))}%`;
  return (
    <View style={s.scaleRow} accessible accessibilityRole="image"
      accessibilityLabel={a11yLabel}>
      <View style={s.scaleTrack}>
        <View style={[s.scaleFill, { width: pct(dose.mid) }]} />
        {dose.hi - dose.lo >= 1 && (
          <>
            <View style={[s.scaleWhisker, { left: pct(dose.lo) }]} />
            <View style={[s.scaleWhisker, { left: pct(dose.hi) }]} />
          </>
        )}
        {scaleMax > CIG_UG && (
          <View style={[s.scaleCigTick, { left: pct(CIG_UG) }]} />
        )}
        {worstUg != null && worstUg > dose.mid * 1.02 && (
          <View style={[s.scaleWorst, { left: pct(worstUg) }]} />
        )}
      </View>
      <Icon name="cigarette" color={V2T.text3} size={13} />
    </View>
  );
}

export function ReceiptSheet({
  data, lang, onDone, onHowWeGotThis, onShare, onSave,
}: {
  data: ReceiptData | null; lang: Lang;
  onDone: () => void; onHowWeGotThis?: (() => void) | null;
  /** secondary action — share the receipt (integrator wires the sheet /
   *  system share); the button only appears when the callback exists */
  onShare?: (() => void) | null;
  /** tertiary action — explicit save to the trip ledger */
  onSave?: (() => void) | null;
}) {
  if (!data) return null;
  const dose = data.doseUg;
  const cigs = dose ? cigOf(dose.mid) : null;
  const worst = data.worstDoseUg;
  const ratio = dose != null && worst != null && dose.mid > 0.5
    ? Math.round((worst / dose.mid) * 10) / 10
    : null;
  const savedCigs = dose != null && worst != null
    ? cigOf(Math.max(0, worst - dose.mid))
    : null;

  const mins = Math.max(1, Math.round(data.durationMin));
  const co2 = data.co2Kg;
  const co2Zero = co2 != null && co2.hi <= 0;
  const breathedTxt = cigs != null
    ? t("receipt_breathed", lang, { n: cigs > 0 && cigs < 0.01 ? 0.01 : cigs })
    : null;
  const ratioTxt = ratio != null && ratio > 1.05
    ? (data.worstLabel
        ? t("receipt_lessVs", lang, { n: ratio, m: data.worstLabel })
        : t("receipt_lessVsWorst", lang, { n: ratio }))
    : null;
  const scaleA11y = [breathedTxt, ratioTxt].filter(Boolean).join(". ");

  return (
    <View style={s.sheet}>
      {/* ── header: arrival + mode chip ── */}
      <View style={s.head}>
        <Text style={[s.title, { fontFamily: fam(lang, "semi") }]} {...DYNAMIC_TYPE}>
          {t("youreHere", lang)}
        </Text>
        {data.modeLabel ? (
          <View style={s.modeChip}>
            {data.mode ? (
              <Icon name={vehicleGlyph(data.mode)} color={V2T.text2} size={14} />
            ) : null}
            <Text style={[s.modeChipTxt, { fontFamily: fam(lang, "med") }]}
              numberOfLines={1} {...DYNAMIC_TYPE}>
              {data.modeLabel}
            </Text>
          </View>
        ) : null}
      </View>

      {/* ── hero: what you breathed ── */}
      <View style={s.eyebrowRow}>
        <Icon name="cigarette" color={V2T.breath1} size={15} />
        <Text style={[s.eyebrow, { fontFamily: fam(lang, "med") }]} {...DYNAMIC_TYPE}>
          {t("youBreathed", lang)}
        </Text>
      </View>
      {cigs == null ? (
        <Text style={[s.heroNone, { fontFamily: fam(lang, "med") }]} {...DYNAMIC_TYPE}>
          {t("receipt_noDose", lang)}
        </Text>
      ) : (
        <>
          <Text style={[s.heroNum, NUM, { fontFamily: fam(lang, "semi") }]} {...DYNAMIC_TYPE}>
            {t("nav_cigs", lang, { n: cigs > 0 && cigs < 0.01 ? 0.01 : cigs })}
            <Text style={s.est}>  {t("receipt_estShort", lang)}</Text>
          </Text>
          {dose && dose.hi - dose.lo >= 1 && (
            <Text style={[s.bandTxt, NUM]} {...DYNAMIC_TYPE}>
              {lt("receipt_doseUgBand", lang, {
                lo: Math.round(dose.lo), hi: Math.round(dose.hi),
              })}
            </Text>
          )}
          {dose && (
            <DoseScale dose={dose} worstUg={worst} a11yLabel={scaleA11y} />
          )}
          {ratioTxt ? (
            <Text style={[s.sub, { fontFamily: fam(lang, "reg") }]} {...DYNAMIC_TYPE}>
              {ratioTxt}
            </Text>
          ) : null}
          {savedCigs != null && savedCigs >= 0.02 && (
            <Text style={[s.sub, { fontFamily: fam(lang, "reg") }]} {...DYNAMIC_TYPE}>
              {t("receiptSaved", lang, { n: savedCigs })}
            </Text>
          )}
        </>
      )}

      {/* ── stats grid: put out · distance · time ── */}
      <View style={s.grid}>
        <View style={s.cell}>
          <Text style={[s.cellVal, NUM, { fontFamily: fam(lang, "med") }]}
            numberOfLines={1} {...DYNAMIC_TYPE}>
            {co2 == null ? "—" : t("nav_kg", lang, { n: r1(Math.max(0, co2.mid)) })}
          </Text>
          <Text style={[s.cellCap, { fontFamily: fam(lang, "reg") }]}
            numberOfLines={1} {...DYNAMIC_TYPE}>
            {t("putOut", lang)}
          </Text>
        </View>
        {data.distanceKm != null && (
          <View style={s.cell}>
            <Text style={[s.cellVal, NUM, { fontFamily: fam(lang, "med") }]}
              numberOfLines={1} {...DYNAMIC_TYPE}>
              {`${r1(Math.max(0, data.distanceKm))} ${t("unitsKm", lang)}`}
            </Text>
            <Text style={[s.cellCap, { fontFamily: fam(lang, "reg") }]}
              numberOfLines={1} {...DYNAMIC_TYPE}>
              {lt("receipt_distance", lang)}
            </Text>
          </View>
        )}
        <View style={s.cell}>
          <Text style={[s.cellVal, NUM, { fontFamily: fam(lang, "med") }]}
            numberOfLines={1} {...DYNAMIC_TYPE}>
            {`${mins} ${t("minUnit", lang)}`}
          </Text>
          <Text style={[s.cellCap, { fontFamily: fam(lang, "reg") }]}
            numberOfLines={1} {...DYNAMIC_TYPE}>
            {lt("receipt_duration", lang)}
          </Text>
        </View>
      </View>

      {/* ── emissions footnotes: band, particles, the alternative ── */}
      {co2 != null && (
        <View style={s.detail}>
          {co2Zero ? (
            <Text style={[s.detailTxt, { fontFamily: fam(lang, "reg") }]} {...DYNAMIC_TYPE}>
              {t("receipt_putOutNone", lang)}
            </Text>
          ) : (
            <>
              <Text style={[s.detailTxt, NUM]} {...DYNAMIC_TYPE}>
                {t("receipt_estLike", lang)}
                {co2.hi - co2.lo > 0.05
                  ? `  ·  ${r1(co2.lo)}–${r1(co2.hi)} kg`
                  : ""}
              </Text>
              {data.pm25G != null && data.pm25G.hi > 0 && (
                <Text style={[s.detailTxt, NUM]} {...DYNAMIC_TYPE}>
                  {t("receipt_pmBand", lang, {
                    lo: r2(data.pm25G.lo), hi: r2(data.pm25G.hi),
                  })}
                </Text>
              )}
              {data.alt && data.alt.co2KgMid != null && (
                <Text style={[s.detailTxt, { fontFamily: fam(lang, "reg") }]} {...DYNAMIC_TYPE}>
                  {t("receipt_altPutOut", lang, {
                    m: data.alt.label, n: r1(Math.max(0, data.alt.co2KgMid)),
                  })}
                </Text>
              )}
            </>
          )}
        </View>
      )}

      {/* ── provenance ── */}
      <View style={s.foot}>
        <Text style={[s.footTxt, { fontFamily: fam(lang, "reg") }]} {...DYNAMIC_TYPE}>
          {[
            data.fieldAgeMin != null
              ? t("updatedMinAgo", lang, { n: Math.max(0, Math.round(data.fieldAgeMin)) })
              : null,
            data.donated ? t("receipt_donated", lang) : t("receipt_private", lang),
          ].filter(Boolean).join("  ·  ")}
        </Text>
      </View>

      {/* ── actions: primary done · secondary share · tertiary info/save ── */}
      <View style={s.btns}>
        <Pressable onPress={onDone}
          style={({ pressed }) => [s.done, pressed && s.pressed]}
          {...a11y(t("done", lang), undefined, "button", { lang })}>
          <Text style={[s.doneTxt, { fontFamily: fam(lang, "semi") }]} {...DYNAMIC_TYPE}>
            {t("done", lang)}
          </Text>
        </Pressable>
        {onShare ? (
          <Pressable onPress={onShare}
            style={({ pressed }) => [s.share, pressed && s.pressed]}
            {...a11y(t("share", lang), undefined, "button", { lang })}>
            <Icon name="share" color={V2T.accent} size={16} />
            <Text style={[s.shareTxt, { fontFamily: fam(lang, "med") }]} {...DYNAMIC_TYPE}>
              {t("share", lang)}
            </Text>
          </Pressable>
        ) : null}
      </View>
      {(onHowWeGotThis || onSave) && (
        <View style={s.tertiaryRow}>
          {onHowWeGotThis ? (
            <Pressable onPress={onHowWeGotThis} hitSlop={slop(10)}
              style={({ pressed }) => [s.tertiary, pressed && s.pressed]}
              {...a11y(t("howWeGotThis", lang), undefined, "button", { lang })}>
              <Text style={[s.tertiaryTxt, { fontFamily: fam(lang, "med") }]} {...DYNAMIC_TYPE}>
                {t("howWeGotThis", lang)}
              </Text>
            </Pressable>
          ) : null}
          {onSave ? (
            <Pressable onPress={onSave} hitSlop={slop(10)}
              style={({ pressed }) => [s.tertiary, pressed && s.pressed]}
              {...a11y(lt("receipt_save", lang), undefined, "button", { lang })}>
              <Text style={[s.tertiaryTxt, { fontFamily: fam(lang, "med") }]} {...DYNAMIC_TYPE}>
                {lt("receipt_save", lang)}
              </Text>
            </Pressable>
          ) : null}
        </View>
      )}
    </View>
  );
}

const s = StyleSheet.create({
  sheet: {
    position: "absolute", left: 12, right: 12, bottom: 28,
    backgroundColor: V2T.surface, borderRadius: V2Radius.sheet,
    borderWidth: 1, borderColor: V2T.line, padding: 18, paddingBottom: 14,
    shadowColor: "#000", shadowOpacity: 0.55, shadowRadius: 18,
    shadowOffset: { width: 0, height: 6 }, elevation: 12,
  },

  /* header */
  head: { flexDirection: "row", alignItems: "center", gap: 10 },
  title: { flex: 1, fontSize: V2Type.title, color: V2T.text },
  modeChip: {
    flexDirection: "row", alignItems: "center", gap: 5,
    backgroundColor: V2T.surface2, borderRadius: V2Radius.pill,
    borderWidth: 1, borderColor: V2T.line,
    paddingHorizontal: 10, paddingVertical: 5, maxWidth: "55%",
  },
  modeChipTxt: { fontSize: V2Type.label, color: V2T.text2 },

  /* hero — what you breathed */
  eyebrowRow: { flexDirection: "row", alignItems: "center", gap: 7, marginTop: 16 },
  eyebrow: { fontSize: V2Type.label, color: V2T.text2, letterSpacing: 0.3 },
  heroNum: { fontSize: V2Type.hero, color: V2T.text, marginTop: 6 },
  heroNone: { fontSize: V2Type.secondary, color: V2T.text2, marginTop: 8 },
  est: { fontSize: V2Type.label, color: V2T.text3 },
  bandTxt: { fontSize: V2Type.label, color: V2T.text3, marginTop: 2 },
  sub: { fontSize: V2Type.label, color: V2T.text2, marginTop: 6 },

  /* dose ruler */
  scaleRow: { flexDirection: "row", alignItems: "center", gap: 8, marginTop: 10 },
  scaleTrack: {
    flex: 1, height: 5, borderRadius: 2.5, backgroundColor: V2T.line,
    overflow: "visible",
  },
  scaleFill: {
    position: "absolute", left: 0, top: 0, bottom: 0,
    borderRadius: 2.5, backgroundColor: V2T.breath1, minWidth: 2,
  },
  scaleWhisker: {
    position: "absolute", top: -2, width: 2.5, height: 9,
    borderRadius: 1.25, backgroundColor: V2T.breath2, marginLeft: -1.25,
  },
  scaleCigTick: {
    position: "absolute", top: -2, width: 2, height: 9,
    borderRadius: 1, backgroundColor: V2T.text3, marginLeft: -1,
  },
  scaleWorst: {
    position: "absolute", top: -2.5, width: 10, height: 10,
    borderRadius: 5, borderWidth: 2, borderColor: V2T.out1,
    backgroundColor: V2T.surface, marginLeft: -5,
  },

  /* stats grid */
  grid: {
    flexDirection: "row", marginTop: 16,
    backgroundColor: V2T.surface2, borderRadius: V2Radius.row,
    borderWidth: 1, borderColor: V2T.line,
    paddingVertical: 10, paddingHorizontal: 4,
  },
  cell: { flex: 1, paddingHorizontal: 10, gap: 2 },
  cellVal: { fontSize: V2Type.secondary, color: V2T.text },
  cellCap: { fontSize: 11, color: V2T.text3 },

  /* emissions footnotes */
  detail: { marginTop: 10, gap: 3, paddingHorizontal: 2 },
  detailTxt: { fontSize: 11, color: V2T.text3 },

  /* provenance */
  foot: { marginTop: 14, borderTopWidth: 1, borderTopColor: V2T.line, paddingTop: 10 },
  footTxt: { fontSize: 11, color: V2T.text3 },

  /* actions */
  btns: { flexDirection: "row", alignItems: "center", gap: 10, marginTop: 14 },
  done: {
    flex: 1, minHeight: 44, alignItems: "center", justifyContent: "center",
    backgroundColor: V2T.accent, borderRadius: V2Radius.pill,
    paddingHorizontal: 22, paddingVertical: 11,
  },
  doneTxt: { fontSize: V2Type.secondary, color: V2T.bg },
  share: {
    minHeight: 44, flexDirection: "row", alignItems: "center", gap: 7,
    borderRadius: V2Radius.pill, borderWidth: 1, borderColor: V2T.line,
    backgroundColor: V2T.surface2, paddingHorizontal: 18, paddingVertical: 11,
  },
  shareTxt: { fontSize: V2Type.secondary, color: V2T.accent },
  tertiaryRow: {
    flexDirection: "row", alignItems: "center", justifyContent: "center",
    gap: 28, marginTop: 2,
  },
  tertiary: { minHeight: 44, justifyContent: "center", paddingHorizontal: 8 },
  tertiaryTxt: { fontSize: V2Type.label, color: V2T.accent },
  pressed: { opacity: 0.65 },
});
