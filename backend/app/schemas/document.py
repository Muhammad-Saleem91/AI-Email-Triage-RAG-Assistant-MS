from datetime import datetime

from pydantic import BaseModel, ConfigDict


class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    original_name: str
    file_type: str
    size_bytes: int
    status: str
    page_count: int | None
    char_count: int
    chunk_count: int
    error_message: str | None
    created_at: datetime
    updated_at: datetime


class DocumentListResponse(BaseModel):
    items: list[DocumentResponse]
    total: int


class BatchUploadItem(BaseModel):
    filename: str
    success: bool
    document: DocumentResponse | None = None
    error: str | None = None


class BatchUploadResponse(BaseModel):
    items: list[BatchUploadItem]
    total: int
    succeeded: int
    failed: int
