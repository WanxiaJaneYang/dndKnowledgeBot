# data/

This directory holds local corpus files. **Raw corpus artifacts here are not committed to git.**

## Expected Layout

```text
data/
|-- raw/           Original source files as obtained (PDFs, etc.), organized by source_id
|-- extracted/     Raw text extracted from source files, pre-normalization, organized by source_id
|-- canonical/     Normalized canonical documents (JSON, per schema), organized by source_id
|-- chunks/        Stable chunk/evidence objects ready for indexing (JSON, per schema)
`-- index/         Derived local retrieval artifacts (FAISS, Chroma, sqlite-vec, etc.)
```

Bootstrap example:

```text
data/
|-- raw/
|   `-- srd_35/
|-- extracted/
|   `-- srd_35/
`-- canonical/
    `-- srd_35/
```

Bootstrap materialization:

- The committed source manifest lives at [`configs/bootstrap_sources/srd_35.manifest.json`](../configs/bootstrap_sources/srd_35.manifest.json).
- Run `python scripts/fetch_srd_35.py` from the repo root to populate `data/raw/srd_35/`.
- The fetch script downloads the pinned `SRD.zip`, verifies its checksum, unpacks the RTF files, and writes `data/raw/srd_35/bootstrap_provenance.json`.
- `data/extracted/srd_35/` and `data/canonical/srd_35/` remain the next handoff points for issue `#4`; this issue does not populate them yet.

## Copyright Notice

Source materials (rulebooks, supplements, errata) are copyrighted by their respective publishers. Do not commit, share, or redistribute these files. This project assumes private local use of lawfully obtained materials only.

## Source Registration

All sources intended for ingestion must be registered in [`configs/source_registry.yaml`](../configs/source_registry.yaml) before processing.
