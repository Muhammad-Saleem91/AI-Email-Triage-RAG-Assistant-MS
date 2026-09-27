import json
from datetime import datetime
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.chat import ChatMessage, ChatSession
from app.services.rag_service import RagService


def _sources_from_json(value: str) -> list[dict]:
    try:
        parsed = json.loads(value or "[]")
        return parsed if isinstance(parsed, list) else []
    except json.JSONDecodeError:
        return []


def message_to_dict(message: ChatMessage) -> dict:
    return {
        "id": message.id,
        "role": message.role,
        "content": message.content,
        "grounded": message.grounded,
        "sources": _sources_from_json(message.sources_json),
        "created_at": message.created_at,
    }


def session_to_summary(session: ChatSession) -> dict:
    return {
        "id": session.id,
        "title": session.title,
        "message_count": len(session.messages),
        "created_at": session.created_at,
        "updated_at": session.updated_at,
    }


def session_to_detail(session: ChatSession) -> dict:
    return {
        "id": session.id,
        "title": session.title,
        "created_at": session.created_at,
        "updated_at": session.updated_at,
        "messages": [message_to_dict(message) for message in session.messages],
    }


def create_chat(db: Session, title: str | None = None) -> ChatSession:
    session = ChatSession(
        id=str(uuid4()),
        title=(title or "New conversation").strip() or "New conversation",
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def list_chats(db: Session) -> list[ChatSession]:
    return list(
        db.scalars(
            select(ChatSession).order_by(ChatSession.updated_at.desc())
        ).all()
    )


def get_chat(db: Session, session_id: str) -> ChatSession | None:
    return db.get(ChatSession, session_id)


def delete_chat(db: Session, session: ChatSession) -> None:
    db.delete(session)
    db.commit()


def answer_in_chat(
    db: Session,
    session: ChatSession,
    question: str,
    top_k: int | None = None,
) -> tuple[ChatMessage, ChatMessage]:
    question = question.strip()
    if not question:
        raise ValueError("Question cannot be empty.")

    rag_result = RagService().answer(question, top_k=top_k)
    now = datetime.utcnow()

    user_message = ChatMessage(
        id=str(uuid4()),
        session_id=session.id,
        role="user",
        content=question,
        grounded=None,
        sources_json="[]",
        created_at=now,
    )

    assistant_message = ChatMessage(
        id=str(uuid4()),
        session_id=session.id,
        role="assistant",
        content=rag_result["answer"],
        grounded=bool(rag_result["grounded"]),
        sources_json=json.dumps(rag_result.get("sources", [])),
        created_at=datetime.utcnow(),
    )

    if not session.messages or session.title == "New conversation":
        session.title = question[:60] + ("..." if len(question) > 60 else "")

    session.updated_at = datetime.utcnow()
    db.add_all([user_message, assistant_message, session])
    db.commit()
    db.refresh(user_message)
    db.refresh(assistant_message)
    db.refresh(session)

    return user_message, assistant_message
