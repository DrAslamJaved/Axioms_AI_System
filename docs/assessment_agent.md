# Assessment Design Agent

## Purpose

The Assessment Design Agent creates instructor-facing, source-bounded assessment blueprints.
It aligns question frameworks to learning outcomes, Bloom levels, difficulty, marks, and
an explicit academic-integrity review before any student release.

## Inputs

- Topic, course level, assessment type, duration, marks, and question count
- Measurable learning outcomes with Bloom levels
- Instructor-approved course-source scope
- Difficulty mix and optional integrity controls

## Outputs

- Mark-balanced assessment blueprint with an explicit outcome/Bloom/difficulty map
- Instructor rubric and qualitative AI-resilience review
- Student DOCX without answers, rubrics, or solution guides
- Instructor DOCX with blueprint, rubric, review, and quality checks

## Guardrails

- The current agent generates question frameworks, not unreviewed live exam questions or
  mathematical answers. The instructor inserts and verifies final item content from the
  approved source scope.
- Student-facing exports never contain rubrics, answers, or solution guides.
- AI-resilience is a qualitative design review, not a guarantee that an item is AI-proof.
- Assessment data is session-scoped; no student names, grades, submissions, or personal
  data are stored.
- No assessment is printed, uploaded to an LMS, released, graded, or sent without instructor approval.

