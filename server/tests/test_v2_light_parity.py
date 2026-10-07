"""/v2-light.json — the basemap style the server hosts for the mobile
offline pack.

The app's OfflineManager.createPack needs an http(s) style_url (the
native fetcher rejects file://), so the server serves a byte-identical
copy of the bundled Mobile/src/map/v2-light.json. If the two ever drift,
the pack warms resources for a different style than the one the map
renders — a silent offline-map bug. This test pins:

  * the route serves the copy, as JSON, cacheable;
  * the copy is byte-identical to the app's bundled style;
  * it still carries every remote resource class the pack fetcher has
    to resolve (vector TileJSON source, glyphs, sprite).

Run from server/:
    .venv/bin/python -m pytest tests/test_v2_light_parity.py -v
"""
import json
import os

from fastapi.testclient import TestClient  # noqa: E402

import main  # noqa: E402

client = TestClient(main.app)

_SERVER = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_REPO = os.path.dirname(_SERVER)
SERVED = os.path.join(_SERVER, "static", "v2-light.json")
BUNDLED = os.path.join(_REPO, "Mobile", "src", "map", "v2-light.json")


def test_route_serves_style_json():
    r = client.get("/v2-light.json")
    assert r.status_code == 200
    assert "application/json" in r.headers.get("content-type", "")
    assert "max-age" in r.headers.get("cache-control", "")
    style = r.json()
    assert style["version"] == 8


def test_served_copy_matches_bundled_bytes():
    assert os.path.exists(BUNDLED), "Mobile bundled style missing"
    assert os.path.exists(SERVED), "server copy missing"
    with open(SERVED, "rb") as f:
        served = f.read()
    with open(BUNDLED, "rb") as f:
        bundled = f.read()
    assert served == bundled, (
        "server/static/v2-light.json drifted from "
        "Mobile/src/map/v2-light.json — the offline pack would warm a "
        "different style than the map renders"
    )


def test_style_carries_pack_resources():
    """The pack fetcher resolves these to decide what to download —
    lose one and the region silently comes up short."""
    style = json.load(open(SERVED))
    src = style["sources"]["openmaptiles"]
    assert src["type"] == "vector"
    assert src["url"].startswith("https://"), src["url"]
    assert style["glyphs"].startswith("https://")
    assert style["sprite"].startswith("https://")
