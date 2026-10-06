"""Profiling-only app wrapper for the server-harden lane — NOT shipped.

Prod never carries a snapshot file (data/field/ is docker-ignored), so
it always serves the LIVE krige+IDW path. This box's egress is
rate-limited by open-meteo, so FIELD.refresh can never land a live
sample set here. To time the live serving path honestly we seed
FIELD._samples from real cells of the newest shipped snapshot — the
same (lat, lon, name, {pm2_5}) row shape a successful refresh produces
— and stamp _fetched_at so refresh() hits its own TTL fast-path.

Run:  PYTHONPATH=core/build312:. .venv312/bin/python -m uvicorn \
      tools.lane_live_app:app --port 8015
"""
import time

import airfield
import main as _main

app = _main.app


def _seed_live_field():
    F = airfield.FIELD
    cells = F._snap_centers  # already decoded by load_snapshot warm start
    if not cells:
        return
    # ~80 rows: the same count a real refresh yields (_grid_points ~52
    # + ~24 station rows), so per-call estimator cost matches prod's.
    step = max(1, len(cells) // 80)
    F._samples = [(la, lo, None, {"pm2_5": float(c["pm25"])})
                  for la, lo, c in cells[::step]
                  if c.get("pm25") is not None]
    F._fetched_at = time.time()
    F._source = "open-meteo/cams (lane seed — profiling only)"
    F._snap = None           # force live serving, not snapshot serving
    F._snap_centers = []
    F._snap_fv = None
    F._snap_idx = None
    from core_engine import KF
    KF.fit(F._samples)       # krige on, exactly as refresh() leaves it


_seed_live_field()
