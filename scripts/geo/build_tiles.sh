#!/usr/bin/env bash
# Build Delhi vector tiles -> data/geo/delhi.pmtiles (OpenMapTiles schema)
#
# Toolchain: tilemaker (docker, ghcr.io/systemed/tilemaker) writes PMTiles
# directly — no conversion step, no external shapefile downloads. We use
# the upstream OpenMapTiles config/lua with the optional-shapefile layers
# (ocean / urban_areas / ice_shelf / glacier) stripped — Delhi is
# landlocked; those layers would be empty anyway.
#
# Why not planetiler: OMT-profile planetiler hard-requires ~1 GB of
# natural-earth + water-polygon + lake-centerline sources (fails before
# osm_pass1 otherwise; --only-layers doesn't skip the check). tilemaker
# produces the same layer schema from just the pbf. Set TILEMAKER_IMAGE
# to pin a different tag. Idempotent; FORCE=1 rebuilds.
source "$(dirname "$0")/common.sh"

TILEMAKER_IMAGE="${TILEMAKER_IMAGE:-ghcr.io/systemed/tilemaker:master}"
CFG="$REPO_ROOT/scripts/geo/config-openmaptiles.json"
LUA="$REPO_ROOT/scripts/geo/process-openmaptiles.lua"

[[ -s "$BBOX_PBF" ]] || die "missing $BBOX_PBF — run fetch_extract.sh first"
[[ -s "$CFG" && -s "$LUA" ]] || die "missing $CFG / $LUA"
if [[ -s "$PMTILES" && "${FORCE:-0}" != "1" ]]; then
  log "pmtiles exists: $PMTILES ($(du -h "$PMTILES" | cut -f1)) — skip"
  exit 0
fi
docker image inspect "$TILEMAKER_IMAGE" >/dev/null 2>&1 \
  || docker pull "$TILEMAKER_IMAGE"

cp "$CFG" "$GEO_DIR/config-openmaptiles.json"
cp "$LUA" "$GEO_DIR/process-openmaptiles.lua"

log "tilemaker -> delhi.pmtiles (OMT schema, z0-14, gzip tiles)"
/usr/bin/time -v docker run --rm -v "$GEO_DIR:/data" "$TILEMAKER_IMAGE" \
  --input /data/delhi-ncr.osm.pbf \
  --output /data/delhi.pmtiles \
  --config /data/config-openmaptiles.json \
  --process /data/process-openmaptiles.lua \
  --bbox "$BBOX" 2>&1 | tail -30
# container wrote root-owned output; hand it back
docker run --rm -v "$GEO_DIR:/data" ubuntu:24.04 \
  chown "$(id -u):$(id -g)" /data/delhi.pmtiles || true
ls -lh "$PMTILES"
