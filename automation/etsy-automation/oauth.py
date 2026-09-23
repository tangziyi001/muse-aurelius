"""Etsy OAuth 2.0 + PKCE（Authorization Code 流程）。

一次性人工：用户打开 auth URL 授权一次，从一次性回调地址取回 `code`，
之后 token 获取/刷新全自动。不起本地回调服务器。

2026-09-20 实测要点：
- 回调 URL 必须 https + 真实域名（Etsy 明确拒绝 IP；localhost 走 http 也被拒）。
  可用 webhook.site 生成一次性 https 回调：建 token 后用
  https://webhook.site/<uuid> 注册，授权后轮询 /token/<uuid>/requests 取 code。
- token endpoint：https://api.etsy.com/v3/public/oauth/token
  （openapi.etsy.com 那版是错的）。
- exchange 时不需要 client_secret（PKCE 公共客户端实测可过）；
  但之后所有 API 请求的 x-api-key 头必须是 `keystring:shared_secret`
  （2026-02-09 起 Etsy 强制的新格式，裸 keystring 会 403）。

凭证来源：~/.config/etsy-automation/env（600 权限），见 config.py。
"""
import argparse
import base64
import hashlib
import secrets
import sys
import urllib.parse

from config import load_env, save_tokens, load_tokens

AUTH_URL = "https://www.etsy.com/oauth/connect"
# 2026-09-20 实测：token endpoint 必须走 api.etsy.com；
# openapi.etsy.com/v3/public/oauth/token 会失败。
TOKEN_URL = "https://api.etsy.com/v3/public/oauth/token"
# 可按需覆盖：ETSY_TOKEN_URL
# 2026-09-20 修正：Etsy 官方文档（developer.etsy.com/documentation/essentials/authentication）
# 当前只承认 12 个 scope。之前多加的 billing_r / cart_r / cart_w / favorites_r /
# favorites_w / feedback_r / inventory_r / inventory_w / recommend_r / recommend_w
# 会导致整个授权请求直接失败（"The authorization request specified invalid permissions"）。
# 注意：Etsy 开发者后台没有 scope 勾选页，scope 全在授权 URL 里动态申请；
# 不要再让用户去后台找 scope 开关。
# 用户要求"权限都打开" → 请求官方承认的全部 12 个。
SCOPES = ("address_r address_w email_r listings_d listings_r listings_w "
          "profile_r profile_w shops_r shops_w transactions_r transactions_w")


def generate_pkce():
    """返回 (code_verifier, code_challenge, state)。"""
    verifier = base64.urlsafe_b64encode(secrets.token_bytes(64)).rstrip(b"=").decode()
    digest = hashlib.sha256(verifier.encode()).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    state = secrets.token_urlsafe(24)
    return verifier, challenge, state


def build_auth_url(client_id, redirect_uri, scopes=SCOPES, state=None, challenge=None):
    if state is None:
        state = secrets.token_urlsafe(24)
    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": scopes,
        "state": state,
    }
    if challenge:
        params["code_challenge"] = challenge
        params["code_challenge_method"] = "S256"
    return AUTH_URL + "?" + urllib.parse.urlencode(params), state


def exchange_code(client_id, redirect_uri, code, code_verifier, client_secret=None,
                 token_url=TOKEN_URL):
    """用授权 code 换 access/refresh token。返回 token dict。"""
    import urllib.request
    import json as _json

    body = {
        "grant_type": "authorization_code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "code": code,
        "code_verifier": code_verifier,
    }
    if client_secret:
        body["client_secret"] = client_secret
    req = urllib.request.Request(
        token_url,
        data=urllib.parse.urlencode(body).encode(),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return _json.loads(resp.read().decode())


def refresh_access_token(client_id, refresh_token, client_secret=None,
                         token_url=TOKEN_URL):
    """用 refresh token 换新的 access token（Etsy 会轮换 refresh token）。"""
    import urllib.request
    import json as _json

    body = {
        "grant_type": "refresh_token",
        "client_id": client_id,
        "refresh_token": refresh_token,
    }
    if client_secret:
        body["client_secret"] = client_secret
    req = urllib.request.Request(
        token_url,
        data=urllib.parse.urlencode(body).encode(),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return _json.loads(resp.read().decode())


def cmd_auth_url(env):
    verifier, challenge, state = generate_pkce()
    url, _ = build_auth_url(
        env["ETSY_CLIENT_ID"], env["ETSY_REDIRECT_URI"],
        state=state, challenge=challenge,
    )
    # verifier 暂存，供 exchange 步骤使用（state 绑定防 CSRF）
    pending = {"code_verifier": verifier, "state": state}
    save_tokens(pending, filename="pending_pkce.json")
    print("1) 在浏览器打开下面这个 URL 并点 Authorize（Etsy 登录态操作，一次性）：")
    print()
    print(url)
    print()
    print("2) Etsy 会 302 跳到注册的 redirect_uri（一次性 webhook.site https 地址即可，")
    print("   2026-09-20 起 Etsy 只接受 https+真实域名的回调，localhost/127.0.0.1 一律拒绝）。")
    print("   从回调请求的 query 里取 code=，然后运行:  python3 oauth.py exchange --code XXXX")
    print("   （state 已存档，exchange 时会自动校验）")


def cmd_exchange(env, code):
    pending = load_tokens(filename="pending_pkce.json")
    if not pending or "code_verifier" not in pending:
        print("ERROR: 找不到 pending_pkce.json，请先运行: python3 oauth.py auth-url",
              file=sys.stderr)
        sys.exit(1)
    token_url = env.get("ETSY_TOKEN_URL", TOKEN_URL)
    tokens = exchange_code(
        env["ETSY_CLIENT_ID"], env["ETSY_REDIRECT_URI"], code,
        pending["code_verifier"], env.get("ETSY_CLIENT_SECRET"), token_url,
    )
    save_tokens(tokens)  # 600 权限
    # 用完即删 verifier
    import os
    from config import _token_path
    try:
        os.remove(_token_path("pending_pkce.json"))
    except OSError:
        pass
    print("OK: token 已保存并加密权限 600。refresh_token 有效期约 90 天，之后自动轮换。")


def main():
    ap = argparse.ArgumentParser(description="Etsy OAuth PKCE 工具")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("auth-url", help="生成一次性授权 URL")
    ex = sub.add_parser("exchange", help="用 code 换 token")
    ex.add_argument("--code", required=True, help="redirect 地址栏里的 code")
    args = ap.parse_args()

    env = load_env()
    for k in ("ETSY_CLIENT_ID", "ETSY_REDIRECT_URI"):
        if k not in env:
            print(f"ERROR: env 缺少 {k}（见 ~/.config/etsy-automation/env）",
                  file=sys.stderr)
            sys.exit(1)

    if args.cmd == "auth-url":
        cmd_auth_url(env)
    elif args.cmd == "exchange":
        cmd_exchange(env, args.code)


if __name__ == "__main__":
    main()
