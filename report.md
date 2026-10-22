# AI打水 — 赔率数据源选型与扫货系统架构建议

> 基于工作区 6 张 Gemini 调研截图 + 2026-10-22 补充调研整理。
> 目的：补全 Gemini 回答中被截断的「扫货系统核心架构设计建议」，给出明确的数据源推荐，并列出 GitHub 上可直接参考的开源实现。
>
> 📄 排版版：见 [index.html](./index.html)（浏览器打开，支持打印导出 PDF）

---

## 〇、数据这块：开源的是代码，不是数据

**结论：对，数据必须买，而且是这套系统里唯一必须持续付费、无法自建的部分。**

GitHub 上的套利项目开源的只是框架和逻辑（取数、赛事匹配、套利计算、注额分配、推送）。它们都不自带数据——每个项目打开 `.env` 第一件事就是让你填 API key。

原因：

1. **实时赔率是商业数据。** 平博这类 sharp 庄家的赔率变动就是市场信号，数据商靠转售它赚钱。
2. **官方渠道已关死。** 平博 2025-07-23 起关闭公开 API 注册，只剩商业协议客户。
3. **免费额度只够测试。**

| 获取方式 | 免费额度 | 能否支撑实盘 | 问题 |
|---|---|---|---|
| The Odds API | 约 500 次/月（以官网为准） | 不能 | REST 轮询 60s 起步，免费档只够验证逻辑 |
| OddsPapi | 250 次/月，含历史赔率 | 不能 | 实时需买 WebSocket 档 |
| Pinnwire | demo key：20 req/min、100 req/天 | 仅验证延迟 | 免费永久但每天 100 次 |
| PinnAPI | 无长期免费档 | 能 | $100–300/月 |
| 自己爬平博网页 | 0 元 | 不推荐 | 反爬强、延迟秒级、封 IP、违反 ToS |

**成本结构：代码成本 ≈ 0，数据成本 = 固定月费（$89–500/月）。** 想省钱只能降数据源等级，砍不掉这一项。

另需分清：**数据商只卖数据，不卖下单能力。** 买了 PinnAPI 仍要自己去平博页面点；要全自动下单得走 PS3838 API（平博白标，经 broker 开户），那是独立账户通道。

---

## 一、结论先行：用哪个？

### 推荐矩阵

| 场景 | 推荐方案 | 延迟 | 价格 | 核心理由 |
|---|---|---|---|---|
| **只打平博、手动扫货**（截图中的首选路径） | **PinnAPI**（专项平博 WebSocket/SSE） | 20–50ms | $100–300/月 | 单一数据源零噪音；SSE `odds-drop` 端点支持**服务端阈值过滤**（`min_drop=N`），客户端只收"值得出手"的变动；专为高频对冲设计 |
| 预算优先、同样只要平博数据 | **Pinnwire** | 未公开（宣称极速） | **$89/月** flat，有免费 demo key | 比 PinnAPI 便宜；REST + WebSocket + SSE 三种接入；每个赔率自带 no-vig 公允价（nvp）；13 个体育项目 |
| 需要跨平台套利 / 看差价 Value | **OddsPapi / The Odds API**（高阶 WebSocket 版） | 较快 | $200–500/月 | 聚合 350+ 家博彩公司（含 Pinnacle、Bet365）；可直接输出"差价/Value"；OddsPapi 免费档含历史赔率数据 |
| 要**全自动下单**（无人值守） | **PS3838 API**（平博白标，走 betting broker 开户） | 官方同源 | 无 API 费，broker 账户模式 | 唯一能对平博真实下单的官方通道；`api.ps3838.com` 与已关闭的平博官方 API 端点完全一致；可用开源库 `ps3838api` |

### 三个必须知道的新信息（截图调研时没有覆盖到）

1. **平博官方 API 已于 2025-07-23 关闭公开注册。** 不再有开放的 developer signup，官方渠道只剩商业数据协议客户。平博数据的现实获取路径只剩两条：第三方数据商（PinnAPI / Pinnwire），或 PS3838（平博自家白标，经 broker 如 Asianconnect 开户，API 同源）。
2. **Pinnwire 是比 PinnAPI 更便宜的平博数据备选**（$89/月 vs $100–300/月），且提供免费 demo key，可以先验证端到端延迟再付费。
3. **Goalserve / Sportradar 这类老牌数据商只卖赛事数据（比分、赛程、球员统计），不提供博彩赔率**——如果你的系统只需要"赛事框架 + 平博赔率"，平博专线 + 免费赛程 API 就够，不用买它们的套餐。

### 避坑（再次强调）

- **不要买 OddsJam API 等美制聚合商**：宣传极快，但不含 Pinnacle 和 Bet365 的核心盘口。付费前必须让对方提供支持的博彩公司列表（Bookmakers List）并逐家核对。
- The Odds API / OddsPapi 免费档（约 250–500 次/月）只能用于测试，REST 轮询模式（60s+）**不够快**，实盘必须买 WebSocket 档。
- 所有"扫货"速度都以**端到端延迟**计：数据商节点 → 你的服务器 → 通知到达你手机/浏览器 → 你完成点击。数据商的 20–50ms 只是第一段，你的通知链路（Telegram/WebSocket）通常要 100–500ms，手动点击再快也要秒级。**想真正"快"，最终都要走到自动下单。**

---

## 二、补全：扫货系统的核心架构设计建议

> Gemini 原回答在此处被截断："二、扫货系统的核心架构设计建议 —— 买到 API 后，为了能让'手工点得更快'，建议搭……"
> 以下为补全内容，并融合了本次调研中 GitHub 开源项目验证过的最佳实践。

### 总体架构（六层）

```
┌─────────────────────────────────────────────────────────────┐
│  ① 接入层 Ingest                                            │
│     SSE / WebSocket 长连接（PinnAPI odds-drop / Pinnwire）   │
│     原则：永远用"推"，不用"拉"                                │
├─────────────────────────────────────────────────────────────┤
│  ② 信号层 Signal                                            │
│     服务端阈值过滤（min_drop）→ 去重/冷却 → 赔率回跳过滤       │
├─────────────────────────────────────────────────────────────┤
│  ③ 决策层 Decision                                          │
│     no-vig 折算 → EV 计算 → Kelly 注额 → 限额检查             │
├─────────────────────────────────────────────────────────────┤
│  ④ 执行层 Act                                               │
│     Telegram/桌面弹窗（带深链接） → 一键到投注单               │
│     （进阶）PS3838 API 自动下单                               │
├─────────────────────────────────────────────────────────────┤
│  ⑤ 数据层 Storage                                           │
│     SQLite/Redis 赔率快照，用于回测与统计真实 edge            │
├─────────────────────────────────────────────────────────────┤
│  ⑥ 风控层 Guard                                             │
│     账号限额跟踪、频率控制、异常熔断                           │
└─────────────────────────────────────────────────────────────┘
```

### 分层要点

**① 接入层 —— 能用推就别用拉**
- 首选 SSE（Server-Sent Events）：比 WebSocket 简单、断线自动重连、穿透防火墙/CDN 友好。PinnAPI 的 `odds-drop` 端点就是 SSE，`min_drop=7` 表示只推送跌幅 ≥7% 的变动，过滤在服务端完成，客户端代码极薄。
- 如果只能用 REST（比如免费档），轮询间隔不低于 90s，且只在开赛前 1–2 小时的窗口轮询——赔率变动最密集的时段才值得花请求配额。
- 多数据源时，各源独立长连接 + 独立断线重连，一个源挂掉不影响其他源。

**② 信号层 —— 少即是多**
- 阈值过滤放服务端；本地只做轻量二次确认。
- **去重与冷却**：同一赛事 + 同一市场（如 1X2 主胜）的信号 N 秒内只报一次，防止赔率连续小幅跳动刷屏。
- **回跳过滤**：prematch 流用 `recheck=N` 参数，让数据商对每个 alert 持留 N 秒复核，过滤"假跌破"（flicker）。
- 按体育项目分频道推送（足球/网球/篮球各一个 Telegram 频道），避免互相干扰。

**③ 决策层 —— 信号里直接带答案**
- 用数据商的 no-vig 公允价（Pinnwire 的 nvp，或本地用 power/shin 方法 devig）算出真实概率。
- EV = 目标盘赔率 × 真实概率 − 1；EV > 0 才推送。
- 注额用分数 Kelly（开源项目通用做法是 30% 全 Kelly，控制方差）。
- **信号消息里直接给出：赛事、市场、当前赔率、建议注额、预期收益**——不要让人现算，手工扫货的每一秒都是钱。

**④ 执行层 —— 让"点到"这一步最短**
- Telegram 消息内嵌平博投注页深链接（带 eventId / lineId），点击即跳到投注单，赔率和盘口已锁定在链接参数里。
- 桌面端：声音 + 弹窗（参考 PROPPR 的 Telegram bot 架构，本地再加一层 OS 通知）。
- 浏览器保持平博登录态；常用注额预设（如 100/500/1000）减少输入。
- **进阶（真正的速度）**：走 PS3838 API 自动下单——GitHub 上 `iliyasone/ps3838api` 提供完整的 Python 封装（查余额、拉 fixtures/odds、`place_straight_bet` 下单、`get_bets` 查状态），可直接作为执行层 SDK。

**⑤ 数据层 —— 为回测留种子**
- 每次推送的信号 + 当时的赔率快照落 SQLite（单表即可：时间、赛事、市场、from_price、to_price、EV、注额、是否出手、赛后结果）。
- 两周后就能统计：哪类信号真能打到、实际 edge 是多少、哪些联赛值得盯。

**⑥ 风控层 —— 活得久比打得快重要**
- **限额跟踪**：平博对盈利账户会限额，系统记录每个账号各市场的最大可下注额，超限的信号直接丢弃。
- 频率控制：每小时出手次数上限，防止信号风暴下重仓。
- 异常熔断：接口连续报错、赔率数据明显异常（如 1.01 这种）时自动暂停并告警。

### 最小可行组合（MVP，一周可落地）

```
PinnAPI SSE（min_drop=5）
   → Python asyncio 消费者
      → 本地 EV + 30% Kelly 计算
         → Telegram Bot 消息（赛事/赔率/建议注额/投注页深链接）
            → SQLite 快照落库
```

这个 MVP 只依赖一个 API key 和一个 Telegram bot token，全部代码约 300–500 行。验证有效后再升级 WebSocket 全量流 + PS3838 自动下单。

---

## 三、GitHub 开源项目清单（可直接参考）

### A. 完整套利 / 扫货系统

| 项目 | 语言 | 一句话 | 值得抄什么 |
|---|---|---|---|
| [danielcardeenas/surebet](https://github.com/danielcardeenas/surebet) | TypeScript | 实时套利扫描 + 下单软件，MIT | **架构最优雅的一个**：Retriever（取数）/Arber（策略）接口分离，websocket/API/Selenium 取数即插即用；fuzzball 模糊匹配跨平台同一赛事；内置 H2H、1X2 策略 |
| [Akinlua/sportybet（BetAlert）](https://github.com/Akinlua/sportybet) | Python | **监控平博赔率 → 自动在 Bet9ja 下注**，EV + Kelly | 与"AI打水"模式最接近的完整闭环：平博做 sharp 信号源、soft 平台执行；power 法 devig、30% Kelly、Selenium 自动投注全流程 |
| [Jayzinq/PROPPR](https://github.com/Jayzinq/PROPPR) | Python | 微服务级赔率情报平台：套利检测、EV 告警、WebSocket 更新、Telegram 分发 | 生产级架构参考：WebSocketUpdater 服务、MongoDB 统一数据层、Team/Player/EV/Arb 多 bot 分发 |
| [harvey-allen/arbitrage-sports-betting](https://github.com/harvey-allen/arbitrage-sports-betting) | Python | 基于 The Odds API 的套利检测 + Telegram 通知 + Docker | 干净适合入门：套利数学（stake 分配/ROI）、策略基类、容器化部署 |

### B. 赔率监控 / 变动告警（steam move）

| 项目 | 语言 | 一句话 | 值得抄什么 |
|---|---|---|---|
| [SteveParadox/Api-bet-monitor](https://github.com/SteveParadox/Api-bet-monitor) | Python | FastAPI + SQLAlchemy 赔率异常监控：平局赔率 30 分钟跌 ≥20%、总进球线移动 ≥1.0 即告警 | 异常检测规则设计 + 赔率时间线存库 + Telegram/webhook 告警、scheduler 架构 |
| [coss1333/Surebet-notifier](https://github.com/coss1333/Surebet-notifier) | Python | 轻量 surebet 通知 bot：轮询赔率，Σ(1/odds)<1 即推 Telegram | 最小实现，几百行跑通全流程；含 2-way / 1X2 套利判断、edge 阈值、去重 |
| [TessaRichardson/SureBetsBot](https://github.com/TessaRichardson/SureBetsBot) | Python | 套利检测 + Kelly 注额 + Streamlit 看板 | Streamlit 监控面板（bankroll 曲线、实时 arbs）可直接用作本地 dashboard |
| [BrandonBell2025/PinnacleScrape](https://github.com/BrandonBell2025/PinnacleScrape) | Python | 平博赔率爬虫（NFL/大学橄榄球 spread）存 CSV | 没有 API key 时的兜底数据获取方案（注意平台 ToS 风险） |
| OddsPapi 官方 examples（oddspapi.io 博客） | Python | Streamlit 赔率对比看板 + Steam Move Detector 教程 | 从零搭建的完整教程：fetch→best price→detect_arb→alert，含 Telegram/Discord 推送代码 |

### C. 平博 / PS3838 API 客户端与自动下单

| 项目 | 一句话 | 值得抄什么 |
|---|---|---|
| [iliyasone/ps3838api](https://github.com/iliyasone/ps3838api) | 平博 PS3838 API 的轻量 Python 封装 | **自动下单的唯一现实通道**：PinnacleClient 拉 fixtures/odds、`place_straight_bet` 下单、`get_bets` 查状态；支持 V4 端点；pip 可直接装 |
| [w1r2p1/hello-world-pinnacle-bet-api](https://github.com/w1r2p1/hello-world-pinnacle-bet-api) | 平博 API 自动投注策略 Hello World（bukosabino 原版 fork） | 自动下注策略的最小骨架：赛事过滤→赔率判断→下单→结果落 CSV |
| [chrisgillam/polymarket_gambot](https://github.com/chrisgillam/polymarket-gambot) | 拉平博 sharp 价 → 对比 Polymarket → Kelly 下注 | 跨市场价值投注的完整方法论；FOK 订单防滑点设计值得借鉴 |
| [Pinnwire-Pinnacle-Odds-API](https://github.com/Pinnwire-Pinnacle-Odds-API) | Pinnwire 官方 SDK 组织（Node/Python client + MCP server） | 平博数据 API 的客户端工具，含 no-vig 价计算 |

### 选型建议

- **想抄架构** → `danielcardeenas/surebet`（TypeScript，接口设计最好）
- **想抄"平博监控 → 执行"闭环** → `Akinlua/sportybet`（Python，和你的场景几乎一样）
- **想抄生产级工程** → `Jayzinq/PROPPR`
- **要自动下单** → `iliyasone/ps3838api` + 上面的监控项目组合

---

## 四、最终推荐路线

```
第 1 步（本周）  买 PinnAPI 月付（$100-300）→ 接 SSE odds-drop
                 → 按第二节 MVP 搭起来 → 手工扫货，验证信号质量
第 2 步（验证后）加 OddsPapi/The Odds API WebSocket 档
                 → 扩展跨平台差价（Value）检测
第 3 步（放大）  Asianconnect 开 broker 户拿 PS3838 API
                 → 用 ps3838api 把执行层改成自动下单
                 → 限额/风控层跟上
```

每步都是"可回退"的：月付数据商随时可停，broker 户不开也不影响前两步。

---

## 五、合规提示

体育博彩与套利在多数司法辖区（包括中国大陆）属于违法或严格监管行为，且多数平台 ToS 禁止自动化接入。本报告及所列开源项目仅供技术研究与学习参考，实盘前请自行确认所在地法规与平台条款，风险自担。
