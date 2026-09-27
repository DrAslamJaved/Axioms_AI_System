# AutoEval Agent

## Purpose

The AutoEval Agent provides a transparent, deterministic quality-assurance layer for draft
deliverables produced by the Axioms AI System. It records what was checked, what was missing, and
the SHA-256 identity of the supplied artifact so a human reviewer can repeat the same check.

## Inputs and outputs

- Inputs: evaluated agent, deliverable title, artifact text, required text markers, optional
  evidence markers, public-facing flag, and a sensitive-data declaration.
- Outputs: deterministic check results, found and missing markers, SHA-256 audit identity, a
  review-signal percentage, review boundary, and DOCX export.

## Explicit limits

- AutoEval performs lexical contract checks only. It does not verify factual accuracy, citations,
  originality, accessibility, pedagogy, legal compliance, or release suitability.
- Evidence-marker presence means only that supplied text occurs in the artifact; it is not source
  verification.
- A declared sensitive-data flag blocks release review. A negative declaration is not an
  independent privacy scan.
- Public-facing deliverables always require explicit human approval.
- Scores are review signals, never automatic pass/fail decisions.
- The agent cannot approve output, reconfigure other agents, modify artifacts, publish, schedule,
  message, or make any external system change.
