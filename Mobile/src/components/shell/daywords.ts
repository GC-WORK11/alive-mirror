/** Shared day-words for the forecast/week surfaces — extracted from
 *  HomeScreen so the week sheet (WeekSheet) and the days-ahead card can
 *  serve the same labels/captions without a screen→component import.
 *  Behaviour is identical to the inline copies they replace. */
import { freshnessTone } from "../FreshnessChip";
import {
  CLEAN_UG,
  type Outlook,
} from "../../api/outlook";
import { t, type Lang, type StringKey } from "../../i18n/strings";

/** the 'as of' line the forecast cards share: the served field's own
 *  age in the freshness chip's tone language — stale says stale, fresh
 *  states the age, unknown says nothing (a card must not imply
 *  freshness it can't show). */
export function fieldAgeLine(
  ageS: number | null | undefined,
  stale: boolean | null | undefined,
  lang: Lang,
): string | null {
  const tone = freshnessTone(ageS, stale);
  if (tone === "unknown") return null;
  const n = Math.max(0, Math.floor((ageS ?? 0) / 60));
  return tone === "stale"
    ? t("dayMorningStale", lang, { n })
    : t("howWe_fieldAge", lang, { n });
}

/* ---------------- the days ahead ---------------- */

/** Served day label ("today" | "tomorrow" | weekday) → localized key.
 *  Unknown labels pass through — a name is honest even untranslated. */
export const DAY_LABEL_KEYS: Record<string, StringKey> = {
  today: "dayLbl_today",
  tomorrow: "dayLbl_tomorrow",
  monday: "dayLbl_monday",
  tuesday: "dayLbl_tuesday",
  wednesday: "dayLbl_wednesday",
  thursday: "dayLbl_thursday",
  friday: "dayLbl_friday",
  saturday: "dayLbl_saturday",
  sunday: "dayLbl_sunday",
};
export const dayLabel = (label: string, lang: Lang): string => {
  const k = DAY_LABEL_KEYS[label.trim().toLowerCase()];
  return k ? t(k, lang) : label;
};

/** Compact the served heavy-hour labels ("21:30" hourly starts) into
 *  ranges: ["21:30","22:30","23:30"] → "21:30–00:30"; singles stay raw.
 *  A day's hours never wrap midnight, so h+1 always means the next slot. */
export function compactHours(labels: string[]): string {
  const hrs = labels
    .map((l) => (/^\d{1,2}:\d{2}/.test(l) ? { h: parseInt(l, 10), raw: l } : null))
    .filter((x): x is { h: number; raw: string } => x !== null);
  if (!hrs.length) return "";
  const out: string[] = [];
  let i = 0;
  while (i < hrs.length) {
    let j = i;
    while (j + 1 < hrs.length && hrs[j + 1].h === hrs[j].h + 1) j++;
    if (j > i) {
      const endH = `${(hrs[j].h + 1) % 24}`.padStart(2, "0");
      out.push(`${hrs[i].raw}–${endH}:${hrs[j].raw.slice(3)}`);
    } else {
      out.push(hrs[i].raw);
    }
    i = j + 1;
  }
  return out.join(", ");
}

/** The card's caption. English gets the wire line verbatim — it is already
 *  honest about partial days and flat weeks. Hindi rebuilds the same
 *  sentence from the served fields so wire English doesn't leak; anything
 *  unexpected falls back to the served text untouched. */
export function outlookCaption(o: Outlook, lang: Lang): string {
  if (!o.verdict) return "";
  if (lang === "en") return o.verdict;
  if (o.best_day) {
    const b = o.best_day;
    const w = t(b.pm25_mid > CLEAN_UG ? "dayOutlookLeastBad" : "dayOutlookCleanest", lang);
    const s = t("dayOutlookVerdict", lang, {
      d: dayLabel(b.label, lang), w,
      c: Math.round(b.pm25_mid),
      g: Math.round(b.pm25_mid - b.delta_vs_mean),
    });
    return b.n_hours < 12 ? s + t("dayOutlookVerdictPartial", lang, { n: b.n_hours }) : s;
  }
  if (o.flat && o.days.length) {
    const mean = Math.round(o.days.reduce((s, d) => s + d.pm25_mid, 0) / o.days.length);
    return t("dayOutlookFlatVerdict", lang, { c: mean, n: o.days.length });
  }
  return o.verdict;
}
