import re
from dataclasses import dataclass, field
from typing import Protocol

from app.retrieval.evidence import is_low_value_chunk


class PageLike(Protocol):
    page_number: int
    text: str


@dataclass(frozen=True)
class Chunk:
    chunk_index: int
    content: str
    page_start: int
    page_end: int
    token_count: int
    metadata: dict = field(default_factory=dict)


def chunk_document_pages(
    pages,
    target_tokens: int = 1000,
    overlap_tokens: int = 150,
) -> list[Chunk]:
    if target_tokens <= 0:
        raise ValueError("target_tokens must be greater than zero.")
    if overlap_tokens < 0:
        raise ValueError("overlap_tokens cannot be negative.")
    if overlap_tokens >= target_tokens:
        raise ValueError("overlap_tokens must be smaller than target_tokens.")

    tokens = _page_tokens(pages)
    if not tokens:
        return []

    chunks: list[Chunk] = []
    start = 0

    while start < len(tokens):
        end = min(start + target_tokens, len(tokens))
        chunk_tokens = tokens[start:end]
        content = _normalize_whitespace(" ".join(token for token, _page_number in chunk_tokens))

        if content:
            page_numbers = [page_number for _token, page_number in chunk_tokens]
            chunks.append(
                Chunk(
                    chunk_index=len(chunks),
                    content=content,
                    page_start=min(page_numbers),
                    page_end=max(page_numbers),
                    token_count=_estimate_tokens(content),
                    metadata={
                        "target_tokens": target_tokens,
                        "overlap_tokens": overlap_tokens,
                        "token_estimator": "word_count_div_0.75",
                        "low_value": is_low_value_chunk(content),
                    },
                )
            )

        if end == len(tokens):
            break

        start = max(end - overlap_tokens, start + 1)

    return chunks


def _page_tokens(pages: list[PageLike]) -> list[tuple[str, int]]:
    tokens: list[tuple[str, int]] = []

    for page in sorted(pages, key=lambda item: item.page_number):
        text = _normalize_whitespace(page.text)
        if not text:
            continue
        tokens.extend((token, page.page_number) for token in text.split())

    return tokens


def _estimate_tokens(text: str) -> int:
    word_count = len(text.split())
    return max(1, int(word_count / 0.75))


def _normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()
