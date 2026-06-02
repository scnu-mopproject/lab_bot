"""财经新闻采集。

优先使用 AKShare 的财经快讯接口；失败且允许回退时使用合成新闻。
返回的 DataFrame 遵循 mock.NEWS_COLUMNS 结构。
"""
from __future__ import annotations

import logging

import pandas as pd

from . import mock

log = logging.getLogger(__name__)


def _akshare_available() -> bool:
    try:
        import akshare  # noqa: F401
        return True
    except Exception:
        return False


def get_financial_news(
    *, max_items: int = 200, allow_fallback: bool = True
) -> pd.DataFrame:
    """采集最新财经快讯，返回含 [datetime, title, content, source, url] 的 DataFrame。"""
    if _akshare_available():
        try:
            df = _ak_news(max_items)
            df.attrs["fallback"] = False
            return df
        except Exception as e:
            log.warning("AKShare 新闻获取失败: %s", e)
            if not allow_fallback:
                raise

    if not allow_fallback:
        raise RuntimeError("AKShare 不可用且未允许回退")
    df = mock.make_news(min(max_items, 50))
    df.attrs["fallback"] = True
    return df


def _ak_news(max_items: int) -> pd.DataFrame:
    import akshare as ak

    # 东方财富全球财经快讯
    df = ak.stock_info_global_em()
    rename = {"标题": "title", "摘要": "content", "发布时间": "datetime"}
    df = df.rename(columns=rename)
    df["source"] = "em"
    if "url" not in df.columns:
        df["url"] = df.get("链接", "")
    for col in mock.NEWS_COLUMNS:
        if col not in df.columns:
            df[col] = ""
    return df[mock.NEWS_COLUMNS].head(max_items).reset_index(drop=True)


def tag_news(df: pd.DataFrame, keywords: list[str]) -> pd.DataFrame:
    """给每条新闻打上命中的关键词标签，便于后续题材/情绪分析。"""
    if df is None or df.empty:
        return df
    df = df.copy()
    df["tags"] = df["title"].fillna("").apply(
        lambda t: ",".join(k for k in keywords if k in t)
    )
    return df
