# assets/map — marker art sources

All artwork in this directory is **hand-drawn in-repo** for Alive
(geometry authored directly as SVG path data in `src/map/markers.tsx`; the
.svg files here are byte-equivalent reference copies for design review and
future raster exports). No third-party or unlicensed assets are used — the
shapes are simple geometry (teardrop pinlet, ring, puck) written for this
project under the repo's own license.

| File | Runtime copy | Use |
|---|---|---|
| `pin-dest.svg` | `DestPin` in `src/map/markers.tsx` | destination pinlet `#E5484D` (doc 03) |
| `pin-origin.svg` | `OriginPin` in `src/map/markers.tsx` | origin white ring + accent dot |
| `puck.svg` | `UserPuck` in `src/map/markers.tsx` | user location puck + heading beam |

Why RN components instead of bundled PNGs: `react-native-svg` is already a
dependency, components scale losslessly across densities, and they tint from
`V2T` tokens at render time. If a native `<Marker>` icon bitmap is ever
needed, render these SVGs at 24/48/96 px and drop the PNGs here.
