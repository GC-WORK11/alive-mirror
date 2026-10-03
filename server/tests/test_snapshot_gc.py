"""Offline tests for snapshot_gc — fake S3, tmp dirs, zero AWS.

Covers the whole degrade matrix the lane requires: no boto3/creds and no
ALIVE_AIR_BUCKET -> dry-run that touches nothing; apply -> local->S3 sync
then retention prune; a failed upload is never deleted.
Run from server/:  .venv/bin/python -m pytest tests/test_snapshot_gc.py -v
"""
import gzip
import os
import sys
import time

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import snapshot_gc  # noqa: E402


class FakeS3:
    def __init__(self, objects=None, fail_puts=()):
        self.objects = dict(objects or {})
        self.fail_puts = set(fail_puts)
        self.puts = []

    def list_objects_v2(self, Bucket, Prefix, **kw):
        return {"IsTruncated": False,
                "Contents": [{"Key": k} for k in sorted(self.objects)
                             if k.startswith(Prefix)]}

    def put_object(self, Bucket, Key, Body, **kw):
        self.puts.append(Key)
        if Key in self.fail_puts:
            raise RuntimeError("injected put failure")
        self.objects[Key] = Body
        return {}


def _snap(root, rel="2026/09/20/1200.json.gz", age_days=10):
    p = os.path.join(str(root), *rel.split("/"))
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with gzip.open(p, "wb") as f:
        f.write(b'{"cells":{}}')
    old = time.time() - age_days * 86400
    os.utime(p, (old, old))
    return p


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    monkeypatch.delenv("ALIVE_AIR_BUCKET", raising=False)
    monkeypatch.delenv("ALIVE_SNAPSHOT_DIR", raising=False)
    monkeypatch.delenv("ALIVE_SNAPSHOT_KEEP_DAYS", raising=False)
    monkeypatch.delenv("ALIVE_GC_APPLY", raising=False)
    monkeypatch.setattr(snapshot_gc, "_aws_ready",
                        lambda: (None, "forced offline"))


# ------------------------------------------------------------------- plan

def test_plan_reports_and_dry_run_is_inert(tmp_path):
    old = _snap(tmp_path, age_days=10)
    new = _snap(tmp_path, "2026/10/02/0900.json.gz", age_days=0.1)
    s3 = FakeS3()
    p = snapshot_gc.plan(root=str(tmp_path), bucket="b", s3_client=s3)
    assert p["files"] == 2 and p["dry_run"] is True
    assert {f["key"] for f in p["to_upload"]} == {
        "field/2026/09/20/1200.json.gz", "field/2026/10/02/0900.json.gz"}
    assert [f["key"] for f in p["to_delete"]] == [
        "field/2026/09/20/1200.json.gz"]
    r = snapshot_gc.run_gc(root=str(tmp_path), bucket="b", s3_client=s3)
    assert r["dry_run"] is True and r["apply"] is False
    assert s3.puts == [] and s3.objects == {}
    assert os.path.exists(old) and os.path.exists(new)


def test_apply_syncs_then_prunes(tmp_path):
    old = _snap(tmp_path, age_days=10)
    new = _snap(tmp_path, "2026/10/02/0900.json.gz", age_days=0.1)
    s3 = FakeS3()
    r = snapshot_gc.run_gc(root=str(tmp_path), bucket="b", s3_client=s3,
                           apply=True)
    assert sorted(r["uploaded"]) == [
        "field/2026/09/20/1200.json.gz", "field/2026/10/02/0900.json.gz"]
    assert r["deleted"] == [old]
    assert not os.path.exists(old) and os.path.exists(new)
    assert set(s3.objects) == set(r["uploaded"])


def test_already_archived_skips_upload_still_prunes(tmp_path):
    old = _snap(tmp_path, age_days=10)
    s3 = FakeS3(objects={"field/2026/09/20/1200.json.gz": b"x"})
    r = snapshot_gc.run_gc(root=str(tmp_path), bucket="b", s3_client=s3,
                           apply=True)
    assert r["uploaded"] == [] and s3.puts == []
    assert r["deleted"] == [old] and r["already_in_s3"] == 1


def test_failed_upload_never_deleted(tmp_path):
    old = _snap(tmp_path, age_days=10)
    s3 = FakeS3(fail_puts={"field/2026/09/20/1200.json.gz"})
    r = snapshot_gc.run_gc(root=str(tmp_path), bucket="b", s3_client=s3,
                           apply=True)
    assert r["uploaded"] == [] and r["deleted"] == []
    assert r["errors"] and "injected put failure" in r["errors"][0]
    assert os.path.exists(old)  # the only copy survives


# ---------------------------------------------------------------- degrade

def test_no_bucket_dry_run_and_no_deletes(tmp_path):
    old = _snap(tmp_path, age_days=365)
    r = snapshot_gc.run_gc(root=str(tmp_path), apply=True)
    assert r["note"] and "ALIVE_AIR_BUCKET unset" in r["note"]
    assert r["uploaded"] == [] and r["deleted"] == []
    assert os.path.exists(old)
    assert r["protected"]  # reported, not touched


def test_bucket_but_no_boto3_protects(tmp_path):
    # _aws_ready forced offline by the fixture -> s3 unresolvable
    old = _snap(tmp_path, age_days=365)
    r = snapshot_gc.run_gc(root=str(tmp_path), bucket="b", apply=True)
    assert "bucket set but" in r["note"]
    assert "nothing synced or deleted" in r["note"]
    assert r["uploaded"] == [] and r["deleted"] == []
    assert os.path.exists(old)


def test_keep_days_param_and_env(tmp_path, monkeypatch):
    _snap(tmp_path, age_days=2)
    s3 = FakeS3()
    p = snapshot_gc.plan(root=str(tmp_path), bucket="b", keep_days=30,
                         s3_client=s3)
    assert p["to_delete"] == []
    monkeypatch.setenv("ALIVE_SNAPSHOT_KEEP_DAYS", "1")
    p = snapshot_gc.plan(root=str(tmp_path), bucket="b", s3_client=s3)
    assert len(p["to_delete"]) == 1 and p["keep_days"] == 1.0


def test_handler_is_dry_run_without_apply(tmp_path):
    old = _snap(tmp_path, age_days=10)
    r = snapshot_gc.handler({"root": str(tmp_path)})
    assert r["dry_run"] is True and os.path.exists(old)
    r = snapshot_gc.handler({"root": str(tmp_path), "apply": True})
    # bucket unset -> still nothing deleted (only copy protected)
    assert r["deleted"] == [] and os.path.exists(old)
