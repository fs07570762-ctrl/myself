---
name: a-share-analysis-models
description: A 股股票分析模型自动调度。用户要求分析股票/个股/自选股、板块选股或比较、找有投资价值的标的、估值与基本面研究、技术面与筹码分析、大盘复盘、财报业绩解读、事件影响、投资组合风险、市场消息/舆情/新闻捕捉、量化资金走向/主力资金/北向/两融/龙虎榜/游资席位，或提到 daily_stock_analysis / Qlib / TradingAgents-CN / InStock / CNEquity / FinGPT / aiagents-stock / TradingAgents-astock 等分析框架时，必须自动加载本技能，按 registry.json 的任务路由调用对应模型，并用 models.py 做可复现计算。触发词：A股、个股、选股、板块、行情、K线、技术指标、MACD、筹码、因子、多因子、估值、PE、PB、ROE、扣非、三季报、复盘、研报、投资价值、目标价、仓位、回测、资金流向、主力资金、北向资金、两融、龙虎榜、游资、席位、舆情、新闻情绪、财联社、快讯、传闻、小作文、公告监控、解禁、stock analysis、screener、valuation、money flow、news sentiment。本技能只提供方法论与计算，不代替真实取数，不生成投资建议。
license: MIT
version: 1.1.0
display_name: A股分析模型调度
metadata:
  enabled: true
  type: workflow
  category:
    - "金融研究"
    - "数据分析"
  tags:
    - "A股"
    - "选股"
    - "多因子"
    - "技术分析"
    - "决策仪表盘"
---

# A 股分析模型自动调度

**用途**：让每一次股票分析任务都自动复用 8 个高关注度开源项目的分析模型，而不是每次临时重新设计框架。2026-11-16 起新增 4 个增强模型，专攻**市场消息捕捉**与**量化资金走向**。

**安装**：从本仓库 clone 后执行 `python a-share-models/install.py`，会把本目录的 `SKILL.md / registry.json / models.py / projects.json` 复制到 `C:/Users/Administrator/.workbuddy/skills/a-share-analysis-models/`，由 WorkBuddy 按触发词自动加载。也可直接把本目录整体复制过去。

## 0. 必须先做的事（强制）

1. 同时加载 `workbuddy-finance-skill`（金融场景总入口，含个股研究 / 估值 / 技术面 / HTML 规范方法论）。
2. 读取同目录 `registry.json` —— 模型注册表、A 股适配证据、部署门槛与任务路由都以它为准。
3. 调用 `route(task)` 得到本次任务应使用的模型组合，**不要凭印象挑模型**。
4. 取数并核对基准日；数据缺失标 `[MISSING]`，超过 90 天标 `[STALE]`。
5. 用 `models.py` 做计算（纯标准库，Python 3.8+ 可直接运行，已在 3.13 验证），再写结论。
6. 输出末尾固定免责声明。

> 注册表核实于 2026-11-16（首批 4 项核实于 2026-11-15），star / fork 是瞬时值；引用具体数字需重新查 GitHub API 或注明查询日期。

## 1. 模型注册表（8 个来源）

| 模型 ID | 上游项目 | 关注度 | 复用什么 | 何时用 |
|---|---|---|---|---|
| `dsa_decision_dashboard` | `ZhuLinsen/daily_stock_analysis` | 72,376 ★ (11-15) | 决策仪表盘四段结构 `core_conclusion / data_perspective / intelligence / battle_plan`；`--market-review` 复盘 | **所有任务的输出契约** |
| `qlib_multifactor` | `microsoft/qlib` | 50,294 ★ (11-15) | Alpha158/Alpha360 因子思想 → 横截面标准化、加权打分、因子贡献归因 | 选股、板块内排序、因子归因、回测设计 |
| `tradingagents_cn_debate` | `hsliuping/TradingAgents-CN` | 32,957 ★ (11-15) | 多智能体角色分工 → 多空辩论 → 风控裁决 → 证伪条件 | 个股深度、逻辑检验、财报/事件解读 |
| `instock_technical_cyq` | `myhhub/stock` | 15,212 ★ (11-15) | 32 类技术指标、61 种 K 线形态、筹码分布 CYQ、11 个策略模板、选股回测 | 技术面、择时校验、筹码结构 |
| `cnequity_moneyflow` | `rootSunc/CNEquity` | 1,038 ★ (11-16) | 五维资金面分层框架（北向/两融/龙虎榜/大宗/主力流向）交叉验证；L7 舆情七要素 | **资金走向、龙虎榜、消息捕捉的数据结构骨架** |
| `tradingagents_astock_sentiment` | `simonlin1212/TradingAgents-astock` | 3,986 ★ (11-16) | A 股特化角色：游资席位画像、政策事件分级、解禁监控；全 Apache-2.0 | 游资行为、政策事件、资金行为解释 |
| `aiagents_stock_news` | `oficcejo/aiagents-stock` | 2,089 ★ (11-16) | 消息三层漏斗（20 源聚合→去重热度→多角色解读）；龙虎榜五视角 | **消息捕捉广度、龙虎榜复盘**（⚠️ 无许可证，仅方法论） |
| `fingpt_sentiment` | `AI4Finance-Foundation/FinGPT` | 21,578 ★ (11-16) | 金融新闻情绪分析管道（中文 V1，v3.3 F1 0.882）；规则版等价实现 | **新闻情绪打分、事件影响**（原生需 GPU，本机跑规则版） |

八个上游项目以 **git submodule** 固定在 `vendors/`（见 `projects.json` 的 `pinned_sha`）。本仓库**不复制上游源码**；`python a-share-models/bootstrap.py` 按需浅克隆。

**筛选口径**：只收「产出分析结论」的项目，排除高 star 但属数据层/执行层的 `vnpy/vnpy`(46,382★)、`akfamily/akshare`(23,341★)、`waditu/tushare`(15,494★) 等。

**必须向用户披露的风险（均有 README 一手依据）**：
- `microsoft/qlib`：官方数据集因数据安全策略暂时禁用；官方 cn 数据由 Yahoo Finance 爬取且自述 "might not be perfect"；README 仅列 Python 3.8–3.12。
- `hsliuping/TradingAgents-CN`：**混合授权**，`app/`、`frontend/`、`core/` 为专有 source-available，禁止再分发与商业使用；需 MongoDB / Redis / Node / LLM Key。**默认不自动初始化**，使用前阅读上游 LICENSE。
- `myhhub/stock`：代码最后推送 2026-04-02，**[STALE] 227 天**（截至 2026-11-15）。仅复用其技术面方法论，**不要依赖其数据抓取层**。活跃替代：`shy3130/tick-stock-panel`。
- `oficcejo/aiagents-stock`：**无开源许可证**（默认版权），只允许学习方法论，禁止复制/再分发其代码；其问财 cookie / Playwright 绕指纹数据通道在本体系**禁用**；其输出边界比本体系宽松，调用时必须叠加本体系合规护栏。
- `rootSunc/CNEquity`：数据集为日更链路，调用其框架前必须核对**数据基准日**是否为当日。
- `AI4Finance-Foundation/FinGPT`：原生模型需 GPU（本机无独显），当前仅运行规则版方法论实现，报告中须注明「规则版，非原生 LoRA 模型」。

## 2. 自动路由表

`registry.json → routing`，或 `python models.py route sector_pick`。

| 任务类型 task | 自动调用的模型 |
|---|---|
| `screen` 全市场/条件选股 | qlib_multifactor + instock_technical_cyq + dsa |
| `sector_pick` 板块内选股 | qlib_multifactor + dsa + tradingagents_cn_debate |
| `deep_dive` 个股深度 | tradingagents_cn_debate + qlib_multifactor + instock_technical_cyq + dsa |
| `technical` 技术面/筹码 | instock_technical_cyq + dsa |
| `market_review` 大盘复盘 | dsa + instock_technical_cyq + cnequity_moneyflow + aiagents_stock_news |
| `earnings` 财报/业绩 | tradingagents_cn_debate + qlib_multifactor + dsa |
| `event` 事件/情景 | tradingagents_cn_debate + tradingagents_astock_sentiment + dsa + fingpt_sentiment |
| `portfolio_risk` 组合风险 | qlib_multifactor + dsa（有 holdings 时追加 portfolio_risk） |
| `money_flow` 资金走向 | cnequity_moneyflow + tradingagents_astock_sentiment + dsa |
| `dragon_tiger` 龙虎榜复盘 | cnequity_moneyflow + aiagents_stock_news + tradingagents_astock_sentiment |
| `news_capture` 消息捕捉/舆情 | aiagents_stock_news + fingpt_sentiment + cnequity_moneyflow + tradingagents_astock_sentiment |

**新任务类型使用要点**：
- `money_flow`：五维框架定结构，**结论须至少两维印证**；各维度口径不同禁止混算总额；强度为「弱（分歧）」时只陈列事实、不下方向性结论。
- `news_capture`：三层漏斗做广度 + 情绪打分 + 舆情七要素质检；**传闻/小作文一律标「未证实」**，与事实分开陈列；情绪极值（|分|>70）常与资金流背离，须交叉验证。
- `dragon_tiger`：**T+1 晚间披露数据，只用于复盘与席位画像**，禁止当作实时买卖信号；独食榜（买一占比>50%）须提示次日冲高回落风险。

## 3. 调用方式

```python
import sys
sys.path.insert(0, "C:/Users/Administrator/.workbuddy/skills/a-share-analysis-models")
from models import (analyze, route, qlib_factor_score, technical_signals, chip_distribution,
                    news_sentiment_score, capital_flow_tracker, dragon_tiger_review, hotmoney_profile)

result = analyze("sector_pick", {
    "as_of": "2026-11-13",   # 必须给真实基准日
    "stocks": [...],         # 从真实数据源取得的候选池
    "bars":   [...],         # 单只前复权 OHLCV，时间升序
    "holdings": [...],       # 可选
    "bull_case": "...", "bear_case": "...", "falsifiers": [...],
    "dashboard": {"core_conclusion": "...", "data_perspective": "...",
                  "intelligence": "...", "battle_plan": "..."},
})

# 消息捕捉示例（task=news_capture）
analyze("news_capture", {
    "as_of": "2026-11-16",
    "news": [{"title": "...", "source": "财联社", "hours_old": 1, "heat": 0.9, "related": ["600519"]}],
    "flows": {"northbound": 32.5, "margin": 18.2, "dragon_tiger": 3.1,
              "block_trade": None, "main_force": 45.6, "as_of": "2026-11-16"},
    "target": "600519",
})
```

`analyze()` 只调用**有真实输入**的模型；缺输入的模型列进 `models_skipped_no_input`，**严禁用编造数据补齐**。

单独调用：`qlib_factor_score(stocks, weights=...)`、`technical_signals(bars)`、`chip_distribution(bars)`、`dsa_dashboard()`、`multiagent_debate()`、`portfolio_risk(holdings)`、`news_sentiment_score(news, target=...)`、`capital_flow_tracker(flows)`、`dragon_tiger_review(record)`、`hotmoney_profile(seats)`。算法自检：`python models.py selftest`（合成数据，非投资结论）。

## 4. 数据路由与标注规则

优先级：① 已连接的金融类 MCP / 行情连接器 → ② `domain_search`（无金融 MCP 时的默认取数层）→ ③ 用户提供的文件/数据 → ④ 本机部署 akshare / baostock / tushare 后自取。

- 每个数字标注**来源 + 基准日**；研报/媒体口径标注「非一手来源，需核实原文」。
- 未查到 → `[MISSING]`；行情/财务/代码状态超过 90 天 → `[STALE]`。
- 每个主张标注类型：**事实 / 管理层声明 / 市场共识 / 模型输出 / 假设 / 判断**。
- A 股特有口径必须核对：前复权、涨跌停、停牌、ST、除权除息、指数成分调整、扣非归母 vs 归母。
- 中国习惯：涨用红色、跌用绿色；货币默认 ¥。

## 5. 输出契约（每个报告必须包含）

1. **数据来源与基准日**（含「今日是否休市」判断）
2. **模型与假设**：因子权重、方向、标准化方式、指标窗口；明确「评分为本次模型输出，非上游项目原生评分、非投资评级」，**不同候选池的分数不可横向比较**
3. **结论与评级**：`Buy / Hold / Sell` 或研究分类须基于足够研究深度；缺 DCF/可比估值支撑时**不给目标价**
4. **多空双方论点**（各 ≥3 条可量化论据）+ **变异认知**
5. **证伪条件与监控项**（≥2 条可观测）+ **PM 七问**（见 `multiagent_debate()`）
6. **边界**：风险偏好/持仓前提/历史估值分位/DCF 假设缺失时，不给仓位比例与买卖指令
7. **免责声明**（固定）：`本报告仅供研究参考，不构成个人投资建议。市场有风险，投资需谨慎；过往表现不预示未来收益。`

## 6. 部署状态

`models.py` 是**零第三方依赖**的方法论等价实现，因此「自动调用模型」在安装后即可工作，**不需要**先拉取四个上游源码。

若要运行上游原生模型：在**仓库根目录**执行 `python a-share-models/bootstrap.py`（3 个宽松许可项目）或 `python a-share-models/bootstrap.py --all --accept-proprietary-license`（含专有许可项），再逐项解决 `projects.json → deploy_blockers`。建议顺序：先接数据层 → qlib 因子与回测 → 最后才是需要 LLM Key / MongoDB 的多智能体系统。**升级前务必核对授权条款。**

## 7. 边界

- 不编造行情、财务、新闻、研报目标价；不把模型评分冒充投资评级。
- 涉及内幕消息 / 未公开信息时明确拒绝。
- 上游项目 README 均声明不构成投资建议；本调度层沿用更严格的口径。
- 本报告仅供研究参考，不构成个人投资建议。市场有风险，投资需谨慎；过往表现不预示未来收益。
