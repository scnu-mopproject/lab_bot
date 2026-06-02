"""端到端流水线测试（全部使用合成数据，离线可跑）。

覆盖：合成数据生成 -> 落库 -> 特征工程 -> 打分 -> 回测 -> 持仓策略。
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from lab_bot.backtest.engine import backtest_scoring
from lab_bot.data import mock
from lab_bot.data.storage import Storage
from lab_bot.features.engineering import (
    FEATURE_COLUMNS, add_indicators, build_feature_table, label_limit_up,
)
from lab_bot.portfolio.strategy import analyze_portfolio
from lab_bot.screen.scoring import score_snapshot, screen_candidates


@pytest.fixture
def price_data():
    return {f"60000{i}": mock.make_price_history(f"60000{i}", days=120, seed=i)
            for i in range(8)}


def test_mock_price_schema():
    df = mock.make_price_history("600519", days=60, seed=1)
    assert list(df.columns) == mock.PRICE_COLUMNS
    assert len(df) == 60
    assert (df["high"] >= df["low"]).all()


def test_storage_roundtrip(tmp_path):
    db = tmp_path / "t.db"
    df = mock.make_price_history("600519", days=30, seed=2)
    with Storage(db) as s:
        n = s.save_price(df)
        assert n == 30
        # 幂等：重复写入不增加行数
        s.save_price(df)
        loaded = s.load_price("600519")
        assert len(loaded) == 30
        assert "600519" in s.symbols()


def test_storage_news(tmp_path):
    db = tmp_path / "n.db"
    news = mock.make_news(20)
    with Storage(db) as s:
        assert s.save_news(news) == 20
        assert len(s.load_news()) <= 20


def test_indicators(price_data):
    df = add_indicators(price_data["600000"])
    for col in ["ma5", "ma20", "rsi14", "macd", "vol_ratio"]:
        assert col in df.columns
    # RSI 介于 0-100
    assert df["rsi14"].between(0, 100).all()


def test_feature_table(price_data):
    ft = build_feature_table(price_data, limit_up_pct=0.095)
    assert not ft.empty
    for col in FEATURE_COLUMNS:
        assert col in ft.columns
    assert {"limit_up", "next_limit_up", "next_ret"} <= set(ft.columns)


def test_scoring_range(price_data):
    ft = build_feature_table(price_data)
    row = ft.iloc[-1]
    res = score_snapshot(row)
    assert 0 <= res["score"] <= 100
    assert abs(sum(res["components"].values()) - res["score"]) < 0.5


def test_screen_topk(price_data):
    ft = build_feature_table(price_data)
    cand = screen_candidates(ft, top_k=3)
    assert len(cand) <= 3
    assert cand["score"].is_monotonic_decreasing


def test_backtest(price_data):
    ft = build_feature_table(price_data)
    res = backtest_scoring(ft, top_k=3, hold_days=1)
    assert "win_rate" in res
    assert 0 <= res["win_rate"] <= 1
    assert res["n_trades"] > 0


def test_portfolio_stop_loss():
    positions = [{"symbol": "600000", "name": "测试", "cost": 100.0, "qty": 100}]
    last_prices = {"600000": 90.0}  # 亏损 10%
    cand = pd.DataFrame([{"symbol": "600001", "score": 80, "close": 20.0}])
    res = analyze_portfolio(positions, last_prices, cand, total_capital=100_000,
                            stop_loss_pct=0.07, take_profit_pct=0.15)
    assert res["holdings"][0]["action"] == "止损"
    assert "disclaimer" in res


def test_portfolio_take_profit():
    positions = [{"symbol": "600000", "cost": 100.0, "qty": 100}]
    res = analyze_portfolio(positions, {"600000": 120.0}, None,
                            stop_loss_pct=0.07, take_profit_pct=0.15)
    assert "止盈" in res["holdings"][0]["action"]


def test_label_limit_up():
    df = mock.make_price_history("600519", days=50, seed=3)
    labeled = label_limit_up(add_indicators(df), 0.095)
    assert labeled["limit_up"].isin([0, 1]).all()
