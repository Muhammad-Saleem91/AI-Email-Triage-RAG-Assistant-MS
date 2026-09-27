from pydantic import BaseModel, Field


class RagQueryRequest(BaseModel):
    question: str = Field(min_length=2, max_length=4000)
    top_k: int | None = Field(default=None, ge=1, le=10)


class SourceReference(BaseModel):
    document_id: str
    document_name: str
    page_number: int | None = None
    chunk_id: str
    score: float
    excerpt: str


class RagQueryResponse(BaseModel):
    answer: str
    grounded: bool
    sources: list[SourceReference]
