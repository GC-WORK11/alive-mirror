"""DynamoDB persistence for the /v2 trip aggregates (docs/plan/05 §4).

`DDBTripAggregates` implements the exact `v2.store.TripAggregates`
interface — record_trip / corridors / city_aggregates / snapshot_cells /
reset — against the `alive108-agg` table provision.sh creates
(PAY_PER_REQUEST, pk/sk, TTL attribute `ttl`). The privacy contract of
docs/plan/07 §3 is preserved end-to-end: only H3 cell keys, the already-
hashed device token, and sanitized summary counters ever touch the table —
the same inputs the in-memory store takes, so a bug upstream cannot put
anything else here. What leaves the store is counts and averages only.

Item layout on the table (composite keys per doc 05):

    pk               sk            attributes
    day#YYYY-MM-DD   sum           trips, km, dose_ug, co2_kg_mid,
                                   pm25_g_mid, switched   (ADD counters)
    day#YYYY-MM-DD   mode#<mode>   same counters, per mode
    cell#<cell-id>   cell          count, dose_sum, tokens (string set of
                                   hashed tokens), last_ts, ttl

TTL only where the doc specifies it: corridor cells get ttl = write + 30d,
refreshed on every traversal; day counters never expire.

Degradation: `get_trip_store()` returns the DDB store when boto3 AND AWS
credentials resolve (same probe as ingest_worker), else the in-memory
TripAggregates — the API shape never changes. Inside the DDB store,
reads degrade to an empty view on failure (a dashboard must not die with
DynamoDB) and set `last_error`; record_trip surfaces the error to the
caller — silently dropping a trip donation would be worse than a 500.

Local dev / tests: pass `client=` (a fake or stubbed DynamoDB client);
`moto`-backed clients work identically.
"""
import os
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from ingest_worker import _aws_ready  # noqa: E402  single credential probe

DEFAULT_TABLE = "alive108-agg"
DEFAULT_REGION = "ap-south-1"   # doc 05 §1: every service lives here
DAY_SUM_SK = "sum"
CELL_SK = "cell"
RECENT_PK = "recent"
GLOBAL_PK = "global"
K_MIN = 3                       # doc 07 §3: publish a cell only with >=3 tokens
CELL_TTL_S = 30 * 86400         # doc 05 §4: corridor cells expire after 30 d
CELL_WINDOW_S = 72 * 3600       # doc 07: k-window is the last 72 h


def _region() -> str:
    return (os.environ.get("AWS_REGION")
            or os.environ.get("AWS_DEFAULT_REGION") or DEFAULT_REGION)


def _n(v) -> dict:
    return {"N": str(v)}


def _num(attr, default=0.0):
    """DDB numeric attr -> int when integral else float (no Decimal leaks)."""
    try:
        f = float((attr or {}).get("N"))
    except (TypeError, ValueError):
        return default
    return int(f) if f.is_integer() else f


class DDBTripAggregates:
    """Aggregate-only trip store on DynamoDB. Same public methods as
    v2.store.TripAggregates; `backend` distinguishes it for /health."""

    backend = "dynamodb"

    def __init__(self, client=None, table_name: str = None):
        self.table_name = (table_name
                           or os.environ.get("AGG_TABLE")
                           or os.environ.get("ALIVE_DDB_TABLE")
                           or DEFAULT_TABLE)
        self._client = client   # None -> resolved lazily via boto3
        self._cell_window_s = CELL_WINDOW_S
        self.last_error = None

    @property
    def client(self):
        if self._client is None:
            import boto3
            self._client = boto3.client("dynamodb", region_name=_region())
        return self._client

    # ------------------------------------------------------------ writes

    def record_trip(self, cells: list, summary: dict,
                    token_hash: str, ts: float = None,
                    origin_area: str = None,
                    dest_area: str = None) -> None:
        ts = ts or time.time()
        day = time.strftime("%Y-%m-%d", time.gmtime(ts))
        mode = str(summary.get("mode") or "unknown")[:24]
        vals = {
            ":one": _n(1),
            ":km": _n(float(summary.get("distance_km") or 0.0)),
            ":d": _n(float(summary.get("dose_ug") or 0.0)),
            ":c": _n(float(summary.get("co2_kg_mid") or 0.0)),
            ":p": _n(float(summary.get("pm25_g_mid") or 0.0)),
            ":sw": _n(1 if summary.get("switched") else 0),
            ":mv": _n(float(summary.get("co2_moving_g") or 0.0)),
            ":id": _n(float(summary.get("co2_idle_g") or 0.0)),
            ":cd": _n(float(summary.get("co2_cold_g") or 0.0)),
            ":st": _n(1 if any(k in summary for k in
                              ("co2_moving_g", "co2_idle_g",
                               "co2_cold_g")) else 0),
            # savings are report-only counters, folded into the same
            # day item: trips that carried avoided_ug and trips that
            # carried a PUC-calibrated co2_avoided_kg each add one
            # reporter count, so readers never divide by trips that
            # couldn't know
            ":av": _n(float(summary.get("avoided_ug") or 0.0)),
            ":avt": _n(1 if summary.get("avoided_ug") else 0),
            ":cav": _n(float(summary.get("co2_avoided_kg") or 0.0)
                       if summary.get("puc_calibrated") else 0.0),
            ":cavt": _n(1 if (summary.get("co2_avoided_kg")
                              and summary.get("puc_calibrated")) else 0),
        }
        expr = ("ADD trips :one, km :km, dose_ug :d, "
                "co2_kg_mid :c, pm25_g_mid :p, switched :sw, "
                "co2_moving_g :mv, co2_idle_g :id, co2_cold_g :cd, "
                "co2_split_trips :st, avoided_ug :av, avoided_trips :avt, "
                "co2_avoided_kg :cav, co2_avoided_trips :cavt")
        pk = f"day#{day}"
        try:
            for sk in (DAY_SUM_SK, f"mode#{mode}"):
                self.client.update_item(
                    TableName=self.table_name,
                    Key={"pk": {"S": pk}, "sk": {"S": sk}},
                    UpdateExpression=expr,
                    ExpressionAttributeValues=vals)
            dose = float(summary.get("dose_ug") or 0.0)
            ttl = int(ts) + CELL_TTL_S
            distinct = list(dict.fromkeys(cells))
            km_cell = (float(summary.get("distance_km") or 0.0)
                       / len(distinct)) if distinct else 0.0
            co2_kg = float(summary.get("co2_kg_mid") or 0.0)
            for c in distinct:  # a cell counts once per trip
                self._add_cell(str(c), dose, token_hash, ts, ttl,
                               km_cell, co2_kg)
            self.last_error = None
        except Exception as e:  # noqa: BLE001 - surface, never silent-loss
            self.last_error = f"{type(e).__name__}: {e}"
            raise
        self._add_recent_hour(ts, summary, token_hash)
        self._add_global(summary, token_hash, origin_area, dest_area)

    def _add_recent_hour(self, ts: float, summary: dict,
                         token_hash: str) -> None:
        """Fold the donation into its UTC-hour aggregate for the admin
        live feed — sk='hour#<h>' carries per-hour sums plus a distinct
        hashed-token set, the same k>=3-device contract corridor cells
        use, so a feed row can never collapse to one trip. The per-trip
        rows this used to write (exact ts + mode + dose + km) WERE a
        single person's journey. Mode counts live on sibling
        'hour#<h>#mode#<m>' items; both expire on the 72 h freshness
        contract. A feed-write failure is recorded but must not sink
        the donation: the counters above already took the truth."""
        h = int(ts // 3600)
        ttl = int(ts) + CELL_WINDOW_S
        try:
            expr = ("SET #ttl = :ttl, last_ts = :ts "
                    "ADD trips :one, dose_ug :d, km :k, "
                    "co2_kg_mid :c, switched :sw")
            vals = {":ttl": _n(ttl), ":ts": _n(round(ts, 3)),
                    ":one": _n(1),
                    ":d": _n(float(summary.get("dose_ug") or 0.0)),
                    ":k": _n(float(summary.get("distance_km") or 0.0)),
                    ":c": _n(float(summary.get("co2_kg_mid") or 0.0)),
                    ":sw": _n(1 if summary.get("switched") else 0)}
            if token_hash:
                # already-hashed upstream — distinct-countable, never
                # linkable; SS union dedupes a device's repeat donations
                expr += ", devices :tok"
                vals[":tok"] = {"SS": [str(token_hash)]}
            self.client.update_item(
                TableName=self.table_name,
                Key={"pk": {"S": RECENT_PK}, "sk": {"S": f"hour#{h}"}},
                UpdateExpression=expr,
                ExpressionAttributeNames={"#ttl": "ttl"},
                ExpressionAttributeValues=vals)
            mode = str(summary.get("mode") or "unknown")[:24]
            self.client.update_item(
                TableName=self.table_name,
                Key={"pk": {"S": RECENT_PK},
                     "sk": {"S": f"hour#{h}#mode#{mode}"}},
                UpdateExpression="SET #ttl = :ttl ADD trips :one",
                ExpressionAttributeNames={"#ttl": "ttl"},
                ExpressionAttributeValues={":ttl": _n(ttl),
                                           ":one": _n(1)})
        except Exception as e:  # noqa: BLE001 - feed is cosmetic, log-only
            self.last_error = f"recent: {type(e).__name__}: {e}"

    def _add_global(self, summary: dict, token_hash: str,
                    origin_area: str, dest_area: str) -> None:
        """The /admin/api/global layer — pk='global' items mirroring the
        memory store's _areas/_od/savings. Area names arrive resolved
        upstream (v2/trip snaps the already-trimmed endpoint to a
        district/sub-district name): a string, never a coordinate. The
        hashed token lands in a devices SS set under the same k>=3
        publish rule as corridor cells. No ttl — lifetime totals, like
        the day counters. A global-write hiccup is log-only: the trip
        truth already landed in the day/cell items."""
        o = str(origin_area or "").replace("#", " ")[:64] or None
        d = str(dest_area or "").replace("#", " ")[:64] or None
        try:
            if o or d or summary.get("avoided_ug") or (
                    summary.get("co2_avoided_kg")
                    and summary.get("puc_calibrated")):
                vals = {":one": _n(1)}
                expr = "ADD trips :one"
                if token_hash:
                    expr += ", devices :tok"
                    vals[":tok"] = {"SS": [str(token_hash)]}
                if o:
                    self.client.update_item(
                        TableName=self.table_name,
                        Key={"pk": {"S": GLOBAL_PK},
                             "sk": {"S": f"area#{o}"}},
                        UpdateExpression=expr,
                        ExpressionAttributeValues=vals)
                if o and d:
                    self.client.update_item(
                        TableName=self.table_name,
                        Key={"pk": {"S": GLOBAL_PK},
                             "sk": {"S": f"od#{o}#{d}"}},
                        UpdateExpression=expr,
                        ExpressionAttributeValues=vals)
            gvals = {}
            gexpr = ""
            if summary.get("avoided_ug"):
                gexpr += " ADD avoided_ug :av, avoided_trips :avt"
                gvals[":av"] = _n(float(summary["avoided_ug"]))
                gvals[":avt"] = _n(1)
            if (summary.get("co2_avoided_kg")
                    and summary.get("puc_calibrated")):
                gexpr += (" ADD " if not gexpr else ", ") + \
                    "co2_avoided_kg :cav, co2_avoided_trips :cavt"
                gvals[":cav"] = _n(float(summary["co2_avoided_kg"]))
                gvals[":cavt"] = _n(1)
            if gvals:
                self.client.update_item(
                    TableName=self.table_name,
                    Key={"pk": {"S": GLOBAL_PK}, "sk": {"S": "sum"}},
                    UpdateExpression=gexpr.strip(),
                    ExpressionAttributeValues=gvals)
        except Exception as e:  # noqa: BLE001 - dashboard cosmetic
            self.last_error = f"global: {type(e).__name__}: {e}"

    def recent(self, limit: int = 20) -> list:
        """Newest-first UTC-hour aggregates for the admin live feed —
        only hours clearing the corridor k>=3 distinct-device rule.
        Legacy 'trip#' rows are ignored (72 h TTL sweeps them)."""
        try:
            hours, modes = {}, {}
            for it in self._scan(RECENT_PK):
                parts = (it.get("sk") or {}).get("S", "").split("#")
                if len(parts) < 2 or parts[0] != "hour":
                    continue
                h = int(parts[1])
                if len(parts) == 2:
                    hours[h] = {
                        "trips": _num(it.get("trips")),
                        "devices": len((it.get("devices") or {})
                                       .get("SS") or []),
                        "dose_ug": _num(it.get("dose_ug")),
                        "km": _num(it.get("km")),
                        "co2_kg_mid": _num(it.get("co2_kg_mid")),
                        "switched": _num(it.get("switched")),
                        "ts": (_num(it.get("last_ts"))
                               or (h + 1) * 3600),
                    }
                elif parts[2] == "mode":
                    modes.setdefault(h, {})["#".join(parts[3:])] = (
                        _num(it.get("trips")))
            out = []
            for h, r in hours.items():
                if r["devices"] < K_MIN:
                    continue
                mm = modes.get(h) or {}
                out.append({
                    "hour": time.strftime("%Y-%m-%d %H:00Z",
                                          time.gmtime(h * 3600)),
                    "ts": r["ts"],
                    "trips": r["trips"],
                    "devices": r["devices"],
                    "mode": max(mm, key=mm.get) if mm else None,
                    "dose_ug": round(float(r["dose_ug"]), 1),
                    "km": round(float(r["km"]), 1),
                    "co2_kg_mid": round(float(r["co2_kg_mid"]), 3),
                    "switched": int(r["switched"] or 0),
                })
            out.sort(key=lambda e: -e["ts"])
            return out[:limit]
        except Exception as e:  # noqa: BLE001 - dashboard degrades, not dies
            self.last_error = f"{type(e).__name__}: {e}"
            return []

    def global_aggregates(self) -> dict:
        """/admin/api/global's read — area rows, OD-pair rows, savings
        counters; same k>=3-on-devices filter and same shape as the
        memory store's. Degrades to the honest-empty shape on failure,
        never a fabricated zero."""
        out = {"areas": [], "od_pairs": [], "avoided": None,
               "co2_avoided": None,
               "suppressed": {"areas": 0, "od_pairs": 0},
               "areas_tracked": 0, "od_pairs_tracked": 0}
        try:
            for it in self._scan(GLOBAL_PK):
                sk = (it.get("sk") or {}).get("S", "")
                if sk == "sum":
                    av_t = int(_num(it.get("avoided_trips")) or 0)
                    if av_t:
                        out["avoided"] = {
                            "dose_ug": round(_num(it.get("avoided_ug")), 1),
                            "trips_reporting": av_t}
                    cav_t = int(_num(it.get("co2_avoided_trips")) or 0)
                    if cav_t:
                        out["co2_avoided"] = {
                            "co2_kg": round(
                                _num(it.get("co2_avoided_kg")), 2),
                            "puc_calibrated_trips": cav_t}
                    continue
                devices = len((it.get("devices") or {}).get("SS") or [])
                trips = int(_num(it.get("trips")) or 0)
                if sk.startswith("area#"):
                    out["areas_tracked"] += 1
                    if devices < K_MIN:
                        out["suppressed"]["areas"] += 1
                        continue
                    out["areas"].append({
                        "area": sk[len("area#"):],
                        "trips": trips, "devices": devices})
                elif sk.startswith("od#"):
                    parts = sk[len("od#"):].split("#")
                    if len(parts) != 2:
                        continue
                    out["od_pairs_tracked"] += 1
                    if devices < K_MIN:
                        out["suppressed"]["od_pairs"] += 1
                        continue
                    out["od_pairs"].append({
                        "origin": parts[0], "dest": parts[1],
                        "trips": trips, "devices": devices})
            out["areas"].sort(key=lambda r: (-r["devices"], -r["trips"]))
            out["od_pairs"].sort(
                key=lambda r: (-r["trips"], -r["devices"]))
            self.last_error = None
        except Exception as e:  # noqa: BLE001 - degrade, dashboard must live
            self.last_error = f"{type(e).__name__}: {e}"
        return out

    def _add_cell(self, cell: str, dose: float, token_hash: str,
                  ts: float, ttl: int, km_cell: float = 0.0,
                  co2_kg: float = 0.0) -> None:
        # even-attribution contract mirrors v2/store.TripAggregates:
        # the trip's km spreads over its distinct cells; co2 accrues
        # only from trips that reported it (a null index is honest
        # absence, never a fake zero)
        expr = ("SET last_ts = :ts, #ttl = :ttl "
                "ADD #cnt :one, dose_sum :d, km_sum :km")
        names = {"#cnt": "count", "#ttl": "ttl"}
        vals = {":ts": _n(round(ts, 3)), ":ttl": _n(ttl),
                ":one": _n(1), ":d": _n(dose), ":km": _n(km_cell)}
        if co2_kg:
            expr += ", co2_kg_sum :co2, co2_trips :co2t"
            vals[":co2"] = _n(co2_kg)
            vals[":co2t"] = _n(1)
        if token_hash:
            # hashed tokens only (v2/trip hashes upstream); empty set is
            # illegal in DDB anyway, so no token -> no set update
            expr += ", tokens :tok"
            vals[":tok"] = {"SS": [token_hash]}
        self.client.update_item(
            TableName=self.table_name,
            Key={"pk": {"S": f"cell#{cell}"}, "sk": {"S": CELL_SK}},
            UpdateExpression=expr,
            ExpressionAttributeNames=names,
            ExpressionAttributeValues=vals)

    # ------------------------------------------------------------- reads

    def _scan(self, pk_prefix: str) -> list:
        """All items whose pk starts with `pk_prefix` (aggregate table —
        a full scan is the honest read at this scale)."""
        out, kw = [], {"TableName": self.table_name}
        while True:
            r = self.client.scan(**kw)
            for it in r.get("Items", []):
                if (it.get("pk") or {}).get("S", "").startswith(pk_prefix):
                    out.append(it)
            lek = r.get("LastEvaluatedKey")
            if not lek:
                return out
            kw["ExclusiveStartKey"] = lek

    def _publishable_cells(self, now: float, limit: int) -> list:
        """k>=3 / 72 h filter — aggregates only, same rule as the
        in-memory store: what leaves here is counts, never tokens."""
        out = []
        for it in self._scan("cell#"):
            toks = (it.get("tokens") or {}).get("SS") or []
            last = _num(it.get("last_ts"))
            if len(toks) < K_MIN or now - last > self._cell_window_s:
                continue
            cnt = _num(it.get("count"), 0)
            co2_trips = int(_num(it.get("co2_trips"), 0))
            km_sum = _num(it.get("km_sum"), 0)
            out.append({
                "cell": it["pk"]["S"][len("cell#"):],
                "trips": cnt,
                "devices": len(toks),
                "avg_dose_ug": round(_num(it.get("dose_sum")) / cnt, 1)
                if cnt else 0.0,
                "co2_g_per_100m": (round(_num(it.get("co2_kg_sum")) * 100.0
                                         / km_sum, 1)
                                   if co2_trips and km_sum > 0 else None),
                "co2_trips": co2_trips or None,
            })
        out.sort(key=lambda x: -x["trips"])
        return out[:limit]

    def corridors(self, now: float = None, limit: int = 20) -> list:
        now = now or time.time()
        try:
            return self._publishable_cells(now, limit)
        except Exception as e:  # noqa: BLE001 - degrade, dashboard must live
            self.last_error = f"{type(e).__name__}: {e}"
            return []

    def city_aggregates(self) -> dict:
        """Everything /v2/city may reveal — totals only."""
        days = {}
        try:
            for it in self._scan("day#"):
                day = it["pk"]["S"][len("day#"):]
                sk = (it.get("sk") or {}).get("S", "")
                d = days.setdefault(day, {
                    "trips": 0, "km": 0.0, "dose_ug": 0.0,
                    "co2_kg_mid": 0.0, "pm25_g_mid": 0.0,
                    "switched": 0, "modes": {},
                    "co2_moving_g": 0.0, "co2_idle_g": 0.0,
                    "co2_cold_g": 0.0, "co2_split_trips": 0,
                    "avoided_ug": 0.0, "avoided_trips": 0,
                    "co2_avoided_kg": 0.0, "co2_avoided_trips": 0})
                if sk == DAY_SUM_SK:
                    for k in ("trips", "km", "dose_ug", "co2_kg_mid",
                              "pm25_g_mid", "switched",
                              "co2_moving_g", "co2_idle_g",
                              "co2_cold_g", "co2_split_trips",
                              "avoided_ug", "avoided_trips",
                              "co2_avoided_kg", "co2_avoided_trips"):
                        d[k] = _num(it.get(k))
                elif sk.startswith("mode#"):
                    d["modes"][sk[len("mode#"):]] = _num(it.get("trips"))
            cells = self._scan("cell#")
            n_pub = len(self._publishable_cells(time.time(), 10 ** 9))
            self.last_error = None
        except Exception as e:  # noqa: BLE001
            self.last_error = f"{type(e).__name__}: {e}"
            cells = []
            n_pub = 0
        return {"days": days, "cells_tracked": len(cells),
                "corridors_publishable": n_pub}

    def snapshot_cells(self) -> dict:
        """Test/debug view of the cell layer (aggregates, no raw data)."""
        try:
            return {
                it["pk"]["S"][len("cell#"):]: {
                    "count": _num(it.get("count")),
                    "dose_sum": _num(it.get("dose_sum")),
                    "devices": len((it.get("tokens") or {}).get("SS") or []),
                }
                for it in self._scan("cell#")
            }
        except Exception as e:  # noqa: BLE001
            self.last_error = f"{type(e).__name__}: {e}"
            return {}

    # ------------------------------------------------------------ debug

    def reset(self) -> None:
        """Drop every aggregate item (dev/test parity with the memory
        store's reset; not wired to any endpoint)."""
        for prefix in ("day#", "cell#", RECENT_PK, GLOBAL_PK):
            for it in self._scan(prefix):
                self.client.delete_item(
                    TableName=self.table_name,
                    Key={"pk": it["pk"], "sk": it["sk"]})


LEDGER_SK_PREFIX = "trip#"
LEDGER_META_PK = "ledger_meta"
LEDGER_TTL_S = 90 * 86400          # per-device rows expire after 90 d


class DDBDeviceLedger:
    """Per-device trip history on DynamoDB — the durable twin of
    v2.store.DeviceLedger (same public methods; `backend` distinguishes
    it for /health and /admin).

    Layout in the shared aggregate table: one item per trip row
      pk = "ledger#<token_hash>"   sk = "trip#<ts>.<seq>"
    plus a device-index item per token
      pk = "ledger_meta"           sk = "device#<token_hash>"
    Reads: trips/totals Query on the device pk (no scan); devices() scans
    only the ledger_meta items. Items carry a ttl attribute so DDB
    expires them; rows store the same sanitized summary fields as
    /v2/trip — never cells, never coordinates.
    """

    backend = "dynamodb"
    per_device_cap = 300

    def __init__(self, client=None, table_name: str = None):
        self.table_name = (table_name
                           or os.environ.get("AGG_TABLE")
                           or os.environ.get("ALIVE_DDB_TABLE")
                           or DEFAULT_TABLE)
        self._client = client
        self.last_error = None

    @property
    def client(self):
        if self._client is None:
            import boto3
            self._client = boto3.client("dynamodb", region_name=_region())
        return self._client

    # ------------------------------------------------------------ writes

    def record(self, token_hash: str, summary: dict,
               ts: float = None) -> None:
        if not token_hash:
            return
        ts = ts or time.time()
        item = {"pk": {"S": f"ledger#{token_hash}"},
                "sk": {"S": f"trip#{ts:.3f}"},
                "ts": _n(round(ts, 3)),
                "ttl": _n(int(ts) + LEDGER_TTL_S)}
        for k, v in (summary or {}).items():
            if isinstance(v, bool):
                item[k] = {"BOOL": v}
            elif isinstance(v, (int, float)):
                item[k] = _n(float(v))
            elif isinstance(v, str):
                item[k] = {"S": v[:64]}
        try:
            self.client.put_item(TableName=self.table_name, Item=item)
            self.client.update_item(
                TableName=self.table_name,
                Key={"pk": {"S": LEDGER_META_PK},
                     "sk": {"S": f"device#{token_hash}"}},
                UpdateExpression="SET last_ts = :ts ADD trips :one",
                ExpressionAttributeValues={
                    ":ts": _n(round(ts, 3)), ":one": _n(1)})
            self.last_error = None
        except Exception as e:  # noqa: BLE001 - surface, never silent-loss
            self.last_error = f"{type(e).__name__}: {e}"
            raise

    # ------------------------------------------------------------- reads

    def _items(self, token_hash: str, limit: int) -> list:
        out, kw = [], {
            "TableName": self.table_name,
            "KeyConditionExpression": "pk = :pk",
            "ExpressionAttributeValues": {
                ":pk": {"S": f"ledger#{token_hash}"}},
            "ScanIndexForward": False,       # newest first
        }
        while len(out) < limit:
            kw["Limit"] = min(200, limit - len(out))
            r = self.client.query(**kw)
            out.extend(r.get("Items", []))
            lek = r.get("LastEvaluatedKey")
            if not lek:
                break
            kw["ExclusiveStartKey"] = lek
        return out

    def _row(self, it: dict) -> dict:
        row = {"ts": _num(it.get("ts"))}
        for k, attr in it.items():
            if k in ("pk", "sk", "ts", "ttl"):
                continue
            if "N" in attr:
                row[k] = _num(attr)
            elif "S" in attr:
                row[k] = attr["S"]
            elif "BOOL" in attr:
                row[k] = attr["BOOL"]
        return row

    def trips(self, token_hash: str, limit: int = 200) -> list:
        try:
            return [self._row(it)
                    for it in self._items(token_hash, limit)]
        except Exception as e:  # noqa: BLE001
            self.last_error = f"{type(e).__name__}: {e}"
            return []

    def totals(self, token_hash: str) -> dict:
        rows = self.trips(token_hash, limit=self.per_device_cap)

        def _s(k: str) -> float:
            return round(sum(float(r.get(k) or 0.0) for r in rows), 2)

        return {"trips": len(rows), "km": _s("distance_km"),
                "dose_ug": _s("dose_ug"), "co2_kg_mid": _s("co2_kg_mid"),
                "pm25_g_mid": _s("pm25_g_mid"),
                "co2_moving_g": _s("co2_moving_g"),
                "co2_idle_g": _s("co2_idle_g"),
                "co2_cold_g": _s("co2_cold_g")}

    def devices(self) -> int:
        try:
            n, kw = 0, {"TableName": self.table_name,
                        "ProjectionExpression": "pk"}
            while True:
                r = self.client.scan(**kw)
                n += sum(1 for it in r.get("Items", [])
                         if (it.get("pk") or {}).get("S") == LEDGER_META_PK)
                lek = r.get("LastEvaluatedKey")
                if not lek:
                    return n
                kw["ExclusiveStartKey"] = lek
        except Exception as e:  # noqa: BLE001
            self.last_error = f"{type(e).__name__}: {e}"
            return 0

    def delete(self, token_hash: str) -> int:
        """Drop one device's ledger rows + its meta counter — /v2/ledger
        DELETE. Trip items are the whole Query page set; the meta row
        lives under LEDGER_META_PK keyed by the same hash."""
        n = 0
        try:
            for it in self._items(token_hash, 10 ** 6):
                self.client.delete_item(
                    TableName=self.table_name,
                    Key={"pk": it["pk"], "sk": it["sk"]})
                n += 1
            self.client.delete_item(
                TableName=self.table_name,
                Key={"pk": {"S": LEDGER_META_PK},
                     "sk": {"S": f"device#{token_hash}"}})
            self.last_error = None
        except Exception as e:  # noqa: BLE001 - surface, never silent-loss
            self.last_error = f"{type(e).__name__}: {e}"
        return n

    def reset(self) -> None:
        """Drop every ledger item (dev/test parity; no endpoint wires it)."""
        for prefix in ("ledger#", LEDGER_META_PK):
            for it in DDBTripAggregates._scan(
                    self, prefix):  # same table, same scan helper
                self.client.delete_item(
                    TableName=self.table_name,
                    Key={"pk": it["pk"], "sk": it["sk"]})


def get_ledger_store(client=None, table_name: str = None):
    """`v2.store.LEDGER`-equivalent factory: DynamoDB when boto3 AND
    credentials resolve, else the in-memory DeviceLedger."""
    if client is not None:
        return DDBDeviceLedger(client=client, table_name=table_name)
    b3, why = _aws_ready()
    if b3 is None:
        from v2.store import DeviceLedger
        return DeviceLedger()
    try:
        return DDBDeviceLedger(
            client=b3.client("dynamodb", region_name=_region()),
            table_name=table_name)
    except Exception:  # noqa: BLE001
        from v2.store import DeviceLedger
        return DeviceLedger()


# ------------------------------------------------------------- factory

def get_trip_store(client=None, table_name: str = None):
    """The store the integrator wires for `v2.store.TRIPS`-equivalent use:
    DynamoDB when boto3 AND credentials resolve, else the in-memory
    TripAggregates — never a construction-time crash."""
    if client is not None:
        return DDBTripAggregates(client=client, table_name=table_name)
    b3, why = _aws_ready()
    if b3 is None:
        from v2.store import TripAggregates
        return TripAggregates()
    try:
        return DDBTripAggregates(
            client=b3.client("dynamodb", region_name=_region()),
            table_name=table_name)
    except Exception:  # noqa: BLE001 - e.g. dynamodb endpoint unavailable
        from v2.store import TripAggregates
        return TripAggregates()


if __name__ == "__main__":
    import json
    s = get_trip_store()
    print(json.dumps({
        "backend": getattr(s, "backend", "in-memory"),
        "table": getattr(s, "table_name", None),
        "env_ALIVE_DDB_TABLE": os.environ.get("ALIVE_DDB_TABLE"),
    }, indent=1))
