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
  Modal,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { StatusBar } from "expo-status-bar";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import Svg, { Path } from "react-native-svg";
import {
  cigOf,
  doseColor,
  fam,
  NUM,
  V2Radius,
  V2T,
  V2Type,
} from "../theme";
import { approx, t, type Lang } from "../i18n/strings";
import { Icon, type Glyph } from "../icons";
import {
  fetchCity,
  fetchCityMoves, type CityMovesPayload,
  type CityCorridor,
  type CityPayload,
} from "../api/city";
import { CityMoves } from "../components/CityMoves";
import { DYNAMIC_TYPE } from "../a11y";

const fmtCig = (v: number): string => (v < 1 ? v.toFixed(2) : v.toFixed(1));
const fmtKm = (km: number): string =>
  km < 10 ? km.toFixed(1) : `${Math.round(km)}`;
const fmtKg = (kg: number): string => (kg < 1 ? kg.toFixed(2) : kg.toFixed(1));

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

function CorridorRow({ c, lang }: { c: CityCorridor; lang: Lang }) {
  const heavy = c.relative === "heavier";
  return (
    <View style={ss.cRow}>
      <View style={ss.cGlyph}>
        <Icon name="pin" color={V2T.text2} size={18} />
      </View>
      <View style={ss.cText}>
        <Text {...DYNAMIC_TYPE}
          style={[ss.cName, { fontFamily: fam(lang, "med") }]}
          numberOfLines={1}
        >
          {c.name ?? t("cityUnnamed", lang)}
        </Text>
        <Text {...DYNAMIC_TYPE} style={[ss.cSub, NUM, { fontFamily: fam(lang, "reg") }]}>
          {t("cityTrips", lang, { n: c.trips })}
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

/* ---------- sheet (mounted only while visible → fresh state each open) --- */

function DelhiSheet({ onClose, lang, showCig }: { onClose: () => void; lang: Lang; showCig: boolean }) {
  const [data, setData] = useState<CityPayload | null>(null);
  const [moves, setMoves] = useState<CityMovesPayload | null>(null);
  const [failed, setFailed] = useState(false);
  const [whyOpen, setWhyOpen] = useState(false);
  const [nonce, setNonce] = useState(0);
  const insets = useSafeAreaInsets();

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
          onPress={onClose}
          hitSlop={10}
          accessibilityRole="button"
          accessibilityLabel={t("a11yBack", lang)}
          style={ss.barBtn}
        >
          <BackGlyph color={V2T.text2} />
        </Pressable>
        <Text {...DYNAMIC_TYPE} style={[ss.title, { fontFamily: fam(lang, "semi") }]}>
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
                setFailed(false);
                setData(null);
                setNonce((n) => n + 1);
              }}
              style={({ pressed }) => [
                ss.retryBtn,
                pressed && { backgroundColor: V2T.surface2 },
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
            {/* hero — one number: a day of Delhi air. Cigarettes only with
                showCig on; the default surface is µg inhaled + the plain
                species/percentile context below (owner mandate). */}
            {data.breath && pm && (showCig ? cig : inhaled) ? (
              <View style={ss.hero}>
                <Text {...DYNAMIC_TYPE}
                  style={[ss.heroLead, { fontFamily: fam(lang, "med") }]}
                >
                  {t("cityHeroLead", lang)}
                </Text>
                <View style={ss.heroRow}>
                  <Text {...DYNAMIC_TYPE}
                    style={[
                      ss.heroNum,
                      NUM,
                      {
                        fontFamily: fam(lang, "semi"),
                        color: doseColor(pm.mid),
                      },
                    ]}
                  >
                    ≈ {showCig ? fmtCig(cig!.mid) : Math.round(inhaled!.mid)}
                  </Text>
                  <Icon
                    name={showCig ? "cigarette" : "dust"}
                    color={doseColor(pm.mid)}
                    size={30}
                  />
                </View>
                <Text {...DYNAMIC_TYPE}
                  style={[ss.heroUnit, { fontFamily: fam(lang, "reg") }]}
                >
                  {t(showCig ? "cityHeroUnit" : "cityHeroUnitUg", lang)}
                </Text>
                <Text {...DYNAMIC_TYPE}
                  style={[ss.heroRange, NUM, { fontFamily: fam(lang, "reg") }]}
                >
                  {showCig
                    ? t("cityHeroRange", lang, {
                        lo: fmtCig(cig!.lo),
                        hi: fmtCig(cig!.hi),
                      })
                    : t("cityHeroRange", lang, {
                        lo: Math.round(inhaled!.lo),
                        hi: Math.round(inhaled!.hi),
                      })}
                </Text>
              </View>
            ) : (
              <Text {...DYNAMIC_TYPE}
                style={[
                  ss.heroLead,
                  { fontFamily: fam(lang, "med"), marginTop: 16 },
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
              const items: string[] = [];
              const push = (key: string, label: string) => {
                const v = sp[key];
                if (v) items.push(`${label} ${v.mean}`);
              };
              push("pm10", "PM10");
              push("nitrogen_dioxide", "NO₂");
              push("ozone", "O₃");
              push("carbon_monoxide", "CO");
              push("sulphur_dioxide", "SO₂");
              push("ammonia", "NH₃");
              const aqi = sp.us_aqi;
              if (aqi) items.push(`US AQI ${Math.round(aqi.mean)}`);
              if (!items.length) return null;
              return (
                <>
                  <Text {...DYNAMIC_TYPE} style={[ss.sec, { fontFamily: fam(lang, "semi") }]}>
                    {t("citySpeciesTitle", lang)}
                  </Text>
                  <Text {...DYNAMIC_TYPE} style={[ss.speciesLine, NUM,
                               { fontFamily: fam(lang, "reg") }]}>
                    {items.join(" · ")}
                  </Text>
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
                {t("cityTypicalLine", lang)
                  .replace("{pct}", `${data.typical.vs_now_pct > 0 ? "+" : ""}${data.typical.vs_now_pct}`)
                  .replace("{med}", `${Math.round(data.typical.median)}`)}
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
                                     { fontFamily: fam(lang, "reg") }]}>
                          {x.h % 3 === 0 ? `${Math.round(x.pm25)}` : ""}
                        </Text>
                        <View style={[ss.fcBar,
                              { height: 4 + Math.round(28 * x.pm25 / max) }]} />
                        <Text {...DYNAMIC_TYPE} style={[ss.fcHr,
                                     { fontFamily: fam(lang, "reg") }]}>
                          {x.h === 0 ? t("cityForecastNow", lang)
                                    : x.h % 3 === 0 ? `+${x.h}h` : ""}
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

            {/* measured streets — k>=3 aggregates, heaviest first */}
            <Text {...DYNAMIC_TYPE} style={[ss.sec, { fontFamily: fam(lang, "semi") }]}>
              {t("cityStreetsTitle", lang)}
            </Text>
            {corridors.length === 0 ? (
              <Text {...DYNAMIC_TYPE} style={[ss.empty, { fontFamily: fam(lang, "reg") }]}>
                {t("cityEmptyStreets", lang)}
              </Text>
            ) : (
              corridors.map((c) => (
                <CorridorRow key={c.cell} c={c} lang={lang} />
              ))
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
                        km: fmtKm(day.km),
                        cigs: fmtCig(cigOf(day.dose_ug) ?? 0),
                        kg: fmtKg(day.co2_kg_mid),
                      })
                    : t("cityTravellersLineUg", lang, {
                        trips: day.trips,
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
                    {t("citySwitched", lang, { n: day.switched })}
                  </Text>
                ) : null}
              </>
            ) : null}

            {/* how Delhi actually moves — real donated aggregates (k≥3),
                honest insufficient-data state inside the card */}
            <CityMoves data={moves} lang={lang} />

            {/* why this is an estimate — the machinery lives here */}
            <Pressable
              onPress={() => setWhyOpen((o) => !o)}
              style={({ pressed }) => [
                ss.whyBtn,
                pressed && { backgroundColor: V2T.surface2 },
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
                    text={t(showCig ? "cityBasisPm25" : "cityBasisPm25Ug", lang, {
                      lo: pm.lo,
                      hi: pm.hi,
                    })}
                    lang={lang}
                  />
                ) : null}
                <WhyLine text={t("cityBasisBand", lang)} lang={lang} />
                <WhyLine
                  text={t("cityBasisPrivacy", lang, {
                    k: tr?.k_min ?? 3,
                    h: tr?.window_h ?? 72,
                  })}
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

/* ---------- public component: <DelhiToday visible onClose lang /> -------- */

export function DelhiToday({
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
  return (
    <Modal
      visible={visible}
      transparent
      animationType="slide"
      onRequestClose={onClose}
      statusBarTranslucent
    >
      <View style={ss.backdrop}>
        <StatusBar style="dark" />
        {visible ? <DelhiSheet onClose={onClose} lang={lang} showCig={showCig} /> : null}
      </View>
    </Modal>
  );
}

export default DelhiToday;

const ss = StyleSheet.create({
  backdrop: { flex: 1, backgroundColor: V2T.scrim },
  root: {
    flex: 1,

    backgroundColor: V2T.bg,
    borderTopLeftRadius: V2Radius.sheet,
    borderTopRightRadius: V2Radius.sheet,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderColor: V2T.line,
    overflow: "hidden",
  },
  bar: {
    flexDirection: "row",
    alignItems: "center",
    height: 52,
    paddingHorizontal: 12,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: V2T.line,
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
    borderRadius: V2Radius.pill,
    backgroundColor: V2T.surface,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: V2T.line,
  },
  retryText: { color: V2T.accent, fontSize: V2Type.secondary },

  hero: { marginTop: 18, marginHorizontal: 18 },
  heroLead: { color: V2T.text2, fontSize: V2Type.body },
  heroRow: {
    flexDirection: "row",
    alignItems: "center",
    marginTop: 4,
    gap: 10,
  },
  heroNum: { fontSize: V2Type.hero, lineHeight: 40 },
  heroUnit: { color: V2T.text, fontSize: V2Type.body, marginTop: 2 },
  heroRange: { color: V2T.text3, fontSize: V2Type.label, marginTop: 4 },

  chips: {
    flexDirection: "row",
    flexWrap: "wrap",
    marginHorizontal: 14,
    marginTop: 14,
    gap: 8,
  },
  chip: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: V2Radius.pill,
    backgroundColor: V2T.surface,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: V2T.line,
  },
  chipText: { color: V2T.text2, fontSize: V2Type.label },

  sec: {
    color: V2T.text3,
    fontSize: V2Type.label,
    letterSpacing: 0.6,
    textTransform: "uppercase",
    marginTop: 22,
    marginBottom: 4,
    marginHorizontal: 18,
  },
  empty: {
    color: V2T.text3,
    fontSize: V2Type.secondary,
    marginHorizontal: 18,
    marginTop: 4,
    lineHeight: 21,
  },
  cRow: {
    flexDirection: "row",
    alignItems: "center",
    minHeight: 54,
    paddingHorizontal: 14,
    paddingVertical: 8,
    marginHorizontal: 4,
    borderRadius: V2Radius.row,
  },
  cGlyph: {
    width: 34,
    height: 34,
    borderRadius: 17,
    backgroundColor: V2T.surface,
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
  speciesLine: {
    color: V2T.text2,
    fontSize: V2Type.secondary,
    marginHorizontal: 18,
    marginTop: 4,
    lineHeight: 22,
  },
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
    width: 10,
    borderRadius: 3,
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
    marginTop: 26,
    marginHorizontal: 14,
    paddingHorizontal: 12,
    paddingVertical: 12,
    borderRadius: V2Radius.row,
    backgroundColor: V2T.surface,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: V2T.line,
  },
  whyLabel: { color: V2T.text2, fontSize: V2Type.secondary, flex: 1 },
  whyBody: { marginHorizontal: 20, marginTop: 10, gap: 8 },
  whyLine: { color: V2T.text3, fontSize: V2Type.label, lineHeight: 19 },
});
