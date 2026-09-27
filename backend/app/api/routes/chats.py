from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.chat import (
    ChatCreateRequest,
    ChatQuestionRequest,
    ChatSessionDetail,
    ChatSessionListResponse,
    ChatSessionSummary,
    ChatTurnResponse,
)
from app.services.chat_service import (
    answer_in_chat,
    create_chat,
    delete_chat,
    get_chat,
    list_chats,
    message_to_dict,
    session_to_detail,
    session_to_summary,
)

router = APIRouter(prefix="/chats", tags=["chats"])


@router.post("", response_model=ChatSessionSummary, status_code=status.HTTP_201_CREATED)
def create_chat_session(payload: ChatCreateRequest, db: Session = Depends(get_db)):
    session = create_chat(db, payload.title)
    return session_to_summary(session)


@router.get("", response_model=ChatSessionListResponse)
def get_chat_sessions(db: Session = Depends(get_db)):
    sessions = list_chats(db)
    return {
        "items": [session_to_summary(session) for session in sessions],
        "total": len(sessions),
    }


@router.get("/{session_id}", response_model=ChatSessionDetail)
def get_chat_session(session_id: str, db: Session = Depends(get_db)):
    session = get_chat(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Chat session not found.")
    return session_to_detail(session)


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_chat_session(session_id: str, db: Session = Depends(get_db)):
    session = get_chat(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Chat session not found.")
    delete_chat(db, session)


@router.post("/{session_id}/messages", response_model=ChatTurnResponse)
def ask_in_chat(
    session_id: str,
    payload: ChatQuestionRequest,
    db: Session = Depends(get_db),
):
    session = get_chat(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Chat session not found.")

    try:
        user_message, assistant_message = answer_in_chat(
            db,
            session,
            payload.question,
            top_k=payload.top_k,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        if "temporarily unavailable" in str(exc):
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Chat request failed.") from exc

    return {
        "session_id": session.id,
        "session_title": session.title,
        "user_message": message_to_dict(user_message),
        "assistant_message": message_to_dict(assistant_message),
    }
