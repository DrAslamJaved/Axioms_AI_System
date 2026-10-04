# Conservative document ingestion

`POST /documents` accepts one PDF, DOCX, or UTF-8 text file as a **local
reference document**. The caller must explicitly confirm that the upload
contains no sensitive personal, student, or confidential data.

The endpoint enforces a 5 MiB upload limit, bounded PDF pages and extracted
text, and DOCX archive expansion checks. It stores only locally extracted text
and returns metadata — identifier, filename, type, size, hash, and timestamp —
never the extracted text itself.

This is deliberately not a RAG or automatic-context feature. Ingested documents
are not attached to tasks, supplied to an LLM, published, shared, or retrieved
through an API. A future, separately reviewed attachment flow must show the
selected document metadata and obtain the applicable human approval before an
agent can use any text as task context.
