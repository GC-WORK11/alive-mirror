"""Operator-session tests — POST <mount>/login mints an HttpOnly
SameSite=Strict cookie signed with ALIVE_ADMIN_TOKEN; _admin_guard
accepts it everywhere it accepts Bearer. Covered here: login ok/bad/
unconfigured, cookie flags + expiry + rotation, logout, the session
probe, the login rate-limit bucket, and the honest-404 contract on the
old guessable paths. State is signed-stateless — no store to reset
between tests.
"""
import time

from fastapi import FastAPI
from fastapi.testclient import TestClient

import middleware
from admin_mount import ADMIN_MOUNT as M


def _m():
    import main
    return main


def _login_client(monkeypatch, token="test-token-xyz"):
    monkeypatch.setenv("ALIVE_ADMIN_TOKEN", token)
    return TestClient(_m().app)


# --- <mount>/login ------------------------------------------------------------

def test_login_ok_sets_signed_httponly_cookie(monkeypatch):
    c = _login_client(monkeypatch)
    r = c.post(M + "/login", json={"token": "test-token-xyz"})
    assert r.status_code == 200 and r.json()["ok"] is True
    sc = r.headers["set-cookie"]
    assert "alive_admin=" in sc
    assert "httponly" in sc.lower()
    assert "samesite=strict" in sc.lower()
    assert "path=/" in sc.lower()
    assert f"max-age={8 * 3600}" in sc.lower()
    # plain-HTTP request → no Secure flag (NLB :80 today; TLS upgrades it)
    assert "secure" not in sc.lower()
    # cookie shape: v1.<expiry>.<32-hex sig>
    val = sc.split("alive_admin=", 1)[1].split(";", 1)[0]
    ver, exp, sig = val.split(".")
    assert ver == "v1" and len(sig) == 32
    assert int(exp) > int(time.time())


def test_login_secure_flag_only_over_tls(monkeypatch):
    c = _login_client(monkeypatch)
    r = c.post(M + "/login", json={"token": "test-token-xyz"},
               headers={"x-forwarded-proto": "https"})
    assert "secure" in r.headers["set-cookie"].lower()


def test_login_bad_token_401_no_cookie(monkeypatch):
    c = _login_client(monkeypatch)
    for bad in ({"token": "wrong"}, {"token": ""}, {}, {"nope": 1}):
        r = c.post(M + "/login", json=bad)
        assert r.status_code == 401
        assert "set-cookie" not in r.headers


def test_login_unconfigured_503(monkeypatch):
    monkeypatch.delenv("ALIVE_ADMIN_TOKEN", raising=False)
    c = TestClient(_m().app)
    assert c.post(M + "/login",
                  json={"token": "x"}).status_code == 503


# --- the cookie on the guard ------------------------------------------------------

def test_session_cookie_opens_guarded_routes(monkeypatch):
    """The cookie alone (no Bearer) must satisfy _admin_guard — the
    usage rollup and the api root both run it."""
    c = _login_client(monkeypatch)
    c.post(M + "/login", json={"token": "test-token-xyz"})
    assert c.get(M + "/session").json() == {"authenticated": True}
    assert c.get(M + "/api/usage").status_code == 200
    assert c.get(M + "/api").status_code == 200


def test_guest_stays_401(monkeypatch):
    c = _login_client(monkeypatch)
    assert c.get(M + "/session").json() == {"authenticated": False}
    assert c.get(M + "/api/usage").status_code == 401
    assert c.get(M + "/api").status_code == 401


def test_expired_and_tampered_cookies_401(monkeypatch):
    m = _m()
    c = _login_client(monkeypatch)
    # expired but correctly signed — signature valid, time says no
    past = int(time.time()) - 10
    c.cookies.set("alive_admin", f"v1.{past}.{m._session_sign(past)}")
    assert c.get(M + "/api/usage").status_code == 401
    # forged signature / malformed values
    for bad in ("v1.9999999999.deadbeef", "v1.notanint.xx", "garbage",
                "v2.9999999999." + m._session_sign(9999999999)):
        c.cookies.set("alive_admin", bad)
        assert c.get(M + "/api/usage").status_code == 401, bad


def test_token_rotation_kills_sessions(monkeypatch):
    """Cookies are signed under the token itself — rotate the token and
    every outstanding session dies with it."""
    c = _login_client(monkeypatch, token="first-token")
    c.post(M + "/login", json={"token": "first-token"})
    assert c.get(M + "/api/usage").status_code == 200
    monkeypatch.setenv("ALIVE_ADMIN_TOKEN", "rotated-token")
    assert c.get(M + "/api/usage").status_code == 401


def test_logout_clears_cookie(monkeypatch):
    c = _login_client(monkeypatch)
    c.post(M + "/login", json={"token": "test-token-xyz"})
    r = c.post(M + "/logout")
    assert r.status_code == 200
    sc = r.headers["set-cookie"]
    assert "alive_admin=" in sc and ("max-age=0" in sc.lower()
                                   or "expires=" in sc.lower())
    c.cookies.clear()
    assert c.get(M + "/session").json() == {"authenticated": False}


def test_loopback_dev_still_open_without_token(monkeypatch):
    """Token unset → the guard keeps its loopback-only dev default; the
    session probe answers the same question."""
    monkeypatch.delenv("ALIVE_ADMIN_TOKEN", raising=False)
    c = TestClient(_m().app)          # TestClient peer IS loopback
    assert c.get(M + "/session").json() == {"authenticated": True}
    assert c.get(M + "/api/usage").status_code == 200


# --- the login rate-limit bucket --------------------------------------------------

def test_login_rate_limit_kicks_in():
    """The default path table gives <mount>/login its own tight bucket:
    5 tries then 429, socket-peer keyed — and the global budget is
    untouched so the gate can't starve the rest of the API."""
    assert middleware._DEFAULT_PATH_LIMITS[M + "/login"] == (0.2, 5)
    app = FastAPI()

    @app.post(M + "/login")
    async def login():
        return {"ok": True}

    @app.get("/ping")
    async def ping():
        return {"ok": True}

    middleware.attach(app, rate_per_s=100, burst=100)
    c = TestClient(app)
    codes = [c.post(M + "/login", json={"token": "x"}).status_code
             for _ in range(7)]
    assert codes[:5] == [200] * 5
    assert 429 in codes[5:]
    assert c.get("/ping").status_code == 200     # global budget untouched


def test_bearer_still_accepted_for_ops_curl(monkeypatch):
    """Bearer stays for go-nogo health-checks and scripts — the browser
    path is cookie-only, but the guard contract is both."""
    c = _login_client(monkeypatch)
    assert c.get(M + "/api/usage",
                 headers={"Authorization": "Bearer test-token-xyz"}
                 ).status_code == 200


# --- <mount>/in/<token> — the one-link sign-in --------------------------------

def test_in_link_mints_cookie_and_redirects_clean(monkeypatch):
    """GET <mount>/in/<real-token> → 303 to the bare mount + the same
    signed HttpOnly cookie the form mints — the address the operator
    lands on never carries the credential."""
    c = _login_client(monkeypatch)
    r = c.get(M + "/in/test-token-xyz", follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"] == M
    assert "no-store" in r.headers.get("cache-control", "")
    sc = r.headers["set-cookie"]
    assert "alive_admin=v1." in sc and "httponly" in sc.lower()
    assert "samesite=strict" in sc.lower() and "path=/" in sc.lower()
    # the minted session is live — the board answers without re-signing
    assert c.get(M + "/session").json() == {"authenticated": True}
    assert c.get(M + "/api").status_code == 200


def test_in_link_wrong_secret_is_honest_404(monkeypatch):
    """A bad guess is indistinguishable from any unknown URL — same
    status, same body, no cookie. Whether a guess was RIGHT never leaks."""
    c = _login_client(monkeypatch)
    bad = c.get(M + "/in/not-the-token", follow_redirects=False)
    unknown = c.get("/no-such-path", follow_redirects=False)
    assert bad.status_code == 404
    assert bad.json() == unknown.json() == {"detail": "Not Found"}
    assert "set-cookie" not in bad.headers
    assert c.get(M + "/session").json() == {"authenticated": False}


def test_in_link_unconfigured_is_404(monkeypatch):
    """No ALIVE_ADMIN_TOKEN → no secret can ever match → the same
    honest 404 (no 503 'endpoint exists' hint)."""
    monkeypatch.delenv("ALIVE_ADMIN_TOKEN", raising=False)
    c = TestClient(_m().app)
    assert c.get(M + "/in/anything").status_code == 404


def test_in_link_rate_bucket_matches_login():
    """The URL-carried credential gets the login brake: 5 tries then
    429 per socket peer, and the global budget stays untouched."""
    assert middleware._DEFAULT_PATH_LIMITS[M + "/in/"] == (0.2, 5)
    app = FastAPI()

    @app.get(M + "/in/{secret}")
    async def inn(secret: str):
        return {"ok": True}

    @app.get("/ping")
    async def ping():
        return {"ok": True}

    middleware.attach(app, rate_per_s=100, burst=100)
    c = TestClient(app)
    codes = [c.get(M + f"/in/guess{i}").status_code for i in range(7)]
    assert codes[:5] == [200] * 5
    assert 429 in codes[5:]
    assert c.get("/ping").status_code == 200     # global budget untouched


def test_in_link_never_reaches_request_log():
    """The path IS the credential — the structured request log renders
    /in/<redacted>, matched route or not (a near-miss guess would still
    leak ~47/48 chars of the real token)."""
    import json

    import observability
    assert observability._SECRET_PATH_PREFIXES == (M + "/in/",)
    lines = []

    class _Cap:
        def info(self, s):
            lines.append(s)

    mw = observability.RequestLoggingMiddleware(None, logger=_Cap())
    mw._emit("rid", "GET", M + "/in/{secret}",
             M + "/in/test-token-xyz", 303, 1.2, {})
    rec = json.loads(lines[0])
    assert rec["path"] == M + "/in/<redacted>"
    assert "test-token-xyz" not in lines[0]


# --- the page -------------------------------------------------------------------

def test_admin_page_is_cookie_flow_not_token_storage():
    """The served page must carry the gate + cookie login and none of the
    sessionStorage-token machinery the XSS report flagged — and no boot
    strip: the console opens straight into content (hash-login lane)."""
    body = TestClient(_m().app).get(M).text
    assert 'id="gate"' in body and 'id="gateform"' in body
    assert "M+'/login'" in body
    assert "M+'/logout'" in body
    assert "M+'/session'" in body
    assert 'id="boot"' not in body and "alive_boot_v1" not in body
    for dead in ("alive_admin_tok", "prompt(", "sessionStorage.setItem('alive_admin"):
        assert dead not in body, dead


# --- the obscurity contract ---------------------------------------------------

def test_old_admin_paths_are_honest_404s(monkeypatch):
    """The whole point of the mount: nothing answers on the guessable
    paths — no redirect, no 401 hint, just the same 404 any unknown URL
    gets. Probing /admin tells a scanner exactly what /no-such-path does.
    """
    c = _login_client(monkeypatch)
    for p in ("/admin", "/admin/", "/admin.html", "/admin/api",
              "/admin/api/status", "/v2/admin/login", "/v2/admin/logout",
              "/v2/admin/session", "/v2/usage"):
        assert c.get(p).status_code == 404, p
    assert c.post("/v2/admin/login",
                  json={"token": "x"}).status_code == 404


def test_console_page_carries_noindex(monkeypatch):
    """Noindex is a response header + a page meta — the path itself never
    appears in a public robots.txt (that file would hand it to everyone)."""
    c = _login_client(monkeypatch)
    r = c.get(M)
    assert r.headers.get("x-robots-tag") == "noindex, nofollow"
    assert 'name="robots" content="noindex,nofollow"' in r.text
