"""Formatting-driven entry detection that runs on raw IR blocks.

Annotates blocks in place with entry roles. Downstream consumers
(sectioning, boundary filter, canonical emission) read annotations
only; they never import ContentTypeConfig.

Detection is shape-driven within a typed config layer:
  - Shape rules are vocabulary-free pattern matchers over font_size
    and starts_with_bold.
  - Type config (content_types.yaml) binds semantic identity to a
    shape and provides per-type shape parameters.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

from .content_types import ContentTypeConfig, eligible_types_for_file


class EntryAnnotationConflict(Exception):
    """Raised when shapes claim overlapping blocks or re-annotation is attempted."""


@dataclass(frozen=True)
class _Match:
    """A successful shape match over a contiguous block range."""
    start_index: int   # inclusive
    end_index: int     # exclusive
    title_index: int
    subtitle_index: int | None  # None for definition_list (each block is its own entry)
    field_indices: tuple[int, ...]
    description_indices: tuple[int, ...]
    title_text: str
    type_config: ContentTypeConfig


def annotate_entries(
    blocks: list[dict],
    *,
    file_name: str,
    content_types: list[ContentTypeConfig],
) -> list[dict]:
    """Annotate blocks with entry roles. Mutates and returns blocks.

    Owns eligibility filtering and shape execution. Raises
    EntryAnnotationConflict if shapes claim overlapping blocks or
    if any block already carries entry annotations.
    """
    if any("entry_index" in b for b in blocks):
        raise EntryAnnotationConflict(
            f"annotate_entries called on already-annotated blocks (file={file_name})"
        )

    eligible = eligible_types_for_file(file_name, content_types)
    if not eligible:
        return blocks

    all_matches: list[tuple[_Match, str]] = []  # (match, shape_family)
    for cfg in eligible:
        if cfg.shape == "entry_with_statblock":
            for m in _find_entry_with_statblock_matches(blocks, cfg):
                all_matches.append((m, "entry_with_statblock"))
        elif cfg.shape == "definition_list":
            for m in _find_definition_list_matches(blocks, cfg):
                all_matches.append((m, "definition_list"))
        else:
            raise ValueError(f"Unknown shape: {cfg.shape}")

    # Conflict detection: any two matches' [start, end) overlap.
    sorted_matches = sorted(all_matches, key=lambda mm: mm[0].start_index)
    for i in range(len(sorted_matches) - 1):
        m_a, _ = sorted_matches[i]
        m_b, _ = sorted_matches[i + 1]
        if m_b.start_index < m_a.end_index:
            raise EntryAnnotationConflict(
                f"Overlapping shape matches in {file_name}: "
                f"{m_a.type_config.name} blocks [{m_a.start_index},{m_a.end_index}) "
                f"vs {m_b.type_config.name} blocks [{m_b.start_index},{m_b.end_index}). "
                f"Hint: narrow file_match in content_types.yaml."
            )

    # Apply annotations. entry_index is a single monotonic counter over the
    # file (NOT per-type), so disjoint matches from different types still get
    # globally-unique indices — required for downstream grouping by entry_index
    # to be unambiguous.
    for entry_index, (match, shape_family) in enumerate(sorted_matches):
        _apply_match(blocks, match, shape_family, entry_index)

    return blocks


# ----------------------------------------------------------------------
# entry_with_statblock shape
# ----------------------------------------------------------------------

def _find_entry_with_statblock_matches(
    blocks: list[dict], cfg: ContentTypeConfig,
) -> Iterable[_Match]:
    params = cfg.shape_params
    max_title_len: int = params.get("max_title_len", 80)
    max_subtitle_len: int = params.get("max_subtitle_len", 80)
    min_fields: int = params.get("min_fields", 2)
    field_pattern = re.compile(params.get("field_pattern", r"^[A-Z][\w '/-]+:"))

    candidates: list[_Match] = []
    n = len(blocks)
    i = 0
    while i < n - 2:
        title = blocks[i]
        subtitle = blocks[i + 1]
        if not _is_valid_title(title, max_title_len, field_pattern):
            i += 1
            continue
        if not _is_valid_subtitle(subtitle, title, max_subtitle_len):
            i += 1
            continue

        # Count consecutive field blocks.
        field_indices: list[int] = []
        j = i + 2
        while j < n and _is_field_block(blocks[j], subtitle, field_pattern):
            field_indices.append(j)
            j += 1
        if len(field_indices) < min_fields:
            i += 1
            continue

        # We have a candidate match starting at i. Provisional end_index
        # is end-of-fields; description blocks (the prose between this
        # entry and the next title) get attached after we know the next
        # match position.
        candidates.append(_Match(
            start_index=i,
            end_index=j,  # exclusive — provisional, extended below
            title_index=i,
            subtitle_index=i + 1,
            field_indices=tuple(field_indices),
            description_indices=(),  # filled in below
            title_text=title["text"].strip(),
            type_config=cfg,
        ))
        i = j  # skip past consumed blocks
    # Extend each match's end_index to include description blocks up to the
    # next match (or EOF — but stop at the first heading_candidate so trailing
    # section headings, footers preceded by a heading, etc. are not absorbed
    # as the last entry's description).
    extended: list[_Match] = []
    for idx, m in enumerate(candidates):
        hard_stop = candidates[idx + 1].start_index if idx + 1 < len(candidates) else n
        desc_end = _description_end(blocks, m.end_index, hard_stop)
        desc_indices = tuple(range(m.end_index, desc_end))
        extended.append(_Match(
            start_index=m.start_index,
            end_index=desc_end,
            title_index=m.title_index,
            subtitle_index=m.subtitle_index,
            field_indices=m.field_indices,
            description_indices=desc_indices,
            title_text=m.title_text,
            type_config=m.type_config,
        ))
    return extended


def _description_end(blocks: list[dict], start: int, hard_stop: int) -> int:
    """Return the exclusive end index for an entry's description range.

    Walks blocks[start:hard_stop] and stops at the first block whose
    block_type is heading_candidate — the IR's heading detector has
    already flagged it as a section boundary. This prevents the final
    entry in a file from absorbing trailing section headings (and any
    blocks beyond them) as its own description. Pure-prose footers
    without a heading marker will still be absorbed; that's a known
    limit, not a bug.
    """
    for k in range(start, hard_stop):
        if blocks[k].get("block_type") == "heading_candidate":
            return k
    return hard_stop


def _is_valid_title(block: dict, max_len: int, field_pattern: re.Pattern) -> bool:
    text = block.get("text", "").strip()
    if not text:
        return False
    if len(text) > max_len:
        return False
    if block.get("starts_with_bold", False):
        return False
    if field_pattern.match(text):
        return False  # title-as-field guard
    return True


def _is_valid_subtitle(block: dict, title: dict, max_len: int) -> bool:
    text = block.get("text", "").strip()
    if not text:
        return False
    if len(text) > max_len:
        return False
    if block.get("starts_with_bold", False):
        return False
    if block.get("font_size", 0) >= title.get("font_size", 0):
        return False  # strict step-down
    return True


def _is_field_block(block: dict, subtitle: dict, field_pattern: re.Pattern) -> bool:
    if not block.get("starts_with_bold", False):
        return False
    if block.get("font_size", 0) != subtitle.get("font_size", 0):
        return False
    text = block.get("text", "").strip()
    return bool(field_pattern.match(text))


# ----------------------------------------------------------------------
# definition_list shape
# ----------------------------------------------------------------------

def _find_definition_list_matches(
    blocks: list[dict], cfg: ContentTypeConfig,
) -> Iterable[_Match]:
    params = cfg.shape_params
    min_blocks: int = params.get("min_blocks", 3)
    term_pattern = re.compile(params.get("term_pattern", r"^[A-Z][\w '/-]*:\s+\S"))

    n = len(blocks)
    matches: list[_Match] = []
    i = 0
    while i < n:
        if not _is_def_block(blocks[i], term_pattern):
            i += 1
            continue
        # Scan forward while same font_size + matches term_pattern.
        # Use .get() consistently with entry_with_statblock predicates so a
        # raw IR block missing font_size simply doesn't match (rather than
        # raising KeyError mid-scan).
        run_size = blocks[i].get("font_size", 0)
        j = i
        run_indices: list[int] = []
        while (
            j < n
            and _is_def_block(blocks[j], term_pattern)
            and blocks[j].get("font_size", 0) == run_size
        ):
            run_indices.append(j)
            j += 1
        if len(run_indices) >= min_blocks:
            # Each block in the run is its own entry (single-block).
            for block_idx in run_indices:
                title_text = _definition_term(blocks[block_idx]["text"])
                matches.append(_Match(
                    start_index=block_idx,
                    end_index=block_idx + 1,
                    title_index=block_idx,
                    subtitle_index=None,
                    field_indices=(),
                    description_indices=(),
                    title_text=title_text,
                    type_config=cfg,
                ))
        i = j
    return matches


def _is_def_block(block: dict, term_pattern: re.Pattern) -> bool:
    if not block.get("starts_with_bold", False):
        return False
    text = block.get("text", "").strip()
    return bool(term_pattern.match(text))


def _definition_term(text: str) -> str:
    return text.split(":", 1)[0].strip()


# ----------------------------------------------------------------------
# Annotation application
# ----------------------------------------------------------------------

def _apply_match(
    blocks: list[dict],
    match: _Match,
    shape_family: str,
    entry_index: int,
) -> None:
    cfg = match.type_config
    base = {
        "entry_index": entry_index,
        "entry_type": cfg.name,
        "entry_category": cfg.category,
        "entry_chunk_type": cfg.chunk_type,
        "entry_title": match.title_text,
        "shape_family": shape_family,
    }

    if shape_family == "definition_list":
        # Single-block entry: one block is title + definition combined.
        blocks[match.title_index].update({**base, "entry_role": "definition"})
        return

    # entry_with_statblock
    blocks[match.title_index].update({**base, "entry_role": "title"})
    if match.subtitle_index is not None:
        blocks[match.subtitle_index].update({**base, "entry_role": "subtitle"})
    for fi in match.field_indices:
        blocks[fi].update({**base, "entry_role": "stat_field"})
    for di in match.description_indices:
        blocks[di].update({**base, "entry_role": "description"})
