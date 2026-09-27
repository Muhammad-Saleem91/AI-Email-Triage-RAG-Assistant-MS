from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.models.document import Document
from app.schemas.document import (
    BatchUploadResponse,
    DocumentListResponse,
    DocumentResponse,
)
from app.services.document_service import (
    ingest_document,
    remove_document_vectors,
    reprocess_document,
)

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("/upload", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """Upload and index one document."""
    try:
        document = await ingest_document(file, db)
        if document.status == "failed":
            raise HTTPException(
                status_code=422,
                detail=document.error_message or "Document processing failed.",
            )
        return document
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/upload-batch", response_model=BatchUploadResponse)
async def upload_documents_batch(
    files: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
):
    """Upload several PDF/DOCX/TXT documents in a single request.

    Files are processed independently so one bad file does not discard the
    successful files in the same batch.
    """
    if not files:
        raise HTTPException(status_code=400, detail="Select at least one file.")

    items: list[dict] = []
    succeeded = 0
    failed = 0

    for file in files:
        filename = file.filename or "unnamed"
        try:
            document = await ingest_document(file, db)
            success = document.status == "processed"
            if success:
                succeeded += 1
            else:
                failed += 1
            items.append(
                {
                    "filename": filename,
                    "success": success,
                    "document": document,
                    "error": None if success else document.error_message,
                }
            )
        except Exception as exc:
            failed += 1
            items.append(
                {
                    "filename": filename,
                    "success": False,
                    "document": None,
                    "error": str(exc),
                }
            )

    return {
        "items": items,
        "total": len(files),
        "succeeded": succeeded,
        "failed": failed,
    }


@router.get("", response_model=DocumentListResponse)
def list_documents(db: Session = Depends(get_db)):
    items = list(db.scalars(select(Document).order_by(Document.created_at.desc())).all())
    total = db.scalar(select(func.count()).select_from(Document)) or 0
    return {"items": items, "total": total}


@router.get("/{document_id}", response_model=DocumentResponse)
def get_document(document_id: str, db: Session = Depends(get_db)):
    document = db.get(Document, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found.")
    return document


@router.post("/{document_id}/reprocess", response_model=DocumentResponse)
def reprocess(document_id: str, db: Session = Depends(get_db)):
    document = db.get(Document, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found.")
    try:
        document = reprocess_document(document, db)
        if document.status == "failed":
            raise HTTPException(status_code=422, detail=document.error_message)
        return document
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(document_id: str, db: Session = Depends(get_db)):
    document = db.get(Document, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found.")

    try:
        remove_document_vectors(document.id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Vector cleanup failed: {exc}") from exc

    path = get_settings().upload_path / document.stored_name
    if path.exists():
        path.unlink()
    db.delete(document)
    db.commit()
