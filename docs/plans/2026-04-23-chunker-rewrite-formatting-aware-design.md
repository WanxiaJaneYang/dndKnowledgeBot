# Chunker Rewrite — Formatting-Aware Entry Detection

**Date**: 2026-04-23
**Supersedes**: `docs/plans/2026-04-21-hierarchical-chunking-design.md`, `docs/plans/2026-04-21-hierarchical-chunking-implementation.md` (PR #63, rolled back)
**Related issues**: #60 (parent goal), #50 (chunk-type prior — receiving end), #46 (structure metadata indexing — receiving end)
**Status**: Design

---

## 1. Goal

Make ingestion produce per-entry canonical docs and the chunker produce parent-child chunks for entry-bearing content, **driven by formatting signals (font size + bold) rather than hardcoded vocabulary lists**, so the architecture stays correct as new sources, editions, and content types are added.

## 2. Scope and non-goals

### In scope

- **Decoder enhancement**: preserve per-run font-size and bold metadata from RTF.
- **IR enrichment**: per-block formatting summary fields.
- **Entry detection rewrite**: vocabulary-free shape rules (`entry_with_statblock`, `definition_list`) running on raw IR blocks before sectioning.
- **Type config**: declarative content-type registry binding semantic identity (category, chunk_type) to shape rules.
- **Pipeline reorder**: entry detection runs *before* sectioning (root fix for the BLOCKING bug Codex flagged on PR #63).
- **Sectioning two-path support**: entry-driven path + heading-candidate fallback, same output shape.
- **Boundary filter cleanup**: remove `_SPELL_BLOCK_FIELDS` private vocabulary; entry-annotated sections accepted as-is.
- **Chunker structure-aware splitting**: parent + optional children driven by upstream-computed structure cuts (no `_STAT_BLOCK_LABELS` list).
- **Schema updates**: `canonical_document.schema.json` gains `processing_hints`; `chunk.schema.json` gains new chunk types + `split_origin`. **Both schemas keep `additionalProperties: false`; new fields are explicit additions to `properties`, not silent extras.**

### Non-goals

- **No retrieval, ranking, or answer generation changes.** Issues #50 and #46 consume the new chunk types and parent_chunk_id; coordination required, but their work lives elsewhere.
- **No 5e or other-edition source ingestion in this PR.** The architecture is designed to support it without code changes; adding a 5e source is a future task.
- **No class-feature or magic-item shape detection.** Architecture absorbs new shapes additively; deferred until corpus sampling reveals their structural conventions.
- **No PDF or HTML extraction changes.** This rewrite stays within the RTF path.

## 3. Current state and problem

PR #63 attempted hierarchical chunking via per-content-type detectors with hardcoded vocabulary:

```python
_SCHOOLS = {"Abjuration", "Conjuration", ...}        # 8 schools, D&D 3.5 only
_FEAT_TAGS = {"GENERAL", "FIGHTER", "METAMAGIC", ...}  # 8 tags, D&D 3.5 only
_KNOWN_CONDITIONS = {"Blinded", "Confused", ...}     # 38 conditions, fully enumerated
_SPELL_BLOCK_FIELDS = {"area", "casting time", ...}  # private vocab in boundary_filter.py
```

Two consequences:

1. **Brittle to new data**: 5e adds new schools, removes `Spell Resistance`, renames feat categories. Every new source requires editing detector code.
2. **Compensating for thrown-away signals**: the RTF source actually carries font-size (`\fs<n>`) and bold (`\b`) markers per text run, which directly encode the entry/stat-block/description structure. The decoder strips all of it; detectors then reverse-engineer the structure from text shape.

PR #63 also placed entry detection *after* `split_sections_from_blocks`, which strips `heading_candidate` lines from section content. Codex flagged this as a P1 BLOCKING issue (sectioner consumes the spell title before detection sees it). PR #63's fix was a `_recover_consumed_header()` band-aid that re-detected against the original IR block text. The implementation was force-rolled back on 2026-04-22.

## 4. Proposed design

### 4.1 Pipeline

```
RTF → decode_rtf_spans (preserves font-size + bold per span)
    → build_extraction_ir (blocks gain font_size + starts_with_bold + all_bold)
    → annotate_entries (formatting-driven shape rules, runs on raw IR)
    → split_sections_from_blocks (entry-driven path | heading-candidate fallback)
    → apply_boundary_filters (entry-annotated sections accepted as-is)
    → emit canonical docs (read entry annotations + processing_hints)
    → chunk (consume processing_hints.structure_cuts + chunk_type_hint)
```

Three structural changes from PR #63:

1. **Detection signals come from formatting, not vocabulary.**
2. **Detection runs *before* sectioning, on the IR.** Kills the consumed-heading bug at the root.
3. **Detection is shape-driven within a typed config layer.** Code knows shapes (`entry_with_statblock`, `definition_list`); type identity (category, chunk_type) lives in declarative config bound to shapes.

### 4.2 Decoder + IR mechanics

#### Decoder API — additive only

```python
def decode_rtf_text(rtf_text: str) -> str: ...    # unchanged, returns plain text

@dataclass
class TextSpan:
    text: str            # visible text (incl. \par as "\n")
    font_size: int       # half-points (RTF native), e.g. 24 = 12pt
    bold: bool

def decode_rtf_spans(rtf_text: str) -> list[TextSpan]: ...  # NEW
```

Both share a private `_parse_rtf` generator. Existing callers stay on `decode_rtf_text`; only `build_extraction_ir` switches to `decode_rtf_spans`.

#### IR per-block summary

`build_extraction_ir` signature changes from `text: str` → `spans: list[TextSpan]`. Each block gains:

| Field | Type | Computed how |
|---|---|---|
| `font_size` | int | mode-by-character-count of span font sizes within the block |
| `font_size_class` | `"larger" \| "body" \| "smaller"` | computed against per-document baseline (diagnostic; shape rules don't depend on it) |
| `starts_with_bold` | bool | first non-whitespace span of the block is bold |
| `all_bold` | bool | every span of the block is bold |

Document baseline = mode of `font_size` across blocks where `bold == False` (biased toward the largest well-represented font to avoid stat-block-heavy file inversion). Computed once at IR-build time and stored on the IR top-level dict as `document_baseline_font_size` (additive field; existing IR consumers ignore it). Per-block `font_size_class` derives from this baseline.

#### Out of scope

No italic, color, alignment, indentation. No style-table resolution. No span-list past the IR (only summary fields).

### 4.3 Entry detection module

#### Public API

```python
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
```

Routing:

1. Filter `content_types` by `file_match` glob (optional allowlist; absent = always eligible).
2. For each eligible type, run its shape against the blocks.
3. Disjoint claims coexist; overlapping claims raise `EntryAnnotationConflict`.
4. Files matching no shape pass through unannotated → sectioning falls back to heading-candidate path.

#### Annotation contract

Per claimed block:

```python
{
  ...existing block fields...,
  "entry_index": 5,                   # per-file, sequential, shared across blocks of one entry
  "entry_role": "stat_field",         # title | subtitle | stat_field | description | definition
  "entry_type": "spell",              # the type config name
  "entry_category": "Spells",         # baked from config — for section_path[0]
  "entry_chunk_type": "spell_entry",  # baked — for chunk classification
  "entry_title": "Sanctuary",         # baked — for locator.entry_title
  "shape_family": "entry_with_statblock"  # diagnostics
}
```

Downstream consumers (sectioning, boundary filter, canonical emission, chunker) **read annotations only**; they never import `ContentTypeConfig`.

#### Shape rules — relational predicates

**`entry_with_statblock`**:

```
For each candidate position i:
  title    = blocks[i]:    not bold, len(text.strip()) > 0,
                           text does not match field_pattern,    ← title-as-field guard
                           len(text) ≤ params.max_title_len
  subtitle = blocks[i+1]:  not bold, len(text) ≤ params.max_subtitle_len,
                           font_size <  blocks[i].font_size      ← strict step-down (relational)
  fields   = blocks[i+2 ..]:
             starts_with_bold = True,
             text matches params.field_pattern,
             font_size == blocks[i+1].font_size                  ← consistent w/ subtitle (relational)
             at least params.min_fields consecutive matches

Match accepted ⇔ title + subtitle + ≥min_fields field-blocks
Entry runs from blocks[i] up to (exclusive) the next accepted match
  position OR end-of-file (computed via forward scan: collect all
  match positions first, then assign block ranges).
```

**`definition_list`**:

```
Run = consecutive blocks where:
  starts_with_bold = True,
  text matches params.term_pattern,
  font_size = same as previous block in run

Match accepted ⇔ Run length ≥ params.min_blocks
Each block in run = one entry; entry_title = bold-prefix text up to ":"
```

#### Type config

`configs/content_types.yaml`:

```yaml
content_types:
  - name: spell
    category: Spells
    chunk_type: spell_entry
    shape: entry_with_statblock
    shape_params:
      max_title_len: 80
      max_subtitle_len: 80
      min_fields: 2
      field_pattern: '^[A-Z][\w \''/-]+:'
    file_match: ["Spells*.rtf", "EpicSpells.rtf", "DivineDomainsandSpells.rtf"]

  - name: feat
    category: Feats
    chunk_type: feat_entry
    shape: entry_with_statblock
    shape_params:
      max_title_len: 80
      max_subtitle_len: 40
      min_fields: 1
      field_pattern: '^[A-Z][\w \''/-]+:'
    file_match: ["Feats.rtf", "EpicFeats.rtf", "DivineAbilitiesandFeats.rtf"]

  - name: condition
    category: Conditions
    chunk_type: condition_entry
    shape: definition_list
    shape_params:
      min_blocks: 3
      term_pattern: '^[A-Z][\w \''/-]*:\s+\S'
    file_match: ["AbilitiesandConditions.rtf"]
```

Validated against `schemas/content_types.schema.json` at load time. Shape params have JSON-Schema-validated defaults per shape.

#### Conflict & re-run semantics

`EntryAnnotationConflict` raised when:
1. Two shape matches claim overlapping block indices in one call.
2. Any input block already has `entry_index` set (re-run protection).

Error message: file_name, competing types, overlapping block range, hint to narrow `file_match`.

### 4.4 Sectioning + pipeline integration

#### Sectioning two-path

```python
def split_sections_from_blocks(file_stem, blocks):
    if any("entry_index" in b for b in blocks):
        return _sections_from_entry_annotations(file_stem, blocks)
    return _sections_from_heading_candidates(file_stem, blocks)  # today's logic, renamed
```

**Entry-driven path** groups blocks by `entry_index`. Each section dict gains optional `entry_metadata`:

```python
{
  ...existing section fields...,
  "entry_metadata": {                  # NEW, optional — present iff entry-driven
    "entry_type": "spell",
    "entry_category": "Spells",
    "entry_chunk_type": "spell_entry",
    "entry_title": "Sanctuary",
    "entry_index": 5,                  # debug provenance
    "shape_family": "entry_with_statblock"
  }
}
```

**Unannotated gap blocks** (between annotated entries — file-level preamble, OGL boilerplate, transitional prose):
- Collected as contiguous block ranges between annotated regions.
- Each gap range is processed by `_sections_from_heading_candidates(file_stem, gap_blocks)` (the heading-candidate logic is callable on any block subset; no global state). This means a multi-paragraph preamble containing its own heading-candidate gets split into multiple sections, while a short OGL one-liner becomes one section.
- No `entry_metadata` set on resulting sections.

**Heading-candidate fallback path**: today's `split_sections_from_blocks` logic, unchanged.

Both paths produce sections with identical key set (`entry_metadata` is the only new optional key).

#### Boundary filter

Entry-annotated sections accepted unconditionally:

```python
for index, candidate in enumerate(candidates):
    if "entry_metadata" in candidate:
        accepted.append(materialized(candidate))
        decisions.append({..., "action": "accepted", "reason_code": "entry_annotated"})
        continue
    # ...today's heuristic loop runs only on heading-candidate-path sections...
```

Removed: `_SPELL_BLOCK_FIELDS`, `_looks_spell_block_field()`, the `elif _looks_spell_block_field(title):` branch.

Other heuristics (`_is_boilerplate_stub`, `_looks_table_label_title`, `_is_table_fragment`, `_looks_truncated_title`) keep their roles.

#### Canonical doc emission

```python
for index, section in enumerate(sections, start=1):
    meta = section.get("entry_metadata")
    if meta:
        section_path = [meta["entry_category"], meta["entry_title"]]
        document_title = meta["entry_title"]
        locator = {
            "section_path": section_path,
            "source_location": f"{file_stem}.rtf#{index:03d}_{section['section_slug']}",
            "entry_title": meta["entry_title"],
        }
        processing_hints = {
            "chunk_type_hint": meta["entry_chunk_type"],
            "structure_cuts": _compute_structure_cuts(section, meta),
        }
    else:
        section_path = [rtf_path.stem, section["section_title"]]
        document_title = section["section_title"]
        locator = {"section_path": section_path, "source_location": ...}
        processing_hints = None

    canonical_doc = {
        "document_id": f"{source_id}::{file_slug}::{index:03d}_{section['section_slug']}",
        "source_ref": source_ref,
        "locator": locator,
        "content": section["content"],
        "document_title": document_title,
        "source_checksum": raw_checksum,
        "ingested_at": ingested_at,
    }
    if processing_hints is not None:
        canonical_doc["processing_hints"] = processing_hints
```

`processing_hints` lives at canonical doc top level (not inside `locator`). `locator` stays scoped to provenance/citation.

#### Reporting

`canonical_report.json` gains optional `entry_annotation_summary`:

```json
{
  "entry_annotation_summary": {
    "files_with_entries": 8,
    "files_passthrough_no_eligible_type": 35,    // file matched no content_type's file_match
    "files_passthrough_no_shape_match": 6,        // eligible but shape didn't fire
    "entries_by_type": {"spell": 687, "feat": 158, "skill": 0, "condition": 38},
    "shape_match_failures": [
      {"file": "DivineDomainsandSpells.rtf", "type": "spell", "reason": "no_match"}
    ]
  }
}
```

### 4.5 Chunker mechanics

#### Canonical → chunk flow

```python
def _build_chunks(canonical_doc, *, previous_chunk_id, next_chunk_id) -> list[dict]:
    parent = _build_parent_chunk(canonical_doc, ...)
    if not _should_split(canonical_doc):
        return [parent]
    children = _split_into_children(canonical_doc, parent["chunk_id"])
    return [parent] + children

def _split_into_children(canonical_doc, parent_chunk_id) -> list[dict]:
    content = canonical_doc["content"]
    cuts = canonical_doc.get("processing_hints", {}).get("structure_cuts", [])

    # 1. Apply structure cuts in order — each produces one child of declared kind.
    children = []
    cursor = 0
    for cut in cuts:
        child_content = content[cursor:cut["char_offset"]]
        # Minimal newline normalization only — preserve precise slice semantics.
        child_content = child_content.rstrip("\n").lstrip("\n")
        if child_content:
            children.append(_make_child(
                canonical_doc, parent_chunk_id,
                child_content, cut["child_chunk_type"],
                split_origin="structure_cut",
            ))
        cursor = cut["char_offset"]

    # 2. Remaining content splits at paragraph boundaries.
    children.extend(_paragraph_group_children(
        canonical_doc, parent_chunk_id, content[cursor:],
        split_origin="paragraph_group",
    ))

    _wire_sibling_adjacency(children)
    return children
```

Parent's `chunk_type`:
- If `processing_hints.chunk_type_hint` present → use directly.
- Else → today's `classify_chunk_type(section_path, content)` heuristic.

Children: `chunk_type` from `cut.child_chunk_type` for structure cuts, `"paragraph_group"` for fallback. Each child record carries `split_origin: "structure_cut" | "paragraph_group"` for diagnostics.

#### `char_offset` semantics (operational definition)

This is the critical contract for the canonical → chunk handoff:

- **Basis**: Python `str` index into `canonical_doc["content"]`. Not byte offset, not codepoint offset, not anything else. `content[0:char_offset]` returns the content up to (exclusive) `char_offset`.
- **Computation upstream**: the annotator computes block-to-content offsets as it materializes section content. Section content is built by `"\n".join(block.text.strip() for block in section_blocks)` (matches today's sectioning behavior). For each annotated entry, `stat_block_end` = `len(joined_content_up_to_and_including_last_stat_field_block)` — i.e., the offset just past the last `\n` that precedes the first non-stat-field block.
- **Cut semantics**: `content[cursor:char_offset]` is the previous child's content; `content[char_offset:]` continues into the next region. Cuts are non-overlapping and strictly increasing.
- **Newline normalization in chunker**: `.rstrip("\n").lstrip("\n")` only. No `.strip()`, no whitespace trimming inside content. Preserves leading/trailing spaces within the slice.
- **Round-trip test required** (Section 5): `content[0:cut.char_offset]` reconstructed in test must match the expected stat-block text byte-for-byte.

#### `structure_cuts` schema (constrained)

Per Section 5 refinement B, `child_chunk_type` is enum-validated, not free-form:

```json
{
  "structure_cuts": {
    "type": "array",
    "items": {
      "type": "object",
      "required": ["kind", "char_offset", "child_chunk_type"],
      "additionalProperties": false,
      "properties": {
        "kind": {"enum": ["stat_block_end"]},
        "char_offset": {"type": "integer", "minimum": 0},
        "child_chunk_type": {"enum": ["stat_block"]}
      }
    }
  }
}
```

Adding new cut kinds (e.g., `table_end`) extends the enum — explicit schema change, not silent drift.

#### Configurable thresholds

```python
# scripts/chunker/config.py
@dataclass(frozen=True)
class ChunkerConfig:
    child_threshold_chars: int = 6000
    paragraph_group_target_chars: int = 2000
    paragraph_group_max_chars: int = 3000
```

Loaded from `configs/chunker.yaml` if present; defaults otherwise. Per-content-type overrides deferred until corpus data informs the need.

#### Adjacency rules (kept from PR #63 design — sound)

- **Child sibling adjacency** (`previous_chunk_id` / `next_chunk_id` among children of the same parent): genuine content continuity.
- **Parent file-order adjacency**: convenience link only, not semantic.
- Children of one parent do not link to children of an adjacent parent.

Documented in `docs/metadata_contract.md`.

#### Reporting

`chunk_report.json`:

```json
{
  "parent_count": 723,
  "child_count": 412,
  "structure_cut_children": 120,
  "paragraph_group_children": 292,
  "chunks_by_type": {
    "spell_entry": 687, "feat_entry": 158, "stat_block": 120,
    "paragraph_group": 292, "rule_section": 41
  }
}
```

Per-record `split_origin` field on child chunks lets diagnostics trace each child back to its split mechanism.

## 5. Data model / schema changes

Both schemas keep `additionalProperties: false`. New fields are explicit additions to `properties`.

### `schemas/canonical_document.schema.json`

Add optional `processing_hints`:

```json
"processing_hints": {
  "type": "object",
  "additionalProperties": false,
  "properties": {
    "chunk_type_hint": {
      "type": "string",
      "enum": ["spell_entry", "feat_entry", "skill_entry", "condition_entry"]
    },
    "structure_cuts": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["kind", "char_offset", "child_chunk_type"],
        "additionalProperties": false,
        "properties": {
          "kind": {"enum": ["stat_block_end"]},
          "char_offset": {"type": "integer", "minimum": 0},
          "child_chunk_type": {"enum": ["stat_block"]}
        }
      }
    }
  }
}
```

### `schemas/chunk.schema.json`

- Add `stat_block` to `chunk_type` enum (alongside existing `spell_entry`, `feat_entry`, `skill_entry`, `condition_entry`, `paragraph_group`, `class_feature`, etc. — most are already declared).
- Add optional `split_origin`:

```json
"split_origin": {
  "type": "string",
  "enum": ["structure_cut", "paragraph_group"],
  "description": "Optional provenance marker for child chunks indicating which split mechanism produced them"
}
```

### `schemas/content_types.schema.json` (new)

Validates `configs/content_types.yaml`. Top-level array of content_type dicts; per-type required fields (`name`, `category`, `chunk_type`, `shape`); `shape_params` schema dispatches on `shape` value (allOf / if-then). `additionalProperties: false`.

### `examples/`

Add `examples/canonical_document_with_hints.json` and `examples/chunk_with_split_origin.json` showing the new optional fields.

## 6. Key decisions

| Decision | Rationale |
|---|---|
| Detection signals = formatting (font_size, bold) | Edition-agnostic; the source already encodes this; PR #63's vocabulary lists were reverse-engineering thrown-away signal |
| Detection runs on IR before sectioning | Root fix for Codex's BLOCKING bug; eliminates `_recover_consumed_header` band-aid |
| Shape rules use relational predicates | Robust to per-document baseline drift; no absolute `font_size_class == "body"` dependency |
| Type config declarative + bound to shape | Adding a new content type = config entry; `if category == X` branches don't appear in code |
| Annotations bake semantic payload | Downstream never re-imports `ContentTypeConfig`; annotation is the contract |
| Strict conflict semantics (raise on overlap / re-run) | Forces config to be unambiguous by construction; loosening is reversible later |
| `processing_hints` at canonical-doc top level (not in `locator`) | `locator` stays scoped to provenance/citation; processing handoffs are separate concern |
| `structure_cuts` schema-constrained, not free-form | Avoids `processing_hints` becoming an unconstrained metadata channel |
| Schema deltas are explicit (`additionalProperties: false` preserved) | Per project feedback: "strict schema + optional extras" is not a real contract |

## 7. Alternatives considered

### A. Pure shape detection without decoder change

Stay above IR; detect entries from text shape and stat-block punctuation patterns only. **Rejected**: the structural signal (font-size step-down, bold-prefix) is in the source RTF; reverse-engineering it from text is the same anti-pattern as PR #63's vocabulary lists, just with regex instead of word lists.

### B. Per-run formatting through entire pipeline

Decoder produces `list[TextSpan]`; spans flow through IR, sectioning, chunker. **Rejected**: bigger blast radius, every consumer's signature changes. Per-block summary fields capture 80% of the value at 20% of the surface area.

### C. Filename-routed detection (`file_match` as primary router)

Each file matches at most one content_type via filename glob; the bound shape runs. **Rejected** (per user pushback in design discussion): regresses to a softer form of hardcoding — routing logic in filenames instead of vocabulary in code. `file_match` is a safety rail, not a router; shapes match on block patterns.

### D. Single mega-PR

Land everything in one commit. **Rejected**: unreviewable. Decoder + IR + annotator + pipeline + boundary filter + chunker + schemas in one diff.

## 8. Risks and open questions

1. **`DivineDomainsandSpells.rtf`** plausibly mixes divine-domain entries (shape unverified) with spells. Multi-claim architecture supports it; need PR 1 spike on real corpus before committing the file to multiple types.
2. **Document baseline detection on stat-block-heavy files**: relational predicates make shape rules baseline-independent, but `font_size_class` (kept for diagnostics) could still mislabel. Acceptable since no rule depends on it.
3. **`stat_block` chunk type contract** must be validated by issue #50 (chunk-type prior) and issue #46 (structure metadata indexing) before PR 4 lands. Coordination required.
4. **Class features and magic items** need a third shape rule (deferred). Architecture absorbs additively.
5. **`BOILERPLATE_PHRASES` cleanup in `boundary_filter.py`** is in scope (per Section 1 discussion): site-specific WotC strings move to per-source manifest as `boilerplate_phrases` field. Implemented in PR 3.
6. **Per-type chunker thresholds** deferred until corpus data shows the need.
7. **Char-offset round-trip integrity** depends on the upstream block-to-content join being byte-stable across runs. Test required (Section 5).

## 9. Next steps — delivery plan

Four PRs, bottom-up. Each leaves master in a working state.

| PR | Scope | Risk | Schema change | Behavioral change |
|---|---|---|---|---|
| **PR 1** | Decoder spans + IR formatting fields + pipeline call-site swap | Low | None | None |
| **PR 2** | `content_types.yaml` + schema + entry annotator (NOT wired) | Low | New `content_types.schema.json` | None |
| **PR 3** | Pipeline integration: annotator wired, sectioning two-path, boundary filter cleanup, canonical emission with `processing_hints`, new entry fixtures, `BOILERPLATE_PHRASES` to manifest | High | `canonical_document.schema.json` adds `processing_hints` | Entry-bearing canonical docs change shape |
| **PR 4** | Chunker structure-cuts + thresholds config + `chunk.schema.json` updates + chunker reporting | Medium | `chunk.schema.json` adds `stat_block`, `split_origin` | Entry chunks change shape |

Detailed tasks/files per PR are in the implementation plan: `docs/plans/2026-04-23-chunker-rewrite-formatting-aware-implementation.md`.

### Coordination

- **Issue #50, #46**: confirm consumers of new chunk types and `parent_chunk_id` are ready before PR 4 merge.
- **GitHub issue**: file a parent issue (or update #60) for this rewrite scope; sub-issues per PR optional.
- **Old PR #63**: close after PR 3 merges; design + plan docs from that PR are superseded by this design.
