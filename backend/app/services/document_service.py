import hashlib
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.document import Document
from app.services.chunking_service import chunk_pages
from app.services.embedding_service import EmbeddingService
from app.services.extraction_service import extract_document
from app.services.vector_service import get_vector_service

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt"}


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _process_and_index(document: Document, path: Path, db: Session) -> Document:
    settings = get_settings()
    extension = Path(document.original_name).suffix.lower()

    try:
        document.status = "processing"
        document.error_message = None
        db.commit()

        extracted = extract_document(path, extension)
        chunks = chunk_pages(
            extracted.pages,
            document_id=document.id,
            chunk_size=settings.chunk_size,
            overlap=settings.chunk_overlap,
        )
        if not chunks:
            raise ValueError("Document produced no indexable chunks.")

        vectors = EmbeddingService().embed_documents(
            [chunk.text for chunk in chunks],
            title=document.original_name,
        )
        get_vector_service().index_chunks(
            document_id=document.id,
            document_name=document.original_name,
            chunks=chunks,
            vectors=vectors,
        )

        document.extracted_text = extracted.text
        document.char_count = len(extracted.text)
        document.page_count = extracted.page_count
        document.chunk_count = len(chunks)
        document.status = "processed"
        document.error_message = None
    except Exception as exc:
        document.status = "failed"
        document.error_message = str(exc)

    db.add(document)
    db.commit()
    db.refresh(document)
    return document


async def ingest_document(file: UploadFile, db: Session) -> Document:
    settings = get_settings()
    upload_dir = settings.upload_path
    upload_dir.mkdir(parents=True, exist_ok=True)

    original_name = file.filename or "unnamed"
    extension = Path(original_name).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise ValueError("Unsupported file type. Use PDF, DOCX or TXT.")

    data = await file.read()
    if not data:
        raise ValueError("Uploaded file is empty.")
    if len(data) > settings.max_upload_mb * 1024 * 1024:
        raise ValueError(f"File exceeds {settings.max_upload_mb} MB limit.")

    digest = _sha256(data)
    existing = db.scalar(select(Document).where(Document.sha256 == digest))
    if existing:
        # If a previous indexing attempt failed, retry it automatically.
        # This is useful after fixing configuration/provider errors because
        # users can simply upload the same file again.
        if existing.status == "failed":
            existing_path = upload_dir / existing.stored_name
            if not existing_path.exists():
                existing_path.write_bytes(data)
            return _process_and_index(existing, existing_path, db)
        return existing

    document_id = str(uuid4())
    stored_name = f"{document_id}{extension}"
    path = upload_dir / stored_name
    path.write_bytes(data)

    document = Document(
        id=document_id,
        original_name=original_name,
        stored_name=stored_name,
        file_type=extension.lstrip("."),
        size_bytes=len(data),
        sha256=digest,
        status="processing",
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    return _process_and_index(document, path, db)


def reprocess_document(document: Document, db: Session) -> Document:
    path = get_settings().upload_path / document.stored_name
    if not path.exists():
        raise FileNotFoundError("Stored document file is missing.")
    return _process_and_index(document, path, db)


def remove_document_vectors(document_id: str) -> None:
    get_vector_service().delete_document(document_id)
