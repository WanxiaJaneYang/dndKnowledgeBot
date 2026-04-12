"""Extract retrieval term candidates from local SRD assets."""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CANONICAL_ROOT = REPO_ROOT / "data" / "canonical" / "srd_35"
DEFAULT_CHUNK_ROOT = REPO_ROOT / "data" / "chunks" / "srd_35"
DEFAULT_OUTPUT = REPO_ROOT / "configs" / "retrieval_terms" / "extraction_candidates.json"

STOP_PHRASES = {
    "open game license",
    "terms of use",
    "privacy policy",
    "legal information",
    "table below",
}

STOP_WORDS = {
    "the",
    "a",
    "an",
    "and",
    "or",
    "of",
    "to",
    "for",
    "in",
    "on",
    "by",
    "from",
    "with",
    "without",
    "at",
}

PROMOTED_CONTENT_KEYWORDS = {
    "ability",
    "armor",
    "attack",
    "bonus",
    "caster",
    "challenge",
    "class",
    "combat",
    "damage",
    "difficulty",
    "feat",
    "grapple",
    "hit",
    "initiative",
    "level",
    "power",
    "range",
    "resistance",
    "save",
    "saving",
    "skill",
    "spell",
    "turn",
    "undead",
    "weapon",
}


def extract_term_candidates(canonical_root: Path, chunk_root: Path) -> dict:
    """Extract deterministic retrieval term candidates from local SRD outputs."""
    title_candidates = _extract_title_candidates(canonical_root)
    content_candidates = _extract_content_candidates(chunk_root)

    protected = sorted(
        set(title_candidates)
        | {
            term for term, count in content_candidates.items()
            if count >= 3 and _should_promote_content_phrase(term)
        }
    )

    section_titles = sorted(set(title_candidates))
    content_phrases = sorted(
        term for term, count in content_candidates.items()
        if count >= 4 and _is_acceptable_phrase(term)
    )

    return {
        "protected_phrase_candidates": protected,
        "section_title_candidates": section_titles,
        "content_phrase_candidates": content_phrases,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract retrieval term candidates from local SRD data.")
    parser.add_argument("--canonical-root", type=Path, default=DEFAULT_CANONICAL_ROOT)
    parser.add_argument("--chunk-root", type=Path, default=DEFAULT_CHUNK_ROOT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    result = extract_term_candidates(args.canonical_root, args.chunk_root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result["protected_phrase_candidates"], indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )


def _extract_title_candidates(canonical_root: Path) -> list[str]:
    candidates: set[str] = set()
    for path in canonical_root.glob("*.json"):
        if path.name == "canonical_report.json":
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))

        values = []
        title = payload.get("document_title")
        if isinstance(title, str):
            values.append(title)

        locator = payload.get("locator", {})
        for section in locator.get("section_path", [])[1:]:
            values.append(section)

        for raw in values:
            normalized = _normalize_phrase(raw)
            if _is_acceptable_phrase(normalized):
                candidates.add(normalized)

    return sorted(candidates)


def _extract_content_candidates(chunk_root: Path) -> Counter:
    counter: Counter[str] = Counter()
    pattern = re.compile(r"\b[a-z][a-z]+(?: [a-z][a-z]+){1,4}\b")

    for path in chunk_root.glob("*.json"):
        if path.name == "chunk_report.json":
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        content = payload.get("content", "")
        for match in pattern.findall(content.casefold()):
            normalized = _normalize_phrase(match)
            if _is_acceptable_phrase(normalized):
                counter[normalized] += 1

    return counter


def _normalize_phrase(value: str) -> str:
    value = value.casefold()
    value = value.replace("_", " ")
    value = value.replace("-", " ")
    value = re.sub(r"\([^)]*\)", " ", value)
    value = re.sub(r"[^a-z0-9\s/]", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def _is_acceptable_phrase(value: str) -> bool:
    if not value or value in STOP_PHRASES:
        return False
    words = value.split()
    if len(words) < 2 or len(words) > 5:
        return False
    if words[0][0].isdigit():
        return False
    if any(word in STOP_WORDS for word in words[:1]):
        return False
    if all(word.isdigit() for word in words):
        return False
    if "license" in words or "copyright" in words:
        return False
    if "spell list" in value or "power list" in value:
        return False
    return True


def _should_promote_content_phrase(value: str) -> bool:
    return any(keyword in value.split() for keyword in PROMOTED_CONTENT_KEYWORDS)


if __name__ == "__main__":
    main()
