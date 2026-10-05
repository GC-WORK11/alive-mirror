"""GET /v2/archive?day=YYYY-MM-DD&tz=ist — the recorded field.

The timelapse (/grid?h=0..11) replays FORECAST slots. This endpoint
replays what the server RECORDED: the served pm2.5 field, snapshotted
hourly into durable storage by server/archive.py. Every payload carries
basis:"recorded" so history can never be confused with the forecast.

A missing hour is a gap — serialized honestly, never backfilled; a
snapshot the field never served (offline upstream, dead task) simply
does not exist. An archive with no snapshots at all answers
{"hours": []} — the honest 'nothing recorded yet'.
"""
import asyncio
from datetime import date
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

router = APIRouter()


def _parse_day(day: Optional[str]) -> "date":
    import archive as _archive
    if not day:
        from datetime import datetime
        return datetime.now(_archive.IST).date()
    try:
        return date.fromisoformat(day)
    except (TypeError, ValueError):
        raise HTTPException(422, "day must be YYYY-MM-DD")


@router.get("/archive")
async def get_archive(day: Optional[str] = Query(default=None),
                      tz: str = Query(default="ist")):
    """One day's hourly served-field snapshots (downsampled cells) +
    the coverage map: which hours exist, which are honest gaps."""
    if tz.lower() != "ist":
        raise HTTPException(
            422, "tz=ist only — the archive is kept in IST")
    import archive as _archive
    # file/S3 enumeration off the event loop
    return await asyncio.to_thread(_archive.day_payload,
                                   _parse_day(day))
