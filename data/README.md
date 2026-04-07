# data/

This directory holds local corpus files. **Nothing here is committed to git.**

## Expected Layout

```
data/
├─ raw/           Original source files as obtained (PDFs, etc.)
├─ extracted/     Raw text extracted from source files, pre-normalization
├─ canonical/     Normalized canonical documents (JSON, per schema)
├─ chunks/        Chunked corpus ready for indexing (JSON, per schema)
└─ index/         Vector index files (Chroma, FAISS, etc.)
```

## Copyright Notice

Source materials (rulebooks, supplements, errata) are copyrighted by their respective publishers. Do not commit, share, or redistribute these files. This project assumes private local use of lawfully obtained materials only.

## Source Registration

All sources intended for ingestion must be registered in [`configs/source_registry.yaml`](../configs/source_registry.yaml) before processing.
