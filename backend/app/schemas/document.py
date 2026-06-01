from datetime import datetime

from pydantic import BaseModel


class DocumentOut(BaseModel):
    id: int
    title: str
    filename: str
    chunk_count: int
    embedding_model: str
    created_at: datetime

    model_config = {"from_attributes": True}


class PaginatedDocuments(BaseModel):
    items: list[DocumentOut]
    total: int
    page: int
    page_size: int


class DocumentImportResult(BaseModel):
    created: int
    duplicated: int
    skipped: list[str] = []
    documents: list[DocumentOut] = []
