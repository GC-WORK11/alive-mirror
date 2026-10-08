#!/usr/bin/env bash
# Common config for the Alive Delhi geo pipeline. Source this.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
GEO_DIR="${ALIVE_GEO_DIR:-$REPO_ROOT/data/geo}"
TOOLS_DIR="$GEO_DIR/tools"
OSRM_DIR="$GEO_DIR/osrm"

# NCR bbox — must match server/v2/deps.py NCR_BBOX (lon/lat W,S,E,N)
BBOX="76.80,28.20,77.90,28.95"
BBOX_PBF="$GEO_DIR/delhi-ncr.osm.pbf"
PMTILES="$GEO_DIR/delhi.pmtiles"

PLANETILER_JAR="$TOOLS_DIR/planetiler.jar"
PLANETILER_URL="https://github.com/onthegomap/planetiler/releases/download/v0.10.2/planetiler.jar"

GEOFABRIK_URL="https://download.geofabrik.de/asia/india/northern-zone-latest.osm.pbf"
BBBIKE_URL="https://download.bbbike.org/osm/bbbike/NewDelhi/NewDelhi.osm.pbf"

OSRM_IMAGE="${OSRM_IMAGE:-osrm/osrm-backend:latest}"
# profile lua path inside the osrm image -> local port
declare -A OSRM_PROFILES=([driving]=car [walking]=foot [cycling]=bicycle)
declare -A OSRM_PORTS=([driving]=5001 [walking]=5002 [cycling]=5003)

log() { printf '\033[1;34m[geo]\033[0m %s\n' "$*"; }
die() { printf '\033[1;31m[geo] ERROR:\033[0m %s\n' "$*" >&2; exit 1; }
