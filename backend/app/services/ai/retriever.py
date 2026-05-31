"""基于 FAQ 表的轻量检索器（关键词重叠打分）。

生产可替换为向量检索（embedding + 向量库），接口保持不变。
"""
import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.faq import FAQ
from app.services.ai.base import RetrievedDoc, Retriever


def _tokenize(text: str) -> set[str]:
    # 简单中英分词：英文按词，中文按 2-gram
    text = text.lower()
    words = set(re.findall(r"[a-z0-9]+", text))
    zh = re.findall(r"[一-鿿]", text)
    for i in range(len(zh) - 1):
        words.add(zh[i] + zh[i + 1])
    words.update(zh)
    return words


class FAQRetriever(Retriever):
    def __init__(self, db: Session):
        self.db = db

    def search(self, query: str, top_k: int = 3) -> list[RetrievedDoc]:
        faqs = list(self.db.scalars(select(FAQ)).all())
        q_tokens = _tokenize(query)
        if not q_tokens:
            return []
        scored: list[RetrievedDoc] = []
        for f in faqs:
            corpus = f"{f.question} {f.keywords or ''}"
            d_tokens = _tokenize(corpus)
            if not d_tokens:
                continue
            overlap = len(q_tokens & d_tokens)
            score = overlap / (len(q_tokens) ** 0.5 * len(d_tokens) ** 0.5)
            if score > 0:
                scored.append(RetrievedDoc(question=f.question, answer=f.answer, score=round(score, 3)))
        scored.sort(key=lambda d: d.score, reverse=True)
        return scored[:top_k]
