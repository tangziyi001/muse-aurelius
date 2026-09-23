# Web Evidence Screenshots → PDF Report

从带认证出口代理的 VM 上，用 Chromium CDP 截取网页关键段落、裁切后嵌入中文 PDF 报告的完整管线。2026-09-20 为 Maya 人设报告攻坚打通。

## 适用场景
- 需要"带截图的证据报告"：论文页、新闻报道、政策页面的关键段落截图 + 中文 PDF 交付
- 站点有反爬虫（Fast Company / MDPI 直接拦截），需要代理 + 真实浏览器指纹

## 前置：本地认证代理
VM 出口代理需要 `Proxy-Authorization`。起一个本地转发代理注入认证头：

```python
# /tmp/localproxy.py — 监听 127.0.0.1:18080，从环境变量读上游代理地址
# 核心逻辑：HTTP CONNECT / 普通请求转发时注入 Proxy-Authorization: Basic <base64>
```

验证：`curl -x http://127.0.0.1:18080 https://example.com -o /dev/null -w '%{http_code}'` 应返回 200。

## Chromium CDP 截图（不要用 --screenshot）
- Chromium CLI 的 `--screenshot` 模式在 headless 下**完全不产出文件**（连 data: URL 都不行），放弃。
- 用 CDP：启动时必须加 `--remote-allow-origins=*`，否则 websocket 连不上。
- 用 `/json/new` 创建新 tab 时必须发 **PUT** 请求：`urllib.request.urlopen` 默认是 GET 会返回 405（2026-09-20 踩坑）。用 `urllib.request.Request(url, method="PUT")`。

```bash
/opt/meta-chromium/chrome \
  --headless=new --disable-gpu --no-sandbox \
  --ignore-certificate-errors \
  --proxy-server=http://127.0.0.1:18080 \
  --remote-debugging-port=9222 \
  --remote-allow-origins=* \
  --user-data-dir=/tmp/chrome-prof \
  about:blank &
```

- 通过 CDP `Page.captureScreenshot` 截全页（先 `Page.getLayoutMetrics` 拿 contentSize，再 `Emulation.setDeviceMetricsOverride` 设视口=全页高）。
- **不要用会匹配自身的 pkill -f**（曾两次误杀自己）。管理进程用 `process.*` 工具或精确 PID。
- 反爬虫站点（Fast Company / MDPI）会返回拦截页：截图成功 ≠ 证据可用，**必须逐张打开验证**标题/来源/日期/关键段落。

## 截图裁切（关键！）
全页截图直接进 PDF 会占整页且留白巨大。裁到"标题 + 来源 + 日期 + 关键段落"：

```python
from PIL import Image
im = Image.open('shot.png')          # 典型 1280x2200
im.crop((0, 0, 1280, 1150)).save('shot.png')   # 取顶部关键区
# 导航栏是垃圾的页面（如未渲染 CSS 的 Wikipedia）：裁底部正文区
im.crop((0, 1750, 1280, 2200)).save('shot.png')
```

裁切前先渲染小图确认区域。标准：每张图在 PDF 里占 ≤ 半页。

## 中文 PDF（weasyprint）
- 安装：`pip install --break-system-packages weasyprint`（PEP 668 环境）
- 中文字体：系统已有 Noto Sans/Serif CJK SC（`/usr/share/fonts/opentype/noto/`），CSS 直接引用
- 图注必须和图同页：`<figcaption>` 放进 `<figure>` 内部 + `figure { page-break-inside: avoid; }`
- 证据块 `.evidence { page-break-inside: avoid; }`
- A4 页边距 20mm/17mm，页码用 `@page { @bottom-center { content: counter(page); } }`，封面页用 `@page :first` 去掉页码

## 证据审计清单（报告正文用）
- 统一证据等级：A=同行评审/官方政策，B=具名案例，C=小样本观察，D=经验/推断；每条标注一手/二手
- 被拦截站点的数字：删截图，改文字引用 + 链接 + 注明"反爬虫拦截未获可用截图，数字经多渠道交叉核验"
- 找不到一手出处的系数（如恐怖谷 β）：直接删除，不用次级来源硬凑
- 二手政策解读（如 Aubrium）不能替代官方政策页，必须明确标注

## 坑
1. `/tmp/shots/` 是临时目录：定稿截图要 `cp` 到 workspace 稳定路径再进 HTML
2. 截图文件名进 HTML 用相对路径；weasyprint 以 HTML 文件所在目录为 base
3. 浏览器后台进程和代理进程是临时的，VM 重启后需重起（脚本放 /tmp 会丢，重要脚本收进 workspace）
