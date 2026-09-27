from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.chat import ChatMessage, ChatSession
from app.models.document import Document

router = APIRouter(prefix="/stats", tags=["stats"])


@router.get("")
def stats(db: Session = Depends(get_db)):
    total_documents = db.scalar(select(func.count()).select_from(Document)) or 0
    processed = db.scalar(
        select(func.count()).select_from(Document).where(Document.status == "processed")
    ) or 0
    processing = db.scalar(
        select(func.count()).select_from(Document).where(Document.status == "processing")
    ) or 0
    failed = db.scalar(
        select(func.count()).select_from(Document).where(Document.status == "failed")
    ) or 0
    total_chunks = db.scalar(select(func.coalesce(func.sum(Document.chunk_count), 0))) or 0
    total_chats = db.scalar(select(func.count()).select_from(ChatSession)) or 0
    total_questions = db.scalar(
        select(func.count()).select_from(ChatMessage).where(ChatMessage.role == "user")
    ) or 0

    return {
        "total_documents": total_documents,
        "processed": processed,
        "processing": processing,
        "failed": failed,
        "total_indexed_chunks": int(total_chunks),
        "total_chats": total_chats,
        "total_questions": total_questions,
    }
