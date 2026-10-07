#!/usr/bin/env python3
"""Local mirror for admin.html work: serves the working copy of
server/admin.html at /admin (+ /admin.html), proxies every other GET to
the live NLB so the page renders real production data locally.
Usage: python3 tools/admin_mirror.py [port]  (default 8080)
"""
import http.server, urllib.request, sys, os

NLB = "http://alive108-2699c171ddded465.elb.ap-south-1.amazonaws.com"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ADMIN = os.path.join(ROOT, "server", "admin.html")
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8080


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

    def _proxy(self):
        url = NLB + self.path
        try:
            req = urllib.request.Request(url, headers={"user-agent": "admin-mirror/1.0"})
            with urllib.request.urlopen(req, timeout=20) as r:
                body = r.read()
                ctype = r.headers.get("content-type", "application/octet-stream")
                self.send_response(r.status)
                self.send_header("content-type", ctype)
                self.send_header("content-length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
        except urllib.error.HTTPError as e:
            body = e.read()
            self.send_response(e.code)
            self.send_header("content-type", e.headers.get("content-type", "text/plain"))
            self.send_header("content-length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except Exception as e:
            self.send_error(502, f"proxy fail: {e}")

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path in ("/admin", "/admin/", "/admin.html"):
            self._serve_admin()
        else:
            self._proxy()


if __name__ == "__main__":
    http.server.ThreadingHTTPServer(("127.0.0.1", PORT), H).serve_forever()
