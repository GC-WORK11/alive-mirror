/** DepartGraph — the "leave later" dose curve (lane r4-departgraph).
 *  x = departure hour over the next 24h, y = estimated inhaled dose (µg)
 *  for the SAME route — data comes from GET /depart (src/api/depart.ts,
 *  `DepartSlot[]` is a structural superset of `DepartDatum` so
 *  `curve.slots` feeds `data` directly).
 *
 *  Pure RN Views — no chart lib, no svg. One candlestick column per
 *  hour: a thin whisker spans dose_lo→dose_hi when the band is known,
 *  the solid bar marks dose_mid. Best hour = accent; the "now" hour is
 *  the brighter baseline; a tapped column brightens and reports back.
 *
 *  Mount (CompareSheet/Sidebar integration):
 *    const c = await fetchDepartCurve({ from, to, vehicle: option.mode });
 *    <DepartGraph
 *      data={c?.slots ?? []}
 *      bestHour={c?.best?.hour ?? 0}
 *      selectedHour={picked}                    // optional — uncontrolled ok
 *      onSelectHour={(h) => setPicked(h)}       // optional
 *      lang={lang} />
 *
 *  NOTE(l10n): the single UI word "now" is a local map below — move it
 *  into i18n/strings.ts at integration (strings.ts is shared; this lane
 *  is constrained to new files only). "est." reuses receipt_estShort.
 */
import React, { useMemo, useState } from "react";
import { Pressable, StyleSheet, Text, View, type LayoutChangeEvent } from "react-native";
import { NUM, V2T, V2Type, fam, famMono } from "../theme";
import { DYNAMIC_TYPE } from "../a11y";
import { t, type Lang } from "../i18n/strings";

export type DepartDatum = {
  hour: number;                      // hours ahead of now (0 = leave now)
  dose_mid: number;                  // µg inhaled — the point estimate
  dose_lo?: number | null;           // honest band, when the source has one
  dose_hi?: number | null;
  start?: string | null;             // naive ISO (UTC basis) → clock labels
};

export type DepartGraphProps = {
  data: DepartDatum[];
  /** `hour` value of the lightest slot — highlighted in accent */
  bestHour: number;
  /** controlled selection; omit to let taps highlight internally */
  selectedHour?: number;
  /** tap callback — (hour, datum) */
  onSelectHour?: (hour: number, d: DepartDatum) => void;
  lang: Lang;
  /** bar-area height in pt; whole component is ~height+56 (axis+caption) */
  height?: number;
};

/* "now" moved into strings.ts (departNow) — the local map predated the
   key; t() keeps en+hi in step with the rest of the sheet. */

const TICK_W = 48;

/** naive-UTC ISO → IST wall-clock "HH:00" (mirrors CompareSheet.hourLabel) */
const clockOf = (iso: string | null | undefined): string | null => {
  if (!iso) return null;
  const d = new Date(iso.endsWith("Z") ? iso : iso + "Z");
  if (isNaN(d.getTime())) return null;
  const ist = new Date(d.getTime() + 5.5 * 3600 * 1000);
  return `${String(ist.getUTCHours()).padStart(2, "0")}:${String(ist.getUTCMinutes()).padStart(2, "0")}`;
};

export function DepartGraph({
  data, bestHour, selectedHour, onSelectHour, lang, height = 64,
}: DepartGraphProps) {
  const [innerSel, setInnerSel] = useState<number | null>(null);
  const [axisW, setAxisW] = useState(0);
  const sel = selectedHour ?? innerSel;

  const rows = useMemo(
    () => [...data].filter((d) => Number.isFinite(d.dose_mid)).sort((a, b) => a.hour - b.hour),
    [data],
  );
  const n = rows.length;
  const max = useMemo(
    () => Math.max(1e-6, ...rows.map((d) => Math.max(d.dose_mid, d.dose_hi ?? 0))),
    [rows],
  );
  const y = (v: number) => Math.max(2, (v / max) * height);

  /* labelled ticks: now / +6h / +12h / +18h / last slot — driven by the
     data's own hour values so a short curve stays honest */
  const tickIdx = useMemo(() => {
    const want = new Set([0, 6, 12, 18, rows[n - 1]?.hour ?? -1]);
    const out: number[] = [];
    rows.forEach((d, i) => { if (want.has(d.hour)) out.push(i); });
    return out;
  }, [rows, n]);

  if (!n) return null;
  const nowHour = rows[0].hour;
  const best = rows.find((d) => d.hour === bestHour) ?? null;
  const detail = rows.find((d) => d.hour === sel) ?? best;

  const onAxis = (e: LayoutChangeEvent) => setAxisW(e.nativeEvent.layout.width);

  /* bars carry the dose they plot — the same warm in-ramp the option
     bars use (heavier hour = warmer bar); best hour stays accent, a
     tapped column still wins in ink */
  const breathRamp = (f: number) =>
    f > 0.66 ? V2T.breath3 : f > 0.33 ? V2T.breath2 : V2T.breath1;
  const barColor = (d: DepartDatum) =>
    d.hour === bestHour ? V2T.accent : d.hour === sel ? V2T.text
      : breathRamp(d.dose_mid / max);

  return (
    <View style={s.wrap}>
      {/* ── bars ── */}
      <View style={[s.bars, { height }]}>
        {rows.map((d) => {
          const c = barColor(d);
          const lo = d.dose_lo ?? d.dose_mid;
          const hi = d.dose_hi ?? d.dose_mid;
          const banded = hi > lo;
          const col = (
            <View style={[s.col, sel === d.hour && s.colSel]}>
              {d.hour === bestHour && <View style={s.bestDot} />}
              {banded && (
                <View style={[
                  s.whisker,
                  { bottom: y(lo), height: Math.max(2, y(hi) - y(lo)), backgroundColor: `${c}66` },
                ]} />
              )}
              <View style={[s.bar, { height: y(d.dose_mid), backgroundColor: c }]} />
            </View>
          );
          const a11y = `${d.hour === nowHour ? t("departNow", lang) : `+${d.hour}h`} ≈ ${Math.round(d.dose_mid)} µg`;
          return onSelectHour ? (
            <Pressable
              key={d.hour} style={s.cell} accessibilityRole="button" accessibilityLabel={a11y}
              onPress={() => { setInnerSel(d.hour); onSelectHour(d.hour, d); }}
              hitSlop={4}>
              {col}
            </Pressable>
          ) : (
            <View key={d.hour} style={s.cell} accessibilityLabel={a11y}>{col}</View>
          );
        })}
      </View>

      {/* ── axis: "+Nh" over wall-clock, at 0/6/12/18/last ── */}
      <View style={s.axis} onLayout={onAxis}>
        {tickIdx.map((i) => {
          const d = rows[i];
          const cx = ((i + 0.5) / n) * axisW;             // bar-centre px
          const left = Math.max(0, Math.min(axisW - TICK_W, cx - TICK_W / 2));
          return (
            <View key={d.hour} style={[s.tick, { left }]}>
              <Text {...DYNAMIC_TYPE} style={[s.tickOffset, { fontFamily: fam(lang, "reg") }, d.hour === bestHour && { color: V2T.accent }]} numberOfLines={1}>
                {d.hour === nowHour ? t("departNow", lang) : `+${d.hour}h`}
              </Text>
              <Text {...DYNAMIC_TYPE} style={[s.tickClock, NUM, { fontFamily: famMono(lang, "reg") }]} numberOfLines={1}>
                {clockOf(d.start) ?? " "}
              </Text>
            </View>
          );
        })}
      </View>

      {/* ── honest caption: "est." + the focused slot's clock + dose ── */}
      <View style={s.caption}>
        <Text {...DYNAMIC_TYPE} style={[s.capTxt, { fontFamily: fam(lang, "reg") }]}>
          {t("receipt_estShort", lang)}
        </Text>
        {detail && (
          <Text {...DYNAMIC_TYPE} style={[s.capTxt, s.capVal, NUM, { fontFamily: famMono(lang, "reg") }]}>
            {`${detail.hour === nowHour ? t("departNow", lang) : `+${detail.hour}h`}` +
              `${clockOf(detail.start) ? ` · ${clockOf(detail.start)}` : ""} ≈ ${Math.round(detail.dose_mid)} µg`}
          </Text>
        )}
      </View>
    </View>
  );
}

const s = StyleSheet.create({
  wrap: { paddingHorizontal: 4 },
  bars: { flexDirection: "row", alignItems: "stretch" },
  cell: { flex: 1 },
  col: { flex: 1, alignItems: "center", justifyContent: "flex-end", borderRadius: 5 },
  colSel: { backgroundColor: V2T.accentTint }, // solid tint — no rgba surface fills (doc 03)
  bar: { width: "58%", minWidth: 4, maxWidth: 11, borderRadius: 2 },
  whisker: { position: "absolute", width: 3, borderRadius: 1.5, alignSelf: "center" },
  bestDot: {
    position: "absolute", top: 1, width: 4, height: 4, borderRadius: 2,
    backgroundColor: V2T.accent, alignSelf: "center",
  },
  axis: { position: "relative", height: 30, marginTop: 3 },
  tick: { position: "absolute", width: TICK_W, alignItems: "center" },
  tickOffset: { fontSize: 10, color: V2T.text2, lineHeight: 13 },
  tickClock: { fontSize: 9, color: V2T.text3, lineHeight: 12 },
  caption: {
    flexDirection: "row", justifyContent: "space-between", alignItems: "baseline",
    marginTop: 4, paddingHorizontal: 2,
  },
  capTxt: { fontSize: V2Type.label, color: V2T.text3 },
  capVal: { color: V2T.text2 },
});

export default DepartGraph;
