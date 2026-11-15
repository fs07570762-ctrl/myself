# a-share-models · A 股分析模型仓库

把 4 个高关注度开源股票分析项目**固定引用**到本仓库，并提供一套零依赖、可移植的「调用层」，方便在任何设备上日后调用。

核实时间：2026-11-15 · 数据来源：GitHub REST API + 各项目 README 原文

## 为什么要这样部署

| 约束 | 事实 | 处理方式 |
|---|---|---|
| 体积 | 四个仓库源码合计约 **244 MB**（DSA ≈119MB、TradingAgents-CN ≈79MB、InStock ≈27MB、qlib ≈18MB） | 用 git submodule 存 commit 引用，主仓库只多几 KB |
| 许可 | `TradingAgents-CN` 的 `app/`、`frontend/`、`core/` 是**专有 source-available，禁止再分发与商业使用** | 不复制任何源码；默认不自动初始化，需显式确认 |
| 可运行性 | 四个项目分别需要 LLM Key、MongoDB/Redis/Node、MySQL/TA-Lib、Python 3.11 等 | 调用层 `models.py` 零依赖即可工作；源码按需拉取 |
| 时效性 | submodule 固定在 `pinned_sha`，上游更新不会悄悄改变行为 | `bootstrap.py --update` 显式升级 |

## 目录结构

```
a-share-models/
├── SKILL.md          # WorkBuddy 技能定义：触发词、工作流、输出契约
├── registry.json     # 模型注册表：A 股证据、部署门槛、8 类任务路由
├── models.py         # 零依赖可执行模型（多因子 / 技术指标 / 筹码 / 多空辩论 / 组合风险）
├── projects.json     # 四个上游项目的 URL、许可证、pinned_sha、部署门槛
├── install.py        # 把调用层安装到用户级技能目录（跨平台）
├── bootstrap.py      # 按需浅克隆上游源码（git submodule）
└── README.md         # 本文件
vendors/              # 4 个 gitlink（不含源码实体）
├── daily_stock_analysis/
├── qlib/
├── TradingAgents-CN/
└── instock/
.gitmodules
```

## 快速开始

```bash
# 1. clone（要连源码一起拿）
git clone --recurse-submodules https://github.com/fs07570762-ctrl/myself.git
cd myself

#    已经 clone 过的仓库，改用：
python a-share-models/bootstrap.py --status
python a-share-models/bootstrap.py            # 只拉 3 个宽松许可项目（浅克隆）
python a-share-models/bootstrap.py --all --accept-proprietary-license  # 含专有许可项

#    若运行环境不允许 Python 启动 git 子进程，bootstrap.py 会自动降级为
#    打印可复制的命令；也可用 --commands 直接输出命令清单。
python a-share-models/bootstrap.py --commands

# 2. 安装调用层到 WorkBuddy（此后股票分析任务自动加载技能）
python a-share-models/install.py
python a-share-models/install.py --check      # 验证安装

# 3. 验证模型可运行（合成数据，仅算法自检，非投资结论）
python a-share-models/models.py selftest
python a-share-models/models.py route sector_pick
```

安装位置：`<用户主目录>/.workbuddy/skills/a-share-analysis-models/`（Windows / macOS / Linux 通用）。
卸载：`python a-share-models/install.py --uninstall`。

## 四个模型

| 模型 ID | 上游项目 | 关注度 | 许可证 | pinned_sha | 复用什么 |
|---|---|---|---|---|---|
| `dsa_decision_dashboard` | `ZhuLinsen/daily_stock_analysis` | 72,376 ★ | MIT | `f044e95` | 决策仪表盘四段结构 |
| `qlib_multifactor` | `microsoft/qlib` | 50,294 ★ | MIT | `5435523` | Alpha158/360 多因子打分 |
| `tradingagents_cn_debate` | `hsliuping/TradingAgents-CN` | 32,957 ★ | **混合授权** | `51060a7` | 多智能体多空辩论 |
| `instock_technical_cyq` | `myhhub/stock` | 15,212 ★ | Apache-2.0 | `b6e0ca2` | 技术指标 / 形态 / 筹码 |

`instock_technical_cyq` 代码最后推送 2026-04-02，**[STALE] 227 天**，只复用方法论，不依赖其数据抓取层。

## 日后调用

安装后，任何「分析股票 / 板块选股 / 估值 / 技术面 / 复盘」类任务会按 `SKILL.md` 的触发词自动加载技能，并按 `registry.json → routing` 选择模型组合：

| 任务 | 自动调用 |
|---|---|
| `screen` | qlib_multifactor + instock_technical_cyq + dsa |
| `sector_pick` | qlib_multifactor + dsa + tradingagents_cn_debate |
| `deep_dive` | 全部四个 |
| `technical` | instock_technical_cyq + dsa |
| `market_review` | dsa + instock_technical_cyq |
| `earnings` | tradingagents_cn_debate + qlib_multifactor + dsa |
| `event` | tradingagents_cn_debate + dsa |
| `portfolio_risk` | qlib_multifactor + dsa |

代码调用：

```python
import sys
sys.path.insert(0, "<用户主目录>/.workbuddy/skills/a-share-analysis-models")
from models import analyze
r = analyze("deep_dive", {
    "as_of": "2026-11-13",   # 真实基准日，必填
    "stocks": [...],         # 真实候选池
    "bars":   [...],         # 真实前复权 OHLCV
})
```

`analyze()` 只调用有真实输入的模型，缺输入的会标 `models_skipped_no_input`，禁止用编造数据补齐。

## 边界

- 本仓库**不复制、不再分发**任何上游源码；submodule 只是 commit 引用。使用前请阅读各项目 LICENSE，尤其 `TradingAgents-CN` 的混合许可。
- `models.py` 是方法论等价实现，不是上游原生模型；因子权重为研究者先验，未经 A 股历史 IC 检验或回测；分数仅在同一候选池内可比。
- 每个数字必须标注来源与基准日；缺失 `[MISSING]`、超 90 天 `[STALE]`；不编造行情财务数据，不给无依据的目标价与买卖指令。
- 本报告仅供研究参考，不构成个人投资建议。市场有风险，投资需谨慎；过往表现不预示未来收益。
