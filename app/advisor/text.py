import re
from typing import Any


def normalize_text_field(value: Any) -> str:
    """Normalize provider text fields without damaging citation labels."""
    if value is None:
        return ""

    if isinstance(value, str):
        text = _repair_character_lines(value)
    elif isinstance(value, list):
        raw_items = [str(item) for item in value if item is not None]
        if _looks_like_character_list(raw_items):
            text = "".join(raw_items)
        else:
            items = [normalize_text_field(item) for item in raw_items]
            non_empty_items = [item for item in items if item]
            text = " ".join(non_empty_items)
    else:
        text = str(value)

    text = _collapse_whitespace(text)
    return _remove_repeated_compressed_text(text)


def _repair_character_lines(text: str) -> str:
    lines = text.splitlines()
    if not _looks_like_character_list(lines):
        return text
    return "".join(lines)


def _looks_like_character_list(values: list[str]) -> bool:
    if len(values) < 12:
        return False
    meaningful_values = [value for value in values if value != ""]
    if len(meaningful_values) < 12:
        return False
    single_character_values = sum(1 for value in meaningful_values if len(value.strip()) <= 1)
    return single_character_values / len(meaningful_values) >= 0.75


def _collapse_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _remove_repeated_compressed_text(text: str) -> str:
    if len(text) < 80:
        return text

    midpoint = len(text) // 2
    first_half = text[:midpoint].strip()
    second_half = text[midpoint:].strip()
    if first_half and _compressed(first_half) == _compressed(second_half):
        return first_half

    sentences = re.split(r"(?<=[.!?])\s+", text)
    if len(sentences) >= 4 and len(sentences) % 2 == 0:
        half = len(sentences) // 2
        first = " ".join(sentences[:half]).strip()
        second = " ".join(sentences[half:]).strip()
        if first and _compressed(first) == _compressed(second):
            return first

    return text


def _compressed(text: str) -> str:
    return re.sub(r"\W+", "", text).lower()
