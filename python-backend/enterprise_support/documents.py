from __future__ import annotations

from html.parser import HTMLParser
from io import BytesIO
from pathlib import Path

from docx import Document as DocxDocument
from pypdf import PdfReader


SUPPORTED_DOCUMENT_SUFFIXES = {".pdf", ".docx", ".html", ".htm", ".md", ".markdown", ".txt"}


class UnsupportedDocumentType(ValueError):
    pass


class _HTMLTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        text = data.strip()
        if text:
            self.parts.append(text)


def extract_document_text(filename: str, data: bytes) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix == ".pdf":
        reader = PdfReader(BytesIO(data))
        return "\n\n".join(page.extract_text() or "" for page in reader.pages).strip()
    if suffix == ".docx":
        document = DocxDocument(BytesIO(data))
        return "\n\n".join(paragraph.text for paragraph in document.paragraphs).strip()
    if suffix in {".html", ".htm"}:
        parser = _HTMLTextExtractor()
        parser.feed(data.decode("utf-8", errors="replace"))
        return "\n\n".join(parser.parts)
    if suffix in {".md", ".markdown", ".txt"}:
        return data.decode("utf-8", errors="replace").strip()
    raise UnsupportedDocumentType(
        "Supported file types: PDF, DOCX, Markdown, TXT, HTML"
    )

