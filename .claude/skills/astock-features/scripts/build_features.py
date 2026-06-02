#!/usr/bin/env python3
"""astock-features skill 脚本：构建技术特征表。"""
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
from lab_bot.features.engineering import FEATURE_COLUMNS, add_indicators, label_limit_up  # noqa: E402
from lab_bot.pipeline import load_feature_table  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="构建技术特征表")
    ap.add_argument("--symbol", help="只输出该股票的最新特征快照")
    ap.add_argument("--config")
    args = ap.parse_args()

    cfg = load_config(args.config)
    db = cfg.resolve_path("data", "cache_db", default="output/lab_bot.db")
    limit_up = cfg.get("features", "limit_up_pct", default=0.095)

    with Storage(db) as store:
        if args.symbol:
            raw = store.load_price(args.symbol)
            if raw.empty:
                print(json.dumps({"error": f"库中无 {args.symbol} 的行情，请先采集"},
                                 ensure_ascii=False))
                return 1
            feat = label_limit_up(add_indicators(raw), limit_up)
            snap = feat.iloc[-1]
            cols = ["date", "close", "pct_chg", *FEATURE_COLUMNS, "limit_up"]
            out = {c: (round(float(snap[c]), 4) if isinstance(snap[c], float) else
                       (snap[c].item() if hasattr(snap[c], "item") else snap[c]))
                   for c in cols if c in snap}
            print(json.dumps({"symbol": args.symbol, "snapshot": out},
                             ensure_ascii=False, indent=2))
            return 0

        ft = load_feature_table(cfg, store)
        if ft.empty:
            print(json.dumps({"error": "无可用行情，请先运行 astock-data 采集"},
                             ensure_ascii=False))
            return 1

        out_csv = cfg.resolve_path("report", "output_dir", default="output/reports").parent / "features.csv"
        out_csv.parent.mkdir(parents=True, exist_ok=True)
        ft.to_csv(out_csv, index=False, encoding="utf-8-sig")

        summary = {
            "rows": int(len(ft)),
            "symbols": int(ft["symbol"].nunique()),
            "date_range": [ft["date"].min(), ft["date"].max()],
            "limit_up_days": int(ft["limit_up"].sum()),
            "ma_bull_ratio": round(float(ft["ma_bull"].mean()), 4),
            "saved_csv": str(out_csv),
        }
        print(json.dumps({"feature_table": summary}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
