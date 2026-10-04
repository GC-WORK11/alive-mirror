/**
 * Turn-step localisation (doc 04: plain-English cues in every UI language).
 * The /directions payload already carries the raw maneuver —
 * {type, modifier, street} — so we rebuild the sentence in the user's
 * language with the same grammar as server/v2/deps.py:_osrm_instruction.
 * English rebuilds byte-for-byte what the server sends; Hindi composes the
 * maneuver in Devanagari while road names stay as the gazetteer named
 * them. Any step missing maneuver fields falls back to the server's own
 * `instruction` — we never guess a maneuver we weren't given.
 */

import { t, type Lang } from "../i18n/strings";

export type StepLike = {
  instruction: string;
  type?: string;
  modifier?: string;
  street?: string;
};

const HI_DIRS: Record<string, string> = {
  left: "बाएँ",
  right: "दाएँ",
  straight: "सीधे",
  "sharp left": "कसकर बाएँ",
  "sharp right": "कसकर दाएँ",
  north: "उत्तर",
  south: "दक्षिण",
  east: "पूर्व",
  west: "पश्चिम",
  northeast: "उत्तर-पूर्व",
  northwest: "उत्तर-पश्चिम",
  southeast: "दक्षिण-पूर्व",
  southwest: "दक्षिण-पश्चिम",
};

/* OSRM exit ordinals — "1st"…"9th"; anything rarer ("10th", non-ascii
   spellings) drops the ordinal word and keeps the raw "Nवाँ" form. */
const HI_ORD: Record<string, string> = {
  "1st": "पहला", "2nd": "दूसरा", "3rd": "तीसरा", "4th": "चौथा",
  "5th": "पाँचवाँ", "6th": "छठा", "7th": "सातवाँ", "8th": "आठवाँ",
  "9th": "नौवाँ",
};

const dir = (mod: string, lang: Lang): string =>
  lang === "hi" ? HI_DIRS[mod] ?? mod : mod;

/** Localised maneuver sentence for one step — same output contract as
 *  the server's English `instruction` field. */
export function localizeStep(st: StepLike, lang: Lang): string {
  const t0 = st.type ?? "";
  const mod = st.modifier ?? "";
  const road = st.street ?? "";
  /* no maneuver data (older payloads, hand-built steps) → trust the
     server string; lang "en" is itself served, so rebuild only for hi */
  if (lang !== "hi" || (!t0 && !mod)) return st.instruction;
  const onto = road ? t("navStep_onto", lang, { r: road }) : "";

  if (mod === "uturn") return t("navStep_uturn", lang) + onto;
  if (t0 === "depart") {
    return mod && road
      ? t("navStep_headDir", lang, { d: dir(mod, lang), r: road })
      : t("navStep_headOut", lang) + onto;
  }
  if (t0 === "arrive") return t("navStep_arrive", lang);
  if (t0 === "roundabout" || t0 === "rotary" || t0 === "roundabout turn") {
    /* the exit ordinal rides only inside the English instruction — lift
       it rather than invent one */
    const m = st.instruction.match(/take the (\w+) exit(?: onto (.+))?/i);
    const ord = m ? HI_ORD[m[1]] ?? `${m[1].replace(/\D/g, "")}वाँ` : "";
    const exRoad = m?.[2] ? t("navStep_onto", lang, { r: m[2] }) : onto;
    return ord
      ? t("navStep_roundabout", lang, { o: ord }) + exRoad
      : st.instruction;
  }
  if (t0 === "on ramp") return t("navStep_ramp", lang) + onto;
  if (t0 === "off ramp") return t("navStep_exitRamp", lang) + onto;
  if (t0 === "merge") return (road ? t("navStep_mergeOn", lang, { r: road }) : t("navStep_merge", lang));
  if (t0 === "continue") {
    return road ? t("navStep_continueOn", lang, { r: road }) : t("navStep_continueStraight", lang);
  }
  if (t0 === "fork") {
    const side = mod.replace("slight ", "");
    return side ? t("navStep_keep", lang, { s: dir(side, lang) }) + onto : t("navStep_continue", lang) + onto;
  }
  if (mod) {
    if (mod === "straight") {
      return road ? t("navStep_continueOn", lang, { r: road }) : t("navStep_continueStraight", lang);
    }
    const bare = mod.replace("slight ", "");
    return mod.startsWith("slight")
      ? t("navStep_bear", lang, { d: dir(bare, lang) }) + onto
      : t("navStep_turn", lang, { d: dir(bare, lang) }) + onto;
  }
  return road ? t("navStep_continueOn", lang, { r: road }) : t("navStep_continue", lang);
}
