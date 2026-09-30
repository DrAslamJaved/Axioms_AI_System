# Upgrade: Option A — Make it genuinely agentic (v0.2.0)

This branch turns the Axioms AI System from a deterministic template-and-validation
service into a genuinely agentic one, starting with a single, fully auditable
vertical (research), and fixes the correctness/security issues raised in review.
The deterministic system still runs unchanged with **no LLM key required**.

## What "agentic" now means here

A new bounded, logged agent loop (`axioms/research_agent_ai.py`):

1. **Tool use** — for every source with a DOI it calls **Crossref** (a real
   external registry, `axioms/tools.py`) and checks the metadata itself. A
   source the caller left `unverified` is promoted to `metadata_verified` **only
   when Crossref confirms the title**. Wrong titles and "peer-reviewed" flags on
   preprints are flagged as discrepancies, never silently accepted.
2. **Governance gate (unchanged)** — upgraded sources pass through the existing
   `build_research_brief`. Only `claim_verified` sources — a judgement that still
   requires a human, because deciding whether a source *supports a claim* is not
   something a metadata lookup can settle — are eligible for synthesis.
3. **Bounded generation** — when a provider is enabled, the LLM synthesises using
   the verified claims **only**; its prompt is built from those claims, so it
   cannot cite anything it wasn't given. With no provider, this step is skipped
   and the deterministic brief is returned.
4. **Guardrail** — the synthesis is run back through the deterministic AutoEval
   checker to confirm it grounds on the supplied source IDs.

Every tool call, state change, generation, and check is recorded in an ordered
`agent_trace`, so a run can be audited and replayed. The agent performs **no
external action**: the output is a draft held for human approval.

New endpoint: `POST /research-briefs/agentic` (same request body as
`/research-briefs`).

## The LLM seam (the piece that was missing)

`axioms/llm.py` is the single integration point. Nothing else imports an LLM SDK.

- Default `DisabledProvider` — with no config the system behaves exactly as
  before; generative paths raise and callers degrade gracefully.
- `AnthropicProvider` / `OpenAIProvider` — lazily import their SDKs (install with
  `pip install '.[agentic]'`), selected via `AXIOMS_LLM_PROVIDER`.
- `FakeProvider` — deterministic, offline, used across the test suite.

## Issues fixed (from the review)

- **#2 DOCX race / cross-user leak** — every DOCX endpoint wrote to one fixed
  path (`artifacts/lecture_plan.docx`), so concurrent requests could overwrite
  each other. Each request now gets a unique temp file, cleaned up after the
  response (`_docx_response` in `axioms/api.py`).
- **#3 Approval boundary not enforced** — added an API-key dependency
  (`axioms/security.py`) on every state-changing endpoint, and approvals now
  record **who approved** (`approved_by`). `GET /health` reports the auth posture
  truthfully (`open-dev` vs `enabled`) so an unsecured deployment is obvious.
- **#4 Decorative policy** — `axioms/policy.py` now produces a real `RiskTier`
  (low / elevated / high) and an honest decision. Default `strict` mode preserves
  the previous "everything needs approval" behaviour; opt-in `risk_based` mode
  (`AXIOMS_APPROVAL_MODE`) plans low-risk internal drafts directly while keeping
  external/sensitive requests gated. High-risk (sensitive-data) requests are
  marked `blocking`.
- **#7 SQLite concurrency** — WAL journal mode, a 5s busy timeout, and
  `check_same_thread=False` (`axioms/store.py`).
- **#8 Tests skipped the HTTP layer** — `tests/test_http.py` uses `TestClient` to
  cover routing, 422 validation, auth (401), and the streamed DOCX response.
- **#9 Wrong package name** — `pyproject` renamed `axioms-ifrs17` → `axioms-ai-system`.

## Configuration (see `.env.example`)

| Variable | Default | Effect |
| --- | --- | --- |
| `AXIOMS_API_KEY` | *(unset)* | Set to require `X-API-Key` on mutating endpoints. Unset = open dev mode. |
| `AXIOMS_APPROVAL_MODE` | `strict` | `strict` or `risk_based`. |
| `AXIOMS_LLM_PROVIDER` | `disabled` | `disabled`, `anthropic`, or `openai`. |
| `AXIOMS_LLM_MODEL` | *(unset)* | Exact model id for the chosen provider. |
| `CROSSREF_MAILTO` | *(unset)* | Optional contact for Crossref API etiquette. |

## New / changed files

New: `axioms/llm.py`, `axioms/tools.py`, `axioms/research_agent_ai.py`,
`axioms/security.py`; `tests/conftest.py`, `tests/test_llm.py`,
`tests/test_tools.py`, `tests/test_research_agent_ai.py`,
`tests/test_security.py`, `tests/test_http.py`.

Changed: `axioms/api.py`, `axioms/core.py`, `axioms/models.py`,
`axioms/policy.py`, `axioms/store.py`, `pyproject.toml`, `.env.example`,
`tests/test_api.py`.

## Validation

`ruff check .` clean · `pytest` 94 passed · `python scripts/verify_release.py --root .` PASS.

## Suggested next steps (not in this branch)

- Map API keys to real user identities (proper authn/authz) before enabling any
  external action.
- Extend the agentic pattern to the writing agent, and add a live citation tool
  beyond Crossref (e.g. OpenAlex / Semantic Scholar).
- Replace the AutoEval percentage with a checklist status (a number invites
  misreading, as noted in review).
