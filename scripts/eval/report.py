"""Build, serialize, and render evaluation reports."""
from __future__ import annotations

import datetime as _dt
import json
import textwrap
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .contracts import CaseOutcome, EvalReport


# Keep this in sync with scripts.eval.tagger._TAG_ORDER.
_TAG_ORDER: tuple[str, ...] = (
    "retrieval_miss",
    "wrong_section",
    "wrong_entry",
    "citation_mismatch",
    "unsupported_inference",
    "missing_abstain",
    "unnecessary_abstain",
    "edition_boundary_failure",
)


def build_report(
    cases: tuple[CaseOutcome, ...],
    *,
    dataset_id: str,
    run_started_at: str | None = None,
) -> EvalReport:
    """Aggregate per-case outcomes into the full ``EvalReport``."""
    tag_counts: dict[str, int] = {tag: 0 for tag in _TAG_ORDER}
    clean = 0
    behavior_match = 0
    for outcome in cases:
        if not outcome.tags:
            clean += 1
        for tag in outcome.tags:
            tag_counts[tag] = tag_counts.get(tag, 0) + 1
        expected_grounded = outcome.expected_behavior != "abstain"
        actual_grounded = outcome.actual_answer_type == "grounded"
        if expected_grounded == actual_grounded:
            behavior_match += 1
    tag_counts["_clean"] = clean

    behavior_match_rate = round(behavior_match / len(cases), 2) if cases else 0.0
    return EvalReport(
        dataset_id=dataset_id,
        run_started_at=run_started_at or _now_iso(),
        case_count=len(cases),
        tag_counts=tag_counts,
        behavior_match_rate=behavior_match_rate,
        cases=cases,
    )


def _now_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def write_json(report: EvalReport, path: Path) -> None:
    """Serialize ``report`` to JSON at ``path``."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = _report_to_dict(report)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _report_to_dict(report: EvalReport) -> dict[str, Any]:
    return {
        "dataset_id": report.dataset_id,
        "run_started_at": report.run_started_at,
        "case_count": report.case_count,
        "tag_counts": dict(report.tag_counts),
        "behavior_match_rate": report.behavior_match_rate,
        "cases": [_case_to_dict(c) for c in report.cases],
    }


def _case_to_dict(case: CaseOutcome) -> dict[str, Any]:
    payload = asdict(case)
    # Tuples round-trip to lists via asdict already; nothing to fix.
    return payload


def format_tag_counts(report: EvalReport) -> str:
    """Render the tag-count table (plus clean total) for stdout."""
    lines: list[str] = []
    lines.append(f"Dataset:       {report.dataset_id}")
    lines.append(f"Cases:         {report.case_count}")
    lines.append(f"Behavior match rate: {report.behavior_match_rate:.2f}")
    lines.append("")
    lines.append("Tag counts:")
    width = max(len(tag) for tag in _TAG_ORDER)
    for tag in _TAG_ORDER:
        count = report.tag_counts.get(tag, 0)
        lines.append(f"  {tag.ljust(width)}  {count}")
    lines.append(f"  {'_clean'.ljust(width)}  {report.tag_counts.get('_clean', 0)}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Markdown
# ---------------------------------------------------------------------------


def write_markdown(report: EvalReport, path: Path) -> None:
    """Render the human-facing Markdown report at ``path``."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_render_markdown(report), encoding="utf-8")


def _render_markdown(report: EvalReport) -> str:
    parts: list[str] = []
    parts.append(f"# Phase 1 Gold-Set Eval — {report.dataset_id}")
    parts.append("")
    parts.append(f"- **Run started:** {report.run_started_at}")
    parts.append(f"- **Cases:** {report.case_count}")
    parts.append(f"- **Behavior match rate:** {report.behavior_match_rate:.2f}")
    parts.append("")
    parts.append("## Tag counts")
    parts.append("")
    parts.append("| tag | count |")
    parts.append("|---|---|")
    for tag in _TAG_ORDER:
        parts.append(f"| `{tag}` | {report.tag_counts.get(tag, 0)} |")
    parts.append(f"| `_clean` | {report.tag_counts.get('_clean', 0)} |")
    parts.append("")

    failing = [c for c in report.cases if c.tags]
    clean = [c for c in report.cases if not c.tags]

    parts.append("## Failing cases")
    parts.append("")
    if not failing:
        parts.append("_No failing cases._")
        parts.append("")
    else:
        # Group by primary (first) tag in §3.2 order, but each case is shown once.
        grouped: dict[str, list[CaseOutcome]] = {tag: [] for tag in _TAG_ORDER}
        for c in failing:
            primary_tag = c.tags[0]
            grouped.setdefault(primary_tag, []).append(c)
        for tag in _TAG_ORDER:
            cases_for_tag = grouped.get(tag, [])
            if not cases_for_tag:
                continue
            parts.append(f"### Tag: `{tag}`")
            parts.append("")
            for case in cases_for_tag:
                parts.extend(_render_case_block(case))
                parts.append("")

    parts.append("## Clean tail")
    parts.append("")
    if clean:
        ids = ", ".join(c.eval_id for c in clean)
        parts.append(f"_{len(clean)} clean cases ({ids})_")
    else:
        parts.append("_No clean cases._")
    parts.append("")
    return "\n".join(parts)


def _render_case_block(case: CaseOutcome) -> list[str]:
    lines: list[str] = []
    lines.append(
        f"#### {case.eval_id} — {case.question_type} → {case.expected_behavior}"
    )
    lines.append("")
    lines.append(f"**Question:** {case.question}")
    lines.append("")
    if case.tags:
        tag_md = ", ".join(f"`{t}`" for t in case.tags)
        lines.append(f"**Tags:** {tag_md}")
    else:
        lines.append("**Tags:** _(clean)_")
    lines.append("")

    lines.append(
        f"**Actual:** {case.actual_answer_type} · "
        f"primary support: {case.actual_summary.primary_support_type or 'n/a'}"
    )
    if case.actual_summary.primary_excerpt:
        excerpt = textwrap.shorten(
            case.actual_summary.primary_excerpt, width=200, placeholder="…"
        )
        lines.append(f"> {excerpt}")
    elif case.actual_summary.abstention_reason:
        lines.append(f"> _abstain: {case.actual_summary.abstention_reason}_")
    lines.append("")

    if case.citation_checks:
        lines.append("**Citations:**")
        lines.append("")
        lines.append(
            "| id | source · edition | section_path | source | section | entry | tokens shared |"
        )
        lines.append("|----|-----|-----|---|---|---|---|")
        # Map citation_id → CitationSummary for display.
        summaries = {c.citation_id: c for c in case.actual_summary.citations}
        for chk in case.citation_checks:
            summary = summaries.get(chk.citation_id)
            if summary is not None:
                source_label = f"{summary.source_id} · {summary.edition}"
                section_path_display = (
                    " > ".join(summary.section_path) if summary.section_path else "(none)"
                )
            else:
                source_label = "?"
                section_path_display = "?"
            section_cell = _bool_cell(chk.section_match)
            entry_cell = _bool_cell(chk.entry_match)
            source_cell = "yes" if chk.source_match else "no"
            tokens = list(chk.token_overlap) if chk.token_overlap else []
            lines.append(
                f"| {chk.citation_id} | {source_label} | {section_path_display} | "
                f"{source_cell} | {section_cell} | {entry_cell} | {tokens} |"
            )
    return lines


def _bool_cell(flag: bool | None) -> str:
    if flag is None:
        return "n/a"
    return "yes" if flag else "no"
