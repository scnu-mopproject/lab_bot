"""行情数据采集。

优先使用 AKShare 拉取真实 A 股行情；当 AKShare 不可用或抓取失败、且配置
允许回退时，自动使用合成数据，保证流程不中断。返回的 DataFrame 始终遵循
mock.PRICE_COLUMNS 定义的标准列结构。
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta

import pandas as pd

from . import mock

log = logging.getLogger(__name__)


def _akshare_available() -> bool:
    try:
        import akshare  # noqa: F401
        return True
    except Exception:
        return False


def get_stock_list(
    *, mode: str = "index", index_symbol: str = "000300",
    custom_symbols: list[str] | None = None, max_symbols: int = 300,
    allow_fallback: bool = True,
) -> pd.DataFrame:
    """获取股票池。返回含 [symbol, name] 的 DataFrame。

    mode:
        index  —— 取某指数成分股（默认沪深300）
        custom —— 使用 custom_symbols
        all    —— 全市场 A 股（数量大，慎用）
    """
    if mode == "custom":
        syms = custom_symbols or []
        return pd.DataFrame({"symbol": syms, "name": syms})[:max_symbols]

    if _akshare_available():
        try:
            return _ak_stock_list(mode, index_symbol, max_symbols)
        except Exception as e:  # 网络/接口异常
            log.warning("AKShare 股票池获取失败: %s", e)
            if not allow_fallback:
                raise

    if not allow_fallback:
        raise RuntimeError("AKShare 不可用且未允许回退")
    log.info("回退到合成股票池")
    return mock.make_stock_list(min(max_symbols, 20))


def _ak_stock_list(mode: str, index_symbol: str, max_symbols: int) -> pd.DataFrame:
    import akshare as ak

    if mode == "all":
        df = ak.stock_zh_a_spot_em()
        out = df.rename(columns={"代码": "symbol", "名称": "name"})[["symbol", "name"]]
    else:  # index 成分股
        df = ak.index_stock_cons_csindex(symbol=index_symbol)
        out = df.rename(columns={"成分券代码": "symbol", "成分券名称": "name"})[
            ["symbol", "name"]
        ]
    return out.head(max_symbols).reset_index(drop=True)


def get_price_history(
    symbol: str, *, days: int = 250, adjust: str = "qfq",
    allow_fallback: bool = True, limit_up_pct: float = 0.095,
) -> pd.DataFrame:
    """获取单只股票近 days 个交易日的日 K 线（前复权）。"""
    if _akshare_available():
        try:
            df = _ak_price_history(symbol, days, adjust)
            df.attrs["fallback"] = False
            return df
        except Exception as e:
            log.warning("AKShare 行情获取失败 %s: %s", symbol, e)
            if not allow_fallback:
                raise

    if not allow_fallback:
        raise RuntimeError("AKShare 不可用且未允许回退")
    df = mock.make_price_history(symbol, days, limit_up_pct=limit_up_pct)
    df.attrs["fallback"] = True
    return df


def _ak_price_history(symbol: str, days: int, adjust: str) -> pd.DataFrame:
    import akshare as ak

    end = datetime.now()
    start = end - timedelta(days=int(days * 1.6) + 10)  # 留足非交易日余量
    df = ak.stock_zh_a_hist(
        symbol=symbol, period="daily",
        start_date=start.strftime("%Y%m%d"), end_date=end.strftime("%Y%m%d"),
        adjust=adjust,
    )
    rename = {
        "日期": "date", "开盘": "open", "最高": "high", "最低": "low",
        "收盘": "close", "成交量": "volume", "成交额": "amount", "涨跌幅": "pct_chg",
    }
    df = df.rename(columns=rename)
    df["symbol"] = symbol
    df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")
    cols = mock.PRICE_COLUMNS
    return df[cols].tail(days).reset_index(drop=True)
