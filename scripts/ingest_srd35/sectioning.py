from __future__ import annotations

import re


def sanitize_identifier(value: str) -> str:
    lowered = value.lower()
    normalized = re.sub(r"[^a-z0-9]+", "_", lowered).strip("_")
    return normalized or "unknown"


def _looks_like_heading(line: str) -> bool:
    text = line.strip()
    if not text or len(text) < 3 or len(text) > 90:
        return False
    if text.endswith((".", "!", "?", ";", ",")):
        return False

    words = re.findall(r"[A-Za-z][A-Za-z'/-]*", text)
    if not words or len(words) > 12:
        return False

    heading_like = 0
    for word in words:
        if word.isupper() or word[0].isupper():
            heading_like += 1

    ratio = heading_like / len(words)
    return ratio >= 0.7


def split_sections(file_stem: str, text: str) -> list[dict]:
    lines = [line.strip() for line in text.splitlines()]
    sections: list[dict] = []
    current_title = file_stem
    current_lines: list[str] = []

    def flush() -> None:
        content = "\n".join([line for line in current_lines if line]).strip()
        if not content:
            return
        sections.append(
            {
                "section_title": current_title,
                "section_slug": sanitize_identifier(current_title),
                "content": content,
            }
        )

    for line in lines:
        if not line:
            current_lines.append("")
            continue

        if _looks_like_heading(line):
            flush()
            current_title = line
            current_lines = []
            continue

        current_lines.append(line)

    flush()

    if not sections:
        sections.append(
            {
                "section_title": file_stem,
                "section_slug": sanitize_identifier(file_stem),
                "content": text.strip(),
            }
        )
    return sections
