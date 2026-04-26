"""Validates the evidence-pack JSON contract against schemas/evidence_pack.schema.json.

The schema is the canonical handoff format between retrieval and answer
generation. These tests pin three things:

1. The committed example artifact validates.
2. A live debug-CLI JSON payload (built end-to-end via retrieve_evidence
   over a tmp index) validates — guards against drift between the schema
   and the actual code path.
3. A few targeted negative cases: known-bad payloads must fail
   validation, so the schema is actually enforcing the invariants.
"""
from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

from jsonschema import Draft7Validator
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT7

from scripts.retrieval.evidence_pack import retrieve_evidence
from scripts.retrieval.lexical_index import build_chunk_index
from scripts.retrieve_debug import _to_json


_REPO_ROOT = Path(__file__).resolve().parents[1]
_SCHEMAS_DIR = _REPO_ROOT / "schemas"
_EXAMPLES_DIR = _REPO_ROOT / "examples"


def _assert_span_invariants(payload: dict) -> None:
    """Cross-field ID-consistency invariants that JSON Schema can't enforce.

    These are producer-side guarantees from build_evidence_pack — schema
    validation alone is not sufficient for downstream code (e.g. citation
    rendering) that depends on ID consistency. Mirror this helper from
    consumer code paths whenever you load an evidence pack from JSON
    rather than constructing it in-process.
    """
    for i, item in enumerate(payload["evidence"]):
        span = item["span"]
        chunk_ids = span["chunk_ids"]
        path = f"evidence[{i}]"

        assert chunk_ids[0] == span["start_chunk_id"], (
            f"{path}: span.chunk_ids[0]={chunk_ids[0]!r} != "
            f"start_chunk_id={span['start_chunk_id']!r}"
        )
        assert chunk_ids[-1] == span["end_chunk_id"], (
            f"{path}: span.chunk_ids[-1]={chunk_ids[-1]!r} != "
            f"end_chunk_id={span['end_chunk_id']!r}"
        )

        if span["merge_reason"] == "singleton":
            assert chunk_ids == [item["chunk_id"]], (
                f"{path}: singleton span.chunk_ids={chunk_ids!r} != "
                f"[chunk_id={item['chunk_id']!r}]"
            )


def _make_validator() -> Draft7Validator:
    main = json.loads(
        (_SCHEMAS_DIR / "evidence_pack.schema.json").read_text(encoding="utf-8")
    )
    common = json.loads(
        (_SCHEMAS_DIR / "common.schema.json").read_text(encoding="utf-8")
    )
    common_resource = Resource.from_contents(common, default_specification=DRAFT7)
    registry = Registry().with_resources(
        [
            ("./common.schema.json", common_resource),
            ("common.schema.json", common_resource),
        ]
    )
    return Draft7Validator(main, registry=registry)


def _aoo_chunk(chunk_id: str, content: str, **extra: object) -> dict:
    chunk = {
        "chunk_id": chunk_id,
        "document_id": "srd_35::combat",
        "source_ref": {
            "source_id": "srd_35",
            "title": "System Reference Document",
            "edition": "3.5e",
            "source_type": "srd",
            "authority_level": "official_reference",
        },
        "locator": {
            "section_path": ["Combat", "Attack of Opportunity"],
            "source_location": "Combat.rtf#001",
        },
        "chunk_type": "rule_section",
        "content": content,
    }
    chunk.update(extra)
    return chunk


# ---------------------------------------------------------------------------
# The committed example must validate
# ---------------------------------------------------------------------------


def test_committed_example_validates():
    """examples/evidence_pack.example.json must validate against the schema.

    If this fails, either the example was not regenerated after a schema
    change, or the schema is wrong.
    """
    payload = json.loads(
        (_EXAMPLES_DIR / "evidence_pack.example.json").read_text(encoding="utf-8")
    )
    errors = list(_make_validator().iter_errors(payload))
    assert errors == [], f"Example failed validation:\n  " + "\n  ".join(
        f"{list(err.absolute_path)}: {err.message}" for err in errors
    )


def test_committed_example_passes_runtime_invariants():
    """The committed example must also satisfy the cross-field ID
    consistency invariants the schema cannot express."""
    payload = json.loads(
        (_EXAMPLES_DIR / "evidence_pack.example.json").read_text(encoding="utf-8")
    )
    _assert_span_invariants(payload)


# ---------------------------------------------------------------------------
# Live debug-CLI output must validate
# ---------------------------------------------------------------------------


def test_live_to_json_output_validates_singleton(tmp_path):
    """A real retrieve_evidence -> _to_json round-trip validates."""
    chunk_path = tmp_path / "aoo.json"
    chunk_path.write_text(
        json.dumps(_aoo_chunk(
            "chunk::srd_35::combat::001_aoo",
            "An attack of opportunity is a single melee attack.",
        )),
        encoding="utf-8",
    )
    db_path = tmp_path / "retrieval.db"
    build_chunk_index(db_path, [chunk_path])

    pack = retrieve_evidence("attack of opportunity", db_path=db_path, top_k=5)
    payload = _to_json(pack)

    errors = list(_make_validator().iter_errors(payload))
    assert errors == [], f"Live output failed validation:\n  " + "\n  ".join(
        f"{list(err.absolute_path)}: {err.message}" for err in errors
    )


def test_live_to_json_output_passes_runtime_invariants(tmp_path):
    """A live retrieve_evidence -> _to_json round-trip also satisfies the
    runtime ID-consistency invariants. Pins build_evidence_pack's producer
    behaviour."""
    chunk_path = tmp_path / "aoo.json"
    chunk_path.write_text(
        json.dumps(_aoo_chunk(
            "chunk::srd_35::combat::001_aoo",
            "An attack of opportunity is a single melee attack.",
        )),
        encoding="utf-8",
    )
    db_path = tmp_path / "retrieval.db"
    build_chunk_index(db_path, [chunk_path])

    pack = retrieve_evidence("attack of opportunity", db_path=db_path, top_k=5)
    payload = _to_json(pack)
    _assert_span_invariants(payload)


def test_live_to_json_output_validates_adjacent_span(tmp_path):
    """A multi-chunk adjacent_span end-to-end also validates."""
    a = _aoo_chunk(
        "chunk::srd_35::combat::001_a",
        "Attack of opportunity first half — the trigger conditions.",
        next_chunk_id="chunk::srd_35::combat::002_b",
    )
    b = _aoo_chunk(
        "chunk::srd_35::combat::002_b",
        "Attack of opportunity second half — the damage resolution.",
        previous_chunk_id="chunk::srd_35::combat::001_a",
    )
    path_a = tmp_path / "a.json"
    path_b = tmp_path / "b.json"
    path_a.write_text(json.dumps(a), encoding="utf-8")
    path_b.write_text(json.dumps(b), encoding="utf-8")
    db_path = tmp_path / "retrieval.db"
    build_chunk_index(db_path, [path_a, path_b])

    pack = retrieve_evidence("attack of opportunity", db_path=db_path, top_k=5)
    payload = _to_json(pack)

    # Sanity: the two chunks did consolidate into one adjacent_span item.
    assert len(payload["evidence"]) == 1
    assert payload["evidence"][0]["span"]["merge_reason"] == "adjacent_span"

    errors = list(_make_validator().iter_errors(payload))
    assert errors == [], f"Live output failed validation:\n  " + "\n  ".join(
        f"{list(err.absolute_path)}: {err.message}" for err in errors
    )


# ---------------------------------------------------------------------------
# Negative cases — schema must reject these
# ---------------------------------------------------------------------------


def _good_payload() -> dict:
    """Returns a freshly-loaded copy of the example for mutation in tests."""
    return json.loads(
        (_EXAMPLES_DIR / "evidence_pack.example.json").read_text(encoding="utf-8")
    )


def test_rejects_missing_top_level_key():
    payload = _good_payload()
    del payload["trace"]
    errors = list(_make_validator().iter_errors(payload))
    assert errors, "schema should reject payload missing 'trace'"


def test_rejects_unknown_top_level_key():
    payload = _good_payload()
    payload["surprise"] = "extra"
    errors = list(_make_validator().iter_errors(payload))
    assert errors, "schema should reject unknown top-level keys (additionalProperties: false)"


def test_rejects_invalid_chunk_type():
    payload = _good_payload()
    payload["evidence"][0]["chunk_type"] = "not_a_real_type"
    errors = list(_make_validator().iter_errors(payload))
    assert errors, "schema should reject chunk_type values outside the enum"


def test_rejects_invalid_merge_reason():
    payload = _good_payload()
    payload["evidence"][0]["span"]["merge_reason"] = "near_duplicate"  # not yet valid
    errors = list(_make_validator().iter_errors(payload))
    assert errors, "schema should reject merge_reason values outside the current enum"


def test_rejects_singleton_with_multiple_chunk_ids():
    """Conditional invariant: merge_reason='singleton' implies chunk_ids has length 1."""
    payload = _good_payload()
    item = payload["evidence"][0]
    item["span"]["merge_reason"] = "singleton"
    item["span"]["chunk_ids"] = ["a", "b"]
    item["span"]["start_chunk_id"] = "a"
    item["span"]["end_chunk_id"] = "b"
    errors = list(_make_validator().iter_errors(payload))
    assert errors, "schema should reject singleton spans with len(chunk_ids) > 1"


def test_rejects_adjacent_span_with_single_chunk_id():
    """Conditional invariant: merge_reason='adjacent_span' implies chunk_ids has length >= 2."""
    payload = _good_payload()
    item = payload["evidence"][0]
    item["span"]["merge_reason"] = "adjacent_span"
    # leave chunk_ids at length 1
    errors = list(_make_validator().iter_errors(payload))
    assert errors, "schema should reject adjacent_span with single-element chunk_ids"


def test_rejects_negative_token_overlap_count():
    payload = _good_payload()
    payload["evidence"][0]["match_signals"]["token_overlap_count"] = -1
    errors = list(_make_validator().iter_errors(payload))
    assert errors, "schema should reject negative token_overlap_count"


def test_rejects_rank_zero():
    payload = _good_payload()
    payload["evidence"][0]["rank"] = 0
    errors = list(_make_validator().iter_errors(payload))
    assert errors, "schema should reject rank < 1"


def test_rejects_unknown_nested_key():
    """additionalProperties: false applies at every level — extra keys
    inside nested objects must also be rejected."""
    payload = _good_payload()
    payload["evidence"][0]["span"]["surprise"] = "extra"
    errors = list(_make_validator().iter_errors(payload))
    assert errors, "schema should reject unknown keys nested inside span"


# ---------------------------------------------------------------------------
# Runtime invariants — cross-field ID consistency that JSON Schema can't enforce
# ---------------------------------------------------------------------------


def test_invariants_reject_singleton_with_mismatched_chunk_id():
    """Singleton item where chunk_id doesn't match span.chunk_ids[0].

    This is the case the auto-review flagged: schema-passes-but-broken.
    The schema (length-only) accepts it; the runtime helper must reject."""
    payload = _good_payload()
    item = payload["evidence"][0]
    # Force a singleton-shaped span with mismatched representative chunk_id.
    item["span"]["merge_reason"] = "singleton"
    item["span"]["chunk_ids"] = ["other_chunk"]
    item["span"]["start_chunk_id"] = "other_chunk"
    item["span"]["end_chunk_id"] = "other_chunk"
    # item["chunk_id"] left as the original real chunk_id from the example.

    # Schema validation passes (this is the gap).
    assert list(_make_validator().iter_errors(payload)) == []

    # Runtime invariants do NOT.
    try:
        _assert_span_invariants(payload)
    except AssertionError as err:
        assert "singleton" in str(err)
    else:
        raise AssertionError(
            "_assert_span_invariants should have rejected mismatched singleton IDs"
        )


def test_invariants_reject_chunk_ids_first_not_equal_start():
    """span.chunk_ids[0] must equal start_chunk_id."""
    payload = _good_payload()
    item = payload["evidence"][0]
    item["span"]["chunk_ids"] = ["unrelated"]
    item["span"]["start_chunk_id"] = "different"
    item["span"]["end_chunk_id"] = "unrelated"
    # Make merge_reason 'adjacent_span' so this isn't also a singleton failure;
    # length still 1 so schema rejects it under the singleton/adjacent-span
    # conditional. Use a 2-element form to isolate the chunk_ids[0] vs
    # start_chunk_id check.
    item["span"]["chunk_ids"] = ["unrelated", item["span"]["end_chunk_id"]]
    item["span"]["merge_reason"] = "adjacent_span"

    try:
        _assert_span_invariants(payload)
    except AssertionError as err:
        assert "chunk_ids[0]" in str(err)
    else:
        raise AssertionError(
            "_assert_span_invariants should reject chunk_ids[0] != start_chunk_id"
        )


def test_invariants_reject_chunk_ids_last_not_equal_end():
    """span.chunk_ids[-1] must equal end_chunk_id."""
    payload = _good_payload()
    item = payload["evidence"][0]
    item["span"]["chunk_ids"] = [item["span"]["start_chunk_id"], "unrelated_end"]
    item["span"]["merge_reason"] = "adjacent_span"
    # end_chunk_id intentionally not updated to match chunk_ids[-1].

    try:
        _assert_span_invariants(payload)
    except AssertionError as err:
        assert "chunk_ids[-1]" in str(err)
    else:
        raise AssertionError(
            "_assert_span_invariants should reject chunk_ids[-1] != end_chunk_id"
        )
