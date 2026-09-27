from dataclasses import dataclass
from pathlib import Path

import fitz
from docx import Document as DocxDocument

from app.core.exceptions import EmptyDocumentError, UnsupportedDocumentTypeError


@dataclass
class PageText:
    page_number: int | None
    text: str


@dataclass
class ExtractionResult:
    text: str
    page_count: int | None
    pages: list[PageText]


def _clean_text(text: str) -> str:
    lines = [line.strip() for line in text.replace("\r\n", "\n").split("\n")]
    return "\n".join(line for line in lines if line).strip()


def extract_pdf(path: Path) -> ExtractionResult:
    doc = fitz.open(path)
    pages: list[PageText] = []
    for index, page in enumerate(doc, start=1):
        cleaned = _clean_text(page.get_text("text"))
        if cleaned:
            pages.append(PageText(page_number=index, text=cleaned))
    text = "\n\n".join(page.text for page in pages)
    return ExtractionResult(text=text, page_count=len(doc), pages=pages)


def extract_docx(path: Path) -> ExtractionResult:
    doc = DocxDocument(path)
    text = _clean_text("\n".join(p.text for p in doc.paragraphs))
    return ExtractionResult(
        text=text,
        page_count=None,
        pages=[PageText(page_number=None, text=text)] if text else [],
    )


def extract_txt(path: Path) -> ExtractionResult:
    try:
        raw = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        raw = path.read_text(encoding="latin-1")
    text = _clean_text(raw)
    return ExtractionResult(
        text=text,
        page_count=None,
        pages=[PageText(page_number=None, text=text)] if text else [],
    )


def extract_document(path: Path, extension: str) -> ExtractionResult:
    extension = extension.lower()
    if extension == ".pdf":
        result = extract_pdf(path)
    elif extension == ".docx":
        result = extract_docx(path)
    elif extension == ".txt":
        result = extract_txt(path)
    else:
        raise UnsupportedDocumentTypeError("Only PDF, DOCX and TXT files are supported.")

    if not result.text:
        raise EmptyDocumentError("No readable text was found in the document.")
    return result
