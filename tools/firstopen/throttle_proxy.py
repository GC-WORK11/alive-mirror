#!/usr/bin/env python3
"""Rate-limited TCP proxy: 127.0.0.1:8790 -> http://65.2.28.40:80

Simulates venue-grade wifi for the app under test. Token-bucket throttle on
each direction independently; rate is settable at runtime via a control port
(8791) so A/B runs share one process:

    curl 127.0.0.1:8791/rate/<bytes_per_sec>     (0 = unthrottled)
    curl 127.0.0.1:8791/stats                  (per-connection totals)

Logs one line per proxied connection: method+path, bytes down/up, seconds.
"""
import asyncio
import sys
import time

UPSTREAM = ("65.2.28.40", 80)
LISTEN = 8790
CTL = 8791

_rate_bps = 0  # bytes/sec; 0 = pass-through
_stats = []


class Bucket:
    def __init__(self):
        self.allowance = 0.0
        self.last = time.monotonic()

    async def take(self, n):
        global _rate_bps
        r = _rate_bps
        if r <= 0:
            return
        # refill
        now = time.monotonic()
        self.allowance = min(self.allowance + (now - self.last) * r, r * 2)
        self.last = now
        if self.allowance >= n:
            self.allowance -= n
            return
        need = (n - self.allowance) / r
        self.allowance = 0
        await asyncio.sleep(need)


async def pump(reader, writer, bucket, tag):
    total = 0
    try:
        while True:
            data = await reader.read(16384)
            if not data:
                break
            total += len(data)
            await bucket.take(len(data))
            writer.write(data)
            await writer.drain()
    except (ConnectionResetError, BrokenPipeError, asyncio.IncompleteReadError):
        pass
    finally:
        try:
            writer.close()
        except Exception:
            pass
    return total


async def handle(cr, cw):
    peer = cw.get_extra_info("peername")
    try:
        ur, uw = await asyncio.open_connection(*UPSTREAM)
    except OSError as e:
        print(f"[proxy] upstream connect fail: {e}", flush=True)
        cw.close()
        return
    down_b, up_b = Bucket(), Bucket()
    t0 = time.monotonic()
    # sniff the request line for the log (peek into first chunk by wrapping pump)
    down_task = asyncio.create_task(pump(ur, cw, down_b, "down"))
    up_task = asyncio.create_task(pump(cr, uw, up_b, "up"))
    results = await asyncio.gather(down_task, up_task, return_exceptions=True)
    dt = time.monotonic() - t0
    _stats.append({"peer": str(peer), "down": results[0] if isinstance(results[0], int) else -1,
                   "up": results[1] if isinstance(results[1], int) else -1, "s": round(dt, 3)})
    print(f"[conn] down={results[0]}B up={results[1]}B {dt:.2f}s rate={_rate_bps}", flush=True)


async def ctl_handle(cr, cw):
    global _rate_bps
    data = await cr.read(4096)
    line = data.decode(errors="replace").splitlines()[0] if data else ""
    body = b"ok\n"
    if "/rate/" in line:
        try:
            _rate_bps = int(line.split("/rate/")[1].split()[0])
        except ValueError:
            body = b"bad rate\n"
        body = f"rate={_rate_bps}\n".encode()
        print(f"[ctl] rate -> {_rate_bps}", flush=True)
    elif "/stats" in line:
        import json
        body = (json.dumps(_stats[-50:]) + "\n").encode()
    cw.write(b"HTTP/1.0 200 OK\r\ncontent-type: text/plain\r\n\r\n" + body)
    await cw.drain()
    cw.close()


async def main():
    await asyncio.start_server(handle, "127.0.0.1", LISTEN)
    await asyncio.start_server(ctl_handle, "127.0.0.1", CTL)
    print(f"[proxy] :{LISTEN} -> {UPSTREAM[0]}:{UPSTREAM[1]} ctl=:{CTL} rate={_rate_bps}B/s", flush=True)
    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
