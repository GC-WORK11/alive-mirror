"""GET /v2/ledger — 'what did *I* breathe and emit' per device.

Trip rows the device itself donated via POST /v2/trip, keyed by the same
hashed device_token. Sanitized summaries only — no coordinates, no cells —
so a person's own history is readable by their device alone while the
community map stays aggregate-only (docs/plan/07 §3). Empty ledger is an
honest answer, not an error.
"""
import hashlib

from fastapi import APIRouter, Query

from .store import LEDGER

router = APIRouter()


@router.get("/ledger")
async def ledger(token: str = Query(min_length=1, max_length=64)):
    token_hash = hashlib.sha256(token.encode()).hexdigest()[:16]
    return {
        "trips": LEDGER.trips(token_hash),
        "totals": LEDGER.totals(token_hash),
        "devices_tracked": LEDGER.devices(),
        "privacy": ("per-device history — same sanitized summary fields as "
                    "/v2/trip; no coordinates or cells are stored per "
                    "device. Only a holder of the raw device_token reads "
                    "this ledger."),
    }


@router.delete("/ledger")
async def delete_ledger(token: str = Query(min_length=1, max_length=64)):
    """'Delete my data' server half — wipes this device's ledger rows.

    Scope is honest: the per-device trip history keyed by the hashed
    token is deleted outright. Corridor cell counts are NOT touched —
    they are anonymous aggregates (count + dose_sum + a set of hashes),
    linkable to nobody; retracting them would also let a device churn
    fresh 'new device' identities and game the k>=3 threshold.
    """
    token_hash = hashlib.sha256(token.encode()).hexdigest()[:16]
    deleted = LEDGER.delete(token_hash) if hasattr(LEDGER, "delete") else 0
    return {"deleted": deleted,
            "scope": ("device ledger rows only — corridor aggregates are "
                      "anonymous cell counters and are not retractable")}
