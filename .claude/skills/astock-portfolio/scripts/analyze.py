#!/usr/bin/env python3
"""astock-portfolio skill 脚本：持仓诊断 + 建仓建议 + 风险提示。"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _find_root(start: Path) -> Path:
    for p in [start, *start.parents]:
        if (p / "lab_bot" / "__init__.py").exists():
            return p
    raise RuntimeError("找不到项目根目录")


ROOT = _find_root(Path(__file__).resolve())
sys.path.insert(0, str(ROOT))

from lab_bot.config import load_config  # noqa: E402
from lab_bot.data.storage import Storage  # noqa: E402
from lab_bot.pipeline import latest_prices, load_feature_table  # noqa: E402
from lab_bot.portfolio.strategy import analyze_portfolio, load_positions  # noqa: E402
from lab_bot.screen.scoring import screen_candidates  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="持仓策略分析")
    ap.add_argument("--positions", help="持仓 JSON 路径")
    ap.add_argument("--capital", type=float)
    ap.add_argument("--stop-loss", type=float)
    ap.add_argument("--take-profit", type=float)
    ap.add_argument("--top-k", type=int)
    ap.add_argument("--config")
    args = ap.parse_args()

    cfg = load_config(args.config)
    db = cfg.resolve_path("data", "cache_db", default="output/lab_bot.db")

    pos_path = args.positions or cfg.get(
        "portfolio", "positions_file", default="config/positions.example.json"
    )
    if not Path(pos_path).is_absolute():
        pos_path = ROOT / pos_path
    positions = load_positions(pos_path)

    capital = args.capital or cfg.get("portfolio", "total_capital", default=100_000)
    stop_loss = args.stop_loss if args.stop_loss is not None else \
        cfg.get("portfolio", "stop_loss_pct", default=0.07)
    take_profit = args.take_profit if args.take_profit is not None else \
        cfg.get("portfolio", "take_profit_pct", default=0.15)
    top_k = args.top_k or cfg.get("model", "top_k", default=10)

    with Storage(db) as store:
        prices = latest_prices(store)
        ft = load_feature_table(cfg, store)
    cand = screen_candidates(ft, top_k=top_k) if not ft.empty else None

    result = analyze_portfolio(
        positions, prices, cand,
        total_capital=capital,
        max_position_pct=cfg.get("portfolio", "max_position_pct", default=0.2),
        stop_loss_pct=stop_loss, take_profit_pct=take_profit,
    )
    result["positions_file"] = str(pos_path)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
