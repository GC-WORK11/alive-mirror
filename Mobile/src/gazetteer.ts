// Instant offline gazetteer for Delhi NCR — 24k ranked POIs from Overture Maps
// (CC-BY 4.0). Substring match answers in <5ms; the network layer appends
// fresher/richer results over it.

type G = { n: string; c: string; lat: number; lon: number; w: number; k: number };
export type LocalHit = { name: string; subtitle: string; lat: number; lon: number; outside_ncr?: boolean };

let GAZ: G[] | null = null;
const load = (): G[] => (GAZ ??= require("../assets/delhi-gazetteer.json") as G[]);

const norm = (s: string) => s.toLowerCase().replace(/[^a-z0-9 ]/g, "").trim();

const SUB: Record<string, string> = {
  locality: "delhi", macrohood: "delhi", neighborhood: "neighbourhood",
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
};

export function localSearch(q: string, bias: { lat: number; lon: number }, limit = 8): LocalHit[] {
  const t = norm(q);
  if (t.length < 2) return [];
  const words = t.split(/\s+/);
  const scored: { s: number; g: G }[] = [];
  for (const g of load()) {
    const n = norm(g.n);
    if (!n) continue;
    let score = 0;
    if (n.startsWith(t)) score = 100;
    else if (n.includes(" " + t) || n.includes(t)) score = 60;
    else {
      let all = true;
      for (const w of words) if (!n.includes(w)) { all = false; break; }
      if (all) score = 40;
    }
    if (!score) continue;
    // closer to bias + higher category weight + confidence wins ties
    const dKm = Math.hypot((g.lat - bias.lat) * 110.6, (g.lon - bias.lon) * 99.4);
    score += g.w + g.k * 2 - Math.min(dKm, 60) * 0.8;
    scored.push({ s: score, g });
    if (scored.length > 400) { scored.sort((a, b) => b.s - a.s); scored.length = 200; }
  }
  scored.sort((a, b) => b.s - a.s);
  return scored.slice(0, limit).map(({ g }) => ({
    name: g.n,
    subtitle: SUB[g.c] ?? g.c.replace(/_/g, " "),
    lat: g.lat, lon: g.lon,
  }));
}
