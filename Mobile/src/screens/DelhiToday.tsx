// "Delhi today" — the consumer city view (docs/plan/07 §1, sidebar §5).
// One scrolling page, light, editorial: the day's breath hero number in
// consumer words (µg inhaled by default; the cigarette figure only renders
// when the user opts in — settings.show_cig), the streets
// travellers actually crossed (k>=3 aggregates only, never trajectories),
// what all ALive travellers did today, and a "why this is an estimate"
// footer where the technical basis lives. Mount contract mirrors
// SearchScreen: <DelhiToday visible onClose lang showCig /> — the sheet
// mounts only while visible, so every open is a fresh fetch.

import React, { useEffect, useState } from "react";
import {
  Animated,
  BackHandler,
  LayoutAnimation,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { StatusBar } from "expo-status-bar";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import Svg, { Defs, LinearGradient, Path, Rect, Stop } from "react-native-svg";
import {
  bandColor,
  bandIdx,
  bandInkIdx,
  bandWashDeepIdx,
  cigOf,
  doseColor,
  fam,
  famMono,
  famMonoText,
  famSerif,
  NUM,
  V2Elev,
  V2Radius,
  V2T,
  V2Type,
} from "../theme";
import { approx, doseUgRound, feltKeyForBand, t, type Lang, type StringKey } from "../i18n/strings";
import { BandScale } from "../components/BandScale";
import { Icon, type Glyph } from "../icons";
import {
  fetchCity,
  fetchCityMoves, type CityMovesPayload,
  type CityCorridor,
  type CityPayload,
} from "../api/city";
import { CityMoves } from "../components/CityMoves";
import { causeNote, type CauseNoteFields } from "../store/events-core";
import { loadTrips } from "../store/ledger";
import { DYNAMIC_TYPE, useReduceMotion } from "../a11y";
import { tick } from "../haptics";
import { bump, jank } from "../perf";

const fmtCig = (v: number): string => (v < 1 ? v.toFixed(2) : v.toFixed(1));
const fmtKm = (km: number): string =>
  km < 10 ? km.toFixed(1) : `${Math.round(km)}`;
const fmtKg = (kg: number): string => (kg < 1 ? kg.toFixed(2) : kg.toFixed(1));

/* OSM gazetteer names arrive inconsistently cased ("hanuman lane" beside
   "Fire Brigade Lane") — title-case only names that carry no uppercase at
   all, so real casing (NH-8, AIIMS Flyover) is never touched. */
const streetName = (name: string): string =>
  /[A-Z]/.test(name)
    ? name
    : name.replace(/\b\w/g, (ch) => ch.toUpperCase());

const latestDay = (data: CityPayload) => {
  const days = data.trips?.days;
  if (!days) return null;
  const key = Object.keys(days).sort().pop(); // ISO keys sort chronologically
  return key ? days[key] : null;
};

/** True only when the payload says plainly there are no live stations —
 * an absent block never reads as "offline". */
const stationsOffline = (data: CityPayload): boolean => {
  const st = data.provenance?.stations;
  if (st) return st.live === false;
  const s = data.sources?.stations;
  return s ? s.up === false : false;
};

function BackGlyph({ color }: { color: string }) {
  return (
    <Svg width={22} height={22} viewBox="0 0 24 24">
      <Path
        d="M14.5 5.5 8 12l6.5 6.5"
        stroke={color}
        strokeWidth={2}
        fill="none"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </Svg>
  );
}

function Chip({
  icon,
  label,
  lang,
}: {
  icon: Glyph;
  label: string;
  lang: Lang;
}) {
  return (
    <View style={ss.chip}>
      <Icon name={icon} color={V2T.text3} size={14} />
      <Text {...DYNAMIC_TYPE} style={[ss.chipText, { fontFamily: fam(lang, "reg") }]}>
        {label}
      </Text>
    </View>
  );
}

function CorridorRow({ c, first, lang }: { c: CityCorridor; first: boolean; lang: Lang }) {
  const heavy = c.relative === "heavier";
  return (
    <View style={[ss.cRow, !first && ss.speciesSep]}>
      <View style={ss.cGlyph}>
        <Icon name="pin" color={V2T.text2} size={18} />
      </View>
      <View style={ss.cText}>
        <Text {...DYNAMIC_TYPE}
          style={[ss.cName, { fontFamily: fam(lang, "med") }]}
          numberOfLines={1}
        >
          {c.name ? streetName(c.name) : t("cityUnnamed", lang)}
        </Text>
        <Text {...DYNAMIC_TYPE} style={[ss.cSub, NUM, { fontFamily: famMonoText(lang, "reg") }]}>
          {t("cityTrips", lang, { n: c.trips, tripNoun: t(c.trips === 1 ? "tripNounOne" : "tripNounMany", lang) })}
        </Text>
      </View>
      {/* heavier carries breath-ramp colour; lighter stays grey —
          lightness is the absence of colour (doc 03) */}
      <Text {...DYNAMIC_TYPE}
        style={[
          ss.cRel,
          {
            fontFamily: fam(lang, "med"),
            color: heavy ? V2T.breath2 : V2T.text2,
          },
        ]}
      >
        {t(heavy ? "cityHeavier" : "cityLighter", lang)}
      </Text>
    </View>
  );
}

function WhyLine({ text, lang }: { text: string; lang: Lang }) {
  return (
    <Text {...DYNAMIC_TYPE} style={[ss.whyLine, { fontFamily: fam(lang, "reg") }]}>{text}</Text>
  );
}

/* The "why tonight" hero — server composes it in English
   (v2/why.py:_line). en keeps the wire line; hi rebuilds the same
   grammar from drivers[].kind (+ trend direction) and wind.from_deg,
   so wire English never reaches the hi UI. */
const WHY_CARRY: [number, StringKey][] = [
  [337.5, "whyDir_N"], [292.5, "whyDir_NW"], [247.5, "whyDir_W"],
  [202.5, "whyDir_SW"], [157.5, "whyDir_S"], [112.5, "whyDir_SE"],
  [67.5, "whyDir_E"], [22.5, "whyDir_NE"],
];
const whyCompass = (deg: number | null | undefined): StringKey => {
  if (deg == null) return "whyDir_NW"; // server's fallback expands NW
  const d = ((deg % 360) + 360) % 360;
  for (const [top, k] of WHY_CARRY) if (d >= top) return k;
  return "whyDir_N";
};
const whyBitKey = (d: { kind: string; direction?: string }): StringKey | null => {
  if (d.kind === "trend")
    return d.direction === "falling" ? "whyBit_trendFalling" : "whyBit_trendRising";
  if (d.kind === "stubble_smoke") return "whyBit_stubble";
  if (d.kind === "stagnation") return "whyBit_stagnation";
  return null; // unknown kinds pass through raw, as the server does
};
function whyLine(
  why: NonNullable<CityPayload["why"]>,
  wind: CityPayload["wind"],
  lang: Lang,
): string {
  if (lang === "en" || !why.line) return why.line ?? "";
  const drivers = why.drivers ?? [];
  if (!drivers.length) return t("whyNoDriver", lang);
  const dir = t(whyCompass(wind?.from_deg), lang);
  const parts = drivers.slice(0, 2).map((d) => {
    const k = whyBitKey(d);
    return k ? (k === "whyBit_stubble" ? t(k, lang, { dir }) : t(k, lang)) : d.kind;
  });
  return parts.join(" + ");
}

/* The cause_note — the parali/news line under the hero. BOTH languages
   rebuild from the structured fields through causeNote: the wire's own
   grammar carries engineering units (m²/s, "city mean", decimal spans)
   that the plain-words rebuild exists to replace. `cause_note` stays as
   the fallback for serves that don't ship fields. */
function noteLine(why: NonNullable<CityPayload["why"]>, lang: Lang): string {
  const f = why.cause_note_fields;
  if (f) return causeNote(f as CauseNoteFields, lang);
  return why.cause_note ?? "";
}

/* ---------- sheet (mounted only while visible → fresh state each open) --- */

function DelhiSheetInner({ onClose, lang, showCig }: { onClose: () => void; lang: Lang; showCig: boolean }) {
  bump("scr.DelhiSheet");
  const [data, setData] = useState<CityPayload | null>(null);
  const [moves, setMoves] = useState<CityMovesPayload | null>(null);
  const [failed, setFailed] = useState(false);
  /* trips on THIS phone — null while the ledger read is still out.
     The traveller aggregates below are counted from trips OTHER
     phones shared; on a fresh install they read as the app's record
     of your own day ("it says I travelled" — owner, Oct 7). Until
     this ledger holds one real trip the honest thing is the empty
     state, and while it's still being read nothing renders — the
     aggregate must never flash for a beat and vanish. */
  const [own, setOwn] = useState<number | null>(null);
  const [whyOpen, setWhyOpen] = useState(false);
  const [nonce, setNonce] = useState(0);
  const insets = useSafeAreaInsets();
  const reduceMotion = useReduceMotion();
  const toggleWhy = () => {
    tick();
    /* the basis block mounts/unmounts — ease it like the settings
       expanders (native path, off under reduce-motion) */
    if (!reduceMotion) LayoutAnimation.configureNext(LayoutAnimation.Presets.easeInEaseOut);
    setWhyOpen((o) => !o);
  };

  /* fetch on mount / retry — aborted on close and between retries;
     moves is best-effort: a failure just leaves the card absent */
  useEffect(() => {
    const ctrl = new AbortController();
    fetchCity(ctrl.signal)
      .then(setData)
      .catch((err: unknown) => {
        if (err instanceof Error && err.name === "AbortError") return;
        setFailed(true);
      });
    fetchCityMoves(ctrl.signal).then(setMoves).catch(() => {});
    loadTrips()
      .then((ts) => { if (!ctrl.signal.aborted) setOwn(ts.length); })
      .catch(() => { if (!ctrl.signal.aborted) setOwn(0); });
    return () => ctrl.abort();
  }, [nonce]);

  const cig = data?.breath?.cigarettes ?? null;
  /* the same hero figure in µg — the surface unit while show_cig is off */
  const inhaled = data?.breath?.day_inhaled_ug ?? null;
  const pm = data?.breath?.pm25_ugm3 ?? null;
  const ageMin = data?.freshness?.age_min ?? null;
  const stale = data?.freshness?.label === "stale";
  const offline = data ? stationsOffline(data) : false;
  const corridors = data?.corridors ?? [];
  const day = data ? latestDay(data) : null;
  const st = data?.provenance?.stations;
  const tr = data?.provenance?.trips;

  return (
    <View style={[ss.root, { marginTop: insets.top + 8 }]}>
      {/* top bar — back + title */}
      <View style={ss.bar}>
        <Pressable
          onPress={() => { tick(); onClose(); }}
          hitSlop={10}
          accessibilityRole="button"
          accessibilityLabel={t("a11yBack", lang)}
          style={({ pressed }) => [ss.barBtn, pressed && { opacity: 0.55 }]}
        >
          <BackGlyph color={V2T.text2} />
        </Pressable>
        <Text {...DYNAMIC_TYPE} style={[ss.title, { fontFamily: famSerif(lang, "semi") }]}>
          {t("delhiTitle", lang)}
        </Text>
      </View>

      <ScrollView style={ss.flex} contentContainerStyle={[ss.content, { paddingBottom: insets.bottom + 24 }]}>
        {failed ? (
          <View style={ss.center}>
            <Text {...DYNAMIC_TYPE} style={[ss.waiting, { fontFamily: fam(lang, "reg") }]}>
              {t("offline", lang)}
            </Text>
            <Pressable
              onPress={() => {
                tick();
                setFailed(false);
                setData(null);
                setNonce((n) => n + 1);
              }}
              style={({ pressed }) => [
                ss.retryBtn,
                pressed && { backgroundColor: "rgba(255,255,255,0.55)" },
              ]}
              accessibilityRole="button"
              accessibilityLabel={t("cityRetry", lang)}
            >
              <Text {...DYNAMIC_TYPE}
                style={[ss.retryText, { fontFamily: fam(lang, "med") }]}
              >
                {t("cityRetry", lang)}
              </Text>
            </Pressable>
          </View>
        ) : data === null ? (
          <Text {...DYNAMIC_TYPE} style={[ss.waiting, { fontFamily: fam(lang, "reg") }]}>
            {t("cityLoading", lang)}
          </Text>
        ) : (
          <>
            {/* hero — one number: a day of Delhi air in µg. With showCig
                on the cigarette equivalence sits as a secondary line
                under the µg — never the hero (owner mandate). */}
            {data.breath && pm && inhaled ? (
              /* the hero is a window into the day's sky (docs/20):
                 the band rendered as graded light, not a flat card */
              <View style={ss.hero}>
                <View style={StyleSheet.absoluteFill} pointerEvents="none">
                  <Svg width="100%" height="100%">
                    <Defs>
                      <LinearGradient id="citySky" x1="0" y1="0" x2="0" y2="1">
                        <Stop offset="0" stopColor={bandWashDeepIdx(bandIdx(pm.mid) ?? 0)} />
                        <Stop offset="1" stopColor={V2T.bg} />
                      </LinearGradient>
                    </Defs>
                    <Rect x="0" y="0" width="100%" height="100%" fill="url(#citySky)" />
                  </Svg>
                </View>
                <Text {...DYNAMIC_TYPE}
                  style={[ss.heroLead, { fontFamily: fam(lang, "med") }]}
                >
                  {t("cityHeroLead", lang, { w: t(feltKeyForBand(bandIdx(pm.mid)), lang) })}
                </Text>
                <View style={ss.heroRow}>
                  <Text {...DYNAMIC_TYPE}
                    style={[
                      ss.heroNum,
                      NUM,
                      {
                        fontFamily: famSerif(lang, "light"),
                        color: bandInkIdx(bandIdx(pm.mid) ?? 0) ?? doseColor(pm.mid),
                      },
                    ]}
                  >
                    {doseUgRound(inhaled.mid)}
                  </Text>
                  <Text {...DYNAMIC_TYPE}
                    style={[ss.heroUnit, { fontFamily: fam(lang, "med") }]}
                  >
                    {t("unitUg", lang).split(" ")[0]}
                  </Text>
                </View>
                <Text {...DYNAMIC_TYPE}
                  style={[ss.heroFelt, { fontFamily: famSerif(lang, "med"), color: bandInkIdx(bandIdx(pm.mid) ?? 0) ?? V2T.text }]}
                >
                  {t(feltKeyForBand(bandIdx(pm.mid)), lang)}
                </Text>
                <Text {...DYNAMIC_TYPE}
                  style={[ss.heroRef, NUM, { fontFamily: fam(lang, "reg") }]}
                >
                  {t("cityHeroUnitUg", lang)}
                  {"\n"}
                  {pm.mid / WHO_DAILY_UG > 1.05
                    ? t("refWhoOver", lang, { x: pm.mid / WHO_DAILY_UG >= 10 ? Math.round(pm.mid / WHO_DAILY_UG) : (pm.mid / WHO_DAILY_UG).toFixed(1) })
                    : t("refWhoUnder", lang)}
                  {` · ${t("cityHeroAirNow", lang, { n: Math.round(pm.mid) })}`}
                </Text>
                {/* the good→severe anchor: where today's city air sits on
                    the CPCB scale — position, not prose */}
                <View style={ss.heroScale}>
                  <BandScale idx={bandIdx(pm.mid) ?? 0} lang={lang} />
                </View>
                {/* a band that starts at 0 says nothing a stranger can use */}
                {Math.round(inhaled.lo) > 0 && (
                  <Text {...DYNAMIC_TYPE}
                    style={[ss.heroRange, NUM, { fontFamily: famMonoText(lang, "reg") }]}
                  >
                    {t("cityHeroRange", lang, {
                      lo: Math.round(inhaled.lo),
                      hi: Math.round(inhaled.hi),
                    })}
                  </Text>
                )}
                {showCig && cig != null && (
                  <Text {...DYNAMIC_TYPE}
                    style={[ss.heroRange, NUM, { fontFamily: famMonoText(lang, "reg") }]}
                  >
                    {`${fmtCig(cig.mid)} ${t("cityHeroUnit", lang)}`}
                  </Text>
                )}
                {/* why tonight — the field's causal read lives inside
                    the hero card, not floating beneath it */}
                {data.why?.line ? (
                  <Text {...DYNAMIC_TYPE} style={[ss.whyHero, { fontFamily: famSerif(lang, "reg") }]}>
                    {whyLine(data.why, data.wind, lang)}
                  </Text>
                ) : null}
                {/* the parali/news note — measured fields in plain words;
                    the tag says where it came from, never a news feed */}
                {data.why && noteLine(data.why, lang) ? (
                  <Text {...DYNAMIC_TYPE} style={[ss.whyNote, { fontFamily: fam(lang, "reg") }]}>
                    {noteLine(data.why, lang)}
                    <Text style={ss.whyNoteTag}>{` · ${t("noteMeasured", lang)}`}</Text>
                  </Text>
                ) : null}
              </View>
            ) : (
              <Text {...DYNAMIC_TYPE}
                style={[
                  ss.heroLead,
                  { fontFamily: fam(lang, "med"), marginTop: 16, marginHorizontal: 18 },
                ]}
              >
                {t("cityNoField", lang)}
              </Text>
            )}

            {/* freshness — the age chip always tells the truth */}
            <View style={ss.chips}>
              {ageMin != null && !stale ? (
                <Chip
                  icon="clock"
                  label={t("updatedMinAgo", lang, {
                    n: Math.max(1, ageMin),
                  })}
                  lang={lang}
                />
              ) : null}
              {stale ? (
                <Chip icon="clock" label={t("cityStale", lang)} lang={lang} />
              ) : null}
              {offline ? (
                <Chip
                  icon="info"
                  label={t("dataFromModelOnly", lang)}
                  lang={lang}
                />
              ) : null}
            </View>

            {/* the other instruments in the air — real field species,
                city mean; a species the field doesn't serve is simply
                absent, never zero-filled */}
            {(() => {
              const sp = data.species;
              if (!sp) return null;
              /* each reading stands beside its WHO 2021 guideline (24-h
                 means; O₃ is the 8-h peak value) — the reference is the
                 meaning, and over-limit values take the over-limit ink */
              const tiles: { label: string; val: string; who: number | null; over: boolean; whoTxt?: string }[] = [];
              const push = (key: string, label: string, who: number | null) => {
                const v = sp[key];
                if (v) tiles.push({ label, val: `${v.mean}`, who, over: who != null && v.mean > who });
              };
              push("pm10", "PM10", 45);
              push("nitrogen_dioxide", "NO\u2082", 25);
              push("ozone", "O\u2083", 100);
              push("carbon_monoxide", "CO", 4000);
              push("sulphur_dioxide", "SO\u2082", 40);
              push("ammonia", "NH\u2083", null);
              const aqi = sp.us_aqi;
              /* the index is NOT µg/m³ — its own 0–500 scale is stated on
                 the tile so it never reads as another concentration */
              if (aqi) tiles.push({ label: "US AQI", val: `${Math.round(aqi.mean)}`, who: null, over: false, whoTxt: t("aqiScale", lang) });
              if (!tiles.length) return null;
              return (
                <>
                  <Text {...DYNAMIC_TYPE} style={[ss.sec, { fontFamily: fam(lang, "semi") }]}>
                    {t("citySpeciesTitle", lang)}
                  </Text>
                  <View style={ss.speciesGrid}>
                    {tiles.map((tile, i) => (
                      <View key={tile.label} style={[ss.speciesTile, i > 0 && ss.speciesSep]}>
                        <Text {...DYNAMIC_TYPE} numberOfLines={1}
                              style={[ss.speciesLab, { fontFamily: fam(lang, "med") }]}>
                          {tile.label}
                        </Text>
                        <Text {...DYNAMIC_TYPE} numberOfLines={1}
                              style={[ss.speciesVal, NUM, { fontFamily: fam(lang, "med"),
                                      color: tile.over ? V2T.band3 : V2T.text }]}>
                          {tile.val}
                        </Text>
                        <Text {...DYNAMIC_TYPE} numberOfLines={1}
                              style={[ss.speciesWho, NUM, { fontFamily: fam(lang, "reg") }]}>
                          {tile.whoTxt ?? (tile.who != null ? t("whoRef", lang, { n: tile.who }) : "")}
                        </Text>
                      </View>
                    ))}
                  </View>
                  <Text {...DYNAMIC_TYPE} style={[ss.speciesNote,
                               { fontFamily: fam(lang, "reg") }]}>
                    {t("citySpeciesNote", lang)}
                  </Text>
                </>
              );
            })()}

            {/* vs the decade norm — real archive baseline, omitted when
                the backend has no typical (never a fabricated one) */}
            {data.typical?.vs_now_pct != null ? (
              <Text {...DYNAMIC_TYPE} style={[ss.speciesNote,
                           { fontFamily: fam(lang, "reg") }]}>
                {t(data.typical.vs_now_pct < 0 ? "cityTypicalBelow" : "cityTypicalAbove", lang, {
                  p: Math.abs(Math.round(data.typical.vs_now_pct)),
                  med: Math.round(data.typical.median),
                })}
              </Text>
            ) : null}

            {/* the next 12 hours — live-anchored CAMS forecast, real
                hourly values; omitted when the horizon is cold */}
            {(() => {
              const hrs = data.next_hours;
              if (!hrs || hrs.length < 2) return null;
              const max = Math.max(...hrs.map((x) => x.pm25), 1);
              return (
                <>
                  <Text {...DYNAMIC_TYPE} style={[ss.sec, { fontFamily: fam(lang, "semi") }]}>
                    {t("cityForecastTitle", lang)}
                  </Text>
                  <View style={ss.fcRow}>
                    {hrs.map((x) => (
                      <View key={x.h} style={ss.fcCol}>
                        <Text {...DYNAMIC_TYPE} style={[ss.fcVal,
                                     { fontFamily: famMono(lang, "reg") }]}>
                          {x.h % 3 === 0 ? `${Math.round(x.pm25)}` : ""}
                        </Text>
                        <View style={[ss.fcBar,
                              { height: 4 + Math.round(28 * x.pm25 / max),
                                /* bars carry the band, not flat accent —
                                   "next 12h" must read heavy when heavy */
                                backgroundColor: bandColor(x.pm25) ?? V2T.text3 }]} />
                        <Text {...DYNAMIC_TYPE} style={[ss.fcHr,
                                     { fontFamily: famMonoText(lang, "reg") }]}>
                          {x.h === 0 ? t("cityForecastNow", lang)
                                    : x.h % 3 === 0 ? t("hourTick", lang, { n: x.h }) : ""}
                        </Text>
                      </View>
                    ))}
                  </View>
                  <Text {...DYNAMIC_TYPE} style={[ss.speciesNote,
                               { fontFamily: fam(lang, "reg") }]}>
                    {t("cityForecastNote", lang)}
                  </Text>
                </>
              );
            })()}

            {/* the traveller aggregates — measured streets, the day's
                totals, how Delhi moves — all counted from shared trips.
                own === 0 keeps them off a fresh install; own === null
                keeps them off until the ledger answers. */}
            {own === null ? null : own === 0 ? (
              <View style={ss.ownEmpty}>
                <Text {...DYNAMIC_TYPE} style={[ss.ownEmptyLine, { fontFamily: fam(lang, "reg") }]}>
                  {t("cityNoOwnTrips", lang)}
                </Text>
                <Text {...DYNAMIC_TYPE} style={[ss.ownEmptySub, { fontFamily: fam(lang, "reg") }]}>
                  {t("cityNoOwnTripsSub", lang)}
                </Text>
              </View>
            ) : (
            <>
            {/* measured streets — k>=3 aggregates, heaviest first */}
            <Text {...DYNAMIC_TYPE} style={[ss.sec, { fontFamily: fam(lang, "semi") }]}>
              {t("cityStreetsTitle", lang)}
            </Text>
            {corridors.length === 0 ? (
              <Text {...DYNAMIC_TYPE} style={[ss.empty, { fontFamily: fam(lang, "reg") }]}>
                {t("cityEmptyStreets", lang)}
              </Text>
            ) : (
              <View style={ss.speciesGrid}>
                {corridors.map((c, i) => (
                  <CorridorRow key={c.cell} c={c} first={i === 0} lang={lang} />
                ))}
              </View>
            )}

            {/* what ALive travellers did today — city totals only;
                hidden when there's nothing (doc 07: no zero-fill) */}
            {day && day.trips > 0 ? (
              <>
                <Text {...DYNAMIC_TYPE} style={[ss.sec, { fontFamily: fam(lang, "semi") }]}>
                  {t("cityTravellersTitle", lang)}
                </Text>
                <Text {...DYNAMIC_TYPE}
                  style={[
                    ss.dayLine,
                    NUM,
                    { fontFamily: fam(lang, "reg") },
                  ]}
                >
                  {showCig
                    ? t("cityTravellersLine", lang, {
                        trips: day.trips,
                        tripNoun: t(day.trips === 1 ? "tripNounOne" : "tripNounMany", lang),
                        km: fmtKm(day.km),
                        cigs: fmtCig(cigOf(day.dose_ug) ?? 0),
                        kg: fmtKg(day.co2_kg_mid),
                      })
                    : t("cityTravellersLineUg", lang, {
                        trips: day.trips,
                        tripNoun: t(day.trips === 1 ? "tripNounOne" : "tripNounMany", lang),
                        km: fmtKm(day.km),
                        ug: approx(Math.round(day.dose_ug)),
                        kg: fmtKg(day.co2_kg_mid),
                      })}
                </Text>
                {day.switched > 0 ? (
                  <Text {...DYNAMIC_TYPE}
                    style={[
                      ss.dayLine,
                      NUM,
                      { fontFamily: fam(lang, "reg") },
                    ]}
                  >
                    {t("citySwitched", lang, { n: day.switched, tripNoun: t(day.switched === 1 ? "tripNounOne" : "tripNounMany", lang) })}
                  </Text>
                ) : null}
              </>
            ) : null}

            {/* how Delhi actually moves — real donated aggregates (k≥3),
                honest insufficient-data state inside the card */}
            <CityMoves data={moves} lang={lang} />
            </>
            )}

            {/* why this is an estimate — the machinery lives here */}
            <Pressable
              onPress={toggleWhy}
              style={({ pressed }) => [
                ss.whyBtn,
                pressed && { backgroundColor: "rgba(255,255,255,0.55)" },
              ]}
              accessibilityRole="button"
              accessibilityLabel={t("cityWhyTitle", lang)}
            >
              <Icon name="info" color={V2T.text2} size={16} />
              <Text {...DYNAMIC_TYPE}
                style={[ss.whyLabel, { fontFamily: fam(lang, "med") }]}
              >
                {t("cityWhyTitle", lang)}
              </Text>
              <View
                style={{
                  transform: [{ rotate: whyOpen ? "90deg" : "0deg" }],
                }}
              >
                <Icon name="chevron" color={V2T.text3} size={14} />
              </View>
            </Pressable>
            {whyOpen ? (
              <View style={ss.whyBody}>
                <WhyLine text={t("cityBasisModel", lang)} lang={lang} />
                <WhyLine
                  text={
                    offline
                      ? t("cityBasisNoStations", lang)
                      : t("cityBasisStations", lang, { n: st?.count ?? 0 })
                  }
                  lang={lang}
                />
                {pm ? (
                  <WhyLine
                    text={t("cityBasisPm25Ug", lang, {
                      lo: pm.lo,
                      hi: pm.hi,
                    })}
                    lang={lang}
                  />
                ) : null}
                <WhyLine text={t("cityBasisBand", lang)} lang={lang} />
                <WhyLine
                  text={((tr?.window_h ?? 72) % 24 === 0
                      ? t("cityBasisPrivacyDays", lang, {
                          k: tr?.k_min ?? 3,
                          d: Math.round((tr?.window_h ?? 72) / 24),
                        })
                      : t("cityBasisPrivacy", lang, {
                          k: tr?.k_min ?? 3,
                          h: tr?.window_h ?? 72,
                        }))}
                  lang={lang}
                />
              </View>
            ) : null}
          </>
        )}
      </ScrollView>
    </View>
  );
}

const DelhiSheet = React.memo(DelhiSheetInner);

/* ---------- public component: <DelhiToday visible onClose lang /> -------- */

function DelhiTodayInner({
  visible,
  onClose,
  lang = "en",
  showCig = false,
}: {
  visible: boolean;
  onClose: () => void;
  lang?: Lang;
  /** cigarette-equivalence framing — off by default (settings.show_cig) */
  showCig?: boolean;
}) {
  bump("scr.DelhiToday");
  /* hardware back closes the sheet — the Modal's onRequestClose used to
     provide this; the overlay needs BackHandler explicitly. */
  useEffect(() => {
    if (!visible) return;
    const sub = BackHandler.addEventListener("hardwareBackPress", () => { onClose(); return true; });
    return () => sub.remove();
  }, [visible, onClose]);

  /* plain absolute overlay — RN Modal's native present/dismiss segfaults
     this stack (reproduced on the search sheet three times) — no Modal,
     no crash class. The slide-up the Modal provided is kept as a JS-driver
     enter spring (the proven-safe pattern from Sheet/SearchScreen). */
  const [enter] = useState(() => new Animated.Value(0));
  const [enterTy] = useState(() => enter.interpolate({ inputRange: [0, 1], outputRange: [36, 0] }));
  /* once the enter spring has run its course the live transform comes
     off: a residual translateY on the ScrollView's parent swallowed drag
     gestures on Android 15 while taps still landed (emulator drive, D1).
     Post-settle the static style is visually identical. */
  const [settled, setSettled] = useState(false);
  const [wasVisible, setWasVisible] = useState(visible);
  if (visible !== wasVisible) {
    /* sanctioned render-phase reset — re-opening re-arms the spring */
    setWasVisible(visible);
    setSettled(false);
  }
  useEffect(() => {
    if (visible) {
      enter.setValue(0);
      jank("enter.delhitoday");
      Animated.spring(enter, { toValue: 1, damping: 24, stiffness: 240, useNativeDriver: true })
        .start(({ finished }) => finished && setSettled(true));
    }
  }, [visible, enter]);

  if (!visible) return null;
  return (
    <View style={ss.backdrop}>
      <StatusBar style="dark" />
      <Animated.View style={settled
        ? { flex: 1 }
        : { flex: 1, opacity: enter, transform: [{ translateY: enterTy }] }}>
        <DelhiSheet onClose={onClose} lang={lang} showCig={showCig} />
      </Animated.View>
    </View>
  );
}

/** WHO 2021 24-hour PM2.5 guideline, µg/m³. */
const WHO_DAILY_UG = 15;

export const DelhiToday = React.memo(DelhiTodayInner);

export default DelhiToday;

const ss = StyleSheet.create({
  /* elevation must beat HomeScreen's 24 — Android dispatches sibling touches
     by z before mount order, so the still-mounted home scroll swallowed this
     sheet's drags. iOS ignores it. */
  backdrop: { ...StyleSheet.absoluteFill, backgroundColor: V2T.scrim, elevation: 30 },
  root: {
    flex: 1,

    /* solid paper, not glass: a full-screen sheet over a populated home
       must not let the hero/cards ghost through (95% glass read as a
       rendering bug, not frost) — the scrim dims, the pane is opaque */
    backgroundColor: V2T.bg,
    borderTopLeftRadius: V2Radius.sheet,
    borderTopRightRadius: V2Radius.sheet,
    ...V2Elev.sheet,
    overflow: "hidden",
  },
  bar: {
    flexDirection: "row",
    alignItems: "center",
    height: 56,
    paddingHorizontal: 12,
  },
  barBtn: { padding: 6, marginRight: 8 },
  title: { color: V2T.text, fontSize: V2Type.title },
  flex: { flex: 1 },
  content: {},
  center: { alignItems: "center", marginTop: 60 },
  waiting: {
    color: V2T.text3,
    fontSize: V2Type.label,
    marginHorizontal: 18,
    marginVertical: 10,
  },
  retryBtn: {
    marginTop: 12,
    paddingHorizontal: 22,
    paddingVertical: 10,
    borderRadius: V2Radius.card,
    backgroundColor: V2T.surface2,
  },
  retryText: { color: V2T.accent, fontSize: V2Type.secondary },

  /* no card: the hero is the top of the sheet, washed by the band and
     settling into paper — the same statement grammar as home */
  hero: {
    paddingHorizontal: 22, paddingTop: 22, paddingBottom: 18,
  },
  heroLead: { color: V2T.text2, fontSize: V2Type.body },
  heroRow: {
    flexDirection: "row",
    alignItems: "center",
    marginTop: 4,
    gap: 10,
  },
  heroNum: { fontSize: 96, lineHeight: 102, letterSpacing: -4, marginLeft: -3 },
  heroUnit: { color: V2T.text2, fontSize: V2Type.body, alignSelf: "flex-end", paddingBottom: 18 },
  heroFelt: { fontSize: V2Type.display, letterSpacing: -0.4, marginTop: -4 },
  heroRef: { color: V2T.text2, fontSize: V2Type.secondary, lineHeight: 21, marginTop: 4 },
  heroScale: { marginTop: 10, alignSelf: "stretch" as const, maxWidth: 210 },
  heroRange: { color: V2T.text2, fontSize: V2Type.label, marginTop: 4 },

  chips: {
    flexDirection: "row",
    flexWrap: "wrap",
    marginHorizontal: 18,
    marginTop: 16,
    gap: 8,
  },
  chip: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    paddingHorizontal: 12,
    paddingVertical: 7,
    borderRadius: V2Radius.pill,
    backgroundColor: V2T.surface2,
  },
  chipText: { color: V2T.text2, fontSize: V2Type.label },

  /* section heads — warm labels, not uppercase micro eyebrows */
  sec: {
    color: V2T.text,
    fontSize: V2Type.secondary,
    marginTop: 24,
    marginBottom: 6,
    marginHorizontal: 18,
  },
  empty: {
    color: V2T.text3,
    fontSize: V2Type.secondary,
    marginHorizontal: 18,
    marginTop: 4,
    lineHeight: 21,
  },
  /* the fresh-install empty state — a quiet well, not a card
     (emptiness reads as stillness, never a coloured block) */
  ownEmpty: {
    marginHorizontal: 18,
    marginTop: 24,
    paddingHorizontal: 16,
    paddingVertical: 16,
    borderRadius: 20,
    backgroundColor: V2T.surface2,
  },
  ownEmptyLine: { color: V2T.text, fontSize: V2Type.secondary, lineHeight: 21 },
  ownEmptySub: { color: V2T.text3, fontSize: V2Type.label, lineHeight: 19, marginTop: 6 },
  cRow: {
    flexDirection: "row",
    alignItems: "center",
    minHeight: 58,
    paddingVertical: 10,
  },
  cGlyph: {
    width: 24,
    alignItems: "center",
    justifyContent: "center",
    marginRight: 12,
  },
  cText: { flex: 1, marginRight: 10 },
  cName: { color: V2T.text, fontSize: V2Type.body },
  cSub: { color: V2T.text3, fontSize: V2Type.label, marginTop: 1 },
  cRel: { fontSize: V2Type.label },

  dayLine: {
    color: V2T.text2,
    fontSize: V2Type.secondary,
    marginHorizontal: 18,
    marginTop: 4,
    lineHeight: 22,
  },
  /* the species instruments as tinted stat tiles — a wrapping grid,
     each tile number-over-symbol in its family well (sky instruments,
     clay AQI summary) */
  speciesGrid: {
    marginHorizontal: 16,
    marginTop: 8,
    borderRadius: 20, borderCurve: "continuous",
    backgroundColor: V2T.surface,
    ...V2Elev.card,
    paddingHorizontal: 16,
  },
  speciesTile: {
    flexDirection: "row", alignItems: "center",
    paddingVertical: 12,
  },
  speciesSep: { borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: V2T.hairline },
  speciesLab: { flex: 1, color: V2T.text2, fontSize: V2Type.secondary },
  speciesVal: { fontSize: V2Type.body, minWidth: 64, textAlign: "right" },
  speciesWho: { color: V2T.text3, fontSize: V2Type.label, minWidth: 84, textAlign: "right" },
  speciesNote: {
    color: V2T.text3,
    fontSize: V2Type.label,
    marginHorizontal: 18,
    marginTop: 2,
  },
  fcRow: {
    flexDirection: "row",
    marginHorizontal: 18,
    marginTop: 8,
    alignItems: "flex-end",
  },
  fcCol: { flex: 1, alignItems: "center" },
  fcVal: { color: V2T.text2, fontSize: V2Type.label, height: 15 },
  fcBar: {
    width: 12,
    borderRadius: 6,
    backgroundColor: V2T.accent,
    marginTop: 2,
  },
  fcHr: {
    color: V2T.text3,
    fontSize: V2Type.label,
    height: 15,
    marginTop: 3,
  },

  whyBtn: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    marginTop: 24,
    marginHorizontal: 18,
    paddingHorizontal: 14,
    paddingVertical: 13,
    borderRadius: V2Radius.row,
    backgroundColor: V2T.surface2,
  },
  whyLabel: { color: V2T.text, fontSize: V2Type.secondary, flex: 1 },
  whyBody: { marginHorizontal: 20, marginTop: 10, gap: 8 },
  whyLine: { color: V2T.text2, fontSize: V2Type.label, lineHeight: 19 },
  whyHero: {
    color: V2T.text2,
    fontSize: V2Type.secondary,
    lineHeight: 21,
    marginTop: 10,
    fontStyle: "italic",
  },
  whyNote: {
    color: V2T.text2,
    fontSize: V2Type.label,
    lineHeight: 19,
    marginTop: 8,
  },
  whyNoteTag: { color: V2T.text3 },
});
