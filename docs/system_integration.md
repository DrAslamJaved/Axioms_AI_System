# System Integration and Readiness

## Implemented integration spine

- Axioms Core routes recognisable requests to all eight specialist profiles.
- `GET /agents` exposes the implemented specialist registry and its typed API endpoint.
- `GET /system/readiness` distinguishes implemented local capabilities from deferred
  infrastructure.
- Every Core hand-off remains review-first and records no external side effect.

## Deliberate deferrals

Redis Streams, semantic retrieval (Chroma/Pinecone), LangGraph, cloud hosting, and live GitHub,
social, research, Moodle, and Overleaf connectors are not enabled. Each needs its own least-
privilege permissions, provenance and retention controls, failure handling, dry-run contract
tests, audit logs, and explicit approval policy.

## Release boundary

This integration layer does not claim production readiness. It provides a single discoverable
system surface and an explicit readiness report so deferred services cannot be mistaken for live
capabilities. Human approval remains required for every public-facing deliverable and all external
actions remain blocked.
