from pathlib import Path

from eta_route_optimization.provenance import build


def test_manifest_excludes_runtime_cache_and_tracks_scripts(tmp_path: Path) -> None:
    for folder in ["src", "tests/__pycache__", "configs", "docs", "scripts", "artifacts/generated"]:
        (tmp_path / folder).mkdir(parents=True, exist_ok=True)
    (tmp_path / "src" / "module.py").write_text("value = 1\n", encoding="utf-8")
    (tmp_path / "tests" / "test_module.py").write_text("def test_ok(): pass\n", encoding="utf-8")
    (tmp_path / "tests" / "__pycache__" / "test_module.pyc").write_bytes(b"volatile")
    (tmp_path / "scripts" / "generate.py").write_text("print('ok')\n", encoding="utf-8")
    for name in ["README.md", "TASKS.md", "pyproject.toml", "references.bib"]:
        (tmp_path / name).write_text("placeholder\n", encoding="utf-8")

    payload = build(tmp_path)
    paths = {item["path"] for item in payload["source_and_document_files"]}

    assert "scripts/generate.py" in paths
    assert not any("__pycache__" in path or path.endswith(".pyc") for path in paths)
