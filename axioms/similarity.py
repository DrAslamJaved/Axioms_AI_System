"""Transparent local similarity screening for review, not plagiarism adjudication."""

from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass

_TOKEN = re.compile(r"[a-z0-9]+")


def _tokens(text: str) -> list[str]:
    return _TOKEN.findall(text.casefold())


def _shingles(text: str, size: int) -> set[tuple[str, ...]]:
    tokens = _tokens(text)
    if len(tokens) < size:
        return {tuple(tokens)} if tokens else set()
    return {tuple(tokens[index : index + size]) for index in range(len(tokens) - size + 1)}


def text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class ComparisonText:
    reference_id: str
    text: str

    def validate(self) -> None:
        if not self.reference_id.strip() or not self.text.strip():
            raise ValueError("Each comparison text needs a reference ID and non-blank text.")


@dataclass(frozen=True, slots=True)
class SimilarityRequest:
    submitted_text: str
    comparison_texts: tuple[ComparisonText, ...]
    shingle_size: int = 3
    review_threshold: float = 0.2

    def validate(self) -> None:
        if not self.submitted_text.strip():
            raise ValueError("Similarity screening needs submitted text.")
        if not self.comparison_texts:
            raise ValueError("Provide at least one comparison text for screening.")
        if not 1 <= self.shingle_size <= 8:
            raise ValueError("Shingle size must be between 1 and 8.")
        if not 0.0 <= self.review_threshold <= 1.0:
            raise ValueError("Review threshold must be between 0 and 1.")
        reference_ids = [item.reference_id for item in self.comparison_texts]
        if len(reference_ids) != len(set(reference_ids)):
            raise ValueError("Comparison reference IDs must be unique.")
        for item in self.comparison_texts:
            item.validate()


@dataclass(frozen=True, slots=True)
class SimilarityMatch:
    reference_id: str
    reference_hash: str
    jaccard_similarity: float
    shared_shingle_count: int
    review_required: bool


@dataclass(frozen=True, slots=True)
class SimilarityReport:
    submitted_hash: str
    shingle_size: int
    review_threshold: float
    matches: tuple[SimilarityMatch, ...]
    screening_boundary: str = (
        "This is a local lexical-similarity screen against only the supplied comparison texts. "
        "It is not a plagiarism finding, an originality determination, or a web-wide search. "
        "A human reviewer must inspect every flagged overlap and record the academic decision."
    )

    def to_dict(self) -> dict:
        return asdict(self)


def screen_similarity(request: SimilarityRequest) -> SimilarityReport:
    """Compute Jaccard overlap over normalized token shingles without retaining text."""
    request.validate()
    submitted = _shingles(request.submitted_text, request.shingle_size)
    matches: list[SimilarityMatch] = []
    for candidate in request.comparison_texts:
        reference = _shingles(candidate.text, request.shingle_size)
        union = submitted | reference
        shared = submitted & reference
        score = len(shared) / len(union) if union else 0.0
        matches.append(
            SimilarityMatch(
                reference_id=candidate.reference_id,
                reference_hash=text_hash(candidate.text),
                jaccard_similarity=round(score, 6),
                shared_shingle_count=len(shared),
                review_required=score >= request.review_threshold,
            )
        )
    matches.sort(key=lambda item: (-item.jaccard_similarity, item.reference_id))
    return SimilarityReport(
        submitted_hash=text_hash(request.submitted_text),
        shingle_size=request.shingle_size,
        review_threshold=request.review_threshold,
        matches=tuple(matches),
    )
