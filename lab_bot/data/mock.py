"""合成数据生成器。

当 AKShare 不可用（无网络 / 接口故障）时，生成结构与真实数据一致的
行情与新闻，保证整条流水线、回测与测试在离线环境下可复现地跑通。

生成的数据带固定随机种子，因此可复现。
"""
from __future__ import annotations

from datetime import datetime, timedelta

import numpy as np
import pandas as pd

# 价格历史的标准列结构（全流程统一）
PRICE_COLUMNS = [
    "date", "symbol", "open", "high", "low", "close", "volume", "amount", "pct_chg",
]
NEWS_COLUMNS = ["datetime", "title", "content", "source", "url"]


def _trading_days(end: datetime, n: int) -> list[datetime]:
    """从 end 往回取 n 个工作日（跳过周末，近似交易日）。"""
    days: list[datetime] = []
    cur = end
    while len(days) < n:
        if cur.weekday() < 5:  # 0-4 为周一到周五
            days.append(cur)
        cur -= timedelta(days=1)
    return list(reversed(days))


def make_price_history(
    symbol: str, days: int = 250, *, seed: int | None = None, limit_up_pct: float = 0.095,
) -> pd.DataFrame:
    """为单只股票生成 days 天的日 K 线，包含偶发涨停。"""
    rng = np.random.default_rng(seed if seed is not None else abs(hash(symbol)) % (2**32))
    dates = _trading_days(datetime.now(), days)

    base = rng.uniform(8, 60)  # 起始价
    drift = rng.normal(0.0003, 0.0005)  # 轻微趋势
    rows = []
    prev_close = base
    for d in dates:
        # 多数日子小幅波动，少数日子触发涨停
        if rng.random() < 0.04:
            pct = rng.uniform(limit_up_pct, 0.10)  # 涨停日
        else:
            pct = np.clip(rng.normal(drift, 0.02), -0.099, 0.099)
        close = round(prev_close * (1 + pct), 2)
        open_ = round(prev_close * (1 + rng.normal(0, 0.01)), 2)
        high = round(max(open_, close) * (1 + abs(rng.normal(0, 0.006))), 2)
        low = round(min(open_, close) * (1 - abs(rng.normal(0, 0.006))), 2)
        volume = int(abs(rng.normal(1_000_000, 400_000)) + 100_000)
        amount = round(volume * (high + low) / 2, 2)
        rows.append([
            d.strftime("%Y-%m-%d"), symbol, open_, high, low, close,
            volume, amount, round(pct * 100, 2),
        ])
        prev_close = close

    return pd.DataFrame(rows, columns=PRICE_COLUMNS)


def make_stock_list(n: int = 20) -> pd.DataFrame:
    """生成一个包含 n 只股票的股票池（代码 + 名称）。"""
    rng = np.random.default_rng(42)
    symbols = []
    for _ in range(n):
        # 沪市 60xxxx / 深市 00xxxx
        if rng.random() < 0.5:
            code = f"60{rng.integers(0, 9999):04d}"
        else:
            code = f"00{rng.integers(0, 9999):04d}"
        symbols.append(code)
    symbols = sorted(set(symbols))
    return pd.DataFrame({"symbol": symbols, "name": [f"模拟股{s}" for s in symbols]})


def make_news(n: int = 50, *, seed: int = 7) -> pd.DataFrame:
    """生成 n 条财经新闻。"""
    rng = np.random.default_rng(seed)
    templates = [
        ("{name}发布业绩预增公告，净利润同比增长{pct}%", "业绩预增"),
        ("{name}筹划重大资产重组，股票明日复牌", "重组"),
        ("利好政策出台，{sector}板块迎来发展机遇", "政策"),
        ("{name}获机构大举增持，资金面持续向好", "利好"),
        ("{name}今日封涨停，成交活跃", "涨停"),
        ("{sector}行业景气度回升，相关个股受关注", "行业"),
    ]
    sectors = ["新能源", "半导体", "医药", "白酒", "军工", "人工智能", "证券"]
    now = datetime.now()
    rows = []
    for i in range(n):
        tpl, tag = templates[rng.integers(0, len(templates))]
        name = f"模拟股{rng.integers(600000, 604000)}"
        title = tpl.format(name=name, pct=rng.integers(20, 200), sector=rng.choice(sectors))
        dt = (now - timedelta(minutes=int(rng.integers(0, 600)))).strftime("%Y-%m-%d %H:%M:%S")
        rows.append([dt, title, title + "。（合成新闻，仅供流程演示）", "mock", ""])
    return pd.DataFrame(rows, columns=NEWS_COLUMNS)
