"""Citation binder: assigns citation ids and builds Citation records.

Implements §3.4 of the minimal-answer-path design. Deduplicates by the
``(chunk_id, excerpt)`` tuple so two segments quoting the same chunk with
the same excerpt share one ``citation_id``.
"""
from __future__ import annotations

from scripts.retrieval.evidence_pack import EvidencePack

from .composer import _ComposedSegment
from .contracts import AnswerSegment, Citation


def bind_citations(
    composed_segments: tuple[_ComposedSegment, ...],
    pack: EvidencePack,  # noqa: ARG001 — reserved for locator narrowing (policy §5)
) -> tuple[tuple[AnswerSegment, ...], tuple[Citation, ...]]:
    """Attach stable citation ids to segments and build the citations tuple."""
    citations: list[Citation] = []
    citation_ids_by_key: dict[tuple[str, str], str] = {}
    answer_segments: list[AnswerSegment] = []

    for composed in composed_segments:
        item = composed.evidence_item
        key = (item.chunk_id, composed.text)
        citation_id = citation_ids_by_key.get(key)
        if citation_id is None:
            citation_id = f"cit_{len(citations) + 1}"
            citation_ids_by_key[key] = citation_id
            citations.append(
                Citation(
                    citation_id=citation_id,
                    chunk_id=item.chunk_id,
                    source_ref=item.source_ref,
                    locator=item.locator,
                    excerpt=composed.text,
                )
            )

        answer_segments.append(
            AnswerSegment(
                segment_id=composed.segment_id,
                text=composed.text,
                support_type=composed.support_type,
                citation_ids=(citation_id,),
            )
        )

    return tuple(answer_segments), tuple(citations)
