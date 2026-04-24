"""Support assessor: strict-signal abstain gate.

Implements §3.2 of the minimal-answer-path design. The assessor inspects the
top evidence item in the pack and decides whether the answer pipeline should
produce a grounded answer or abstain. ``token_overlap_count`` alone does not
license a grounded answer; at least one of ``exact_phrase_hits``,
``protected_phrase_hits``, or ``section_path_hit`` must be present.
"""
from __future__ import annotations

from scripts.retrieval.evidence_pack import EvidencePack

from .contracts import AssessmentResult


def assess_support(pack: EvidencePack) -> AssessmentResult:
    """Decide whether the pack's top item has strong enough signals to answer."""
    if not pack.evidence:
        return AssessmentResult(outcome="abstain", trigger_code="empty_evidence")

    signals = pack.evidence[0].match_signals
    has_strong_signal = (
        bool(signals["exact_phrase_hits"])
        or bool(signals["protected_phrase_hits"])
        or signals["section_path_hit"]
    )
    if not has_strong_signal:
        return AssessmentResult(outcome="abstain", trigger_code="weak_signals")

    return AssessmentResult(outcome="grounded", trigger_code=None)
