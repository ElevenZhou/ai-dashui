# AI打水 · 赔率数据源选型与扫货系统架构调研

体育博彩赔率数据的获取路径、成本结构，以及一套「赔率变动 → 信号过滤 → EV/Kelly → 一键下单」扫货系统的架构建议。

👉 **在线阅读：[https://elevenzhou.github.io/ai-dashui/](https://elevenzhou.github.io/ai-dashui/)**（GitHub Pages）
👉 本地版：**[index.html](./index.html)**（浏览器直接打开，支持打印 / 导出 PDF）

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
├── docs/screenshots/              # 原始调研截图（Gemini 对话）
└── README.md
```

## 报告包含

1. **数据要买吗** — 免费额度对比表，为什么自建/爬虫不可持续
2. **用哪个数据源** — 四场景推荐矩阵、三个截图调研遗漏的关键信息
3. **扫货架构设计** — 接入 / 信号 / 决策 / 执行 / 数据 / 风控六层，含 MVP 方案
4. **GitHub 开源项目** — 14 个可直接参考的实现，分套利系统 / 监控告警 / 下单 SDK 三类
5. **落地路线** — 三步走，每步可回退

## 合规提示

体育博彩与套利在多数司法辖区（包括中国大陆）属于违法或严格监管行为，多数平台服务条款禁止自动化接入。本仓库内容仅供技术研究与学习参考，实盘风险自担。

## 参考

- [PinnAPI](http://pinnapi.com/) · [Pinnwire](https://pinnwire.com/) · [OddsPapi](https://oddspapi.io/) · [The Odds API](https://the-odds-api.com/)
- [danielcardeenas/surebet](https://github.com/danielcardeenas/surebet) · [Akinlua/sportybet](https://github.com/Akinlua/sportybet) · [iliyasone/ps3838api](https://github.com/iliyasone/ps3838api) · [Jayzinq/PROPPR](https://github.com/Jayzinq/PROPPR)

> 价格与政策随时变动，以服务商官网为准。
