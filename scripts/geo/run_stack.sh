#!/usr/bin/env bash
# Run the whole local geo stack: 3x osrm-routed + the FastAPI tile server.
#
#   driving  -> :5001   walking -> :5002   cycling -> :5003
#   tiles    -> FastAPI on :8000 (uvicorn server.main:app, or any app that
#               mounted server/tiles.py — needs ALIVE_PMTILES)
#
# Usage: ./run_stack.sh          # start everything (idempotent)
#        ./run_stack.sh stop     # stop the osrm daemons
#        ./run_stack.sh status   # container + memory status
source "$(dirname "$0")/common.sh"

stop() {
  for mode in driving walking cycling; do
    docker rm -f "alive-osrm-$mode" >/dev/null 2>&1 || true
  done
  log "osrm daemons stopped"
}

status() {
  docker ps --filter "name=alive-osrm-" \
    --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
  docker stats --no-stream --format \
    "table {{.Name}}\t{{.MemUsage}}\t{{.CPUPerc}}" $(docker ps -q --filter "name=alive-osrm-") 2>/dev/null || true
}

case "${1:-start}" in
  stop) stop; exit 0 ;;
  status) status; exit 0 ;;
  start) ;;
  *) die "usage: run_stack.sh [start|stop|status]" ;;
esac

for mode in driving walking cycling; do
  dir="$OSRM_DIR/$mode"
  [[ -f "$dir/delhi.osrm.mldgr" ]] || die "missing graph $dir — run build_osrm.sh first"
  port="${OSRM_PORTS[$mode]}"
  docker rm -f "alive-osrm-$mode" >/dev/null 2>&1 || true
  docker run -d --name "alive-osrm-$mode" \
    -p "$port:5000" -v "$dir:/data" \
    "$OSRM_IMAGE" \
    osrm-routed --algorithm=MLD /data/delhi.osrm >/dev/null
  log "$mode -> http://127.0.0.1:$port (osrm-routed, MLD)"
done

log "waiting for daemons..."
for mode in driving walking cycling; do
  port="${OSRM_PORTS[$mode]}"
  for i in $(seq 1 30); do
    curl -sf "http://127.0.0.1:$port/route/v1/$mode/77.2090,28.6139;77.2190,28.6239" >/dev/null && break
    sleep 1
  done
done
status
cat <<EOF

Stack up. Point the server at it:
  export OSRM_URL=http://127.0.0.1:5001
  export OSRM_URL_DRIVING=http://127.0.0.1:5001
  export OSRM_URL_WALKING=http://127.0.0.1:5002
  export OSRM_URL_CYCLING=http://127.0.0.1:5003
  export ALIVE_PMTILES=$PMTILES
  uvicorn main:app --host 0.0.0.0 --port 8000   # from server/
EOF
