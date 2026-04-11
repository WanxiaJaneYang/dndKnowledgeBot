# SRD 3.5 Bootstrap Source Implementation Plan

> **Execution note:** Implement this plan task-by-task and verify each task before proceeding.

**Goal:** Add a reproducible manifest and fetch workflow that materializes the `srd_35` bootstrap source under `data/raw/srd_35/` without committing the raw SRD files.

**Architecture:** The branch will commit a machine-readable manifest and a small standard-library Python fetcher. The fetcher will download `SRD.zip`, verify its published checksums, unpack the archive into `data/raw/srd_35/rtf/`, and write a local provenance record for later ingestion work.

**Tech Stack:** Git, Python standard library, Internet Archive hosted artifact metadata, Markdown and JSON docs/config

---

### Task 1: Add the committed bootstrap source contract

**Files:**
- Create: `configs/bootstrap_sources/srd_35.manifest.json`
- Modify: `configs/source_registry.yaml`
- Modify: `data/README.md`
- Modify: `README.md`

**Step 1: Write the manifest**

Include:
- source identity fields that match the repo vocabulary
- the pinned upstream item and download URL
- the expected checksums and archive shape
- the local target paths for raw, extracted, and canonical handoff
- caveats about archive provenance and non-paginated locators

**Step 2: Align the registry and docs**

Update the registry and repo docs so `srd_35` points at the manifest-driven bootstrap flow instead of remaining a conceptual source only.

**Step 3: Verify the content reads coherently**

Run:

```powershell
Get-Content configs/bootstrap_sources/srd_35.manifest.json
Get-Content configs/source_registry.yaml
Get-Content data/README.md
```

Expected: the manifest, registry, and docs agree on `source_id`, edition, `authority_level`, local layout, and the fact that raw artifacts remain untracked.

### Task 2: Add the fetch script

**Files:**
- Create: `scripts/fetch_srd_35.py`

**Step 1: Implement the fetcher**

Behavior:
- load the committed manifest
- create `data/raw/srd_35/`
- download `SRD.zip` if missing or when forced
- verify the archive checksums
- unpack into `data/raw/srd_35/rtf/`
- write `data/raw/srd_35/bootstrap_provenance.json`
- support a dry-run mode so the workflow is inspectable without downloading

**Step 2: Run the script in dry-run mode**

Run:

```powershell
python scripts/fetch_srd_35.py --dry-run
```

Expected: the script prints the planned download target, checksums, extraction directory, and provenance file path without writing raw content.

**Step 3: Run the script for real**

Run:

```powershell
python scripts/fetch_srd_35.py
```

Expected: `data/raw/srd_35/SRD.zip`, `data/raw/srd_35/rtf/`, and `data/raw/srd_35/bootstrap_provenance.json` exist locally, and checksum validation passes.

### Task 3: Verify the bootstrap source handoff

**Files:**
- Verify: `data/raw/srd_35/`
- Verify: `data/raw/srd_35/bootstrap_provenance.json`

**Step 1: Check the local output layout**

Run:

```powershell
Get-ChildItem data/raw/srd_35
Get-ChildItem data/raw/srd_35/rtf | Select-Object -First 5
```

Expected: the raw directory contains the pinned archive, the extracted RTF directory, and the provenance record.

**Step 2: Check the repo diff**

Run:

```powershell
git status --short
```

Expected: only the intended committed files appear in git status; the raw source files stay ignored.

**Step 3: Commit**

```bash
git add README.md data/README.md configs/source_registry.yaml configs/bootstrap_sources/srd_35.manifest.json scripts/fetch_srd_35.py docs/plans/2026-04-09-srd-35-bootstrap-source-design.md docs/plans/2026-04-09-srd-35-bootstrap-source-implementation.md
git commit -m "Introduce pinned srd_35 bootstrap source snapshot"
```
