"""Validate chunk objects against chunk.schema.json."""
from __future__ import annotations

import json
from pathlib import Path


def _load_schemas(schema_root: Path) -> tuple[dict, dict]:
    chunk_schema = json.loads((schema_root / "chunk.schema.json").read_text(encoding="utf-8"))
    common_schema = json.loads((schema_root / "common.schema.json").read_text(encoding="utf-8"))
    return chunk_schema, common_schema


def _resolver_store(schema_root: Path, common_schema: dict) -> dict:
    common_uri = (schema_root / "common.schema.json").resolve().as_uri()
    return {
        common_uri: common_schema,
        "./common.schema.json": common_schema,
        "common.schema.json": common_schema,
    }


def validate_chunks(
    chunks: list[dict],
    repo_root: Path,
    *,
    require_validation: bool,
) -> dict:
    if not require_validation:
        return {"enabled": False, "validated_count": 0}

    try:
        import jsonschema
    except ImportError as exc:
        raise RuntimeError(
            "jsonschema package is required for chunk schema validation. "
            "Install it and rerun with --require-schema-validation."
        ) from exc

    schema_root = repo_root / "schemas"
    chunk_schema, common_schema = _load_schemas(schema_root)
    resolver = jsonschema.RefResolver.from_schema(
        chunk_schema,
        store=_resolver_store(schema_root, common_schema),
    )
    validator = jsonschema.Draft7Validator(chunk_schema, resolver=resolver)
    for chunk in chunks:
        validator.validate(chunk)

    return {"enabled": True, "validated_count": len(chunks)}
