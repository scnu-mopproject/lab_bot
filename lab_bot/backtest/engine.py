"""打分策略回测引擎（walk-forward）。

策略逻辑：在每个交易日收盘后，对全体股票当日快照打分，等权买入分数最高的
Top-K 只，持有 hold_days 天后卖出，计入双边交易成本。汇总胜率、平均收益、
累计净值、最大回撤、夏普等指标，用于验证打分是否具备区分度。

这是诚实的验证环节：如果回测表明打分没有正向区分度，就不该据此实盘。
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from ..screen.scoring import score_snapshot


def _forward_return(group: pd.DataFrame, idx: int, hold_days: int) -> float | None:
    """从 group 第 idx 行买入，持有 hold_days 天的收益率（基于收盘价）。"""
    if idx + hold_days >= len(group):
        return None
    buy = group.iloc[idx]["close"]
    sell = group.iloc[idx + hold_days]["close"]
    if not buy or buy <= 0:
        return None
    return sell / buy - 1


def backtest_scoring(
    feature_table: pd.DataFrame, *, top_k: int = 10, hold_days: int = 1,
    fee_rate: float = 0.0013, min_score: float = 0.0,
) -> dict:
    """对特征表执行回测，返回汇总指标与逐日明细。"""
    if feature_table is None or feature_table.empty:
        return {"error": "empty feature table"}

    ft = feature_table.sort_values(["symbol", "date"]).copy()
    # 预计算每行的打分与前瞻收益
    ft["score"] = ft.apply(lambda r: score_snapshot(r)["score"], axis=1)

    fwd = []
    for _, g in ft.groupby("symbol"):
        g = g.reset_index(drop=True)
        fwd.append(pd.Series(
            [_forward_return(g, i, hold_days) for i in range(len(g))], index=g.index
        ))
    ft["fwd_ret"] = pd.concat(fwd, ignore_index=True).values

    trades = []
    daily = []
    for date, day in ft.groupby("date"):
        picks = day[day["score"] >= min_score].nlargest(top_k, "score")
        picks = picks.dropna(subset=["fwd_ret"])
        if picks.empty:
            continue
        net = picks["fwd_ret"] - 2 * fee_rate  # 买卖各一次成本
        daily.append({"date": date, "n": len(picks), "ret": float(net.mean())})
        for _, p in picks.iterrows():
            trades.append({
                "date": date, "symbol": p["symbol"], "score": p["score"],
                "gross_ret": float(p["fwd_ret"]), "net_ret": float(p["fwd_ret"] - 2 * fee_rate),
            })

    if not daily:
        return {"error": "no tradable days", "n_trades": 0}

    dret = pd.DataFrame(daily).sort_values("date")
    tr = pd.DataFrame(trades)
    equity = (1 + dret["ret"]).cumprod()
    roll_max = equity.cummax()
    drawdown = equity / roll_max - 1

    daily_ret = dret["ret"]
    sharpe = (
        float(daily_ret.mean() / daily_ret.std() * np.sqrt(252))
        if daily_ret.std() > 0 else 0.0
    )

    return {
        "n_trades": int(len(tr)),
        "n_days": int(len(dret)),
        "win_rate": round(float((tr["net_ret"] > 0).mean()), 4),
        "avg_net_ret": round(float(tr["net_ret"].mean()), 4),
        "avg_gross_ret": round(float(tr["gross_ret"].mean()), 4),
        "total_return": round(float(equity.iloc[-1] - 1), 4),
        "max_drawdown": round(float(drawdown.min()), 4),
        "sharpe": round(sharpe, 3),
        "params": {"top_k": top_k, "hold_days": hold_days, "fee_rate": fee_rate},
        "equity_curve": [round(float(x), 4) for x in equity.tolist()],
        "trades_sample": tr.head(20).to_dict(orient="records"),
    }
