"""跨 skill 复用的流水线辅助。

把"从库里读行情 -> 构建特征表"这一步集中在此，供 features / screen /
backtest 脚本共享，避免重复实现。
"""
from __future__ import annotations

import pandas as pd

from .config import Config
from .data.storage import Storage
from .features.engineering import build_feature_table


def load_price_by_symbol(store: Storage) -> dict[str, pd.DataFrame]:
    """从库里读出全部行情，按股票分组。"""
    df = store.load_price()
    if df.empty:
        return {}
    return {sym: g.reset_index(drop=True) for sym, g in df.groupby("symbol")}


def load_feature_table(cfg: Config, store: Storage) -> pd.DataFrame:
    """读库行情并构建带技术指标 + 涨停标注的特征表。"""
    limit_up = cfg.get("features", "limit_up_pct", default=0.095)
    return build_feature_table(load_price_by_symbol(store), limit_up_pct=limit_up)


def latest_prices(store: Storage) -> dict[str, float]:
    """每只股票的最新收盘价。"""
    df = store.load_price()
    if df.empty:
        return {}
    last = df.sort_values("date").groupby("symbol").tail(1)
    return dict(zip(last["symbol"], last["close"]))
