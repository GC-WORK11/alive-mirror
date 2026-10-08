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
        # Memory bound: every windowed store (_cells/_hours/_areas/_od)
        # evicts entries whose last_ts is past the window — the same
        # 72 h freshness rule the publishable read already applies, so
        # nothing published can change. Without it the in-memory
        # backend (dev/CI, or any deployment without AGG_TABLE) grew
        # _cells and the per-cell token sets forever: a real OOM vector
        # on a small task under sustained donations. Prune runs at most
        # once a minute, amortized inside record_trip's lock.
        self._last_prune = 0.0
        # per-UTC-hour aggregates for the admin live feed — sums plus a
        # distinct hashed-token set, the same k>=3-device contract the
        # corridor cells use. Per-trip rows (ts/mode/dose/km) would
        # collapse to a single person's journey; hour buckets can't.
        self._hours: dict = {}
        # global layer for the console api/global: the donated trip's
        # endpoint AREA (district/sub-district name resolved upstream in
        # v2/trip from the already-trimmed endpoint) — a string, not a
        # coordinate. Distinct hashed devices per area/pair keep the
        # k>=3 publish contract identical to corridor cells.
        self._areas: dict = {}  # origin area -> {trips, devices:set}
        self._od: dict = {}     # (o_area, d_area) -> {trips, devices:set}
        # mutation counter — /v2/city's short payload cache keys on it,
        # so a new donation or a reset can never serve a stale ledger
        # (the DDB backend has no counter; its readers fall back to the
        # cache's TTL, disclosed via 'cached_s').
        self._rev = 0

    def _prune_stale(self, ts: float) -> None:
        """Drop entries dead past the publish window — call with LOCK
        held. 'cells_tracked'/'areas_tracked' then mean 'live in the
        last 72 h', which is what a reader of the corridor map should
        weigh anyway."""
        if ts - self._last_prune < 60.0:
            return
        self._last_prune = ts
        w = self._cell_window_s
        for store in (self._cells, self._areas, self._od):
            for stale in [k for k, v in store.items()
                          if ts - v.get("last_ts", 0.0) > w]:
                del store[stale]

    def record_trip(self, cells: list, summary: dict,
                    token_hash: str, ts: float = None,
                    origin_area: str = None,
                    dest_area: str = None) -> None:
        ts = ts or time.time()
        day = time.strftime("%Y-%m-%d", time.gmtime(ts))
        with LOCK:
            d = self._days.setdefault(day, {
                "trips": 0, "km": 0.0, "dose_ug": 0.0,
                "co2_kg_mid": 0.0, "pm25_g_mid": 0.0,
                "switched": 0, "modes": {},
                "co2_moving_g": 0.0, "co2_idle_g": 0.0,
                "co2_cold_g": 0.0, "co2_split_trips": 0,
                "avoided_ug": 0.0, "avoided_trips": 0,
                "co2_avoided_kg": 0.0, "co2_avoided_trips": 0,
                "last_ts": 0.0})
            # rounded like the DDB backend's write so city_aggregates()
            # parity holds between stores; the newest donation stamp on
            # a day drives 'last shared trip N min ago' surfaces
            d["last_ts"] = max(d["last_ts"], round(ts, 3))
            d["trips"] += 1
            d["km"] += float(summary.get("distance_km") or 0.0)
            d["dose_ug"] += float(summary.get("dose_ug") or 0.0)
            d["co2_kg_mid"] += float(summary.get("co2_kg_mid") or 0.0)
            d["pm25_g_mid"] += float(summary.get("pm25_g_mid") or 0.0)
            for k in ("co2_moving_g", "co2_idle_g", "co2_cold_g"):
                d[k] += float(summary.get(k) or 0.0)
            if any(k in summary
                   for k in ("co2_moving_g", "co2_idle_g", "co2_cold_g")):
                d["co2_split_trips"] += 1
            if summary.get("switched"):
                d["switched"] += 1
            # savings accounting is report-only: a trip donates
            # avoided_ug (router-fastest dose minus taken dose) and/or
            # co2_avoided_kg (vs the fastest option's PUC-calibrated
            # receipt) only when the app actually computed them — the
            # counters count just the trips that reported, so the mean
            # is never diluted by trips that couldn't know
            if summary.get("avoided_ug"):
                d["avoided_ug"] += float(summary["avoided_ug"])
                d["avoided_trips"] += 1
            if (summary.get("co2_avoided_kg")
                    and summary.get("puc_calibrated")):
                d["co2_avoided_kg"] += float(summary["co2_avoided_kg"])
                d["co2_avoided_trips"] += 1
            self._rev += 1
            mode = str(summary.get("mode") or "unknown")[:24]
            d["modes"][mode] = d["modes"].get(mode, 0) + 1
            dose = float(summary.get("dose_ug") or 0.0)
            distinct = list(dict.fromkeys(cells))  # a cell counts once/trip
            km_cell = (float(summary.get("distance_km") or 0.0)
                       / len(distinct)) if distinct else 0.0
            for c in distinct:
                v = self._cells.setdefault(
                    c, {"count": 0, "dose_sum": 0.0, "tokens": set(),
                        "last_ts": 0.0,
                        "co2_kg_sum": 0.0, "km_sum": 0.0,
                        "co2_trips": 0})
                v["count"] += 1
                v["dose_sum"] += dose
                v["last_ts"] = max(v["last_ts"], ts)
                # emission attribution: the trip's km is spread evenly
                # over its distinct cells (the only honest split — cell-
                # level path lengths aren't retained); trips that
                # reported co2_kg_mid add to the intensity index
                v["km_sum"] += km_cell
                if summary.get("co2_kg_mid"):
                    v["co2_kg_sum"] += float(summary["co2_kg_mid"])
                    v["co2_trips"] += 1
                if token_hash:
                    v["tokens"].add(token_hash)
            h = int(ts // 3600)
            hr = self._hours.setdefault(h, {
                "trips": 0, "devices": set(), "dose_ug": 0.0,
                "km": 0.0, "co2_kg_mid": 0.0, "switched": 0,
                "modes": {}, "last_ts": 0.0})
            hr["trips"] += 1
            if token_hash:
                hr["devices"].add(token_hash)
            hr["dose_ug"] += dose
            hr["km"] += float(summary.get("distance_km") or 0.0)
            hr["co2_kg_mid"] += float(summary.get("co2_kg_mid") or 0.0)
            hr["switched"] += 1 if summary.get("switched") else 0
            hr["modes"][mode] = hr["modes"].get(mode, 0) + 1
            hr["last_ts"] = max(hr["last_ts"], ts)
            for stale in [k for k in self._hours
                          if ts - k * 3600 > self._cell_window_s]:
                del self._hours[stale]
            o = str(origin_area or "").replace("#", " ")[:64] or None
            d2 = str(dest_area or "").replace("#", " ")[:64] or None
            if o:
                a = self._areas.setdefault(
                    o, {"trips": 0, "devices": set(), "last_ts": 0.0})
                a["trips"] += 1
                a["last_ts"] = max(a["last_ts"], ts)
                if token_hash:
                    a["devices"].add(token_hash)
            if o and d2:
                pair = self._od.setdefault(
                    (o, d2), {"trips": 0, "devices": set(),
                              "last_ts": 0.0})
                pair["trips"] += 1
                pair["last_ts"] = max(pair["last_ts"], ts)
                if token_hash:
                    pair["devices"].add(token_hash)
            self._prune_stale(ts)

    def _publishable_cells(self, now: float, limit: int) -> list:
        """k>=3-window filter — call with LOCK held (aggregates only)."""
        out = [{
            "cell": c, "trips": v["count"],
            "devices": len(v["tokens"]),
            "avg_dose_ug": round(v["dose_sum"] / v["count"], 1),
            # g emitted per 100 m of corridor by the trips that crossed
            # it — mode-mix implied intensity; None (not 0) when no trip
            # carried a co2 figure or no km was attributed
            "co2_g_per_100m": (round(v["co2_kg_sum"] * 100.0
                                     / v["km_sum"], 1)
                               if v["co2_trips"] and v["km_sum"] > 0
                               else None),
            "co2_trips": v["co2_trips"] or None,
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

    def recent(self, limit: int = 20) -> list:
        """Newest-first UTC-hour aggregates for the admin live feed —
        only hours clearing the corridor k>=3 distinct-device rule.
        Mirrors agg_ddb.DDBTripAggregates.recent's row shape."""
        with LOCK:
            out = []
            for h, r in self._hours.items():
                if len(r["devices"]) < 3:
                    continue
                out.append({
                    "hour": time.strftime("%Y-%m-%d %H:00Z",
                                          time.gmtime(h * 3600)),
                    "ts": r["last_ts"],
                    "trips": r["trips"],
                    "devices": len(r["devices"]),
                    "mode": (max(r["modes"], key=r["modes"].get)
                             if r["modes"] else None),
                    "dose_ug": round(r["dose_ug"], 1),
                    "km": round(r["km"], 1),
                    "co2_kg_mid": round(r["co2_kg_mid"], 3),
                    "switched": r["switched"],
                })
            out.sort(key=lambda e: -e["ts"])
            return out[:limit]

    def hours_window(self, window_s: float, now: float = None) -> dict:
        """Rolling-window sums over the retained UTC-hour aggregates —
        trips/km/dose totals plus the UNIONED distinct-device count.

        Scalar totals only: a window sum is a city figure, not a person,
        so no k-gate applies here (the hour ROWS stay behind recent()'s
        >=3-device rule as before). Covers at most the 72 h retention of
        _hours. Mirrors agg_ddb.DDBTripAggregates.hours_window."""
        now = now or time.time()
        trips = 0
        km = dose = 0.0
        devices = set()
        hours = 0
        with LOCK:
            for h, r in self._hours.items():
                if now - h * 3600 > window_s:
                    continue
                hours += 1
                trips += r["trips"]
                km += r["km"]
                dose += r["dose_ug"]
                devices |= r["devices"]
        return {"trips": trips, "km": round(km, 1),
                "dose_ug": round(dose, 1), "devices": len(devices),
                "hours": hours}

    def trips_per_hour(self, hours: int = 24) -> list:
        """Donations bucketed per UTC hour, oldest→newest — the usage
        sparkline over the ledger's own hour aggregates (mirrors
        community.journeys_per_hour, which reads its corridor subset)."""
        cur = int(time.time() // 3600)
        with LOCK:
            return [self._hours.get(cur - hours + 1 + i, {}).get("trips", 0)
                    for i in range(hours)]

    def global_aggregates(self) -> dict:
        """Everything the console api/global may reveal — area and OD-pair
        rows plus the lifetime savings counters, k>=3 filtered on
        distinct devices exactly like corridor cells. Mirrors
        agg_ddb.DDBTripAggregates.global_aggregates' shape."""
        with LOCK:
            areas = []
            suppressed_areas = 0
            for name, v in self._areas.items():
                if len(v["devices"]) < 3:
                    suppressed_areas += 1
                    continue
                areas.append({"area": name, "trips": v["trips"],
                              "devices": len(v["devices"])})
            areas.sort(key=lambda r: (-r["devices"], -r["trips"]))
            od = []
            suppressed_od = 0
            for (o, d), v in self._od.items():
                if len(v["devices"]) < 3:
                    suppressed_od += 1
                    continue
                od.append({"origin": o, "dest": d, "trips": v["trips"],
                           "devices": len(v["devices"])})
            od.sort(key=lambda r: (-r["trips"], -r["devices"]))
            avoided = 0.0
            avoided_trips = 0
            co2_av = 0.0
            co2_av_trips = 0
            for v in self._days.values():
                avoided += float(v.get("avoided_ug") or 0.0)
                avoided_trips += int(v.get("avoided_trips") or 0)
                co2_av += float(v.get("co2_avoided_kg") or 0.0)
                co2_av_trips += int(v.get("co2_avoided_trips") or 0)
        return {
            "areas": areas,
            "od_pairs": od,
            "avoided": {
                "dose_ug": round(avoided, 1),
                "trips_reporting": avoided_trips,
            } if avoided_trips else None,
            "co2_avoided": {
                "co2_kg": round(co2_av, 2),
                "puc_calibrated_trips": co2_av_trips,
            } if co2_av_trips else None,
            "suppressed": {"areas": suppressed_areas,
                           "od_pairs": suppressed_od},
            "areas_tracked": len(self._areas),
            "od_pairs_tracked": len(self._od),
        }

    def snapshot_cells(self) -> dict:
        """Test/debug view of the cell layer (aggregates, no raw data)."""
        with LOCK:
            return {c: {"count": v["count"], "dose_sum": v["dose_sum"],
                        "devices": len(v["tokens"])}
                    for c, v in self._cells.items()}

    def reset(self) -> None:
        with LOCK:
            self._rev += 1
            self._days.clear()
            self._cells.clear()
            self._areas.clear()
            self._od.clear()
            self._hours.clear()


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
                "pm25_g_mid": _s("pm25_g_mid"),
                "co2_moving_g": _s("co2_moving_g"),
                "co2_idle_g": _s("co2_idle_g"),
                "co2_cold_g": _s("co2_cold_g")}

    def devices(self) -> int:
        with LOCK:
            return len(self._ledgers)

    def device_windows(self, now: float = None) -> dict:
        """Distinct devices by last-donation recency: 24 h / 7 d /
        all-time. 'Seen' = the device's newest ledger row — the ledger
        only ever learns a token when a donation carries it, so these
        count 'devices that shared', never installs.
        Mirrors agg_ddb.DDBDeviceLedger.device_windows."""
        now = now or time.time()
        with LOCK:
            lasts = [max(r["ts"] for r in rows)
                     for rows in self._ledgers.values() if rows]
        return {"total": len(lasts),
                "seen_24h": sum(1 for t in lasts if now - t <= 86400),
                "seen_7d": sum(1 for t in lasts if now - t <= 7 * 86400)}

    def dose_values(self, limit: int = 50000) -> list:
        """Every retained per-trip dose_ug in the ledger — numbers only
        (no keys, no ordering), for aggregate distribution stats.
        Mirrors agg_ddb.DDBDeviceLedger.dose_values."""
        out = []
        with LOCK:
            for rows in self._ledgers.values():
                for r in rows:
                    d = r.get("dose_ug")
                    if isinstance(d, (int, float)):
                        out.append(float(d))
                        if len(out) >= limit:
                            return out
        return out

    def delete(self, token_hash: str) -> int:
        """Drop one device's rows — /v2/ledger DELETE. Returns count."""
        with LOCK:
            rows = self._ledgers.pop(token_hash, None)
        return len(rows) if rows else 0

    def reset(self) -> None:
        with LOCK:
            self._ledgers.clear()


def _select_ledger():
    """Same backend selection as _select_trips: DynamoDB when the env
    table + boto3 + credentials resolve, else in-memory. /health and
    The console reads LEDGER.backend to show which is live."""
    table = (os.environ.get("AGG_TABLE")
             or os.environ.get("ALIVE_DDB_TABLE") or "").strip()
    if not table:
        return DeviceLedger()
    try:
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        import agg_ddb
        b3, why = agg_ddb._aws_ready()
        if b3 is None:
            return DeviceLedger()
        return agg_ddb.DDBDeviceLedger(
            client=b3.client("dynamodb", region_name=agg_ddb._region()),
            table_name=table)
    except Exception:  # noqa: BLE001 — never let backend selection 500 the app
        return DeviceLedger()


LEDGER = _select_ledger()
