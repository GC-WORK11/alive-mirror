"""Operator-session tests — POST /v2/admin/login mints an HttpOnly
SameSite=Strict cookie signed with ALIVE_ADMIN_TOKEN; _admin_guard
accepts it everywhere it accepts Bearer. Covered here: login ok/bad/
unconfigured, cookie flags + expiry + rotation, logout, the session
probe, and the login rate-limit bucket. State is signed-stateless — no
store to reset between tests.
"""
import time

from fastapi import FastAPI
from fastapi.testclient import TestClient

import middleware


def _m():
    import main
    return main


def _login_client(monkeypatch, token="test-token-xyz"):
    monkeypatch.setenv("ALIVE_ADMIN_TOKEN", token)
    return TestClient(_m().app)


# --- /v2/admin/login ------------------------------------------------------------

def test_login_ok_sets_signed_httponly_cookie(monkeypatch):
    c = _login_client(monkeypatch)
    r = c.post("/v2/admin/login", json={"token": "test-token-xyz"})
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
    r = c.post("/v2/admin/login", json={"token": "test-token-xyz"},
               headers={"x-forwarded-proto": "https"})
    assert "secure" in r.headers["set-cookie"].lower()


def test_login_bad_token_401_no_cookie(monkeypatch):
    c = _login_client(monkeypatch)
    for bad in ({"token": "wrong"}, {"token": ""}, {}, {"nope": 1}):
        r = c.post("/v2/admin/login", json=bad)
        assert r.status_code == 401
        assert "set-cookie" not in r.headers


def test_login_unconfigured_503(monkeypatch):
    monkeypatch.delenv("ALIVE_ADMIN_TOKEN", raising=False)
    c = TestClient(_m().app)
    assert c.post("/v2/admin/login",
                  json={"token": "x"}).status_code == 503


# --- the cookie on the guard ------------------------------------------------------

def test_session_cookie_opens_guarded_routes(monkeypatch):
    """The cookie alone (no Bearer) must satisfy _admin_guard — /v2/usage
    and /admin/api both run it."""
    c = _login_client(monkeypatch)
    c.post("/v2/admin/login", json={"token": "test-token-xyz"})
    assert c.get("/v2/admin/session").json() == {"authenticated": True}
    assert c.get("/v2/usage").status_code == 200
    assert c.get("/admin/api").status_code == 200


def test_guest_stays_401(monkeypatch):
    c = _login_client(monkeypatch)
    assert c.get("/v2/admin/session").json() == {"authenticated": False}
    assert c.get("/v2/usage").status_code == 401
    assert c.get("/admin/api").status_code == 401


def test_expired_and_tampered_cookies_401(monkeypatch):
    m = _m()
    c = _login_client(monkeypatch)
    # expired but correctly signed — signature valid, time says no
    past = int(time.time()) - 10
    c.cookies.set("alive_admin", f"v1.{past}.{m._session_sign(past)}")
    assert c.get("/v2/usage").status_code == 401
    # forged signature / malformed values
    for bad in ("v1.9999999999.deadbeef", "v1.notanint.xx", "garbage",
                "v2.9999999999." + m._session_sign(9999999999)):
        c.cookies.set("alive_admin", bad)
        assert c.get("/v2/usage").status_code == 401, bad


def test_token_rotation_kills_sessions(monkeypatch):
    """Cookies are signed under the token itself — rotate the token and
    every outstanding session dies with it."""
    c = _login_client(monkeypatch, token="first-token")
    c.post("/v2/admin/login", json={"token": "first-token"})
    assert c.get("/v2/usage").status_code == 200
    monkeypatch.setenv("ALIVE_ADMIN_TOKEN", "rotated-token")
    assert c.get("/v2/usage").status_code == 401


def test_logout_clears_cookie(monkeypatch):
    c = _login_client(monkeypatch)
    c.post("/v2/admin/login", json={"token": "test-token-xyz"})
    r = c.post("/v2/admin/logout")
    assert r.status_code == 200
    sc = r.headers["set-cookie"]
    assert "alive_admin=" in sc and ("max-age=0" in sc.lower()
                                   or "expires=" in sc.lower())
    c.cookies.clear()
    assert c.get("/v2/admin/session").json() == {"authenticated": False}


def test_loopback_dev_still_open_without_token(monkeypatch):
    """Token unset → the guard keeps its loopback-only dev default; the
    session probe answers the same question."""
    monkeypatch.delenv("ALIVE_ADMIN_TOKEN", raising=False)
    c = TestClient(_m().app)          # TestClient peer IS loopback
    assert c.get("/v2/admin/session").json() == {"authenticated": True}
    assert c.get("/v2/usage").status_code == 200


# --- the login rate-limit bucket --------------------------------------------------

def test_login_rate_limit_kicks_in():
    """The default path table gives /v2/admin/login its own tight bucket:
    5 tries then 429, socket-peer keyed — and the global budget is
    untouched so the gate can't starve the rest of the API."""
    assert middleware._DEFAULT_PATH_LIMITS["/v2/admin/login"] == (0.2, 5)
    app = FastAPI()

    @app.post("/v2/admin/login")
    async def login():
        return {"ok": True}

    @app.get("/ping")
    async def ping():
        return {"ok": True}

    middleware.attach(app, rate_per_s=100, burst=100)
    c = TestClient(app)
    codes = [c.post("/v2/admin/login", json={"token": "x"}).status_code
             for _ in range(7)]
    assert codes[:5] == [200] * 5
    assert 429 in codes[5:]
    assert c.get("/ping").status_code == 200     # global budget untouched


def test_bearer_still_accepted_for_ops_curl(monkeypatch):
    """Bearer stays for go-nogo health-checks and scripts — the browser
    path is cookie-only, but the guard contract is both."""
    c = _login_client(monkeypatch)
    assert c.get("/v2/usage",
                 headers={"Authorization": "Bearer test-token-xyz"}
                 ).status_code == 200


# --- the page -------------------------------------------------------------------

def test_admin_page_is_cookie_flow_not_token_storage():
    """The served page must carry the gate + cookie login and none of the
    sessionStorage-token machinery the XSS report flagged."""
    body = TestClient(_m().app).get("/admin").text
    assert 'id="gate"' in body and 'id="gateform"' in body
    assert "/v2/admin/login" in body
    assert "/v2/admin/logout" in body
    assert "/v2/admin/session" in body
    for dead in ("alive_admin_tok", "prompt(", "sessionStorage.setItem('alive_admin"):
        assert dead not in body, dead
