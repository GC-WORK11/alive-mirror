// T0 — the on-device search tier (docs/plan/04 §2).
// Bundled Delhi gazetteer behind a prefix index; answers in <5 ms so the
// first suggestion paints inside a frame (<16 ms) while the server tiers
// (client.ts) stream in behind it. normalize() is shared with the
// merge/dedupe layer so every tier keys names identically.

type Raw = { n: string; c: string; lat: number; lon: number; w: number; k: number };

export type LatLon = { lat: number; lon: number };
export type SearchTier = "t0" | "t1" | "t2";

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

// Delhi NCR bounds — the same box App.tsx uses for the "outside Delhi" tag.
const NCR = { minLon: 76.75, maxLon: 77.95, minLat: 28.15, maxLat: 28.98 };
export const inNcr = (lat: number, lon: number) =>
  lon > NCR.minLon && lon < NCR.maxLon && lat > NCR.minLat && lat < NCR.maxLat;
export const DELHI_CENTER: LatLon = { lat: 28.6139, lon: 77.209 };

// Fast km estimate near Delhi (~28.6°N) — same constants as the rest of the
// app so distances read identically everywhere.
export const distKm = (a: LatLon, b: LatLon): number =>
  Math.hypot((a.lat - b.lat) * 110.6, (a.lon - b.lon) * 99.4);

// Hinglish / common abbreviations (docs/plan/04 §2 normalization table).
// Applied query-side; full names are also reverse-aliased at index time so
// "gk" finds Greater Kailash even before expansion is considered.
const ABBREV: Record<string, string> = {
  cp: "connaught place",
  gk: "greater kailash",
  sec: "sector",
  ngr: "nagar",
  vhr: "vihar",
  ext: "extension",
  encl: "enclave",
  mkt: "market",
  rd: "road",
  stn: "station",
  chok: "chowk",
  ph: "phase",
  clny: "colony",
};
const EXPANSIONS: [string, string][] = Object.entries(ABBREV).map(([ab, exp]) => [exp, ab]);

/** Shared normalization: lowercase, punctuation → space, abbreviation
 * expansion, single spaces. Used for queries, index keys and dedupe. */
export function normalize(q: string): string {
  const s = q.toLowerCase().replace(/[^a-z0-9]+/g, " ").replace(/\s+/g, " ").trim();
  if (!s) return "";
  return s
    .split(" ")
    .map((tok) => ABBREV[tok] ?? tok)
    .join(" ");
}

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
  nrm: string; toks: string[];
};

let ENTRIES: Entry[] | null = null;
let PREFIX: Map<string, number[]> | null = null;

const MAX_PREFIX = 8;   // longest indexed prefix per token
const PREFIX_CAP = 80;  // max ids kept per prefix (heaviest first)

const weight = (e: Entry) => e.w + e.k * 2;

function build(): void {
  if (ENTRIES) return;
  const raw = require("../../assets/delhi-gazetteer.json") as Raw[];
  const entries: Entry[] = [];
  const prefix = new Map<string, number[]>();

  for (const g of raw) {
    // malformed corpus rows are skipped, never crash the sheet
    if (!g || typeof g.n !== "string") continue;
    const nrm = g.n.toLowerCase().replace(/[^a-z0-9]+/g, " ").replace(/\s+/g, " ").trim();
    if (!nrm) continue;
    const e: Entry = { n: g.n, c: g.c, lat: g.lat, lon: g.lon, w: g.w, k: g.k, nrm, toks: nrm.split(" ") };
    const id = entries.push(e) - 1;

    const keys = new Set<string>();
    for (const tok of e.toks)
      for (let l = 1; l <= Math.min(tok.length, MAX_PREFIX); l++) keys.add(tok.slice(0, l));
    // reverse aliases: a name containing "greater kailash" also answers to "gk"
    for (const [exp, ab] of EXPANSIONS)
      if (nrm.includes(exp))
        for (let l = 1; l <= Math.min(ab.length, MAX_PREFIX); l++) keys.add(ab.slice(0, l));

    for (const key of keys) {
      const list = prefix.get(key);
      if (list) list.push(id);
      else prefix.set(key, [id]);
    }
  }

  for (const ids of prefix.values())
    if (ids.length > PREFIX_CAP) {
      ids.sort((a, b) => weight(entries[b]) - weight(entries[a]));
      ids.length = PREFIX_CAP;
    }

  // free the 2.7MB source array — the require()d JSON otherwise stays
  // pinned in Metro's module registry for the app lifetime (perf-r4)
  raw.length = 0;
  ENTRIES = entries;
  PREFIX = prefix;
}

/** Preload the gazetteer + index (call when the search UI opens). */
export function warm(): void {
  build();
}

/** On-device search: prefix-index lookup, distance+weight ranked.
 * Typical <5 ms. */
export function query(q: string, userLoc?: LatLon | null, limit = 8): PlaceResult[] {
  build();
  const nq = normalize(q);
  const entries = ENTRIES!;
  const prefix = PREFIX!;
  if (!nq) return [];

  const qToks = nq.split(" ");
  // Candidate pool = posting list of the rarest query token; every other
  // token is then verified against the entry's tokens. Postings are capped
  // at PREFIX_CAP so the scan is bounded.
  const lists = qToks.map((tk) => prefix.get(tk.slice(0, MAX_PREFIX)) ?? []);
  if (lists[0].length === 0) return [];
  let base = 0;
  for (let i = 1; i < lists.length; i++) if (lists[i].length < lists[base].length) base = i;

  const scored: { s: number; e: Entry }[] = [];
  outer: for (const id of lists[base]) {
    const e = entries[id];
    const allToks = qToks.every((qt) => e.toks.some((nt) => nt.startsWith(qt)));
    const phrase = e.nrm.startsWith(nq) || e.nrm.includes(` ${nq}`) || e.nrm.includes(nq);
    if (!allToks && !phrase) continue outer;
    let s = e.nrm.startsWith(nq) ? 100 : allToks ? 70 : 40;
    s += weight(e);
    if (userLoc) s -= Math.min(distKm(e, userLoc), 60) * 0.8;
    scored.push({ s, e });
  }

  scored.sort((a, b) => b.s - a.s);
  const seen = new Set<string>();
  const out: PlaceResult[] = [];
  for (const { e } of scored) {
    const key = `${e.nrm}|${e.lat.toFixed(3)}|${e.lon.toFixed(3)}`;
    if (seen.has(key)) continue;
    seen.add(key);
    out.push({
      name: e.n,
      subtitle: kindLabel(e.c),
      lat: e.lat,
      lon: e.lon,
      kind: e.c,
      outside_ncr: !inNcr(e.lat, e.lon),
      tier: "t0",
    });
    if (out.length >= limit) break;
  }
  return out;
}
