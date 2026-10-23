# AI打水 · 赔率数据源选型与扫货系统架构调研

体育博彩赔率数据的获取路径、成本结构，以及一套「赔率变动 → 信号过滤 → EV/Kelly → 一键下单」扫货系统的架构建议。

> **当前版本 `v0.1.0`** · 阶段：**调研收口，暂停开发**（2026-10-23）
> 已产出：选型报告 + 可用的 PinnAPI 探测工具 + 一批实测结论（含两个推翻文档口径的发现）。尚未写 MVP 主程序。

👉 **在线阅读：[https://elevenzhou.github.io/ai-dashui/](https://elevenzhou.github.io/ai-dashui/)**（GitHub Pages）
👉 本地版：**[index.html](./index.html)**（浏览器直接打开，支持打印 / 导出 PDF）

## 项目状态

| 模块 | 状态 | 说明 |
|---|---|---|
| 数据源选型调研 | ✅ 完成 | 见 `report.md` / `index.html` |
| GitHub 开源项目清单 | ✅ 完成 | 14 个项目，分三类 |
| 扫货系统六层架构设计 | ✅ 完成 | 接入 → 信号 → 决策 → 执行 → 数据 → 风控 |
| PinnAPI 接入验证 | ✅ 完成 | trial key 实测，`scripts/pinnapi_probe.py` 可用 |
| EV 口径校准 | ✅ 完成 | 推翻文档公式，见下方「EV 口径的坑」 |
| 赛事数据/赛况能力盘点 | ✅ 完成 | 有赛程与实时比分，无历史/统计/阵容 |
| **MVP 主程序** | ⬜ 未开始 | SSE 消费者 → 信号 → 通知，待续 |
| **软庄数据源** | ⬜ 未开始 | 没有它算不出真实 edge（关键缺口） |
| **通知 / 自动下单 / 回测** | ⬜ 未开始 | 依赖前两项 |

## 结论速览

- **开源的是代码，不是数据。** GitHub 上的套利项目都是框架，打开 `.env` 第一件事就是填 API key。数据是这套系统唯一必须持续付费的部分（$89–500/月）。
- **平博官方 API 已于 2025-07-23 关闭公开注册**，数据只剩第三方数据商（PinnAPI / Pinnwire）或 PS3838 白标两条路。
- **推荐：** 手动扫货用 PinnAPI（SSE `odds-drop` 服务端阈值过滤）；预算优先用 Pinnwire（$89/月，含 no-vig 公允价）；跨平台 Value 用 OddsPapi / The Odds API WebSocket 档；自动下单走 PS3838 API + `ps3838api`。
- **避坑：** OddsJam 等美制聚合商不含 Pinnacle / Bet365 核心盘口，付费前必须核对 Bookmakers List。

## 仓库结构

```
.
├── index.html                     # 调研报告（单页，带目录与阅读进度）
├── report.md                      # 报告 Markdown 源
├── scripts/pinnapi_probe.py       # PinnAPI 探测工具（验证套餐 / 拉快照 / 扫 drops edge）
├── .env.example                   # 凭据模板（复制为 .env 后填 key，.env 不入库）
├── docs/screenshots/              # 原始调研截图（Gemini 对话）
└── README.md
```

## 快速开始（已验证可用）

```bash
cp .env.example .env          # 填入 PINNAPI_KEY
python scripts/pinnapi_probe.py me                 # 套餐、限额、今日用量
python scripts/pinnapi_probe.py markets 1 prematch # 足球赛前快照（1足球 2网球 3篮球 11电竞）
python scripts/pinnapi_probe.py live 3             # 篮球在赛赛事 + 实时比分/节次/剩余时间
python scripts/pinnapi_probe.py drops --min-drop 8 --min-ev 0.05   # 扫可下手的降赔
python scripts/pinnapi_probe.py sse                # 探测 SSE 权限
```

仅用 Python 标准库，无需 pip install。Trial 档额度 100 请求/天、20/分钟，脚本每次调用算 1 次。

### 赛事数据与实时赛况（实测）

**有，但定位是「有盘口的比赛」，不是独立赛程/赛况 API。**

| 能力 | 有没有 | 实测细节 |
|---|---|---|
| 赛程（比赛列表） | ✅ | 足球赛前 **2381 场 / 253 个联赛 / 覆盖 25 天**（2026-10-10 → 11-04）；字段 `event_id / league_name / starts / home / away / parent_id` |
| 完整盘口树 | ✅ | 每场带全部 period（足球 p0/p1/p8，网球最多 18 个），含 `max` 限额与 `nvp` |
| 实时比分/时钟 | ✅ 仅 REST | 篮球：`quarter` `time_remaining_in_qtr` `state.home.score` `scoreByQuarter`；网球：`setsWon` `gamesBySet` `points`(0/15/30/40/Ad) `serving` |
| 足球赛况字段 | 文档声明 | `redCards` `yellowCards` `corners` `match.minutes`（本次未实测到，见下方异常） |
| drop 流里的赛况 | ⚠️ 部分 | drop 对象自带 `score`（如 `"1:1"`）和 `match_minute`，**但没有完整 state** |
| 历史赛果 / 历史赔率 | ❌ | 官方 FAQ 明确 No；`/api/drops` 只留 ~3 小时 |
| 技术统计 / 阵容 / 伤停 | ❌ | `home_stats` 只有 `{"period":0}` 这样的索引，无具体数值 |

三个直接影响架构的点：

1. **`state` 只在 REST**，SSE drop 流里没有 → 想靠赛况判断「进球导致降赔」还是「纯资金面」，必须在收到 drop 后回查 `/kit/v1/details`（多一次请求，且 Trial 100/天扛不住）。
2. **盘口里的 `meta.home_score / away_score` 会滞后**：实测 tennis 事件 `state` 已有比分而 `meta` 仍是 `null`，两者不要混用。
3. **无盘口的比赛不出现** —— 想要纯赛程日历（未开盘的远期赛事、无赔率赛事）得另找赛事数据源（API-Football / Sportradar）。

**未解异常（待观察）**：实测时足球 live 在 `/kit/v1/markets` 返回 **0 场**，但 `/api/drops` 里有 8 条足球 live 降赔（Atlas vs Club Leon 1:1 / 第 136 分钟），用 `/kit/v1/details` 查这两场也返回 0 场；同时 `/api/drops` 的 `meta.events_in_store ≈ 15`，正好等于网球 10 + 篮球 5 → **足球 live 没进 live 商店**。结论：足球赛况目前拉不到，需向 `info@pinnapi.com` 确认是否为已知问题。

### 实测发现：EV 口径的坑

文档示例写 `EV = to_price / nvp - 1`，但把平博**自己**的新价代入后**恒为负**（300 条样本中位数 −6.0%，无一条为正）——因为 `to` 本身就是含水的庄家价，这个式子只是在量水位，量不出 edge。

可用的两种口径：

| 口径 | 300 条样本中位数 | 含义 |
|---|---|---|
| `from / nvp - 1` | **+3.2%**（80% 为正） | 软庄还没跟上、仍挂旧价时的理论 edge，可作信号排序依据 |
| `软庄实际挂价 / nvp - 1` | — | 唯一真实的 edge，但需要第二个（软庄）数据源 |

结论：**PinnAPI 的 `nvp` 是公允锚点，不是收益来源**。单靠它只能算「平博动了多少」，要算「我能赚多少」必须有软庄价格。

## 报告包含

1. **数据要买吗** — 免费额度对比表，为什么自建/爬虫不可持续
2. **用哪个数据源** — 四场景推荐矩阵、三个截图调研遗漏的关键信息
3. **扫货架构设计** — 接入 / 信号 / 决策 / 执行 / 数据 / 风控六层，含 MVP 方案
4. **GitHub 开源项目** — 14 个可直接参考的实现，分套利系统 / 监控告警 / 下单 SDK 三类
5. **落地路线** — 三步走，每步可回退

## 下一步（续做时从这里开始）

按依赖顺序，前两步不做完，后面的都没有意义：

1. **补一个软庄数据源**（关键缺口）。`nvp` 只能给公允锚点，真实 edge 需要软庄实际挂价。候选：OddsPapi / The Odds API（跨平台聚合），或直接抓某个软庄页面。**没有这一步，「EV 决策层」无法落地。**
2. **确认足球 live 异常**：发邮件 `info@pinnapi.com` 问 `sport_id=1&event_type=live` 为何返回 0 场（详见下方异常记录）。足球是降赔量最大的项目，赛况缺失会让信号过滤少一个维度。
3. **升到 Drops 档（$99/月）**开 SSE。trial 的 100 请求/天扛不住轮询，只能做验证不能做生产。
4. **写 MVP 主程序**：SSE 消费 → 去重冷却 → `from/nvp` 排序 → Telegram 深链接 → SQLite 快照（约 300–500 行）。
5. 可选：`/kit/v1/details` 回查 `state`，做「进球降赔 vs 资金面降赔」二次过滤。

## 变更记录

### v0.1.0 — 2026-10-23（调研收口版）
- 新增 `report.md` + `index.html` 双版调研报告（含六层架构 SVG、目录导航、阅读进度、打印样式）
- 新增 `scripts/pinnapi_probe.py`：`me` / `markets` / `live` / `drops` / `sse` 五个子命令，仅标准库
- 归档 6 张原始调研截图到 `docs/screenshots/`
- GitHub Pages 上线：https://elevenzhou.github.io/ai-dashui/
- **实测推翻文档口径**：`EV = to/nvp - 1` 恒为负（中位数 −6.0%，0 条为正），正确信号是 `from/nvp - 1`（+3.2%）
- **实测盘点赛况能力**：`state` 仅 REST 有、drop 流无；足球 live 在 markets 返回 0 场（未解）
- 完成 trial key 接入验证（100 请求/天，`features.sse=false`）

## 合规提示

体育博彩与套利在多数司法辖区（包括中国大陆）属于违法或严格监管行为，多数平台服务条款禁止自动化接入。本仓库内容仅供技术研究与学习参考，实盘风险自担。

## 参考

- [PinnAPI](http://pinnapi.com/) · [Pinnwire](https://pinnwire.com/) · [OddsPapi](https://oddspapi.io/) · [The Odds API](https://the-odds-api.com/)
- [danielcardeenas/surebet](https://github.com/danielcardeenas/surebet) · [Akinlua/sportybet](https://github.com/Akinlua/sportybet) · [iliyasone/ps3838api](https://github.com/iliyasone/ps3838api) · [Jayzinq/PROPPR](https://github.com/Jayzinq/PROPPR)

> 价格与政策随时变动，以服务商官网为准。
