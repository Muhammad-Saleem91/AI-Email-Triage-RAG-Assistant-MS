from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.rag import SourceReference


class ChatCreateRequest(BaseModel):
    title: str | None = Field(default=None, max_length=180)


class ChatMessageResponse(BaseModel):
    id: str
    role: str
    content: str
    grounded: bool | None = None
    sources: list[SourceReference] = Field(default_factory=list)
    created_at: datetime


class ChatSessionSummary(BaseModel):
    id: str
    title: str
    message_count: int
    created_at: datetime
    updated_at: datetime


class ChatSessionListResponse(BaseModel):
    items: list[ChatSessionSummary]
    total: int


class ChatSessionDetail(BaseModel):
    id: str
    title: str
    created_at: datetime
    updated_at: datetime
    messages: list[ChatMessageResponse]


class ChatQuestionRequest(BaseModel):
    question: str = Field(min_length=2, max_length=4000)
    top_k: int | None = Field(default=None, ge=1, le=10)


class ChatTurnResponse(BaseModel):
    session_id: str
    session_title: str
    user_message: ChatMessageResponse
    assistant_message: ChatMessageResponse
