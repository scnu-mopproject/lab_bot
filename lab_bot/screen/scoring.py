"""涨停候选打分（透明、可解释）。

这里只做**确定性的规则打分**：把若干技术信号映射到 0-100 的分数，并保留
每一项的贡献明细（component breakdown）。

设计意图（重要）：分数不是「涨停概率」，而是「技术形态强度」的可解释度量。
真正的多维研判（结合新闻、题材、资金、市场环境）由 agent 在脚本输出之上完成。
这样既保证了底层可复现，又避免把不可靠的预测伪装成精确概率。
"""
from __future__ import annotations

import pandas as pd

# 各信号的权重（总和为 100）。可按需调整，分项透明可审计。
WEIGHTS = {
    "ma_bull": 20,       # 均线多头排列
    "vol_surge": 20,     # 放量
    "momentum": 20,      # 近端动量 / 连阳
    "macd_pos": 15,      # MACD 金叉/红柱
    "rsi_zone": 15,      # RSI 处于强势但未超买区间
    "near_high": 10,     # 接近20日高点（突破前形态）
}


def score_snapshot(row: pd.Series) -> dict:
    """对单个「股票-当日」特征快照打分，返回 {score, components}。"""
    c: dict[str, float] = {}

    c["ma_bull"] = WEIGHTS["ma_bull"] if row.get("ma_bull", 0) == 1 else 0

    vr = row.get("vol_ratio", 1) or 1
    # 量比 1.5~3 给满分，过高（>4，可能见顶放量）打折
    if 1.5 <= vr <= 3:
        c["vol_surge"] = WEIGHTS["vol_surge"]
    elif 3 < vr <= 4:
        c["vol_surge"] = WEIGHTS["vol_surge"] * 0.7
    elif vr > 4:
        c["vol_surge"] = WEIGHTS["vol_surge"] * 0.4
    else:
        c["vol_surge"] = WEIGHTS["vol_surge"] * max(0, (vr - 0.8) / 0.7)

    streak = row.get("up_streak", 0) or 0
    pct = row.get("pct_chg", 0) or 0
    mom = min(1.0, streak / 3) * 0.6 + min(1.0, max(0, pct) / 6) * 0.4
    c["momentum"] = WEIGHTS["momentum"] * mom

    macd_hist = row.get("macd_hist", 0) or 0
    c["macd_pos"] = WEIGHTS["macd_pos"] if macd_hist > 0 else 0

    rsi = row.get("rsi14", 50) or 50
    # RSI 55~70 视为强势健康区间
    if 55 <= rsi <= 70:
        c["rsi_zone"] = WEIGHTS["rsi_zone"]
    elif 70 < rsi <= 80:
        c["rsi_zone"] = WEIGHTS["rsi_zone"] * 0.5
    elif rsi > 80:
        c["rsi_zone"] = 0  # 超买
    else:
        c["rsi_zone"] = WEIGHTS["rsi_zone"] * max(0, (rsi - 40) / 15)

    dist = row.get("dist_high20", -1)
    dist = -1 if dist is None else dist
    # 距高点 -3%~0% 给高分（突破临界）
    if -0.03 <= dist <= 0:
        c["near_high"] = WEIGHTS["near_high"]
    elif -0.08 <= dist < -0.03:
        c["near_high"] = WEIGHTS["near_high"] * 0.5
    else:
        c["near_high"] = 0

    score = round(sum(c.values()), 1)
    return {"score": score, "components": {k: round(v, 1) for k, v in c.items()}}


def screen_candidates(
    feature_table: pd.DataFrame, *, top_k: int = 10, as_of: str | None = None
) -> pd.DataFrame:
    """对特征表中每只股票的「最新交易日」快照打分并排序，取 Top-K。

    as_of: 指定交易日（YYYY-MM-DD）；缺省取每只股票的最后一行。
    返回列：symbol, date, score, 各分项, 关键指标。
    """
    if feature_table is None or feature_table.empty:
        return pd.DataFrame()

    if as_of:
        snap = feature_table[feature_table["date"] == as_of]
    else:
        snap = feature_table.sort_values("date").groupby("symbol").tail(1)

    rows = []
    for _, r in snap.iterrows():
        res = score_snapshot(r)
        rows.append({
            "symbol": r["symbol"], "date": r["date"], "close": r.get("close"),
            "pct_chg": r.get("pct_chg"), "score": res["score"],
            **res["components"],
            "vol_ratio": round(r.get("vol_ratio", float("nan")), 2),
            "rsi14": round(r.get("rsi14", float("nan")), 1),
            "ma_bull": int(r.get("ma_bull", 0)),
        })
    out = pd.DataFrame(rows).sort_values("score", ascending=False).reset_index(drop=True)
    return out.head(top_k)
