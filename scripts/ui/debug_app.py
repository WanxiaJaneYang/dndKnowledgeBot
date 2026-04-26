from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
import sys
from typing import Any

import streamlit as st

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from scripts.answer.citation_binder import bind_citations
from scripts.answer.composer import compose_segments_with_decisions
from scripts.answer.contracts import Abstention, GroundedAnswer
from scripts.answer.pipeline import build_answer, to_debug_json
from scripts.answer.support_assessor import assess_support
from scripts.retrieval.candidate_consolidation import consolidate_adjacent
from scripts.retrieval.candidate_shaping import shape_candidates
from scripts.retrieval.contracts import NormalizedQuery
from scripts.retrieval.evidence_pack import retrieve_evidence
from scripts.retrieval.filters import build_constraints
from scripts.retrieval.lexical_retriever import DEFAULT_DB_PATH, retrieve_lexical
from scripts.retrieval.query_normalization import normalize_query
from scripts.ui.panels import (
    format_answer_segments,
    format_candidate_rows,
    format_citation_rows,
    format_slot_decision_rows,
)
from scripts.ui.state import QueryHistoryEntry, history_entry_to_inputs, push_history_entry


st.set_page_config(page_title="D&D 3.5 Debug UI", layout="wide")

_DB_PATH = DEFAULT_DB_PATH
_DEFAULT_MODE = "Debug"
_DEFAULT_TOP_K = 10
_DEFAULT_EDITION = "3.5e"
_DEFAULT_SOURCE_TYPE = "srd"


def main() -> None:
    _ensure_state()

    st.title("D&D 3.5 Retrieval / Answer Debug UI")
    st.caption("Local-only inspection UI for the lexical retrieval and v1 answer pipeline.")

    if not _DB_PATH.exists():
        _render_missing_index()
        return

    run_requested = _render_sidebar()

    with st.form("query_form"):
        st.text_input("Query", key="query_text", placeholder="attack of opportunity")
        submitted = st.form_submit_button("Run")

    if submitted:
        run_requested = True

    if run_requested:
        query = st.session_state["query_text"].strip()
        if query:
            st.session_state["last_run"] = _run_pipeline(
                query=query,
                top_k=st.session_state["top_k"],
                db_path=_DB_PATH,
            )
            entry = QueryHistoryEntry(
                query=query,
                top_k=st.session_state["top_k"],
                edition=st.session_state["edition"],
                source_type=st.session_state["source_type"],
                ran_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            )
            st.session_state["query_history"] = push_history_entry(
                st.session_state["query_history"],
                entry,
            )

    result_bundle = st.session_state.get("last_run")
    if result_bundle is not None:
        _render_answer_panel(result_bundle)
        if st.session_state["mode"] == "Debug":
            _render_debug_panels(result_bundle)
    else:
        st.info("Enter a query and press Run to inspect the pipeline.")


def _ensure_state() -> None:
    st.session_state.setdefault("mode", _DEFAULT_MODE)
    st.session_state.setdefault("top_k", _DEFAULT_TOP_K)
    st.session_state.setdefault("edition", _DEFAULT_EDITION)
    st.session_state.setdefault("source_type", _DEFAULT_SOURCE_TYPE)
    st.session_state.setdefault("query_text", "")
    st.session_state.setdefault("query_history", [])
    st.session_state.setdefault("last_run", None)


def _render_sidebar() -> bool:
    run_requested = False
    with st.sidebar:
        st.header("Controls")
        st.radio("Mode", options=["User", "Debug"], key="mode", horizontal=True)
        st.slider("top_k", min_value=1, max_value=25, key="top_k")
        st.selectbox("edition", options=[_DEFAULT_EDITION], key="edition", disabled=True)
        st.selectbox(
            "source_type",
            options=[_DEFAULT_SOURCE_TYPE],
            key="source_type",
            disabled=True,
        )
        st.text_input("DB path", value=str(_DB_PATH), disabled=True)

        st.divider()
        st.subheader("Query history")
        if not st.session_state["query_history"]:
            st.caption("No queries in this session yet.")
        for index, entry in enumerate(st.session_state["query_history"]):
            label = entry.query if len(entry.query) <= 32 else f"{entry.query[:29]}..."
            if st.button(label, key=f"history_{index}", use_container_width=True):
                restored = history_entry_to_inputs(entry)
                st.session_state["query_text"] = restored["query"]
                st.session_state["top_k"] = restored["top_k"]
                st.session_state["edition"] = restored["edition"]
                st.session_state["source_type"] = restored["source_type"]
                run_requested = True
            st.caption(entry.ran_at)
    return run_requested


def _render_missing_index() -> None:
    st.error(f"Chunk index not found at `{_DB_PATH}`.")
    st.write("Build the lexical index first:")
    st.code("python scripts/chunk_srd_35.py")


def _run_pipeline(*, query: str, top_k: int, db_path: Path) -> dict[str, Any]:
    normalization_payload = normalize_query(query)
    normalized_query = NormalizedQuery.from_query_normalization(normalization_payload)
    constraints = build_constraints()
    candidates = retrieve_lexical(
        normalized_query,
        constraints=constraints,
        db_path=db_path,
        top_k=top_k,
    )
    groups = shape_candidates(candidates)
    span_groups = consolidate_adjacent(groups)

    pack = retrieve_evidence(query, db_path=db_path, top_k=top_k)
    assessment = assess_support(pack)
    result = build_answer(pack)

    composed_segments: tuple[Any, ...] = ()
    slot_decisions: tuple[Any, ...] = ()
    bound_segments: tuple[Any, ...] = ()
    citations: tuple[Any, ...] = ()
    if isinstance(result, GroundedAnswer) and assessment.outcome == "grounded":
        composed_segments, slot_decisions = compose_segments_with_decisions(pack)
        bound_segments, citations = bind_citations(composed_segments, pack)

    return {
        "normalization": normalization_payload,
        "constraints": pack.constraints_summary,
        "candidates": candidates,
        "groups": groups,
        "span_groups": span_groups,
        "evidence_pack": pack,
        "assessment": assessment,
        "result": result,
        "composed_segments": composed_segments,
        "slot_decisions": slot_decisions,
        "bound_segments": bound_segments,
        "citations": citations,
        "debug_payload": to_debug_json(result, pack, composed_segments),
    }


def _render_answer_panel(bundle: dict[str, Any]) -> None:
    result = bundle["result"]
    st.subheader("Answer")
    if isinstance(result, Abstention):
        st.warning(f"{result.reason} ({result.trigger_code})")
        return

    segment_rows = format_answer_segments(result.segments)
    for row in segment_rows:
        st.markdown(
            f"**{row['segment_id']}** `{row['support_type']}` {row['citations']}\n\n{row['text']}"
        )

    st.markdown("**Citations**")
    st.table(format_citation_rows(result.citations))


def _render_debug_panels(bundle: dict[str, Any]) -> None:
    with st.expander("Query normalization", expanded=False):
        st.json(bundle["normalization"], expanded=False)

    with st.expander("Constraints", expanded=False):
        st.json(bundle["constraints"], expanded=False)

    with st.expander("Top-k candidates", expanded=False):
        st.table(format_candidate_rows(bundle["candidates"]))

    with st.expander("Candidate shaping groups", expanded=False):
        st.json(
            [
                {
                    "document_id": group.document_id,
                    "section_root": group.section_root,
                    "best_rank": group.best_rank,
                    "candidate_chunk_ids": [candidate.chunk_id for candidate in group.candidates],
                }
                for group in bundle["groups"]
            ],
            expanded=False,
        )
        st.json(
            [
                {
                    "document_id": group.document_id,
                    "section_root": group.section_root,
                    "spans": [
                        {
                            "representative_chunk_id": span.representative.chunk_id,
                            "chunk_ids": list(span.chunk_ids),
                            "merge_reason": span.merge_reason,
                        }
                        for span in group.spans
                    ],
                }
                for group in bundle["span_groups"]
            ],
            expanded=False,
        )

    with st.expander("Evidence pack", expanded=False):
        st.json(_to_jsonable(bundle["evidence_pack"]), expanded=False)

    with st.expander("Support assessment", expanded=False):
        st.json(_to_jsonable(bundle["assessment"]), expanded=False)

    with st.expander("Composer slot decisions", expanded=False):
        if bundle["slot_decisions"]:
            st.table(format_slot_decision_rows(bundle["slot_decisions"]))
        else:
            st.info("No slot decisions recorded because the answer abstained.")

    with st.expander("Citation binding", expanded=False):
        if bundle["bound_segments"]:
            st.markdown("**Bound segments**")
            st.table(format_answer_segments(bundle["bound_segments"]))
            st.markdown("**Bound citations**")
            st.table(format_citation_rows(bundle["citations"]))
        else:
            st.info("No citation binding output because the answer abstained.")

    with st.expander("Raw --json-debug output", expanded=False):
        st.json(bundle["debug_payload"], expanded=False)


def _to_jsonable(value: Any) -> Any:
    if is_dataclass(value):
        return {key: _to_jsonable(item) for key, item in asdict(value).items()}
    if isinstance(value, dict):
        return {key: _to_jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_jsonable(item) for item in value]
    return value


if __name__ == "__main__":
    main()
