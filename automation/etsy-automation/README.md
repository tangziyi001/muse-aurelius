# Etsy 全自动运营 · API 原型（Track A）

ZenPixelWalls 的 listing 创建 / 图片上传 / 数字文件上传 / 标题描述标签价格更新，
全部走 **Etsy 官方 Open API v3** —— 不碰浏览器、不碰 DataDome 滑块。

> 站内客服消息：官方 API 没有 conversation/message/reply endpoint
> （2026-09-20 已对官方 spec 全文核对 + 两个独立开源项目交叉验证）。
> 因此客服自动回复不在本原型范围内，需独立通道（见下方）。

## 架构

```
oauth.py    PKCE 授权 URL 生成 / code 换 token / refresh token 自动轮换
client.py   EtsyClient：建草稿、传图、传数字文件、更新 listing、查 taxonomy/shop
demo.py     端到端演示：读 listings.csv 一行 → 建 download 草稿 → 上传首图
config.py   从 ~/.config/etsy-automation/env 读凭证（600 权限，不在代码/日志里出现）
```

## 已验证的事实（2026-09-20，全部有实测/官方 spec 依据）

- `POST /v3/application/shops/{shop_id}/listings` 创建草稿（form-urlencoded），scope `listings_w`
- `type` 参数：`physical | download | both` —— 数字壁纸用 `download`
- `POST .../listings/{id}/images` 传图（multipart），scope `listings_w`
- `POST .../listings/{id}/files` 传数字交付文件（multipart），scope `listings_w`
- `PUT .../listings/{id}` 更新标题/描述/tags/价格/state
- API 域名 `openapi.etsy.com` 云端 VM 直连可达（无 DataDome），key 格式经服务器实测为 `keystring:shared_secret`
- OAuth：`https://www.etsy.com/oauth/connect` + PKCE S256；token 端点 `https://openapi.etsy.com/v3/public/oauth/token`

## 一次性人工步骤（仅此一次，之后永久自动）

1. 打开 https://www.etsy.com/developers ，登录后创建一个 **seller app**
2. Redirect URI 登记为：`http://localhost:8080/etsy/callback`（必须精确一致）
3. 审批通过后，把 **keystring** 和 **shared secret** 交给主 agent（走安全流程，不进聊天）
4. 运行 `python3 oauth.py auth-url`，把打印出的 URL 在浏览器打开并点 Authorize
5. 浏览器地址栏会跳到 `http://localhost:8080/etsy/callback?code=XXXX&state=...`
   （页面打不开是正常的）——把 `code=XXXX` 的值交给主 agent
6. 主 agent 运行 `python3 oauth.py exchange --code XXXX`，token 自动存入
   `~/.config/etsy-automation/tokens.json`（600 权限），之后 refresh 全自动

## 运行演示

```bash
cd ~/workspace/etsy-automation
python3 demo.py                 # 用 listings.csv 第 0 行建一个 download 测试草稿 + 上传首图
python3 demo.py --row 3         # 用第 3 行
python3 demo.py --publish --deliverable /path/to/pack.zip
    # 先传交付文件，再把草稿设为 active（会产生 $0.20/listing 上架费，默认不执行）
```

## 安全规则

- 凭证只存在 `~/.config/etsy-automation/env`（600），token 只存在 `tokens.json`（600）
- 绝不把 keystring / secret / code / token 打印到日志或写进代码
- access token 约 1 小时过期；client 每次调用前自动 refresh（refresh token 约 90 天）

## 待办（给主 agent）

- [ ] 用户完成上面 6 步一次性流程后，运行 demo.py 验证端到端
- [ ] 确认数字壁纸的 seller taxonomy 节点（demo 会自动按关键词 "digital" 搜索，可用 `--taxonomy-id` 覆盖）
- [ ] 决定 20 个 listing 是否自动 publish（$0.20/个上架费）还是先全建草稿人工看一眼
- [ ] 客服消息通道：API 不支持，需另立项（住宅浏览器 hardened / 邮件通知触发人工模板）
