/** Arrival receipt (doc 02 §S7 + doc 10 claims ledger).
 *
 *   You're here.                                        [ Auto ]
 *   ─────────────────────────────────────────────────────────────
 *   🚬/∿ YOU BREATHED
 *   ≈ 42 µg  est.                       (≈ 0.12 cigarettes with showCig on)
 *   est. 35–52 µg                       (the honest band, when it spreads)
 *   [████▏▏ ▏ ▏  ◯───────────────]🚬    dose ruler: 0 → 1 cigarette —
 *                                        scales to trip/worst µg when
 *                                        the metaphor is off;
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
 */
import React, { useEffect, useState } from "react";
import { Animated, Pressable, StyleSheet, Text, View } from "react-native";
import { CIG_UG, NUM, V2Elev, V2Radius, V2T, V2Type, cigOf, fam, famMonoText, famSerif } from "../../theme";
import { Icon, vehicleGlyph } from "../../icons";
import { approx, doseUgRound, t, type Lang } from "../../i18n/strings";
import { DYNAMIC_TYPE, a11y, slop, useReduceMotion } from "../../a11y";
import { PressSpring } from "../PressSpring";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import type { Band } from "../../nav/strip";
import { bump, jank } from "../../perf";

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
  /** donation result: "sent" = server took it; "queued" = in the outbox,
   *  honest pending state; false = kept private (or share off) */
  donated?: "sent" | "queued" | false;
  /** true when the rider ended the trip manually before reaching the
      destination — the header must not claim "You're here" */
  endedEarly?: boolean;
};

const r1 = (n: number) => Math.round(n * 10) / 10;
const r2 = (n: number) => Math.round(n * 100) / 100;

/** A stat tile that lands with the sheet — spring up + fade, ~80 ms
 *  behind the tile before it (doc 20 §6: the receipt is earned, so its
 *  numbers arrive instead of popping; ~250 ms settle, no overshoot).
 *  Reduce-motion → the tile is simply there. */
function StatTile({ index, reduce, children }: {
  index: number; reduce: boolean; children: React.ReactNode;
}) {
  const [v] = useState(() => new Animated.Value(reduce ? 1 : 0));
  const [ty] = useState(() =>
    v.interpolate({ inputRange: [0, 1], outputRange: [10, 0] }));
  useEffect(() => {
    if (reduce) { v.setValue(1); return; }
    Animated.spring(v, {
      toValue: 1, delay: 220 + index * 80,
      damping: 15, stiffness: 210, mass: 0.9, useNativeDriver: true,
    }).start();
  }, [v, index, reduce]);
  return (
    <Animated.View style={[s.cell, { opacity: v, transform: [{ translateY: ty }] }]}>
      {children}
    </Animated.View>
  );
}

/** Dose ruler — this trip's band on the 0 → 1 cigarette scale
 *  (`CIG_UG` = 316 µg inhaled PM2.5, the Berkeley Earth rule —
 *  docs/plan/06-science.md §1, doc 10; same constant the cigarette
 *  strings already use, so the visual can never contradict the copy).
 *  Solid fill = mid estimate; whisker ticks = the honest lo/hi band;
 *  hollow ring = the smokiest planned option (prop, not invented);
 *  upright tick + the cigarette glyph mark where one cigarette sits.
 *  The scale extends past one cigarette on genuinely heavy trips —
 *  the tick keeps the 1 🚬 point calibrated instead of clamping.
 *  With the cigarette metaphor off (showCig=false) the ruler drops the
 *  cig tick + glyph and scales to the trip/worst µg alone. */
function DoseScale({ dose, worstUg, showCig, a11yLabel }: {
  dose: Band; worstUg?: number | null; showCig: boolean; a11yLabel: string;
}) {
  bump("shell.DoseScale");
  const reduceMotion = useReduceMotion();
  const scaleMax = showCig
    ? Math.max(CIG_UG, dose.hi, worstUg ?? 0, 1)
    : Math.max(dose.hi, worstUg ?? 0, 1);
  const pct = (v: number): `${number}%` =>
    `${Math.max(0, Math.min(100, (v / scaleMax) * 100))}%`;
  /* the ruler fills to its real value on mount — the dose "lands" the
     way a gauge settles, honest motion for an earned number. Native
     driver: scaleX is a transform (the only safe native-driver flip in
     this file — no mixed animated graph, unlike Sheet), transformOrigin
     pins the left edge; reduce-motion jumps to done. */
  const [fillAnim] = useState(() => new Animated.Value(0));
  useEffect(() => {
    if (reduceMotion) { fillAnim.setValue(1); return; }
    jank("receipt.fill");
    Animated.timing(fillAnim, {
      toValue: 1, duration: 480, delay: 180, useNativeDriver: true,
    }).start();
  }, [fillAnim, reduceMotion]);
  return (
    <View style={s.scaleRow} accessible accessibilityRole="image"
      accessibilityLabel={a11yLabel}>
      <View style={s.scaleTrack}>
        <Animated.View style={[s.scaleFill, {
          width: pct(dose.mid),
          transform: [{ scaleX: fillAnim }],
          transformOrigin: "0% 50%",
        }]} />
        {dose.hi - dose.lo >= 1 && (
          <>
            <View style={[s.scaleWhisker, { left: pct(dose.lo) }]} />
            <View style={[s.scaleWhisker, { left: pct(dose.hi) }]} />
          </>
        )}
        {showCig && scaleMax > CIG_UG && (
          <View style={[s.scaleCigTick, { left: pct(CIG_UG) }]} />
        )}
        {worstUg != null && worstUg > dose.mid * 1.02 && (
          <View style={[s.scaleWorst, { left: pct(worstUg) }]} />
        )}
      </View>
      <Icon name="dust" color={V2T.text3} size={13} />
    </View>
  );
}

function ReceiptSheetInner({
  data, lang, onDone, onHowWeGotThis, onShare, onSave, showCig = false,
}: {
  data: ReceiptData | null; lang: Lang;
  /** cigarette-equivalence framing — off by default (settings.show_cig);
   *  off → the hero reads the µg dose and the ruler drops the cig marks */
  showCig?: boolean;
  onDone: () => void; onHowWeGotThis?: (() => void) | null;
  /** secondary action — share the receipt (integrator wires the sheet /
   *  system share); the button only appears when the callback exists */
  onShare?: (() => void) | null;
  /** tertiary action — explicit save to the trip ledger */
  onSave?: (() => void) | null;
}) {
  bump("shell.Receipt");
  const insets = useSafeAreaInsets();
  const reduceMotion = useReduceMotion();
  /* enter spring — the receipt rises + fades like a real earned card.
     Native driver: enter feeds only opacity + translateY through one
     interpolate — no Animated.add mixing JS + native nodes, so the
     ui.tsx:159 detach class does not apply here. */
  const [enter] = useState(() => new Animated.Value(0));
  const [enterTy] = useState(() =>
    enter.interpolate({ inputRange: [0, 1], outputRange: [26, 0] }));
  useEffect(() => {
    if (reduceMotion) { enter.setValue(1); return; }
    jank("enter.receipt");
    Animated.spring(enter, {
      toValue: 1, damping: 24, stiffness: 240, useNativeDriver: true,
    }).start();
  }, [enter, reduceMotion]);
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
  /* the same "would have added" figure in µg for the default surface */
  const savedUg = dose != null && worst != null
    ? Math.max(0, worst - dose.mid)
    : null;

  const mins = Math.max(1, Math.round(data.durationMin));
  const co2 = data.co2Kg;
  const co2Zero = co2 != null && co2.hi <= 0;
  const breathedTxt = dose != null
    ? `${t("youBreathed", lang)} ${t("doseUg", lang, { n: approx(doseUgRound(dose.mid)) })}`
    : null;
  /* show_cig demotes the metaphor to a secondary line — the equivalence
     stays available under the µg hero, never as the headline number */
  const cigTxt = showCig && cigs != null
    ? t("nav_cigs", lang, { n: approx(cigs > 0 && cigs < 0.01 ? 0.01 : cigs) })
    : null;
  const ratioTxt = ratio != null && ratio > 1.05
    ? (data.worstLabel
        ? t("receipt_lessVs", lang, { n: ratio, m: data.worstLabel })
        : t("receipt_lessVsWorst", lang, { n: ratio }))
    : null;
  const scaleA11y = [breathedTxt, ratioTxt, cigTxt].filter(Boolean).join(". ");

  return (
    <Animated.View style={[s.sheet, {
      bottom: insets.bottom + 14,
      opacity: enter,
      transform: [{ translateY: enterTy }],
    }]}>
      {/* ── header: arrival + mode chip ── */}
      <View style={s.head}>
        <Text style={[s.title, { fontFamily: famSerif(lang, "semi") }]} {...DYNAMIC_TYPE}>
          {t(data?.endedEarly ? "tripEnded" : "youreHere", lang)}
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
        <Icon name="dust" color={V2T.breath1} size={15} />
        <Text style={[s.eyebrow, { fontFamily: fam(lang, "med") }]} {...DYNAMIC_TYPE}>
          {t("youBreathed", lang)}
        </Text>
      </View>
      {dose == null ? (
        <Text style={[s.heroNone, { fontFamily: fam(lang, "med") }]} {...DYNAMIC_TYPE}>
          {t("receipt_noDose", lang)}
        </Text>
      ) : (
        <>
          <Text style={[s.heroNum, NUM, { fontFamily: famSerif(lang, "semi") }]} {...DYNAMIC_TYPE}>
            {t("doseUg", lang, { n: approx(doseUgRound(dose.mid)) })}
            <Text {...DYNAMIC_TYPE} style={s.est}>  {t("receipt_estShort", lang)}</Text>
          </Text>
          {dose.hi - dose.lo >= 1 && (
            <Text style={[s.bandTxt, NUM, { fontFamily: famMonoText(lang) }]} {...DYNAMIC_TYPE}>
              {t("receipt_doseUgBand", lang, {
                lo: doseUgRound(dose.lo), hi: doseUgRound(dose.hi),
              })}
            </Text>
          )}
          {/* cigarette equivalence — secondary line under the hero when
              the user opted in; never the headline (owner rule) */}
          {cigTxt != null && (
            <Text style={[s.bandTxt, NUM, { fontFamily: famMonoText(lang) }]} {...DYNAMIC_TYPE}>
              {cigTxt}
            </Text>
          )}
          <DoseScale dose={dose} worstUg={worst} showCig={showCig} a11yLabel={scaleA11y} />
          {ratioTxt ? (
            <Text style={[s.sub, { fontFamily: fam(lang, "reg") }]} {...DYNAMIC_TYPE}>
              {ratioTxt}
            </Text>
          ) : null}
          {savedUg != null && savedUg >= 6 && (
            <Text style={[s.sub, { fontFamily: fam(lang, "reg") }]} {...DYNAMIC_TYPE}>
              {t("receiptSavedUg", lang, { n: approx(doseUgRound(savedUg)) })}
              {showCig && savedCigs != null && savedCigs >= 0.02
                ? `  ·  ${t("nav_cigs", lang, { n: approx(savedCigs) })}`
                : ""}
            </Text>
          )}
        </>
      )}

      {/* ── stats grid: put out · distance · time — tiles land in a
          short cascade on open (spring up+fade ~80 ms apart) ── */}
      <View style={s.grid}>
        <StatTile index={0} reduce={reduceMotion}>
          <Text style={[s.cellVal, NUM, { fontFamily: famMonoText(lang, "med") }]}
            numberOfLines={1} {...DYNAMIC_TYPE}>
            {co2 == null ? "—" : t("nav_kg", lang, { n: approx(r1(Math.max(0, co2.mid))) })}
          </Text>
          <Text style={[s.cellCap, { fontFamily: fam(lang, "reg") }]}
            numberOfLines={1} {...DYNAMIC_TYPE}>
            {t("putOut", lang)}
          </Text>
        </StatTile>
        {data.distanceKm != null && (
          <StatTile index={1} reduce={reduceMotion}>
            <Text style={[s.cellVal, NUM, { fontFamily: famMonoText(lang, "med") }]}
              numberOfLines={1} {...DYNAMIC_TYPE}>
              {`${r1(Math.max(0, data.distanceKm))} ${t("unitsKm", lang)}`}
            </Text>
            <Text style={[s.cellCap, { fontFamily: fam(lang, "reg") }]}
              numberOfLines={1} {...DYNAMIC_TYPE}>
              {t("receipt_distance", lang)}
            </Text>
          </StatTile>
        )}
        <StatTile index={data.distanceKm != null ? 2 : 1} reduce={reduceMotion}>
          <Text style={[s.cellVal, NUM, { fontFamily: famMonoText(lang, "med") }]}
            numberOfLines={1} {...DYNAMIC_TYPE}>
            {`${mins} ${t("minUnit", lang)}`}
          </Text>
          <Text style={[s.cellCap, { fontFamily: fam(lang, "reg") }]}
            numberOfLines={1} {...DYNAMIC_TYPE}>
            {t("receipt_duration", lang)}
          </Text>
        </StatTile>
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
              <Text style={[s.detailTxt, NUM, { fontFamily: famMonoText(lang, "reg") }]} {...DYNAMIC_TYPE}>
                {t("receipt_estLike", lang)}
                {co2.hi - co2.lo > 0.05
                  /* the raw band survives the >0.05 gate but rounds to the
                     same 1dp value → "0.1–0.1 kg" read like a formatting bug;
                     collapse to the single value (NavChrome co2 precedent).
                     nav_kg also keeps the unit Devanagari in hi (किग्रा). */
                  ? `  ·  ${r1(co2.lo) === r1(co2.hi)
                    ? t("nav_kg", lang, { n: r1(co2.hi).toFixed(1) })
                    : t("nav_kg", lang, { n: `${r1(co2.lo)}–${r1(co2.hi)}` })}`
                  : ""}
              </Text>
              {data.pm25G != null && data.pm25G.hi > 0 && (() => {
                const lo = r2(data.pm25G.lo), hi = r2(data.pm25G.hi);
                /* a band that collapses at display precision: never print
                   "0–0"; a true-zero print would overstate, so a sub-
                   resolution band says <0.01 instead */
                const txt = lo === hi
                  ? (hi === 0 ? t("receipt_pmBandTiny", lang) : t("receipt_pmBandOne", lang, { x: hi }))
                  : t("receipt_pmBand", lang, { lo, hi });
                return <Text style={[s.detailTxt, NUM, { fontFamily: famMonoText(lang, "reg") }]} {...DYNAMIC_TYPE}>{txt}</Text>;
              })()}
              {data.alt && data.alt.co2KgMid != null && (
                <Text style={[s.detailTxt, { fontFamily: fam(lang, "reg") }]} {...DYNAMIC_TYPE}>
                  {t("receipt_altPutOut", lang, {
                    m: data.alt.label, n: approx(r1(Math.max(0, data.alt.co2KgMid))),
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
            data.donated === "sent"
              ? t("receipt_donated", lang)
              : data.donated === "queued"
                ? t("receipt_queued", lang)
                : t("receipt_private", lang),
          ].filter(Boolean).join("  ·  ")}
        </Text>
      </View>

      {/* ── actions: primary done · secondary share · tertiary info/save ── */}
      <View style={s.btns}>
        <PressSpring style={{ flex: 1 }}>
          <Pressable onPress={onDone}
            style={s.done}
            {...a11y(t("done", lang), undefined, "button", { lang })}>
            <Text style={[s.doneTxt, { fontFamily: fam(lang, "semi") }]} {...DYNAMIC_TYPE}>
              {t("done", lang)}
            </Text>
          </Pressable>
        </PressSpring>
        {onShare ? (
          <PressSpring>
            <Pressable onPress={onShare}
              style={s.share}
              {...a11y(t("share", lang), undefined, "button", { lang })}>
              <Icon name="share" color={V2T.accent} size={16} />
              <Text style={[s.shareTxt, { fontFamily: fam(lang, "med") }]} {...DYNAMIC_TYPE}>
                {t("share", lang)}
              </Text>
            </Pressable>
          </PressSpring>
        ) : null}
      </View>
      {(onHowWeGotThis || onSave) && (
        <View style={s.tertiaryRow}>
          {onHowWeGotThis ? (
            <PressSpring>
              <Pressable onPress={onHowWeGotThis} hitSlop={slop(10)}
                style={s.tertiary}
                {...a11y(t("howWeGotThis", lang), undefined, "button", { lang })}>
                <Text style={[s.tertiaryTxt, { fontFamily: fam(lang, "med") }]} {...DYNAMIC_TYPE}>
                  {t("howWeGotThis", lang)}
                </Text>
              </Pressable>
            </PressSpring>
          ) : null}
          {onSave ? (
            <PressSpring>
              <Pressable onPress={onSave} hitSlop={slop(10)}
                style={s.tertiary}
                {...a11y(t("receipt_save", lang), undefined, "button", { lang })}>
                <Text style={[s.tertiaryTxt, { fontFamily: fam(lang, "med") }]} {...DYNAMIC_TYPE}>
                  {t("receipt_save", lang)}
                </Text>
              </Pressable>
            </PressSpring>
          ) : null}
        </View>
      )}
    </Animated.View>
  );
}

export const ReceiptSheet = React.memo(ReceiptSheetInner);

const s = StyleSheet.create({
  sheet: {
    position: "absolute", left: 12, right: 12,
    /* solid paper pop — at 91% glass the destination's map labels and the
       MapLibre attribution ghosted through the footnotes; the map still
       frames the sheet's edges, the pane itself reads opaque */
    backgroundColor: V2T.bg, borderRadius: V2Radius.sheet,
    ...V2Elev.pop,
    padding: 18, paddingBottom: 14,
  },

  /* header */
  head: { flexDirection: "row", alignItems: "center", gap: 10 },
  title: { flex: 1, fontSize: V2Type.title, color: V2T.text },
  modeChip: {
    flexDirection: "row", alignItems: "center", gap: 5,
    backgroundColor: V2T.surface2, borderRadius: V2Radius.pill,
    paddingHorizontal: 11, paddingVertical: 6, maxWidth: "55%",
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
    flex: 1, height: 6, borderRadius: 3, backgroundColor: V2T.hairline,
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

  /* stats — each figure its own chip, not cells in a strip */
  grid: {
    flexDirection: "row", marginTop: 18, gap: 8,
  },
  cell: {
    flex: 1, paddingHorizontal: 10, gap: 2,
    backgroundColor: V2T.surface2, borderRadius: V2Radius.row,
    paddingVertical: 11, alignItems: "center",
  },
  cellVal: { fontSize: V2Type.body, color: V2T.text },
  cellCap: { fontSize: 11, color: V2T.text3 },

  /* emissions footnotes */
  detail: { marginTop: 10, gap: 3, paddingHorizontal: 2 },
  detailTxt: { fontSize: 11, color: V2T.text3 },

  /* provenance */
  foot: { marginTop: 14, borderTopWidth: 1, borderTopColor: V2T.glassLine, paddingTop: 10 },
  footTxt: { fontSize: 11, color: V2T.text3 },

  /* actions */
  btns: { flexDirection: "row", alignItems: "center", gap: 10, marginTop: 14 },
  done: {
    flex: 1, minHeight: 48, alignItems: "center", justifyContent: "center",
    backgroundColor: V2T.text, borderRadius: V2Radius.pill,
    paddingHorizontal: 22, paddingVertical: 12,
  },
  doneTxt: { fontSize: V2Type.secondary, color: V2T.bg },
  share: {
    minHeight: 48, flexDirection: "row", alignItems: "center", gap: 7,
    borderRadius: V2Radius.pill,
    backgroundColor: V2T.surface2, paddingHorizontal: 18, paddingVertical: 12,
  },
  shareTxt: { fontSize: V2Type.secondary, color: V2T.accentInk },
  tertiaryRow: {
    flexDirection: "row", alignItems: "center", justifyContent: "center",
    gap: 28, marginTop: 2,
  },
  tertiary: { minHeight: 44, justifyContent: "center", paddingHorizontal: 8 },
  tertiaryTxt: { fontSize: V2Type.label, color: V2T.accent },
});
