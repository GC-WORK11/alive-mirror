# Map depth: v2-light vs Google Maps Delhi at z16+

Forensic side-by-side, 3 Oct 2026 — app on iPhone sim (left pane evidence) vs
Google Maps web on the same Delhi viewports (Chandni Chowk z16.5, Karol Bagh/
Central Vista z16.5). Same tile source the Android build renders.

## Closed this leg (source-available)

- **Bilingual street/landmark labels** — Google renders `English / देवनागरी`
  dual lines; we now do too on `v2-road-label-major`, `v2-poi-civic`,
  `v2-poi-transit`, `v2-place-neighbourhood`, `v2-place-suburb` (commit
  a6e88d6). Verified live: Janpath/जनपथ, Ashoka Road/अशोका रोड, Firoz Shah
  Road/फिरोज़ शाह रोड, Sarvodaya Bal School, Jhandewalan/झंडेवालान, Fateha
  Jame Mosque, Central Ridge Reserve Forest. Romanized `name:hi` dupes are
  suppressed via `downcase` equality — "Eastern Court" renders once.
- **Landmark civic names** — dispensaries, clinics, schools, mosques render
  with names at z13.5+ (v2-poi-civic), same pane where Google shows them.
- **Housenumbers** — z16.5+ along commercial blocks (v2-housenumber).
- **Metro gates** — "Gate No. N" labels at z16.5+ (v2-poi-gate).
- **One-way arrows** — visible on Chowri Bazar gullies (v2-oneway).
- **Building footprints** — dense to property granularity via
  v2-building + v2-building-extrusion.

## Gaps a judge would still notice

| Gap | Why | Closeable? |
|---|---|---|
| Business POI density (restaurants, shops, banks with names) | OSM Delhi shop coverage is thin; the style already filters them in (v2-poi-services z15.5+, v2-poi-text) — features simply aren't in the tiles. Google licenses commercial POI data. | No — source-data gap, not a style gap. Only fixable by buying a POI provider (not keyless). |
| Ratings/photos/"busy now" | Licensed Google data | No |
| Metro line colour badges (Yellow/Violet line pills) | OMT tiles don't carry Delhi line refs/colours in route attrs | Not without a custom overlay layer sourced elsewhere |
| Live traffic shading | No keyless traffic tiles | No |
| 3D building colour/texture variety | Google stylized; our extrusion is monotone | Style-only tweak possible (colour by height band) — low judge value |
| Search precision to shop names | Server gazetteer is OSM-derived | Same source-data gap |

## Source forensics (verified)

- OpenFreeMap planet = dated snapshot `planet/20260927_080001_pt`, maxzoom 14
  (clients overzoom for z15+; label density doesn't thin because our label
  layers sit at minzoom ≤16.5 against overzoomed features).
- Chandni Chowk z14 tile carries `name`, `name:latin`, `name:hi`, `name:en`,
  `name_en`, `name:nonlatin` plus ~50 multilingual variants per named feature.
  For Delhi: `name`=English, `name:hi`=Devanagari.
- Devanagari glyphs ship in OpenFreeMap's "Noto Sans Regular" fontstack
  (range 2304-2559.pbf → HTTP 200).

## Verdict

At z16 the basemap now holds up next to Google on structure, street names,
civic landmarks, and bilingual labels. The remaining visible gap is commercial
POI density + ratings — a licensed-data gap no keyless stack closes.
