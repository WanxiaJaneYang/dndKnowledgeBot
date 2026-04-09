from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path


DEFAULT_MANIFEST = Path("configs/bootstrap_sources/srd_35.manifest.json")


class ChecksumMismatchError(RuntimeError):
    """Raised when a downloaded or cached archive fails checksum verification."""


def load_manifest(manifest_path: Path) -> dict:
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def build_materialization_plan(manifest: dict, repo_root: Path) -> dict:
    layout = manifest["local_layout"]
    artifact = manifest["artifact"]

    archive_path = (repo_root / layout["archive_path"]).resolve()
    expanded_root = (repo_root / layout["expanded_root"]).resolve()
    provenance_path = (repo_root / layout["provenance_path"]).resolve()
    raw_root = (repo_root / layout["raw_root"]).resolve()

    return {
        "source_id": manifest["source_id"],
        "title": manifest.get("title", manifest["source_id"]),
        "download_url": artifact["download_url"],
        "archive_path": str(archive_path),
        "expanded_root": str(expanded_root),
        "provenance_path": str(provenance_path),
        "raw_root": str(raw_root),
        "expected_checksums": expected_checksums(artifact),
        "expected_file_count": artifact.get("expected_file_count"),
    }


def digest_file(path: Path, algorithm: str) -> str:
    digest = hashlib.new(algorithm)
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def expected_checksums(artifact: dict) -> dict[str, str]:
    if "checksums" in artifact:
        return {name.lower(): value for name, value in artifact["checksums"].items()}

    checksum = artifact["checksum"]
    return {checksum["algorithm"].lower(): checksum["value"]}


def download_file(url: str, destination: Path) -> None:
    with urllib.request.urlopen(url) as response, destination.open("wb") as target:
        shutil.copyfileobj(response, target)


def _remove_directory_if_present(path: Path, repo_root: Path) -> None:
    if not path.exists():
        return

    resolved_repo_root = repo_root.resolve()
    resolved_path = path.resolve()
    if resolved_repo_root not in resolved_path.parents and resolved_path != resolved_repo_root:
        raise RuntimeError(f"Refusing to remove path outside repo root: {resolved_path}")

    shutil.rmtree(resolved_path)


def extract_archive(archive_path: Path, expanded_root: Path, repo_root: Path) -> list[str]:
    _remove_directory_if_present(expanded_root, repo_root)
    expanded_root.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(archive_path, "r") as archive:
        names = archive.namelist()
        archive.extractall(expanded_root)
    return names


def write_provenance(
    manifest: dict,
    plan: dict,
    archive_checksums: dict[str, str],
    extracted_names: list[str],
) -> dict:
    provenance = {
        "source_id": manifest["source_id"],
        "edition": manifest["edition"],
        "materialized_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "archive": {
            "filename": manifest["artifact"]["filename"],
            "download_url": manifest["artifact"]["download_url"],
            "verified_checksums": archive_checksums,
            "expected_file_count": manifest["artifact"].get("expected_file_count"),
            "extracted_file_count": len(extracted_names),
        },
        "upstream": manifest["artifact"].get("upstream", {}),
        "local_layout": {
            "archive_path": plan["archive_path"],
            "expanded_root": plan["expanded_root"],
            "provenance_path": plan["provenance_path"],
        },
    }

    provenance_path = Path(plan["provenance_path"])
    provenance_path.parent.mkdir(parents=True, exist_ok=True)
    provenance_path.write_text(json.dumps(provenance, indent=2) + "\n", encoding="utf-8")
    return provenance


def verify_checksums(archive_path: Path, checksums: dict[str, str]) -> dict[str, str]:
    actual_checksums: dict[str, str] = {}
    for algorithm, expected_checksum in checksums.items():
        actual_checksum = digest_file(archive_path, algorithm)
        if actual_checksum != expected_checksum:
            raise ChecksumMismatchError(
                f"Checksum mismatch for {archive_path.name} ({algorithm}): "
                f"expected {expected_checksum}, got {actual_checksum}"
            )
        actual_checksums[algorithm] = actual_checksum
    return actual_checksums


def materialize_source(
    manifest: dict,
    repo_root: Path,
    *,
    dry_run: bool = False,
    force: bool = False,
) -> dict:
    plan = build_materialization_plan(manifest, repo_root)
    if dry_run:
        return plan

    artifact = manifest["artifact"]
    checksums = expected_checksums(artifact)
    archive_path = Path(plan["archive_path"])
    raw_root = Path(plan["raw_root"])
    raw_root.mkdir(parents=True, exist_ok=True)

    if force or not archive_path.exists():
        download_path = archive_path.with_suffix(archive_path.suffix + ".download")
        if download_path.exists():
            download_path.unlink()

        download_file(artifact["download_url"], download_path)
        archive_checksums = verify_checksums(download_path, checksums)
        os.replace(download_path, archive_path)
    else:
        archive_checksums = verify_checksums(archive_path, checksums)

    extracted_names = extract_archive(archive_path, Path(plan["expanded_root"]), repo_root)
    expected_file_count = artifact.get("expected_file_count")
    if expected_file_count is not None and len(extracted_names) != expected_file_count:
        raise ValueError(
            f"Unexpected archive file count: expected {expected_file_count}, got {len(extracted_names)}"
        )

    write_provenance(manifest, plan, archive_checksums, extracted_names)

    return {
        **plan,
        "archive_checksums": archive_checksums,
        "extracted_file_count": len(extracted_names),
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Materialize the pinned srd_35 bootstrap source locally.")
    parser.add_argument(
        "--manifest",
        type=Path,
        default=DEFAULT_MANIFEST,
        help="Path to the committed srd_35 manifest JSON.",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="Repository root used to resolve local data paths.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the planned local paths without downloading or extracting anything.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Redownload the archive even if a local copy already exists.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print the result as JSON.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    repo_root = args.repo_root.resolve()
    manifest_path = args.manifest if args.manifest.is_absolute() else (repo_root / args.manifest).resolve()
    manifest = load_manifest(manifest_path)
    result = materialize_source(manifest, repo_root, dry_run=args.dry_run, force=args.force)

    if args.json or args.dry_run:
        print(json.dumps(result, indent=2))
    else:
        print(f"Materialized {result['source_id']} to {result['raw_root']}")
        print(f"Archive: {result['archive_path']}")
        print(f"Extracted files: {result['extracted_file_count']}")
        print(f"Provenance: {result['provenance_path']}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
