#!/usr/bin/env python3
"""PinnAPI 探测工具 —— 读取 .env 中的 PINNAPI_KEY，验证套餐 / 拉数据 / 扫 EV。

仅依赖标准库，无需 pip install。

用法:
    python scripts/pinnapi_probe.py me                     # 套餐、配额、今日用量
    python scripts/pinnapi_probe.py markets 1 prematch     # 足球赛前快照（1=足球）
    python scripts/pinnapi_probe.py markets 2 live 5       # 网球滚球，只打印前 5 场
    python scripts/pinnapi_probe.py drops --min-drop 5 --sport 1 --limit 20 --min-ev 0.02
    python scripts/pinnapi_probe.py sse                    # 探测 SSE 权限

注意: Trial 档 100 请求/天、20/分钟，且 features.sse=false（推流需付费）。
      /api/drops 走 REST，Trial 可用，是免费验证 EV 逻辑的唯一途径。

实测口径（2026-10-23，300 条样本）:
      to/nvp-1   中位数 -6.0%，>0 占比 0%   → 平博自己的价天然含水，测不出 edge
      from/nvp-1 中位数 +3.2%，>0 占比 80%  → 软庄滞后时的理论 edge，这才是可用信号
      真实 edge 必须用「软庄实际挂价 / nvp - 1」，单靠 PinnAPI 无法得到。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASE = "https://pinnapi.com"


def load_env() -> None:
    """把仓库根目录 .env 读进 os.environ（不覆盖已有变量）。"""
    env_file = ROOT / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def api_key() -> str:
    load_env()
    key = os.environ.get("PINNAPI_KEY", "").strip()
    if not key or key.startswith("your_"):
        sys.exit("缺少 PINNAPI_KEY：请复制 .env.example 为 .env 并填入真实 key")
    return key


# Cloudflare 会拦截默认的 Python-urllib UA（error 1010），必须伪装成普通客户端
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"


def _headers(**extra: str) -> dict:
    h = {"x-portal-apikey": api_key(), "User-Agent": UA, "Accept": "application/json"}
    h.update(extra)
    return h


def get(path: str, params: dict | None = None, timeout: int = 40) -> dict:
    url = BASE + path
    if params:
        url += "?" + urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
    req = urllib.request.Request(url, headers=_headers())
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")[:300]
        sys.exit(f"HTTP {e.code} {path}: {body}")
    except urllib.error.URLError as e:
        sys.exit(f"网络失败 {path}: {e.reason}（若在代理环境，检查 127.0.0.1:7897 是否可用）")


def cmd_me(_: argparse.Namespace) -> None:
    d = get("/panel/api/me")
    plan = d.get("plan", {})
    print(f"账户     {d.get('email')}  (id={d.get('id')}, prefix={d.get('api_key_prefix')})")
    print(f"套餐     {plan.get('label')}  价格 ${plan.get('price')}  状态 {d.get('status')}")
    print(f"限额     {plan.get('limits')}")
    print(f"功能     SSE 推流: {'开' if plan.get('features', {}).get('sse') else '关闭（需升级）'}")
    print(f"今日用量 {d.get('usage')}")
    ws = d.get("ws_addon", {})
    print(f"WS 附加  eligible={ws.get('eligible')} active={ws.get('active')} ${ws.get('monthly_usd')}/mo")


def cmd_markets(a: argparse.Namespace) -> None:
    d = get("/kit/v1/markets", {"sport_id": a.sport, "event_type": a.type, "is_have_odds": "true"})
    events = d.get("events") or []
    print(f"{d.get('sport_name')} / {a.type}: {len(events)} 场 | last={d.get('last')} stale={d.get('stale')}")
    for e in events[: a.limit]:
        p0 = (e.get("periods") or {}).get("num_0", {})
        ml = p0.get("money_line") or {}
        tots = p0.get("totals") or {}
        tline = next(iter(tots.values()), {}) if tots else {}
        print(f"  [{e.get('event_id')}] {e.get('league_name')} | {e.get('home')} vs {e.get('away')}")
        print(f"      starts={e.get('starts')} live_status={e.get('live_status_id')}")
        print(f"      ML {ml}  | totals 示例 {tline}")
        print(f"      periods={list((e.get('periods') or {}).keys())} special={bool(e.get('special_markets'))}")


def cmd_drops(a: argparse.Namespace) -> None:
    params = {"limit": a.limit, "min_drop": a.min_drop, "sport_id": a.sport, "window": a.window}
    d = get("/api/drops", params)
    drops = d.get("drops") or []
    meta = d.get("meta") or {}
    print(f"缓冲区 total={d.get('total')} 返回 {len(drops)} 条 | live 跟踪={meta.get('tracked_outcomes')} 事件")

    # 口径说明（实测结论，勿改回 to）：
    #   to / nvp - 1  恒为负（实测中位数 -6%），因为 to 是平博自己的价，天然含水位 → 测不出 edge
    #   from / nvp - 1 是「软庄还没跟上、仍挂旧价」时的理论 edge（实测中位数 +3.2%，80% 为正）
    def edge(x: dict) -> float:
        ref = x.get(a.metric)
        if not x.get("nvp") or not ref:
            return float("-inf")
        return ref / x["nvp"] - 1

    if a.min_ev is not None:
        drops = [x for x in drops if edge(x) >= a.min_ev]
        print(f"按 {a.metric}/nvp-1 ≥ {a.min_ev:.1%} 过滤后剩 {len(drops)} 条")
    print(f"{'edge':>7} {'跌幅':>6} {'旧价':>7} {'新价':>7} {'nvp':>7}  {'运动':<10} 赛事 / 盘口")
    print("-" * 108)
    for x in sorted(drops, key=edge, reverse=True):
        flag = "滚球" if x.get("is_live") else "赛前"
        side = x.get("designation") or x.get("side") or ""
        print(
            f"{edge(x):>6.2%} {x.get('drop_pct', 0):>5.1f}% {x.get('from', 0):>7.3f} {x.get('to', 0):>7.3f} "
            f"{x.get('nvp', 0):>7.3f}  {x.get('sport_name', ''):<10} "
            f"{x.get('home')} vs {x.get('away')} | {x.get('market')} {side} {x.get('points') or ''} "
            f"p{x.get('period')} [{flag}]"
        )


def cmd_sse(_: argparse.Namespace) -> None:
    url = f"{BASE}/odds-drop?key={api_key()}&min_drop=5"
    req = urllib.request.Request(url, headers={"Accept": "text/event-stream", "User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=6) as r:
            print(f"SSE 可用 (HTTP {r.status})，首帧：")
            print(r.readline().decode("utf-8", "replace").strip())
    except urllib.error.HTTPError as e:
        print(f"SSE 不可用 HTTP {e.code}: {e.read().decode('utf-8', 'replace')[:200]}")
    except Exception as e:  # 超时=连接建立成功但没数据，也算可用
        print(f"SSE 连接结果: {type(e).__name__}: {e}")


def main() -> None:
    ap = argparse.ArgumentParser(description="PinnAPI 探测工具")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("me").set_defaults(fn=cmd_me)
    sub.add_parser("sse").set_defaults(fn=cmd_sse)

    m = sub.add_parser("markets")
    m.add_argument("sport", type=int, help="1足球 2网球 3篮球 4冰球 5美式 6棒球 11电竞")
    m.add_argument("type", choices=["prematch", "live"], nargs="?", default="prematch")
    m.add_argument("limit", type=int, nargs="?", default=3, help="打印前 N 场")
    m.set_defaults(fn=cmd_markets)

    d = sub.add_parser("drops")
    d.add_argument("--min-drop", type=float, default=5.0, help="最小跌幅%%（默认 5）")
    d.add_argument("--sport", type=int, default=None)
    d.add_argument("--limit", type=int, default=30)
    d.add_argument("--window", type=str, default=None, help="时间窗，如 10m / 1h")
    d.add_argument("--min-ev", type=float, default=None, help="按 edge 过滤，如 0.03")
    d.add_argument(
        "--metric",
        choices=["from", "to"],
        default="from",
        help="边缘口径：from=假设软庄滞后仍挂旧价（推荐）；to=平博新价，恒为负仅作对照",
    )
    d.set_defaults(fn=cmd_drops)

    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
