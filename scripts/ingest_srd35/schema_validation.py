from __future__ import annotations

import json
from pathlib import Path


def _load_schema(schema_root: Path) -> tuple[dict, dict]:
    canonical_path = schema_root / "canonical_document.schema.json"
    common_path = schema_root / "common.schema.json"
    return (
        json.loads(canonical_path.read_text(encoding="utf-8")),
        json.loads(common_path.read_text(encoding="utf-8")),
    )


def _build_resolver_store(schema_root: Path, common_schema: dict) -> dict:
    common_uri = (schema_root / "common.schema.json").resolve().as_uri()
    return {
        common_uri: common_schema,
        "./common.schema.json": common_schema,
        "common.schema.json": common_schema,
    }


def validate_canonical_docs(
    canonical_docs: list[dict],
    repo_root: Path,
    *,
    require_validation: bool,
) -> dict:
    try:
        import jsonschema
    except ImportError as exc:
        if require_validation:
            raise RuntimeError(
                "jsonschema package is required for canonical schema validation. "
                "Install it and rerun with --require-schema-validation."
            ) from exc
        return {"enabled": False, "validated_count": 0}

    schema_root = repo_root / "schemas"
    canonical_schema, common_schema = _load_schema(schema_root)
    resolver = jsonschema.RefResolver.from_schema(
        canonical_schema,
        store=_build_resolver_store(schema_root, common_schema),
    )

    validator = jsonschema.Draft7Validator(canonical_schema, resolver=resolver)
    for doc in canonical_docs:
        validator.validate(doc)

    return {"enabled": True, "validated_count": len(canonical_docs)}
