from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class QueryHistoryEntry:
    query: str
    top_k: int
    edition: str
    source_type: str
    ran_at: str


def push_history_entry(
    history: list[QueryHistoryEntry],
    entry: QueryHistoryEntry,
    *,
    limit: int = 20,
) -> list[QueryHistoryEntry]:
    updated = [entry, *history]
    return updated[:limit]


def history_entry_to_inputs(entry: QueryHistoryEntry) -> dict[str, object]:
    return {
        "query": entry.query,
        "top_k": entry.top_k,
        "edition": entry.edition,
        "source_type": entry.source_type,
    }
