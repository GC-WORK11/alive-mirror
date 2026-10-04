#!/usr/bin/env bash
# Provision local toolchain into data/geo/tools/ — idempotent.
#   osmium-tool : Ubuntu .deb downloaded + dpkg -x (no root needed)
#   planetiler  : fat jar (needs java >= 17 on PATH)
# Usage: ./tools.sh          # ensure everything
source "$(dirname "$0")/common.sh"

mkdir -p "$TOOLS_DIR" "$TOOLS_DIR/osmium" "$TOOLS_DIR/boostlib"

# --- osmium-tool -------------------------------------------------------------
# system package wins (CodeBuild apt-installs it); else apt download +
# dpkg -x into tools/ — the no-root path for dev machines.
OSMIUM_BIN="$TOOLS_DIR/osmium/usr/bin/osmium"
if command -v osmium >/dev/null; then
  echo "osmium: $(command -v osmium) (system)"
else
  if [[ ! -x "$OSMIUM_BIN" ]]; then
    log "osmium-tool: apt download + dpkg -x (no root)"
    tmp=$(mktemp -d)
    # boost package name varies across Ubuntu releases (1.74 jammy /
    # 1.83 noble) — resolve whatever the apt repo offers
    BOOST_PKG="$(apt-cache search '^libboost-program-options[0-9.]+$' \
      | awk '{print $1}' | sort -V | tail -1)"
    (cd "$tmp" && apt-get download osmium-tool "$BOOST_PKG" >/dev/null)
    for deb in "$tmp"/osmium-tool_*.deb; do dpkg -x "$deb" "$TOOLS_DIR/osmium"; done
    for deb in "$tmp"/libboost-program-options*_*.deb; do dpkg -x "$deb" "$TOOLS_DIR/boostlib"; done
    rm -rf "$tmp"
  fi
  export LD_LIBRARY_PATH="$TOOLS_DIR/boostlib/usr/lib/x86_64-linux-gnu:${LD_LIBRARY_PATH:-}"
  "$OSMIUM_BIN" --version >/dev/null || die "osmium-tool failed to run"
  echo "osmium: $OSMIUM_BIN"
fi

# --- planetiler --------------------------------------------------------------
if [[ ! -s "$PLANETILER_JAR" ]]; then
  log "planetiler: downloading fat jar"
  curl -fSL --retry 3 -o "$PLANETILER_JAR" "$PLANETILER_URL"
fi
command -v java >/dev/null || die "java not found (need >= 17)"
echo "planetiler: $PLANETILER_JAR"

# --- docker images -----------------------------------------------------------
if ! docker image inspect "$OSRM_IMAGE" >/dev/null 2>&1; then
  log "docker pull $OSRM_IMAGE"
  docker pull "$OSRM_IMAGE"
fi
echo "osrm image: $OSRM_IMAGE"
