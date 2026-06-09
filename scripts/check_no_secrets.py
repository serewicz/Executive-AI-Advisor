"""Lightweight tracked-file secret scanner for local pre-commit checks."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
IGNORED_PATHS = {".env.example"}
IGNORED_SUFFIXES = {".pyc", ".png", ".jpg", ".jpeg", ".gif", ".pdf", ".sqlite"}
KEY_TOKEN_PATTERNS = [
    re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"\bsk-ant-[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"\bxai-[A-Za-z0-9_-]{20,}\b"),
]
ENV_ASSIGNMENT_PATTERN = re.compile(r"^(OPENAI_API_KEY|ANTHROPIC_API_KEY|XAI_API_KEY)=(.+)$")
SAFE_PLACEHOLDERS = {"", '""', "''", "<key>", "your_key_here", "change_me", "placeholder"}


def _tracked_files() -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return [ROOT / line.strip() for line in result.stdout.splitlines() if line.strip()]


def _is_ignored(path: Path) -> bool:
    relative = path.relative_to(ROOT).as_posix()
    return relative in IGNORED_PATHS or path.suffix.lower() in IGNORED_SUFFIXES


def _scan_file(path: Path) -> list[str]:
    if _is_ignored(path):
        return []
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return []

    findings = []
    relative = path.relative_to(ROOT).as_posix()
    for pattern in KEY_TOKEN_PATTERNS:
        if pattern.search(text):
            findings.append(f"{relative}: key-like token matched {pattern.pattern}")

    for line_number, line in enumerate(text.splitlines(), start=1):
        match = ENV_ASSIGNMENT_PATTERN.match(line.strip())
        if not match:
            continue
        value = match.group(2).strip()
        if value not in SAFE_PLACEHOLDERS:
            findings.append(f"{relative}:{line_number}: non-empty {match.group(1)} assignment")
    return findings


def main() -> int:
    findings = []
    for path in _tracked_files():
        findings.extend(_scan_file(path))

    if findings:
        print("Potential secrets found:")
        for finding in findings:
            print(f"- {finding}")
        return 1

    print("No tracked API keys or secret-like tokens found.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
