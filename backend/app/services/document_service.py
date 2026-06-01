"""知识文档：解析 -> 切片 -> 向量化 -> 入库；以及删除。

支持 txt / md / pdf / docx / xlsx。
"""
import io
import re

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.document import Document, DocumentChunk
from app.services.ai.embedding import get_embedding_provider

CHUNK_SIZE = 500
CHUNK_OVERLAP = 50
# 在句末标点 / 换行处切句，避免切断语义
_SENT_SPLIT = re.compile(r"(?<=[。！？!?；;\n])")


def parse_file(content: bytes, filename: str) -> str:
    name = filename.lower()
    if name.endswith((".txt", ".md", ".markdown")):
        return content.decode("utf-8", errors="ignore")
    if name.endswith(".pdf"):
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(content))
        return "\n".join((p.extract_text() or "") for p in reader.pages)
    if name.endswith(".docx"):
        import docx

        d = docx.Document(io.BytesIO(content))
        parts = [p.text for p in d.paragraphs]
        for tbl in d.tables:
            for row in tbl.rows:
                parts.append(" ".join(c.text for c in row.cells))
        return "\n".join(parts)
    if name.endswith(".xlsx"):
        from openpyxl import load_workbook

        wb = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
        lines = []
        for ws in wb.worksheets:
            for row in ws.iter_rows(values_only=True):
                cells = [str(c) for c in row if c is not None]
                if cells:
                    lines.append(" ".join(cells))
        return "\n".join(lines)
    raise ValueError("仅支持 txt / md / pdf / docx / xlsx 文件")


def chunk_text(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    text = re.sub(r"[ \t]+", " ", text).strip()
    if not text:
        return []
    sentences = [s.strip() for s in _SENT_SPLIT.split(text) if s.strip()]
    chunks: list[str] = []
    cur = ""
    for s in sentences:
        if len(s) > size:  # 超长句硬切
            if cur:
                chunks.append(cur)
                cur = ""
            for i in range(0, len(s), size - overlap):
                chunks.append(s[i:i + size])
            continue
        if len(cur) + len(s) <= size:
            cur += s
        else:
            chunks.append(cur)
            # 带一点重叠，保留上下文
            cur = (cur[-overlap:] if overlap else "") + s
    if cur:
        chunks.append(cur)
    return chunks


def index_document(db: Session, *, content: bytes, filename: str,
                   title: str | None, uploaded_by: int | None) -> Document:
    text = parse_file(content, filename)
    chunks = chunk_text(text)
    if not chunks:
        raise ValueError("文档解析后无有效文本内容")

    provider = get_embedding_provider()
    vectors = provider.embed(chunks)

    doc = Document(
        title=title or filename, filename=filename, uploaded_by=uploaded_by,
        chunk_count=len(chunks), embedding_model=provider.name,
    )
    db.add(doc)
    db.flush()  # 取得 doc.id
    for i, (chunk, vec) in enumerate(zip(chunks, vectors)):
        db.add(DocumentChunk(document_id=doc.id, chunk_index=i, content=chunk,
                             embedding=vec, embedding_model=provider.name))
    db.commit()
    db.refresh(doc)
    return doc


def delete_document(db: Session, doc_id: int) -> bool:
    doc = db.get(Document, doc_id)
    if not doc:
        return False
    db.execute(delete(DocumentChunk).where(DocumentChunk.document_id == doc_id))
    db.delete(doc)
    db.commit()
    return True


def list_documents(db: Session) -> list[Document]:
    return list(db.scalars(select(Document).order_by(Document.created_at.desc())).all())
