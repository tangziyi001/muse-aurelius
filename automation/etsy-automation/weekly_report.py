"""每周一产出 ZenPixelWalls 流量周报（只读聚合，不碰上架流程）。

读 hidden_files/stats/etsy_*.jsonl + pinterest_*.jsonl（近 7 天），
按系列聚合：订单 / 收入 / 收藏增量 / 评价 / Pinterest impressions-saves-引流点击。
结论只写数据支持的；数据不足时如实说"数据不足"，不编排名依据。

输出：hidden_files/reports/weekly_YYYY-MM-DD.md
stdout 打印精简 digest，供 cron worker 转达用户。
"""
import glob
import json
import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

TZ = ZoneInfo("America/New_York")
GOAL = os.path.expanduser("~/workspace/goals/etsy-zenpixelwalls-30")
STATS_DIR = os.path.join(GOAL, "hidden_files", "stats")
REPORTS_DIR = os.path.join(GOAL, "hidden_files", "reports")
SERIES_MAP = os.path.join(STATS_DIR, "series_map.json")


def load_series_map():
    sm = json.load(open(SERIES_MAP))
    return (sm.get("series_names", {}), sm.get("listing_series", {}),
            sm.get("keyword_rules", []), sm.get("series_order", []))


def resolve_series(listing_id, title, listing_series, keyword_rules):
    if str(listing_id) in listing_series:
        return listing_series[str(listing_id)]
    tl = (title or "").lower()
    for rule in keyword_rules:
        if any(k in tl for k in rule.get("keywords", [])):
            return rule["series"]
    return "unmapped"


def read_jsonl_window(prefix, days=7):
    end = datetime.now(TZ).date()
    recs = []
    for i in range(days):
        d = (end - timedelta(days=i)).strftime("%Y-%m-%d")
        p = os.path.join(STATS_DIR, f"{prefix}_{d}.jsonl")
        if not os.path.exists(p):
            continue
        for line in open(p):
            line = line.strip()
            if line:
                try:
                    recs.append(json.loads(line))
                except Exception:
                    pass
    return recs


def main():
    names, listing_series, keyword_rules, order = load_series_map()
    end = datetime.now(TZ).date()
    start = end - timedelta(days=6)
    label = end.strftime("%Y-%m-%d")

    recs = read_jsonl_window("etsy", 7)
    precs = read_jsonl_window("pinterest", 7)

    # ---- listings: 首/末快照 ----
    snaps = sorted([r for r in recs if r.get("type") == "snapshot"],
                   key=lambda r: r["date"])
    first, last = {}, {}
    if snaps:
        for s in snaps[0]["listings"]:
            first[str(s["listing_id"])] = s
        for s in snaps[-1]["listings"]:
            last[str(s["listing_id"])] = s
    listing_ids = sorted(set(first) | set(last))

    # ---- receipts / reviews ----
    s0, s1 = start.strftime("%Y-%m-%d"), label
    receipts = [r["receipt"] for r in recs
                if r.get("type") == "receipt" and r.get("date") and s0 <= r["date"] <= s1]
    reviews = [r["review"] for r in recs if r.get("type") == "review"]

    # ---- pinterest 去重 (pin_id, date) 取最新 pull ----
    pin_days = {}
    for r in precs:
        if r.get("type") != "pin_day":
            continue
        pin_days[(r["pin_id"], r["date"])] = r

    agg = {}
    def A(series):
        return agg.setdefault(series, {"orders": 0, "revenue": 0.0, "favorers": 0,
                                       "views": 0, "reviews": 0, "rating_sum": 0,
                                       "impr": 0, "saves": 0, "clicks": 0,
                                       "listings": set()})

    for lid in listing_ids:
        f, l = first.get(lid, {}), last.get(lid, {})
        series = resolve_series(lid, l.get("title") or f.get("title"),
                                listing_series, keyword_rules)
        a = A(series)
        a["listings"].add(lid)
        a["favorers"] += (l.get("num_favorers") or 0) - (f.get("num_favorers") or 0)
        a["views"] += (l.get("views") or 0) - (f.get("views") or 0)

    for rc in receipts:
        lids = rc.get("listing_ids") or []
        total = rc.get("total") or 0
        share = total / len(lids) if lids else 0
        for lid in lids:
            series = resolve_series(lid, "", listing_series, keyword_rules)
            a = A(series)
            a["orders"] += 1
            a["revenue"] += share

    for rv in reviews:
        series = resolve_series(rv.get("listing_id"), "", listing_series, keyword_rules)
        a = A(series)
        a["reviews"] += 1
        if rv.get("rating"):
            a["rating_sum"] += rv["rating"]

    for r in pin_days.values():
        series = r.get("series") or resolve_series(
            r.get("listing_id"), "", listing_series, keyword_rules)
        a = A(series)
        a["impr"] += r.get("impressions", 0) or 0
        a["saves"] += r.get("saves", 0) or 0
        a["clicks"] += r.get("outbound_clicks", 0) or 0

    # ---- 评分与建议 ----
    def score(a):
        return (a["orders"] * 10 + a["revenue"] + a["favorers"] * 2
                + a["clicks"] * 1 + a["saves"] * 0.5)

    series_list = [s for s in order if s in agg] + [s for s in agg if s not in order]
    ranked = sorted(series_list, key=lambda s: score(agg[s]), reverse=True)
    tot_orders = sum(a["orders"] for a in agg.values())
    tot_rev = sum(a["revenue"] for a in agg.values())
    tot_fav = sum(a["favorers"] for a in agg.values())
    tot_clicks = sum(a["clicks"] for a in agg.values())

    lines = []
    lines.append(f"# ZenPixelWalls 流量周报（{start} ~ {label}）\n")
    lines.append(f"- 订单：{tot_orders} 笔 / 收入：${tot_rev:.2f}")
    lines.append(f"- 收藏净增：{tot_fav} / 新增评价：{sum(a['reviews'] for a in agg.values())}")
    lines.append(f"- Pinterest：{sum(a['impr'] for a in agg.values())} 曝光 / "
                 f"{sum(a['saves'] for a in agg.values())} 收藏 / "
                 f"{tot_clicks} 引流点击\n")
    lines.append("## 系列对比\n")
    lines.append("| 系列 | 订单 | 收入$ | 收藏+ | 评价 | Pin曝光 | Pin收藏 | 引流点击 | 在架数 |")
    lines.append("|---|---|---|---|---|---|---|---|---|")
    for s in ranked:
        a = agg[s]
        avg = (a["rating_sum"] / a["reviews"]) if a["reviews"] else "-"
        lines.append(f"| {names.get(s, s)} | {a['orders']} | {a['revenue']:.2f} | "
                     f"{a['favorers']} | {a['reviews']}({avg}) | {a['impr']} | "
                     f"{a['saves']} | {a['clicks']} | {len(a['listings'])} |")
    lines.append("")
    lines.append("## 结论（只写数据支持的）\n")
    if tot_orders == 0 and tot_fav <= 0 and tot_clicks == 0:
        lines.append("- 本周零订单、零收藏净增、零 Pinterest 引流点击："
                     "数据不足以排序任何系列。")
        lines.append("- 建议：维持现有生产计划，不做加减；下周复看。 "
                     "若连续两周零信号，优先检查 Pinterest 引流是否真正跑起来 "
                     "（pin 是否公开可见），再谈产品问题。")
        advice_add, advice_cut = "（数据不足，暂不点名）", "（数据不足，暂不点名）"
    else:
        top, bottom = ranked[0], ranked[-1]
        lines.append(f"- 本周信号最强的系列：{names.get(top, top)} "
                     f"（订单 {agg[top]['orders']} / 收入 ${agg[top]['revenue']:.2f} / "
                     f"收藏+{agg[top]['favorers']} / 引流点击 {agg[top]['clicks']}）。")
        if score(agg[bottom]) == 0 and len(ranked) > 1:
            lines.append(f"- 零信号系列：{names.get(bottom, bottom)} "
                         f"（在架 {len(agg[bottom]['listings'])} 个，本周订单/收藏/点击全零）——"
                         f"连续两周零信号则考虑停做或按新美术方向改造。")
        else:
            lines.append(f"- 相对最弱：{names.get(bottom, bottom)}，先观察一周再定。")
        advice_add, advice_cut = names.get(top, top), names.get(bottom, bottom)
    lines.append("")
    lines.append("## 下一波生产建议\n")
    lines.append(f"- 加做：{advice_add}")
    lines.append(f"- 减做/改造候选：{advice_cut}")
    lines.append("")
    lines.append("## 数据口径与盲区（必读）\n")
    lines.append("- views 字段：Etsy listing 资源自带，但 2026-09-20 起全为 0，"
                 "是否随真实流量递增【未验证】——本周不参与排名，仅记录。")
    lines.append("- Etsy v3 没有单品访客数/转化率接口：转化漏斗算不出来，"
                 "只能用 订单/收藏/引流点击 三个硬指标。")
    lines.append("- Pinterest analytics 有 1-2 天延迟，近 2 天数据可能偏低。")
    lines.append("- receipts 需要 transactions_r 权限；缺权限期间订单行为不可见，"
                 "周报会如实标注。")

    os.makedirs(REPORTS_DIR, exist_ok=True)
    path = os.path.join(REPORTS_DIR, f"weekly_{label}.md")
    open(path, "w").write("\n".join(lines) + "\n")
    print(f"report written: {path}")

    # ---- stdout digest（cron worker 转达用户） ----
    print("---DIGEST---")
    print(f"ZenPixelWalls 周报（{start}~{label}）：订单 {tot_orders} 笔 / "
          f"${tot_rev:.2f} / 收藏净增 {tot_fav} / 引流点击 {tot_clicks}")
    if tot_orders == 0 and tot_fav <= 0 and tot_clicks == 0:
        print("结论：本周零信号，数据不足以排序；维持生产计划，下周复看。")
    else:
        print(f"加做：{advice_add}；减做/改造候选：{advice_cut}。")


if __name__ == "__main__":
    main()
