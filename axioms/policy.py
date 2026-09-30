"""Risk-based approval policy.

The MVP's policy function returned ``requires_approval=True`` on every branch:
the keyword sets computed a differing *reason* but never a differing *decision*,
so the classification was decorative and one branch was dead code.

This version produces a real :class:`~axioms.models.RiskTier` classification and
an honest decision, in two modes:

* ``strict`` (the default): every draft still requires an approval checkpoint,
  exactly as before -- but the tier now carries genuine information (a request
  touching student data is ``HIGH`` and blocking, an external delivery is
  ``ELEVATED``, a private draft is ``LOW``).
* ``risk_based``: low-risk internal drafts are ``PLANNED`` immediately, while
  external and sensitive requests remain gated. This is opt-in via
  ``AXIOMS_APPROVAL_MODE`` so the conservative posture stays the default and no
  safety behaviour changes silently.

``HIGH`` (sensitive-data) requests are marked ``blocking``: approval alone is not
enough; the data governance issue must be resolved first.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from axioms.models import RiskTier, TaskRequest

STRICT_MODE = "strict"
RISK_BASED_MODE = "risk_based"

EXTERNAL_KEYWORDS = {"publish", "post", "send", "submit", "schedule", "upload", "email"}
SENSITIVE_KEYWORDS = {"student", "grade", "marks", "roll number", "cnic"}


@dataclass(frozen=True, slots=True)
class PolicyDecision:
    requires_approval: bool
    risk_tier: RiskTier
    reason: str
    blocking: bool = False


def _mode(explicit: str | None) -> str:
    mode = (explicit or os.getenv("AXIOMS_APPROVAL_MODE", STRICT_MODE)).strip().casefold()
    return mode if mode in {STRICT_MODE, RISK_BASED_MODE} else STRICT_MODE


def assess_request(request: TaskRequest, *, mode: str | None = None) -> PolicyDecision:
    """Classify a request into a risk tier and decide whether it needs approval."""

    text = request.goal.casefold()
    if any(keyword in text for keyword in SENSITIVE_KEYWORDS):
        return PolicyDecision(
            requires_approval=True,
            risk_tier=RiskTier.HIGH,
            reason="Sensitive educational or personal data requires human review before any use.",
            blocking=True,
        )
    if request.external_delivery or any(keyword in text for keyword in EXTERNAL_KEYWORDS):
        return PolicyDecision(
            requires_approval=True,
            risk_tier=RiskTier.ELEVATED,
            reason="External delivery is disabled until the owner approves it.",
        )
    if _mode(mode) == RISK_BASED_MODE:
        return PolicyDecision(
            requires_approval=False,
            risk_tier=RiskTier.LOW,
            reason="Low-risk internal draft: planned directly, with a checkpoint before external use.",
        )
    return PolicyDecision(
        requires_approval=True,
        risk_tier=RiskTier.LOW,
        reason="Strict mode: all drafts require a human approval checkpoint.",
    )
