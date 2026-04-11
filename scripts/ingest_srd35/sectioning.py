from __future__ import annotations

import re


def sanitize_identifier(value: str) -> str:
    lowered = value.lower()
    normalized = re.sub(r"[^a-z0-9]+", "_", lowered).strip("_")
    return normalized or "unknown"


def looks_like_heading(line: str) -> bool:
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

    return (heading_like / len(words)) >= 0.7


def split_sections_from_blocks(file_stem: str, blocks: list[dict]) -> list[dict]:
    sections: list[dict] = []
    current_title = file_stem
    current_blocks: list[str] = []

    def flush() -> None:
        content = "\n".join([line for line in current_blocks if line]).strip()
        if not content:
            return
        sections.append(
            {
                "section_title": current_title,
                "section_slug": sanitize_identifier(current_title),
                "content": content,
            }
        )

    for block in blocks:
        text = block.get("text", "").strip()
        block_type = block.get("block_type", "paragraph")
        if not text:
            continue
        if block_type == "heading":
            flush()
            current_title = text
            current_blocks = []
            continue
        current_blocks.append(text)

    flush()

    if not sections:
        fallback_content = "\n".join(
            block.get("text", "").strip() for block in blocks if block.get("text", "").strip()
        ).strip()
        sections.append(
            {
                "section_title": file_stem,
                "section_slug": sanitize_identifier(file_stem),
                "content": fallback_content,
            }
        )
    return sections


def split_sections(file_stem: str, text: str) -> list[dict]:
    blocks = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        block_type = "heading" if looks_like_heading(stripped) else "paragraph"
        blocks.append({"text": stripped, "block_type": block_type})
    return split_sections_from_blocks(file_stem, blocks)
