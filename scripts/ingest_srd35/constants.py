from __future__ import annotations

from pathlib import Path


DEFAULT_MANIFEST = Path("configs/bootstrap_sources/srd_35.manifest.json")

INGESTION_NOTES = [
    "Phase-1 ingestion spike: one canonical document per SRD RTF file.",
    "Locator policy follows source-native file names with section_path and source_location.",
]

EXTRACTION_CAVEATS = [
    "RTF control words are stripped heuristically and may lose some formatting semantics.",
    "Table-heavy sections may flatten cell structure and should be refined in later ingestion iterations.",
]

IGNORABLE_DESTINATIONS = {
    "fonttbl",
    "colortbl",
    "stylesheet",
    "info",
    "generator",
    "filetbl",
    "listtable",
    "listoverridetable",
    "revtbl",
}
