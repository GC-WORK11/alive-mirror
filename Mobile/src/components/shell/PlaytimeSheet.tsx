/** PlaytimeSheet — 'when to go out': the dedicated playtime surface.
 *
 *  The area's rolling next-24 h air as a real banded strip — one bar
 *  per served hour in its own CPCB band colour, a now-marker on the
 *  first bar, the lightest contiguous window underlined in forest —
 *  then the window in words ('today 08:30–18:30 · ~84 µg'), the
 *  heaviest run as a callout, and the server's own verdict + decisions.
 *  Warm and playful in shape, but every number is /v2/playtime's. */
import React, { useEffect, useMemo, useRef, useState } from "react";
import { ScrollView, StyleSheet, Text, View } from "react-native";
import { NUM, V2T, bandColor, fam } from "../../theme";
import { DYNAMIC_TYPE } from "../../a11y";
import { Sheet } from "../../ui";
import { t, type Lang } from "../../i18n/strings";
import { mark } from "../../perf";
import {
  fetchPlaytime,
  type ExploreAnchor, type ExploreMode, type PlaytimeData,
} from "../../api/explore";
import {
  ExploreHead, HonestChip, HonestLine, windowWords,
} from "./exploreShared";

type Props = {
  anchor: ExploreAnchor;
  lang: Lang;
  onModeChange: (m: ExploreMode) => void;
  onClose: () => void;
};

export function PlaytimeSheet({ anchor, lang, onModeChange, onClose }: Props) {
  const [data, setData] = useState<PlaytimeData | null>(null);
  const [failed, setFailed] = useState(false);
  const seq = useRef(0);

  useEffect(() => {
    mark("explore.play.show");
    const my = ++seq.current;
    let dead = false;
    (async () => {
      const d = await fetchPlaytime(anchor);
      if (dead || my !== seq.current) return;
      if (d) { setData(d); setFailed(false); } else setFailed(true);
    })();
    return () => { dead = true; };
  }, [anchor]);

  const anchorLine = useMemo(() => {
    const n = data?.near.name ?? ("name" in anchor ? anchor.name : null);
    return n ? t("exploreAnchorNear", lang, { place: n })
             : t("exploreAnchorNearYou", lang);
  }, [data, anchor, lang]);

  return (
    <Sheet detent="half" onClose={onClose} lang={lang} style={s.sheet}>
      <ExploreHead
        lang={lang}
        glyph="explore"
        title={t("explorePlayTitle", lang)}
        sub={anchorLine}
        disclosure={t("playDisclosure", lang)}
        siblingLabel={t("staysTitle", lang)}
        onSibling={() => onModeChange("stays")}
      />
      <PlaytimeBody data={data} failed={failed} lang={lang} />
    </Sheet>
  );
}

/* ------------------------------------------------------------------ */

function PlaytimeBody({ data, failed, lang }: {
  data: PlaytimeData | null; failed: boolean; lang: Lang;
}) {
  if (failed || (data && data.error))
    return <HonestLine lang={lang}
      text={data?.error ? t("exploreOutOfArea", lang)
                        : t("exploreNoCurve", lang)} />;
  if (!data)
    return <HonestLine lang={lang} text={t("exploreReading", lang)} />;
  if (!data.hours.length)
    return <HonestLine lang={lang} text={t("exploreNoCurve", lang)} />;

  const max = Math.max(...data.hours.map((h) => h.pm25_mid));
  const min = Math.min(...data.hours.map((h) => h.pm25_mid));
  const span = Math.max(1, max - min);
  const inWindow = (w: typeof data.best_window) => {
    const hs = new Set<number>();
    if (w) {
      const end = w.end_h ?? data.hours[data.hours.length - 1].h;
      for (let h = w.start_h; h <= end; h++) hs.add(h);
    }
    return hs;
  };
  const bestHs = inWindow(data.best_window);
  const worstHs = inWindow(data.worst_window);
  const best = data.best_window;
  const worst = data.worst_window;
  return (
    <ScrollView style={s.list} showsVerticalScrollIndicator={false}>
      {data.sparse && (
        <HonestChip lang={lang}
          text={data.nearest_station_km != null
            ? t("exploreThinRead", lang, { n: data.nearest_station_km })
            : t("exploreThinReadNoKm", lang)} />
      )}
      {/* the server's own sentence — it computed the windows, it names
          them honestly (flat days say so in the same register) */}
      <Text {...DYNAMIC_TYPE}
        style={[s.verdict, { fontFamily: fam(lang, "med") }]}>
        {data.verdict}
      </Text>

      {/* the banded strip — 24 served hours, each in its band colour,
          heights scaled to the day's own min–max */}
      <View style={s.strip}>
        {data.hours.map((h) => {
          const frac = 0.14 + 0.86 * ((h.pm25_mid - min) / span);
          const inBest = bestHs.has(h.h);
          const inWorst = worstHs.has(h.h);
          const col = bandColor(h.pm25_mid) ?? V2T.text4;
          /* hour-0's now-ness lives in the axis label below ('now ·
             08:30') — a floating word inside a 24-cell strip clips to
             two letters at this width (seen on sim), so nothing here
             carries text but the bars themselves */
          return (
            <View key={h.h} style={s.cell}>
              <View
                style={[s.bar, {
                  height: Math.max(6, Math.round(60 * frac)),
                  backgroundColor: col,
                  opacity: inBest ? 1 : 0.72,
                }]}
              />
              {/* the ground mark — forest under the lightest run, a
                  quiet stone tick under the heaviest */}
              <View style={[s.ground,
                inBest && s.groundBest,
                !inBest && inWorst && s.groundWorst]} />
            </View>
          );
        })}
      </View>
      <View style={s.axisRow}>
        <Text style={[s.axisTxt, NUM, { fontFamily: fam(lang, "reg") }]}>
          {t("exploreNowMarker", lang)} · {data.hours[0].ist_label}
        </Text>
        <Text style={[s.axisTxt, NUM, { fontFamily: fam(lang, "reg") }]}>
          {data.hours[data.hours.length - 1].ist_label}
          {data.hours[data.hours.length - 1].day_offset > 0
            ? ` · ${data.hours[data.hours.length - 1].day_offset === 1
                ? t("exploreTomorrow", lang)
                : t("exploreInDays", lang,
                    { n: data.hours[data.hours.length - 1].day_offset })}`
            : ""}
        </Text>
      </View>

      {/* the windows in words */}
      {best && (
        <Text {...DYNAMIC_TYPE}
          style={[s.bestLine, { fontFamily: fam(lang, "med") }]}>
          {t("playBestLine", lang, {
            w: windowWords(best, lang),
            n: Math.round(best.pm25_mid ?? 0),
          })}
        </Text>
      )}
      {worst && (
        <Text {...DYNAMIC_TYPE}
          style={[s.worstLine, { fontFamily: fam(lang, "reg") }]}>
          {t("playWorstLine", lang, {
            w: windowWords(worst, lang),
            n: Math.round(worst.pm25_mid ?? 0),
          })}
        </Text>
      )}
      {data.mean_pm25 != null && (
        <Text {...DYNAMIC_TYPE}
          style={[s.avgLine, NUM, { fontFamily: fam(lang, "reg") }]}>
          {t("exploreAvgLine", lang, { n: Math.round(data.mean_pm25) })}
        </Text>
      )}
      {data.decisions.map((d) => (
        <Text key={d.label} {...DYNAMIC_TYPE}
          style={[s.decision, { fontFamily: fam(lang, "reg") }]}>
          {d.line}
        </Text>
      ))}
      <View style={{ height: 14 }} />
    </ScrollView>
  );
}

const s = StyleSheet.create({
  sheet: { paddingHorizontal: 22 },
  list: { flexShrink: 1, flexGrow: 0 },
  verdict: { fontSize: 14.5, color: V2T.text, marginTop: 6, marginBottom: 12 },
  strip: {
    flexDirection: "row", alignItems: "flex-end",
    height: 96, marginTop: 4,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: V2T.ink10,
  },
  cell: {
    flex: 1, alignItems: "center", justifyContent: "flex-end",
    height: "100%",
  },
  bar: {
    width: "62%", borderTopLeftRadius: 3, borderTopRightRadius: 3,
    minHeight: 4,
  },
  ground: { height: 3, width: "100%", marginTop: 2, borderRadius: 1.5 },
  groundBest: { backgroundColor: V2T.accent },
  groundWorst: { backgroundColor: V2T.text4 },
  axisRow: {
    flexDirection: "row", justifyContent: "space-between",
    alignItems: "center", marginTop: 20,
  },
  axisTxt: { fontSize: 10.5, color: V2T.text3 },
  bestLine: { fontSize: 13.5, color: V2T.accentInk, marginTop: 12 },
  worstLine: { fontSize: 12.5, color: V2T.text2, marginTop: 4 },
  avgLine: { fontSize: 12, color: V2T.text3, marginTop: 8 },
  decision: { fontSize: 12.5, color: V2T.text2, marginTop: 8 },
});
