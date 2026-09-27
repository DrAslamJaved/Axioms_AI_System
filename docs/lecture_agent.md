# Lecture Design Agent

## Purpose

The agent converts a professor-approved topic and teaching brief into a structured,
reviewable lesson plan. It is intentionally deterministic at this stage: it creates a
pedagogical framework rather than claiming to generate verified mathematical content.

## Input contract

- Topic, course level, audience, and duration (30–240 minutes)
- Two to six observable learning outcomes
- Prior knowledge and an optional real-world application context
- Whether a short Python/NumPy activity is appropriate

## Output contract

- A timed sequence whose minutes sum exactly to the requested duration
- The teaching pattern: opening intuition → formal development → worked example → guided
  application → retrieval/exit check
- Board-work cues, active practice, and an instructor review checklist
- JSON through `POST /lecture-plans` and a DOCX export through
  `POST /lecture-plans/docx`

## Guardrails

- The instructor must verify all subject-matter statements, examples, and references.
- The agent must not process or retain student names, grades, or other personal data.
- DOCX export creates teaching material only; it does not publish, email, or share it.
- Future retrieval and LLM functionality require source provenance, consent, evaluation,
  and explicit owner approval.

