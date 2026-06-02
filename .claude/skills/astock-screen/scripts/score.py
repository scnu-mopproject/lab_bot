#!/usr/bin/env python3
"""astock-screen skill 脚本：涨停候选打分与排序。"""
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
from lab_bot.pipeline import load_feature_table  # noqa: E402
from lab_bot.screen.scoring import screen_candidates  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="涨停候选打分")
    ap.add_argument("--top-k", type=int)
    ap.add_argument("--as-of", help="指定交易日 YYYY-MM-DD")
    ap.add_argument("--config")
    args = ap.parse_args()

    cfg = load_config(args.config)
    top_k = args.top_k or cfg.get("model", "top_k", default=10)
    db = cfg.resolve_path("data", "cache_db", default="output/lab_bot.db")

    with Storage(db) as store:
        ft = load_feature_table(cfg, store)
    if ft.empty:
        print(json.dumps({"error": "无可用行情，请先运行 astock-data 采集"},
                         ensure_ascii=False))
        return 1

    cand = screen_candidates(ft, top_k=top_k, as_of=args.as_of)
    print(json.dumps({
        "as_of": args.as_of or "各股最新交易日",
        "top_k": top_k,
        "note": "score 为技术形态强度(0-100)，非涨停概率；请结合新闻/题材/大盘综合研判。",
        "candidates": cand.to_dict(orient="records"),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
