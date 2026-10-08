/** Explore-intent detection for the search sheet — 'stays' and 'when to
 *  go out' as real query paths. parseQuery still owns the grammar; this
 *  only classifies the parsed ask and pulls the anchor's name text out
 *  of it. A miss returns null — no intent row, nothing implied. */
import type { Parsed } from "./parse";
import type { ExploreMode } from "../api/explore";

export type ExploreIntent = {
  mode: ExploreMode;
  /** place text the ask anchors to — 'karol bagh' in 'hotels near
   *  karol bagh', 'lodhi garden' in 'play football lodhi garden'.
   *  null = the ask means "near me". */
  nearQuery: string | null;
};

/** tokens that mean 'a roof to sleep under' — superset of the KIND_RE
 *  lodging entries, because people type 'stay', 'pg', 'rooms' too */
const STAY_TOKS = new Set([
  "hotel", "hotels", "stay", "stays", "staying", "hostel", "hostels",
  "pg", "guesthouse", "guest", "lodge", "lodging", "lodgings",
  "resort", "resorts", "dharamshala", "dharamsala", "accommodation",
  "accomodation", "room", "rooms", "inn", "motel",
]);

/** tokens that mean 'time outside doing something' — the play ask.
 *  'park'/'stadium' deliberately excluded: those words name places,
 *  and a bare 'lodhi garden' or 'park' ask is a place search, not a
 *  'when' question. */
const PLAY_TOKS = new Set([
  "play", "playing", "playtime", "played", "plays",
  "football", "soccer", "cricket", "badminton", "basketball", "tennis",
  "hockey", "volleyball", "kabaddi", "skating", "skate",
  "khel", "khelna", "khelne", "khelo", "khail",
  "jog", "jogging", "exercise", "exercising", "workout", "yoga",
  "swimming", "swim", "cycling", "cycle", "badm",
]);

/** 'walk'/'run'/'out' only count with a when-word or activity context —
 *  'run' alone is a verb that lives inside too many asks. */
const PLAY_PHRASE =
  /when.*(play|go out|out|run|jog|walk|exercise|cycle|swim)|best time|cleanest|lightest|saaf|kab (saaf|khel|jaaye|jaye)|kya.*(khel|bahar|nikle)|bacche.*(khel|bahar)/i;

/** question/time words that are never an anchor name — stripping them
 *  keeps 'when should kids play' from becoming the place
 *  'when should kids'. */
const STOP_TOKS = new Set([
  "when", "what", "should", "shall", "can", "could", "is", "are", "it",
  "kids", "kid", "child", "children", "bachcha", "baccha", "bacche",
  "bachhe", "log", "hum", "we", "i", "me", "my", "time", "best",
  "good", "safe", "safest", "clean", "outside", "out", "outdoors",
  "today", "tomorrow", "tonight", "kal", "aaj", "abhi", "subah",
  "morning", "evening", "shaam", "raat", "night", "day", "din",
  "now", "later", "weekend", "week", "delhi", "ncr",
]);

export function exploreIntent(parsed: Parsed | null): ExploreIntent | null {
  if (!parsed) return null;
  const { toks, near, nq, kind } = parsed;

  const stayHit =
    (kind != null && STAY_TOKS.has(kind)) || toks.some((t) => STAY_TOKS.has(t));
  const playHit =
    PLAY_PHRASE.test(nq) || toks.some((t) => PLAY_TOKS.has(t));
  const mode: ExploreMode | null = stayHit ? "stays" : playHit ? "playtime" : null;
  if (!mode) return null;

  /* anchor: the near-part always wins ('hotels near karol bagh' →
     karol bagh); else the head tokens minus trigger words and question
     words. Whatever survives is the place text — resolved by the
     server's own near= engine, never by a client guess. */
  const anchorToks =
    near ??
    toks.filter((t) => !STAY_TOKS.has(t) && !PLAY_TOKS.has(t) &&
                       !STOP_TOKS.has(t) && t !== kind);
  const nearQuery = anchorToks.length ? anchorToks.join(" ") : null;
  return { mode, nearQuery };
}

/* ── the air ask ────────────────────────────────────────────────────────
 * 'air around me' / 'air here' / 'aqi' / 'pollution' (+ the romanized and
 * Devanagari equivalents) is not a place search at all — it asks for the
 * field itself. airIntent only re-reads the ask: a hit lets the shell
 * land the user on the air-map surface; nothing here invents a place.
 * A miss returns null and the place tiers answer as usual. */
export type AirIntent = {
  /** place text the ask anchors to — 'karol bagh' in 'air near karol
   *  bagh', 'lodhi road' in 'pollution lodhi road'. null = 'around me':
   *  the anchor is a real fix, never a made-up point. */
  nearQuery: string | null;
};

/** tokens that only ever mean air — one alone is the whole ask, and any
 *  leftover tokens are the anchor ('aqi karol bagh' → air near karol
 *  bagh). 'pm' alone stays OUT ('pm modi' is a name ask); the numeric
 *  forms pm25/pm2.5 (normalize() splits the dot → 'pm2 5') are in. */
const AIR_TOKS = new Set([
  "aqi", "aqhi", "aod", "usqi", "airindex", "airquality",
  "pm25", "pm2", "pm2p5", "pm10",
  "pollution", "polluted", "pollutant", "pollutants",
  "smog", "smoggy", "haze", "hazy",
  "dhundh", "dhund", "dhua", "dhuan", "dhuaan",
  "pradushan", "pradusahan", "pradooshan", "pradushit", "pradusit",
  "vayugunvatta",
]);

/** the ambiguous air words — 'air'/'hawa'/'vayu' name things too ('air
 *  india', 'hawa mahal'), so they only count inside an air-phrased ask:
 *  every remaining head token must be air or context, or the ask must
 *  carry an air word up front with a real place phrase trailing
 *  ('air karol bagh' → air AT karol bagh). */
const AIR_WORD = new Set([
  "air", "aer", "eyar", "hawa", "hava", "hva", "vayu", "vaayu", "wayu",
]);

/** ask-words that never anchor — question/context around the air ask;
 *  what survives outside them is the place text. */
const AIR_STOP = new Set([
  "around", "me", "my", "mine", "here", "there", "near", "quality",
  "index", "now", "today", "tonight", "tomorrow", "yesterday",
  "outside", "inside", "outdoors", "indoors", "delhi", "ncr",
  "it", "is", "the", "how", "hows", "what", "whats", "tell", "check",
  "show", "about", "report", "status", "level", "levels", "current",
  "currently", "rate", "rating",
  "kaisi", "kaisa", "kaise", "kya", "kyaa", "kiya", "hai", "hain", "he",
  "hin", "ki", "ke", "ka", "yahan", "yaha", "wahan", "waha", "idhar",
  "udhar", "aaj", "abhi", "ab", "kal", "subah", "savere", "shaam",
  "raat", "din", "saaf", "saf", "kharab", "kharaab", "achhi", "achha",
  "acchi", "accha", "buri", "bura", "gandi", "ganda", "bekar", "theek",
  "thik", "best", "clean", "cleanest", "worst", "dirty",
]);

/** trailing places where 'air X' is a NAME ask, not air — 'air india',
 *  'air force station', 'air asia' stay with the place tiers. */
const AIR_BLOCK = new Set([
  "india", "indian", "airlines", "airline", "force", "asia", "pacific",
  "express", "port", "airport", "field", "airfield", "canada", "arabia",
  "france", "china", "japan", "zealand", "bnb",
]);

/** Devanagari asks — normalize() strips non-Latin before tokenizing, so
 *  the raw text is the only honest place to see them. */
const AIR_DEVANAGARI =
  /हवा|वायु|प्रदूष|धुंध|धुँध|एयर|एअर|पीएम|धुआँ|धुआ|स्मॉग|कोहरा/;

export function airIntent(raw: string, parsed: Parsed | null): AirIntent | null {
  const devaHit = AIR_DEVANAGARI.test(raw);
  /* parsed==null → every Latin token stripped or nothing to parse; a
     Devanagari air ask still counts (the ask is air, the anchor is 'me') */
  if (!parsed) return devaHit ? { nearQuery: null } : null;
  const { toks, near } = parsed;
  const isAirTok = (t: string) => AIR_TOKS.has(t) || AIR_WORD.has(t);
  const anchorToks = (arr: string[]) =>
    arr.filter((t) => !isAirTok(t) && !AIR_STOP.has(t) && !/^\d+$/.test(t));

  /* hard: an unambiguous air token anywhere — leftover head tokens or the
     near-side name the anchor ('aqi karol bagh', 'pollution lodhi road',
     'smog near anand vihar'). A Devanagari air word in the raw counts the
     same way (its Latin neighbours can still anchor: 'प्रदूषण karol bagh'). */
  const hard = devaHit || toks.some((t) => AIR_TOKS.has(t));
  if (hard) {
    const anch = anchorToks(near ?? toks);
    return { nearQuery: anch.length ? anch.join(" ") : null };
  }

  /* soft phrased: everything left is air/context ('air around me' →
     toks=['air']; 'the air' → ['air']; 'hawa kaisi hai' → all context) —
     and at least one real air word. The near-side anchors it. */
  if (
    toks.length > 0 &&
    toks.every((t) => isAirTok(t) || AIR_STOP.has(t)) &&
    toks.some((t) => isAirTok(t))
  ) {
    const anch = near ? anchorToks(near) : [];
    return { nearQuery: anch.length ? anch.join(" ") : null };
  }

  /* soft anchored: 'air X' where X is a place phrase not on the
     name-block list ('air karol bagh' → air AT karol bagh) — only the
     latin head earns it: 'hawa X' is a name ask as often as an air ask
     ('hawa mahal'), so the hawa/vayu family needs the fully-phrased
     branch or a near= to count. */
  if (
    toks.length > 1 &&
    (toks[0] === "air" || toks[0] === "aer" || toks[0] === "eyar") &&
    toks.slice(1).every((t) => !isAirTok(t) && !AIR_STOP.has(t)) &&
    !toks.slice(1).some((t) => AIR_BLOCK.has(t) || /^\d+$/.test(t))
  ) {
    return { nearQuery: toks.slice(1).join(" ") };
  }

  return null;
}
