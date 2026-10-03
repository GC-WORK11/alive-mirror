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
