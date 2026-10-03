/** FreshnessChip — how old the air field behind the numbers is.
 *
 *  Every dose number the app shows is computed on a server-side field
 *  (airfield.FIELD) that refreshes about every 15 min and can be served
 *  from a built snapshot, a live station blend, or nothing at all.
 *  This chip is the honest surface for that: mounted next to any
 *  field-derived number so staleness is stated, never implied by
 *  silence.
 *
 *  MOUNT CONTRACT (plan screen / any field-number surface):
 *
 *    import { FreshnessChip } from "../components/FreshnessChip";
 *    import { fieldSources } from "../api/plan";
 *
 *    const f = planResult.field;                    // FieldStatus | null
 *    <FreshnessChip
 *      ageS={f?.age_s}
 *      stale={f?.stale}
 *      sources={fieldSources(f)}
 *      lang={lang}
 *    />
 *
 *  Props:
 *    ageS     seconds since the served field was fetched/built — the
 *             server's `field.age_s`. null/undefined → the "no live
 *             reading" state; the chip never guesses an age.
 *    stale    the server's own verdict (`field.stale`: age older than
 *             `stale_after_s`, 45 min). `true` always forces the stale
 *             state; `false`/absent does NOT suppress staleness — the
 *             chip's own 30-minute limit still applies.
 *    sources  provenance tokens — build them with `fieldSources(field)`
 *             from api/plan (splits the server's "+"-joined `source`
 *             string and prepends `serving`). When a non-empty list
 *             carries no station token (openaq/cpcb/station…) the chip
 *             appends the "model + satellite only" line — stations
 *             going dark is stated, not hidden. Empty/absent → no
 *             provenance claim either way.
 *    lang     i18n Lang ("en" | "hi") — REQUIRED. All copy comes from
 *             i18n/strings.ts keys that already exist in both tables
 *             (howWe_fieldAge, cityStale, cityNoField, dataFromModelOnly,
 *             minUnit); strings.ts is another lane's file, so this
 *             component adds no keys.
 *    compact  tight "{n} min" label for cramped surfaces (nav chrome,
 *             map overlays). Provenance drops off the face but the
 *             tone colour still tells the truth; the a11y label keeps it.
 *
 *  Tones (freshnessTone, exported for tests):
 *    fresh    age < 10 min                    → green dot
 *    ok       age < 30 min                    → amber dot
 *    stale    stale===true or age ≥ 30 min    → muted dot + muted text
 *    unknown  no age at all                   → muted, "no live reading"
 *
 *  The green is a *status* hue for data-age. Doc 03's "no green" rule
 *  covers dose/smoke colour (lightness = absence of colour) — freshness
 *  signalling is the exception the mission spec calls for. Stale is
 *  deliberately muted, not red: old data is information, not alarm.
 */
import React from "react";
import { StyleSheet, Text, View } from "react-native";
import { fam, NUM, V2Radius, V2T, V2Type } from "../theme";
import { t, type Lang } from "../i18n/strings";

/** <10 min served age reads as fresh. */
export const FRESH_LIMIT_S = 10 * 60;
/** ≥30 min reads as stale. The server's own `stale` flag trips at
 *  45 min (airfield.STALE_AFTER_S) — this chip is stricter on purpose:
 *  the field cadence is ~15 min, so anything past two cadences is old. */
export const STALE_LIMIT_S = 30 * 60;

export type FreshnessTone = "fresh" | "ok" | "stale" | "unknown";

/** Display tone for a field age. `stale === true` always wins (a
 *  last-known serve never reads green); otherwise the age decides. */
export function freshnessTone(
  ageS: number | null | undefined,
  stale?: boolean | null,
): FreshnessTone {
  if (stale === true) return "stale";
  if (ageS == null || !Number.isFinite(ageS)) return "unknown";
  if (ageS >= STALE_LIMIT_S) return "stale";
  if (ageS >= FRESH_LIMIT_S) return "ok";
  return "fresh";
}

/** Status-hue dot per tone. Green lives only here — a freshness signal,
 *  not a dose colour (see header note). */
const DOT: Record<FreshnessTone, string> = {
  fresh: "#4CC38A",   // soft green — legible on V2T.surface2, dark-safe
  ok: V2T.breath1,    // #F2C14E amber — same hue as the mild smoke ramp
  stale: V2T.text3,   // muted — stale data is quiet, not alarming
  unknown: V2T.text3,
};

/** A provenance token counts as "live stations" when it names a station
 *  feed — the server's source strings are "openaq-stations",
 *  "open-meteo/cams", "unavailable", "+"-joined. */
const STATION_TOKEN = /station|openaq|cpcb|aqi/i;

export function FreshnessChip({
  ageS,
  stale,
  sources,
  lang,
  compact = false,
}: {
  ageS?: number | null;
  stale?: boolean | null;
  sources?: string[] | null;
  lang: Lang;
  compact?: boolean;
}) {
  const tone = freshnessTone(ageS, stale);
  const min =
    ageS != null && Number.isFinite(ageS)
      ? Math.max(0, Math.floor(ageS / 60))
      : null;

  /* stations went dark → the provenance suffix says so (only when the
     caller handed us sources; an absent list claims nothing). */
  const stationsDark =
    !!sources?.length && !sources.some((s) => STATION_TOKEN.test(s));
  const provenance =
    !compact && stationsDark ? t("dataFromModelOnly", lang) : null;

  let label: string;
  if (compact) {
    label = min != null ? `${min} ${t("minUnit", lang)}` : "—";
  } else if (tone === "unknown") {
    label = t("cityNoField", lang);
  } else if (tone === "stale") {
    label = t("cityStale", lang);
    if (min != null) label += ` · ${min} ${t("minUnit", lang)}`;
  } else {
    label = t("howWe_fieldAge", lang, { n: min ?? 0 });
  }
  if (provenance) label += ` · ${provenance}`;

  /* the a11y label always carries the full provenance — compact faces
     drop the suffix visually but a screen reader still hears it */
  const a11y = sources?.length
    ? `${label} — ${sources.join(" + ")}`
    : label;

  return (
    <View
      style={cs.chip}
      accessible
      accessibilityRole="text"
      accessibilityLabel={a11y}
    >
      <View style={[cs.dot, { backgroundColor: DOT[tone] }]} />
      <Text
        numberOfLines={2}
        style={[
          cs.txt,
          NUM,
          {
            fontFamily: fam(lang, "reg"),
            color: tone === "stale" || tone === "unknown"
              ? V2T.text3
              : V2T.text2,
          },
        ]}
      >
        {label}
      </Text>
    </View>
  );
}

const cs = StyleSheet.create({
  chip: {
    flexDirection: "row",
    alignItems: "center",
    alignSelf: "flex-start",
    backgroundColor: V2T.surface2,
    borderRadius: V2Radius.pill,
    borderWidth: 1,
    borderColor: V2T.line,
    paddingHorizontal: 10,
    paddingVertical: 5,
    gap: 7,
  },
  dot: { width: 7, height: 7, borderRadius: 3.5 },
  txt: { fontSize: V2Type.label, flexShrink: 1 },
});
