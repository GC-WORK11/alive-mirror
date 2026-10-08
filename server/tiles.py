"""Local Delhi vector tiles — serves a PMTiles archive over HTTP.

Self-contained PMTiles v3 reader (no new deps): parses the 127-byte
header, decodes the Hilbert tile-id directories (root + leaf, gzip
internally compressed), and hands out raw tile bytes. Zero AWS, zero
marginal cost; the file is mmap-friendly for the kernel page cache.

Endpoints (all read-only):
  GET /tiles/tilejson.json          TileJSON 3.0 for MapLibre `sources`
  GET /tiles/delhi/{z}/{x}/{y}.mvt  decoded tile (Content-Encoding kept)
  GET /tiles/delhi.pmtiles          raw archive, HTTP Range supported —
                                    browser clients can point the
                                    `pmtiles` npm protocol at this URL
  GET /tiles/health                 artifact presence + header summary

Env:
  ALIVE_PMTILES  path to the archive (default server/data/geo/delhi.pmtiles
                 then repo-root data/geo/delhi.pmtiles)

INTEGRATOR MOUNT NOTE — add to server/main.py beside the /v2 mount:
    try:
        import tiles as _tiles
    except ImportError:
        from server import tiles as _tiles  # package import
    app.include_router(_tiles.router)
Nothing else changes; the router 503s honestly until the archive exists
(scripts/geo/build_tiles.sh).
"""
import gzip
import json
import os
import struct
import sys
import threading
from typing import List, Optional, Tuple

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, JSONResponse, Response

_SERVER_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(_SERVER_DIR)
if _SERVER_DIR not in sys.path:
    sys.path.insert(0, _SERVER_DIR)

router = APIRouter(tags=["tiles"])

# ---------------------------------------------------------------- PMTiles v3

_HEADER_LEN = 127
# PMTiles v3 compression enum: 0=unknown 1=none 2=gzip 3=brotli 4=zstd
_COMP = {0: None, 1: None, 2: "gzip", 3: "br", 4: "zstd"}
_TILE_MIME = {
    0: "application/octet-stream",
    1: "application/vnd.mapbox-vector-tile",  # mvt
    2: "image/png",
    3: "image/jpeg",
    4: "image/webp",
    5: "image/avif",
}
_BOUNDS = (76.80, 28.20, 77.90, 28.95)  # NCR bbox (see v2/deps.NCR_BBOX)


def _varints(buf: bytes, pos: int, n: int) -> Tuple[List[int], int]:
    out = []
    for _ in range(n):
        shift = result = 0
        while True:
            b = buf[pos]
            pos += 1
            result |= (b & 0x7F) << shift
            if not (b & 0x80):
                break
            shift += 7
        out.append(result)
    return out, pos


def _zxy_to_tileid(z: int, x: int, y: int) -> int:
    """PMTiles Hilbert tile id for a z/x/y address."""
    if z > 26 or not (0 <= x < (1 << z)) or not (0 <= y < (1 << z)):
        raise ValueError("zxy out of range")
    base = ((1 << z) * (1 << z) - 1) // 3
    n = 1 << z
    tx, ty, d, s = x, y, 0, n >> 1
    while s:
        rx = 1 if (tx & s) else 0
        ry = 1 if (ty & s) else 0
        d += s * s * ((3 * rx) ^ ry)
        if ry == 0:
            if rx == 1:
                tx, ty = n - 1 - tx, n - 1 - ty
            tx, ty = ty, tx
        s >>= 1
    return base + d


def _decode_dir(buf: bytes) -> List[Tuple[int, int, int, int]]:
    """Directory -> [(tile_id, offset, length, run_length), ...]."""
    (n,), pos = _varints(buf, 0, 1)
    deltas, pos = _varints(buf, pos, n)
    runs, pos = _varints(buf, pos, n)
    lens, pos = _varints(buf, pos, n)
    offs_raw, _ = _varints(buf, pos, n)
    entries, tid, prev_end = [], 0, 0
    for i in range(n):
        tid += deltas[i]
        off = prev_end if offs_raw[i] == 0 else offs_raw[i] - 1
        entries.append((tid, off, lens[i], runs[i]))
        prev_end = off + lens[i]
    return entries


def _decompress(buf: bytes, comp: int) -> bytes:
    if comp == 2:
        return gzip.decompress(buf)
    if comp == 3:
        import brotli  # optional; only needed if archive uses it
        return brotli.decompress(buf)
    if comp == 4:
        import zstandard  # optional
        return zstandard.ZstdDecompressor().decompress(buf)
    return buf


class _PMTiles:
    """Open archive: header + root dir cached; leaf dirs decoded on miss."""

    def __init__(self, path: str):
        self.path = path
        st = os.stat(path)
        self.mtime, self.size = st.st_mtime, st.st_size
        self._fh = open(path, "rb")
        head = self._fh.read(_HEADER_LEN)
        if head[:7] != b"PMTiles" or head[7] != 3:
            raise ValueError(f"{path}: not a PMTiles v3 archive")
        u = struct.unpack_from
        (self.root_off, self.root_len, self.meta_off, self.meta_len,
         self.leaf_off, self.leaf_len, self.tile_off, self.tile_len,
         self.n_tiles, self.n_entries, self.n_contents) = u("<11Q", head, 8)
        (self.clustered, self.int_comp, self.tile_comp, self.tile_type,
         self.min_zoom, self.max_zoom) = u("<6B", head, 96)
        (self.min_lon, self.min_lat, self.max_lon, self.max_lat,
         ) = (v / 1e7 for v in u("<4i", head, 102))
        self.center_zoom = head[118]
        (self.center_lon, self.center_lat) = (v / 1e7 for v in u("<2i", head, 119))
        root = self._fh.read(self.root_len) if self.root_off == _HEADER_LEN else self._read_at(self.root_off, self.root_len)
        self.root = _decode_dir(_decompress(root, self.int_comp))
        self._meta = None
        self._lock = threading.Lock()

    def _read_at(self, off: int, n: int) -> bytes:
        with self._lock:
            self._fh.seek(off)
            return self._fh.read(n)

    def _find(self, entries, tid):
        lo, hi, hit = 0, len(entries) - 1, None
        while lo <= hi:
            mid = (lo + hi) // 2
            e = entries[mid]
            if e[0] <= tid:
                hit = e
                lo = mid + 1
            else:
                hi = mid - 1
        if hit is None:
            return None
        return hit if hit[3] == 0 or tid < hit[0] + hit[3] else None

    def tile(self, z: int, x: int, y: int) -> Optional[bytes]:
        try:
            tid = _zxy_to_tileid(z, x, y)
        except ValueError:
            return None
        e = self._find(self.root, tid)
        if e is None:
            return None
        _, off, ln, run = e
        if run == 0:  # leaf pointer
            raw = _decompress(self._read_at(self.leaf_off + off, ln), self.int_comp)
            e = self._find(_decode_dir(raw), tid)
            if e is None:
                return None
            _, off, ln, run = e
            if run == 0:
                return None
        return self._read_at(self.tile_off + off, ln)

    def metadata(self) -> dict:
        if self._meta is None:
            if self.meta_len:
                raw = _decompress(self._read_at(self.meta_off, self.meta_len), self.int_comp)
                self._meta = json.loads(raw)
            else:
                self._meta = {}
        return self._meta


_cache: Optional[_PMTiles] = None
_cache_lock = threading.Lock()


def _path() -> str:
    return os.environ.get(
        "ALIVE_PMTILES",
        os.path.join(_REPO_ROOT, "data", "geo", "delhi.pmtiles"))


def _archive() -> Optional[_PMTiles]:
    """Cached open archive; re-opens if the file changed. None if absent."""
    global _cache
    p = _path()
    try:
        st = os.stat(p)
    except OSError:
        return None
    with _cache_lock:
        if (_cache is None or _cache.path != p
                or _cache.mtime != st.st_mtime or _cache.size != st.st_size):
            try:
                _cache = _PMTiles(p)
            except Exception:
                return None  # unreadable/partial archive -> honest 503
        return _cache


def _missing() -> JSONResponse:
    return JSONResponse(status_code=503, content={
        "error": "delhi.pmtiles not built",
        "fix": "run scripts/geo/fetch_extract.sh then scripts/geo/build_tiles.sh",
        "expected_path": _path(),
    })


# ---------------------------------------------------------------- endpoints

@router.get("/tiles/tilejson.json")
def tilejson(request: Request):
    a = _archive()
    if a is None:
        return _missing()
    base = str(request.base_url).rstrip("/")
    tj = {
        "tilejson": "3.0.0",
        "name": "Alive Delhi NCR (OpenMapTiles schema)",
        "version": "1.0",
        "scheme": "xyz",
        "format": "pbf",
        "tiles": [f"{base}/tiles/delhi/{{z}}/{{x}}/{{y}}.mvt"],
        "minzoom": a.min_zoom,
        "maxzoom": a.max_zoom,
        "bounds": [a.min_lon, a.min_lat, a.max_lon, a.max_lat],
        "center": [a.center_lon, a.center_lat, a.center_zoom],
        "attribution": "© OpenStreetMap contributors",
    }
    meta = a.metadata()
    if isinstance(meta.get("vector_layers"), list):
        tj["vector_layers"] = meta["vector_layers"]
    for k in ("name", "description", "attribution", "version"):
        if meta.get(k):
            tj[k] = meta[k]
    return tj


@router.get("/tiles/delhi/{z}/{x}/{y}.mvt")
def tile(z: int, x: int, y: int):
    a = _archive()
    if a is None:
        return _missing()
    raw = a.tile(z, x, y)
    if raw is None:
        return Response(status_code=404)
    headers = {}
    if _COMP.get(a.tile_comp):
        headers["Content-Encoding"] = _COMP[a.tile_comp]
    return Response(
        content=raw,
        media_type=_TILE_MIME.get(a.tile_type, "application/octet-stream"),
        headers={**headers, "Cache-Control": "public, max-age=86400"},
    )


@router.get("/tiles/delhi.pmtiles")
def archive_file():
    """Raw archive for `pmtiles://` clients — FileResponse supports Range."""
    p = _path()
    if not os.path.isfile(p):
        return _missing()
    return FileResponse(p, media_type="application/x-pmtiles",
                        filename="delhi.pmtiles")


@router.get("/tiles/health")
def health():
    a = _archive()
    if a is None:
        return _missing()
    return {
        "ok": True,
        "path": a.path,
        "size_mb": round(a.size / 1e6, 1),
        "zoom": [a.min_zoom, a.max_zoom],
        "bounds": [a.min_lon, a.min_lat, a.max_lon, a.max_lat],
        "tile_entries": a.n_entries,
        "addressed_tiles": a.n_tiles,
        "tile_type": a.tile_type,
        "tile_compression": _COMP.get(a.tile_comp),
    }
