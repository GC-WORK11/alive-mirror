"""Landing page serve-path smoke: / + /landing must return the real
page, not a truncated or stale file.

The raster field + live status are assembled in-browser — the only
automatable check is that the served HTML still contains the markers
every piece of that machinery hangs off. A 3KB truncated write, a
missing fetch path, or a placeholder restore fails this loudly.
Design guards: owner rejected capsule buttons, ASCII art and heavy
copy — the FORBIDDEN list keeps the page from drifting back.
"""
import re

from fastapi.testclient import TestClient  # noqa: E402

import main  # noqa: E402

client = TestClient(main.app)

# anchors that make the page what it is: the raster canvas, the
# live fetch paths, the status line, the CPCB band painter, nav links.
REQUIRED = [
    "<canvas",
    "raster",
    "paint",
    "bandCol",
    "/grid",
    "/health",
    "/city",
    "/community",
    "/app-hero-708.webp",
    "hero-grid",
    "statusline",
    "confSplit",
    "fieldAge",
    "buildTag",
    "dosimeter",
    "the app knows what you breathed",
]
# owner-vetoed elements + placeholder guards
FORBIDDEN = [
    "lorem ipsum",
    "TODO",
    "FIXME",
    "placeholder text",
    "border-radius:999px",  # capsule buttons — rejected outright
    "border-radius: 999px",
    "aether",
    "ROUTE_ODS",
]
# landing-only bans (community legitimately links /admin in its nav)
LANDING_FORBIDDEN = FORBIDDEN + [
    "/admin",  # owner: "admin is personal — nothing admin on the marketing page"
]


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
    for bad in LANDING_FORBIDDEN:
        assert bad not in body, f"landing contains placeholder {bad!r}"


def test_landing_script_wellformed():
    """A truncated <script> assembly is how a page 'loads but does
    nothing' — braces must balance and the IIFE tail must be present."""
    body = client.get("/").text
    m = re.search(r"<script>(.*)</script>", body, re.S)
    assert m, "landing has no inline script"
    js = m.group(1)
    assert js.count("{") == js.count("}"), "unbalanced braces in landing JS"
    assert "setInterval" in js, "refresh loop missing"
    assert "fetch(" in js, "live fetch missing"


def test_community_serves_page_to_browsers():
    """/community content-negotiates: browser Accept → the v5 page,
    API clients → the totals JSON the app consumes."""
    html = client.get("/community", headers={"accept": "text/html"})
    assert html.status_code == 200
    assert "text/html" in html.headers.get("content-type", "")
    for marker in ("/community", "lgrid", "corridors", "enough phones", "top_corridors"):
        assert marker in html.text, f"community page lost marker {marker!r}"
    for bad in FORBIDDEN:
        assert bad not in html.text
    js = client.get("/community")
    assert js.status_code == 200
    assert "application/json" in js.headers.get("content-type", "")
    assert "contributors" in js.json()
