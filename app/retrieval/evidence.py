import re


_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "how",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "should",
    "that",
    "the",
    "to",
    "what",
    "when",
    "where",
    "which",
    "who",
    "why",
    "with",
}


def is_low_value_chunk(text: str) -> bool:
    normalized = " ".join(text.split())
    if not normalized:
        return True

    word_count = len(_keywords(normalized, include_stopwords=True))
    sentence_count = len(_split_sentences(normalized))
    dot_ratio = normalized.count(".") / max(1, len(normalized))
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    page_number_lines = sum(1 for line in lines if re.search(r"(?:\.{2,}|\s)\d{1,4}$", line))
    short_lines = sum(1 for line in lines if len(line.split()) <= 8)

    starts_with_contents = normalized.lower().startswith(("contents", "table of contents"))
    has_section_listing_terms = len(re.findall(r"\b(?:chapter|section|appendix|executive summary|overview)\b", normalized.lower()))
    has_sentence_like_content = sentence_count > 0 and word_count >= 4

    if word_count < 8 and not has_sentence_like_content:
        return True
    if dot_ratio > 0.08:
        return True
    if len(lines) >= 4 and page_number_lines / len(lines) >= 0.5 and short_lines / len(lines) >= 0.5:
        return True
    if starts_with_contents and (page_number_lines >= 2 or has_section_listing_terms >= 3):
        return True
    if starts_with_contents and word_count < 80 and sentence_count <= 1:
        return True
    if sentence_count == 0 and word_count < 40:
        return True

    return False


def extract_relevant_excerpt(chunk_text: str, query: str, max_chars: int = 500) -> str:
    normalized_text = " ".join(chunk_text.split())
    if not normalized_text:
        return ""

    sentences = _split_sentences(normalized_text)
    if not sentences:
        return normalized_text[:max_chars].strip()

    query_terms = set(_keywords(query))
    if not query_terms:
        return normalized_text[:max_chars].strip()

    scores = [_sentence_score(sentence, query_terms) for sentence in sentences]
    best_index = max(range(len(sentences)), key=lambda index: scores[index])
    if scores[best_index] <= 0:
        return normalized_text[:max_chars].strip()

    start = best_index
    end = best_index + 1

    while start > 0 and end - start < 4:
        candidate = " ".join(sentences[start - 1 : end])
        if len(candidate) > max_chars:
            break
        start -= 1

    while end < len(sentences) and end - start < 4:
        candidate = " ".join(sentences[start : end + 1])
        if len(candidate) > max_chars:
            break
        end += 1

    excerpt = " ".join(sentences[start:end]).strip()
    if len(excerpt) <= max_chars:
        return excerpt

    return _excerpt_window(sentences[best_index], query_terms, max_chars)


def relevance_reason(excerpt: str, query: str) -> str | None:
    query_terms = set(_keywords(query))
    excerpt_terms = set(_keywords(excerpt))
    overlap = sorted(query_terms & excerpt_terms)
    if not overlap:
        return None
    return "Matched query terms: " + ", ".join(overlap[:6])


def _excerpt_window(text: str, query_terms: set[str], max_chars: int) -> str:
    lowered = text.lower()
    match_positions = [
        lowered.find(term)
        for term in query_terms
        if lowered.find(term) >= 0
    ]
    if not match_positions:
        return text[:max_chars].strip()

    center = min(match_positions)
    start = max(0, center - max_chars // 4)
    end = min(len(text), start + max_chars)
    if end - start < max_chars:
        start = max(0, end - max_chars)

    excerpt = text[start:end].strip()
    if start > 0:
        excerpt = "... " + excerpt
    if end < len(text):
        excerpt = excerpt + " ..."
    return excerpt


def _sentence_score(sentence: str, query_terms: set[str]) -> int:
    sentence_terms = set(_keywords(sentence))
    return len(sentence_terms & query_terms)


def _split_sentences(text: str) -> list[str]:
    return [
        sentence.strip()
        for sentence in re.split(r"(?<=[.!?])\s+", text)
        if sentence.strip()
    ]


def _keywords(text: str, include_stopwords: bool = False) -> list[str]:
    words = [word.lower() for word in re.findall(r"[A-Za-z][A-Za-z0-9_-]*", text)]
    if include_stopwords:
        return words
    return [word for word in words if len(word) > 2 and word not in _STOPWORDS]
