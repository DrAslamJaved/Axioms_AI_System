"""Conservative local extraction and storage for explicitly non-sensitive reference documents."""

from __future__ import annotations

import hashlib
import sqlite3
import zipfile
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path
from uuid import uuid4

from docx import Document
from pypdf import PdfReader
from pypdf.errors import PdfReadError

from axioms.store import database_path

MAX_UPLOAD_BYTES = 5 * 1024 * 1024
MAX_EXTRACTED_CHARACTERS = 200_000
MAX_PDF_PAGES = 250
MAX_DOCX_UNCOMPRESSED_BYTES = 20 * 1024 * 1024
MAX_DOCX_COMPRESSION_RATIO = 100
SUPPORTED_SUFFIXES = {".pdf", ".docx", ".txt"}


class DocumentIngestionError(ValueError):
    """Raised when an upload cannot safely become local reference text."""


@dataclass(frozen=True, slots=True)
class StoredDocument:
    document_id: str
    filename: str
    media_type: str
    char_count: int
    sha256: str
    created_at: str
    confirmed_non_sensitive: bool

    def to_dict(self) -> dict:
        return asdict(self)


def extract_text(content: bytes, filename: str) -> tuple[str, str]:
    """Extract bounded text from a supported document without contacting any external service."""
    _validate_upload(content, filename)
    suffix = Path(filename).suffix.casefold()
    try:
        if suffix == ".txt":
            text = content.decode("utf-8")
            media_type = "text/plain"
        elif suffix == ".docx":
            _validate_docx_archive(content)
            document = Document(BytesIO(content))
            text = "\n".join(paragraph.text for paragraph in document.paragraphs)
            media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        else:
            reader = PdfReader(BytesIO(content))
            if reader.is_encrypted:
                raise DocumentIngestionError("Encrypted PDFs are not accepted.")
            if len(reader.pages) > MAX_PDF_PAGES:
                raise DocumentIngestionError(f"PDFs may contain at most {MAX_PDF_PAGES} pages.")
            text = "\n\n".join(page.extract_text() or "" for page in reader.pages)
            media_type = "application/pdf"
    except (PdfReadError, UnicodeDecodeError, zipfile.BadZipFile, ValueError) as error:
        if isinstance(error, DocumentIngestionError):
            raise
        raise DocumentIngestionError("The document could not be read safely.") from error

    normalized = _normalise_text(text)
    if not normalized:
        raise DocumentIngestionError("No extractable text was found in the document.")
    if len(normalized) > MAX_EXTRACTED_CHARACTERS:
        raise DocumentIngestionError(
            f"Extracted text exceeds the {MAX_EXTRACTED_CHARACTERS:,}-character limit."
        )
    return normalized, media_type


def _validate_upload(content: bytes, filename: str) -> None:
    if not filename or Path(filename).name != filename:
        raise DocumentIngestionError("Provide a plain filename without a path.")
    if Path(filename).suffix.casefold() not in SUPPORTED_SUFFIXES:
        supported = ", ".join(sorted(SUPPORTED_SUFFIXES))
        raise DocumentIngestionError(f"Unsupported document type. Supported types: {supported}.")
    if not content:
        raise DocumentIngestionError("The uploaded document is empty.")
    if len(content) > MAX_UPLOAD_BYTES:
        raise DocumentIngestionError(f"Uploads may not exceed {MAX_UPLOAD_BYTES // (1024 * 1024)} MiB.")


def _validate_docx_archive(content: bytes) -> None:
    with zipfile.ZipFile(BytesIO(content)) as archive:
        uncompressed_size = sum(item.file_size for item in archive.infolist())
        if uncompressed_size > MAX_DOCX_UNCOMPRESSED_BYTES:
            raise DocumentIngestionError("DOCX archive expands beyond the safe size limit.")
        if any(
            item.compress_size and item.file_size / item.compress_size > MAX_DOCX_COMPRESSION_RATIO
            for item in archive.infolist()
        ):
            raise DocumentIngestionError("DOCX archive compression ratio exceeds the safe limit.")


def _normalise_text(text: str) -> str:
    paragraphs = (" ".join(line.split()) for line in text.splitlines())
    return "\n".join(paragraph for paragraph in paragraphs if paragraph).strip()


class DocumentStore:
    """Private local reference-text store; content is never returned by the public API."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or database_path()
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS ingested_documents (
                    document_id TEXT PRIMARY KEY,
                    filename TEXT NOT NULL,
                    media_type TEXT NOT NULL,
                    content TEXT NOT NULL,
                    char_count INTEGER NOT NULL,
                    sha256 TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    confirmed_non_sensitive INTEGER NOT NULL
                )
                """
            )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, check_same_thread=False, timeout=5.0)
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA busy_timeout=5000")
        return connection

    def ingest(self, content: bytes, filename: str, *, confirmed_non_sensitive: bool) -> StoredDocument:
        """Persist one explicit non-sensitive reference document after safe local extraction."""
        if not confirmed_non_sensitive:
            raise DocumentIngestionError(
                "Document ingestion requires explicit confirmation that the upload contains no sensitive data."
            )
        text, media_type = extract_text(content, filename)
        document = StoredDocument(
            document_id=f"doc_{uuid4().hex[:12]}",
            filename=filename,
            media_type=media_type,
            char_count=len(text),
            sha256=hashlib.sha256(content).hexdigest(),
            created_at=datetime.now(UTC).isoformat(),
            confirmed_non_sensitive=True,
        )
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO ingested_documents
                (document_id, filename, media_type, content, char_count, sha256, created_at, confirmed_non_sensitive)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    document.document_id,
                    document.filename,
                    document.media_type,
                    text,
                    document.char_count,
                    document.sha256,
                    document.created_at,
                    int(document.confirmed_non_sensitive),
                ),
            )
        return document

    def get_metadata(self, document_id: str) -> StoredDocument | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT document_id, filename, media_type, char_count, sha256, created_at, confirmed_non_sensitive
                FROM ingested_documents WHERE document_id = ?
                """,
                (document_id,),
            ).fetchone()
        return StoredDocument(*row[:-1], confirmed_non_sensitive=bool(row[-1])) if row else None

    def get_text_for_internal_use(self, document_id: str) -> str | None:
        """Return stored text only to future reviewed internal task-attachment code, never an API response."""
        with self._connect() as connection:
            row = connection.execute(
                "SELECT content FROM ingested_documents WHERE document_id = ?", (document_id,)
            ).fetchone()
        return str(row[0]) if row else None

    def delete(self, document_id: str) -> bool:
        """Permanently remove one locally stored document, including its extracted text.

        Task attachment records are immutable metadata snapshots and remain in
        their task audit trail.  They contain no extracted document text, so a
        deletion request removes the only stored copy of the document content.
        """
        with self._connect() as connection:
            cursor = connection.execute(
                "DELETE FROM ingested_documents WHERE document_id = ?", (document_id,)
            )
        return cursor.rowcount == 1
