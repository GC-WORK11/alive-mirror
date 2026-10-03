"""Stores for /v2 — in-memory now, DynamoDB-shaped for later.

Two things live here, and nothing else ever may:

1. RouteStore — plan-time route geometries keyed by route_id so
   /v2/strip can re-sample them. Short TTL, they are UI state, not data.

2. TripAggregates — what /v2/trip writes to. Aggregates ONLY: per-day
   mode counters and per-H3-cell traversal counts + dose sums + the set
   of hashed device tokens that feed the k>=3 display threshold
   (docs/plan/07 §3). No raw trajectories, no raw tokens, nothing
   linkable to a person. The class is the interface a DynamoDB table
   (alive108-agg) implements next: same two methods.
"""
import threading
import time
import uuid

LOCK = threading.Lock()


class RouteStore:
    def __init__(self, ttl_s: float = 3600.0, cap: int = 500):
        self._ttl = ttl_s
        self._cap = cap
        self._routes: dict = {}

    def put(self, rec: dict) -> str:
        rid = uuid.uuid4().hex[:12]
        with LOCK:
            self._prune()
            self._routes[rid] = (time.time(), rec)
        return rid

    def get(self, rid: str) -> dict:
        with LOCK:
            hit = self._routes.get(rid)
            if not hit:
                return None
            ts, rec = hit
            if time.time() - ts > self._ttl:
                self._routes.pop(rid, None)
                return None
            return rec

    def _prune(self) -> None:
        if len(self._routes) < self._cap:
            return
        now = time.time()
        dead = [k for k, (ts, _) in self._routes.items()
                if now - ts > self._ttl]
        for k in dead:
            self._routes.pop(k, None)
        if len(self._routes) >= self._cap:
            for k, _ in sorted(self._routes.items(),
                               key=lambda kv: kv[1][0])[:64]:
                self._routes.pop(k, None)


class TripAggregates:
    """Aggregate-only trip store. `record_trip` takes already-privacized
    data — H3 cell keys, a hashed token, a sanitized summary — so a bug
    upstream cannot put raw coordinates or identity at rest here."""

    def __init__(self):
        self._days: dict = {}    # "YYYY-MM-DD" -> day counters
        self._cells: dict = {}   # cell key -> {count, dose_sum, tokens:set}
        self._cell_window_s = 72 * 3600  # corridor rule: 72 h freshness

    def record_trip(self, cells: list, summary: dict,
                    token_hash: str, ts: float = None) -> None:
        ts = ts or time.time()
        day = time.strftime("%Y-%m-%d", time.gmtime(ts))
        with LOCK:
            d = self._days.setdefault(day, {
                "trips": 0, "km": 0.0, "dose_ug": 0.0,
                "co2_kg_mid": 0.0, "pm25_g_mid": 0.0,
                "switched": 0, "modes": {}})
            d["trips"] += 1
            d["km"] += float(summary.get("distance_km") or 0.0)
            d["dose_ug"] += float(summary.get("dose_ug") or 0.0)
            d["co2_kg_mid"] += float(summary.get("co2_kg_mid") or 0.0)
            d["pm25_g_mid"] += float(summary.get("pm25_g_mid") or 0.0)
            if summary.get("switched"):
                d["switched"] += 1
            mode = str(summary.get("mode") or "unknown")[:24]
            d["modes"][mode] = d["modes"].get(mode, 0) + 1
            dose = float(summary.get("dose_ug") or 0.0)
            for c in dict.fromkeys(cells):  # count a cell once per trip
                v = self._cells.setdefault(
                    c, {"count": 0, "dose_sum": 0.0, "tokens": set(),
                        "last_ts": 0.0})
                v["count"] += 1
                v["dose_sum"] += dose
                v["last_ts"] = max(v["last_ts"], ts)
                if token_hash:
                    v["tokens"].add(token_hash)

    def _publishable_cells(self, now: float, limit: int) -> list:
        """k>=3-window filter — call with LOCK held (aggregates only)."""
        out = [{
            "cell": c, "trips": v["count"],
            "devices": len(v["tokens"]),
            "avg_dose_ug": round(v["dose_sum"] / v["count"], 1),
        } for c, v in self._cells.items()
            if len(v["tokens"]) >= 3
            and now - v["last_ts"] <= self._cell_window_s]
        out.sort(key=lambda x: -x["trips"])
        return out[:limit]

    def corridors(self, now: float = None, limit: int = 20) -> list:
        """Cells with >=3 distinct tokens in 72 h — the publishable set."""
        now = now or time.time()
        with LOCK:
            return self._publishable_cells(now, limit)

    def city_aggregates(self) -> dict:
        """Everything /v2/city may reveal — totals only."""
        with LOCK:
            days = {k: {kk: (dict(vv) if kk == "modes" else vv)
                        for kk, vv in v.items()}
                    for k, v in self._days.items()}
            n_pub = len(self._publishable_cells(time.time(), 10 ** 9))
            cells_tracked = len(self._cells)
        return {
            "days": days,
            "cells_tracked": cells_tracked,
            "corridors_publishable": n_pub,
        }

    def snapshot_cells(self) -> dict:
        """Test/debug view of the cell layer (aggregates, no raw data)."""
        with LOCK:
            return {c: {"count": v["count"], "dose_sum": v["dose_sum"],
                        "devices": len(v["tokens"])}
                    for c, v in self._cells.items()}

    def reset(self) -> None:
        with LOCK:
            self._days.clear()
            self._cells.clear()


ROUTES = RouteStore()
TRIPS = TripAggregates()
