#!/usr/bin/env bash
# Prepare OSRM MLD routing graphs for car / foot / bicycle.
# Output: data/geo/osrm/<mode>/delhi.osrm*   (one dir per mode —
# osrm file names are fixed, separate dirs keep them apart)
#
# MLD (extract -> partition -> customize) instead of CH: faster queries
# and supports live speed updates later via osrm-customize --segment-speed.
# Idempotent: skips modes whose .osrm.mldgr exists; FORCE=1 rebuilds.
source "$(dirname "$0")/common.sh"

[[ -s "$BBOX_PBF" ]] || die "missing $BBOX_PBF — run fetch_extract.sh first"
# Only need the OSRM docker image — not tools.sh (it provisions osmium +
# planetiler for the tile lane and dies without java, which this build
# doesn't need).
docker image inspect "$OSRM_IMAGE" >/dev/null 2>&1 || docker pull "$OSRM_IMAGE"
mkdir -p "$OSRM_DIR"

# Modes to build — the deploy sidecar needs only `driving` (a self-hosted
# osrm-routed serves ONE profile; the public demo it replaces is car-only
# anyway). OSRM_MODES="driving" for the deploy build, all three locally.
for mode in ${OSRM_MODES:-driving walking cycling}; do
  prof="${OSRM_PROFILES[$mode]}"
  dir="$OSRM_DIR/$mode"
  mkdir -p "$dir"
  if [[ -f "$dir/delhi.osrm.mldgr" && "${FORCE:-0}" != "1" ]]; then
    log "$mode graph exists — skip (FORCE=1 to redo)"
    continue
  fi
  log "osrm $mode: extract+partition+customize with /opt/$prof.lua"
  rm -f "$dir"/delhi.osrm* "$GEO_DIR"/delhi-ncr.osrm*
  # osrm-extract derives output names from the input file — extract in
  # GEO_DIR, then move the whole .osrm* set into the per-mode dir.
  docker run --rm -v "$GEO_DIR:/data" "$OSRM_IMAGE" \
    osrm-extract -p "/opt/$prof.lua" /data/delhi-ncr.osm.pbf --threads 12
  docker run --rm -v "$GEO_DIR:/data" "$OSRM_IMAGE" \
    osrm-partition /data/delhi-ncr.osrm --threads 12
  docker run --rm -v "$GEO_DIR:/data" "$OSRM_IMAGE" \
    osrm-customize /data/delhi-ncr.osrm --threads 12
  for f in "$GEO_DIR"/delhi-ncr.osrm*; do
    mv "$f" "$dir/delhi.osrm${f##*delhi-ncr.osrm}"
  done
  docker run --rm -v "$GEO_DIR:/data" ubuntu:24.04 \
    chown -R "$(id -u):$(id -g)" "/data/osrm/$mode" || true
  du -sh "$dir"
done
log "OSRM graphs ready under $OSRM_DIR"
