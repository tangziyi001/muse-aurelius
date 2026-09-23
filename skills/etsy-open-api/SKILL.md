---
name: "etsy-open-api"
description: "Operate an Etsy shop through the official Etsy Open API v3: OAuth PKCE onboarding, token refresh, listing draft/create/publish, image and digital-file uploads, taxonomy lookup. Use for any Etsy shop automation — never drive Etsy through a browser; openapi.etsy.com is not bot-walled. Reference implementation: ~/workspace/etsy-automation/client.py."
---

# Etsy Open API

Operate an Etsy shop via the official Etsy Open API v3 (pure stdlib Python, no browser).
Reference implementation lives in `~/workspace/etsy-automation/` (`oauth.py` PKCE flow, `client.py` API client, `config.py` credential store).

## Measured rules (all verified 2026-09-20, do not re-derive)

1. **No browser needed.** `https://openapi.etsy.com` answers from datacenter IPs with no DataDome/PerimeterX wall. Never route Etsy shop work through Pi browser or any login automation. (Browser login was tried and abandoned 2026-09-20.)
2. **Seller app callback URL must be HTTPS on a real domain.** The Etsy developer app-creation form **rejects** `http://localhost:*` and `http://127.0.0.1:*`. For the one-time OAuth dance, register an HTTPS callback on a real domain (e.g. a one-off `https://webhook.site/<uuid>` URL); read the `code` from its request inspector.
3. **Token endpoint is `https://api.etsy.com/v3/public/oauth/token`** — not the `openapi.etsy.com` host. (A prototype that used the openapi host for token exchange was wrong.)
4. **`x-api-key` header format is `keystring:shared_secret`.** A bare keystring returns 403 (measured 2026-02-09+ behavior change). Send on EVERY request:
   `x-api-key: {keystring}:{shared_secret}`
5. **OAuth is PKCE, public client.** Code exchange and refresh do NOT need the shared secret / client secret. Do not invent a client-secret parameter — an unverified combination can break the verified path.
6. **Refresh token rotates.** Each refresh response carries a NEW refresh token; the old one dies. Always persist the newest response. Access tokens live ~3600 s; refresh when `expires_at - 120s < now`.
7. **Scopes are per-app and must be re-authorized if changed.** Etsy has NO scope checkboxes in the developer dashboard — scopes are requested dynamically in the authorize URL; the consent screen lists them. **Only the 12 scopes on the official auth page are accepted** (verified 2026-09-20): `address_r address_w email_r listings_d listings_r listings_w profile_r profile_w shops_r shops_w transactions_r transactions_w`. Requesting anything else (`billing_r`, `cart_r/w`, `favorites_r/w`, `feedback_r`, `inventory_r/w`, `recommend_r/w`) fails the ENTIRE authorization with "The authorization request specified invalid permissions" — Etsy documents these nowhere now, do not invent them. Requested set for ZenPixelWalls (2026-09-20, user asked for all permissions): the 12 official scopes; re-authorized 2026-09-20 ~12:10 EDT, receipts endpoint verified 200 with transactions_r live (0 orders so far). Stats pipeline needs no code changes — it was already written against transactions_r. Etsy customer-service/conversations have NO API — do not look for one.
8. **`GET /v3/application/users/{user_id}/shops` shape varies.** For a single-shop seller app it returns a **single shop object** (top-level `shop_id`/`shop_name`), not `{"results":[...]}`. Parser must accept: single object → `[obj]`; list → as-is; `{"results":[...]}` → results array.
9. **updateListing is PATCH, not PUT.** The old PUT on `/v3/application/shops/{shop_id}/listings/{listing_id}` now returns 404 `{"error": "Resource not found"}` (measured 2026-09-20). Send updates (including `state=active` for publishing) as **PATCH** with `application/x-www-form-urlencoded` body.

## One-time human setup (irreducible)

1. Human creates the Etsy seller app at etsy.com/developers (name, HTTPS callback above), approves scopes, clicks Authorize once.
2. Human hands the agent: API keystring + shared secret (secure channel), and pastes the OAuth `code` from the callback URL once.
3. Agent exchanges code → tokens, stores them, and refresh runs unattended afterwards (until refresh token is revoked/expires, which needs one more human Authorize).

Credential storage: `~/.config/etsy-automation/env` (KEY=VALUE, mode 600) and `~/.config/etsy-automation/tokens.json` (mode 600). **Never print token/keystring/secret values** in chat, logs, memory, or reports — refer to them by role only.

## Listing operations (client.py)

- `create_draft_listing(shop_id, title, description, price, taxonomy_id, tags, ...)` — `type="download"` for digital products, `quantity=999`.
- `upload_listing_image(shop_id, listing_id, image_path, rank=...)` — up to 10 images; rank 1 = thumbnail. Multipart form.
- `upload_listing_file(shop_id, listing_id, file_path, ...)` — digital deliverables (zip/pdf/png). **A download listing cannot go active until at least one digital file is attached** (Etsy enforces this).
- `update_listing(..., state="active")` / `publish_listing(shop_id, listing_id, deliverable_path=None)` — publish = optional file attach + state→active.
- Read-back: `get_listing(listing_id, includes=("Images",))`; shop listing files via `GET /v3/application/shops/{shop_id}/listings/{listing_id}/files`.
- **改价必须走 inventory endpoint**（2026-09-20 实测）：PATCH `/listings/{id}` 带 `price` 会返回 200 但被静默忽略。正确路线：`GET /v3/application/listings/{id}/inventory` 取 products/offerings（注意是无 shop 前缀的路径），再 `PUT /v3/application/listings/{id}/inventory`，Content-Type 必须 `application/json`（client.py 的 form-encoded 会被 400 "Not a valid JSON string"）。PUT body 里 products 条目**不能带 `product_id` / `offering_id`**（带了就 400 "invalid keys"），offering 的 price 用浮点数（如 `9.99`），顶层带上 `price_on_property: []`、`quantity_on_property: []`、`sku_on_property: []`。改完用 `get_listing` 读回 `price.amount` 核验。

## Listing field limits (enforced by Etsy)

- Title ≤ 140 chars. Front-load the primary keyword (e.g. `lockscreen`) in the first 60 chars for SEO.
- Tags: max 13, **each ≤ 20 chars** (longer tags are rejected — validate before submit).
- Digital products: taxonomy `2078` (Art & Collectibles > Prints > Digital Prints). Do NOT use 6112 (Home Decor > Wall Decor > Wallpaper — that is physical wallpaper).
- Every digital listing copy must state: digital download, compatible sizes, personal use only, no resale, and the line `Every design is original to this shop and AI-assisted`.

## 4K delivery standard (2026-09-20, permanent)

All ZenPixelWalls wallpaper products ship 4K, and listings say so honestly:
- Phone wallpapers: **2340×5064** (2x Real-ESRGAN upscale of 1170×2532 source,
  `fal-ai/esrgan` sync API — see fal-ai skill). Label as
  **"4K Ultra HD (2340x5064)"**. NEVER write 2160×3840 for phone files —
  forcing that aspect ratio distorts or crops the clock area.
- Desktop wallpapers: **3840×2160** native (already 4K UHD, no upscale needed).
- Delivery: high-quality JPG (~3–4MB per phone wallpaper); ZIP per product,
  ≤20MB per file (Etsy cap).
- Existing listings are upgraded in place via upload-new-then-delete-old on
  `/listings/{id}/files` (no relist, no fee); buyers can re-download free.
  Script: `/tmp/up4k_batch/etsy_update.py` (pattern).

## 2026-09-20 封面规格更正（用户用 Etsy App 实测，永久有效）

- 店面缩略图是**正方形**；商品详情页的主图视窗也是接近正方形的裁切框。
  竖长图（2列×3行六宫格等）在详情页会被上下裁掉——底下一行根本看不到。**一律用正方形**。
- Bundle 六宫格规范：**2000×2000 JPG，无字**。3列×2行，每格 666×1000，
  取原图中央部分等比填充（原图 2340×5064 竖长，缩放至宽 666 后高约 1441，
  中央裁掉上下各约 220px，允许裁掉原图上下一部分），格子间无缝或细线分隔均可。
- 写拼图脚本时**行号用 `i // COLS`，列号用 `i % COLS`**——2026-09-20 实测用
  `i // ROWS` 会把第 3、6 张贴到画布外，生成两格纯白，肉眼抽查一张都不够，
  必须程序自检（每格 stddev > 3 才算有内容）。
- Pack 三联图同理：店面缩略图是正方形，横长三联在缩略图里会被左右裁掉——
  需另行按正方形规格处理（pack agent 负责）。

## 2026-09-20 出站网络故障记录（infra，恢复后无视）

- 2026-09-20 14:40 EDT 起本 VM 出站 HTTPS 代理故障：`openapi.etsy.com` 和
  `google.com` 均连接超时（Etsy API 本身在 18:02 UTC 仍正常，是本机出口问题，
  不是 Etsy 平台问题）。
- 故障期间 Etsy 写操作一律 park：只做本地准备（拼图、文案草稿），不盲重试烧时间。
- 恢复探测只做一次 cheap GET（`get_listing` 单个 listing，timeout 45s）；
  恢复后对 bundle/pack 上线的精确顺序：读 live title/description/images/price →
  已有 10 张图则先删旧 rank-1 → 上传新首图 → 标题加数量前缀（≤140 字符）→
  描述最前插省钱行（其余不动）→ API 读回验证（images[0] 新图、标题/描述前缀、
  价格未变）→ 写 report JSON → 更新本 skill 的坑。

## 2026-09-20 bundle 上线实测坑（永久有效）

- **删旧 rank-1 再上传新图会产生 rank 并列**：删掉旧 rank-1 后 Etsy 会把剩下
  的一张图自动提为 rank-1，再用 `upload_listing_image(..., rank=1)` 上传新图会
  出现两个 rank=1。Etsy 服务端会在几分钟内异步收敛，最终新上传的图成为唯一的
  rank-1、其余顺延为 2..N。**正确做法**：上传后轮询 `get_listing(includes=Images)`
  等 ranks 收敛为 1..N 且新图为 rank-1（约 2–4 分钟），不要急着下结论；
  不确定时只读 readback，绝不盲重传。
- **v3 没有 updateListingImage**：`PUT /v3/application/shops/{id}/listings/{lid}/images/{img_id}`
  返回 404（v2 才有该接口）。rank 只能在上传时指定 + 靠服务端收敛，无法直接改。
- **描述里的 ASCII 省略号会被 Etsy 转义**：`that's` 存进去读回来变成
  `that&#39;s`（页面渲染正常，但字符串比对失败）。省钱行等固定文案用
  U+2019（’）代替 ASCII `'`，可干净 round-trip。
- **读回断言必须做实体归一化**：`html.unescape()` 后再做字符串比对，
  否则幂等检查会误判"文案还没写"而重复插入省钱行（2026-09-20 redo
  上线实测，已验证 L07–L18 无重复省钱行）。

## 2026-09-20 redo 上线数字文件事故（永久有效）

- 上一任 agent 打的 6 个 ZIP 是 44–65MB，上传被 Etsy 400 拒绝
  （"This file exceeds the maximum file size"）；且脚本**先删旧包后传新包**，
  第一次上传失败前已删掉 L07 的旧包，导致 L07 一度线上无数字文件。
- 修复：`~/workspace/etsy-pack-covers/rebuild_redo_zips_small.py`
  自适应重打（phone 图 q88 + optimize），6 个包全部 ≤12.3MB；
  **永远先传新后删旧**，删前必须确认新文件已上传成功并读回验证。

## Costs

Listing fee is $0.20 per published listing. Drafts are free until activated.

## 流量与订单监控（2026-09-20 实测）

- `GET /v3/application/shops/{shop_id}/receipts` 需要 `transactions_r` scope；缺权限时 403
  `{"error":"Access token lacks scope for this request (requires scope: transactions_r)."}`。
  补 scope 必须重新走一次 OAuth（旧 token 不会自动获得新 scope）——这是 Etsy 的 scope 模型，不是 bug。
- `GET /v3/application/shops/{shop_id}/reviews` 当前 scope（`listings_r listings_w shops_r shops_w`）
  即可读；新店 `count=0` 正常。分页走标准 `limit`/`offset`。
- listing 资源自带 `num_favorers`（收藏数）和 `views` 字段——shop listings 接口
  （`GET /v3/application/shops/{shop_id}/listings`）直接返回，无需额外调用：
  - `num_favorers`：可用。2026-09-20 全 0（开店第 1 天，与零流量一致）。
  - `views`：字段存在但同期全为 0；它是否随真实流量递增**未验证**——在观测到非零值
    之前，不许当作流量指标用，周报里必须明确标注，不许编造"浏览量"。
- Etsy v3 **没有**单品访客数/转化率接口：转化漏斗算不出来，只能用
  订单 / 收藏 / Pinterest 引流点击三个硬指标回答"哪个系列赚钱"。
- 监控管线（全部只读，不动上架流程）：
  - `~/workspace/etsy-automation/stats.py`（每日）：listings 快照 + receipts 增量
    （按 receipt_id 去重，水位 `receipts_seen.json`）+ reviews 增量；
    输出 `~/workspace/goals/etsy-zenpixelwalls-30/hidden_files/stats/etsy_YYYY-MM-DD.jsonl`。
    receipts 缺权限时记 `meta` 不崩溃；receipt 只存 receipt_id/时间/listing/金额，
    **绝不存 buyer 姓名/邮箱/地址**。
  - `~/workspace/pinterest-automation/analytics.py`（每日）：按 `posted_pins.json` 的 pin_id
    拉 `GET /v5/pins/{pin_id}/analytics`（`metric_types=IMPRESSION,SAVE,OUTBOUND_CLICK`，
    近 7 天滚动）；无 token 时静默跳过 exit 0。Pinterest analytics 有 1-2 天延迟。
  - `~/workspace/etsy-automation/weekly_report.py`（每周一）：按 10 个系列聚合近 7 天，
    输出 `hidden_files/reports/weekly_YYYY-MM-DD.md`；结论只写数据支持的，
    零信号时如实写"数据不足"，不编排名。
- 系列映射：`hidden_files/stats/series_map.json`（`listing_series` 显式映射优先，
  `keyword_rules` 按标题关键词兜底；上新 listing 时把新 id 加进来，否则归入 unmapped）。
- 通知规则（cron `etsy-traffic-stats-daily` 执行）：首单 / 新订单 / 新评价 /
  收藏突增（单日 +3，或从 0 到 ≥2）才打扰用户；平时静默只记日志。

## 2026-09-20 pack 表达改造（14 个普通 pack，永久有效）

- 目标：店面网格一眼区分档位。手段：标题 `3-Pack: ` 前缀（≤140 字符，超长从尾截断）+
  描述首行省钱句 `3 DESIGNS FOR $4.99 — that's $1.66 each, 44% less than $2.99 singles.` +
  正方形 2000×2000 三联首图（3 竖条 667/666/667，每条取原图中央等比裁切、无拉伸、无字）。
- 正方形铁律（用户 Etsy App 实测）：竖长拼图在详情页被上下裁掉、横长拼图在方形店面缩略图
  被左右裁掉——拼图封面一律正方形。生成后必须像素自检（每条 stddev>3）。
- 图片替换流程（client 已验证）：删旧 rank-1 → readback 确认删除 → 上传新图 rank=1 →
  readback 确认新 rank-1 → PATCH 标题/描述 → 独立读回验证（标题前缀/描述首行/新 rank-1/
  价格 499·divisor 100/section 不变/state active）。PATCH 只带 title+description，
  绝不带 price（PATCH 带 price 会被静默忽略，且有误改风险）。
- 本次实绩：L01–L06、L10–L15、L19、L20 共 14/14 上线验证通过。
  报告 `~/workspace/etsy-pack-covers/pack-refresh-report.json`，
  改前快照 `pack-before-state.json`，封面 `L{nn}-triptych-square.jpg`，
  脚本 `build_triptychs_square.py` / `launch_pack_refresh.py`。
- 源图选择（包内 phone/desktop 数量本就不一致，listings.csv 有据）：
  4P+2D 的包（L01–L03、L13–L15）取前 3 张 phone；3P+3D（L10–L12、L19–L20）取 3 张 phone；
  2P+4D 的桌面包（L04–L06，标题即 Desktop Pack）取前 3 张 desktop 竖切——液态铬抽象图
  竖切后视觉效果好，已目检。
- 旧规格产物（2400×1732 横长三联等）已作废，不在 etsy-pack-covers/ 根目录保留引用。
