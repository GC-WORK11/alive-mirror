// T0 — the on-device search tier (docs/plan/04 §2).
// Bundled Delhi gazetteer behind a prefix index; answers in <5 ms so the
// first suggestion paints inside a frame (<16 ms) while the server tiers
// (client.ts) stream in behind it. normalize() is shared with the
// merge/dedupe layer so every tier keys names identically.
//
// Matching stages, weakest-truth-first ordering: token-prefix →
// transliteration-fold prefix ("ashook nagar" = "ashok nagar", "ngr" =
// nagar/nagri) → fused-name skeleton ("nandanagri" = "nand nagri") →
// per-token DL fuzzy (typos). "gali no 4", "block a", "pocket b" parse
// as units inside their resolved area; "X near Y" biases X to Y's fix;
// a bare kind word ("bakery near hanuman mandir") becomes a kind-scan
// around the anchor. Everything stays honest — a miss shows nothing,
// never a fabricated place.

import { EXPANSIONS, fold, foldName, normalize } from "./text";
import { kindRegexFor, parseQuery, type Parsed } from "./parse";
import { msSinceInput } from "../startup/idle";

export { normalize } from "./text";

type Raw = { n: string; c: string; lat: number; lon: number; w: number; k: number };

export type LatLon = { lat: number; lon: number };
export type SearchTier = "t0" | "t1" | "t2" | "t3";

export type PlaceResult = {
  name: string;
  subtitle: string;          // short address or category label
  lat: number;
  lon: number;
  kind: string;              // gazetteer/server category
  outside_ncr: boolean;
  tier: SearchTier;
};

// What the shell receives from SearchScreen.onSelect.
export type SearchSelection =
  | { type: "place"; place: PlaceResult }
  | { type: "current_location" }
  | { type: "choose_on_map" };

/* Delhi NCR service bounds — THE single source. The server's canonical
   box is v2/deps.NCR_BBOX = (76.80, 28.20, 77.90, 28.95) (same as
   airfield in_service_area / tiles.py _BOUNDS / the offline pack's
   region row). This client used to carry a WIDER box (76.75–77.95 /
   28.15–28.98), so a fringe point read "in Delhi" here while the API
   said beyond_field_edge — 'outside NCR' verdicts diverged at the edges
   (component-audit hardcode hunt). Order: [minLon, minLat, maxLon,
   maxLat] — the order a bbox query param takes. */
export const NCR_BOUNDS: [number, number, number, number] = [76.8, 28.2, 77.9, 28.95];
export const inNcr = (lat: number, lon: number) =>
  lon > NCR_BOUNDS[0] && lon < NCR_BOUNDS[2] && lat > NCR_BOUNDS[1] && lat < NCR_BOUNDS[3];
export const DELHI_CENTER: LatLon = { lat: 28.6139, lon: 77.209 };

// Fast km estimate near Delhi (~28.6°N) — same constants as the rest of the
// app so distances read identically everywhere.
export const distKm = (a: LatLon, b: LatLon): number =>
  Math.hypot((a.lat - b.lat) * 110.6, (a.lon - b.lon) * 99.4);

// normalize/ABBREV/EXPANSIONS/fold live in ./text (shared with parse.ts
// and client.ts); `normalize` is re-exported above for existing callers.

// Category → short label (mirrors src/gazetteer.ts so T0 rows read the same).
const SUB: Record<string, string> = {
  locality: "Delhi", macrohood: "Delhi", neighborhood: "neighbourhood",
  neighbourhood: "neighbourhood",
  monument: "monument", historic_site: "historic site", museum: "museum",
  restaurant: "restaurant", cafe: "cafe", hotel: "hotel", hospital: "hospital",
  place_of_worship: "place of worship", hindu_temple: "temple", mosque: "mosque",
  gurudwara: "gurdwara", church: "church", shopping_mall: "mall",
  bank_or_credit_union: "bank", school: "school", college: "college",
  university: "university", park: "park", stadium: "stadium",
  metro_station: "metro station", transit_stop: "transit stop",
  train_station: "railway station", bus_station: "bus station",
  airport: "airport", movie_theater: "cinema", gym: "gym",
  police: "police", fire_station: "fire station", fuel_station: "fuel",
  landmark: "landmark", tourist_attraction: "attraction",
  // corpus emit (osm tag tops) — never let a road class or admin term
  // render raw as a subtitle
  motorway: "road", trunk: "road", primary: "road", secondary: "road",
  tertiary: "road", unclassified: "road", residential: "residential area",
  living_street: "street", pedestrian: "street", administrative: "district",
  address: "address", platform: "platform", place: "place",
  // corpus-kind cook: the gazetteer emits hundreds of raw OSM categories
  // (shop=clothes, office=company, amenity=atm...). Map the heavy ones so
  // subtitles read like Google Maps categories, not tag dumps.
  hindu_place_of_worship: "temple", muslim_place_of_worship: "mosque",
  christian_place_of_worship: "church", buddhist_place_of_worship: "buddhist temple",
  jewish_place_of_worship: "synagogue", sikh_place_of_worship: "gurdwara",
  college_university: "college", government_office: "government office",
  government: "government office", political: "political office",
  political_party: "political office", diplomatic: "embassy",
  courthouse: "court", lawyer: "lawyer", accountant: "accountant",
  insurance: "insurance", financial: "financial services",
  financial_advisor: "financial advisor", bureau_de_change: "money changer",
  money_lender: "money lender", pawnbroker: "pawn shop", gold_buyer: "gold buyer",
  atm: "ATM", bank: "bank", blood_bank: "blood bank",
  blood_donation: "blood donation", clinic: "clinic", dentist: "dentist",
  doctors: "doctor", healthcare: "clinic", specialty_hospital: "hospital",
  veterinary: "vet", veterinary_pharmacy: "vet pharmacy",
  medical_supply: "medical supplies", laboratory: "lab", pharmacy: "pharmacy",
  chemist: "chemist", optician: "optician", optometrist: "optometrist",
  physiotherapist: "physiotherapist", psychotherapist: "therapist",
  therapist: "therapist", nursing_home: "nursing home", hospice: "hospice",
  rehabilitation: "rehab centre", sample_collection: "sample collection",
  vaccination_centre: "vaccination centre", dental_clinic: "dental clinic",
  outpatient_care_facility: "clinic", station: "station", subway: "metro",
  metro: "metro", subway_entrance: "metro entrance", rail: "railway",
  railway: "railway", halt: "rail halt", stop: "stop", stop_position: "stop",
  stop_area: "stop", bus_stop: "bus stop", bus_inspector: "bus depot",
  taxi: "taxi stand", parking: "parking", bicycle_parking: "bicycle parking",
  parking_entrance: "parking entrance", car_wash: "car wash",
  car_repair: "car repair", car_parts: "car parts", car_rental: "car rental",
  car: "car dealer", automobile: "car dealer", auto_dealer: "car dealer",
  motorcycle: "motorcycle dealer", motorcycle_repair: "motorcycle repair",
  motorcycle_parking: "motorcycle parking", scooter: "scooter shop",
  bicycle: "bicycle shop", bicycle_rental: "bicycle rental",
  bicycle_repair_station: "bicycle repair", tyres: "tyre shop",
  vehicle_inspection: "vehicle inspection", charging_station: "charging station",
  fuel: "fuel", gas: "gas", weighbridge: "weighbridge",
  driver_training: "driving school", driving_school: "driving school",
  gate: "gate", lift_gate: "gate", swing_gate: "swing gate",
  city_gate: "city gate", toll_booth: "toll booth", gantry: "gantry",
  junction: "junction", entrance: "entrance", service: "road",
  footway: "path", path: "path", track: "track", steps: "steps",
  cycleway: "cycleway", corridor: "corridor", bridge: "bridge",
  street: "street", building: "building", house: "house",
  housename: "address", apartment: "apartment", apartments: "apartments",
  dormitory: "dormitory", room: "room", bed: "bed shop",
  commercial: "commercial", industrial: "industrial area",
  retail: "retail", office: "office", company: "company",
  construction: "construction site", proposed: "proposed site",
  named: "place", geonames: "place", amenity: "place", indoor: "indoor venue",
  village: "village", hamlet: "village", town: "town", city: "city",
  suburb: "suburb", district: "district", subdistrict: "subdistrict",
  tehsil: "tehsil", quarter: "quarter", sector: "sector", block: "block",
  phase: "phase", plot: "plot", city_block: "block", county: "county",
  municipality: "municipality", state: "state", estate_agent: "estate agent",
  property_management: "property management", educational_institution: "educational institute",
  education: "educational institute", institute: "institute",
  research_institute: "research institute", prep_school: "school",
  kindergarten: "school", childcare: "childcare", study_space: "study space",
  driving_range: "driving range", arts_centre: "arts centre",
  community_centre: "community centre", social_facility: "social facility",
  social_centre: "social centre", hostel: "hostel", guest_house: "guest house",
  motel: "motel", resort: "resort", camp_site: "camp site",
  caravan_site: "caravan site", student_accommodation: "student accommodation",
  fast_food: "fast food", food_court: "food court", canteen: "canteen",
  deli: "deli", bakery: "bakery", confectionery: "sweets shop",
  pastry: "pastry shop", chocolate: "chocolate shop", sweets: "sweets shop",
  sweets_shop: "sweets shop", namkeen: "namkeen shop", pickle: "pickle shop",
  dry_fruits: "dry fruits", ice_cream: "ice cream", tea: "tea shop",
  coffee: "coffee shop", juice_bar: "juice bar", dairy: "dairy",
  greengrocer: "vegetable shop", butcher: "butcher", seafood: "seafood shop",
  grocery: "grocery", convenience: "convenience store",
  supermarket: "supermarket", department_store: "department store",
  variety_store: "variety store", general: "general store",
  wholesale: "wholesale", marketplace: "market", market: "market",
  shopping_centre: "mall", mall: "mall", shop: "shop", store: "store",
  trade: "trade", kiosk: "kiosk", booth: "booth",
  clothes: "clothing shop", shoes: "shoe shop", bag: "bag shop",
  fashion_accessories: "accessories", fashion_store: "fashion store",
  fashion_and_apparel_store: "clothing shop", boutique: "boutique",
  leather: "leather shop", footwear: "shoe shop", tailor: "tailor",
  dressmaker: "dressmaker", shoemaker: "shoemaker", fabric: "fabric shop",
  carpet: "carpet shop", carpets_and_pashmina_shawls: "carpet shop",
  jewelry: "jewellery", jeweller: "jeweller", watches: "watch shop",
  watchmaker: "watchmaker", cosmetics: "cosmetics", perfumery: "perfume shop",
  beauty: "salon", hairdresser: "salon", massage: "massage",
  tattoo: "tattoo studio", hairdresser_supply: "salon supplies",
  mobile_phone: "mobile shop", mobile_phone_accessories: "mobile accessories",
  electronics: "electronics", electronics_repair: "electronics repair",
  electronic_parts: "electronics", computer: "computer shop",
  it: "IT services", telecommunication: "telecom", appliance: "appliance shop",
  hifi: "hi-fi shop", camera: "camera shop", photo: "photo studio",
  photo_studio: "photo studio", photographer: "photographer",
  photo_booth: "photo booth", frame: "frame shop", furniture: "furniture",
  interior_decoration: "interiors", interior_design: "interiors",
  houseware: "houseware", kitchen: "kitchen shop",
  bathroom_furnishing: "bathroom fittings", lighting: "lighting",
  electrical: "electrical shop", hardware: "hardware",
  hardware_home_and_garden_store: "hardware store", paint: "paint shop",
  tiles: "tiles", flooring: "flooring", curtain: "curtain shop",
  doityourself: "hardware store", metal_construction: "metal works",
  metal_works: "metal works", glaziery: "glaziery", stonemason: "stonemason",
  carpenter: "carpenter", blacksmith: "blacksmith", pottery: "pottery",
  upholstery: "upholstery", locksmith: "locksmith", key_cutter: "key cutter",
  electrician: "electrician", repair: "repair shop", workshop: "workshop",
  garage: "garage", garages: "garage", books: "bookshop",
  stationery: "stationery", newsagent: "newsagent", newspaper: "newsagent",
  gift: "gift shop", florist: "florist", art: "art", antiques: "antiques",
  handicraft: "handicrafts", craft: "craft shop", toys: "toy shop",
  baby_goods: "baby shop", music: "music shop",
  musical_instrument: "instruments", video: "video shop",
  video_games: "video games", beverages: "beverages", alcohol: "liquor shop",
  wine: "wine shop", tobacco: "tobacco shop", betel_quid: "paan shop",
  hookah: "hookah lounge", hookah_lounge: "hookah lounge",
  spices: "spice shop", nuts: "nuts shop", herbalist: "herbalist",
  nutrition_supplements: "supplements", health_food: "health food",
  organic_food: "organic shop", bar: "bar", pub: "pub",
  nightclub: "nightclub", lounge: "lounge", biergarten: "beer garden",
  events_venue: "event venue", conference_centre: "conference centre",
  convention_centre: "convention centre", auditorium: "auditorium",
  banquet_hall: "banquet hall", marquee: "marquee", theatre: "theatre",
  cinema: "cinema", amusement_park: "amusement park",
  amusement_arcade: "arcade", theme_park: "theme park", water_park: "water park",
  escape_game: "escape game", trampoline_park: "trampoline park",
  indoor_play: "indoor play", zoo: "zoo", planetarium: "planetarium",
  stadium_arena: "stadium", sports: "sports", sport: "sports",
  sports_centre: "sports centre", sports_hall: "sports hall",
  fitness_centre: "gym", fitness_station: "fitness station",
  swimming_pool: "swimming pool", swimming_area: "swimming area",
  golf_course: "golf course", pitch: "sports ground",
  recreation_ground: "recreation ground", playground: "playground",
  bleachers: "bleachers", dog_park: "dog park", skate_park: "skate park",
  arena: "arena", artwork: "artwork", gallery: "gallery",
  memorial: "memorial", statue: "statue",
  fountain: "fountain", archaeological_site: "archaeological site",
  ruins: "ruins", fort: "fort", castle: "castle", tomb: "tomb",
  temple: "temple", shrine: "shrine",
  religious: "religious site", religion: "religious site", monastery: "monastery",
  cemetery: "cemetery", crematorium: "crematorium", grave_yard: "graveyard",
  funeral_directors: "funeral services",
  embassy: "embassy", prison: "prison", military: "military",
  barracks: "barracks", guardhouse: "guardhouse", bunker: "bunker",
  local_authority: "local authority", civic: "civic office",
  ngo: "NGO", association: "association", charity: "charity",
  club: "club", cooperative: "cooperative", coworking: "coworking space",
  coworking_space: "coworking space", foundation: "foundation",
  logistics: "logistics", courier: "courier", post_office: "post office",
  post_box: "post box", post_depot: "post depot", copyshop: "photocopy shop",
  print_shop: "print shop", internet_cafe: "internet cafe",
  advertising_agency: "ad agency", travel_agency: "travel agency",
  travel_agent: "travel agency", consulting: "consultant", notary: "notary",
  tax_advisor: "tax advisor", employment_agency: "employment agency",
  event_planning: "event planning", event_organizer: "event organiser",
  graphic_design: "graphic design", signmaker: "signmaker",
  architectural_firm: "architect", architect: "architect", builder: "builder",
  ticket: "ticket counter", information: "info", lost_property: "lost property",
  left_luggage: "left luggage", luggage_locker: "lockers", toilets: "toilet",
  public_bath: "public bath", drinking_water: "drinking water",
  water_point: "water point", water_filter: "water filter",
  waste_transfer_station: "waste transfer", recycling: "recycling",
  landfill: "landfill", water_works: "water works", water_utility: "water works",
  substation: "substation", transformer: "transformer", telecom: "telecom",
  monitoring_station: "monitoring station", technical_station: "technical station",
  canal: "canal", drain: "drain", water: "water",
  stream: "stream", river: "river", farmland: "farmland", grass: "grass",
  forest: "forest", national_park: "national park", nature_reserve: "nature reserve",
  garden: "garden", garden_centre: "garden centre", plant_nursery: "plant nursery",
  shelter: "shelter", tent_house: "tent house", depot: "depot",
  warehouse: "warehouse", storage_tank: "storage tank", shed: "shed",
  pumping_station: "pumping station", wastewater_plant: "wastewater plant",
  water_tower: "water tower", water_well: "well", observatory: "observatory",
  university_hospital: "hospital", typewriter: "typewriter",
};

/** Suffix fallbacks for the gazetteer's long tail — kinds not in SUB that
 * still end in a recognisable category word. Ordered: first match wins. */
const SUFFIX_LABELS: readonly (readonly [string, string])[] = [
  ["_place_of_worship", "place of worship"], ["_subway_entrance", "metro entrance"],
  ["_guest_house", "guest house"], ["_entrance", "entrance"],
  ["_station", "station"], ["_link", "road"], ["_parking", "parking"],
  ["_school", "school"], ["_college", "college"], ["_university", "university"],
  ["_institute", "institute"], ["_clinic", "clinic"], ["_hospital", "hospital"],
  ["_pharmacy", "pharmacy"], ["_office", "office"], ["_centre", "centre"],
  ["_center", "center"], ["_hall", "hall"], ["_venue", "venue"],
  ["_auditorium", "auditorium"], ["_theatre", "theatre"], ["_theater", "theater"],
  ["_cinema", "cinema"], ["_museum", "museum"], ["_gallery", "gallery"],
  ["_library", "library"], ["_laboratory", "laboratory"],
  ["_temple", "temple"], ["_mosque", "mosque"], ["_church", "church"],
  ["_gurudwara", "gurdwara"], ["_shrine", "shrine"], ["_monastery", "monastery"],
  ["_ashram", "ashram"], ["_memorial", "memorial"], ["_monument", "monument"],
  ["_tomb", "tomb"], ["_fort", "fort"], ["_palace", "palace"],
  ["_ruins", "ruins"], ["_tower", "tower"], ["_gate", "gate"],
  ["_bridge", "bridge"], ["_flyover", "flyover"], ["_underpass", "underpass"],
  ["_tunnel", "tunnel"], ["_junction", "junction"], ["_crossing", "crossing"],
  ["_roundabout", "roundabout"], ["_interchange", "interchange"],
  ["_terminal", "terminal"], ["_depot", "depot"], ["_stop", "stop"],
  ["_stand", "stand"], ["_halt", "halt"], ["_helipad", "helipad"],
  ["_heliport", "heliport"], ["_hangar", "hangar"], ["_warehouse", "warehouse"],
  ["_storage", "storage"], ["_shed", "shed"], ["_farm", "farm"],
  ["_garden", "garden"], ["_park", "park"], ["_playground", "playground"],
  ["_pitch", "sports ground"], ["_field", "field"], ["_pool", "pool"],
  ["_court", "court"], ["_lounge", "lounge"], ["_bar", "bar"],
  ["_pub", "pub"], ["_cafe", "cafe"], ["_restaurant", "restaurant"],
  ["_bakery", "bakery"], ["_butcher", "butcher"], ["_dairy", "dairy"],
  ["_hotel", "hotel"], ["_hostel", "hostel"], ["_resort", "resort"],
  ["_motel", "motel"], ["_lodge", "lodge"], ["_camp", "camp"],
  ["_market", "market"], ["_mall", "mall"], ["_shop", "shop"],
  ["_store", "store"], ["_boutique", "boutique"], ["_kiosk", "kiosk"],
  ["_agency", "agency"], ["_rental", "rental"], ["_repair", "repair"],
  ["_studio", "studio"], ["_salon", "salon"], ["_workshop", "workshop"],
  ["_gym", "gym"], ["_spa", "spa"], ["_substation", "substation"],
  ["_toilets", "toilets"], ["_toilet", "toilet"], ["_shelter", "shelter"],
  ["_cemetery", "cemetery"], ["_graveyard", "graveyard"],
  ["_stadium", "stadium"], ["_embassy", "embassy"], ["_prison", "prison"],
  ["_pond", "pond"], ["_lake", "lake"], ["_river", "river"],
  ["_stream", "stream"], ["_canal", "canal"], ["_drain", "drain"],
  ["_ditch", "ditch"], ["_reservoir", "reservoir"], ["_wetland", "wetland"],
  ["_forest", "forest"], ["_well", "well"], ["_pump", "pump"],
  ["_tank", "tank"], ["_dam", "dam"], ["_block", "block"],
  ["_sector", "sector"], ["_colony", "colony"], ["_enclave", "enclave"],
  ["_village", "village"], ["_district", "district"], ["_suburb", "suburb"],
  ["_town", "town"], ["_city", "city"], ["_hamlet", "hamlet"],
  ["_quarter", "quarter"], ["_apartments", "apartments"], ["_flat", "flat"],
];

/** Gazetteer kind → display label. SUB exact match → suffix rule → last
 * resort the raw kind with spaces (honest — it IS what the corpus says). */
export function kindLabel(c: string): string {
  const direct = SUB[c];
  if (direct) return direct;
  for (const [suf, lab] of SUFFIX_LABELS) if (c.endsWith(suf)) return lab;
  return c.replace(/_/g, " ");
}

type Entry = {
  n: string; c: string; lat: number; lon: number; w: number; k: number;
  nrm: string; toks: string[]; ftoks: string[]; fskel: string;
  wt: number;   // rank weight — computed once at index time (boot-storm)
};

let ENTRIES: Entry[] | null = null;
let PREFIX: Map<string, number[]> | null = null;
let FPREFIX: Map<string, number[]> | null = null;  // fold-token prefixes
let FSKEL: Map<string, number[]> | null = null;    // fused-name skeleton prefixes
let AREA: Map<string, number[]> | null = null;     // area-kind rows by geo cell
let GEO: Map<string, number[]> | null = null;      // all rows by geo cell

const MAX_PREFIX = 8;   // longest indexed prefix per token
const PREFIX_CAP = 80;  // max ids kept per prefix (heaviest first)
const GEO_CELL = 0.002; // ~221 m lat / ~196 m lon at 28.6°N

/* Type ordering (owner's ranking rule): a street/address row beats a
   landmark, which beats a locality, for the same match quality — plus
   the gazetteer's own w/k importance at HALF weight (the raw table was
   worship-heavy: hindu_place_of_worship w=9 vs address w=2 buried street
   rows under temple rows for the same name).
   boot-storm lane: this gauntlet ran ~10 regex .test() calls INSIDE the
   cap() sort comparator — ~2 compares per posting id across ~3 M ids of
   capped lists meant hundreds of millions of interpreted regex evals in
   one macrotask (a ~2 min 100%-CPU storm on the iOS sim, cold-launch
   death included). The kind vocabulary is ~720 strings, so the verdict
   is memoized: each kind pays the regexes once, ever. */
const _TB = new Map<string, number>();
const typeBonus = (c: string): number => {
  const hit = _TB.get(c);
  if (hit !== undefined) return hit;
  let b = 8;    // real POI/shop/service kinds — the honest mid-tier
  if (/^(address|housenumber|housename|house|street|residential|living_street|pedestrian|tertiary|unclassified|service|secondary|primary|trunk|motorway|link|crossing|junction)$/.test(c)) b = 14;
  else if (/^(platform|stop_position|stop|bus_stop|subway_entrance|entrance|parking|parking_space|parking_entrance|gate|lift_gate|shed)$/.test(c)) b = 2;
  else if (/^(monument|landmark|tourist_attraction|memorial|statue|artwork|fort|tomb|castle|ruins|archaeological_site|attraction)$/.test(c)) b = 11;
  else if (/^(station|train_station|metro|subway|halt|rail|railway|bus_station|bus_depot|depot|terminal|terminus|isbt)$/.test(c)) b = 10;
  else if (/^(locality|neighborhood|neighbourhood|suburb|village|hamlet|district|subdistrict|quarter|macrohood|administrative|sector|block|place|town|city|county|municipality|estate|colony)$/.test(c)) b = 9;
  else if (/^(park|garden|playground|recreation_ground|pitch|dog_park|national_park|nature_reserve)$/.test(c)) b = 7;
  else if (/worship|temple|mosque|church|gurudwara|gurdwara|shrine|ashram|monastery|dargah|religious|synagogue/.test(c)) b = 5;
  else if (/^(historic_site|heritage)$/.test(c)) b = 5;
  else if (/^(building|named|amenity|geonames|office|company|commercial|industrial)$/.test(c)) b = 5;
  _TB.set(c, b);
  return b;
};

const weight = (e: Entry) => e.wt;

/* Kinds that name an AREA — they anchor "near Y" resolution and supply
   the locality half of a subtitle ("street · Shahdara"). */
const AREA_KINDS = new Set([
  "locality", "neighborhood", "neighbourhood", "suburb", "village",
  "hamlet", "district", "subdistrict", "quarter", "macrohood",
  "administrative", "sector", "block", "place", "town", "city",
  "colony", "estate",
]);

/* The corpus load + index build used to run as ONE synchronous block the
   first time search touched it — inside the sheet's mount effect. On a
   mid-range phone that's an 11 MB parse plus ~124k-entry indexing —
   seconds of dead JS thread; the sheet's JS-driven enter spring froze
   mid-slide and the owner saw "10 seconds, screen hung". Now the work
   is sliced: warm() steps through ~6k entries per macrotask at boot-idle
   (or on the CTA's press-in), so the index is almost always complete
   before the first keystroke. A query that lands mid-build still
   finishes the remainder synchronously — correctness never waits on
   the scheduler. */
let RAW: Raw[] | null = null;   // the require'd corpus, freed once built
let cursor = 0;                  // next raw row to index
let capIdx = 0;                  // next postings map to cap (tail slices)
let built = false;
let scheduled = false;
const WARM_SLICE = 6000;         // ~15-30 ms a slice on-device
/* hard wall-clock cap per slice: on a saturated rig (sim/emu boot burst)
   a 6k-row slice can run 100 ms+ — the cap stops mid-slice inside a frame
   budget so queued input always wins the next macrotask (boot-burst lane). */
const WARM_SLICE_MS = 12;
/* a touch inside this window pauses the slice loop — the user's own tap
   always lands before deferred index work resumes (priority to input). */
const INPUT_YIELD_MS = 1200;

const post = (map: Map<string, number[]>, key: string, id: number) => {
  const list = map.get(key);
  if (list) list.push(id); else map.set(key, [id]);
};

function indexRow(g: Raw): void {
  // malformed corpus rows are skipped, never crash the sheet
  if (!g || typeof g.n !== "string") return;
  const nrm = g.n.toLowerCase().replace(/[^a-z0-9]+/g, " ").replace(/\s+/g, " ").trim();
  if (!nrm) return;
  const toks = nrm.split(" ");
  const e: Entry = {
    n: g.n, c: g.c, lat: g.lat, lon: g.lon, w: g.w, k: g.k,
    nrm, toks,
    ftoks: toks.map(fold).filter(Boolean),
    fskel: foldName(nrm),
    wt: typeBonus(g.c) + g.w * 0.5 + g.k * 2,
  };
  const id = ENTRIES!.push(e) - 1;

  const keys = new Set<string>();
  const fkeys = new Set<string>();
  for (const tok of e.toks)
    for (let l = 1; l <= Math.min(tok.length, MAX_PREFIX); l++) keys.add(tok.slice(0, l));
  for (const tok of e.ftoks) {
    if (!tok) continue;
    for (let l = 1; l <= Math.min(tok.length, MAX_PREFIX); l++) fkeys.add(tok.slice(0, l));
  }
  for (let l = 2; l <= Math.min(e.fskel.length, MAX_PREFIX); l++)
    post(FSKEL!, e.fskel.slice(0, l), id);
  // reverse aliases: a name containing "greater kailash" also answers to "gk"
  for (const [exp, ab] of EXPANSIONS)
    if (nrm.includes(exp))
      for (let l = 1; l <= Math.min(ab.length, MAX_PREFIX); l++) keys.add(ab.slice(0, l));

  for (const key of keys) post(PREFIX!, key, id);
  for (const key of fkeys) post(FPREFIX!, key, id);

  const gk = `${Math.floor(e.lat / GEO_CELL)},${Math.floor(e.lon / GEO_CELL)}`;
  post(GEO!, gk, id);
  if (AREA_KINDS.has(e.c)) post(AREA!, gk, id);
}

/** One slice of index work; returns true when the whole index is ready.
 *  `maxMs` bounds the slice's wall time regardless of row count — the
 *  loop exits mid-slice once the budget is spent. */
function buildSlice(maxRows: number, maxMs = Infinity): boolean {
  if (built) return true;
  if (!RAW) {
    /* the require's own parse is the one cost we can't slice — it lands
       whichever way the first touch arrives; every indexed row after it
       is what the slice loop amortizes */
    RAW = require("../../assets/delhi-gazetteer.json") as Raw[];
    ENTRIES = [];
    PREFIX = new Map();
    FPREFIX = new Map();
    FSKEL = new Map();
    AREA = new Map();
    GEO = new Map();
    cursor = 0;
    capIdx = 0;
  }
  const raw = RAW, end = Math.min(cursor + maxRows, raw.length);
  const t0 = performance.now();
  for (; cursor < end; cursor++) {
    indexRow(raw[cursor]);
    /* wall-time early-out: a saturating rig stretches a 6k-row slice far
       past one frame — bail mid-slice so queued input wins the next
       macrotask (a clock read per row costs ~ms total across the build). */
    if (performance.now() - t0 > maxMs) return false;
  }
  if (cursor < raw.length) return false;
  /* the posting-cap sorts ride the same slice discipline as the row
     build — one map per call so a saturated rig parks between them.
     The comparator reads the precomputed wt: the old weight() call
     re-ran the typeBonus regex gauntlet twice per compare, which IS
     the cold-boot ~2 min 100%-CPU storm this lane hunted (see the
     memoized typeBonus note above). */
  const entries = ENTRIES!;
  const cap = (map: Map<string, number[]>) => {
    for (const ids of map.values())
      if (ids.length > PREFIX_CAP) {
        ids.sort((a, b) => entries[b].wt - entries[a].wt);
        ids.length = PREFIX_CAP;
      }
  };
  const capSet = [PREFIX!, FPREFIX!, FSKEL!][capIdx++];
  if (capSet) { cap(capSet); return false; }

  // free the multi-MB source array — the require()d JSON otherwise stays
  // pinned in Metro's module registry for the app lifetime (perf-r4)
  raw.length = 0;
  RAW = null;
  built = true;
  return true;
}

/** Synchronous finish — every reader path (query, nearestPlace) calls
 *  this, so results are always complete however far warm() got. */
function build(): void {
  while (!built) buildSlice(1 << 30);
}

/** Preload the gazetteer + index in background slices — call at boot-idle
 *  and on the search CTA's press-in. Idempotent; a no-op once built. */
export function warm(): void {
  if (built || scheduled || deferred) return;
  /* sigbus-release lane: the warm burst is thousands of allocations inside
     ~8 ms slices — while it runs during the cold-boot window (bundle eval,
     module init, tile churn, first mounts, roughly the first ~12 s) the
     Hermes heap gets corrupted on the iOS sim and detonates later inside a
     TimerCallback (SIGBUS/SIGSEGV, docs/lanes/sigbus-release-report.md).
     The same burst is harmless once boot activity settles, so the first
     call defers the whole build past the window instead of racing it.
     Press-in calls still warm lazily through the same path — the index
     also builds on demand, so early queries stay complete.

     boot-burst lane: inside the slice loop itself, real input wins — a
     touch within INPUT_YIELD_MS pauses slicing, and each slice is capped
     at WARM_SLICE_MS of wall time, so a saturated rig never parks the JS
     thread behind index work while the user is tapping. */
  deferred = true;
  setTimeout(() => {
    if (built || scheduled) return;
    scheduled = true;
    const step = () => {
      if (msSinceInput() < INPUT_YIELD_MS) {
        setTimeout(step, INPUT_YIELD_MS);
        return;
      }
      if (buildSlice(WARM_SLICE, WARM_SLICE_MS)) scheduled = false;
      else setTimeout(step, STEP_GAP_MS);
    };
    setTimeout(step, 0);
  }, WARM_DEFER_MS);
}

const WARM_DEFER_MS = 15000;
const STEP_GAP_MS = 50;
let deferred = false;

/** Damerau-Levenshtein with an early-exit cap — only runs when the cheap
 * stages found nothing, over a few hundred dictionary folds. */
function dlDist(a: string, b: string, cap: number): number {
  const la = a.length, lb = b.length;
  if (Math.abs(la - lb) > cap) return cap + 1;
  if (la === 0) return lb;
  if (lb === 0) return la;
  let p2: number[] = [];
  let p1: number[] = [];
  let cur: number[] = [];
  for (let j = 0; j <= lb; j++) p1[j] = j;
  for (let i = 1; i <= la; i++) {
    cur[0] = i;
    let rowMin = cur[0];
    for (let j = 1; j <= lb; j++) {
      const cost = a[i - 1] === b[j - 1] ? 0 : 1;
      let v = Math.min(p1[j] + 1, cur[j - 1] + 1, p1[j - 1] + cost);
      if (i > 1 && j > 1 && a[i - 1] === b[j - 2] && a[i - 2] === b[j - 1])
        v = Math.min(v, p2[j - 2] + 1);
      cur[j] = v;
      if (v < rowMin) rowMin = v;
    }
    if (rowMin > cap) return cap + 1;
    const t = p2; p2 = p1; p1 = cur; cur = t;
  }
  return p1[lb];
}

/** does a row's token set satisfy a unit ask — 'gali 4' needs a 'gali'
 * family token AND a token equal to '4' ('44' is a different gali); a
 * letter value also accepts letter+digit ('a block' ~ 'a5 block'). */
const STRUCT_ALTS: Record<string, string[]> = {
  gali: ["gali", "gully", "lane", "street"], gully: ["gali", "gully", "lane"],
  lane: ["lane", "gali", "street"], street: ["street", "gali", "lane", "road"],
  block: ["block", "blk"], pocket: ["pocket", "poket", "pkt"], poket: ["pocket", "poket", "pkt"],
  pkt: ["pocket", "poket", "pkt"], sector: ["sector", "sec"], phase: ["phase", "ph"],
  part: ["part"], khand: ["khand"], enclave: ["enclave"], extension: ["extension", "ext"],
  khasra: ["khasra", "kh"], kh: ["khasra", "kh"], ward: ["ward"], zone: ["zone"],
  market: ["market", "mkt"],
};

const unitSat = (etoks: string[], u: { struct: string; value: string }): boolean => {
  const alts = STRUCT_ALTS[u.struct] ?? [u.struct];
  if (!alts.some((a) => etoks.includes(a))) return false;
  return etoks.some((t) =>
    t === u.value ||
    (u.value.length === 1 && /[a-z]/.test(u.value) && t.startsWith(u.value) && /^\d+$/.test(t.slice(1))));
};

/** nearest area-kind row to a point — the locality half of a subtitle. */
function areaNear(lat: number, lon: number, maxM = 1400): Entry | null {
  const area = AREA!;
  const entries = ENTRIES!;
  const bi = Math.floor(lat / GEO_CELL), bj = Math.floor(lon / GEO_CELL);
  let best: Entry | null = null;
  let bestS = -Infinity;
  for (let r = 0; r <= 8; r++) {
    for (let di = -r; di <= r; di++)
      for (let dj = -r; dj <= r; dj++) {
        if (Math.max(Math.abs(di), Math.abs(dj)) !== r) continue;
        for (const i of area.get(`${bi + di},${bj + dj}`) ?? []) {
          const e = entries[i];
          const d = distKm(e, { lat, lon }) * 1000;
          if (d > maxM) continue;
          const s = weight(e) - d / 400;
          if (s > bestS) { bestS = s; best = e; }
        }
      }
    if (best) break;  // first ring with an area wins — nearest is the truth
  }
  return best;
}

/** the subtitle a Google-style row shows: "<kind> · <locality>" — the
 * resolved street/gali + area, not just a bare name pin. */
const subtitleFor = (e: Entry): string => {
  if (AREA_KINDS.has(e.c)) return kindLabel(e.c);
  const a = areaNear(e.lat, e.lon);
  return a && a.nrm !== e.nrm ? `${kindLabel(e.c)} · ${a.n}` : kindLabel(e.c);
};

/** staged candidate collection: union of prefix, fold-prefix and
 * skeleton postings → per-entry best match tier. */
function matchStage(
  p: Parsed, bias: LatLon | null | undefined, cap: number,
): { s: number; e: Entry }[] {
  const entries = ENTRIES!, prefix = PREFIX!, fprefix = FPREFIX!, fskel = FSKEL!;
  const head = p.toks.join(" ");
  const cand = new Set<number>();

  const lists = p.toks.map((tk) => prefix.get(tk.slice(0, MAX_PREFIX)) ?? []);
  const flists = p.folds.map((tk) => fprefix.get(tk.slice(0, MAX_PREFIX)) ?? []);
  const allLists = [...lists, ...flists];
  if (allLists.length && allLists.every((l) => l.length === 0)) {
    // no prefix anywhere — try the fused-name skeleton before giving up
    const sk = fold(p.toks.join(""));
    if (sk.length >= 2) for (const id of fskel.get(sk.slice(0, MAX_PREFIX)) ?? []) cand.add(id);
    if (!cand.size) return [];
  } else {
    // rarest posting bounds the scan; fold lists widen the same pool
    let base = 0;
    for (let i = 1; i < allLists.length; i++)
      if (allLists[i].length < allLists[base].length) base = i;
    for (const id of allLists[base]) cand.add(id);
    // fused single-token queries also check the full-name skeleton
    if (p.toks.length === 1) {
      const sk = fold(p.toks[0]);
      if (sk.length >= 2) for (const id of fskel.get(sk.slice(0, MAX_PREFIX)) ?? []) cand.add(id);
    }
  }

  const scored: { s: number; e: Entry }[] = [];
  for (const id of cand) {
    const e = entries[id];
    let m = 0;
    if (head && e.nrm.startsWith(head)) m = 100;
    else if (p.toks.every((qt) => e.toks.some((nt) => nt.startsWith(qt)))) m = 75;
    else if (p.folds.length && p.folds.every((qt) => e.ftoks.some((nt) => nt.startsWith(qt)))) m = 62;
    else if (head && (e.nrm.includes(` ${head}`) || e.nrm.includes(head))) m = 50;
    else if (p.folds.length === 1 && e.fskel.startsWith(fold(p.toks[0]))) m = 58;
    else continue;
    scored.push({ s: m + weight(e), e });
  }

  /* fuzzy stage — only when nothing matched. Typos, not guesses: every
     query fold-token must land within DL distance 1 (short) or 2. */
  if (!scored.length && p.folds.length) {
    for (let i = 0; i < entries.length; i++) {
      const e = entries[i];
      let sum = 0;
      let failed = false;
      for (const qf of p.folds) {
        const bcap = qf.length <= 4 ? 1 : 2;
        let bd = bcap + 1;
        for (const ft of e.ftoks) {
          if (Math.abs(ft.length - qf.length) > bcap) continue;
          const d = dlDist(qf, ft, bcap);
          if (d < bd) bd = d;
          if (bd === 0) break;
        }
        if (bd > bcap) { failed = true; break; }
        sum += bd;
      }
      if (failed) continue;
      scored.push({ s: 55 - sum * 8 + weight(e), e });
      if (scored.length > 400) break;
    }
  }

  if (bias && typeof distKm === "function")
    for (const r of scored) r.s -= Math.min(distKm(r.e, bias), 60) * 0.8;
  scored.sort((a, b) => b.s - a.s);
  return scored.slice(0, cap);
}

/** resolve a near-phrase ("near hanuman mandir") to a real row — any kind
 * can anchor. Common names ("hanuman mandir" is everywhere) resolve to
 * the NEAREST strong match to the caller, like Google — a famous mandir
 * 12 km away is never "the" mandir the user is standing next to. */
function resolveAnchor(toks: string[], userLoc?: LatLon | null): Entry | null {
  const p: Parsed = {
    raw: toks.join(" "), nq: toks.join(" "), toks,
    folds: toks.map(fold), units: [], kind: null, near: null,
  };
  const hits = matchStage(p, userLoc, 8);
  if (!hits.length) return null;
  if (!userLoc || typeof distKm !== "function") return hits[0].e;
  // nearest among the matches — but never pay more than the weight gap
  // of a clearly better answer (~20 pts ≈ 25 km) for proximity
  let best = hits[0];
  for (const h of hits.slice(1)) {
    const dNew = distKm(h.e, userLoc), dBest = distKm(best.e, userLoc);
    if (dNew + 1e-9 < dBest && h.s - dNew * 0 >= best.s - dBest * 2.2) best = h;
  }
  return best.e;
}

/** entries satisfying every unit ask within maxM of an anchor — "gali 4"
 * inside Ashok Nagar. Rides the same geo cells as nearestPlace. */
function unitScan(anchor: LatLon, units: Parsed["units"], maxM = 2600, cap = 6): { e: Entry; d: number }[] {
  const entries = ENTRIES!;
  const geo = GEO!;
  const out: { e: Entry; d: number }[] = [];
  const cells = Math.ceil(maxM / 1000 / 0.22);
  const bi = Math.floor(anchor.lat / GEO_CELL), bj = Math.floor(anchor.lon / GEO_CELL);
  for (let di = -cells; di <= cells; di++)
    for (let dj = -cells; dj <= cells; dj++)
      for (const i of geo.get(`${bi + di},${bj + dj}`) ?? []) {
        const e = entries[i];
        if (!units.every((u) => unitSat(e.toks, u))) continue;
        const d = distKm(e, anchor) * 1000;
        if (d <= maxM) out.push({ e, d });
      }
  out.sort((a, b) => a.d - b.d);
  return out.slice(0, cap);
}

/** kind-scan — "bakery near hanuman mandir": real kind rows around the
 * anchor, honestly labelled as the kind (never pretending to be a named
 * place the corpus doesn't hold). A name qualifier ('pawan') that a row's
 * own name carries outranks one it doesn't. */
function kindScan(anchor: LatLon, kindRe: RegExp, nameToks: string[], maxM = 2600, cap = 6): { e: Entry; d: number }[] {
  const entries = ENTRIES!;
  const geo = GEO!;
  const out: { e: Entry; d: number; named: number }[] = [];
  const cells = Math.ceil(maxM / 1000 / 0.22);
  const bi = Math.floor(anchor.lat / GEO_CELL), bj = Math.floor(anchor.lon / GEO_CELL);
  for (let di = -cells; di <= cells; di++)
    for (let dj = -cells; dj <= cells; dj++)
      for (const i of geo.get(`${bi + di},${bj + dj}`) ?? []) {
        const e = entries[i];
        if (!kindRe.test(e.c)) continue;
        const d = distKm(e, anchor) * 1000;
        if (d > maxM) continue;
        const named = nameToks.length && nameToks.every((t) => e.toks.some((nt) => nt.startsWith(t))) ? 1 : 0;
        out.push({ e, d, named });
      }
  out.sort((a, b) => b.named - a.named || a.d - b.d);
  return out.slice(0, cap);
}

const toResult = (e: Entry, sub?: string): PlaceResult => ({
  name: e.n,
  subtitle: sub ?? subtitleFor(e),
  lat: e.lat,
  lon: e.lon,
  kind: e.c,
  outside_ncr: !inNcr(e.lat, e.lon),
  tier: "t0",
});

/** On-device search: staged prefix/fold/fuzzy lookup over the bundled
 * gazetteer, unit + near-anchor resolution on top. Typical <5 ms. */
export function query(q: string, userLoc?: LatLon | null, limit = 8): PlaceResult[] {
  build();
  const p = parseQuery(q);
  if (!p || (!p.toks.length && !p.units.length)) return [];

  /* "X near Y" — resolve Y first; it becomes the bias for everything. */
  const nearAnchor = p.near && p.near.length ? resolveAnchor(p.near, userLoc) : null;
  const bias = nearAnchor ?? userLoc ?? null;

  let scored = p.toks.length ? matchStage(p, bias, limit * 4) : [];

  /* trailing-context retry — "ashok nagar shahdara" may only resolve as
     "ashok nagar" when 'shahdara' is neighbourhood context, not name
     text. Drop tail tokens one at a time; a dropped tail that resolves
     as its own anchor biases among same-named candidates. */
  if (!scored.length && p.toks.length > 1) {
    for (let cut = p.toks.length - 1; cut >= 1 && !scored.length; cut--) {
      const tail = resolveAnchor(p.toks.slice(cut), userLoc);
      const sub: Parsed = {
        ...p,
        toks: p.toks.slice(0, cut),
        folds: p.folds.slice(0, cut),
        nq: p.toks.slice(0, cut).join(" "),
      };
      scored = matchStage(sub, tail ?? bias, limit * 4);
      if (scored.length && tail) break;
    }
  }

  /* units — 'gali 4'/'block a' inside the resolved place: unit rows
     around the anchor are THE answer; the area itself stands when no
     unit row exists (honest area answer, not a wrong-colony guess). */
  const unitRows: PlaceResult[] = [];
  const anchorE = nearAnchor ?? scored[0]?.e ?? null;
  if (p.units.length && anchorE) {
    for (const { e } of unitScan(anchorE, p.units))
      unitRows.push(toResult(e));
  }

  /* kind routing — 'bakery near hanuman mandir' is a kind ask around an
     anchor, not a name ask: name rows of "bakery"-named places get the
     scan too, but the honest category answer leads. Same for a lone kind
     word ('atm') — nearby real ATMs beat "Atma Ram College". Only when
     the scan finds nothing do name-path rows stand. */
  let kindRows: PlaceResult[] = [];
  const loneKind = p.kind != null && p.toks.length === 1;
  const kindFirst = p.kind != null && (loneKind || (nearAnchor != null && p.toks.length >= 1));
  if (p.kind && (kindFirst || !scored.length) && !unitRows.length) {
    const re = new RegExp(kindRegexFor(p.kind)!);
    const nameToks = p.toks.filter((t) => t !== p.kind);
    const anchor: LatLon | null = nearAnchor ?? bias;
    if (anchor) {
      const anchorSub = nearAnchor ? ` · ${nearAnchor.n}` : "";
      kindRows = kindScan(anchor, re, nameToks, 2600, limit)
        .map(({ e }) => toResult(e, `${kindLabel(e.c)}${anchorSub}`));
    }
    // for a name-bearing kind ask the name hits may still be the better
    // answer — append them after the kind rows, dedupe handles overlap
  }

  /* assemble: unit rows → name hits → kind rows, hard-deduped. Same
     normalized name within ~400 m is ONE place no matter how many rows
     the corpus split it into. */
  const out: PlaceResult[] = [];
  const seenExact = new Set<string>();
  const seenName: { nrm: string; lat: number; lon: number }[] = [];
  const push = (r: PlaceResult, e?: Entry) => {
    if (out.length >= limit) return;
    const nrm = e ? e.nrm : normalize(r.name);
    const key = `${nrm}|${r.lat.toFixed(3)}|${r.lon.toFixed(3)}`;
    if (seenExact.has(key)) return;
    if (seenName.some((s) => s.nrm === nrm && Math.hypot((s.lat - r.lat) * 110.6, (s.lon - r.lon) * 99.4) * 1000 < 400)) return;
    seenExact.add(key);
    seenName.push({ nrm, lat: r.lat, lon: r.lon });
    out.push(r);
  };

  for (const r of unitRows) push(r);
  if (loneKind) {
    // a lone kind word's name-path rows are usually a different thing
    // entirely ('atm' → "Atma Ram College") — the scan IS the answer
    for (const r of kindRows) push(r);
    for (const { e } of scored) push(toResult(e), e);
  } else if (kindRows.length && kindFirst) {
    for (const r of kindRows) push(r);
    for (const { e } of scored) push(toResult(e), e);
  } else {
    for (const { e } of scored) push(toResult(e), e);
    for (const r of kindRows) push(r);
  }
  return out;
}

// --- offline reverse -----------------------------------------------------------
// Same idea as server/core_engine.nearest: the GEO lat/lon cell grid
// over the SAME bundled entries (built in build() — also serves unit
// and kind scans). A dropped pin with no network can still name the
// nearest real place — never a fabricated label.

// kinds that orient a dropped pin: street/address/locality names first,
// shops+POIs only when nothing else is nearby ("nearest:" phrasing
// keeps it honest either way).
const NEAR_FIRST = new Set([
  "address", "street", "road", "locality", "place", "neighbourhood",
  "suburb", "village", "district", "sector", "block", "residential area",
]);

export type NearestHit = { name: string; kind: string; distance_m: number };

export function nearestPlace(p: LatLon, maxM = 150): NearestHit | null {
  build();
  const entries = ENTRIES!;
  const geo = GEO!;
  const bi = Math.floor(p.lat / GEO_CELL), bj = Math.floor(p.lon / GEO_CELL);
  let best: NearestHit | null = null;
  let bestRank = 99, bestD = maxM;
  // ring r's points can't sit closer than (r-1)*~195 m — 3 rings covers
  // every cell that can hold a point within 150 m.
  for (let r = 0; r <= 2; r++) {
    for (let di = -r; di <= r; di++)
      for (let dj = -r; dj <= r; dj++) {
        if (Math.max(Math.abs(di), Math.abs(dj)) !== r) continue;
        for (const i of geo.get(`${bi + di},${bj + dj}`) ?? []) {
          if (typeof distKm !== "function") continue; // inline-require flake — miss over crash
          const e = entries[i];
          const d = distKm(e, p) * 1000;
          if (d > maxM) continue;
          const rank = NEAR_FIRST.has(e.c) ? 0 : 1;
          if (rank < bestRank || (rank === bestRank && d < bestD)) {
            bestRank = rank; bestD = d;
            best = { name: e.n, kind: e.c, distance_m: d };
          }
        }
      }
  }
  return best;
}
