/** "Your day" — the dosimeter surface (docs/plan/alive-depth L1–L4).
 *  One additive card stack, never a new IA: the existing journey stays
 *  where it was; this screen is a peek card on the idle map + one
 *  full-screen stack behind it.
 *
 *  What's on it, top to bottom:
 *   1. the morning card — the field's own h-series at the user's cell
 *      (GET /grid?cells=8&param=pm2_5&h=0..11), a hairline sparkline with
 *      CPCB band-dots, the heaviest + lightest ~3h windows, and the ONE
 *      decision the swing changes ("same plan at X breathes ~N× lighter").
 *      Never "don't go out" — always the cheaper-for-lungs version of the
 *      same plan; a flat day says it's flat.
 *   2. your day — the on-device reconstruction (daylog.ts): ≈µg breathed,
 *      a 24-slot hour arc (covered spans only — the arc leaves uncovered
 *      hours blank instead of inventing exposure), top accumulators.
 *   3. the symptom lens — breath/eyes/energy single-tap check-in, stored
 *      on this phone only; the correlation line earns itself after ~7 days.
 *   4. personal tiles — today µg / week arc / budget left, in the admin
 *      tile language (mono micro label + serif number).
 *   5. your budget — quiet profile ceiling, honest over/under flag.
 *
 *  Copy rule for the whole stack: "same life, cheaper for lungs" — a card
 *  that can't name a cheaper window/mode shows the number plainly, never
 *  a restriction.
 */

import React, { useEffect, useState } from "react";
import {
  Animated,
  BackHandler,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { StatusBar } from "expo-status-bar";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import Svg, { Circle, Path } from "react-native-svg";
import {
  NUM,
  V2Radius,
  V2T,
  V2Type,
  bandColor,
  fam,
  famMono,
  famSerif,
} from "../theme";
import { approx, t, type Lang } from "../i18n/strings";
import { Icon } from "../icons";
import { DYNAMIC_TYPE, useReduceMotion } from "../a11y";
import { tap, tick } from "../haptics";
import { inNcr } from "../components/shell/net";
import {
  allSamples,
  dayKey,
  getCheckins,
  reconstructDay,
  symptomLens,
  type Checkin,
  type DayReconstruction,
  type LensVerdict,
} from "../store/daylog";
import type { Trip } from "../store/ledger";
import {
  fetchDayCurve,
  morningAnswers,
  type DayCurve,
} from "../api/dayfield";
import { PROFILE_BUDGET_UG, type ShellSettings } from "../components/shell/settings";

/* ---------------- the hook: one assemble of the day's data --------------- */

export type DayData = {
  /** today's reconstruction — never null once disk is read */
  rec: DayReconstruction;
  /** last 7 local days' totals (oldest→today) for the week dots */
  week: { day: string; ug: number }[];
  /** the field's hourly curve at the user's cell (null = no fetch yet) */
  curve: DayCurve | null;
  /** true while position is outside the served window */
  outside: boolean;
  lens: LensVerdict;
  checkin: Checkin | null;
  /** seconds since the curve was last fetched fresh — for the stale line */
  curveAgeS: number | null;
};

/** Assemble everything the stack needs. `nonce` is a cheap re-render
 *  signal — bump it when a new ambient read lands (the aqi poll does).
 *  lat/lon select the forecast cell; DELHI centroid when no fix exists —
 *  the same fallback the freshness chip has always used. */
export function useDayData(
  lat: number, lon: number, trips: Trip[], nonce: number,
  /** fetch the 12-payload forecast curve — the peek card doesn't need it,
      so cold-start doesn't pay 12 /grid requests for a card it may never open */
  withCurve = true,
): DayData | null {
  const [data, setData] = useState<DayData | null>(null);
  // ~500 m rounding — the grid cell is ~10 km wide; drifting by a street
  // must not refetch 12 hourly payloads
  const rl = `${lat.toFixed(2)},${lon.toFixed(2)}`;
  useEffect(() => {
    let live = true;
    void (async () => {
      const [samples, checkins] = await Promise.all([allSamples(), getCheckins()]);
      const now = Date.now();
      const today = dayKey(now);
      const rec = reconstructDay(today, samples, trips, now);

      // week: one reconstruction per day — cheap at this volume, and
      // honest (a day with no samples reads 0, not an invented number)
      const week: DayData["week"] = [];
      for (let i = 6; i >= 0; i--) {
        const d = new Date(now);
        d.setDate(d.getDate() - i);
        const k = dayKey(d.getTime());
        week.push({ day: k, ug: i === 0 ? rec.totalUg : reconstructDay(k, samples, trips, d.getTime()).totalUg });
      }

      // the lens needs a dose per checkin's *previous* day, counted only
      // where coverage was real enough to say so
      const doseByDay: Record<string, number> = {};
      const keys = new Set<string>();
      for (const k of Object.keys(checkins)) {
        const d = new Date(`${k}T00:00:00`);
        d.setDate(d.getDate() - 1);
        keys.add(dayKey(d.getTime()));
      }
      for (const k of keys) {
        const r = reconstructDay(k, samples, trips, new Date(`${k}T23:59:59`).getTime());
        if (r.coveredMin >= 30 || r.parts.length > 0) doseByDay[k] = r.totalUg;
      }

      const outside = !inNcr(lat, lon);
      const curve = outside || !withCurve ? null : await fetchDayCurve(lat, lon);
      if (!live) return;
      setData({
        rec, week, curve, outside,
        lens: symptomLens(checkins, doseByDay),
        checkin: checkins[today] ?? null,
        curveAgeS: null,
      });
    })();
    return () => { live = false; };
  }, [rl, nonce, trips, withCurve]); // eslint-disable-line react-hooks/exhaustive-deps
  return data;
}

/* ---------------- shared atoms ---------------- */

const mono = (lang: Lang, w: "reg" | "med" | "semi" = "reg") => famMono(lang, w);

/** A CPCB band dot — the only colour that means data. null → empty ring. */
function BandDot({ conc, size = 7 }: { conc: number | null; size?: number }) {
  const c = bandColor(conc);
  return (
    <View style={{
      width: size, height: size, borderRadius: size / 2,
      backgroundColor: c ?? "transparent",
      borderWidth: c ? 0 : 1, borderColor: V2T.hairline,
    }} />
  );
}

/** A dose dot — colour comes from the day's fraction of the user's budget,
 *  not ambient bands (µg inhaled isn't µg/m³ air). Lighter reads quieter. */
function doseDotColor(ug: number, budgetUg: number): string {
  const r = budgetUg > 0 ? ug / budgetUg : 1;
  if (ug <= 0) return "transparent";
  if (r < 0.34) return V2T.text3;
  if (r < 0.67) return V2T.band2;
  if (r <= 1) return V2T.band3;
  return V2T.band4;
}

const fmtHr = (h: number) => `${((h + 11) % 12) + 1}${h % 24 < 12 ? "am" : "pm"}`;

/* ---------------- the morning card ---------------- */

function Sparkline({ series, lang }: { series: (number | null)[]; lang: Lang }) {
  const [w, setW] = useState(0);
  const H = 44, PAD = 8;
  const vals = series.filter((v): v is number => v != null);
  const max = Math.max(...vals, 1), min = Math.min(...vals, 0);
  const span = Math.max(1, max - min);
  const x = (i: number) => PAD + (w - 2 * PAD) * (series.length <= 1 ? 0 : i / (series.length - 1));
  const y = (v: number) => H - 14 - (H - 24) * ((v - min) / span);
  /* contiguous runs only — a failed hour is a gap in the stroke, not a
     line drawn through a guess */
  const runs: string[] = [];
  let cur = "";
  series.forEach((v, i) => {
    if (v == null) { if (cur) runs.push(cur); cur = ""; return; }
    cur += `${cur ? " L" : "M"}${x(i).toFixed(1)} ${y(v).toFixed(1)}`;
  });
  if (cur) runs.push(cur);
  return (
    <View onLayout={(e) => setW(e.nativeEvent.layout.width)}>
      {w > 0 && (
        <Svg width={w} height={H + 14}>
          {runs.map((d, i) => (
            <Path key={i} d={d} stroke={V2T.text3} strokeWidth={1} fill="none" />
          ))}
          {series.map((v, i) => (
            <Circle key={i} cx={x(i)} cy={y(v ?? min)} r={2.2}
              fill={bandColor(v) ?? V2T.hairline} opacity={v == null ? 0.4 : 1} />
          ))}
        </Svg>
      )}
      <View style={ss.sparkLabels}>
        {series.map((v, i) => (
          <Text key={i} {...DYNAMIC_TYPE}
            style={[ss.sparkHr, { fontFamily: mono(lang) }]}>
            {i % 3 === 0 ? `+${i}` : ""}
          </Text>
        ))}
      </View>
    </View>
  );
}

function MorningCard({ curve, outside, lang }: {
  curve: DayCurve | null; outside: boolean; lang: Lang;
}) {
  if (outside) {
    return (
      <View style={ss.card}>
        <Text {...DYNAMIC_TYPE} style={[ss.cardEyebrow, { fontFamily: mono(lang, "med") }]}>
          {t("dayMorningTitle", lang)}
        </Text>
        <Text {...DYNAMIC_TYPE} style={[ss.emptyLine, { fontFamily: fam(lang, "reg") }]}>
          {t("dayOutsideDelhi", lang)}
        </Text>
      </View>
    );
  }
  if (!curve) return null; // still loading — the card mounts when it can say something
  if (!curve.covered) {
    return (
      <View style={ss.card}>
        <Text {...DYNAMIC_TYPE} style={[ss.cardEyebrow, { fontFamily: mono(lang, "med") }]}>
          {t("dayMorningTitle", lang)}
        </Text>
        <Text {...DYNAMIC_TYPE} style={[ss.emptyLine, { fontFamily: fam(lang, "reg") }]}>
          {t("dayMorningNoCell", lang)}
        </Text>
      </View>
    );
  }
  const srv = curve.server;
  const a = morningAnswers(curve.series);
  // prefer the server's own windows/decisions when /v2/day answered —
  // it folds the same horizon /depart and /grid?h= serve, and a null
  // window there is an honest "no meaningful run", not missing data
  const heavy = srv ? srv.heavy : a.heavy;
  const clean = srv ? srv.clean : a.clean;
  const flat = srv ? (!srv.heavy && !srv.clean) : a.flat;
  const heavyF = srv?.heavyLabel ?? (heavy ? fmtHr(heavy.from + nowHour()) : "");
  const heavyT = srv?.heavyEndLabel ?? (heavy ? fmtHr(heavy.to + nowHour()) : "");
  const cleanF = srv?.cleanLabel ?? (clean ? fmtHr(clean.from + nowHour()) : "");
  const cleanT = srv?.cleanEndLabel ?? (clean ? fmtHr(clean.to + nowHour()) : "");
  const decision = srv?.decisions?.[0]?.line ?? null;
  return (
    <View style={ss.card}>
      <Text {...DYNAMIC_TYPE} style={[ss.cardEyebrow, { fontFamily: mono(lang, "med") }]}>
        {t("dayMorningTitle", lang)}
      </Text>
      <Sparkline series={curve.series} lang={lang} />
      {flat ? (
        <Text {...DYNAMIC_TYPE} style={[ss.moveLine, { fontFamily: fam(lang, "med") }]}>
          {decision ?? t("dayMorningFlat", lang)}
        </Text>
      ) : (
        <>
          {heavy && (
            <View style={ss.mRow}>
              <BandDot conc={heavy.conc} />
              <Text {...DYNAMIC_TYPE} style={[ss.mLine, NUM, { fontFamily: mono(lang) }]}>
                {t("dayMorningHeavy", lang, {
                  f: heavyF,
                  t: heavyT,
                  c: Math.round(heavy.conc),
                })}
              </Text>
            </View>
          )}
          {clean && (
            <View style={ss.mRow}>
              <BandDot conc={clean.conc} />
              <Text {...DYNAMIC_TYPE} style={[ss.mLine, NUM, { fontFamily: mono(lang) }]}>
                {t("dayMorningClean", lang, {
                  f: cleanF,
                  t: cleanT,
                  c: Math.round(clean.conc),
                })}
              </Text>
            </View>
          )}
          {decision ? (
            <Text {...DYNAMIC_TYPE} style={[ss.moveLine, NUM, { fontFamily: fam(lang, "med") }]}>
              {decision}
            </Text>
          ) : (
            clean && heavy && a.ratio != null && a.ratio >= 1.2 && (
              <Text {...DYNAMIC_TYPE} style={[ss.moveLine, NUM, { fontFamily: fam(lang, "med") }]}>
                {t("dayMorningMove", lang, {
                  f: cleanF,
                  g: heavyF,
                  x: a.ratio.toFixed(1),
                })}
              </Text>
            )
          )}
        </>
      )}
      {curve.conf === "lo" && (
        <Text {...DYNAMIC_TYPE} style={[ss.finePrint, { fontFamily: fam(lang, "reg") }]}>
          {t("howWe_conf", lang, { c: t("conf_low", lang) })}
        </Text>
      )}
    </View>
  );
}

const nowHour = () => new Date().getHours();

/* ---------------- your day: the arc ---------------- */

function HourArc({ rec, lang }: { rec: DayReconstruction; lang: Lang }) {
  const max = Math.max(...rec.arc.map((h) => h.dose_ug), 0.5);
  const nh = nowHour();
  return (
    <View style={ss.arcWrap}>
      {rec.arc.map((h) => {
        const isNow = h.hour === nh;
        return (
          <View key={h.hour} style={ss.arcCol}>
            <View style={ss.arcBarCol}>
              {h.conc != null && (
                <View style={[ss.arcDot, { backgroundColor: bandColor(h.conc) ?? V2T.hairline }]} />
              )}
              {h.covered && h.dose_ug > 0 && (
                <View style={[ss.arcBar, {
                  height: 4 + 40 * (h.dose_ug / max),
                  backgroundColor: isNow ? V2T.text : V2T.text3,
                }]} />
              )}
              {h.trip_marks > 0 && <View style={ss.arcTrip} />}
            </View>
            <Text {...DYNAMIC_TYPE}
              style={[ss.arcHr, { fontFamily: mono(lang) }, isNow && { color: V2T.text }]}>
              {h.hour % 3 === 0 ? `${h.hour}` : ""}
            </Text>
          </View>
        );
      })}
    </View>
  );
}

function DayCard({ rec, budgetUg, lang }: {
  rec: DayReconstruction; budgetUg: number; lang: Lang;
}) {
  return (
    <View style={ss.card}>
      <Text {...DYNAMIC_TYPE} style={[ss.cardEyebrow, { fontFamily: mono(lang, "med") }]}>
        {t("dayTitle", lang)}
      </Text>
      {rec.thin ? (
        <Text {...DYNAMIC_TYPE} style={[ss.emptyLine, { fontFamily: fam(lang, "reg") }]}>
          {t("dayThin", lang)}
        </Text>
      ) : (
        <>
          <View style={ss.heroRow}>
            <Text {...DYNAMIC_TYPE}
              style={[ss.heroNum, NUM, { fontFamily: famSerif(lang, "semi"), color: doseDotColor(rec.totalUg, budgetUg) }]}>
              ≈{Math.round(rec.totalUg)}
            </Text>
            <View style={ss.heroMeta}>
              <Text {...DYNAMIC_TYPE} style={[ss.heroUnit, { fontFamily: fam(lang, "reg") }]}>
                {t("dayBreathed", lang)}
              </Text>
              <Text {...DYNAMIC_TYPE} style={[ss.heroSub, NUM, { fontFamily: mono(lang) }]}>
                µg · {t("dayCovered", lang, { h: Math.floor(rec.coveredMin / 60), m: rec.coveredMin % 60 })}
              </Text>
            </View>
          </View>
          <HourArc rec={rec} lang={lang} />
          {rec.parts.length > 0 && (
            <>
              <Text {...DYNAMIC_TYPE} style={[ss.partsEyebrow, { fontFamily: mono(lang, "med") }]}>
                {t("dayPartsTitle", lang)}
              </Text>
              {rec.parts.map((p, i) => (
                <View key={i} style={ss.partRow}>
                  <View style={[ss.partDot, { backgroundColor: doseDotColor(p.ug, budgetUg) }]} />
                  <Text {...DYNAMIC_TYPE} style={[ss.partLabel, { fontFamily: fam(lang, "reg") }]}
                    numberOfLines={1}>
                    {p.label}
                  </Text>
                  <Text {...DYNAMIC_TYPE} style={[ss.partUg, NUM, { fontFamily: mono(lang) }]}>
                    {approx(Math.round(p.ug))}µg
                  </Text>
                </View>
              ))}
            </>
          )}
        </>
      )}
    </View>
  );
}

/* ---------------- the symptom lens ---------------- */

const FACETS = [
  { key: "breath", labelKey: "lensBreath" },
  { key: "eyes", labelKey: "lensEyes" },
  { key: "energy", labelKey: "lensEnergy" },
] as const;
const OPTS = ["lensGood", "lensMeh", "lensRough"] as const;

function LensCard({ checkin, lens, lang, onCheckin }: {
  checkin: Checkin | null; lens: LensVerdict; lang: Lang;
  onCheckin: (c: Omit<Checkin, "ts">) => void;
}) {
  const val = { breath: checkin?.breath ?? -1, eyes: checkin?.eyes ?? -1, energy: checkin?.energy ?? -1 };
  return (
    <View style={ss.card}>
      <Text {...DYNAMIC_TYPE} style={[ss.cardEyebrow, { fontFamily: mono(lang, "med") }]}>
        {t("lensTitle", lang)}
      </Text>
      <Text {...DYNAMIC_TYPE} style={[ss.lensSub, { fontFamily: fam(lang, "reg") }]}>
        {t("lensSub", lang)}
      </Text>
      {FACETS.map((f) => (
        <View key={f.key} style={ss.facetRow}>
          <Text {...DYNAMIC_TYPE} style={[ss.facetLabel, { fontFamily: fam(lang, "med") }]}>
            {t(f.labelKey, lang)}
          </Text>
          <View style={ss.facetOpts}>
            {OPTS.map((ok, v) => {
              const sel = val[f.key] === v;
              return (
                <Pressable key={ok}
                  onPress={() => { tap(); onCheckin({ breath: val.breath, eyes: val.eyes, energy: val.energy, [f.key]: v }); }}
                  accessibilityRole="button"
                  accessibilityLabel={`${t(f.labelKey, lang)}: ${t(ok, lang)}`}
                  style={[ss.opt, sel && ss.optSel]}>
                  <Text {...DYNAMIC_TYPE}
                    style={[ss.optTxt, { fontFamily: fam(lang, "reg") }, sel && ss.optTxtSel]}>
                    {t(ok, lang)}
                  </Text>
                </Pressable>
              );
            })}
          </View>
        </View>
      ))}
      <Text {...DYNAMIC_TYPE} style={[ss.finePrint, { fontFamily: fam(lang, "reg") }]}>
        {t("lensPrivacy", lang)}
      </Text>
      {/* the verdict earns its line honestly */}
      <Text {...DYNAMIC_TYPE} style={[ss.verdict, { fontFamily: fam(lang, "med") }]}>
        {lens.kind === "early" ? t("lensEarly", lang)
          : lens.kind === "flat" ? t("lensFlat", lang, { n: lens.days })
          : t("lensLink", lang, {
              f: t(lens.facet === "eyes" ? "lensFacetEyes"
                    : lens.facet === "energy" ? "lensFacetEnergy" : "lensFacetBreath", lang),
            })}
      </Text>
    </View>
  );
}

/* ---------------- personal tiles + budget ---------------- */

function TileRow({ data, budgetUg, lang }: { data: DayData; budgetUg: number; lang: Lang }) {
  const left = budgetUg - data.rec.totalUg;
  const maxW = Math.max(...data.week.map((w) => w.ug), 1);
  return (
    <View style={ss.tiles}>
      <View style={ss.tile}>
        <Text {...DYNAMIC_TYPE} style={[ss.tileLbl, { fontFamily: mono(lang, "med") }]}>
          {t("tileToday", lang)}
        </Text>
        <Text {...DYNAMIC_TYPE} style={[ss.tileNum, NUM, { fontFamily: famSerif(lang, "reg") }]}>
          {data.rec.thin ? "—" : approx(Math.round(data.rec.totalUg))}
        </Text>
        <Text {...DYNAMIC_TYPE} style={[ss.tileSub, { fontFamily: mono(lang) }]}>µg</Text>
      </View>
      <View style={ss.tile}>
        <Text {...DYNAMIC_TYPE} style={[ss.tileLbl, { fontFamily: mono(lang, "med") }]}>
          {t("tileWeek", lang)}
        </Text>
        <View style={ss.weekRow}>
          {data.week.map((w, i) => (
            <View key={w.day} style={[ss.weekDot, {
              backgroundColor: w.ug > 0 ? doseDotColor(w.ug, budgetUg) : "transparent",
              borderWidth: w.ug > 0 ? 0 : 1, borderColor: V2T.hairline,
              opacity: 0.5 + 0.5 * (w.ug / maxW),
            }]} />
          ))}
        </View>
        <Text {...DYNAMIC_TYPE} style={[ss.tileSub, NUM, { fontFamily: mono(lang) }]}>
          {approx(Math.round(data.week.reduce((s, w) => s + w.ug, 0)))}µg
        </Text>
      </View>
      <View style={ss.tile}>
        <Text {...DYNAMIC_TYPE} style={[ss.tileLbl, { fontFamily: mono(lang, "med") }]}>
          {t("tileBudget", lang)}
        </Text>
        <Text {...DYNAMIC_TYPE} style={[ss.tileNum, NUM, {
          fontFamily: famSerif(lang, "reg"),
          color: left < 0 ? V2T.breath2 : V2T.text,
        }]}>
          {data.rec.thin ? "—" : `${left < 0 ? "−" : ""}${Math.abs(Math.round(left))}`}
        </Text>
        <Text {...DYNAMIC_TYPE} style={[ss.tileSub, NUM, { fontFamily: mono(lang) }]}>µg</Text>
      </View>
    </View>
  );
}

const PROFILES = [
  { k: "general", labelKey: "profileGeneral" },
  { k: "sensitive", labelKey: "profileSensitive" },
  { k: "child", labelKey: "profileChild" },
] as const;

function BudgetCard({ totalUg, profile, lang, onProfile }: {
  totalUg: number; profile: ShellSettings["profile"]; lang: Lang;
  onProfile: (p: ShellSettings["profile"]) => void;
}) {
  const budget = PROFILE_BUDGET_UG[profile];
  const over = totalUg - budget;
  const frac = Math.max(0, Math.min(1, totalUg / budget));
  return (
    <View style={ss.card}>
      <Text {...DYNAMIC_TYPE} style={[ss.cardEyebrow, { fontFamily: mono(lang, "med") }]}>
        {t("budgetTitle", lang)}
      </Text>
      <View style={ss.budgetBar}>
        <View style={[ss.budgetFill, {
          width: `${frac * 100}%`,
          backgroundColor: over > 0 ? V2T.breath2 : V2T.accent,
        }]} />
      </View>
      <Text {...DYNAMIC_TYPE} style={[ss.budgetLine, NUM, { fontFamily: mono(lang) }]}>
        {over > 0
          ? t("budgetOver", lang, { o: Math.round(over), p: t(`profile${profile[0].toUpperCase()}${profile.slice(1)}` as never, lang) })
          : t("budgetWithin", lang, { r: Math.round(-over), b: budget })}
      </Text>
      <View style={ss.profileRow}>
        {PROFILES.map((p) => {
          const sel = profile === p.k;
          return (
            <Pressable key={p.k} onPress={() => { tap(); onProfile(p.k); }}
              accessibilityRole="button" accessibilityLabel={t(p.labelKey, lang)}
              style={[ss.opt, sel && ss.optSel]}>
              <Text {...DYNAMIC_TYPE}
                style={[ss.optTxt, { fontFamily: fam(lang, "reg") }, sel && ss.optTxtSel]}>
                {t(p.labelKey, lang)}
              </Text>
            </Pressable>
          );
        })}
      </View>
      <Text {...DYNAMIC_TYPE} style={[ss.finePrint, { fontFamily: fam(lang, "reg") }]}>
        {t("budgetProfileQ", lang)}
      </Text>
    </View>
  );
}

/* ---------------- the peek card (idle map) ---------------- */

/** The idle-map card — one glance: today µg, the week's dots, the budget
 *  bar. Tap opens the stack. An empty day says so in one line and still
 *  opens — the morning card + check-in are useful before the arc fills. */
export function DayPeek({ data, lang, onOpen }: {
  data: DayData | null; lang: Lang; onOpen: () => void;
}) {
  if (!data) return null;
  return (
    <Pressable onPress={() => { tap(); onOpen(); }}
      accessibilityRole="button" accessibilityLabel={t("peekTitle", lang)}
      style={({ pressed }) => [ss.peek, pressed && { backgroundColor: V2T.surface2 }]}>
      <View style={ss.peekTop}>
        <Text {...DYNAMIC_TYPE} style={[ss.peekEyebrow, { fontFamily: mono(lang, "med") }]}>
          {t("peekTitle", lang)}
        </Text>
        <Icon name="chevron" color={V2T.text3} size={14} />
      </View>
      {data.rec.thin ? (
        <Text {...DYNAMIC_TYPE} style={[ss.peekEmpty, { fontFamily: fam(lang, "reg") }]}>
          {t("peekEmpty", lang)}
        </Text>
      ) : (
        <View style={ss.peekRow}>
          <Text {...DYNAMIC_TYPE} style={[ss.peekNum, NUM, { fontFamily: famSerif(lang, "semi") }]}>
            ≈{Math.round(data.rec.totalUg)}
          </Text>
          <Text {...DYNAMIC_TYPE} style={[ss.peekUnit, { fontFamily: mono(lang) }]}>µg</Text>
          <View style={ss.peekDots}>
            {data.week.map((w) => (
              <View key={w.day} style={[ss.weekDot, {
                backgroundColor: w.ug > 0 ? doseDotColor(w.ug, 216) : "transparent",
                borderWidth: w.ug > 0 ? 0 : 1, borderColor: V2T.hairline,
              }]} />
            ))}
          </View>
        </View>
      )}
    </Pressable>
  );
}

/* ---------------- the screen ---------------- */

function DaySheet({ data, lang, settings, onClose, onGo, onProfile, onCheckin }: {
  data: DayData; lang: Lang; settings: ShellSettings;
  onClose: () => void; onGo: () => void;
  onProfile: (p: ShellSettings["profile"]) => void;
  onCheckin: (c: Omit<Checkin, "ts">) => void;
}) {
  const insets = useSafeAreaInsets();
  const budget = PROFILE_BUDGET_UG[settings.profile];
  return (
    <View style={[ss.root, { marginTop: insets.top + 8 }]}>
      <View style={ss.bar}>
        <Pressable onPress={() => { tick(); onClose(); }} hitSlop={10}
          accessibilityRole="button" accessibilityLabel={t("a11yBack", lang)}
          style={ss.barBtn}>
          <Svg width={22} height={22} viewBox="0 0 24 24">
            <Path d="M14.5 5.5 8 12l6.5 6.5" stroke={V2T.text2} strokeWidth={2}
              fill="none" strokeLinecap="round" strokeLinejoin="round" />
          </Svg>
        </Pressable>
        <Text {...DYNAMIC_TYPE} style={[ss.title, { fontFamily: famSerif(lang, "semi") }]}>
          {t("dayTitle", lang)}
        </Text>
      </View>
      <ScrollView style={ss.flex}
        contentContainerStyle={[ss.content, { paddingBottom: insets.bottom + 24 }]}>
        <MorningCard curve={data.curve} outside={data.outside} lang={lang} />
        <DayCard rec={data.rec} budgetUg={budget} lang={lang} />
        <LensCard checkin={data.checkin} lens={data.lens} lang={lang} onCheckin={onCheckin} />
        <TileRow data={data} budgetUg={budget} lang={lang} />
        <BudgetCard totalUg={data.rec.totalUg} profile={settings.profile} lang={lang} onProfile={onProfile} />
        {/* the journey stays one tap away — routing is a tool inside the day */}
        <Pressable onPress={() => { tap(); onGo(); }}
          accessibilityRole="button" accessibilityLabel={t("goLabel", lang)}
          style={({ pressed }) => [ss.goRow, pressed && { backgroundColor: V2T.surface2 }]}>
          <Icon name="navigate" color={V2T.accent} size={16} />
          <Text {...DYNAMIC_TYPE} style={[ss.goTxt, { fontFamily: fam(lang, "med") }]}>
            {t("goLabel", lang)}
          </Text>
          <Icon name="chevron" color={V2T.text3} size={14} />
        </Pressable>
      </ScrollView>
    </View>
  );
}

export function DayScreen({ visible, data, lang, settings, onClose, onGo, onProfile, onCheckin }: {
  visible: boolean;
  data: DayData | null;
  lang: Lang;
  settings: ShellSettings;
  onClose: () => void;
  onGo: () => void;
  onProfile: (p: ShellSettings["profile"]) => void;
  onCheckin: (c: Omit<Checkin, "ts">) => void;
}) {
  /* hardware back closes the sheet — no Modal, no onRequestClose */
  useEffect(() => {
    if (!visible) return;
    const sub = BackHandler.addEventListener("hardwareBackPress", () => { onClose(); return true; });
    return () => sub.remove();
  }, [visible, onClose]);

  /* plain absolute overlay + JS-driver enter spring — the proven-safe
     pattern (RN Modal's native present/dismiss segfaults this stack) */
  const [enter] = useState(() => new Animated.Value(0));
  const [enterTy] = useState(() => enter.interpolate({ inputRange: [0, 1], outputRange: [36, 0] }));
  const reduceMotion = useReduceMotion();
  useEffect(() => {
    if (!visible) return;
    enter.setValue(reduceMotion ? 1 : 0);
    if (!reduceMotion) {
      Animated.spring(enter, { toValue: 1, damping: 24, stiffness: 240, useNativeDriver: false }).start();
    }
  }, [visible, enter, reduceMotion]);

  if (!visible) return null;
  return (
    <View style={ss.backdrop}>
      <StatusBar style="dark" />
      <Animated.View style={{ flex: 1, opacity: enter, transform: [{ translateY: enterTy }] }}>
        {data ? (
          <DaySheet data={data} lang={lang} settings={settings}
            onClose={onClose} onGo={onGo} onProfile={onProfile} onCheckin={onCheckin} />
        ) : (
          <View style={[ss.root, { paddingTop: 60 }]}>
            <Text {...DYNAMIC_TYPE} style={[ss.emptyLine, { fontFamily: fam(lang, "reg"), marginHorizontal: 18 }]}>
              {t("cityLoading", lang)}
            </Text>
          </View>
        )}
      </Animated.View>
    </View>
  );
}

export default DayScreen;

export { BandDot, doseDotColor, fmtHr };

const ss = StyleSheet.create({
  backdrop: { ...StyleSheet.absoluteFill, backgroundColor: V2T.scrim },
  root: {
    flex: 1,
    backgroundColor: V2T.glassDeep,
    borderTopLeftRadius: V2Radius.sheet,
    borderTopRightRadius: V2Radius.sheet,
    borderTopWidth: 1,
    borderColor: V2T.glassEdge,
    overflow: "hidden",
  },
  bar: {
    flexDirection: "row", alignItems: "center", height: 52,
    paddingHorizontal: 12,
    borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: V2T.glassLine,
  },
  barBtn: { padding: 6, marginRight: 8 },
  title: { color: V2T.text, fontSize: V2Type.title },
  flex: { flex: 1 },
  content: { paddingHorizontal: 14, paddingTop: 12, gap: 12 },

  card: {
    backgroundColor: V2T.surface,
    borderWidth: 1, borderColor: V2T.hairline,
    borderRadius: V2Radius.card,
    paddingHorizontal: 16, paddingTop: 14, paddingBottom: 14,
  },
  cardEyebrow: {
    color: V2T.text3, fontSize: V2Type.micro,
    letterSpacing: 1.8, textTransform: "uppercase", marginBottom: 10,
  },
  emptyLine: { color: V2T.text4, fontSize: V2Type.secondary, lineHeight: 21 },
  finePrint: { color: V2T.text3, fontSize: V2Type.micro, marginTop: 10 },

  /* morning card */
  sparkLabels: { flexDirection: "row", justifyContent: "space-between", marginTop: 2 },
  sparkHr: { color: V2T.text4, fontSize: 9, flex: 1, textAlign: "center" },
  mRow: { flexDirection: "row", alignItems: "center", gap: 8, marginTop: 6 },
  mLine: { color: V2T.text2, fontSize: V2Type.secondary },
  moveLine: { color: V2T.accentInk, fontSize: V2Type.secondary, marginTop: 8 },

  /* day arc */
  heroRow: { flexDirection: "row", alignItems: "flex-end", gap: 10 },
  heroNum: { fontSize: V2Type.display, lineHeight: 34 },
  heroMeta: { flex: 1, paddingBottom: 2 },
  heroUnit: { color: V2T.text2, fontSize: V2Type.label },
  heroSub: { color: V2T.text3, fontSize: V2Type.micro, marginTop: 2 },
  arcWrap: { flexDirection: "row", alignItems: "flex-end", marginTop: 12 },
  arcCol: { flex: 1, alignItems: "center" },
  arcBarCol: { height: 52, alignItems: "center", justifyContent: "flex-end" },
  arcDot: { width: 5, height: 5, borderRadius: 2.5, marginBottom: 3 },
  arcBar: { width: 2 },
  arcTrip: {
    width: 5, height: 5, marginTop: 3, borderRadius: 1,
    backgroundColor: V2T.accent,
  },
  arcHr: { color: V2T.text4, fontSize: 9, marginTop: 4, height: 12 },
  partsEyebrow: {
    color: V2T.text3, fontSize: V2Type.micro, letterSpacing: 1.8,
    textTransform: "uppercase", marginTop: 14, marginBottom: 4,
  },
  partRow: { flexDirection: "row", alignItems: "center", gap: 8, paddingVertical: 4 },
  partDot: { width: 6, height: 6, borderRadius: 3 },
  partLabel: { color: V2T.text2, fontSize: V2Type.label, flex: 1 },
  partUg: { color: V2T.text, fontSize: V2Type.label },

  /* lens */
  lensSub: { color: V2T.text3, fontSize: V2Type.label, marginBottom: 10 },
  facetRow: {
    flexDirection: "row", alignItems: "center", justifyContent: "space-between",
    paddingVertical: 6,
  },
  facetLabel: { color: V2T.text, fontSize: V2Type.secondary },
  facetOpts: { flexDirection: "row", gap: 6 },
  opt: {
    paddingHorizontal: 10, paddingVertical: 6,
    borderRadius: V2Radius.row, borderWidth: 1, borderColor: V2T.hairline,
    backgroundColor: V2T.surface,
  },
  optSel: { backgroundColor: V2T.accentWash, borderColor: V2T.accent },
  optTxt: { color: V2T.text2, fontSize: V2Type.label },
  optTxtSel: { color: V2T.accentInk },
  verdict: { color: V2T.text2, fontSize: V2Type.label, marginTop: 12 },

  /* tiles — the admin tile language: mono micro label + serif number */
  tiles: { flexDirection: "row", gap: 10 },
  tile: {
    flex: 1, backgroundColor: V2T.surface,
    borderWidth: 1, borderColor: V2T.hairline, borderRadius: V2Radius.card,
    paddingHorizontal: 12, paddingTop: 12, paddingBottom: 10,
  },
  tileLbl: {
    color: V2T.text3, fontSize: 9, letterSpacing: 1.6,
    textTransform: "uppercase", marginBottom: 6,
  },
  tileNum: { color: V2T.text, fontSize: V2Type.display, lineHeight: 32 },
  tileSub: { color: V2T.text3, fontSize: V2Type.micro, marginTop: 2 },
  weekRow: { flexDirection: "row", gap: 5, alignItems: "center", height: 32 },
  weekDot: { width: 8, height: 8, borderRadius: 4 },

  /* budget */
  budgetBar: {
    height: 3, borderRadius: 2, backgroundColor: V2T.surface2,
    overflow: "hidden", marginBottom: 8,
  },
  budgetFill: { height: 3, borderRadius: 2 },
  budgetLine: { color: V2T.text2, fontSize: V2Type.secondary },
  profileRow: { flexDirection: "row", gap: 6, marginTop: 12 },

  /* go row */
  goRow: {
    flexDirection: "row", alignItems: "center", gap: 10,
    backgroundColor: V2T.surface, borderWidth: 1, borderColor: V2T.hairline,
    borderRadius: V2Radius.card, paddingHorizontal: 16, paddingVertical: 14,
  },
  goTxt: { color: V2T.accentInk, fontSize: V2Type.secondary, flex: 1 },

  /* the peek card on the idle map — the parent wrapper positions it */
  peek: {
    marginHorizontal: 16,
    backgroundColor: V2T.glassDeep,
    borderWidth: 1, borderColor: V2T.hairline,
    borderRadius: V2Radius.card,
    paddingHorizontal: 14, paddingTop: 10, paddingBottom: 12,
  },
  peekTop: { flexDirection: "row", alignItems: "center", justifyContent: "space-between" },
  peekEyebrow: {
    color: V2T.text3, fontSize: V2Type.micro, letterSpacing: 1.8,
    textTransform: "uppercase",
  },
  peekEmpty: { color: V2T.text3, fontSize: V2Type.label, marginTop: 6 },
  peekRow: { flexDirection: "row", alignItems: "flex-end", gap: 8, marginTop: 4 },
  peekNum: { color: V2T.text, fontSize: V2Type.display, lineHeight: 32 },
  peekUnit: { color: V2T.text3, fontSize: V2Type.micro, paddingBottom: 4 },
  peekDots: { flexDirection: "row", gap: 4, flex: 1, justifyContent: "flex-end", paddingBottom: 8 },
});

