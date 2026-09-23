"""Pinterest OAuth 2.0 helpers (stdlib only).

One-time human flow:
  1. Human creates Pinterest Business account + app at developers.pinterest.com,
     registers a redirect URI (recommend a one-off https://webhook.site/<uuid> URL),
     notes App ID + App Secret, submits Trial access request.
  2. Coordinator prints the authorize URL from build_auth_url(); human opens it,
     approves scopes, pastes the `code` from the redirect URL back (one time).
  3. exchange_code() trades code -> tokens; tokens stored, refresh runs unattended.
"""
import base64
import json
import urllib.parse
import urllib.request

AUTH_URL = "https://www.pinterest.com/oauth/"
TOKEN_URL = "https://api.pinterest.com/v5/oauth/token"

DEFAULT_SCOPES = ["boards:read", "boards:write", "pins:read", "pins:write"]


def build_auth_url(app_id, redirect_uri, scopes=DEFAULT_SCOPES, state="zenpixelwalls"):
    params = {
        "client_id": app_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": ",".join(scopes),
        "state": state,
    }
    return AUTH_URL + "?" + urllib.parse.urlencode(params)


def _basic_auth_header(app_id, app_secret):
    raw = f"{app_id}:{app_secret}".encode()
    return "Basic " + base64.b64encode(raw).decode()


def _post_token(data, app_id, app_secret):
    body = urllib.parse.urlencode(data).encode()
    req = urllib.request.Request(
        TOKEN_URL, data=body, method="POST",
        headers={
            "Authorization": _basic_auth_header(app_id, app_secret),
            "Content-Type": "application/x-www-form-urlencoded",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"Pinterest token HTTP {e.code}: {e.read().decode()[:300]}")


def exchange_code(app_id, app_secret, code, redirect_uri):
    return _post_token(
        {"grant_type": "authorization_code", "code": code, "redirect_uri": redirect_uri},
        app_id, app_secret,
    )


def refresh_tokens(app_id, app_secret, refresh_token):
    return _post_token(
        {"grant_type": "refresh_token", "refresh_token": refresh_token},
        app_id, app_secret,
    )
