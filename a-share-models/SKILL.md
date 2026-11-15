---
name: a-share-analysis-models
description: A 股股票分析模型自动调度。用户要求分析股票/个股/自选股、板块选股或比较、找有投资价值的标的、估值与基本面研究、技术面与筹码分析、大盘复盘、财报业绩解读、事件影响、投资组合风险，或提到 daily_stock_analysis / Qlib / TradingAgents-CN / InStock 等分析框架时，必须自动加载本技能，按 registry.json 的任务路由调用对应模型，并用 models.py 做可复现计算。触发词：A股、个股、选股、板块、行情、K线、技术指标、MACD、筹码、因子、多因子、估值、PE、PB、ROE、扣非、三季报、复盘、研报、投资价值、目标价、仓位、回测、stock analysis、screener、valuation。本技能只提供方法论与计算，不代替真实取数，不生成投资建议。
license: MIT
version: 1.0.0
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

**用途**：让每一次股票分析任务都自动复用 4 个高关注度开源项目的分析模型，而不是每次临时重新设计框架。

**安装**：从本仓库 clone 后执行 `python a-share-models/install.py`，会把本目录的 `SKILL.md / registry.json / models.py / projects.json` 复制到 `<用户主目录>/.workbuddy/skills/a-share-analysis-models/`，由 WorkBuddy 按触发词自动加载。也可直接把本目录整体复制过去。

## 0. 必须先做的事（强制）

1. 同时加载 `workbuddy-finance-skill`（金融场景总入口，含个股研究 / 估值 / 技术面 / HTML 规范方法论）。
2. 读取同目录 `registry.json` —— 模型注册表、A 股适配证据、部署门槛与任务路由都以它为准。
3. 调用 `route(task)` 得到本次任务应使用的模型组合，**不要凭印象挑模型**。
4. 取数并核对基准日；数据缺失标 `[MISSING]`，超过 90 天标 `[STALE]`。
5. 用 `models.py` 做计算（纯标准库，Python 3.8+ 可直接运行，已在 3.13 验证），再写结论。
6. 输出末尾固定免责声明。

> 注册表核实于 2026-11-15，star / fork 是瞬时值；引用具体数字需重新查 GitHub API 或注明「截至 2026-11-15」。

## 1. 模型注册表（4 个来源）

| 模型 ID | 上游项目 | 关注度(2026-11-15) | 复用什么 | 何时用 |
|---|---|---|---|---|
| `dsa_decision_dashboard` | `ZhuLinsen/daily_stock_analysis` | 72,376 ★ | 决策仪表盘四段结构 `core_conclusion / data_perspective / intelligence / battle_plan`；`--market-review` 复盘 | **所有任务的输出契约** |
| `qlib_multifactor` | `microsoft/qlib` | 50,294 ★ | Alpha158/Alpha360 因子思想 → 横截面标准化、加权打分、因子贡献归因 | 选股、板块内排序、因子归因、回测设计 |
| `tradingagents_cn_debate` | `hsliuping/TradingAgents-CN` | 32,957 ★ | 多智能体角色分工 → 多空辩论 → 风控裁决 → 证伪条件 | 个股深度、逻辑检验、财报/事件解读 |
| `instock_technical_cyq` | `myhhub/stock` | 15,212 ★ | 32 类技术指标、61 种 K 线形态、筹码分布 CYQ、11 个策略模板、选股回测 | 技术面、择时校验、筹码结构 |

四个上游项目以 **git submodule** 固定在 `vendors/`（见 `projects.json` 的 `pinned_sha`）。本仓库**不复制上游源码**；`python a-share-models/bootstrap.py` 按需浅克隆。

**筛选口径**：只收「产出分析结论」的项目，排除高 star 但属数据层/执行层的 `vnpy/vnpy`(46,382★)、`akfamily/akshare`(23,341★)、`waditu/tushare`(15,494★) 等。

**必须向用户披露的风险（均有 README 一手依据）**：
- `microsoft/qlib`：官方数据集因数据安全策略暂时禁用；官方 cn 数据由 Yahoo Finance 爬取且自述 "might not be perfect"；README 仅列 Python 3.8–3.12。
- `hsliuping/TradingAgents-CN`：**混合授权**，`app/`、`frontend/`、`core/` 为专有 source-available，禁止再分发与商业使用；需 MongoDB / Redis / Node / LLM Key。**默认不自动初始化**，使用前阅读上游 LICENSE。
- `myhhub/stock`：代码最后推送 2026-04-02，**[STALE] 227 天**（截至 2026-11-15）。仅复用其技术面方法论，**不要依赖其数据抓取层**。活跃替代：`shy3130/tick-stock-panel`。

## 2. 自动路由表

`registry.json → routing`，或 `python models.py route sector_pick`。

| 任务类型 task | 自动调用的模型 |
|---|---|
| `screen` 全市场/条件选股 | qlib_multifactor + instock_technical_cyq + dsa |
| `sector_pick` 板块内选股 | qlib_multifactor + dsa + tradingagents_cn_debate |
| `deep_dive` 个股深度 | tradingagents_cn_debate + qlib_multifactor + instock_technical_cyq + dsa |
| `technical` 技术面/筹码 | instock_technical_cyq + dsa |
| `market_review` 大盘复盘 | dsa + instock_technical_cyq |
| `earnings` 财报/业绩 | tradingagents_cn_debate + qlib_multifactor + dsa |
| `event` 事件/情景 | tradingagents_cn_debate + dsa |
| `portfolio_risk` 组合风险 | qlib_multifactor + dsa（有 holdings 时追加 portfolio_risk） |

## 3. 调用方式

```python
import sys
sys.path.insert(0, "<用户主目录>/.workbuddy/skills/a-share-analysis-models")
from models import analyze, route, qlib_factor_score, technical_signals, chip_distribution

result = analyze("sector_pick", {
    "as_of": "2026-11-13",   # 必须给真实基准日
    "stocks": [...],         # 从真实数据源取得的候选池
    "bars":   [...],         # 单只前复权 OHLCV，时间升序
    "holdings": [...],       # 可选
    "bull_case": "...", "bear_case": "...", "falsifiers": [...],
    "dashboard": {"core_conclusion": "...", "data_perspective": "...",
                  "intelligence": "...", "battle_plan": "..."},
})
```

`analyze()` 只调用**有真实输入**的模型；缺输入的模型列进 `models_skipped_no_input`，**严禁用编造数据补齐**。

单独调用：`qlib_factor_score(stocks, weights=...)`、`technical_signals(bars)`、`chip_distribution(bars)`、`dsa_dashboard()`、`multiagent_debate()`、`portfolio_risk(holdings)`。算法自检：`python models.py selftest`（合成数据，非投资结论）。

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

若要运行上游原生模型：`python bootstrap.py`（3 个宽松许可项目）或 `--all --accept-proprietary-license`（含专有许可项），再逐项解决 `projects.json → deploy_blockers`。建议顺序：先接数据层 → qlib 因子与回测 → 最后才是需要 LLM Key / MongoDB 的多智能体系统。**升级前务必核对授权条款。**

## 7. 边界

- 不编造行情、财务、新闻、研报目标价；不把模型评分冒充投资评级。
- 涉及内幕消息 / 未公开信息时明确拒绝。
- 上游项目 README 均声明不构成投资建议；本调度层沿用更严格的口径。
- 本报告仅供研究参考，不构成个人投资建议。市场有风险，投资需谨慎；过往表现不预示未来收益。
