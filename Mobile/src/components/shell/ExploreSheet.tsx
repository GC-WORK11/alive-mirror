/** ExploreSheet — the 'stay & play' settle surface for the search
 *  flow's explore intents (hackathon features 2 & 3):
 *
 *    stays    — lodging rows near the anchor, each scored by the live-
 *               anchored next-24h forecast AT ITS OWN coordinates and
 *               ranked lightest-first; every row carries the honest
 *               'pm X · N µg lighter than your air' delta. A tap drops
 *               the stay on the air map (the map's own tap-read names
 *               the field there — same settle grammar as the map).
 *    playtime — the area's rolling next-24h air curve (same served
 *               hours as /v2/day, folded past midnight), the lightest
 *               contiguous window banded, the verdict line the server
 *               computed, and the heaviest run so 'kids out 6-9 am'
 *               is a plan, not a vibe.
 *
 *  Every number is the endpoint's; empty/sparse/thin reads are said,
 *  never filled. */
import React, { useEffect, useMemo, useRef, useState } from "react";
import { Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { V2T, bandColor, bandColorIdx, fam } from "../../theme";
import { bandIdxForName } from "../../api/outlook";
import { DYNAMIC_TYPE } from "../../a11y";
import { Icon } from "../../icons";
import { Sheet } from "../../ui";
import { localizeKind, t, type Lang } from "../../i18n/strings";
import { mark } from "../../perf";
import {
  fetchPlaytime, fetchStays,
  type ExploreAnchor, type ExploreMode,
  type PlaytimeData, type StaysData, type StayRow,
} from "../../api/explore";

type Props = {
  mode: ExploreMode;
  anchor: ExploreAnchor;
  lang: Lang;
  onModeChange: (m: ExploreMode) => void;
  onPin: (p: { lat: number; lon: number; name: string }) => void;
  onClose: () => void;
};

const dayWord = (off: number, lang: Lang) =>
  off <= 0 ? "" : off === 1 ? ` ${t("exploreTomorrow", lang)}`
                          : ` ${t("exploreInDays", lang, { n: off })}`;

export function ExploreSheet({ mode, anchor, lang, onModeChange, onPin, onClose }: Props) {
  const [stays, setStays] = useState<StaysData | null>(null);
  const [play, setPlay] = useState<PlaytimeData | null>(null);
  const [failed, setFailed] = useState<ExploreMode | null>(null);
  const seq = useRef(0);

  useEffect(() => {
    mark("explore.show");
    const my = ++seq.current;
    let dead = false;
    (async () => {
      if (mode === "stays") {
        const d = await fetchStays(anchor);
        if (dead || my !== seq.current) return;
        if (d) { setStays(d); setFailed((f) => (f === "stays" ? null : f)); }
        else setFailed("stays");
      } else {
        const d = await fetchPlaytime(anchor);
        if (dead || my !== seq.current) return;
        if (d) { setPlay(d); setFailed((f) => (f === "playtime" ? null : f)); }
        else setFailed("playtime");
      }
    })();
    return () => { dead = true; };
  }, [mode, anchor]);

  const anchorName = useMemo(() => {
    const n = (mode === "stays" ? stays?.near.name : play?.near.name) ??
      ("name" in anchor ? anchor.name : null);
    return n;
  }, [mode, stays, play, anchor]);
  const anchorLine = anchorName
    ? t("exploreAnchorNear", lang, { place: anchorName })
    : t("exploreAnchorNearYou", lang);

  const body = mode === "stays"
    ? <StaysBody data={stays} failed={failed === "stays"} lang={lang} onPin={onPin} />
    : <PlaytimeBody data={play} failed={failed === "playtime"} lang={lang} />;

  return (
    <Sheet detent="half" onClose={onClose} lang={lang} style={s.sheet}>
      <View style={s.head}>
        <View style={s.pinWell}>
          <Icon name={mode === "stays" ? "hotel" : "explore"} color={V2T.accent} size={15} />
        </View>
        <View style={{ flex: 1 }}>
          <Text {...DYNAMIC_TYPE} style={[s.title, { fontFamily: fam(lang, "semi") }]}
            numberOfLines={1}>
            {t(mode === "stays" ? "exploreStayTitle" : "explorePlayTitle", lang)}
          </Text>
          <Text {...DYNAMIC_TYPE} style={[s.sub, { fontFamily: fam(lang, "reg") }]}
            numberOfLines={1}>{anchorLine}</Text>
          {/* the sibling mode is one tap away — same anchor, other ask.
              Inside the head's text column: the sheet's top-right corner
              sits under the iOS status-bar battery cluster at this detent
              (taps there never arrive — found on sim), and a pill rendered
              as a free sibling above `body` loses its rect to the body
              ScrollView's hit zone. */}
          <Pressable
            onPress={() => onModeChange(mode === "stays" ? "playtime" : "stays")}
            accessibilityRole="button"
            accessibilityLabel={t(mode === "stays" ? "explorePlayTitle" : "exploreStayTitle", lang)}
            style={({ pressed }) => [s.modeBtn, pressed && { opacity: 0.55 }]}
            hitSlop={10}
          >
            <Text {...DYNAMIC_TYPE}
              style={[s.modeBtnTxt, { fontFamily: fam(lang, "med") }]}
              numberOfLines={1}>
              {t(mode === "stays" ? "explorePlayTitle" : "exploreStayTitle", lang)}
            </Text>
          </Pressable>
        </View>
      </View>
      {body}
    </Sheet>
  );
}

/* ------------------------------------------------------------------ */

function StaysBody({ data, failed, lang, onPin }: {
  data: StaysData | null; failed: boolean; lang: Lang;
  onPin: Props["onPin"];
}) {
  if (failed || (data && data.error))
    return <HonestLine lang={lang}
      text={data?.error ? t("exploreOutOfArea", lang)
                        : t("exploreNoStays", lang)} />;
  if (!data)
    return <HonestLine lang={lang} text={t("exploreReading", lang)} />;
  if (!data.stays.length)
    return <HonestLine lang={lang} text={t("exploreNoStays", lang)} />;

  const nowOnly = data.scored_h === 0;
  return (
    <ScrollView style={s.list} showsVerticalScrollIndicator={false}>
      {data.sparse && (
        <HonestChip lang={lang}
          text={data.nearest_station_km != null
            ? t("exploreThinRead", lang, { n: data.nearest_station_km })
            : t("exploreThinReadNoKm", lang)} />
      )}
      {nowOnly && (
        <HonestChip lang={lang} text={t("exploreNowOnly", lang)} />
      )}
      {data.stays.map((r) => (
        <StayRowEl key={r.id} row={r} lang={lang} onPin={onPin} />
      ))}
      <View style={{ height: 14 }} />
    </ScrollView>
  );
}

function StayRowEl({ row, lang, onPin }: {
  row: StayRow; lang: Lang; onPin: Props["onPin"];
}) {
  const idx = bandIdxForName(row.band);
  const dot = bandColorIdx(idx) ?? V2T.text4;
  const delta = row.cleaner_by_ug;
  const deltaTxt =
    delta == null ? null
      : Math.abs(delta) < 0.5 ? t("exploreSameAir", lang)
      : delta > 0 ? t("exploreLighter", lang, { n: Math.abs(delta) })
                  : t("exploreHeavier", lang, { n: Math.abs(delta) });
  const deltaCol =
    delta == null || Math.abs(delta) < 0.5 ? V2T.text3
      : delta > 0 ? V2T.accentInk : V2T.text2;
  return (
    <Pressable
      onPress={() => onPin({ lat: row.lat, lon: row.lon, name: row.name })}
      accessibilityRole="button"
      accessibilityLabel={row.name}
      style={({ pressed }) => [s.stayRow, pressed && { opacity: 0.55 }]}
    >
      <View style={[s.bandDot, { backgroundColor: dot }]} />
      <View style={{ flex: 1 }}>
        <Text {...DYNAMIC_TYPE} numberOfLines={1}
          style={[s.stayName, { fontFamily: fam(lang, "med") }]}>
          {row.name}
        </Text>
        <Text {...DYNAMIC_TYPE} numberOfLines={1}
          style={[s.staySub, { fontFamily: fam(lang, "reg") }]}>
          {`${localizeKind(row.kind, lang)} · ${row.dist_km} km` +
            (row.sparse
              ? (row.nearest_station_km != null
                ? ` · ${t("exploreThinRead", lang, { n: row.nearest_station_km })}`
                : ` · ${t("exploreThinReadNoKm", lang)}`)
              : "")}
        </Text>
      </View>
      <View style={s.stayRight}>
        <Text {...DYNAMIC_TYPE} numberOfLines={1}
          style={[s.stayPm, { fontFamily: fam(lang, "med") }]}>
          {row.scored_on === "unrated"
            ? t("exploreUnrated", lang)
            : `~${Math.round(row.window_mean_ug ?? row.pm25_now ?? 0)} µg`}
        </Text>
        {deltaTxt != null && (
          <Text {...DYNAMIC_TYPE} numberOfLines={1}
            style={[s.stayDelta, { color: deltaCol, fontFamily: fam(lang, "reg") }]}>
            {deltaTxt}
          </Text>
        )}
      </View>
    </Pressable>
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
  const bestHs = new Set<number>();
  if (data.best_window) {
    const end = data.best_window.end_h ?? data.hours[data.hours.length - 1].h;
    for (let h = data.best_window.start_h; h <= end; h++) bestHs.add(h);
  }
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

      <View style={s.curveWrap}>
        {data.hours.map((h) => {
          const frac = 0.12 + 0.88 * ((h.pm25_mid - min) / span);
          const inBest = bestHs.has(h.h);
          const col = bandColor(h.pm25_mid) ?? V2T.text4;
          return (
            <View key={h.h} style={s.barCell}>
              <View style={[s.barShadow, inBest && s.barBestHalo]} />
              <View
                style={[s.bar, {
                  height: Math.max(6, Math.round(56 * frac)),
                  backgroundColor: col,
                  opacity: inBest ? 1 : 0.72,
                }]}
              />
              {h.h === 0 && (
                <Text style={[s.nowMark, { fontFamily: fam(lang, "reg") }]}>
                  {t("exploreNowMarker", lang)}
                </Text>
              )}
              {inBest && h.h === best!.start_h && (
                <Text style={[s.bestMark, { fontFamily: fam(lang, "med") }]}
                  numberOfLines={1}>
                  {t("exploreBestChip", lang)}
                </Text>
              )}
            </View>
          );
        })}
      </View>
      <View style={s.axisRow}>
        <Text style={[s.axisTxt, { fontFamily: fam(lang, "reg") }]}>
          {data.hours[0].ist_label}
        </Text>
        {best && (
          <Text style={[s.axisTxt, { fontFamily: fam(lang, "med") }]}>
            {t("exploreWindowChip", lang, {
              start: best.start_label ?? "",
              end: best.end_label ?? "…",
              day: dayWord(best.start_day_offset, lang).trim() || "" })}
          </Text>
        )}
        <Text style={[s.axisTxt, { fontFamily: fam(lang, "reg") }]}>
          {data.hours[data.hours.length - 1].ist_label}
          {dayWord(data.hours[data.hours.length - 1].day_offset, lang)}
        </Text>
      </View>
      {data.mean_pm25 != null && (
        <Text {...DYNAMIC_TYPE}
          style={[s.avgLine, { fontFamily: fam(lang, "reg") }]}>
          {t("exploreAvgLine", lang, { n: Math.round(data.mean_pm25) })}
        </Text>
      )}
      {worst && (
        <Text {...DYNAMIC_TYPE}
          style={[s.worstLine, { fontFamily: fam(lang, "reg") }]}>
          {`${t("exploreWorstChip", lang)}: ` +
            t("exploreWindowChip", lang, {
              start: worst.start_label ?? "",
              end: worst.end_label ?? "…",
              day: dayWord(worst.start_day_offset, lang).trim() || "" }) +
            ` · ~${Math.round(worst.pm25_mid ?? 0)} µg/m³`}
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

function HonestLine({ text, lang }: { text: string; lang: Lang }) {
  return (
    <View style={s.honestWrap}>
      <Text {...DYNAMIC_TYPE}
        style={[s.honestTxt, { fontFamily: fam(lang, "reg") }]}>
        {text}
      </Text>
    </View>
  );
}

function HonestChip({ text, lang }: { text: string; lang: Lang }) {
  return (
    <View style={s.chip}>
      <Text {...DYNAMIC_TYPE}
        style={[s.chipTxt, { fontFamily: fam(lang, "reg") }]}>
        {text}
      </Text>
    </View>
  );
}

const s = StyleSheet.create({
  sheet: { paddingHorizontal: 22 },
  head: { flexDirection: "row", alignItems: "center", marginBottom: 6 },
  pinWell: {
    width: 30, height: 30, borderRadius: 15,
    backgroundColor: V2T.accentWash,
    alignItems: "center", justifyContent: "center",
    marginRight: 10,
  },
  title: { fontSize: 17, color: V2T.text, letterSpacing: -0.2 },
  sub: { fontSize: 12.5, color: V2T.text3, marginTop: 1 },
  modeBtn: {
    alignSelf: "flex-start",
    paddingHorizontal: 12, paddingVertical: 6,
    borderRadius: 999, borderWidth: StyleSheet.hairlineWidth,
    borderColor: V2T.ink10, marginTop: 6, marginBottom: 2,
  },
  modeBtnTxt: { fontSize: 12.5, color: V2T.accentInk },
  /* the sheet's maxHeight is the only bound — flex:1 would size this
     ScrollView off an undefined parent and collapse the body to 0
     (same reason compare uses grow:0/shrink:1) */
  list: { flexShrink: 1, flexGrow: 0 },
  honestWrap: { paddingVertical: 30, alignItems: "center" },
  honestTxt: { fontSize: 13.5, color: V2T.text3, textAlign: "center" },
  chip: {
    alignSelf: "flex-start", borderRadius: 999,
    backgroundColor: V2T.accentWash,
    paddingHorizontal: 10, paddingVertical: 4,
    marginTop: 4, marginBottom: 6,
  },
  chipTxt: { fontSize: 11.5, color: V2T.accentInk },
  stayRow: {
    flexDirection: "row", alignItems: "center",
    paddingVertical: 11,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: V2T.ink10,
  },
  bandDot: { width: 7, height: 7, borderRadius: 4, marginRight: 10 },
  stayName: { fontSize: 14.5, color: V2T.text },
  staySub: { fontSize: 11.5, color: V2T.text3, marginTop: 1 },
  stayRight: { alignItems: "flex-end", marginLeft: 10 },
  stayPm: { fontSize: 13.5, color: V2T.text },
  stayDelta: { fontSize: 11, marginTop: 1 },
  verdict: { fontSize: 14.5, color: V2T.text, marginTop: 4, marginBottom: 10 },
  curveWrap: {
    flexDirection: "row", alignItems: "flex-end",
    height: 78, marginTop: 4,
  },
  barCell: { flex: 1, alignItems: "center", justifyContent: "flex-end" },
  barShadow: {
    position: "absolute", bottom: -2, height: 4,
    width: "80%", borderRadius: 2, backgroundColor: "transparent",
  },
  barBestHalo: { backgroundColor: V2T.accent, bottom: -4 },
  bar: { width: "58%", borderRadius: 3, minHeight: 4 },
  nowMark: { fontSize: 8.5, color: V2T.text3, marginTop: 2 },
  bestMark: {
    position: "absolute", top: -14, fontSize: 8.5,
    color: V2T.accentInk,
  },
  axisRow: {
    flexDirection: "row", justifyContent: "space-between",
    alignItems: "center", marginTop: 6,
  },
  axisTxt: { fontSize: 10.5, color: V2T.text3 },
  avgLine: { fontSize: 12, color: V2T.text3, marginTop: 10 },
  worstLine: { fontSize: 12, color: V2T.text2, marginTop: 4 },
  decision: { fontSize: 12.5, color: V2T.text2, marginTop: 8 },
});
