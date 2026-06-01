"""检索器：FAQ 关键词检索 + 文档向量检索，可混合。"""
import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.document import DocumentChunk
from app.models.faq import FAQ
from app.services.ai.base import RetrievedDoc, Retriever
from app.services.ai.embedding import cosine, get_embedding_provider


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
                scored.append(RetrievedDoc(title=f.question, content=f.answer,
                                           score=round(score, 3), kind="faq"))
        scored.sort(key=lambda d: d.score, reverse=True)
        return scored[:top_k]


class VectorRetriever(Retriever):
    """文档切片向量检索（余弦相似度）。"""

    def __init__(self, db: Session):
        self.db = db
        self.provider = get_embedding_provider()

    def search(self, query: str, top_k: int = 4) -> list[RetrievedDoc]:
        from app.models.document import Document

        chunks = list(self.db.scalars(select(DocumentChunk)).all())
        if not chunks:
            return []
        qv = self.provider.embed_one(query)
        titles = {d.id: d.title for d in self.db.scalars(select(Document)).all()}
        scored: list[RetrievedDoc] = []
        for ch in chunks:
            # 仅比对同一向量化方案、同维度的切片
            if ch.embedding_model != self.provider.name or len(ch.embedding) != len(qv):
                continue
            sim = cosine(qv, ch.embedding)
            if sim > 0:
                scored.append(RetrievedDoc(
                    title=titles.get(ch.document_id, "文档"),
                    content=ch.content, score=round(sim, 3), kind="document"))
        scored.sort(key=lambda d: d.score, reverse=True)
        return scored[:top_k]
