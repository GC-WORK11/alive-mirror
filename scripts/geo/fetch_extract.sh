#!/usr/bin/env bash
# Fetch Delhi NCR OSM data -> data/geo/delhi-ncr.osm.pbf
#
# Source (env EXTRACT_SOURCE):
#   geofabrik (default): northern-zone-latest.osm.pbf (~224 MB) clipped
#                        to the NCR bbox with osmium — fresh daily, covers
#                        full NCR incl. Noida/Gurgaon/Faridabad/Ghaziabad
#   bbbike             : pre-clipped New Delhi city extract (~37 MB),
#                        weekly refresh, slightly tighter than NCR bbox
# Idempotent: skips while delhi-ncr.osm.pbf exists; FORCE=1 rebuilds.
source "$(dirname "$0")/common.sh"
SRC="${EXTRACT_SOURCE:-geofabrik}"
mkdir -p "$GEO_DIR"

if [[ -s "$BBOX_PBF" && "${FORCE:-0}" != "1" ]]; then
  log "extract exists: $BBOX_PBF ($(du -h "$BBOX_PBF" | cut -f1)) — skip (FORCE=1 to redo)"
  exit 0
fi

case "$SRC" in
  geofabrik)
    RAW="$GEO_DIR/northern-zone.osm.pbf"
    if [[ ! -s "$RAW" || "${REFRESH:-0}" == "1" ]]; then
      log "downloading Geofabrik northern-zone (~224 MB)"
      curl -fSL --retry 3 -o "$RAW" "$GEOFABRIK_URL"
    fi
    # osmium: system package when present (CodeBuild apt-installs it),
    # else the no-root dpkg -x copy provisioned by tools.sh
    if command -v osmium >/dev/null; then
      OSMIUM=osmium
    else
      "$REPO_ROOT/scripts/geo/tools.sh" >/dev/null
      OSMIUM="$TOOLS_DIR/osmium/usr/bin/osmium"
      export LD_LIBRARY_PATH="$TOOLS_DIR/boostlib/usr/lib/x86_64-linux-gnu:${LD_LIBRARY_PATH:-}"
    fi
    log "clipping to NCR bbox $BBOX (smart strategy keeps boundary ways whole)"
    "$OSMIUM" extract --bbox "$BBOX" --strategy smart \
      --set-bounds --overwrite -o "$BBOX_PBF" "$RAW"
    ;;
  bbbike)
    log "downloading BBBike NewDelhi extract (~37 MB, pre-clipped)"
    curl -fSL --retry 3 -o "$BBOX_PBF" "$BBBIKE_URL"
    ;;
  *) die "unknown EXTRACT_SOURCE=$SRC (geofabrik|bbbike)" ;;
esac

ls -lh "$BBOX_PBF"
log "done: $BBOX_PBF"
