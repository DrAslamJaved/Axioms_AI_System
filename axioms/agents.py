from __future__ import annotations

from typing import Any

from axioms.agent_registry import profile_for
from axioms.models import AgentName, Deliverable, TaskRequest


def lecture_draft(request: TaskRequest) -> Deliverable:
    title = f"Lecture planning draft: {request.goal}"
    content = f"""# {title}

## Teaching context
- Audience: {request.audience}
- Deadline: {request.deadline or 'not supplied'}
- Constraints: {', '.join(request.constraints) or 'none supplied'}

## Proposed structure
1. Motivation and a familiar intuition (10 minutes)
2. Formal definitions and notation (15 minutes)
3. Worked example with assumptions stated (20 minutes)
4. Guided practice and discussion (20 minutes)
5. Summary, misconceptions, and follow-up reading (10 minutes)

## Instructor review required
- Verify mathematical statements, examples, and references.
- Adjust timing to the actual class duration.
- Confirm that no student-specific data appears in materials.
"""
    return Deliverable(title=title, agent=AgentName.LECTURE, content=content)


def writing_draft(request: TaskRequest) -> Deliverable:
    title = f"Writing planning draft: {request.goal}"
    content = f"""# {title}

## Purpose and audience
- Audience: {request.audience}
- Deadline: {request.deadline or 'not supplied'}

## Suggested structure
1. Context and objective
2. Main message or contribution
3. Supporting evidence (to be verified by the author)
4. Limitations, assumptions, or next steps
5. Requested action / conclusion

## Verification checklist
- Replace all placeholders with author-verified facts.
- Cite only sources whose metadata and claims have been checked.
- Obtain approval before sending, posting, or submitting externally.
"""
    return Deliverable(title=title, agent=AgentName.WRITING, content=content)


def social_media_draft(request: TaskRequest) -> Deliverable:
    title = f"Social-media planning draft: {request.goal}"
    content = f"""# {title}

## Purpose and audience
- Audience: {request.audience}
- Deadline: {request.deadline or 'not supplied'}

## Proposed review sequence
1. Confirm platform, approved sources, verified facts, and recipient consent where relevant.
2. Prepare platform-native draft copy and accessibility notes.
3. Check the 48-hour same-topic cooldown for each platform.
4. Obtain explicit author approval before any scheduling, upload, sharing, or publication.

## Safety boundary
- This draft does not connect to, schedule, or post through any social account.
- Do not use mass messages, scraping, engagement bait, or unapproved automation.
"""
    return Deliverable(title=title, agent=AgentName.SOCIAL_MEDIA, content=content)


def portfolio_draft(request: TaskRequest) -> Deliverable:
    title = f"STEM AI portfolio planning draft: {request.goal}"
    content = f"""# {title}

## Purpose and audience
- Audience: {request.audience}
- Deadline: {request.deadline or 'not supplied'}

## Proposed review sequence
1. Record author-verified research claims and their source references.
2. Check data access, licence, attribution, and public-release eligibility.
3. Prepare a repository structure, README plan, reproduction steps, and test plan.
4. Obtain explicit approval before any repository creation, push, or visibility change.

## Safety boundary
- This draft does not create, modify, push to, or publish any GitHub repository.
- Do not include API keys, student data, proprietary material, or unverified research claims.
"""
    return Deliverable(title=title, agent=AgentName.PORTFOLIO, content=content)


def autoeval_draft(request: TaskRequest) -> Deliverable:
    title = f"AutoEval planning draft: {request.goal}"
    content = f"""# {title}

## Purpose and audience
- Audience: {request.audience}
- Deadline: {request.deadline or 'not supplied'}

## Proposed review sequence
1. Define required text markers and evidence markers for the target deliverable.
2. Run deterministic contract checks and record the artifact hash.
3. Route every warning, missing marker, or sensitive-data declaration to human review.

## Safety boundary
- Scores are review signals, not proof of factual quality or release readiness.
- AutoEval cannot approve, publish, schedule, reconfigure other agents, or make external changes.
"""
    return Deliverable(title=title, agent=AgentName.AUTOEVAL, content=content)


def specialist_draft(request: TaskRequest, agent: AgentName) -> Deliverable:
    """Create a safe Core hand-off when a specialised endpoint needs typed inputs."""
    profile = profile_for(agent)
    title = f"{profile.label} planning draft: {request.goal}"
    content = f"""# {title}

## Intended specialist
- Capability: {profile.purpose}
- Typed endpoint: `{profile.endpoint}`
- Audience: {request.audience}
- Deadline: {request.deadline or 'not supplied'}

## Required human preparation
1. Supply typed inputs and author-approved source scope.
2. Review factual, data-governance, and release constraints.
3. Obtain explicit approval before any external or public-facing action.

## Safety boundary
- This is a routing hand-off, not a completed specialist deliverable.
- No external action, publication, schedule, account access, or data release is performed.
"""
    return Deliverable(title=title, agent=agent, content=content)


def apply_approved_preferences(draft: Deliverable, preferences: list[dict[str, Any]]) -> Deliverable:
    """Append only owner-approved, task-snapshotted preferences without treating them as facts or instructions to act."""
    if not preferences:
        return draft
    lines = [
        "## Owner-approved preferences (snapshotted at planning)",
        "- Apply these preferences only where relevant to this review draft.",
        "- They are not verified facts and do not override evidence, data-governance, safety, or human-approval requirements.",
    ]
    lines.extend(
        f"- {entry['category']}.{entry['preference_key']}: {entry['preference_value']}"
        for entry in preferences
    )
    draft.content += "\n\n" + "\n".join(lines)
    return draft
