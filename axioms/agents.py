from __future__ import annotations

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
