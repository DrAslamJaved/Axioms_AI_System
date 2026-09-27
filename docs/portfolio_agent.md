# STEM AI Portfolio Agent

## Purpose

The STEM AI Portfolio Agent turns author-provided, verified research evidence into a reviewable
portfolio case-study blueprint. It prepares the documentation and reproducibility plan needed to
make a project understandable to academic and industry audiences without pretending that a
repository, demo, or research result already exists.

## Inputs and outputs

- Inputs: project title, research summary, audience, proposed repository visibility,
  author-verified claims with source references, dataset assets, and optional demo/notebook plans.
- Outputs: repository structure, README plan, reproducibility checklist, evidence-bound impact
  summary, publication checks, and DOCX export.

## Guardrails

- Every public-facing project claim must be supplied as a verified evidence record with a source
  reference. The agent does not infer novelty, impact, performance, citation, GitHub-star, or
  publication outcomes.
- Public repository plans reject proprietary, restricted, and unknown-access assets. Public or
  de-identified data also require a licence or permission statement and attribution.
- Reproducibility plans require pinned dependencies, deterministic controls, tests, documented
  data provenance, and stated limitations.
- API keys, credentials, student information, unpublished results, and non-public datasets must
  never appear in a public portfolio package.
- The agent cannot create, modify, push to, or publish GitHub repositories. Explicit human
  approval is required before any external repository action.
