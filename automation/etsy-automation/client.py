"""Etsy Open API v3 客户端（纯标准库）。

覆盖 ZenPixelWalls 所需的全部 listing 操作：
  建草稿 / 传图 / 传数字交付文件 / 更新标题描述tags价格 / 上下架 / 查店铺与 taxonomy

每次请求前检查 access token 有效期，过期自动用 refresh token 轮换。
API key 以 `x-api-key: {keystring}:{shared_secret}` 发送
（格式经 openapi.etsy.com 服务器返回的错误信息实测确认，2026-09-20）。
"""
import json
import mimetypes
import os
import time
import urllib.parse
import urllib.request
import uuid

from config import load_env, load_tokens, save_tokens
from oauth import refresh_access_token, TOKEN_URL

API_BASE = "https://openapi.etsy.com"


class EtsyError(Exception):
    def __init__(self, status, payload):
        self.status = status
        self.payload = payload
        super().__init__(f"Etsy API {status}: {payload}")


def _encode_multipart(fields, files):
    """fields: dict[str,str]；files: list[(field, filename, bytes, mimetype)]"""
    boundary = uuid.uuid4().hex
    body = b""
    for k, v in fields.items():
        body += (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="{k}"\r\n\r\n'
            f"{v}\r\n"
        ).encode()
    for field, filename, data, mtype in files:
        body += (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="{field}"; filename="{filename}"\r\n'
            f"Content-Type: {mtype}\r\n\r\n"
        ).encode() + data + b"\r\n"
    body += f"--{boundary}--\r\n".encode()
    return body, f"multipart/form-data; boundary={boundary}"


class EtsyClient:
    def __init__(self, env=None, tokens=None):
        self.env = env or load_env()
        self.tokens = tokens or load_tokens()
        if not self.tokens or "access_token" not in self.tokens:
            raise RuntimeError(
                "没有可用 token。请先跑完一次性 OAuth：\n"
                "  python3 oauth.py auth-url   # 用户浏览器授权一次\n"
                "  python3 oauth.py exchange --code XXXX"
            )
        self.keystring = self.env.get("ETSY_CLIENT_ID", "")
        self.shared_secret = self.env.get("ETSY_SHARED_SECRET", "")
        if not self.keystring or not self.shared_secret:
            raise RuntimeError("env 缺少 ETSY_CLIENT_ID / ETSY_SHARED_SECRET")
        self.token_url = self.env.get("ETSY_TOKEN_URL", TOKEN_URL)
        self._shop_id = None

    # ---------- token ----------
    def _ensure_token(self):
        # Etsy access token 约 1 小时；提前 120 秒刷新
        if self.tokens.get("expires_at", 0) - 120 > time.time():
            return
        if "refresh_token" not in self.tokens:
            raise RuntimeError("access token 过期且无 refresh_token，需重新走一次性 OAuth")
        # 2026-09-20 实测：refresh 不需要 client_secret（PKCE 公共客户端）。
        # 不要把 ETSY_CLIENT_SECRET 传进去——没验证过的组合可能破坏已验证的路径。
        new = refresh_access_token(
            self.env["ETSY_CLIENT_ID"], self.tokens["refresh_token"],
            None, self.token_url,
        )
        # Etsy 轮换 refresh_token：新响应自带新的；旧的没有就保留
        if "refresh_token" not in new and "refresh_token" in self.tokens:
            new["refresh_token"] = self.tokens["refresh_token"]
        new["expires_at"] = time.time() + int(new.get("expires_in", 3600))
        self.tokens = new
        save_tokens(new)

    # ---------- http ----------
    def _request(self, method, path, params=None, data=None, content_type=None,
                 files=None):
        self._ensure_token()
        url = API_BASE + path
        if params:
            url += "?" + urllib.parse.urlencode(params)
        body, ctype = None, content_type
        if files:
            body, ctype = _encode_multipart(data or {}, files)
        elif data is not None:
            body = urllib.parse.urlencode(data).encode()
            ctype = ctype or "application/x-www-form-urlencoded"
        headers = {
            "x-api-key": f"{self.keystring}:{self.shared_secret}",
            "Authorization": f"Bearer {self.tokens['access_token']}",
        }
        if ctype:
            headers["Content-Type"] = ctype
        req = urllib.request.Request(url, data=body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                raw = resp.read().decode()
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as e:
            try:
                payload = e.read().decode()
            except Exception:
                payload = ""
            raise EtsyError(e.code, payload)

    def get(self, path, params=None):
        return self._request("GET", path, params=params)

    # ---------- shop ----------
    def get_shop_id(self, shop_name=None):
        """解析店铺 ID。

        2026-09-20 实测：该 seller app 的 GET .../shops 返回**单个店铺对象**
        （顶层就有 shop_id / shop_name），不是 {"results":[...]}。
        两种形状都兼容。
        """
        if self._shop_id:
            return self._shop_id
        me = self.get("/v3/application/users/me")
        shops = self.get(f"/v3/application/users/{me['user_id']}/shops")
        if isinstance(shops, dict) and "shop_id" in shops:
            results = [shops]  # 单店铺对象
        elif isinstance(shops, list):
            results = shops
        else:
            results = (shops or {}).get("results", []) if isinstance(shops, dict) else []
        if not results:
            raise RuntimeError("该 Etsy 账号下没有店铺")
        want = shop_name or self.env.get("ETSY_SHOP_NAME", "")
        for s in results:
            if want and s.get("shop_name") == want:
                self._shop_id = s["shop_id"]
                return self._shop_id
        self._shop_id = results[0]["shop_id"]
        return self._shop_id

    # ---------- taxonomy ----------
    def find_seller_taxonomy(self, keyword):
        """在 seller taxonomy 树里按关键词找节点 ID（数字壁纸用 "digital" 试）。"""
        nodes = self.get("/v3/application/seller-taxonomy/nodes")
        kw = keyword.lower()
        hits = []

        def walk(nodelist, trail=""):
            for n in nodelist:
                name = n.get("name", "")
                path = f"{trail} > {name}" if trail else name
                if kw in name.lower():
                    hits.append((n["id"], path))
                walk(n.get("children", []), path)

        walk(nodes if isinstance(nodes, list) else nodes.get("results", []))
        return hits

    # ---------- listings ----------
    def create_draft_listing(self, shop_id, title, description, price, taxonomy_id,
                             tags=None, materials=None, quantity=999,
                             who_made="i_did", when_made="2020_2026",
                             listing_type="download", **extra):
        """创建 download（数字下载）草稿 listing。成功返回 201 + listing JSON。"""
        data = {
            "quantity": quantity,
            "title": title,
            "description": description,
            "price": price,
            "who_made": who_made,
            "when_made": when_made,
            "taxonomy_id": taxonomy_id,
            "type": listing_type,
            "is_supply": "false",
        }
        if tags:
            data["tags"] = ",".join(tags) if isinstance(tags, list) else tags
        if materials:
            data["materials"] = ",".join(materials) if isinstance(materials, list) else materials
        data.update({k: v for k, v in extra.items() if v is not None})
        return self._request(
            "POST", f"/v3/application/shops/{shop_id}/listings", data=data)

    def upload_listing_image(self, shop_id, listing_id, image_path, rank=1,
                             overwrite=False):
        with open(image_path, "rb") as f:
            img = f.read()
        mtype = mimetypes.guess_type(image_path)[0] or "image/jpeg"
        return self._request(
            "POST",
            f"/v3/application/shops/{shop_id}/listings/{listing_id}/images",
            data={"rank": str(rank), "overwrite": str(overwrite).lower()},
            files=[("image", os.path.basename(image_path), img, mtype)],
        )

    def upload_listing_file(self, shop_id, listing_id, file_path, name=None, rank=1):
        """上传数字交付文件（zip/pdf/png…）。把文件挂到 download listing 上。"""
        with open(file_path, "rb") as f:
            blob = f.read()
        mtype = mimetypes.guess_type(file_path)[0] or "application/octet-stream"
        return self._request(
            "POST",
            f"/v3/application/shops/{shop_id}/listings/{listing_id}/files",
            data={"name": name or os.path.basename(file_path), "rank": str(rank)},
            files=[("file", os.path.basename(file_path), blob, mtype)],
        )

    def get_listing_files(self, shop_id, listing_id):
        """列出 listing 当前挂载的数字交付文件（含 listing_file_id）。"""
        return self.get(
            f"/v3/application/shops/{shop_id}/listings/{listing_id}/files")

    def delete_listing_file(self, shop_id, listing_id, listing_file_id):
        """删除一个数字交付文件（替换流程用：先删旧再传新）。"""
        return self._request(
            "DELETE",
            f"/v3/application/shops/{shop_id}/listings/{listing_id}/files/{listing_file_id}")

    def delete_listing_image(self, shop_id, listing_id, listing_image_id):
        """删除一张 listing 图片。用于 10 图上限时腾位置，或替换旧首图。

        2026-09-20 实测：DELETE /images/{id} 返回 200 + 空 JSON；删除后
        get_listing 的 Images 列表不再含该图，其它图的 rank 不变
        （删掉 rank=1 后，原 rank=2 的图不会自动升为 rank=1——
        必须显式上传新图并指定 rank=1）。
        """
        return self._request(
            "DELETE",
            f"/v3/application/shops/{shop_id}/listings/{listing_id}/images/{listing_image_id}")

    def update_listing(self, shop_id, listing_id, title=None, description=None,
                       price=None, tags=None, state=None, quantity=None, **extra):
        """更新标题/描述/tags/价格/state(active|inactive|draft…)。"""
        data = {}
        if title is not None:
            data["title"] = title
        if description is not None:
            data["description"] = description
        if price is not None:
            data["price"] = price
        if tags is not None:
            data["tags"] = ",".join(tags) if isinstance(tags, list) else tags
        if state is not None:
            data["state"] = state
        if quantity is not None:
            data["quantity"] = quantity
        data.update({k: v for k, v in extra.items() if v is not None})
        if not data:
            raise ValueError("update_listing: 没有要更新的字段")
        # 2026-09-20 实测：Etsy 已把 updateListing 从 PUT 迁到 PATCH；
        # 旧 PUT 路径返回 404 {"error": "Resource not found"}。
        return self._request(
            "PATCH", f"/v3/application/shops/{shop_id}/listings/{listing_id}",
            data=data)

    def publish_listing(self, shop_id, listing_id, deliverable_path=None):
        """发布：数字 listing 激活前必须已挂交付文件（Etsy 强制要求）。"""
        if deliverable_path:
            self.upload_listing_file(shop_id, listing_id, deliverable_path)
        return self.update_listing(shop_id, listing_id, state="active")

    def get_listing(self, listing_id, includes=("Images",)):
        params = {"includes": ",".join(includes)} if includes else None
        return self.get(f"/v3/application/listings/{listing_id}", params=params)

    def get_shop_listings(self, shop_id, state="draft", limit=25, offset=0):
        return self.get(f"/v3/application/shops/{shop_id}/listings",
                        params={"state": state, "limit": limit, "offset": offset})

    # ---------- shop sections ----------
    def get_shop_sections(self, shop_id):
        """列出店铺所有 sections（含 shop_section_id）。"""
        return self.get(f"/v3/application/shops/{shop_id}/sections")

    def create_shop_section(self, shop_id, title):
        """建 section。Etsy 限制标题 <=24 字符；创建顺序即店铺页展示顺序。"""
        return self._request("POST", f"/v3/application/shops/{shop_id}/sections",
                             data={"title": title})

    def update_shop_section(self, shop_id, shop_section_id, title):
        return self._request(
            "PUT", f"/v3/application/shops/{shop_id}/sections/{shop_section_id}",
            data={"title": title})

    def delete_shop_section(self, shop_id, shop_section_id):
        return self._request(
            "DELETE", f"/v3/application/shops/{shop_id}/sections/{shop_section_id}")
