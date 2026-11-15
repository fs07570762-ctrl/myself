#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
A 股分析模型注册表 —— 可执行模型层（方法论等价的轻量实现，纯标准库）。

对应上游项目（详见同目录 registry.json）：
  - microsoft/qlib               -> qlib_factor_score()      横截面多因子打分
  - myhhub/stock                 -> technical_signals()      技术指标 / K 线形态
                                   chip_distribution()      筹码分布近似
  - hsliuping/TradingAgents-CN   -> multiagent_debate()     多空辩论与证伪框架
  - ZhuLinsen/daily_stock_analysis -> dsa_dashboard()       决策仪表盘四段输出契约
  - rootSunc/CNEquity            -> capital_flow_tracker()  五维资金面交叉验证
  - AI4Finance-Foundation/FinGPT -> news_sentiment_score()  金融新闻情绪打分（规则版）
  - oficcejo/aiagents-stock      -> news_sentiment_score()  消息三层漏斗（聚合->去重->多角色解读）
                                   dragon_tiger_review()   龙虎榜五视角复盘
  - simonlin1212/TradingAgents-astock -> hotmoney_profile() 游资席位行为画像

重要边界：
  1. 本模块只做「计算与结构化」，不取数、不预测、不生成行情或财务数字。
     所有输入必须由调用方从真实数据源取得；伪造输入得到的是伪造结论。
  2. 所有分数均为【模型输出】，不是投资评级，也不是目标价。
  3. 本模块未安装、未调用任何上游项目的原生代码；只是可复现的方法论实现。

用法：
  python models.py selftest                 # 合成数据算法自检（非投资结论）
  python models.py route sector_pick       # 查看某类任务应自动调用的模型
  from models import analyze               # 由 Skill 在分析中调用
"""

from __future__ import annotations

import json
import math
import os
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REGISTRY = os.path.join(HERE, "registry.json")

DISCLAIMER = "本报告仅供研究参考，不构成个人投资建议。市场有风险，投资需谨慎；过往表现不预示未来收益。"

# ---------------------------------------------------------------------------
# 因子定义：qlib Alpha158/Alpha360 思想的横截面等价实现
#   direction: +1 越大越好；-1 越小越好
#   weight:    默认权重（合计 1.00），必须由调用方在报告中显式披露
# ---------------------------------------------------------------------------
DEFAULT_FACTORS = {
    "pe_ttm":          {"dir": -1, "w": 0.15, "desc": "PE(TTM)，越低越好；<=0 视为不适用"},
    "pb":              {"dir": -1, "w": 0.08, "desc": "PB，越低越好"},
    "roe":             {"dir": +1, "w": 0.15, "desc": "ROE(%)，越高越好"},
    "profit_quality":  {"dir": +1, "w": 0.12, "desc": "扣非净利/归母净利，越接近 1 越好"},
    "rev_growth":      {"dir": +1, "w": 0.10, "desc": "营收同比(%)"},
    "profit_growth":   {"dir": +1, "w": 0.12, "desc": "归母净利同比(%)"},
    "q3_momentum":     {"dir": +1, "w": 0.08, "desc": "单季利润动能(%)"},
    "fund_flow_20d":   {"dir": +1, "w": 0.10, "desc": "20 日主力净额(亿元)"},
    "chg60":           {"dir": +1, "w": 0.05, "desc": "60 日涨跌幅(%)"},
    "debt_ratio":      {"dir": -1, "w": 0.05, "desc": "资产负债率(%)"},
}


def _winsorize(values, k=3.0):
    """中位数 ± k*MAD 截尾，抑制极端值；纯标准库。"""
    finite = [v for v in values if v is not None and math.isfinite(v)]
    if not finite:
        return list(values)
    med = statistics.median(finite)
    mad = statistics.median([abs(v - med) for v in finite]) or 0.0
    spread = 1.4826 * mad
    if spread < 1e-8:  # 横截面取值过于集中时退化到总体标准差，避免把因子压成常数
        spread = statistics.pstdev(finite) if len(finite) > 1 else 0.0
        if spread < 1e-8:
            spread = abs(med) * 0.01 + 1e-8
    lo, hi = med - k * spread, med + k * spread
    return [None if v is None or not math.isfinite(v) else min(max(v, lo), hi) for v in values]


def _zscore(values):
    finite = [v for v in values if v is not None]
    if len(finite) < 2:
        return [0.0 for _ in values]
    mu, sd = statistics.mean(finite), statistics.pstdev(finite) or 1e-9
    return [0.0 if v is None else (v - mu) / sd for v in values]


def qlib_factor_score(stocks, weights=None, factors=None, base=50.0, scale=15.0):
    """横截面多因子打分（0–100）。

    stocks: [{"code","name", 因子名: 数值, ...}, ...]
    返回：分数、排名、分位、逐因子贡献、被插补/不适用的字段、显式假设。
    """
    spec = dict(factors or DEFAULT_FACTORS)
    if weights:
        for k, v in weights.items():
            if k in spec:
                spec[k] = dict(spec[k], w=float(v))
    tot_w = sum(f["w"] for f in spec.values()) or 1.0

    if not stocks:
        return {"error": "empty universe", "model_output": True}

    detail, missing_log = {}, {}
    total_z = [0.0] * len(stocks)
    for fname, cfg in spec.items():
        raw = [s.get(fname) for s in stocks]
        skip_impute = set()
        # 负 PE / 亏损：估值因子不适用，单独标记，不参与标准化也不插补
        if fname == "pe_ttm":
            invalid = [i for i, v in enumerate(raw) if v is None or v <= 0]
            if invalid:
                missing_log[fname] = [stocks[i].get("code") for i in invalid]
            skip_impute = set(invalid)
            raw = [None if (v is None or v <= 0) else v for v in raw]
        missing = [i for i, v in enumerate(raw) if v is None and i not in skip_impute]
        if missing and len(missing) < len(raw):
            fill = statistics.median([v for v in raw if v is not None])
            for i in missing:
                raw[i] = fill
            missing_log.setdefault(fname, []).extend(
                [stocks[i].get("code") for i in missing]
            )
        w = _winsorize(raw)
        z = _zscore(w)
        signed = [cfg["dir"] * x for x in z]
        wnorm = cfg["w"] / tot_w
        total_z = [a + b * wnorm for a, b in zip(total_z, signed)]
        detail[fname] = {
            "weight": round(cfg["w"], 4), "direction": cfg["dir"],
            "desc": cfg["desc"], "z_contribution": [round(x * wnorm, 3) for x in signed],
        }

    scores = [max(0.0, min(100.0, base + scale * z)) for z in total_z]
    order = sorted(range(len(stocks)), key=lambda i: scores[i], reverse=True)
    out = []
    for rank, i in enumerate(order, 1):
        out.append({
            "rank": rank, "code": stocks[i].get("code"), "name": stocks[i].get("name"),
            "score": round(scores[i], 2),
            "percentile": round(100.0 * (len(stocks) - rank) / max(1, len(stocks) - 1), 1),
            "factor_z": {k: v["z_contribution"][i] for k, v in detail.items()},
        })
    return {
        "model": "qlib_multifactor", "model_output": True,
        "universe_size": len(stocks), "ranking": out, "factor_detail": detail,
        "assumptions": [
            "横截面中位数 ± 3*MAD 截尾后做 z-score 标准化，因子方向见 factor_detail",
            f"总分 = clip({base} + {scale} * 加权 z, 0, 100)；base/scale 为展示参数，不改变排序",
            "缺失因子按横截面中位数插补；负 PE 或亏损股的估值因子视为不适用并排除",
            "默认权重为研究者设定的先验，非项目原生权重、未经 A 股历史 IC 检验或回测",
            "分数仅在同一候选池内可比，跨池 / 跨日期不可横向比较",
        ],
        "imputed_or_inapplicable": missing_log,
        "limitations": [
            "未做行业中性化、市值中性化、涨跌停/停牌/ST 过滤、复权口径校验",
            "未计算 IC / IR / 分组收益 / 最大回撤，不能据此宣称策略有效",
        ],
        "source_project": "microsoft/qlib (Alpha158/Alpha360 思想，非原生实现)",
    }


# ---------------------------------------------------------------------------
# 技术指标与形态（myhhub/stock / InStock 方法论的纯 Python 等价实现）
# ---------------------------------------------------------------------------

def _ema(xs, n):
    if not xs:
        return []
    k, out, prev = 2.0 / (n + 1), [], xs[0]
    for x in xs:
        prev = x * k + prev * (1 - k)
        out.append(prev)
    return out


def _sma(xs, n):
    return [None if i + 1 < n else sum(xs[i + 1 - n:i + 1]) / n for i in range(len(xs))]


def _rsi(closes, n):
    if len(closes) < n + 1:
        return None
    gains, losses = [], []
    for i in range(1, len(closes)):
        d = closes[i] - closes[i - 1]
        gains.append(max(d, 0.0)); losses.append(max(-d, 0.0))
    ag, al = statistics.mean(gains[:n]), statistics.mean(losses[:n])
    for i in range(n, len(gains)):
        ag = (ag * (n - 1) + gains[i]) / n
        al = (al * (n - 1) + losses[i]) / n
    if al == 0:
        return 100.0
    return round(100.0 - 100.0 / (1 + ag / al), 2)


def _kdj(bars, n=9):
    if len(bars) < n:
        return None
    k, d, out = 50.0, 50.0, []
    for i in range(n - 1, len(bars)):
        win = bars[i + 1 - n:i + 1]
        hi, lo = max(b["high"] for b in win), min(b["low"] for b in win)
        rsv = 50.0 if hi == lo else (bars[i]["close"] - lo) / (hi - lo) * 100
        k = 2.0 / 3 * k + 1.0 / 3 * rsv
        d = 2.0 / 3 * d + 1.0 / 3 * k
        out.append((k, d, 3 * k - 2 * d))
    k, d, j = out[-1]
    return {"K": round(k, 2), "D": round(d, 2), "J": round(j, 2)}


def _pattern(b):
    """极简 K 线形态识别（明确不是 TA-Lib 61 种形态的完整实现）。"""
    o, h, l, c = b["open"], b["high"], b["low"], b["close"]
    body, rng = abs(c - o), max(h - l, 1e-9)
    lower, upper = min(o, c) - l, h - max(o, c)
    out = []
    if body / rng < 0.1 and lower > body and upper > body:
        out.append("十字星/长腿十字")
    if lower >= 2 * body and upper <= body and c >= o:
        out.append("锤头线(偏多)")
    if upper >= 2 * body and lower <= body and c <= o:
        out.append("射击之星(偏空)")
    if c > o and body / rng > 0.6:
        out.append("大阳线")
    if c < o and body / rng > 0.6:
        out.append("大阴线")
    return out or ["无典型单根形态"]


def technical_signals(bars):
    """bars: 时间升序的 [{'date','open','high','low','close','volume'}, ...]"""
    n = len(bars)
    if n < 2:
        return {"error": "bars 至少需要 2 根", "model_output": True}
    closes = [b["close"] for b in bars]
    vols = [b.get("volume", 0) for b in bars]
    ma = {p: _sma(closes, p) for p in (5, 10, 20, 60)}
    dif = [a - b for a, b in zip(_ema(closes, 12), _ema(closes, 26))]
    dea = _ema(dif, 9)
    macd_hist = [2 * (a - b) for a, b in zip(dif, dea)]
    ma20 = ma[20][-1]
    sd20 = statistics.pstdev(closes[-20:]) if n >= 20 else 0.0
    prev5 = vols[-6:-1] or [0]
    vol_ratio = round(vols[-1] / (statistics.mean(prev5) or 1e-9), 2)
    price = closes[-1]

    trend = []
    for p in (5, 10, 20, 60):
        v = ma[p][-1]
        if v is not None:
            trend.append(f"MA{p}={v:.2f}({'上方' if price >= v else '下方'})")
    flags = []
    if n < 60:
        flags.append("[MISSING] 不足 60 根 K 线，MA60 / 长周期结论不可用")
    if dif[-1] > dea[-1] and dif[-1] < 0:
        flags.append("MACD 金叉但位于零轴下方 —— 下降趋势中的反弹，非趋势反转")
    if _rsi(closes, 6) is not None and _rsi(closes, 6) > 80:
        flags.append("RSI6 超买区(>80)")
    if _rsi(closes, 6) is not None and _rsi(closes, 6) < 20:
        flags.append("RSI6 超卖区(<20)")

    return {
        "model": "instock_technical_cyq", "model_output": True,
        "as_of": bars[-1].get("date", "[MISSING]"), "last_close": price,
        "ma": trend,
        "macd": {"DIF": round(dif[-1], 4), "DEA": round(dea[-1], 4),
                 "HIST": round(macd_hist[-1], 4),
                 "cross": "金叉" if dif[-1] > dea[-1] else "死叉",
                 "above_zero": dif[-1] > 0},
        "rsi6": _rsi(closes, 6), "rsi14": _rsi(closes, 14), "kdj": _kdj(bars),
        "boll": None if ma20 is None else {
            "mid": round(ma20, 2), "upper": round(ma20 + 2 * sd20, 2),
            "lower": round(ma20 - 2 * sd20, 2)},
        "volume_ratio_5d": vol_ratio,
        "kline_pattern_last": _pattern(bars[-1]),
        "risk_flags": flags,
        "assumptions": [
            "EMA/MACD 采用 12/26/9，RSI 采用 Wilder 平滑，KDJ 采用 9/3/3，BOLL 采用 20 日 ±2 倍总体标准差",
            "形态识别仅覆盖 6 类单根形态，不是 TA-Lib 61 种形态的完整实现",
            "输入须为前复权 OHLCV；未处理除权除息、停牌、涨跌停与 ST 规则",
        ],
        "source_project": "myhhub/stock (InStock 指标口径，非原生实现)",
    }


def chip_distribution(bars, bins=30, half_life=60):
    """筹码分布(CYQ)近似：把每根 K 线的成交量按 [low, high] 三角形权重摊到价格桶，
    并按时间半衰期衰减。非东方财富精确算法。"""
    if len(bars) < 2:
        return {"error": "bars 至少需要 2 根", "model_output": True}
    lo = min(b["low"] for b in bars)
    hi = max(b["high"] for b in bars)
    if hi <= lo:
        return {"error": "价格区间为 0", "model_output": True}
    width = (hi - lo) / bins
    acc = [0.0] * bins
    n = len(bars)
    for idx, b in enumerate(bars):
        decay = 0.5 ** ((n - 1 - idx) / half_life)
        vol = b.get("volume", 0) * decay
        if vol <= 0:
            continue
        a = max(0, int((b["low"] - lo) / width))
        z = min(bins - 1, int((b["high"] - lo) / width))
        weights = []
        for j in range(a, z + 1):
            center = lo + (j + 0.5) * width
            weights.append(max(1e-9, 1 - abs(center - (b["high"] + b["low"]) / 2) / max(width, (b["high"] - b["low"]) / 2 + width)))
        sw = sum(weights) or 1.0
        for j, w in zip(range(a, z + 1), weights):
            acc[j] += vol * w / sw
    total = sum(acc) or 1.0
    price = bars[-1]["close"]
    profit_ratio = sum(acc[j] for j in range(bins) if lo + (j + 0.5) * width <= price) / total
    avg_cost = sum((lo + (j + 0.5) * width) * acc[j] for j in range(bins)) / total
    cum, low90, high90 = 0.0, lo, hi
    for j, v in enumerate(acc):
        cum += v / total
        if cum >= 0.05 and low90 == lo:
            low90 = lo + j * width
        if cum >= 0.95:
            high90 = lo + (j + 1) * width
            break
    return {
        "model": "instock_technical_cyq", "model_output": True,
        "price_bins": [{"price": round(lo + (j + 0.5) * width, 2),
                        "pct": round(100 * v / total, 2)} for j, v in enumerate(acc)],
        "profit_ratio_pct": round(100 * profit_ratio, 2),
        "avg_cost": round(avg_cost, 2),
        "cost_90_range": [round(low90, 2), round(high90, 2)],
        "concentration": round((high90 - low90) / price, 3),
        "assumptions": [
            f"仅用最近 {n} 根 K 线，半衰期 {half_life} 根；分 {bins} 个价格桶",
            "按三角形权重分配成交量，未使用真实换手率衰减与除权还原",
            "结果为近似值，不等同于东方财富/同花顺的筹码分布，禁止直接用于买卖决策",
        ],
        "source_project": "myhhub/stock (CYQ 思想，非原生实现)",
    }


# ---------------------------------------------------------------------------
# 输出契约：DSA 决策仪表盘 + TradingAgents-CN 多空辩论 + 组合风险
# ---------------------------------------------------------------------------

DSA_SECTIONS = ["core_conclusion", "data_perspective", "intelligence", "battle_plan"]


def dsa_dashboard(payload=None):
    """返回决策仪表盘四段结构契约。payload 由调用方填入真实数据。"""
    p = payload or {}
    out = {
        "model": "dsa_decision_dashboard", "model_output": "framework",
        "sections": {k: p.get(k, "[MISSING] 待填入真实数据与结论") for k in DSA_SECTIONS},
        "field_contract": {
            "core_conclusion": "一句话结论 / 信号 / 研究分类（须声明非投资评级）",
            "data_perspective": "趋势、价格位置、量能、筹码、估值与业绩质量",
            "intelligence": "新闻、公告、风险警报、利好催化（每条标注来源与日期）",
            "battle_plan": "关键观察位、证伪条件、风控清单；缺风险偏好与持仓前提时禁止给仓位/买卖指令",
        },
        "source_project": "ZhuLinsen/daily_stock_analysis (SKILL.md 四段结构)",
    }
    out["valid"] = all(isinstance(v, str) and v and not v.startswith("[MISSING]")
                       for v in out["sections"].values())
    return out


PM_SEVEN = [
    "什么被错误定价了？（无变异认知 -> 标监控项或放弃）",
    "当前价格反映了什么？",
    "什么能证明论点？",
    "什么能推翻论点？",
    "为什么是现在？",
    "什么会改变仓位/评级/目标价？",
    "还缺少什么证据？",
]


def multiagent_debate(payload=None):
    """多智能体辩论框架：只输出必须回答的问题与结构，不代替研究结论。"""
    p = payload or {}
    return {
        "model": "tradingagents_cn_debate", "model_output": "framework",
        "agents": ["大盘/板块分析师", "基本面分析师", "新闻/情绪分析师",
                   "技术面分析师", "乐观研究员", "审慎研究员", "风控裁决"],
        "required_outputs": {
            "bull_case": p.get("bull_case", "[MISSING] 须列 3 条可量化论据"),
            "bear_case": p.get("bear_case", "[MISSING] 须列 3 条可量化反证"),
            "variant_perception": p.get("variant_perception", "[MISSING] 市场共识错在哪里"),
            "falsifiers": p.get("falsifiers", "[MISSING] 至少 2 条可观测证伪条件"),
            "pm_seven_questions": PM_SEVEN,
            "action_class": p.get("action_class", "[MISSING] 加仓/持有/减仓/观察名单/等待证据/放弃/重新评估"),
        },
        "guardrails": [
            "每个数字必须标注来源与基准日；无法查证的标 [MISSING]，禁止编造",
            "区分 事实 / 管理层声明 / 市场共识 / 模型输出 / 假设 / 判断",
            "多智能体若共享同一错误数据会放大偏差，须先做数据交叉核验",
            "不输出目标价、止损止盈、买卖时机（与上游项目 README 免责声明一致）",
        ],
        "source_project": "hsliuping/TradingAgents-CN (多智能体辩论范式)",
    }


def portfolio_risk(holdings):
    """holdings: [{'code','name','sector','weight'(0-1)}, ...]"""
    if not holdings:
        return {"error": "empty holdings", "model_output": True}
    ws = [h.get("weight", 0) for h in holdings]
    total = sum(ws) or 1.0
    hhi = sum((w / total) ** 2 for w in ws)
    sectors = {}
    for h in holdings:
        sectors[h.get("sector", "未分类")] = sectors.get(h.get("sector", "未分类"), 0) + h.get("weight", 0)
    top = sorted(holdings, key=lambda h: h.get("weight", 0), reverse=True)[:3]
    breaches = [h for h in holdings if h.get("weight", 0) > 0.20]
    return {
        "model": "portfolio_risk", "model_output": True,
        "hhi": round(hhi, 4), "effective_n": round(1 / hhi, 2) if hhi else None,
        "sector_exposure": {k: round(100 * v / total, 2) for k, v in sectors.items()},
        "top3": [{"code": h.get("code"), "weight_pct": round(100 * h.get("weight", 0) / total, 2)} for h in top],
        "single_name_breach_20pct": [h.get("code") for h in breaches],
        "assumptions": ["HHI 按归一化权重计算；单票 20% 上限为示例阈值，非用户风险偏好",
                        "未纳入相关性、波动率、beta、流动性、涨跌停无法卖出的风险"],
        "limitations": ["无收益序列，无法计算真实最大回撤 / VaR / 相关性，相关项标 [MISSING]"],
    }


# ---------------------------------------------------------------------------
# 市场消息捕捉与资金走向（2026-11-16 新增四个上游项目的方法论等价实现）
# ---------------------------------------------------------------------------

# 情绪词典：规则版 FinGPT 方法论。键为词，值为 (方向, 强度)。
# 仅作演示级默认词典；实战中调用方可按板块语料扩展，扩展后必须在报告中披露。
_POS_WORDS = {
    "涨停": 2, "大涨": 2, "新高": 2, "超预期": 2, "中标": 2, "获批": 2,
    "增长": 1, "利好": 1, "回升": 1, "回暖": 1, "突破": 1, "放量": 1,
    "净流入": 1, "增持": 1, "回购": 1, "分红": 1, "订单": 1, "扩产": 1,
}
_NEG_WORDS = {
    "跌停": 2, "大跌": 2, "新低": 2, "暴雷": 2, "立案": 2, "处罚": 2,
    "减持": 1, "下滑": 1, "亏损": 1, "利空": 1, "退市": 2, "质押": 1,
    "净流出": 1, "解禁": 1, "商誉": 1, "问询": 1, "警示": 1, "违约": 2,
}
_RUMOR_WORDS = ("传闻", "网传", "据说", "或", "疑似", "未证实", "小作文", "消息称")

# 来源可靠性先验权重（研究设定，可在调用时覆盖）
_SOURCE_WEIGHT = {
    "交易所公告": 1.0, "证监会": 1.0, "公司公告": 1.0,
    "证券时报": 0.9, "财联社": 0.9, "上证报": 0.9, "中证报": 0.9,
    "第一财经": 0.85, "界面": 0.8, "澎湃": 0.8,
    "自媒体": 0.4, "论坛": 0.3, "群聊截图": 0.1,
}


def _recency_weight(hours_old):
    """时效权重：0-2h=1.0，之后每 12h 减半；None 视为陈旧 0.2。"""
    if hours_old is None:
        return 0.2
    if hours_old <= 2:
        return 1.0
    return max(0.05, 0.5 ** ((hours_old - 2) / 12.0))


def news_sentiment_score(news_items, source_weight=None, target=None):
    """金融新闻情绪打分（FinGPT 管道 + aiagents-stock 三层漏斗的规则版）。

    news_items: [{"title": str, "source": str, "hours_old": float|None,
                  "heat": float|None, "related": [code,...]}, ...]
    返回：标的/全市场情绪分 (-100~+100)、逐条判定、传闻清单、漏斗统计。
    """
    if not news_items:
        return {"error": "empty news", "model_output": True}
    sw = dict(_SOURCE_WEIGHT)
    if source_weight:
        sw.update(source_weight)

    # 漏斗第一层：去重（标题前 12 字指纹）
    seen, dedup = set(), []
    for it in news_items:
        fp = (it.get("title") or "")[:12]
        if fp and fp in seen:
            continue
        seen.add(fp)
        dedup.append(it)

    judged, rumors = [], []
    for it in dedup:
        title = it.get("title") or ""
        pos = sum(w for k, w in _POS_WORDS.items() if k in title)
        neg = sum(w for k, w in _NEG_WORDS.items() if k in title)
        rumor = any(k in title for k in _RUMOR_WORDS)
        if rumor:
            rumors.append(title)
        raw = pos - neg
        label = "利多" if raw > 0 else ("利空" if raw < 0 else "中性")
        w_src = sw.get(it.get("source"), 0.5)
        w_time = _recency_weight(it.get("hours_old"))
        heat = max(0.1, min(1.0, (it.get("heat") or 0.5)))
        weight = w_src * w_time * (0.5 + 0.5 * heat)
        if rumor:
            weight *= 0.3  # 传闻降权
        judged.append({
            "title": title, "source": it.get("source", "[MISSING]"),
            "label": label, "strength": abs(raw), "weight": round(weight, 3),
            "rumor": rumor, "related": it.get("related") or [],
        })

    if target:
        pool = [j for j in judged if target in (j["related"] or [])]
    else:
        pool = judged
    num = sum((1 if j["label"] == "利多" else -1 if j["label"] == "利空" else 0) * j["weight"]
              for j in pool)
    den = sum(j["weight"] for j in pool) or 1e-9
    score = round(100 * num / den, 2)

    return {
        "model": "fingpt_sentiment + aiagents_stock_news", "model_output": True,
        "target": target or "全市场聚合",
        "sentiment_score": score,
        "sentiment_label": ("偏多" if score > 20 else "偏空" if score < -20 else "中性"),
        "n_input": len(news_items), "n_after_dedup": len(dedup),
        "n_rumor": len(rumors), "rumor_titles": rumors,
        "items": judged,
        "assumptions": [
            "规则版词典打分，非 FinGPT 原生 LoRA 模型（本机无 GPU）；正负词命中做加权计数",
            "权重 = 来源可靠性 x 时效衰减 x 热度归一；传闻再乘 0.3 降权",
            "情绪分只代表『市场怎么说』，不代表事实本身；禁止单独作为买卖依据",
        ],
        "guardrails": [
            "传闻/小作文一律标『未证实』，须在报告中与事实分开陈列",
            "情绪极值（|score|>70）常是反向指标，必须与资金流交叉验证",
        ],
        "source_project": "AI4Finance-Foundation/FinGPT + oficcejo/aiagents-stock（方法论，非原生实现）",
    }


def capital_flow_tracker(flows):
    """CNEquity L4 五维资金面交叉验证。

    flows: {"northbound": 亿元(净买入，可负), "margin": 亿元(两融净买入),
            "dragon_tiger": 亿元(龙虎榜净买入), "block_trade": 亿元(大宗净额),
            "main_force": 亿元(主力净流入), "as_of": "YYYY-MM-DD"}  缺维度给 None。
    返回：方向一致性、印证维度数、结论强度。任一维缺失标 [MISSING]。
    """
    dims = ["northbound", "margin", "dragon_tiger", "block_trade", "main_force"]
    dim_cn = {"northbound": "北向资金", "margin": "两融净买入", "dragon_tiger": "龙虎榜净买入",
              "block_trade": "大宗交易净额", "main_force": "主力净流入"}
    vals, missing = {}, []
    for d in dims:
        v = flows.get(d)
        if v is None:
            missing.append(d)
        else:
            vals[d] = v

    as_of = flows.get("as_of", "[MISSING]")
    if len(vals) < 2:
        return {"model": "cnequity_moneyflow", "model_output": True,
                "as_of": as_of,
                "error": "可用维度不足 2 个，无法交叉验证",
                "missing": [dim_cn[d] for d in missing]}

    signs = {d: (1 if v > 0 else -1 if v < 0 else 0) for d, v in vals.items()}
    net = sum(signs.values())
    agree = sum(1 for s in signs.values() if s == (1 if net > 0 else -1 if net < 0 else 0))
    verdict = ("资金共振流入" if net > 0 else "资金共振流出") if abs(net) == len(signs) else \
              ("多数维度流入" if net > 0 else "多数维度流出" if net < 0 else "方向分歧")
    strength = "强" if agree >= 4 else ("中" if agree == 3 else "弱（分歧）")

    return {
        "model": "cnequity_moneyflow", "model_output": True,
        "as_of": as_of,
        "dimensions": {dim_cn[d]: {"value_亿": vals[d],
                                   "direction": ("流入" if signs[d] > 0 else "流出" if signs[d] < 0 else "持平")}
                       for d in vals},
        "missing_dims": [dim_cn[d] for d in missing],
        "verdict": verdict, "agree_dims": agree, "n_dims": len(vals),
        "conclusion_strength": strength,
        "assumptions": [
            "方向只按净额正负判断，未做金额量级归一（各维度体量差异大，不可直接相加）",
            "各维度数据口径不同（北向为港交所、两融为交易所、主力流向多为数据商口径），禁止混算总额",
            "数据基准日必须一致；跨日拼接的资金面结论无效",
        ],
        "guardrails": ["结论强度为弱（分歧）时，禁止输出方向性资金结论，只陈列事实"],
        "source_project": "rootSunc/CNEquity（L4 资金面分层框架，非原生实现）",
    }


def dragon_tiger_review(record):
    """龙虎榜五视角复盘框架（aiagents-stock 智瞰龙虎方法论）。

    record: {"code","name","date","buy_seats":[{"name","amount"}], 
             "sell_seats":[{"name","amount"}], "reason": 上榜原因}
    只输出结构化视角与必须回答的问题，席位解读须由调用方填真实数据。
    """
    r = record or {}
    buys = r.get("buy_seats") or []
    sells = r.get("sell_seats") or []
    buy_amt = sum(s.get("amount", 0) for s in buys)
    sell_amt = sum(s.get("amount", 0) for s in sells)
    return {
        "model": "aiagents_stock_news (智瞰龙虎)", "model_output": True,
        "code": r.get("code", "[MISSING]"), "name": r.get("name", "[MISSING]"),
        "date": r.get("date", "[MISSING]"),
        "reason": r.get("reason", "[MISSING]"),
        "buy_total_亿": round(buy_amt, 2), "sell_total_亿": round(sell_amt, 2),
        "net_亿": round(buy_amt - sell_amt, 2),
        "five_views": {
            "买方结构": "一线游资/量化/机构/拉萨席位的占比与集中度（前 1 席占比 >50% 为独食，警惕）",
            "卖方结构": "卖出席位是获利了结还是割肉离场，对照成本区",
            "席位历史": "上榜席位近 60 日历史胜率与次日平均溢价（须真实统计，禁止凭印象）",
            "题材联动": "同板块当日是否多股同上榜（联动=板块级行情，孤立=个股行为）",
            "次日概率": "基于历史同类榜单结构的统计概率，仅作参考，非买卖信号",
        },
        "guardrails": [
            "龙虎榜为 T+1 晚间披露数据，只能用于复盘与席位画像，禁止当作实时信号",
            "单一席位买入不构成推荐依据；独食榜次日冲高回落概率高，须提示风险",
        ],
        "source_project": "oficcejo/aiagents-stock（智瞰龙虎五视角方法论，无许可证仅复用思想）",
    }


def hotmoney_profile(seats):
    """游资席位行为画像（TradingAgents-astock 游资追踪师方法论）。

    seats: [{"name","appearances": 上榜次数, "win_rate": 历史胜率(0-1),
             "avg_premium_next": 次日平均溢价(%), "style": 风格备注}, ...]
    返回：席位分层（龙头游资/跟风/量化）与可信度标记。
    """
    if not seats:
        return {"error": "empty seats", "model_output": True}
    out = []
    for s in seats:
        n = s.get("appearances", 0)
        wr = s.get("win_rate")
        prem = s.get("avg_premium_next")
        if n < 5:
            tier = "样本不足"
        elif wr is not None and prem is not None and wr >= 0.55 and prem > 0:
            tier = "高胜率席位"
        elif wr is not None and wr < 0.4:
            tier = "反向指标席位"
        else:
            tier = "普通席位"
        out.append({
            "name": s.get("name", "[MISSING]"), "appearances": n,
            "win_rate": wr, "avg_premium_next": prem,
            "tier": tier, "style": s.get("style", ""),
        })
    out.sort(key=lambda x: (x["tier"] != "高胜率席位", -(x["win_rate"] or 0)))
    return {
        "model": "tradingagents_astock_sentiment", "model_output": True,
        "seats": out,
        "assumptions": [
            "分层阈值（上榜>=5 次、胜率 55%/40%）为研究设定，非统计检验结果",
            "胜率与溢价必须由调用方从真实龙虎榜历史数据统计，禁止凭印象填写",
        ],
        "guardrails": ["席位画像用于解释资金行为，不构成对个股的推荐"],
        "source_project": "simonlin1212/TradingAgents-astock（游资追踪师方法论）",
    }


# ---------------------------------------------------------------------------
# 自动路由与统一入口
# ---------------------------------------------------------------------------

def route(task):
    """从 registry.json 读取任务 -> 模型组合的路由表。"""
    try:
        with open(REGISTRY, encoding="utf-8") as f:
            reg = json.load(f)
    except (OSError, ValueError) as e:
        return {"error": f"registry.json 不可读: {e}"}
    r = reg.get("routing", {})
    return {"task": task, "models": r.get(task, r.get("deep_dive")),
            "fallback_used": task not in r,
            "known_tasks": sorted(r.keys()),
            "registry_verified_at": reg.get("verified_at")}


def analyze(task, payload=None):
    """统一入口：按任务类型自动调用相关模型。

    payload 可含：stocks（候选池）、bars（单只 OHLCV）、holdings（组合）、
                  news（新闻列表）、flows（五维资金）、lhb（龙虎榜记录）、
                  seats（游资席位）、target（标的代码）、
                  bull_case / bear_case / falsifiers / dashboard 各段。
    """
    p = payload or {}
    r = route(task)
    if "error" in r:
        return r
    results, called = {}, []
    for mid in r["models"]:
        if mid == "qlib_multifactor" and p.get("stocks"):
            results[mid] = qlib_factor_score(p["stocks"], weights=p.get("weights"))
            called.append(mid)
        elif mid == "instock_technical_cyq" and p.get("bars"):
            results[mid] = {"signals": technical_signals(p["bars"]),
                            "chips": chip_distribution(p["bars"])}
            called.append(mid)
        elif mid == "tradingagents_cn_debate":
            results[mid] = multiagent_debate(p)
            called.append(mid)
        elif mid == "dsa_decision_dashboard":
            results[mid] = dsa_dashboard(p.get("dashboard"))
            called.append(mid)
        elif mid == "cnequity_moneyflow" and p.get("flows"):
            results[mid] = capital_flow_tracker(p["flows"])
            called.append(mid)
        elif mid == "fingpt_sentiment" and p.get("news"):
            results[mid] = news_sentiment_score(p["news"], target=p.get("target"))
            called.append(mid)
        elif mid == "aiagents_stock_news":
            sub = {}
            if p.get("news"):
                sub["news_funnel"] = news_sentiment_score(p["news"], target=p.get("target"))
            if p.get("lhb"):
                sub["dragon_tiger"] = dragon_tiger_review(p["lhb"])
            if sub:
                results[mid] = sub
                called.append(mid)
        elif mid == "tradingagents_astock_sentiment" and p.get("seats"):
            results[mid] = hotmoney_profile(p["seats"])
            called.append(mid)
    if p.get("holdings"):
        results["portfolio_risk"] = portfolio_risk(p["holdings"])
        called.append("portfolio_risk")
    skipped = [m for m in r["models"] if m not in called]
    return {
        "task": task, "models_called": called,
        "models_skipped_no_input": skipped,
        "skipped_reason": "缺少该模型所需的真实输入；禁止用编造数据补齐",
        "results": results,
        "data_baseline": p.get("as_of", "[MISSING] 调用方必须提供数据基准日"),
        "disclaimer": DISCLAIMER,
    }


def selftest():
    """合成数据算法自检 —— 数字全部虚构，仅验证计算路径，不构成投资结论。"""
    print("=== SYNTHETIC SELFTEST (数字为虚构，仅验证算法) ===")
    stocks = [
        {"code": "A", "name": "合成甲", "pe_ttm": 22, "pb": 2.1, "roe": 18,
         "profit_quality": 0.96, "rev_growth": 25, "profit_growth": 38,
         "q3_momentum": 12, "fund_flow_20d": 3.2, "chg60": 8, "debt_ratio": 28},
        {"code": "B", "name": "合成乙", "pe_ttm": 145, "pb": 9.8, "roe": 4,
         "profit_quality": 0.41, "rev_growth": 9, "profit_growth": -12,
         "q3_momentum": -30, "fund_flow_20d": -1.1, "chg60": -4, "debt_ratio": 55},
        {"code": "C", "name": "合成丙", "pe_ttm": -55, "pb": 3.7, "roe": -6,
         "profit_quality": 0.2, "rev_growth": 54, "profit_growth": None,
         "q3_momentum": -670, "fund_flow_20d": 0.4, "chg60": -5, "debt_ratio": 41},
    ]
    s = qlib_factor_score(stocks)
    print("factor_score:", [(x["code"], x["score"], x["rank"]) for x in s["ranking"]])
    print("inapplicable/pe_ttm:", s["imputed_or_inapplicable"].get("pe_ttm"))

    bars = []
    price = 10.0
    for i in range(80):
        o = price
        c = round(o * (1 + 0.004 * math.sin(i / 6) + 0.001), 4)
        h, l = round(max(o, c) * 1.008, 4), round(min(o, c) * 0.992, 4)
        bars.append({"date": f"D{i+1}", "open": o, "high": h, "low": l,
                     "close": c, "volume": 100000 + 5000 * (i % 7)})
        price = c
    t = technical_signals(bars)
    print("macd:", t["macd"], "rsi6:", t["rsi6"], "kdj:", t["kdj"])
    cyq = chip_distribution(bars)
    print("cyq profit_ratio:", cyq["profit_ratio_pct"], "avg_cost:", cyq["avg_cost"])
    print("route(sector_pick):", route("sector_pick")["models"])
    # 2026-11-16 新增：消息捕捉与资金走向模型自检
    news = [
        {"title": "某公司中标大额订单，业绩超预期", "source": "财联社", "hours_old": 1,
         "heat": 0.9, "related": ["A"]},
        {"title": "传闻某板块将出大利好（未证实）", "source": "论坛", "hours_old": 3,
         "heat": 0.8, "related": ["B"]},
        {"title": "某公司大股东减持，净利润下滑", "source": "公司公告", "hours_old": 20,
         "heat": 0.6, "related": ["A"]},
    ]
    ns = news_sentiment_score(news, target="A")
    print("news_sentiment(A):", ns["sentiment_score"], ns["sentiment_label"], "rumors:", ns["n_rumor"])
    flows = {"northbound": 32.5, "margin": 18.2, "dragon_tiger": 3.1,
             "block_trade": None, "main_force": 45.6, "as_of": "2026-11-16"}
    cf = capital_flow_tracker(flows)
    print("capital_flow:", cf["verdict"], "agree:", f"{cf['agree_dims']}/{cf['n_dims']}",
          "missing:", cf["missing_dims"])
    lhb = dragon_tiger_review({"code": "A", "name": "合成甲", "date": "2026-11-16",
                               "buy_seats": [{"name": "某席位", "amount": 1.2}],
                               "sell_seats": [{"name": "某席位", "amount": 0.8}],
                               "reason": "日涨幅偏离值达7%"})
    print("lhb net(亿):", lhb["net_亿"])
    seats = hotmoney_profile([{"name": "合成席位", "appearances": 12,
                               "win_rate": 0.6, "avg_premium_next": 1.8}])
    print("hotmoney tier:", seats["seats"][0]["tier"])
    a = analyze("news_capture", {"news": news, "flows": flows, "target": "A"})
    print("analyze(news_capture) called:", a["models_called"])
    a = analyze("deep_dive", {"stocks": stocks, "bars": bars,
                              "holdings": [{"code": "A", "sector": "半导体", "weight": 0.3},
                                           {"code": "B", "sector": "传媒", "weight": 0.2}]})
    print("analyze called:", a["models_called"])
    print("disclaimer:", a["disclaimer"])
    print("=== SELFTEST OK ===")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "selftest"
    if cmd == "selftest":
        selftest()
    elif cmd == "route":
        print(json.dumps(route(sys.argv[2] if len(sys.argv) > 2 else "deep_dive"),
                         ensure_ascii=False, indent=2))
    else:
        print(__doc__)
