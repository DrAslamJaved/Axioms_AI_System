# Writing & Communication Agent

## Purpose

The agent creates structured, author-reviewable draft frameworks for emails, reports,
paper sections, recommendation letters, grant sections, and public articles. Its writing
standard is clear, precise, approachable, and intellectually rigorous.

## Input contract

- Document type, subject, audience, and purpose
- One to ten key points
- At least one author-verified fact; recommendation letters require at least two
- Optional approved references and delivery context

## Output contract

- Document-type-specific draft sections
- Suggested email subject line where relevant
- Evidence, originality, and author-edit checklists
- JSON through `POST /writing-drafts` and DOCX through `POST /writing-drafts/docx`

## Guardrails

- The agent does not invent facts, citations, results, qualifications, endorsements, or
  institutional decisions.
- A similarity score is only a review signal; it cannot establish originality or replace
  an institutional academic-integrity process.
- Every citation and its associated claim must be verified before final use.
- Recommendation letters must be based on verified factual information.
- The agent does not send, submit, publish, or share drafts. The author must approve each
  final document before external delivery.

