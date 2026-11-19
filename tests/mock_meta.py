#!/usr/bin/env python3
"""Local stand-in for graph.facebook.com + rupload.facebook.com, to test publish.py end to end.
Logs every call to mock_calls.jsonl; fails the request if the token is sent in a URL or the upload headers are wrong."""
import json
import sys
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
BASE = f"http://127.0.0.1:{PORT}"
LOG = sys.argv[2] if len(sys.argv) > 2 else "mock_calls.jsonl"
FAIL_IG = "--fail-ig" in sys.argv


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, obj):
        b = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def _rec(self, body_len=0, form=None):
        u = urllib.parse.urlparse(self.path)
        q = dict(urllib.parse.parse_qsl(u.query))
        rec = {"m": self.command, "path": u.path, "q": q, "auth": self.headers.get("Authorization", ""),
               "form": form or {}, "len": body_len, "offset": self.headers.get("offset"),
               "file_size": self.headers.get("file_size")}
        with open(LOG, "a") as f:
            f.write(json.dumps(rec) + "\n")
        return u.path, q, rec

    def do_GET(self):
        path, q, rec = self._rec()
        if "access_token" in q or not rec["auth"].startswith("OAuth "):
            return self._send(400, {"error": {"message": "token must be in the Authorization header"}})
        f = q.get("fields", "")
        p = path.split("/")[2:]  # after /v25.0/
        if p == ["me"]:
            return self._send(200, {"id": "SU1", "name": "autopost system user"})
        if p == ["me", "permissions"]:
            return self._send(200, {"data": [{"permission": x, "status": "granted"} for x in
                                             ["pages_show_list", "pages_read_engagement", "pages_manage_posts",
                                              "instagram_basic", "instagram_content_publish", "business_management"]]})
        if p == ["me", "accounts"]:
            return self._send(200, {"data": [{"id": "PAGE1", "name": "COMPUTER DZ",
                                              "instagram_business_account": {"id": "IG1", "username": "computerdz"}}]})
        if p == ["PAGE1"] and f == "access_token":
            return self._send(200, {"access_token": "PAGETOKEN", "id": "PAGE1"})
        if p == ["PAGE1"]:
            return self._send(200, {"id": "PAGE1", "name": "COMPUTER DZ",
                                    "instagram_business_account": {"id": "IG1", "username": "computerdz"}})
        if p == ["IG1", "content_publishing_limit"]:
            return self._send(200, {"data": [{"quota_usage": 1, "config": {"quota_total": 50}}]})
        if p == ["V1"]:
            return self._send(200, {"status": {"video_status": "ready", "publishing_phase": {"status": "complete"}},
                                    "permalink_url": "/reel/111"})
        if p == ["C1"]:
            return self._send(200, {"status_code": "ERROR" if FAIL_IG else "FINISHED", "status": "test"})
        if p == ["M1"]:
            return self._send(200, {"permalink": "https://www.instagram.com/reel/abc/"})
        return self._send(404, {"error": {"message": "unknown " + path}})

    def do_POST(self):
        n = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(n)
        ctype = self.headers.get("Content-Type", "")
        form = dict(urllib.parse.parse_qsl(body.decode())) if "urlencoded" in ctype else {}
        path, q, rec = self._rec(n, form)
        if "access_token" in q or "access_token" in form or not rec["auth"].startswith("OAuth "):
            return self._send(400, {"error": {"message": "token must be in the Authorization header"}})
        if path.startswith("/video-upload/") or path.startswith("/ig-api-upload/"):
            if rec["offset"] != "0" or rec["file_size"] != str(n) or n == 0:
                return self._send(400, {"error": {"message": "bad upload headers"}})
            return self._send(200, {"success": True})
        p = path.split("/")[2:]
        if p == ["PAGE1", "video_reels"] and form.get("upload_phase") == "start":
            if rec["auth"] != "OAuth PAGETOKEN":
                return self._send(400, {"error": {"message": "Reels need the Page token"}})
            return self._send(200, {"video_id": "V1", "upload_url": f"{BASE}/video-upload/v25.0/V1"})
        if p == ["PAGE1", "video_reels"] and form.get("upload_phase") == "finish":
            ok = form.get("video_id") == "V1" and form.get("video_state") == "PUBLISHED" and form.get("description")
            return self._send(200 if ok else 400, {"success": bool(ok)})
        if p == ["IG1", "media"]:
            ok = form.get("media_type") == "REELS" and form.get("upload_type") == "resumable" and form.get("caption")
            return self._send(200 if ok else 400, {"id": "C1", "uri": f"{BASE}/ig-api-upload/v25.0/C1"})
        if p == ["IG1", "media_publish"] and form.get("creation_id") == "C1":
            return self._send(200, {"id": "M1"})
        return self._send(404, {"error": {"message": "unknown " + path}})


if __name__ == "__main__":
    HTTPServer(("127.0.0.1", PORT), H).serve_forever()
