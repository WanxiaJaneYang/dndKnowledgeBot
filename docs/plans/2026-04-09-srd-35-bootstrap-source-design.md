# SRD 3.5 Bootstrap Source Design

## Goal

Materialize `srd_35` as a reproducible local bootstrap source without committing the raw SRD content into git.

## Context

Issue `#9` bridges the gap between the bootstrap-source policy and the first source-backed work. The repo already admits `srd_35` in the registry, but later work still lacks a pinned upstream artifact, checksum policy, and a repeatable way to populate `data/raw/srd_35/`.

## Proposed Design

Use a committed source manifest plus a small fetch script.

- Pin one upstream artifact: the Internet Archive `dnd35srd` item, using the all-in-one `SRD.zip`.
- Store the committed manifest outside `data/raw/` so raw content remains untracked.
- Download into `data/raw/srd_35/`, verify checksum, and unpack the RTF files into a deterministic subdirectory.
- Write a local provenance record after download so later ingestion work can see what was fetched and when.

## Why This Shape

- It keeps the bootstrap source reproducible instead of relying on a hand-written note.
- It preserves the repo rule that raw corpus material is local and untracked.
- It pins a single artifact with a stable checksum instead of depending on a third-party HTML rendering layer.
- It gives issue `#6` and issue `#4` a concrete handoff target under `data/raw/srd_35/`.

## Data To Commit

- `configs/bootstrap_sources/srd_35.manifest.json`
- `scripts/fetch_srd_35.py`
- repo docs that explain how the bootstrap source is materialized and what caveats apply

## Local Files Created By The Script

- `data/raw/srd_35/SRD.zip`
- `data/raw/srd_35/rtf/*.rtf`
- `data/raw/srd_35/bootstrap_provenance.json`

## Alternatives Considered

### Manual download instructions only

Rejected because the repo would still depend on memory and manual judgment for provenance and checksum validation.

### Commit the SRD files directly

Rejected because the project already treats raw corpus material as local-only, and keeping raw artifacts out of git is the cleaner long-term pattern for all sources.

### Pin a third-party SRD mirror

Rejected as the default because it adds an avoidable derived layer when the archived original artifact is scriptable enough to use directly.

## Risks

- The Internet Archive item is not an official Wizards-hosted endpoint, so the provenance note needs to say clearly that this is an archived copy of the original WotC SRD distribution.
- The zip may contain naming quirks or RTF edge cases that later extraction has to normalize.
- If the upstream archive changes unexpectedly, checksum validation should fail loudly instead of silently accepting drift.

## Next Steps

1. Add the committed manifest and fetch script.
2. Update the registry and data docs to point at the manifest-driven bootstrap flow.
3. Run the fetch script once locally to verify it materializes `data/raw/srd_35/` correctly.
