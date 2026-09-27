# Research Agent

## Purpose

The Research Agent is an evidence-first workspace for literature synthesis and citation
auditing. Its current deterministic core accepts author-entered source records and makes
their verification status visible before any synthesis is attempted.

## Workflow

1. State the research question and scope.
2. Record each source with bibliographic metadata, a source-linked claim, and a verification state.
3. Audit every record.
4. Synthesize only claim-verified records; keep all other claims in the verification queue.
5. Review the evidence ledger and approve any resulting research output.

## Verification states

| State | Meaning | Eligible for factual synthesis? |
| --- | --- | --- |
| `unverified` | Record was entered but has not been checked. | No |
| `metadata_verified` | Bibliographic metadata was checked. | No |
| `claim_verified` | Metadata and the recorded source-linked claim were checked. | Yes, constrained to that claim |
| `rejected` | Record is unsuitable or incorrect. | No |

## Current outputs

- Source audit and verification queue
- Constrained-synthesis boundary
- DOCX evidence ledger (`POST /research-briefs/docx`)
- BibTeX export limited to metadata-verified and claim-verified records (`POST /research-briefs/bibtex`)

## Deliberate limitations

- DOI format validation is not DOI verification. A human or an approved external verifier
  must check the DOI and record the evidence.
- The agent does not yet retrieve from ArXiv, Semantic Scholar, PubMed, Crossref, or Google
  Scholar. Those connectors require a source-specific credential, request budget, caching,
  provenance manifest, and tests.
- A preprint is never treated as peer reviewed merely because it is discoverable online.
- No source, claim, result, dataset, or research direction is fabricated by this agent.

