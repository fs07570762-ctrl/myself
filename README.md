# myself

个人工具与模型仓库。仓库创建于 2026-11-15，首次提交为 GitHub 网页端的 `175ea69`，随后合入了本地的 `dc3aa1e`。

## 内容

| 路径 | 说明 |
|---|---|
| `a-share-models/` | **A 股分析模型调用层**：可移植的技能定义、模型注册表、零依赖可执行模型、安装与引导脚本。详见 [a-share-models/README.md](a-share-models/README.md) |
| `vendors/` | 四个上游分析项目的 git submodule 引用（固定 commit，不含源码实体） |
| `.gitmodules` | submodule 的 URL 与分支配置 |

## A 股分析模型（快速开始）

四个项目以 submodule 固定引用，主仓库只存 commit 指针；调用层零依赖、可单独使用。

```bash
git clone --recurse-submodules https://github.com/fs07570762-ctrl/myself.git
cd myself

python a-share-models/install.py        # 安装调用层到 WorkBuddy 用户级技能目录
python a-share-models/models.py selftest
python a-share-models/bootstrap.py --status
```

安装后，任何股票分析 / 选股 / 估值 / 复盘任务会自动加载技能并按任务类型调用对应模型。

**引用的四个项目**（2026-11-15 核实）：`ZhuLinsen/daily_stock_analysis`（MIT）、`microsoft/qlib`（MIT）、`hsliuping/TradingAgents-CN`（**混合授权**，应用层专有，默认不自动初始化）、`myhhub/stock`（Apache-2.0，代码 [STALE]）。

> 本仓库不复制、不再分发任何上游源码。使用前请阅读各项目 LICENSE。模型输出仅供研究参考，不构成个人投资建议。

## 后续

- 新增模型 / 更新 pinned_sha 时，同步更新 `a-share-models/projects.json` 与 `registry.json`
- 后续提交按实际变更生成提交消息
