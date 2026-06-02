#!/usr/bin/env python3
"""astock-backtest skill 脚本：打分策略历史回测。"""
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

from lab_bot.backtest.engine import backtest_scoring  # noqa: E402
from lab_bot.config import load_config  # noqa: E402
from lab_bot.data.storage import Storage  # noqa: E402
from lab_bot.pipeline import load_feature_table  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="打分策略回测")
    ap.add_argument("--top-k", type=int)
    ap.add_argument("--hold-days", type=int)
    ap.add_argument("--fee", type=float)
    ap.add_argument("--config")
    args = ap.parse_args()

    cfg = load_config(args.config)
    top_k = args.top_k or cfg.get("model", "top_k", default=10)
    hold = args.hold_days or cfg.get("backtest", "hold_days", default=1)
    fee = args.fee if args.fee is not None else cfg.get("backtest", "fee_rate", default=0.0013)
    db = cfg.resolve_path("data", "cache_db", default="output/lab_bot.db")

    with Storage(db) as store:
        ft = load_feature_table(cfg, store)
    if ft.empty:
        print(json.dumps({"error": "无可用行情，请先运行 astock-data 采集"},
                         ensure_ascii=False))
        return 1

    result = backtest_scoring(ft, top_k=top_k, hold_days=hold, fee_rate=fee)
    # 净值曲线可能很长，输出时截断展示，完整曲线另存
    curve = result.pop("equity_curve", [])
    result["equity_curve_points"] = len(curve)
    result["equity_last"] = curve[-1] if curve else None
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
