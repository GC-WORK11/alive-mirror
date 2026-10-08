#!/usr/bin/env python3
"""Local mirror for admin.html work: serves the working copy of
server/admin.html at its real mount (server/admin_mount.py), proxies
every other GET to the live NLB so the page renders real production
data locally. Until the mount ships on prod, mount-relative fetches
fall back to the legacy /admin + /v2 paths transparently.
Usage: python3 tools/admin_mirror.py [port]  (default 8080)
"""
import http.server, urllib.request, sys, os

NLB = "http://alive108-2699c171ddded465.elb.ap-south-1.amazonaws.com"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ADMIN = os.path.join(ROOT, "server", "admin.html")
sys.path.insert(0, os.path.join(ROOT, "server"))
from admin_mount import ADMIN_MOUNT  # noqa: E402

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8080

# pre-deploy bridge: prod still serves the console on its old paths, so
# a 404 on a mount-relative fetch retries once against the legacy route
_LEGACY = [(ADMIN_MOUNT + "/api/usage", "/v2/usage"),
           (ADMIN_MOUNT + "/api", "/admin/api"),
           (ADMIN_MOUNT + "/session", "/v2/admin/session"),
           (ADMIN_MOUNT + "/login", "/v2/admin/login"),
           (ADMIN_MOUNT + "/logout", "/v2/admin/logout"),
           (ADMIN_MOUNT, "/admin")]


def _legacy(path):
    for new, old in _LEGACY:
        if path == new or path.startswith(new + "/"):
            return old + path[len(new):]
    return None


class H(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _serve_admin(self):
        try:
            body = open(ADMIN, "rb").read()
        except OSError:
            self.send_error(500, "admin.html missing")
            return
        self.send_response(200)
        self.send_header("content-type", "text/html; charset=utf-8")
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _fetch(self, path):
        url = NLB + path
        req = urllib.request.Request(url, headers={"user-agent": "admin-mirror/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                return r.status, r.headers.get("content-type",
                                               "application/octet-stream"), r.read()
        except urllib.error.HTTPError as e:
            return e.code, e.headers.get("content-type", "text/plain"), e.read()

    def _proxy(self):
        path = self.path
        status, ctype, body = self._fetch(path)
        if status == 404:
            old = _legacy(path.split("?", 1)[0])
            if old:
                q = "?" + path.split("?", 1)[1] if "?" in path else ""
                status, ctype, body = self._fetch(old + q)
        self.send_response(status)
        self.send_header("content-type", ctype)
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path in (ADMIN_MOUNT, ADMIN_MOUNT + "/"):
            self._serve_admin()
        else:
            self._proxy()


if __name__ == "__main__":
    print(f"console mirror → http://127.0.0.1:{PORT}{ADMIN_MOUNT}")
    http.server.ThreadingHTTPServer(("127.0.0.1", PORT), H).serve_forever()
