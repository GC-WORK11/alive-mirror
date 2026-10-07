"""GET /v2/ledger — 'what did *I* breathe and emit' per device.

Trip rows the device itself donated via POST /v2/trip, keyed by the same
hashed device_token. Sanitized summaries only — no coordinates, no cells —
so a person's own history is readable by their device alone while the
community map stays aggregate-only (docs/plan/07 §3). Empty ledger is an
honest answer, not an error.
"""
import hashlib
from typing import Optional

from fastapi import APIRouter, Header, HTTPException, Query

from .store import LEDGER

router = APIRouter()


def _token(token: Optional[str], x_device_token: Optional[str]) -> tuple:
    """The device read-key, plus which transport carried it.

    X-Device-Token header preferred — a token in the query string lands
    in uvicorn access logs, browser history and Referer headers (the
    privacy audit caught it there); ?token= stays only as a back-compat
    path for already-shipped clients, and responses that used it are
    marked token_via="query" so the deprecation is honest, not silent.
    """
    t = x_device_token or token
    if not t or len(t) > 64:
        raise HTTPException(422, "device token required "
                                 "(X-Device-Token header)")
    via = "header" if x_device_token else "query"
    return hashlib.sha256(t.encode()).hexdigest()[:16], via


@router.get("/ledger")
async def ledger(token: Optional[str] = Query(default=None),
                 x_device_token: Optional[str] = Header(default=None)):
    token_hash, via = _token(token, x_device_token)
    body = {
        "trips": LEDGER.trips(token_hash),
        "totals": LEDGER.totals(token_hash),
        "devices_tracked": LEDGER.devices(),
        "privacy": ("per-device history — same sanitized summary fields as "
                    "/v2/trip; no coordinates or cells are stored per "
                    "device. Only a holder of the raw device_token reads "
                    "this ledger."),
    }
    if via == "query":
        body["token_via"] = "query"
    return body


@router.delete("/ledger")
async def delete_ledger(token: Optional[str] = Query(default=None),
                        x_device_token: Optional[str] = Header(default=None)):
    """'Delete my data' server half — wipes this device's ledger rows.

    Scope is honest: the per-device trip history keyed by the hashed
    token is deleted outright. Corridor cell counts are NOT touched —
    they are anonymous aggregates (count + dose_sum + a set of hashes),
    linkable to nobody; retracting them would also let a device churn
    fresh 'new device' identities and game the k>=3 threshold.
    """
    token_hash, via = _token(token, x_device_token)
    deleted = LEDGER.delete(token_hash) if hasattr(LEDGER, "delete") else 0
    body = {"deleted": deleted,
            "scope": ("device ledger rows only — corridor aggregates are "
                      "anonymous cell counters and are not retractable")}
    if via == "query":
        body["token_via"] = "query"
    return body
