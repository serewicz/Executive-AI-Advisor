from app.retrieval.evidence import extract_relevant_excerpt


def test_relevant_excerpt_is_shorter_than_full_chunk_and_matches_query_terms():
    chunk_text = (
        "This introductory paragraph discusses company history and market background. "
        + "x " * 300
        + "Security governance gaps create access control risk for the board. "
        "Privileged access reviews are inconsistent and should be monitored. "
        "The final paragraph discusses unrelated hiring plans."
    )

    excerpt = extract_relevant_excerpt(chunk_text, "security governance access risk", max_chars=500)

    assert len(excerpt) < len(chunk_text)
    assert "Security governance" in excerpt
    assert "access control risk" in excerpt
