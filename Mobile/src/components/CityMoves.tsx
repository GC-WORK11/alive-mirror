// CityMoves — "how Delhi moves" card (docs/plan/07 §1 sibling of
// DelhiToday). Renders GET /v2/city/moves — REAL donated-trip aggregates
// only: mode share, the publishable-corridor count, and per-trip
// dose/emission percentile bands. Every server row already cleared
// k>=3; this component adds no data of its own.
//
// Contract: <CityMoves data lang /> — presentational; the parent fetches
// via fetchCityMoves() and owns retry/offline labelling. `data` null =
// still loading (shows a quiet waiting line, never a fake empty state);
// `insufficient_data` = the honest "not enough shared trips yet" card —
// real counts still show, no distribution is drawn from < min_k trips.
//
// i18n keys landed (strings.ts): movesTitle, movesWindowDays,
// movesNotEnough, movesSuppressed, movesCorridorN, movesTypical,
// movesModeOther.

import React from "react";
import { StyleSheet, Text, View } from "react-native";
import {
  fam,
  famMono,
  famMonoText,
  NUM,
  V2Radius,
  V2T,
  V2Type,
} from "../theme";
import { t, type Lang, type StringKey } from "../i18n/strings";
import { Icon, type Glyph } from "../icons";
import type {
  CityMovesBand,
  CityMovesModeRow,
  CityMovesPayload,
} from "../api/city";
import { DYNAMIC_TYPE } from "../a11y";

const fmtUg = (v: number): string =>
  v < 10 ? v.toFixed(1) : `${Math.round(v)}`;
const fmtKg = (v: number): string => (v < 1 ? v.toFixed(2) : v.toFixed(1));
const fmtPct = (share: number): string => `${Math.round(share * 100)}%`;

/** Colour carries the exhaust meaning (doc 03): shared + human modes
 *  stay grey/blue — lightness is the absence of colour — and the
 *  motorized stack climbs the breath ramp bike → auto → car. */
const MODE_META: Record<
  string,
  { icon: Glyph; label?: StringKey; color: string }
> = {
  metro: { icon: "metro", label: "vehicle_metro", color: V2T.accent },
  bus: { icon: "bus", label: "vehicle_bus", color: V2T.accent },
  walk: { icon: "walk", label: "vehicle_walk", color: V2T.text2 },
  cycle: { icon: "cycle", label: "vehicle_cycle", color: V2T.text3 },
  bike: { icon: "bike", label: "vehicle_bike", color: V2T.breath1 },
  auto: { icon: "auto", label: "vehicle_auto", color: V2T.breath2 },
  erick: { icon: "erick", label: "vehicle_auto", color: V2T.breath2 },
  cab: { icon: "cab", label: "vehicleCab", color: V2T.breath3 },
  car: { icon: "car", label: "vehicle_car", color: V2T.breath3 },
  car_open: { icon: "car", label: "vehicle_car", color: V2T.breath3 },
  // the server's pooled bucket — every member stayed under k, the pool
  // is what makes them showable; no per-mode name may surface here
  other: { icon: "flag", color: V2T.out2 },
};
const META_FALLBACK = { icon: "flag" as Glyph, color: V2T.out2 };

function modeLabel(m: string, lang: Lang): string {
  const meta = MODE_META[m];
  if (meta?.label) return t(meta.label, lang);
  // The pooled under-k bucket gets a real label in both languages — the
  // wire token "other" is data, not copy, and must not leak into the UI.
  if (m === "other") return t("movesModeOther", lang);
  // unrecognized ids render the server token itself — it is data, not
  // copy (same rule as a corridor's gazetteer name).
  return m;
}

function ModeRow({ row, lang }: { row: CityMovesModeRow; lang: Lang }) {
  const meta = MODE_META[row.mode] ?? META_FALLBACK;
  return (
    <View style={ss.mRow}>
      <Icon name={meta.icon} color={meta.color} size={18} />
      <Text {...DYNAMIC_TYPE}
        style={[ss.mName, { fontFamily: fam(lang, "reg") }]}
        numberOfLines={1}
      >
        {modeLabel(row.mode, lang)}
      </Text>
      <Text {...DYNAMIC_TYPE} style={[ss.mPct, NUM, { fontFamily: famMono(lang, "med") }]}>
        {fmtPct(row.share)}
      </Text>
      <Text {...DYNAMIC_TYPE} style={[ss.mTrips, NUM, { fontFamily: famMonoText(lang, "reg") }]}>
        {t("cityTrips", lang, { n: row.trips })}
      </Text>
    </View>
  );
}

/** label + "≈{p50} {unit}" over the muted "{p25}–{p75}" band — the
 *  honest middle half, never a fake point. */
function BandRow({
  label,
  band,
  unit,
  fmt,
  lang,
}: {
  label: string;
  band: CityMovesBand | null | undefined;
  unit: string;
  fmt: (v: number) => string;
  lang: Lang;
}) {
  if (!band) return null;
  return (
    <View style={ss.bRow}>
      <Text {...DYNAMIC_TYPE} style={[ss.bLabel, { fontFamily: fam(lang, "reg") }]}>
        {label}
      </Text>
      <View style={ss.bVals}>
        <Text {...DYNAMIC_TYPE} style={[ss.bMid, NUM, { fontFamily: famMonoText(lang, "med") }]}>
          {t("movesTypical", lang)} ≈{fmt(band.p50)} {unit}
        </Text>
        <Text {...DYNAMIC_TYPE} style={[ss.bBand, NUM, { fontFamily: famMono(lang, "reg") }]}>
          {fmt(band.p25)}–{fmt(band.p75)}
        </Text>
      </View>
    </View>
  );
}

export function CityMoves({
  data,
  lang = "en",
}: {
  data: CityMovesPayload | null;
  lang?: Lang;
}) {
  /* still loading / fetch failed — a quiet line, not a fake empty */
  if (data === null) {
    return (
      <View style={ss.card}>
        <Text {...DYNAMIC_TYPE} style={[ss.note, { fontFamily: fam(lang, "reg") }]}>
          {t("cityLoading", lang)}
        </Text>
      </View>
    );
  }

  const minK = data.min_k ?? 3;
  const windowDays = data.window?.days ?? 7;
  const corridors = data.corridors;
  const perTrip = data.per_trip;
  const suppressed = data.mode_share_suppressed_trips ?? 0;

  return (
    <View style={ss.card}>
      <Text {...DYNAMIC_TYPE} style={[ss.title, { fontFamily: fam(lang, "semi") }]}>
        {t("movesTitle", lang)}
      </Text>
      {/* context: window + real trip count */}
      <Text {...DYNAMIC_TYPE} style={[ss.sub, NUM, { fontFamily: famMonoText(lang, "reg") }]}>
        {windowDays === 7 ? t("ledgerLast7", lang) : t("movesWindowDays", lang, { d: windowDays })}
        {"  ·  "}
        {t("cityTrips", lang, { n: data.n_trips })}
      </Text>

      {data.insufficient_data ? (
        /* honest empty state — counts above stay real */
        <Text {...DYNAMIC_TYPE} style={[ss.note, { fontFamily: fam(lang, "reg") }]}>
          {t("movesNotEnough", lang, { k: minK, d: windowDays })}
        </Text>
      ) : (
        <>
          {/* mode share — proportional bar, segments sized by trips */}
          {data.mode_share.length > 0 ? (
            <View
              style={ss.bar}
              accessibilityRole="summary"
              accessibilityLabel={data.mode_share
                .map(
                  (r) =>
                    `${modeLabel(r.mode, lang)} ${fmtPct(r.share)}`,
                )
                .join(", ")}
            >
              {data.mode_share.map((r) => (
                <View
                  key={r.mode}
                  style={[
                    ss.seg,
                    {
                      flexGrow: r.trips,
                      backgroundColor:
                        (MODE_META[r.mode] ?? META_FALLBACK).color,
                    },
                  ]}
                />
              ))}
            </View>
          ) : null}
          {data.mode_share.map((r) => (
            <ModeRow key={r.mode} row={r} lang={lang} />
          ))}
          {suppressed > 0 ? (
            /* a count, not a row — the under-k footnote stays stated */
            <Text {...DYNAMIC_TYPE}
              style={[ss.note, NUM, { fontFamily: famMonoText(lang, "reg") }]}
            >
              {t("movesSuppressed", lang, { n: suppressed, k: minK })}
            </Text>
          ) : null}

          {/* measured streets — "{n} streets measured in {h} h" + the
              streets' own dose band */}
          {corridors ? (
            <View style={ss.bRow}>
              <Text {...DYNAMIC_TYPE}
                style={[ss.bLabel, { fontFamily: fam(lang, "reg") }]}
              >
                {t("movesCorridorN", lang, {
                  n: corridors.active ?? 0,
                  h: corridors.window_h ?? 72,
                })}
              </Text>
              <View style={ss.bVals}>
                {corridors.avg_dose_ug ? (
                  <Text {...DYNAMIC_TYPE}
                    style={[
                      ss.bBand,
                      NUM,
                      { fontFamily: famMonoText(lang, "reg") },
                    ]}
                  >
                    {t("tripsDoseBand", lang, {
                      lo: fmtUg(corridors.avg_dose_ug.p25),
                      hi: fmtUg(corridors.avg_dose_ug.p75),
                    })}
                  </Text>
                ) : null}
              </View>
            </View>
          ) : null}

          {/* per-trip bands — p50 over the muted p25–p75 middle half */}
          {perTrip ? (
            <>
              <BandRow
                label={t("compare_smokeIn", lang)}
                band={perTrip.dose_ug}
                unit="µg"
                fmt={fmtUg}
                lang={lang}
              />
              <BandRow
                label={t("compare_smokeOut", lang)}
                band={perTrip.co2_kg}
                unit="kg"
                fmt={fmtKg}
                lang={lang}
              />
              {perTrip.pm25_g ? (
                /* "incl. {lo}–{hi} g of fine particles" — reads as the
                   whole line, so no separate label */
                <Text {...DYNAMIC_TYPE}
                  style={[
                    ss.note,
                    NUM,
                    { fontFamily: famMonoText(lang, "reg") },
                  ]}
                >
                  {(() => {
                    /* same collapse rule as the receipt: p25===p75 at display
                       precision must never print "0.2–0.2" */
                    const lo = fmtUg(perTrip.pm25_g.p25), hi = fmtUg(perTrip.pm25_g.p75);
                    return t(lo === hi ? "receipt_pmBandOne" : "receipt_pmBand", lang,
                      lo === hi ? { x: hi } : { lo, hi });
                  })()}
                </Text>
              ) : null}
            </>
          ) : null}

          {/* the rule is part of the data — k>=3 / 72 h, stated */}
          <Text {...DYNAMIC_TYPE} style={[ss.foot, { fontFamily: fam(lang, "reg") }]}>
            {t("cityBasisPrivacy", lang, {
              k: minK,
              h: corridors?.window_h ?? 72,
            })}
          </Text>
        </>
      )}
    </View>
  );
}

export default CityMoves;

const ss = StyleSheet.create({
  card: {
    marginHorizontal: 14,
    marginTop: 14,
    padding: 14,
    borderRadius: V2Radius.row,
    backgroundColor: V2T.glassSoft,
    borderWidth: 1,
    borderColor: V2T.glassLine,
  },
  title: { color: V2T.text, fontSize: V2Type.body },
  sub: { color: V2T.text3, fontSize: V2Type.label, marginTop: 2 },
  note: {
    color: V2T.text3,
    fontSize: V2Type.label,
    marginTop: 10,
    lineHeight: 19,
  },
  foot: {
    color: V2T.text3,
    fontSize: V2Type.label,
    marginTop: 12,
    lineHeight: 18,
  },

  /* proportional mode-share bar */
  bar: {
    flexDirection: "row",
    height: 8,
    borderRadius: 4,
    overflow: "hidden",
    marginTop: 12,
    gap: 2,
    backgroundColor: "rgba(20,24,31,0.08)",
  },
  seg: { minWidth: 3 },

  /* legend rows */
  mRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
    minHeight: 30,
    marginTop: 6,
  },
  mName: { color: V2T.text2, fontSize: V2Type.secondary, flex: 1 },
  mPct: { color: V2T.text, fontSize: V2Type.secondary },
  mTrips: { color: V2T.text3, fontSize: V2Type.label, width: 64, textAlign: "right" },

  /* stat rows — label left, p50 + muted p25–p75 right */
  bRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginTop: 12,
    gap: 12,
  },
  bLabel: { color: V2T.text3, fontSize: V2Type.secondary, flex: 1 },
  bVals: { alignItems: "flex-end" },
  bMid: { color: V2T.text, fontSize: V2Type.secondary },
  bBand: { color: V2T.text3, fontSize: V2Type.label, marginTop: 1 },
});
