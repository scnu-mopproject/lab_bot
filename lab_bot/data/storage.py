"""SQLite 存储层。

负责把行情与新闻落库，并提供读取接口。所有 skill 脚本共享同一个数据库，
避免重复抓取。表结构简单、幂等（重复写入按主键覆盖）。
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd

_SCHEMA = """
CREATE TABLE IF NOT EXISTS price_history (
    date    TEXT NOT NULL,
    symbol  TEXT NOT NULL,
    open    REAL, high REAL, low REAL, close REAL,
    volume  INTEGER, amount REAL, pct_chg REAL,
    PRIMARY KEY (symbol, date)
);
CREATE TABLE IF NOT EXISTS news (
    datetime TEXT NOT NULL,
    title    TEXT NOT NULL,
    content  TEXT,
    source   TEXT,
    url      TEXT,
    PRIMARY KEY (datetime, title)
);
CREATE INDEX IF NOT EXISTS idx_price_symbol ON price_history(symbol);
"""


class Storage:
    """轻量 SQLite 封装。用作上下文管理器或直接调用。"""

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.executescript(_SCHEMA)
        self.conn.commit()

    # -- 写入 -------------------------------------------------------------
    def save_price(self, df: pd.DataFrame) -> int:
        """幂等写入行情，返回写入行数。"""
        if df is None or df.empty:
            return 0
        rows = df[[
            "date", "symbol", "open", "high", "low", "close",
            "volume", "amount", "pct_chg",
        ]].itertuples(index=False, name=None)
        self.conn.executemany(
            "INSERT OR REPLACE INTO price_history "
            "(date,symbol,open,high,low,close,volume,amount,pct_chg) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            rows,
        )
        self.conn.commit()
        return len(df)

    def save_news(self, df: pd.DataFrame) -> int:
        if df is None or df.empty:
            return 0
        rows = df[["datetime", "title", "content", "source", "url"]].itertuples(
            index=False, name=None
        )
        self.conn.executemany(
            "INSERT OR REPLACE INTO news (datetime,title,content,source,url) "
            "VALUES (?,?,?,?,?)",
            rows,
        )
        self.conn.commit()
        return len(df)

    # -- 读取 -------------------------------------------------------------
    def load_price(self, symbol: str | None = None) -> pd.DataFrame:
        if symbol:
            q = "SELECT * FROM price_history WHERE symbol=? ORDER BY date"
            return pd.read_sql_query(q, self.conn, params=(symbol,))
        return pd.read_sql_query(
            "SELECT * FROM price_history ORDER BY symbol,date", self.conn
        )

    def load_news(self, limit: int = 200) -> pd.DataFrame:
        return pd.read_sql_query(
            "SELECT * FROM news ORDER BY datetime DESC LIMIT ?", self.conn, params=(limit,)
        )

    def symbols(self) -> list[str]:
        cur = self.conn.execute("SELECT DISTINCT symbol FROM price_history ORDER BY symbol")
        return [r[0] for r in cur.fetchall()]

    def close(self) -> None:
        self.conn.close()

    def __enter__(self) -> "Storage":
        return self

    def __exit__(self, *exc) -> None:
        self.close()
