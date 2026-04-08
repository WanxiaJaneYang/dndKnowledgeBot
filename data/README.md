# data/

This directory holds local corpus files. **Nothing here is committed to git.**

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

## Copyright Notice

Source materials (rulebooks, supplements, errata) are copyrighted by their respective publishers. Do not commit, share, or redistribute these files. This project assumes private local use of lawfully obtained materials only.

## Source Registration

All sources intended for ingestion must be registered in [`configs/source_registry.yaml`](../configs/source_registry.yaml) before processing.
