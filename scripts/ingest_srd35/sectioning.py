from __future__ import annotations

import re

MIN_SECTION_BODY_CHARS = 40


def sanitize_identifier(value: str) -> str:
    lowered = value.lower()
    normalized = re.sub(r"[^a-z0-9]+", "_", lowered).strip("_")
    return normalized or "unknown"


def looks_like_heading(line: str) -> bool:
    text = line.strip()
    if not text or len(text) < 3 or len(text) > 90:
        return False
    if text.endswith((".", "!", "?", ";", ",", ":")):
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
    current_block_indices: list[int] = []

    def flush() -> None:
        if not current_block_indices:
            return
        content_lines: list[str] = []
        block_type_counts: dict[str, int] = {}
        for block_index in current_block_indices:
            block = blocks[block_index]
            text = block.get("text", "").strip()
            if not text:
                continue
            content_lines.append(text)
            block_type = block.get("block_type", "paragraph")
            block_type_counts[block_type] = block_type_counts.get(block_type, 0) + 1
        content = "\n".join(content_lines).strip()
        if not content:
            return
        start_index = current_block_indices[0]
        end_index = current_block_indices[-1]
        start_block = blocks[start_index]
        end_block = blocks[end_index]
        sections.append(
            {
                "section_title": current_title,
                "section_slug": sanitize_identifier(current_title),
                "content": content,
                "body_char_count": len(content),
                "block_start_index": start_index,
                "block_end_index": end_index,
                "block_start_id": start_block.get("block_id"),
                "block_end_id": end_block.get("block_id"),
                "block_type_counts": block_type_counts,
            }
        )

    def is_boundary_candidate(index: int) -> bool:
        block = blocks[index]
        if block.get("block_type") != "heading_candidate":
            return False
        next_index = index + 1
        if next_index >= len(blocks):
            return False
        if blocks[next_index].get("block_type") == "heading_candidate":
            return False
        body_chars = 0
        has_paragraph = False
        for look_ahead in blocks[next_index:]:
            look_type = look_ahead.get("block_type", "paragraph")
            if look_type == "heading_candidate":
                break
            if look_type in {"list_item", "table_row"}:
                body_chars += len(look_ahead.get("text", "").strip())
                continue
            if look_type == "paragraph":
                has_paragraph = True
                body_chars += len(look_ahead.get("text", "").strip())
        return has_paragraph and body_chars >= MIN_SECTION_BODY_CHARS

    for index, block in enumerate(blocks):
        text = block.get("text", "").strip()
        if not text:
            continue
        if is_boundary_candidate(index):
            flush()
            current_title = text
            current_block_indices = []
            continue
        current_block_indices.append(index)

    flush()

    if not sections:
        fallback_indices = [index for index, block in enumerate(blocks) if block.get("text", "").strip()]
        fallback_content = "\n".join(blocks[index].get("text", "").strip() for index in fallback_indices).strip()
        block_type_counts: dict[str, int] = {}
        for index in fallback_indices:
            block_type = blocks[index].get("block_type", "paragraph")
            block_type_counts[block_type] = block_type_counts.get(block_type, 0) + 1
        start_index = fallback_indices[0] if fallback_indices else 0
        end_index = fallback_indices[-1] if fallback_indices else 0
        start_block = blocks[start_index] if blocks else {}
        end_block = blocks[end_index] if blocks else {}
        sections.append(
            {
                "section_title": file_stem,
                "section_slug": sanitize_identifier(file_stem),
                "content": fallback_content,
                "body_char_count": len(fallback_content),
                "block_start_index": start_index,
                "block_end_index": end_index,
                "block_start_id": start_block.get("block_id"),
                "block_end_id": end_block.get("block_id"),
                "block_type_counts": block_type_counts,
            }
        )
    return sections


def split_sections(file_stem: str, text: str) -> list[dict]:
    blocks = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        block_type = "heading_candidate" if looks_like_heading(stripped) else "paragraph"
        blocks.append({"text": stripped, "block_type": block_type})
    return split_sections_from_blocks(file_stem, blocks)
