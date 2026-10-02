"""Validate per-app deploy manifests (tkp/tcp/agm/yq/shared)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_DIR = REPO_ROOT / "deployment" / "windows-vps" / "manifests"


@pytest.mark.parametrize("name", ["tkp", "tcp", "agm", "yq", "shared"])
def test_app_manifest_json(name: str):
    path = MANIFEST_DIR / f"{name}.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data.get("schema_version")
    assert data.get("app") == name
    assert data.get("source_files")
    for rel in data["source_files"]:
        src = REPO_ROOT / rel.replace("/", "\\")
        assert src.is_file(), f"missing source for {name}: {rel}"
    if "target_app_directory" in data:
        assert r"C:\HC" in data["target_app_directory"]
        assert r"C:\H&C" not in data["target_app_directory"]


def test_manifests_exclude_legacy_tcp_monolith():
    tcp = json.loads((MANIFEST_DIR / "tcp.json").read_text(encoding="utf-8"))
    assert "tcp_ts.py" in tcp["exclude_from_git_deploy"]
    assert "tcp_ts.py" not in tcp["source_files"]
