from __future__ import annotations

import argparse
import hashlib
import json
import platform
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

PACKAGES = ["numpy", "pandas", "pyarrow", "scipy", "scikit-learn", "lightgbm", "ortools"]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def describe(path: Path, root: Path) -> dict:
    return {
        "path": str(path.relative_to(root)),
        "bytes": path.stat().st_size,
        "sha256": sha256(path),
    }


def build(project: Path) -> dict:
    tracked = []
    for folder in ["src", "tests", "configs", "docs", "scripts"]:
        tracked.extend(
            path
            for path in (project / folder).rglob("*")
            if path.is_file()
            and "__pycache__" not in path.parts
            and path.suffix not in {".pyc", ".pyo"}
            and path.name != ".DS_Store"
        )
    tracked.extend(project / name for name in ["README.md", "TASKS.md", "pyproject.toml", "references.bib"])
    generated = [
        path
        for path in (project / "artifacts" / "generated").rglob("*")
        if path.is_file() and path.name != "MANIFEST.json"
    ]
    package_versions = {}
    for package in PACKAGES:
        try:
            package_versions[package] = version(package)
        except PackageNotFoundError:
            package_versions[package] = None
    return {
        "format": "eta-route-artifact-manifest-v1",
        "python": platform.python_version(),
        "platform": platform.platform(),
        "package_versions": package_versions,
        "random_seeds": [17, 29, 43, 71, 101],
        "source_and_document_files": [describe(path, project) for path in sorted(tracked)],
        "generated_artifacts": [describe(path, project) for path in sorted(generated)],
        "raw_data_note": (
            "Raw data are not copied into the project manifest. Their file sizes and dataset-level "
            "counts are recorded by audit.py and artifacts/data_audit_snapshot_2026-11-16.json."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    payload = build(args.project.resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"status": "pass", "artifacts": len(payload["generated_artifacts"])}, indent=2))


if __name__ == "__main__":
    main()
