"""Geo mirror — ingest_worker.sync_geo_artifacts pulls s3://<air>/geo/*
onto the path tiles.py serves, atomically and honestly. boto3 is faked
in-process; no AWS is touched.
"""
import importlib
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import ingest_worker as iw  # noqa: E402
import tiles  # noqa: E402


class _S3:
    """Tiny s3 fake: head_object + download_file over an in-memory store."""
    def __init__(self, objects):
        self.objects = objects  # key -> bytes

    def head_object(self, Bucket, Key):
        if Key not in self.objects:
            raise RuntimeError("404")
        return {"ContentLength": len(self.objects[Key])}

    def download_file(self, Bucket, Key, dest):
        if Key not in self.objects:
            raise RuntimeError("404")
        with open(dest, "wb") as f:
            f.write(self.objects[Key])


class _B3:
    def __init__(self, objects):
        self._s3 = _S3(objects)

    def client(self, name):
        assert name == "s3"
        return self._s3


def _patch(monkeypatch, tmp_path, objects, bucket="alive108-air"):
    monkeypatch.setenv("ALIVE_AIR_BUCKET", bucket)
    monkeypatch.setenv("ALIVE_PMTILES", str(tmp_path / "geo" / "delhi.pmtiles"))
    monkeypatch.setattr(tiles, "_cache", None)
    importlib.reload(tiles)
    monkeypatch.setattr(iw, "_aws_ready", lambda: (_B3(objects), None))
    return tmp_path / "geo" / "delhi.pmtiles"


def test_no_bucket_skips(monkeypatch):
    monkeypatch.delenv("ALIVE_AIR_BUCKET", raising=False)
    out = iw.sync_geo_artifacts()
    assert out["ok"] is False
    assert out["skipped"] == "no ALIVE_AIR_BUCKET"


def test_unpublished_skips_cleanly(monkeypatch, tmp_path):
    _patch(monkeypatch, tmp_path, {})
    out = iw.sync_geo_artifacts()
    assert out == {"ok": True, "downloaded": [], "skipped": None}


def test_downloads_atomically(monkeypatch, tmp_path):
    dest = _patch(monkeypatch, tmp_path,
                  {"geo/delhi.pmtiles": b"PMTiles-fake"})
    out = iw.sync_geo_artifacts()
    assert out["downloaded"] == ["geo/delhi.pmtiles"]
    assert dest.read_bytes() == b"PMTiles-fake"
    assert not (dest.parent / "delhi.pmtiles.tmp").exists()
    # second run: same size -> skipped, not re-downloaded
    out2 = iw.sync_geo_artifacts()
    assert out2["downloaded"] == []


def test_replaces_when_size_changes(monkeypatch, tmp_path):
    dest = _patch(monkeypatch, tmp_path,
                  {"geo/delhi.pmtiles": b"v2-archive-bytes"})
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(b"old")
    out = iw.sync_geo_artifacts()
    assert out["downloaded"] == ["geo/delhi.pmtiles"]
    assert dest.read_bytes() == b"v2-archive-bytes"


def test_dest_honors_alive_pmtiles_env(monkeypatch, tmp_path):
    _patch(monkeypatch, tmp_path, {"geo/delhi.pmtiles": b"x"})
    iw.sync_geo_artifacts()
    assert (tmp_path / "geo" / "delhi.pmtiles").exists()
