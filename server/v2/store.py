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
import os
import sys
import threading
import time
import uuid
from typing import Optional

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

    def age_s(self, rid: str) -> Optional[float]:
        """Seconds since a live route_id was issued; None if unknown or
        expired. Lets /v2/strip report the route's age honestly instead
        of implying freshness."""
        with LOCK:
            hit = self._routes.get(rid)
            if not hit:
                return None
            ts, _ = hit
            if time.time() - ts > self._ttl:
                return None
            return round(time.time() - ts, 1)

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
    """Aggregate-only trip store, in-memory backend — dev/CI default.
    `record_trip` takes already-privacized data — H3 cell keys, a hashed
    token, a sanitized summary — so a bug upstream cannot put raw
    coordinates or identity at rest here. `backend` distinguishes it
    from the DynamoDB implementation for /health."""
    backend = "memory"

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


def _select_trips():
    """AGG_TABLE (or ALIVE_DDB_TABLE) set + boto3 + resolvable credentials
    → the DynamoDB aggregate store (agg_ddb.DDBTripAggregates). Anything
    missing → in-memory: dev/CI stays free, /health reads TRIPS.backend
    to show which is live."""
    table = (os.environ.get("AGG_TABLE")
             or os.environ.get("ALIVE_DDB_TABLE") or "").strip()
    if not table:
        return TripAggregates()
    try:
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        import agg_ddb
        b3, why = agg_ddb._aws_ready()
        if b3 is None:
            return TripAggregates()
        return agg_ddb.DDBTripAggregates(table_name=table)
    except Exception:  # noqa: BLE001 — never let backend selection 500 the app
        return TripAggregates()


TRIPS = _select_trips()


class DeviceLedger:
    """Per-device dose/emission history, keyed by the same hashed token
    the aggregates use — /v2/ledger's backend.

    Stores ONLY the sanitized summary fields /v2/trip already accepts
    (km, s, dose_ug, co2/pm25 bands, mode, switched) + a timestamp —
    never cells, never coordinates — so a device can read its own
    history while the community layer stays aggregate-only (k>=3).
    Pseudonymous, not private to us: whoever holds the raw device_token
    reads the ledger; the hash alone links trips to nothing.
    """
    backend = "memory"

    def __init__(self, per_device_cap: int = 300, device_cap: int = 5000):
        self._per_device_cap = per_device_cap
        self._device_cap = device_cap
        self._ledgers: dict = {}   # token_hash -> [{ts, ...summary}]

    def record(self, token_hash: str, summary: dict,
               ts: float = None) -> None:
        if not token_hash:
            return
        ts = ts or time.time()
        with LOCK:
            rows = self._ledgers.setdefault(token_hash, [])
            rows.append({"ts": round(ts, 1), **dict(summary)})
            if len(rows) > self._per_device_cap:
                del rows[:len(rows) - self._per_device_cap]
            if len(self._ledgers) > self._device_cap:
                # evict the least-recently-active device, never the newest
                oldest = min(self._ledgers.items(),
                             key=lambda kv: kv[1][-1]["ts"] if kv[1] else 0)
                self._ledgers.pop(oldest[0], None)

    def trips(self, token_hash: str, limit: int = 200) -> list:
        """Newest-first trip rows for one hashed token."""
        with LOCK:
            rows = list(self._ledgers.get(token_hash) or [])
        return rows[-limit:][::-1]

    def totals(self, token_hash: str) -> dict:
        rows = self.trips(token_hash, limit=self._per_device_cap)

        def _s(k: str) -> float:
            return round(sum(float(r.get(k) or 0.0) for r in rows), 2)

        return {"trips": len(rows), "km": _s("distance_km"),
                "dose_ug": _s("dose_ug"), "co2_kg_mid": _s("co2_kg_mid"),
                "pm25_g_mid": _s("pm25_g_mid")}

    def devices(self) -> int:
        with LOCK:
            return len(self._ledgers)

    def reset(self) -> None:
        with LOCK:
            self._ledgers.clear()


LEDGER = DeviceLedger()
