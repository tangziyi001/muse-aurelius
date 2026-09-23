"""Pinterest API v5 client (stdlib only). Verified against the official generated
client docs 2026-09-20: POST https://api.pinterest.com/v5/pins with
media_source {source_type: image_base64, content_type, data}.

Token model: access_token (~30 days) + refresh_token (rotates; persist newest).
"""
import base64
import json
import mimetypes
import os
import time
import urllib.error
import urllib.request

import config
import oauth

API_BASE = "https://api.pinterest.com/v5"


class PinterestError(RuntimeError):
    pass


class PinterestClient:
    def __init__(self):
        env = config.load_env()
        self.app_id = env.get("PINTEREST_APP_ID")
        self.app_secret = env.get("PINTEREST_APP_SECRET")
        if not self.app_id or not self.app_secret:
            raise PinterestError("PINTEREST_APP_ID / PINTEREST_APP_SECRET missing in env file")
        self.tokens = config.load_tokens() or {}

    # ---- tokens ----
    def _ensure_access_token(self):
        tok = self.tokens
        if tok.get("access_token") and tok.get("expires_at", 0) - 120 > time.time():
            return tok["access_token"]
        if not tok.get("refresh_token"):
            raise PinterestError("no refresh_token; need one-time OAuth code exchange")
        new = oauth.refresh_tokens(self.app_id, self.app_secret, tok["refresh_token"])
        # refresh_token rotates: persist the newest response wholesale
        new["expires_at"] = time.time() + int(new.get("expires_in", 2592000))
        self.tokens = new
        config.save_tokens(new)
        return new["access_token"]

    def store_initial_tokens(self, token_response):
        token_response["expires_at"] = time.time() + int(token_response.get("expires_in", 2592000))
        self.tokens = token_response
        config.save_tokens(token_response)

    # ---- http ----
    def _request(self, method, path, body=None):
        token = self._ensure_access_token()
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(
            API_BASE + path, data=data, method=method,
            headers={"Authorization": f"Bearer {token}",
                     "Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                raw = r.read()
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as e:
            raise PinterestError(f"{method} {path} -> HTTP {e.code}: {e.read().decode()[:400]}")

    # ---- boards ----
    def list_boards(self):
        return self._request("GET", "/boards")

    def create_board(self, name, description=""):
        return self._request("POST", "/boards",
                             {"name": name, "description": description, "privacy": "PUBLIC"})

    def ensure_board(self, name, description=""):
        items = self.list_boards().get("items", [])
        for b in items:
            if b.get("name") == name:
                return b
        return self.create_board(name, description)

    # ---- pins ----
    def create_pin(self, board_id, image_path, title, description, link, alt_text=""):
        with open(image_path, "rb") as f:
            data = base64.b64encode(f.read()).decode()
        ctype, _ = mimetypes.guess_type(image_path)
        body = {
            "board_id": board_id,
            "title": (title or "")[:100],
            "description": (description or "")[:500],
            "link": link,
            "alt_text": (alt_text or "")[:500],
            "media_source": {
                "source_type": "image_base64",
                "content_type": ctype or "image/jpeg",
                "data": data,
            },
        }
        return self._request("POST", "/pins", body)

    def get_pin(self, pin_id):
        return self._request("GET", f"/pins/{pin_id}")
