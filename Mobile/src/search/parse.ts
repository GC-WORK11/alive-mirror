// Query understanding for the search tiers — how people actually type
// Delhi addresses: "gali no 4 ashok nagar shahdara", "a block nand nagri",
// "bakery ke paas hanuman mandir", "h no 123 sector 15". Raw keyboard text
// becomes a structured ask: which tokens name the place, which mark a unit
// (gali/block/pocket/sector/phase + its letter-or-number), which are pure
// filler ("no", "number", "wala"), and whether a near-/context phrase pins
// the answer to another place. Used by t0.ts (offline tier) so the bundled
// gazetteer answers the same phrasing the server tiers do.
//
// Honesty rule: parsing only RE-READS the query — it never invents a place.
// What remains unmatched stays unmatched and the caller shows the honest
// miss state.

import { normalize, fold } from "./text";

export type UnitSpec = {
  struct: string;   // gali | block | pocket | sector | phase | part | khand | enclave | house | flat | plot
  value: string;    // the letter/number: 'a', '4', 'a5', '12'
};

export type Parsed = {
  raw: string;
  nq: string;              // normalize(raw) — full normalized query
  toks: string[];          // place-name tokens (fillers + units + near-part removed)
  folds: string[];         // fold() of each place token — phonetic matching
  units: UnitSpec[];       // extracted designators, in query order
  kind: string | null;     // one kind word the query carries, if any ('bakery')
  near: string[] | null;   // "X near Y" — Y's tokens (the context anchor)
};

/** words that never disambiguate a place — fillers Delhi users actually
 * type around a name. Stripped before matching, never required of rows. */
const FILLER = new Set([
  "no", "num", "number", "nbr", "hno", "h", "house", "flat", "plot",
  "kothi", "unit", "gf", "ff", "floor", "wala", "wale", "wali",
  "in", "at", "of", "the", "a", "an", "for", "to", "from", "by",
  "ke", "ki", "ka", "se", "me", "mein", "pe", "par", "andar",
  "bahar", "main", "mein", "wala", "something", "type", "kuch",
]);

/** near-words that split "X near Y" — the trailing side is the anchor the
 * user is orienting by. Mirrors _COMPOUND_STOP on the server. */
const NEAR = new Set([
  "near", "nearer", "paas", "pas", "nazdeek", "najdeek", "najdik",
  "kareeb", "karib", "qareeb", "saamne", "samne", "sammne", "peeche",
  "piche", "aage", "age", "opposite", "opp", "behind", "front",
  "around", "close", "beside", "next", "baju", "bagal",
]);

/** unit designators — 'gali 4', 'block a', 'pocket b', 'sector 62',
 * 'phase 2'. Mirrors _SUBPLACE_STRUCT on the server. A struct word
 * consumes a following (or preceding) letter/number as the unit value. */
const STRUCT = new Set([
  "gali", "gully", "lane", "block", "pocket", "poket", "pkt",
  "sector", "phase", "part", "khand", "enclave", "extension",
  "khasra", "kh", "ward", "zone", "market",
]);

/** unit values look like '4', 'a', 'a5', '12b', 'iv' — letter(s),
 * digit(s), or the common letter+digit house-tag form. */
const UNIT_VAL = /^[a-z]?\d{1,4}[a-z]?$|^[a-z]{1,2}$|^([ivx]{1,4})$/;

const isUnitValue = (t: string) => UNIT_VAL.test(t) && !FILLER.has(t) && !STRUCT.has(t);

/** kind words → a corpus-category regex for the offline kind-fallback
 * ('bakery near X' asks for A bakery — the category, honestly labelled).
 * A compact subset of server _KIND_PHRASES keyed for single tokens. */
export const KIND_RE: [RegExp, string][] = [
  [/^(bakery|bakeries|bekri|confectionery|mithai|sweet|sweets|pastry)$/, "bakery|pastry|confectionery|sweets|sweets_shop|sweet|namkeen"],
  [/^(atm)$/, "atm"],
  [/^(bank|banks)$/, "bank|bank_or_credit_union"],
  [/^(hospital|aspatal|hospitals)$/, "hospital|specialty_hospital|nursing_home|university_hospital"],
  [/^(clinic|dispensary|policlinic|polyclinic)$/, "clinic|dental_clinic|outpatient_care_facility|centre|healthcare"],
  [/^(pharmacy|chemist|medicine|medicals?)$/, "pharmacy|chemist|medical_supply"],
  [/^(school|schools)$/, "school|prep_school|kindergarten|educational_institution"],
  [/^(college|colleges)$/, "college|college_university|educational_institution"],
  [/^(university|universities)$/, "university|college_university"],
  [/^(petrol|fuel|diesel|cng)$/, "fuel|charging_station"],
  [/^(temple|mandir|mandeer)$/, "temple|hindu_place_of_worship|place_of_worship|shrine"],
  [/^(mosque|masjid|dargah)$/, "mosque|muslim_place_of_worship|place_of_worship"],
  [/^(church)$/, "church|christian_place_of_worship|place_of_worship"],
  [/^(gurudwara|gurdwara)$/, "gurudwara|sikh_place_of_worship|place_of_worship"],
  [/^(park|parks|parkk)$/, "park|garden|playground|recreation_ground"],
  [/^(restaurant|dhaba|restaurent|resturant|hotel.*khana)$/, "restaurant|fast_food|food_court|canteen"],
  [/^(hotel|hotels|guesthouse)$/, "hotel|guest_house|hostel|motel|resort"],
  [/^(hostel|hostels|pg)$/, "hostel|dormitory|student_accommodation"],
  [/^(cafe|cafeteria)$/, "cafe|coffee|internet_cafe"],
  [/^(cinema|movie|multiplex|theatre|theater)$/, "cinema|theatre"],
  [/^(mall|malls)$/, "shopping_mall|mall|shopping_centre|department_store"],
  [/^(market|mandi|bazaar|bazar|mkt)$/, "marketplace|market|greengrocer|convenience"],
  [/^(shop|shops|store|stores|dukan)$/, "shop|convenience|supermarket|store|variety_store|general|retail"],
  [/^(grocery|kirana|kiryana)$/, "supermarket|convenience|grocery|greengrocer|general"],
  [/^(salon|parlour|parlor|barber|nai)$/, "hairdresser|beauty"],
  [/^(gym|gymnasium|akha?da)$/, "gym|fitness_centre|sports_centre"],
  [/^(metro|subway)$/, "metro|subway|subway_entrance"],
  [/^(station|railway|rail)$/, "station|train_station|rail|halt"],
  [/^(bus)$/, "bus_stop|bus_station|platform|stop"],
  [/^(police|thana|thanna)$/, "police|policeoutpost"],
  [/^(parking|parkings)$/, "parking|parking_space|parking_entrance"],
  [/^(post|postoffice)$/, "post_office|post_depot|post_box"],
  [/^(library)$/, "library|public_bookcase"],
  [/^(stadium)$/, "stadium_arena|stadium|sports_centre"],
  [/^(bar|pub|theka|thekka)$/, "bar|pub|nightclub|lounge|alcohol|wine"],
  [/^(cemetery|graveyard|kabristan|smashan|shamshan)$/, "grave_yard|cemetery|crematorium"],
  [/^(taxi|cab|autos?tand|rickshaw)$/, "taxi"],
  [/^(vet|veterinary|pashu)$/, "veterinary"],
  [/^(tailor|darzi)$/, "tailor|dressmaker"],
  [/^(electrician|bijli)$/, "electrician"],
  [/^(plumber)$/, "plumber"],
  [/^(bakery.*)$/, "bakery|pastry|confectionery"],
];

export const kindRegexFor = (tok: string): string | null => {
  for (const [re, cats] of KIND_RE) if (re.test(tok)) return cats;
  return null;
};

/** Parse raw keyboard text into a structured ask. Order of extraction:
 * near-split → filler-strip → unit extraction → kind detection → the
 * residue is the anchor name. */
export function parseQuery(raw: string): Parsed | null {
  const nq = normalize(raw);
  if (!nq) return null;
  const all = nq.split(" ");

  /* 1 — "X near Y": split at the LAST near-word so 'X near Y' anchors on
     Y even when X is a full name phrase. 'the tea shop near neelam
     chowk' → x=[tea shop] y=[neelam chowk]. A leading 'near' with
     nothing after stays part of the name ('near nangloi' is a name
     query, not a compound). */
  let near: string[] | null = null;
  let head = all;
  for (let i = all.length - 1; i > 0; i--) {
    if (NEAR.has(all[i]) && i < all.length - 1) {
      const y = all.slice(i + 1).filter((t) => !FILLER.has(t) && !NEAR.has(t));
      if (y.length) {
        near = y;
        head = all.slice(0, i);
      }
      break;
    }
  }

  /* 2 — fillers out of the head side, EXCEPT a single-letter 'a'/'an'
     sitting next to a designator: 'a block' means the unit letter A —
     'nandanagri a block pocket something' is block-A inside Nand Nagri. */
  const nextToStruct = (i: number, arr: string[]) =>
    (i > 0 && STRUCT.has(arr[i - 1])) || (i < arr.length - 1 && STRUCT.has(arr[i + 1]));
  const kept = head.filter((t, i) => {
    if (NEAR.has(t)) return false;
    if ((t === "a" || t === "an") && nextToStruct(i, head)) return true;
    return !FILLER.has(t);
  });

  /* 3 — units: 'gali 4'/'gali no 4' (filler already gone → 'gali 4'),
     'a block', '4 gali'. Consume the value token beside the struct.
     A bare struct with no value is still a designator, never name text —
     it leaves the token list too (only the unit ask knows it was there). */
  const units: UnitSpec[] = [];
  const consumed = new Set<number>();
  for (let i = 0; i < kept.length; i++) {
    const t = kept[i];
    if (!STRUCT.has(t)) continue;
    let took = false;
    // prefer the value AFTER the struct ('gali 4'), else BEFORE ('4 gali')
    for (const j of [i + 1, i - 1]) {
      if (j < 0 || j >= kept.length || consumed.has(j) || STRUCT.has(kept[j])) continue;
      // 'a'/'an' reached here only because they survived nextToStruct —
      // they ARE the unit letter ('a block' = block A)
      if (isUnitValue(kept[j]) || kept[j] === "a" || kept[j] === "an") {
        units.push({ struct: t, value: kept[j] });
        consumed.add(i);
        consumed.add(j);
        took = true;
        break;
      }
    }
    if (!took) consumed.add(i);   // bare struct — designator, not name text
  }
  const toks = kept.filter((_, i) => !consumed.has(i));

  /* 4 — a lone kind word among the anchor tokens. It stays IN toks (a
     'bakery' place name is also honest), the caller falls back to a
     kind-scan only when name matching fails. */
  const kind = toks.find((t) => kindRegexFor(t)) ?? null;

  if (!toks.length && !units.length && !near) return null;
  return {
    raw,
    nq,
    toks,
    folds: toks.map(fold),
    units,
    kind,
    near,
  };
}
