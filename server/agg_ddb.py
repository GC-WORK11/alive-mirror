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
                    token_hash: str, ts: float = None) -> None:
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
        }
        expr = ("ADD trips :one, km :km, dose_ug :d, "
                "co2_kg_mid :c, pm25_g_mid :p, switched :sw")
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
            for c in dict.fromkeys(cells):  # a cell counts once per trip
                self._add_cell(str(c), dose, token_hash, ts, ttl)
            self.last_error = None
        except Exception as e:  # noqa: BLE001 - surface, never silent-loss
            self.last_error = f"{type(e).__name__}: {e}"
            raise

    def _add_cell(self, cell: str, dose: float, token_hash: str,
                  ts: float, ttl: int) -> None:
        expr = "SET last_ts = :ts, #ttl = :ttl ADD #cnt :one, dose_sum :d"
        names = {"#cnt": "count", "#ttl": "ttl"}
        vals = {":ts": _n(round(ts, 3)), ":ttl": _n(ttl),
                ":one": _n(1), ":d": _n(dose)}
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
            out.append({
                "cell": it["pk"]["S"][len("cell#"):],
                "trips": cnt,
                "devices": len(toks),
                "avg_dose_ug": round(_num(it.get("dose_sum")) / cnt, 1)
                if cnt else 0.0,
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
                    "switched": 0, "modes": {}})
                if sk == DAY_SUM_SK:
                    for k in ("trips", "km", "dose_ug", "co2_kg_mid",
                              "pm25_g_mid", "switched"):
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
        for prefix in ("day#", "cell#"):
            for it in self._scan(prefix):
                self.client.delete_item(
                    TableName=self.table_name,
                    Key={"pk": it["pk"], "sk": it["sk"]})


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
