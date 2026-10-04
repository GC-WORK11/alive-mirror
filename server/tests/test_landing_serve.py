"""Landing page serve-path smoke: / + /landing must return the real
page, not a truncated or stale file.

The aether + live-data cards are assembled in-browser — the only
automatable check is that the served HTML still contains the markers
every piece of that machinery hangs off. A 3KB truncated write, a
missing fetch path, or a placeholder restore fails this loudly.
"""
import re

from fastapi.testclient import TestClient  # noqa: E402

import main  # noqa: E402

client = TestClient(main.app)

# anchors that make the page what it is: the canvas, the live fetch
# paths, the OD rotation, the shared plan fetch, the indexing axis.
REQUIRED = [
    "<canvas",
    "ROUTE_ODS",
    "renderDose",
    "drawAether",
    "FIELD_BBOX",
    "/v2/plan",
    "/v2/reverse",
    "/community",
    "/health",
    "aether-axis",
    "hotTxt",
]
FORBIDDEN = ["lorem ipsum", "TODO", "FIXME", "placeholder text"]


def test_root_serves_landing():
    r = client.get("/")
    assert r.status_code == 200
    assert "text/html" in r.headers.get("content-type", "")
    assert "<title>" in r.text and "lungs" in r.text.lower()


def test_landing_alias_same_payload():
    a, b = client.get("/"), client.get("/landing")
    assert a.status_code == 200 and b.status_code == 200
    assert a.text == b.text


def test_landing_machinery_intact():
    body = client.get("/").text
    missing = [s for s in REQUIRED if s not in body]
    assert not missing, f"landing lost markers: {missing}"
    for bad in FORBIDDEN:
        assert bad not in body, f"landing contains placeholder {bad!r}"


def test_landing_script_wellformed():
    """A truncated <script> assembly is how a page 'loads but does
    nothing' — braces must balance and the IIFE tail must be present."""
    body = client.get("/").text
    m = re.search(r"<script>(.*)</script>", body, re.S)
    assert m, "landing has no inline script"
    js = m.group(1)
    assert js.count("{") == js.count("}"), "unbalanced braces in landing JS"
    assert "requestAnimationFrame" in js, "render loop missing"
