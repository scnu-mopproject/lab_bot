"""基于用户实仓的策略与风险管理。

输入：用户持仓（成本价、数量）、最新价、候选打分、资金与风控参数。
输出：每只持仓的盈亏与止盈/止损建议，以及候选股的建议仓位（金额/股数）。

声明：所有「建议」均为基于规则的风险管理提示，不构成投资建议。
最终决策与风险由用户自行承担。
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


def load_positions(path: str | Path) -> list[dict]:
    """读取持仓 JSON。结构见 config/positions.example.json。"""
    p = Path(path)
    if not p.exists():
        return []
    with open(p, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("positions", data) if isinstance(data, dict) else data


def _position_advice(pos: dict, last_price: float, stop_loss: float, take_profit: float) -> dict:
    cost = float(pos["cost"])
    qty = int(pos["qty"])
    pnl_pct = last_price / cost - 1 if cost > 0 else 0
    market_value = last_price * qty
    pnl = (last_price - cost) * qty

    if pnl_pct <= -stop_loss:
        action, reason = "止损", f"亏损 {pnl_pct:.1%} 已触及止损线 -{stop_loss:.0%}"
    elif pnl_pct >= take_profit:
        action, reason = "止盈/减仓", f"盈利 {pnl_pct:.1%} 已达止盈线 {take_profit:.0%}"
    elif pnl_pct >= take_profit * 0.6:
        action, reason = "持有/移动止盈", f"盈利 {pnl_pct:.1%}，接近止盈，建议上移止盈位"
    else:
        action, reason = "持有", f"盈亏 {pnl_pct:.1%}，在风控区间内"

    return {
        "symbol": pos["symbol"], "name": pos.get("name", pos["symbol"]),
        "cost": round(cost, 2), "qty": qty, "last": round(last_price, 2),
        "market_value": round(market_value, 2), "pnl": round(pnl, 2),
        "pnl_pct": round(pnl_pct, 4), "action": action, "reason": reason,
    }


def analyze_portfolio(
    positions: list[dict], last_prices: dict[str, float], candidates: pd.DataFrame,
    *, total_capital: float = 100_000, max_position_pct: float = 0.2,
    stop_loss_pct: float = 0.07, take_profit_pct: float = 0.15,
    held_symbols_exclude: bool = True,
) -> dict:
    """生成持仓诊断与候选建仓建议。"""
    # 1) 持仓诊断
    holdings = []
    held = set()
    invested = 0.0
    for pos in positions:
        sym = pos["symbol"]
        held.add(sym)
        last = float(last_prices.get(sym, pos.get("cost", 0)))
        adv = _position_advice(pos, last, stop_loss_pct, take_profit_pct)
        invested += adv["market_value"]
        holdings.append(adv)

    cash = max(0.0, total_capital - invested)

    # 2) 候选建仓建议（剔除已持有，按分数分配，单票不超过上限）
    per_cap = total_capital * max_position_pct
    suggestions = []
    if candidates is not None and not candidates.empty:
        cand = candidates.copy()
        if held_symbols_exclude:
            cand = cand[~cand["symbol"].isin(held)]
        budget = cash
        for _, c in cand.iterrows():
            if budget <= 0:
                break
            last = float(last_prices.get(c["symbol"], c.get("close") or 0))
            if last <= 0:
                continue
            alloc = min(per_cap, budget)
            # A股按手（100股）取整
            lots = int(alloc // (last * 100))
            if lots < 1:
                continue
            qty = lots * 100
            cost = round(qty * last, 2)
            budget -= cost
            suggestions.append({
                "symbol": c["symbol"], "score": c["score"], "last": round(last, 2),
                "suggest_qty": qty, "suggest_amount": cost,
                "weight": round(cost / total_capital, 3),
            })

    # 3) 组合层面风险提示
    warnings = []
    if invested / total_capital > 0.9:
        warnings.append("仓位过重（>90%），市场回调时回撤风险大，建议保留现金。")
    losers = [h for h in holdings if h["action"] == "止损"]
    if losers:
        warnings.append(f"有 {len(losers)} 只持仓触及止损线，需优先处理。")
    if candidates is not None and not candidates.empty and candidates["score"].max() < 40:
        warnings.append("当前候选股打分普遍偏低（<40），形态信号不强，建议轻仓观望。")

    return {
        "summary": {
            "total_capital": round(total_capital, 2),
            "invested": round(invested, 2),
            "cash": round(cash, 2),
            "position_ratio": round(invested / total_capital, 4) if total_capital else 0,
            "total_pnl": round(sum(h["pnl"] for h in holdings), 2),
        },
        "holdings": holdings,
        "suggestions": suggestions,
        "warnings": warnings,
        "disclaimer": "以上为基于规则的风险管理提示，不构成投资建议，决策与风险自负。",
    }
