#!/usr/bin/env python3
"""astock-data skill 脚本：采集 A 股行情与新闻并落库。

输出 JSON 摘要到 stdout，数据写入 config 指定的 SQLite。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _find_root(start: Path) -> Path:
    """向上查找包含 lab_bot 包的项目根目录。"""
    for p in [start, *start.parents]:
        if (p / "lab_bot" / "__init__.py").exists():
            return p
    raise RuntimeError("找不到项目根目录（lab_bot 包）")


ROOT = _find_root(Path(__file__).resolve())
sys.path.insert(0, str(ROOT))

from lab_bot.config import load_config  # noqa: E402
from lab_bot.data import market, news as news_mod  # noqa: E402
from lab_bot.data.storage import Storage  # noqa: E402


def _resolve_symbols(cfg, args) -> list[tuple[str, str]]:
    if args.symbols:
        syms = [s.strip() for s in args.symbols.split(",") if s.strip()]
        return [(s, s) for s in syms]
    df = market.get_stock_list(
        mode=cfg.get("universe", "mode", default="index"),
        index_symbol=cfg.get("universe", "index_symbol", default="000300"),
        custom_symbols=cfg.get("universe", "custom_symbols", default=[]),
        max_symbols=cfg.get("universe", "max_symbols", default=300),
        allow_fallback=cfg.get("data", "allow_fallback", default=True),
    )
    return list(df[["symbol", "name"]].itertuples(index=False, name=None))


def cmd_prices(cfg, store, args) -> dict:
    days = args.days or cfg.get("data", "history_days", default=250)
    allow_fb = cfg.get("data", "allow_fallback", default=True)
    limit_up = cfg.get("features", "limit_up_pct", default=0.095)
    pairs = _resolve_symbols(cfg, args)

    total, ok, fb_count = 0, 0, 0
    for sym, _name in pairs:
        try:
            df = market.get_price_history(
                sym, days=days, allow_fallback=allow_fb, limit_up_pct=limit_up
            )
        except Exception as e:  # noqa: BLE001
            print(f"[warn] {sym} 获取失败: {e}", file=sys.stderr)
            continue
        if df.attrs.get("fallback"):
            fb_count += 1
        total += store.save_price(df)
        ok += 1
    # 真实采集了几只、回退了几只，如实反映数据可信度
    return {"task": "prices", "symbols": len(pairs), "saved_symbols": ok,
            "rows_written": total, "days": days,
            "fallback_symbols": fb_count,
            "fallback": fb_count == ok if ok else None,
            "data_quality": ("synthetic" if fb_count == ok else
                             "real" if fb_count == 0 else "mixed")}


def cmd_news(cfg, store, args) -> dict:
    max_items = cfg.get("news", "max_items", default=200)
    df = news_mod.get_financial_news(
        max_items=max_items, allow_fallback=cfg.get("data", "allow_fallback", default=True)
    )
    fallback = bool(df.attrs.get("fallback")) if not df.empty else None
    df = news_mod.tag_news(df, cfg.get("news", "keywords", default=[]))
    n = store.save_news(df)
    return {"task": "news", "rows_written": n, "fallback": fallback,
            "data_quality": "synthetic" if fallback else "real"}


def main() -> int:
    ap = argparse.ArgumentParser(description="A股数据采集")
    ap.add_argument("task", choices=["prices", "news", "all"])
    ap.add_argument("--symbols", help="逗号分隔的股票代码，覆盖配置股票池")
    ap.add_argument("--days", type=int, help="历史回看天数")
    ap.add_argument("--config", help="配置文件路径")
    args = ap.parse_args()

    cfg = load_config(args.config)
    db = cfg.resolve_path("data", "cache_db", default="output/lab_bot.db")
    out = {}
    with Storage(db) as store:
        if args.task in ("prices", "all"):
            out["prices"] = cmd_prices(cfg, store, args)
        if args.task in ("news", "all"):
            out["news"] = cmd_news(cfg, store, args)
    out["db"] = str(db)
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
