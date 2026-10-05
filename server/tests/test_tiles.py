"""Local PMTiles tile server — honest absence + Hilbert tile-id math.

The archive itself is a build artifact (scripts/geo pipeline -> S3 ->
task-side geo mirror), never committed, so endpoint tests assert the
honest-503 contract when it's missing and the happy path against a
synthesized minimal archive when building a fixture is cheap enough —
here it is: a hand-rolled v3 header + empty root directory is enough to
exercise _PMTiles init and the 404 branch.
"""
import importlib
import json
import os
import struct
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import tiles  # noqa: E402


# ------------------------------------------------------------ tile ids

def test_zxy_to_tileid_origin():
    # PMTiles Hilbert order: z0 root is 0; z1 fills 1..4 starting at
    # (0,0) down-left, tracing (0,0)->(0,1)->(1,1)->(1,0).
    assert tiles._zxy_to_tileid(0, 0, 0) == 0
    assert tiles._zxy_to_tileid(1, 0, 0) == 1
    assert tiles._zxy_to_tileid(1, 0, 1) == 2
    assert tiles._zxy_to_tileid(1, 1, 1) == 3
    assert tiles._zxy_to_tileid(1, 1, 0) == 4


def test_zxy_to_tileid_connaught_place():
    # CP (77.2167, 28.6315) -> z14/11705/6831 — the doc-verified tile the
    # live lane smokes against; just needs a valid id, value not pinned.
    tid = tiles._zxy_to_tileid(14, 11705, 6831)
    base14 = ((1 << 14) * (1 << 14) - 1) // 3
    base15 = ((1 << 15) * (1 << 15) - 1) // 3
    assert base14 <= tid < base15


def test_zxy_out_of_range():
    with pytest.raises(ValueError):
        tiles._zxy_to_tileid(14, -1, 0)
    with pytest.raises(ValueError):
        tiles._zxy_to_tileid(14, 0, 1 << 14)
    with pytest.raises(ValueError):
        tiles._zxy_to_tileid(27, 0, 0)


# ------------------------------------------------------------ endpoints

def _fresh(monkeypatch, tmp_path, archive_bytes: bytes = None):
    """Point ALIVE_PMTILES at tmp_path (fixture or absent) and reset the
    module's archive cache."""
    p = tmp_path / "delhi.pmtiles"
    if archive_bytes is not None:
        p.write_bytes(archive_bytes)
    monkeypatch.setenv("ALIVE_PMTILES", str(p))
    monkeypatch.setattr(tiles, "_cache", None)
    importlib.reload(tiles)  # clears module-level state honestly
    return p


def _minimal_archive() -> bytes:
    """Smallest well-formed v3 archive: header + a 1-byte root directory
    (n=0 varint). No tiles — every lookup legitimately 404s."""
    root = b"\x00"  # varint n_entries=0
    h = bytearray(127)
    h[:7] = b"PMTiles"
    h[7] = 3
    struct.pack_into("<11Q", h, 8,
                     127, len(root),   # root dir right after header
                     127 + len(root), 0,
                     0, 0,             # no leaf dirs
                     127 + len(root), 0,
                     0, 0, 0)
    struct.pack_into("<6B", h, 96, 1, 1, 2, 1, 0, 14)
    struct.pack_into("<4i", h, 102,
                     768000000, 282000000, 779000000, 289500000)
    h[118] = 12
    struct.pack_into("<2i", h, 119, 772167000, 286315000)
    return bytes(h) + root


def _client(monkeypatch, tmp_path, archive_bytes=None):
    _fresh(monkeypatch, tmp_path, archive_bytes)
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    app = FastAPI()
    app.include_router(tiles.router)
    return TestClient(app)


def test_absent_archive_503s_honestly(monkeypatch, tmp_path):
    c = _client(monkeypatch, tmp_path)
    for path in ("/tiles/health", "/tiles/tilejson.json",
                 "/tiles/delhi/14/11705/6831.mvt",
                 "/tiles/delhi.pmtiles"):
        r = c.get(path)
        assert r.status_code == 503, path
        if "json" in path or "health" in path:
            assert r.json()["error"] == "delhi.pmtiles not built"


def test_corrupt_archive_503s_honestly(monkeypatch, tmp_path):
    # A truncated/random blob must never 500 — the honest signal is the
    # same "not built" 503 as a missing file.
    c = _client(monkeypatch, tmp_path, b"\xde\xad\xbe\xef" * 64)
    assert c.get("/tiles/health").status_code == 503
    assert c.get("/tiles/tilejson.json").status_code == 503


def test_minimal_archive_health_and_404(monkeypatch, tmp_path):
    c = _client(monkeypatch, tmp_path, _minimal_archive())
    h = c.get("/tiles/health")
    assert h.status_code == 200
    body = h.json()
    assert body["zoom"] == [0, 14]
    assert body["bounds"] == [76.8, 28.2, 77.9, 28.95]
    assert body["tile_type"] == 1
    assert body["tile_compression"] == "gzip"
    tj = c.get("/tiles/tilejson.json")
    assert tj.status_code == 200
    assert tj.json()["tiles"] == [
        "http://testserver/tiles/delhi/{z}/{x}/{y}.mvt"]
    # valid archive, empty directory -> miss is a plain 404, not a 503
    assert c.get("/tiles/delhi/14/11705/6831.mvt").status_code == 404


def test_archive_hotswap_on_mtime(monkeypatch, tmp_path):
    # The geo mirror os.replace()s a rebuilt archive — tiles must re-open
    # on mtime/size change without a restart.
    p = _fresh(monkeypatch, tmp_path)
    c = _client(monkeypatch, tmp_path)
    assert c.get("/tiles/health").status_code == 503
    p.write_bytes(_minimal_archive())
    assert c.get("/tiles/health").status_code == 200
    # and back to 503 if the artifact disappears underfoot
    p.unlink()
    assert c.get("/tiles/health").status_code == 503
