from dataclasses import dataclass

from app.services.extraction_service import PageText


@dataclass
class TextChunk:
    chunk_id: str
    page_number: int | None
    text: str


def _split_text(text: str, chunk_size: int, overlap: int) -> list[str]:
    if chunk_size <= overlap:
        raise ValueError("chunk_size must be greater than chunk_overlap")

    chunks: list[str] = []
    start = 0
    length = len(text)

    while start < length:
        end = min(start + chunk_size, length)
        if end < length:
            boundary = text.rfind(" ", start, end)
            if boundary > start + chunk_size // 2:
                end = boundary

        piece = text[start:end].strip()
        if piece:
            chunks.append(piece)

        if end >= length:
            break
        start = max(end - overlap, start + 1)

    return chunks


def chunk_pages(
    pages: list[PageText],
    document_id: str,
    chunk_size: int,
    overlap: int,
) -> list[TextChunk]:
    chunks: list[TextChunk] = []
    global_index = 1

    for page in pages:
        for text in _split_text(page.text, chunk_size, overlap):
            chunks.append(
                TextChunk(
                    chunk_id=f"{document_id}-chunk-{global_index:04d}",
                    page_number=page.page_number,
                    text=text,
                )
            )
            global_index += 1

    return chunks
