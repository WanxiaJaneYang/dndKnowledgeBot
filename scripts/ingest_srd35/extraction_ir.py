from __future__ import annotations

import re
from collections import Counter

from .sectioning import looks_like_heading
from .text_spans import TextSpan


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


def _normalize_block_text(text: str) -> str:
    """Whitespace normalization within a block (mirrors decoder's full-text pass)."""
    text = text.replace("\r", "\n")
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n[ \t]+", "\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text.strip()


def _summarize_block(spans_in_block: list[TextSpan]) -> tuple[int, bool, bool]:
    """Return (font_size_dominant, starts_with_bold, all_bold) for a block.

    font_size_dominant: mode of span font_size weighted by character count.
    starts_with_bold: True iff the first non-whitespace span is bold.
    all_bold: True iff every non-whitespace span is bold.
    """
    char_weighted: Counter[int] = Counter()
    for span in spans_in_block:
        # Weight by visible non-whitespace characters only. Whitespace
        # (spaces, tabs, newlines) carries no font signal and would
        # otherwise let indentation-only or trailing-space spans skew the
        # block's dominant size, and through that the document baseline.
        visible_chars = sum(1 for ch in span.text if not ch.isspace())
        if visible_chars:
            char_weighted[span.font_size] += visible_chars
    font_size_dominant = char_weighted.most_common(1)[0][0] if char_weighted else 0

    non_ws_spans = [s for s in spans_in_block if s.text.replace("\n", "").strip()]
    if not non_ws_spans:
        return font_size_dominant, False, False
    starts_with_bold = non_ws_spans[0].bold
    all_bold = all(s.bold for s in non_ws_spans)
    return font_size_dominant, starts_with_bold, all_bold


def _split_spans_into_blocks(spans: list[TextSpan]) -> list[list[TextSpan]]:
    """Split the span stream at \\n boundaries.

    Output matches ``str.splitlines()`` semantics: each block corresponds to
    one logical source line. Blank lines surface as empty blocks (preserved
    so build_extraction_ir can derive accurate line_start / line_end). A
    trailing newline does NOT add an extra empty block (matching
    splitlines), so emitted block count == source line count exactly.
    """
    blocks: list[list[TextSpan]] = []
    current: list[TextSpan] = []
    for span in spans:
        if "\n" not in span.text:
            current.append(span)
            continue
        parts = span.text.split("\n")
        # First part attaches to the in-flight block.
        if parts[0]:
            current.append(TextSpan(text=parts[0], font_size=span.font_size, bold=span.bold))
        # Each subsequent part marks a logical newline. Always flush
        # current (including when it's empty — that's a blank line),
        # then start a fresh block holding the part text.
        for part in parts[1:]:
            blocks.append(current)
            current = []
            if part:
                current.append(TextSpan(text=part, font_size=span.font_size, bold=span.bold))
    # Trailing partial line (no terminating newline). If the last span
    # ended with \n, current is already [] and we don't append an extra
    # blank block — matches str.splitlines() stripping the final newline.
    if current:
        blocks.append(current)
    return blocks


def _compute_baseline(blocks: list[list[TextSpan]]) -> int:
    """Mode of font_size across blocks where no span is bold.

    If all blocks contain bold content (unusual), fall back to mode
    across all blocks.
    """
    non_bold_blocks = [b for b in blocks if not any(s.bold for s in b)]
    candidate_blocks = non_bold_blocks if non_bold_blocks else blocks
    sizes: Counter[int] = Counter()
    for block in candidate_blocks:
        size, _starts, _all = _summarize_block(block)
        if size > 0:
            sizes[size] += 1
    if not sizes:
        return 0
    # On ties, prefer the larger size (stat-block-heavy file inversion guard).
    max_count = max(sizes.values())
    candidates = [size for size, count in sizes.items() if count == max_count]
    return max(candidates)


def _classify_size(font_size: int, baseline: int) -> str:
    if baseline == 0 or font_size == 0:
        return "body"
    if font_size > baseline:
        return "larger"
    if font_size < baseline:
        return "smaller"
    return "body"


def build_extraction_ir(*, file_name: str, spans: list[TextSpan]) -> dict:
    """Build extraction IR from a list of TextSpans.

    Each block (\\n-delimited) gains font_size, font_size_class,
    starts_with_bold, and all_bold fields. Document baseline is stored
    at the IR top level.
    """
    span_blocks = _split_spans_into_blocks(spans)
    baseline = _compute_baseline(span_blocks)

    ir_blocks: list[dict] = []
    line_number = 0
    for span_block in span_blocks:
        line_number += 1
        raw_text = "".join(s.text for s in span_block)
        text = _normalize_block_text(raw_text)
        if not text:
            continue
        block_type = classify_block_type(text)
        font_size, starts_with_bold, all_bold = _summarize_block(span_block)
        ir_blocks.append(
            {
                "block_id": f"b{len(ir_blocks) + 1:04d}",
                "block_type": block_type,
                "text": text,
                "line_start": line_number,
                "line_end": line_number,
                "font_size": font_size,
                "font_size_class": _classify_size(font_size, baseline),
                "starts_with_bold": starts_with_bold,
                "all_bold": all_bold,
            }
        )

    return {
        "ir_version": "2.0",
        "file_name": file_name,
        "blocks": ir_blocks,
        "document_baseline_font_size": baseline,
    }
