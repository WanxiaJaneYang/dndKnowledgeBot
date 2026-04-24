"""Chunker pipeline: canonical document → chunk objects.

Phase 1 strategy (v2-formatting-aware):

- Each canonical document yields one **parent** chunk.
- When the upstream pipeline supplied `processing_hints`, the parent may also
  yield **child** chunks via two mechanisms:
    1. **Structure cuts**: each `processing_hints.structure_cuts[i]` produces
       one typed child sliced from `content[cursor:cut.char_offset]`. The
       chunker does not detect block boundaries itself — it consumes
       offsets the annotator already computed.
    2. **Paragraph-group fallback**: any remaining content (after the last
       cut, or all content when there are no cuts) splits at paragraph
       boundaries targeting `config.paragraph_group_target_chars`.
- Children carry `parent_chunk_id` and a `split_origin` provenance marker
  (`"structure_cut"` or `"paragraph_group"`).

Canonical docs without `processing_hints` are emitted as a single parent
chunk with byte-identical content to v1 (legacy passthrough). This preserves
the upstream contract: the chunker only restructures docs the annotator
explicitly marked for splitting.
"""
from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from .config import ChunkerConfig, load_chunker_config
from .schema_validation import validate_chunks
from .type_classifier import classify_chunk_type

CHUNK_VERSION = "v2-formatting-aware"


def _chunk_id(document_id: str) -> str:
    return f"chunk::{document_id}"


def _source_file_key(doc: dict) -> str:
    """Group key for within-file adjacency.

    Adjacency links are only meaningful within the same source file —
    a link crossing file boundaries would imply context continuity that
    doesn't exist. Derive the key from source_location (the part before '#')
    and fall back to section_path[0] when source_location is absent.
    """
    locator = doc.get("locator", {})
    source_location = locator.get("source_location", "")
    if source_location:
        return source_location.split("#")[0]
    section_path = locator.get("section_path", [])
    if section_path:
        return section_path[0]
    return "__unknown__"


def _load_config(repo_root: Path) -> ChunkerConfig:
    """Load ChunkerConfig from configs/chunker.yaml when present, else defaults."""
    cfg_path = repo_root / "configs" / "chunker.yaml"
    if cfg_path.exists():
        return load_chunker_config(cfg_path.read_text(encoding="utf-8"))
    return ChunkerConfig()


def _build_parent_chunk(
    canonical_doc: dict,
    *,
    previous_chunk_id: str | None,
    next_chunk_id: str | None,
) -> dict:
    document_id = canonical_doc["document_id"]
    section_path = canonical_doc.get("locator", {}).get("section_path", [])
    content = canonical_doc.get("content", "")

    # `or {}` defends against an explicit `processing_hints: null` in the
    # canonical doc (.get with default would still return None and
    # .get("chunk_type_hint") would AttributeError).
    hints = canonical_doc.get("processing_hints") or {}
    chunk_type = hints.get("chunk_type_hint")
    if chunk_type is None:
        chunk_type = classify_chunk_type(section_path, content)

    chunk: dict = {
        "chunk_id": _chunk_id(document_id),
        "document_id": document_id,
        "source_ref": canonical_doc["source_ref"],
        "locator": canonical_doc["locator"],
        "chunk_type": chunk_type,
        "content": content,
        "chunk_version": CHUNK_VERSION,
    }
    if previous_chunk_id is not None:
        chunk["previous_chunk_id"] = previous_chunk_id
    if next_chunk_id is not None:
        chunk["next_chunk_id"] = next_chunk_id
    return chunk


def _should_split(canonical_doc: dict, config: ChunkerConfig) -> bool:
    """Return True when the chunker should produce children for this doc.

    Policy: only split docs the upstream pipeline annotated with
    `processing_hints`. Legacy docs (no hints) stay as a single parent chunk
    so v1 outputs remain byte-identical except for the chunk_version field.

    Within annotated docs, split when either:
    - structure_cuts non-empty (the cuts ARE the split points), OR
    - content exceeds child_threshold_chars (paragraph_group fallback fires).
    """
    hints = canonical_doc.get("processing_hints")
    if not hints:
        return False
    if hints.get("structure_cuts"):
        return True
    content = canonical_doc.get("content", "")
    return len(content) > config.child_threshold_chars


def _make_child(
    canonical_doc: dict,
    parent_chunk_id: str,
    child_content: str,
    chunk_type: str,
    *,
    split_origin: str,
) -> dict:
    """Build a child chunk dict. chunk_id is renumbered in _wire_sibling_adjacency."""
    document_id = canonical_doc["document_id"]
    return {
        # Placeholder; renumbered by _wire_sibling_adjacency once group order is known.
        "chunk_id": f"chunk::{document_id}::child_pending",
        "document_id": document_id,
        "source_ref": canonical_doc["source_ref"],
        "locator": canonical_doc["locator"],
        "chunk_type": chunk_type,
        "content": child_content,
        "chunk_version": CHUNK_VERSION,
        "parent_chunk_id": parent_chunk_id,
        "split_origin": split_origin,
    }


def _paragraph_group_children(
    canonical_doc: dict,
    parent_chunk_id: str,
    content: str,
    config: ChunkerConfig,
) -> list[dict]:
    """Split `content` at paragraph boundaries into paragraph_group children.

    Paragraphs are separated by blank lines (``\\n\\n``). Groups grow until
    adding the next paragraph would exceed `config.paragraph_group_target_chars`;
    any single paragraph or merged group that still exceeds
    `config.paragraph_group_max_chars` is sliced at character boundaries to
    enforce the hard cap (prevents one runaway paragraph from producing an
    oversized chunk).
    """
    if not content.strip():
        return []
    paragraphs = [p for p in content.split("\n\n") if p.strip()]
    if not paragraphs:
        return []

    groups: list[list[str]] = []
    current_group: list[str] = []
    current_size = 0
    for para in paragraphs:
        if current_size > 0 and current_size + len(para) > config.paragraph_group_target_chars:
            groups.append(current_group)
            current_group = []
            current_size = 0
        current_group.append(para)
        current_size += len(para)
    if current_group:
        groups.append(current_group)

    children: list[dict] = []
    for group in groups:
        group_text = "\n\n".join(group)
        for slice_text in _enforce_max_chars(group_text, config.paragraph_group_max_chars):
            children.append(_make_child(
                canonical_doc, parent_chunk_id,
                slice_text, "paragraph_group",
                split_origin="paragraph_group",
            ))
    return children


def _enforce_max_chars(text: str, max_chars: int) -> list[str]:
    """Yield text slices each at most ``max_chars`` long.

    Tries split candidates in this preference order, picking the latest
    one that fits within ``max_chars``:

      1. Paragraph boundary ``\\n\\n`` (separator consumed between chunks).
      2. Single newline ``\\n`` (separator consumed).
      3. Sentence-end ``. `` (period stays in prior chunk; space consumed).
      4. Raw character boundary at ``max_chars`` (no separator consumed).

    Whitespace inside content is preserved — only newline separators at
    chunk boundaries are stripped (matches the chunker's elsewhere
    newline-only normalization rule, so leading spaces / indentation in
    paragraphs are not silently lost).
    """
    if not text:
        return []
    if len(text) <= max_chars:
        return [text]
    slices: list[str] = []
    remaining = text
    while len(remaining) > max_chars:
        cut: int  # end of prior chunk (exclusive)
        sep_len: int  # how many chars of separator to consume between chunks
        para_pos = remaining.rfind("\n\n", 0, max_chars)
        if para_pos > 0:
            cut, sep_len = para_pos, 2
        else:
            nl_pos = remaining.rfind("\n", 0, max_chars)
            sentence_pos = remaining.rfind(". ", 0, max_chars)
            if nl_pos > 0 and nl_pos >= sentence_pos:
                cut, sep_len = nl_pos, 1
            elif sentence_pos > 0:
                # Include the period in the prior chunk; consume the trailing space.
                cut, sep_len = sentence_pos + 1, 1
            else:
                # Last resort: raw char boundary, no separator to consume.
                cut, sep_len = max_chars, 0
        chunk = remaining[:cut].strip("\n")
        if chunk:
            slices.append(chunk)
        remaining = remaining[cut + sep_len:].lstrip("\n")
    if remaining:
        slices.append(remaining)
    return [s for s in slices if s]


def _wire_sibling_adjacency(children: list[dict]) -> None:
    """Renumber child chunk_ids and wire previous_chunk_id/next_chunk_id within siblings."""
    if not children:
        return
    document_id = children[0]["document_id"]
    for idx, child in enumerate(children):
        child["chunk_id"] = f"chunk::{document_id}::child_{idx + 1:03d}"
    for i, child in enumerate(children):
        if i > 0:
            child["previous_chunk_id"] = children[i - 1]["chunk_id"]
        if i < len(children) - 1:
            child["next_chunk_id"] = children[i + 1]["chunk_id"]


def _validate_structure_cuts(cuts: list[dict], content_len: int, document_id: str) -> None:
    """Validate cut offsets are sane before slicing content.

    Catches schema-valid but logically broken cuts (negative, beyond
    content end, decreasing) early with a clear error rather than
    producing silently-wrong slices downstream.
    """
    last_offset = 0
    for i, cut in enumerate(cuts):
        offset = cut.get("char_offset", -1)
        if not isinstance(offset, int) or offset < 0 or offset > content_len:
            raise ValueError(
                f"structure_cuts[{i}].char_offset {offset} out of range [0, {content_len}] "
                f"for document {document_id!r}"
            )
        if offset < last_offset:
            raise ValueError(
                f"structure_cuts must be strictly increasing: cuts[{i}].char_offset "
                f"{offset} < previous {last_offset} for document {document_id!r}"
            )
        last_offset = offset


def _split_into_children(
    canonical_doc: dict,
    parent_chunk_id: str,
    config: ChunkerConfig,
) -> list[dict]:
    """Produce child chunks via structure cuts then paragraph-group fallback."""
    content = canonical_doc.get("content", "")
    # `or {}` defends against `processing_hints: null` (see _build_parent_chunk).
    hints = canonical_doc.get("processing_hints") or {}
    cuts = hints.get("structure_cuts") or []
    _validate_structure_cuts(cuts, len(content), canonical_doc.get("document_id", "<unknown>"))

    children: list[dict] = []
    cursor = 0
    for cut in cuts:
        end = cut["char_offset"]
        # Newline-only normalization: preserve precise slice semantics per
        # design §4.5. Do NOT use .strip() — leading/trailing spaces within
        # the slice are part of the canonical content.
        child_text = content[cursor:end].lstrip("\n").rstrip("\n")
        if child_text:
            children.append(_make_child(
                canonical_doc, parent_chunk_id,
                child_text, cut["child_chunk_type"],
                split_origin="structure_cut",
            ))
        cursor = end

    remaining = content[cursor:]
    children.extend(_paragraph_group_children(
        canonical_doc, parent_chunk_id, remaining, config,
    ))

    _wire_sibling_adjacency(children)
    return children


def _build_chunks(
    canonical_doc: dict,
    *,
    previous_chunk_id: str | None,
    next_chunk_id: str | None,
    config: ChunkerConfig,
) -> list[dict]:
    """Return [parent] or [parent, *children] for one canonical doc."""
    parent = _build_parent_chunk(
        canonical_doc,
        previous_chunk_id=previous_chunk_id,
        next_chunk_id=next_chunk_id,
    )
    if not _should_split(canonical_doc, config):
        return [parent]
    children = _split_into_children(canonical_doc, parent["chunk_id"], config)
    if not children:
        return [parent]
    return [parent] + children


def chunk_source(
    canonical_root: Path,
    output_root: Path,
    repo_root: Path,
    source_id: str | None = None,
    *,
    force: bool = False,
    require_schema_validation: bool = False,
) -> dict:
    """Read all canonical docs from canonical_root, produce chunks in output_root.

    source_id is written to the chunk report. When None it is derived from
    the canonical docs; when provided it must match every doc's source_ref.source_id.

    Callers that accept user-supplied paths (e.g. the CLI) are responsible for
    validating that output_root is inside repo_root before calling with force=True.
    """
    if not canonical_root.exists():
        raise FileNotFoundError(f"Canonical root not found: {canonical_root}")

    if output_root.exists() and not force:
        raise FileExistsError(
            f"Chunk output directory already exists: {output_root}. "
            "Re-run with --force to regenerate."
        )
    if force and output_root.exists():
        shutil.rmtree(output_root)
    output_root.mkdir(parents=True, exist_ok=True)

    config = _load_config(repo_root)

    # Load and sort canonical docs so adjacency links are deterministic.
    canonical_paths = sorted(canonical_root.glob("*.json"))
    canonical_paths = [p for p in canonical_paths if p.name != "canonical_report.json"]

    canonical_docs = []
    for path in canonical_paths:
        doc = json.loads(path.read_text(encoding="utf-8"))
        canonical_docs.append((path.stem, doc))

    # Derive or validate source_id from canonical docs so the report is
    # always consistent with the chunk source_ref fields.
    if canonical_docs:
        canonical_source_ids = {doc["source_ref"]["source_id"] for _, doc in canonical_docs}
        if len(canonical_source_ids) > 1:
            raise ValueError(
                f"Canonical docs contain multiple source_ids: {canonical_source_ids}. "
                "chunk_source expects a single-source canonical root."
            )
        derived_source_id = canonical_source_ids.pop()
        if source_id is not None and source_id != derived_source_id:
            raise ValueError(
                f"Provided source_id {source_id!r} does not match canonical docs "
                f"source_ref.source_id {derived_source_id!r}."
            )
        source_id = derived_source_id
    elif source_id is None:
        source_id = "unknown"

    # Group by source file so parent file-order adjacency stays within the same file.
    # Adjacency between parents in different files would imply continuity that
    # doesn't exist; child sibling adjacency is wired separately within each parent.
    by_file: dict[str, list[tuple[str, dict]]] = {}
    for stem, doc in canonical_docs:
        key = _source_file_key(doc)
        by_file.setdefault(key, []).append((stem, doc))

    # Build chunk objects: each canonical doc yields a parent (with file-order
    # previous/next links to neighboring parents) and optionally children.
    chunks: list[tuple[str, dict]] = []
    for file_docs in by_file.values():
        n = len(file_docs)
        for i, (stem, doc) in enumerate(file_docs):
            prev_id = _chunk_id(file_docs[i - 1][1]["document_id"]) if i > 0 else None
            next_id = _chunk_id(file_docs[i + 1][1]["document_id"]) if i < n - 1 else None
            built = _build_chunks(
                doc,
                previous_chunk_id=prev_id,
                next_chunk_id=next_id,
                config=config,
            )
            for chunk in built:
                chunks.append((stem, chunk))

    # Validate before writing.
    chunked_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    chunk_objects = [c for _, c in chunks]
    validation_result = validate_chunks(
        chunk_objects,
        repo_root,
        require_validation=require_schema_validation,
    )

    # Write chunk files and accumulate report counters.
    chunk_records: list[dict] = []
    parent_count = 0
    child_count = 0
    structure_cut_children = 0
    paragraph_group_children = 0
    chunks_by_type: dict[str, int] = {}

    for stem, chunk in chunks:
        chunks_by_type[chunk["chunk_type"]] = chunks_by_type.get(chunk["chunk_type"], 0) + 1
        if "parent_chunk_id" in chunk:
            child_suffix = chunk["chunk_id"].split("::")[-1]
            chunk_path = output_root / f"{stem}__{child_suffix}.json"
            child_count += 1
            if chunk.get("split_origin") == "structure_cut":
                structure_cut_children += 1
            else:
                paragraph_group_children += 1
        else:
            chunk_path = output_root / f"{stem}.json"
            parent_count += 1
        chunk_path.write_text(json.dumps(chunk, indent=2) + "\n", encoding="utf-8")
        try:
            display_path = str(chunk_path.relative_to(repo_root))
        except ValueError:
            display_path = str(chunk_path)
        record = {
            "chunk_id": chunk["chunk_id"],
            "document_id": chunk["document_id"],
            "chunk_type": chunk["chunk_type"],
            "chunk_path": display_path,
        }
        if "parent_chunk_id" in chunk:
            record["parent_chunk_id"] = chunk["parent_chunk_id"]
            record["split_origin"] = chunk["split_origin"]
        chunk_records.append(record)

    # Write chunk report.
    report = {
        "source_id": source_id,
        "chunked_at_utc": chunked_at,
        "strategy": CHUNK_VERSION,
        "chunk_count": len(chunk_records),
        "parent_count": parent_count,
        "child_count": child_count,
        "structure_cut_children": structure_cut_children,
        "paragraph_group_children": paragraph_group_children,
        "chunks_by_type": chunks_by_type,
        "schema_validation": validation_result,
        "records": chunk_records,
    }
    report_path = output_root / "chunk_report.json"
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    return {
        "source_id": source_id,
        "canonical_root": str(canonical_root),
        "output_root": str(output_root),
        "chunks_written": len(chunk_records),
        "chunk_report": str(report_path),
        "schema_validation": validation_result,
    }
