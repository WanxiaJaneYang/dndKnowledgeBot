from __future__ import annotations

import re

from .sectioning import looks_like_heading

_LIST_ITEM_PATTERN = re.compile(r"^(\d+[\.\)]|[-*])\s+")


def classify_block_type(line: str) -> str:
    text = line.strip()
    if not text:
        return "empty"
    if " | " in text:
        return "table_row"
    if _LIST_ITEM_PATTERN.match(text):
        return "list_item"
    if looks_like_heading(text):
        return "heading_candidate"
    return "paragraph"


def build_extraction_ir(*, file_name: str, text: str) -> dict:
    blocks: list[dict] = []
    line_number = 0
    for raw_line in text.splitlines():
        line_number += 1
        stripped = raw_line.strip()
        if not stripped:
            continue
        block_type = classify_block_type(stripped)
        blocks.append(
            {
                "block_id": f"b{len(blocks) + 1:04d}",
                "block_type": block_type,
                "text": stripped,
                "line_start": line_number,
                "line_end": line_number,
            }
        )
    return {
        "ir_version": "1.0",
        "file_name": file_name,
        "blocks": blocks,
    }
