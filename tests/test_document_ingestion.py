from __future__ import annotations

from io import BytesIO
from pathlib import Path

import pytest
from docx import Document
from pypdf import PdfWriter

from axioms.document_ingestion import DocumentIngestionError, DocumentStore, extract_text


def _docx_bytes(*paragraphs: str) -> bytes:
    document = Document()
    for paragraph in paragraphs:
        document.add_paragraph(paragraph)
    buffer = BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def test_extract_text_supports_utf8_text_and_docx_with_normalised_paragraphs() -> None:
    text, media_type = extract_text(b"First   line\n\nSecond line\n", "notes.txt")
    assert text == "First line\nSecond line"
    assert media_type == "text/plain"

    docx_text, docx_media_type = extract_text(
        _docx_bytes("First   paragraph", "Second paragraph"), "reference.docx"
    )
    assert docx_text == "First paragraph\nSecond paragraph"
    assert docx_media_type.endswith("wordprocessingml.document")


def test_extract_text_rejects_unsupported_paths_empty_documents_and_blank_pdfs() -> None:
    with pytest.raises(DocumentIngestionError, match="Supported types"):
        extract_text(b"hello", "notes.csv")
    with pytest.raises(DocumentIngestionError, match="without a path"):
        extract_text(b"hello", "../notes.txt")
    with pytest.raises(DocumentIngestionError, match="empty"):
        extract_text(b"", "notes.txt")

    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    buffer = BytesIO()
    writer.write(buffer)
    with pytest.raises(DocumentIngestionError, match="No extractable text"):
        extract_text(buffer.getvalue(), "blank.pdf")


def test_store_requires_explicit_non_sensitive_confirmation_and_returns_metadata_only(tmp_path: Path) -> None:
    store = DocumentStore(tmp_path / "documents.sqlite3")
    with pytest.raises(DocumentIngestionError, match="explicit confirmation"):
        store.ingest(b"Internal research notes", "notes.txt", confirmed_non_sensitive=False)

    stored = store.ingest(b"Internal research notes", "notes.txt", confirmed_non_sensitive=True)
    assert stored.document_id.startswith("doc_")
    assert stored.char_count == len("Internal research notes")
    assert len(stored.sha256) == 64
    assert stored.confirmed_non_sensitive
    assert store.get_metadata(stored.document_id) == stored
    assert store.get_text_for_internal_use(stored.document_id) == "Internal research notes"
    assert store.get_metadata("doc_missing") is None
    assert store.get_text_for_internal_use("doc_missing") is None
