"""技术指标计算与涨停标注。

输入为 data 层产出的标准行情 DataFrame，输出在其基础上追加一组技术特征。
所有指标均为确定性计算，不含任何预测；预测/打分交由 screen 层与 agent。
"""
from __future__ import annotations

import numpy as np
import pandas as pd

# 由 build_feature_table 产出的特征列（screen / backtest 依赖此约定）
FEATURE_COLUMNS = [
    "ma5", "ma10", "ma20", "ma_bull", "vol_ratio", "rsi14",
    "macd", "macd_signal", "macd_hist", "dist_high20", "pct_chg",
    "up_streak", "amp",
]


def _rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss.replace(0, np.nan)
    return (100 - 100 / (1 + rs)).fillna(50)


def _macd(close: pd.Series, fast=12, slow=26, signal=9):
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    macd = ema_fast - ema_slow
    sig = macd.ewm(span=signal, adjust=False).mean()
    return macd, sig, macd - sig


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """对单只股票的行情（按日期升序）追加技术指标列。"""
    df = df.sort_values("date").reset_index(drop=True).copy()
    close, vol = df["close"], df["volume"]

    df["ma5"] = close.rolling(5).mean()
    df["ma10"] = close.rolling(10).mean()
    df["ma20"] = close.rolling(20).mean()
    # 多头排列：MA5 > MA10 > MA20
    df["ma_bull"] = ((df["ma5"] > df["ma10"]) & (df["ma10"] > df["ma20"])).astype(int)
    # 量比：当日成交量 / 过去5日均量
    df["vol_ratio"] = vol / vol.rolling(5).mean().shift(1)
    df["rsi14"] = _rsi(close)
    df["macd"], df["macd_signal"], df["macd_hist"] = _macd(close)
    # 距20日最高价的距离（负值=低于高点的百分比）
    df["dist_high20"] = close / close.rolling(20).max() - 1
    # 连续上涨天数
    up = (df["pct_chg"] > 0).astype(int)
    df["up_streak"] = up.groupby((up != up.shift()).cumsum()).cumsum() * up
    # 当日振幅
    df["amp"] = (df["high"] - df["low"]) / close.shift(1)
    return df


def label_limit_up(df: pd.DataFrame, limit_up_pct: float = 0.095) -> pd.DataFrame:
    """标注「次日是否涨停」作为回测/研究的目标变量（不用于实时预测）。"""
    df = df.copy()
    df["limit_up"] = (df["pct_chg"] >= limit_up_pct * 100).astype(int)
    df["next_limit_up"] = df["limit_up"].shift(-1).fillna(0).astype(int)
    df["next_ret"] = df["close"].shift(-1) / df["close"] - 1
    return df


def build_feature_table(
    price_by_symbol: dict[str, pd.DataFrame], limit_up_pct: float = 0.095
) -> pd.DataFrame:
    """对一批股票批量计算特征，合并为一张长表。

    price_by_symbol: {symbol: 行情DataFrame}
    返回：每行 = 某股票某交易日的特征快照（含标注）。
    """
    frames = []
    for sym, raw in price_by_symbol.items():
        if raw is None or len(raw) < 25:  # 数据太短无法算指标
            continue
        feat = label_limit_up(add_indicators(raw), limit_up_pct)
        feat["symbol"] = sym
        frames.append(feat)
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)
