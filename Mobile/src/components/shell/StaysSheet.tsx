/** StaysSheet — 'where to stay': the dedicated stays surface (the
 *  owner's split — stays and playtime are each a real component now,
 *  not two plain modes of one half-detent sheet).
 *
 *  Warm card-less rows on hairlines: a band square, the stay's name,
 *  kind + walking distance, and its air story — the next-24 h forecast
 *  mean at THE STAY'S OWN coordinates (never the anchor's air
 *  relabelled) plus the honest 'N µg lighter' delta against the
 *  anchor's live read. A tap drops the stay on the air map — the map's
 *  own tap-read names the field there.
 *
 *  Every number is /v2/stays'; thin reads and forecast-down rows are
 *  said, never filled. */
import React, { useEffect, useMemo, useRef, useState } from "react";
import { Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { NUM, V2T, bandColorIdx, fam } from "../../theme";
import { bandIdxForName } from "../../api/outlook";
import { DYNAMIC_TYPE } from "../../a11y";
import { Sheet } from "../../ui";
import { localizeKind, t, type Lang } from "../../i18n/strings";
import { mark } from "../../perf";
import {
  fetchStays,
  type ExploreAnchor, type ExploreMode,
  type StaysData, type StayRow,
} from "../../api/explore";
import { ExploreHead, HonestChip, HonestLine } from "./exploreShared";

type Props = {
  anchor: ExploreAnchor;
  lang: Lang;
  onModeChange: (m: ExploreMode) => void;
  onPin: (p: { lat: number; lon: number; name: string }) => void;
  onClose: () => void;
};

export function StaysSheet({ anchor, lang, onModeChange, onPin, onClose }: Props) {
  const [data, setData] = useState<StaysData | null>(null);
  const [failed, setFailed] = useState(false);
  const seq = useRef(0);

  useEffect(() => {
    mark("explore.stays.show");
    const my = ++seq.current;
    let dead = false;
    (async () => {
      const d = await fetchStays(anchor);
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

  const nowOnly = !!data && data.scored_h === 0;
  return (
    <Sheet detent="half" onClose={onClose} lang={lang} style={s.sheet}>
      <ExploreHead
        lang={lang}
        glyph="hotel"
        title={t("staysTitle", lang)}
        sub={anchorLine}
        /* the basis is said once up top, not restated on every row;
           with a dead horizon every number is a live read and the
           chip below names that instead */
        disclosure={nowOnly ? undefined : t("staysDisclosure", lang)}
        siblingLabel={t("explorePlayTitle", lang)}
        onSibling={() => onModeChange("playtime")}
      />
      <StaysBody data={data} failed={failed} nowOnly={nowOnly}
        lang={lang} onPin={onPin} />
    </Sheet>
  );
}

/* ------------------------------------------------------------------ */

function StaysBody({ data, failed, nowOnly, lang, onPin }: {
  data: StaysData | null; failed: boolean; nowOnly: boolean; lang: Lang;
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
      <Text {...DYNAMIC_TYPE}
        style={[s.hint, { fontFamily: fam(lang, "reg") }]}>
        {t("staysPinHint", lang)}
      </Text>
      <View style={{ height: 10 }} />
    </ScrollView>
  );
}

/** straight-line km → the walk pace convention (5 km/h ≈ 12 min/km).
 *  Under ~2.5 km the stay is on foot and the row says the minutes;
 *  past that nobody's walking and the row says the distance. */
function walkLabel(distKm: number, lang: Lang): string {
  if (distKm < 2.5) {
    const mins = Math.max(2, Math.round(distKm * 12));
    return t("staysWalkMin", lang, { n: mins });
  }
  return t("staysKmAway", lang, { n: distKm });
}

function StayRowEl({ row, lang, onPin }: {
  row: StayRow; lang: Lang; onPin: Props["onPin"];
}) {
  const idx = bandIdxForName(row.band);
  const sq = bandColorIdx(idx) ?? V2T.text4;
  const delta = row.cleaner_by_ug;
  const deltaTxt =
    delta == null ? null
      : Math.abs(delta) < 0.5 ? t("exploreSameAir", lang)
      : delta > 0 ? t("exploreLighter", lang, { n: Math.abs(delta) })
                  : t("exploreHeavier", lang, { n: Math.abs(delta) });
  const deltaCol =
    delta == null || Math.abs(delta) < 0.5 ? V2T.text3
      : delta > 0 ? V2T.accentInk : V2T.text2;
  /* a row scored on the live read alone (forecast down mid-flight)
     flags its basis inline — 'now · 2 µg lighter' */
  const basis = row.scored_on === "now"
    ? `${t("staysNowBasis", lang)} · ` : "";
  const distTxt = `${localizeKind(row.kind, lang)} · ${walkLabel(row.dist_km, lang)}` +
    (row.sparse
      ? (row.nearest_station_km != null
        ? ` · ${t("exploreThinRead", lang, { n: row.nearest_station_km })}`
        : ` · ${t("exploreThinReadNoKm", lang)}`)
      : "");
  return (
    <Pressable
      onPress={() => onPin({ lat: row.lat, lon: row.lon, name: row.name })}
      accessibilityRole="button"
      accessibilityLabel={`${row.name}, ${distTxt}`}
      style={({ pressed }) => [s.stayRow, pressed && { opacity: 0.55 }]}
    >
      <View style={[s.bandSq, { backgroundColor: sq }]} />
      <View style={{ flex: 1 }}>
        <Text {...DYNAMIC_TYPE} numberOfLines={1}
          style={[s.stayName, { fontFamily: fam(lang, "med") }]}>
          {row.name}
        </Text>
        <Text {...DYNAMIC_TYPE} numberOfLines={1}
          style={[s.staySub, { fontFamily: fam(lang, "reg") }]}>
          {distTxt}
        </Text>
      </View>
      <View style={s.stayRight}>
        <Text {...DYNAMIC_TYPE} numberOfLines={1}
          style={[s.stayPm, NUM, { fontFamily: fam(lang, "med") }]}>
          {row.scored_on === "unrated"
            ? t("exploreUnrated", lang)
            : `~${Math.round(row.window_mean_ug ?? row.pm25_now ?? 0)} µg`}
        </Text>
        {deltaTxt != null && (
          <Text {...DYNAMIC_TYPE} numberOfLines={1}
            style={[s.stayDelta, { color: deltaCol, fontFamily: fam(lang, "reg") }]}>
            {basis}{deltaTxt}
          </Text>
        )}
      </View>
    </Pressable>
  );
}

const s = StyleSheet.create({
  sheet: { paddingHorizontal: 22 },
  /* the sheet's maxHeight is the only bound — flex:1 would size this
     ScrollView off an undefined parent and collapse the body to 0
     (same reason compare uses grow:0/shrink:1) */
  list: { flexShrink: 1, flexGrow: 0 },
  stayRow: {
    flexDirection: "row", alignItems: "center",
    paddingVertical: 12,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: V2T.ink10,
  },
  bandSq: { width: 8, height: 8, borderRadius: 2, marginRight: 11 },
  stayName: { fontSize: 14.5, color: V2T.text },
  staySub: { fontSize: 11.5, color: V2T.text3, marginTop: 2 },
  stayRight: { alignItems: "flex-end", marginLeft: 10 },
  stayPm: { fontSize: 14, color: V2T.text },
  stayDelta: { fontSize: 11, marginTop: 2 },
  hint: {
    fontSize: 11.5, color: V2T.text4, textAlign: "center",
    marginTop: 12,
  },
});
