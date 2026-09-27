# Personal Knowledge Base Governance

## Implemented scope

The Personal Knowledge Base stores only owner-approved preferences in four categories: teaching
style, research voice, content brand, and recurring templates. Explicit feedback can be recorded
against an agent and artifact reference. Feedback never creates or modifies a preference by itself.

Every preference begins as a pending proposal. Only an explicit approval creates or replaces the
corresponding KB entry. Rejection keeps the proposal audit record but makes no KB change.

## Safety boundary

- Student and personal-identifying information are rejected from feedback and KB proposals.
- No preference is inferred from comments, edits, ratings, or agent output.
- No implicit edit tracking, weighted-rule decay, style extraction, or semantic retrieval is
  enabled in this MVP.
- KB records do not grant permission for public delivery, scheduling, publishing, account access,
  or any external action.

## Deferred work

Safe bootstrapping from existing materials requires consent, item-level provenance, retention and
deletion controls, review of extracted candidates, and evaluation for unwanted style or privacy
effects. Those prerequisites must be completed in a separate phase before automated extraction or
retrieval can be enabled.
