"""Load the Phase 1 gold set YAML into ``GoldCase`` records."""
from __future__ import annotations

from pathlib import Path

import yaml

from .contracts import GoldCase

_REQUIRED_FIELDS: tuple[str, ...] = (
    "eval_id",
    "question",
    "question_type",
    "expected_source_ids",
    "expected_section_or_entry",
    "expected_behavior",
    "expected_answer_notes",
)


def load_gold_set(path: Path) -> tuple[GoldCase, ...]:
    """Parse a gold-set YAML file into a tuple of ``GoldCase``."""
    payload = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    cases_raw = payload.get("cases", []) if isinstance(payload, dict) else []
    cases: list[GoldCase] = []
    for index, raw in enumerate(cases_raw):
        if not isinstance(raw, dict):
            raise ValueError(f"Case at index {index} is not a mapping")
        for field in _REQUIRED_FIELDS:
            if field not in raw:
                eval_id = raw.get("eval_id", f"<index {index}>")
                raise ValueError(
                    f"Case {eval_id} is missing required field '{field}'"
                )
        cases.append(
            GoldCase(
                eval_id=str(raw["eval_id"]),
                question=str(raw["question"]),
                question_type=str(raw["question_type"]),
                expected_source_ids=tuple(raw["expected_source_ids"] or ()),
                expected_section_or_entry=tuple(
                    raw["expected_section_or_entry"] or ()
                ),
                expected_behavior=raw["expected_behavior"],
                expected_answer_notes=str(raw["expected_answer_notes"]),
            )
        )
    return tuple(cases)
