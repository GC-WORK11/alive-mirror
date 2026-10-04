// Row glyph for a gazetteer/server category. Every category resolves to a
// first-class glyph from the app set (src/icons.tsx — Material Symbols
// Rounded geometry), so every search row shows a crisp category mark
// (docs/plan/02 S2). Order matters: first matching regex wins.
import React from "react";
import { Icon, type Glyph } from "../icons";

const MAP: [RegExp, Glyph][] = [
  [/metro|subway/, "metro"],
  [/train|railway|rail/, "rail"],
  [/bus|transit/, "bus"],
  [/restaurant|cafe|food|eatery|dhaba|bakery|bar|pub/, "restaurant"],
  [/hospital|clinic|doctor|health|vet/, "hospital"],
  [/pharmacy|chemist|medicine/, "pharmacy"],
  [/mall|shopping/, "mall"],
  [/shop|market|store|bazaar|retail/, "shop"],
  [/school|college|university|education|institute/, "school"],
  [/airport|airfield|airstrip/, "airport"],
  [/mosque|masjid|dargah/, "mosque"],
  [/church/, "church"],
  [/worship|temple|gurudwara|gurdwara|shrine|mandir/, "temple"],
  [/atm/, "atm"],
  [/bank|finance|credit/, "bank"],
  [/hotel|lodge|guest|resort|hostel|inn|stay/, "hotel"],
  [/cinema|movie|theater|theatre|multiplex/, "cinema"],
  [/stadium|arena|sports|playground|ground/, "stadium"],
  [/fuel|petrol|gas_station|charging/, "fuel"],
  [/police|security/, "police"],
  [/gym|fitness/, "gym"],
  [/office|business|cowork/, "office"],
  [/park|garden|forest|nature/, "park"],
  [/museum|gallery/, "museum"],
  [/landmark|monument|historic|attraction|memorial|fort/, "monument"],
  [/fire/, "flame"],
];

/** Row glyph for a gazetteer/server category — official geometry throughout. */
export function categoryGlyph(kind: string | undefined, color: string, size = 22): React.ReactNode {
  const k = (kind ?? "").toLowerCase().replace(/_/g, " ");
  for (const [re, glyph] of MAP) {
    if (re.test(k)) return <Icon name={glyph} color={color} size={size} />;
  }
  return <Icon name="pin" color={color} size={size} />;
}
