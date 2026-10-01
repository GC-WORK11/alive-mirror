# FIRMS setup (2 min, free)

1. Register at https://firms.modaps.eosdis.nasa.gov/api/area/ → "Get MAP_KEY"
2. You get a key by email instantly.
3. `export FIRMS_MAP_KEY=<key>` before starting the server.

Dataset used: VIIRS_SNPP_NRT (375m, <3h latency, global).
Without the key, `server/fires.py` degrades to modifier=1.0 and an empty
fires layer — no fabricated detections.
