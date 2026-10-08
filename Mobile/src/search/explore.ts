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
