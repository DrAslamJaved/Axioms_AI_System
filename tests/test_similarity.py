import pytest

from axioms.similarity import ComparisonText, SimilarityRequest, screen_similarity, text_hash


def test_similarity_screen_flags_strong_overlap_and_uses_hashes_only() -> None:
    report = screen_similarity(
        SimilarityRequest(
            submitted_text="Fuzzy similarity supports transparent drug target interaction ranking.",
            comparison_texts=(
                ComparisonText(
                    "source_a",
                    "Fuzzy similarity supports transparent drug target interaction ranking.",
                ),
                ComparisonText("source_b", "Spectral graph theory studies eigenvalues of graph matrices."),
            ),
            review_threshold=0.5,
        )
    )
    assert report.matches[0].reference_id == "source_a"
    assert report.matches[0].jaccard_similarity == 1.0
    assert report.matches[0].review_required
    assert report.matches[0].reference_hash == text_hash(
        "Fuzzy similarity supports transparent drug target interaction ranking."
    )
    assert "plagiarism finding" in report.screening_boundary


def test_similarity_screen_handles_short_and_disjoint_texts() -> None:
    report = screen_similarity(
        SimilarityRequest(
            submitted_text="Graph theory",
            comparison_texts=(ComparisonText("other", "Fuzzy sets"),),
            shingle_size=3,
        )
    )
    assert report.matches[0].jaccard_similarity == 0.0
    assert not report.matches[0].review_required


def test_similarity_screen_rejects_bad_comparison_contract() -> None:
    with pytest.raises(ValueError, match="unique"):
        screen_similarity(
            SimilarityRequest(
                submitted_text="A sufficiently long submitted text.",
                comparison_texts=(ComparisonText("same", "first"), ComparisonText("same", "second")),
            )
        )
    with pytest.raises(ValueError, match="between 1 and 8"):
        SimilarityRequest(
            submitted_text="A sufficiently long submitted text.",
            comparison_texts=(ComparisonText("one", "comparison text"),),
            shingle_size=9,
        ).validate()
