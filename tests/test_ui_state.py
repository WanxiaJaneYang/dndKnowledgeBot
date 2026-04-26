from __future__ import annotations

from scripts.ui.state import QueryHistoryEntry, history_entry_to_inputs, push_history_entry


def _entry(query: str, top_k: int = 10) -> QueryHistoryEntry:
    return QueryHistoryEntry(
        query=query,
        top_k=top_k,
        edition="3.5e",
        source_type="srd",
        ran_at="2026-04-26T10:00:00Z",
    )


def test_push_history_entry_prepends_newest_entry():
    history = [_entry("older"), _entry("oldest")]

    updated = push_history_entry(history, _entry("newest"))

    assert [entry.query for entry in updated] == ["newest", "older", "oldest"]


def test_push_history_entry_caps_at_limit():
    history = [_entry(f"q{i}") for i in range(20)]

    updated = push_history_entry(history, _entry("latest"), limit=20)

    assert len(updated) == 20
    assert updated[0].query == "latest"
    assert updated[-1].query == "q18"


def test_history_entry_to_inputs_restores_sidebar_values():
    restored = history_entry_to_inputs(_entry("turn undead", top_k=7))

    assert restored == {
        "query": "turn undead",
        "top_k": 7,
        "edition": "3.5e",
        "source_type": "srd",
    }
