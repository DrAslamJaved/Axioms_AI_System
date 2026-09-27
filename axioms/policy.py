from __future__ import annotations

from dataclasses import dataclass

from axioms.models import TaskRequest


@dataclass(frozen=True, slots=True)
class PolicyDecision:
    requires_approval: bool
    reason: str


EXTERNAL_KEYWORDS = {"publish", "post", "send", "submit", "schedule", "upload", "email"}
SENSITIVE_KEYWORDS = {"student", "grade", "marks", "roll number", "cnic"}


def assess_request(request: TaskRequest) -> PolicyDecision:
    """Apply the MVP's conservative approval rule before any deliverable is released."""
    text = request.goal.casefold()
    if any(keyword in text for keyword in SENSITIVE_KEYWORDS):
        return PolicyDecision(True, "Sensitive educational or personal data requires human review.")
    if request.external_delivery or any(keyword in text for keyword in EXTERNAL_KEYWORDS):
        return PolicyDecision(True, "External delivery is disabled until the owner approves it.")
    return PolicyDecision(True, "All MVP drafts require a human approval checkpoint.")

