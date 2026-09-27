from fastapi import APIRouter, HTTPException

from app.schemas.rag import RagQueryRequest, RagQueryResponse
from app.services.rag_service import RagService

router = APIRouter(prefix="/rag", tags=["rag"])


@router.post("/query", response_model=RagQueryResponse)
def rag_query(payload: RagQueryRequest):
    try:
        return RagService().answer(payload.question, top_k=payload.top_k)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        if "temporarily unavailable" in str(exc):
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="RAG query failed.") from exc
