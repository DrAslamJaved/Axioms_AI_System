"""Deterministic, review-first writing and communication agent for the Axioms MVP."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum
from pathlib import Path

from docx import Document


class DocumentType(StrEnum):
    EMAIL = "email"
    REPORT = "report"
    PAPER_SECTION = "paper_section"
    RECOMMENDATION_LETTER = "recommendation_letter"
    GRANT_SECTION = "grant_section"
    PUBLIC_ARTICLE = "public_article"


@dataclass(frozen=True, slots=True)
class WritingRequest:
    document_type: DocumentType
    subject: str
    audience: str
    purpose: str
    key_points: tuple[str, ...]
    verified_facts: tuple[str, ...]
    tone: str = "clear, precise, approachable, and intellectually rigorous"
    references: tuple[str, ...] = ()
    external_delivery: bool = False

    def validate(self) -> None:
        if not self.subject.strip() or not self.audience.strip() or not self.purpose.strip():
            raise ValueError("Subject, audience, and purpose are required.")
        if not 1 <= len(self.key_points) <= 10:
            raise ValueError("Provide between one and ten key points.")
        if not self.verified_facts:
            raise ValueError("Provide at least one verified fact or explicitly verified source detail.")
        if any(not item.strip() for item in self.key_points + self.verified_facts):
            raise ValueError("Key points and verified facts cannot be blank.")
        if self.document_type is DocumentType.RECOMMENDATION_LETTER and len(self.verified_facts) < 2:
            raise ValueError("Recommendation letters require at least two verified facts.")


@dataclass(frozen=True, slots=True)
class DraftSection:
    heading: str
    content: str


@dataclass(frozen=True, slots=True)
class WritingDraft:
    request: WritingRequest
    sections: tuple[DraftSection, ...]
    subject_line: str | None
    evidence_checklist: tuple[str, ...]
    originality_checklist: tuple[str, ...]
    suggested_edits: tuple[str, ...]
    approval_required: bool = True

    def to_dict(self) -> dict:
        return asdict(self)

    def to_markdown(self) -> str:
        sections = "\n\n".join(f"## {section.heading}\n{section.content}" for section in self.sections)
        evidence = "\n".join(f"- [ ] {item}" for item in self.evidence_checklist)
        originality = "\n".join(f"- [ ] {item}" for item in self.originality_checklist)
        edits = "\n".join(f"- {item}" for item in self.suggested_edits)
        subject_line = f"**Suggested subject:** {self.subject_line}\n\n" if self.subject_line else ""
        return f"""# Draft: {self.request.subject}

{subject_line}{sections}

## Evidence review before use
{evidence}

## Originality review before use
{originality}

## Suggested author edits
{edits}
"""


def _bullets(items: tuple[str, ...]) -> str:
    return "\n".join(f"- {item}" for item in items)


def _draft_sections(request: WritingRequest) -> tuple[DraftSection, ...]:
    facts = _bullets(request.verified_facts)
    points = _bullets(request.key_points)
    if request.document_type is DocumentType.EMAIL:
        return (
            DraftSection("Opening", f"Dear {request.audience},\n\nI am writing regarding {request.subject}. {request.purpose}"),
            DraftSection("Key message", points),
            DraftSection("Verified details", facts),
            DraftSection("Closing", "Please review the verified details above and let me know the appropriate next step.\n\nKind regards,"),
        )
    if request.document_type is DocumentType.RECOMMENDATION_LETTER:
        return (
            DraftSection("Purpose", f"I am pleased to provide this recommendation in support of {request.subject}."),
            DraftSection("Verified basis", facts),
            DraftSection("Assessment framework", f"The recommendation should address the following verified strengths or achievements:\n{points}"),
            DraftSection("Closing", "The author must review every statement for accuracy, context, and fairness before signing."),
        )
    if request.document_type is DocumentType.PAPER_SECTION:
        return (
            DraftSection("Section purpose", request.purpose),
            DraftSection("Author-verified foundation", facts),
            DraftSection("Proposed argument sequence", points),
            DraftSection("Evidence placeholders", "Insert only checked citations and clearly distinguish established findings, assumptions, methods, and limitations."),
            DraftSection("Transition", "Conclude by linking the verified argument to the next section without overstating novelty or results."),
        )
    if request.document_type is DocumentType.GRANT_SECTION:
        return (
            DraftSection("Objective", request.purpose),
            DraftSection("Verified context", facts),
            DraftSection("Proposed case", points),
            DraftSection("Feasibility and evaluation", "Specify measurable deliverables, responsible parties, risks, and evaluation criteria using author-verified information."),
        )
    if request.document_type is DocumentType.PUBLIC_ARTICLE:
        return (
            DraftSection("Opening", f"{request.purpose} The following points should guide a concise public explanation."),
            DraftSection("Core message", points),
            DraftSection("Verified details", facts),
            DraftSection("Closing", "Add a proportionate call to action only after the author confirms the audience, platform, and publication approval."),
        )
    return (
        DraftSection("Purpose", request.purpose),
        DraftSection("Verified context", facts),
        DraftSection("Key points", points),
        DraftSection("Recommended action", "Turn the approved key points into a clear action, decision, or next-step statement."),
    )


def build_writing_draft(request: WritingRequest) -> WritingDraft:
    """Build an auditable draft framework without inventing facts, citations, or results."""
    request.validate()
    subject_line = f"Regarding: {request.subject}" if request.document_type is DocumentType.EMAIL else None
    evidence_checklist = [
        "Confirm every factual statement against its source or an approved record.",
        "Replace all generic or placeholder language with author-reviewed context.",
        "Verify names, roles, dates, figures, and institutional details before delivery.",
    ]
    if request.references:
        evidence_checklist.append("Verify every cited source and its claim before retaining it in the final text.")
    originality_checklist = (
        "Run the institutionally approved similarity-review process where required.",
        "Treat any similarity score as a review signal, not proof of originality.",
        "Rewrite or cite any passage that relies too closely on a source.",
    )
    suggested_edits = (
        f"Adjust the register for {request.audience} while retaining the selected tone.",
        "Add only evidence that has been checked and can be defended by the author.",
        "Approve the final text before sending, submitting, publishing, or sharing it externally.",
    )
    return WritingDraft(
        request=request,
        sections=_draft_sections(request),
        subject_line=subject_line,
        evidence_checklist=tuple(evidence_checklist),
        originality_checklist=originality_checklist,
        suggested_edits=suggested_edits,
    )


def export_docx(draft: WritingDraft, destination: Path) -> Path:
    """Export a draft for author review. No external delivery happens here."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    document = Document()
    document.add_heading(draft.request.subject, level=0)
    document.add_paragraph(f"Document type: {draft.request.document_type.value.replace('_', ' ').title()}")
    document.add_paragraph(f"Audience: {draft.request.audience}")
    if draft.subject_line:
        document.add_heading("Suggested subject", level=1)
        document.add_paragraph(draft.subject_line)
    for section in draft.sections:
        document.add_heading(section.heading, level=1)
        document.add_paragraph(section.content)
    document.add_heading("Evidence review before use", level=1)
    for item in draft.evidence_checklist:
        document.add_paragraph(item, style="List Bullet")
    document.add_heading("Originality review before use", level=1)
    for item in draft.originality_checklist:
        document.add_paragraph(item, style="List Bullet")
    document.add_heading("Suggested author edits", level=1)
    for item in draft.suggested_edits:
        document.add_paragraph(item, style="List Bullet")
    document.save(destination)
    return destination

