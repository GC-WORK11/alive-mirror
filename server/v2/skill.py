"""GET /v2/skill — the product grading its own forecast, in public.

Pairs every recorded hour in the archive (basis:recorded snapshots,
server/archive.py) with the forecast surfaces the api had already
served for that hour (/grid?h=, stored inside each snapshot) and
reports per-horizon error: MAE, signed bias, CPCB band hit-rate, and
the honest n behind each number. Buckets with too few realizations
answer {"status":"thin","n":k}; an empty archive answers
{"status":"thin","n":0}. Nothing is smoothed, extrapolated, or
invented — every figure traces to a stored pair.
"""
import asyncio
import concurrent.futures

from fastapi import APIRouter

router = APIRouter()

# Off the event loop, and off the shared default executor too — file/S3
# enumeration + gzip reads would queue behind the cold-boot warm fleet
# for the whole first-minutes window (executor-audit lane). One worker
# is enough for a low-traffic read.
_SKILL_EXEC = concurrent.futures.ThreadPoolExecutor(
    max_workers=1, thread_name_prefix="alive-skill")


@router.get("/skill")
async def get_skill():
    """Per-horizon skill of the served forecast vs the recorded field —
    computed off the durable archive, so 'since Oct 5' is provable."""
    import skill as _skill
    # file/S3 enumeration + gzip reads off the event loop
    return await asyncio.get_running_loop().run_in_executor(
        _SKILL_EXEC, _skill.skill_payload)
