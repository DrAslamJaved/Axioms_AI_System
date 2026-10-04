# Conservative document ingestion

`POST /documents` accepts one PDF, DOCX, or UTF-8 text file as a **local
reference document**. The caller must explicitly confirm that the upload
contains no sensitive personal, student, or confidential data.

The endpoint enforces a 5 MiB upload limit, bounded PDF pages and extracted
text, and DOCX archive expansion checks. It stores only locally extracted text
and returns metadata — identifier, filename, type, size, hash, and timestamp —
never the extracted text itself.

This is deliberately not a RAG or automatic-context feature. An approver may
attach an ingested document's identifier, filename, type, character count, and
hash to a task **only before execution approval**. The attachment is visible in
the task record and audit trace, and is locked once approval is granted.

An attachment still does not supply extracted text to a specialist agent or an
LLM, and there is no content-retrieval API. A future, separately reviewed
context-use flow must obtain fresh approval before any agent can use document
text as task context.
