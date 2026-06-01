from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Document(Base):
    """管理员上传的知识文档（用于 RAG 问答）。"""
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(256))
    filename: Mapped[str] = mapped_column(String(256))
    uploaded_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    # 解析文本的 sha256，用于重复上传去重
    content_hash: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    # 记录建索引时使用的向量化方案，便于检索时只比对同方案的向量
    embedding_model: Mapped[str] = mapped_column(String(64), default="local")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class DocumentChunk(Base):
    """文档切片及其向量。"""
    __tablename__ = "document_chunks"

    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"), index=True)
    chunk_index: Mapped[int] = mapped_column(Integer, default=0)
    content: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list] = mapped_column(JSON, default=list)  # list[float]
    embedding_model: Mapped[str] = mapped_column(String(64), default="local")
