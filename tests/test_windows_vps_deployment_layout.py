"""Tests for Windows VPS deployment layout artifacts (Phase P4).

No application behavior changes — validates scripts, manifests, env template,
and filesystem preview coherence only.
"""
from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
DEPLOY = REPO_ROOT / "deployment" / "windows-vps"
PREVIEW_ROOT = DEPLOY / "filesystem-preview" / "HC"
INIT_SCRIPT = DEPLOY / "scripts" / "Initialize-HCServerLayout.ps1"
TEST_SCRIPT = DEPLOY / "scripts" / "Test-HCServerLayout.ps1"
ENV_EXAMPLE = DEPLOY / "config-templates" / "hc-vps.env.example"

FORBIDDEN_VPS_SUBSTRINGS = [
    "Coding Projects",
    "OneDrive",
    "Azure",
    "AWS",
    "OVH",
    "C:\\Users\\",
]

REQUIRED_PREVIEW_DIRS = [
    "apps/tkp", "apps/tcp", "apps/agm", "apps/yq", "apps/dashboard", "apps/shared",
    "data/tkp", "data/tcp", "data/agm", "data/yq",
    "config", "secrets",
    "logs/tkp", "logs/tcp", "logs/agm", "logs/yq", "logs/dashboard", "logs/ingest",
    "backups/tkp", "backups/tcp", "backups/agm", "backups/yq",
    "website", "deployment",
]


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _run_ps1(script: Path, *args: str) -> subprocess.CompletedProcess:
    cmd = [
        "powershell",
        "-NoProfile",
        "-ExecutionPolicy", "Bypass",
        "-File", str(script),
        *args,
    ]
    return subprocess.run(cmd, capture_output=True, text=True, check=False)


@pytest.mark.parametrize("manifest", [
    "application-file-map.json",
    "persistent-data-map.json",
    "windows-services.json",
    "network-map.json",
])
def test_manifest_json_syntax(manifest: str):
    path = DEPLOY / "manifests" / manifest
    assert path.is_file(), f"missing {manifest}"
    data = _load_json(path)
    assert data.get("schema_version")


def test_env_template_has_no_secret_values():
    text = ENV_EXAMPLE.read_text(encoding="utf-8")
    assert "DO NOT COMMIT A POPULATED VERSION" in text
    assert "HC_APP_ENV=vps-production" in text
    assert "HC_TKP_STATE_PATH=C:\\HC\\data\\tkp" in text
    # Secret keys present but empty
    for line in text.splitlines():
        if line.startswith("TCP_V2_ADMIN_TOKEN="):
            assert line.strip().endswith("=")
        if line.startswith("TCP_V2_SESSION_SECRET="):
            assert line.strip().endswith("=")


def test_preview_has_all_required_directories():
    for rel in REQUIRED_PREVIEW_DIRS:
        target = PREVIEW_ROOT / rel.replace("/", "\\")
        assert target.is_dir(), f"missing preview dir: {rel}"
        readme = target / "README.md"
        assert readme.is_file(), f"missing README in {rel}"


def test_preview_contains_no_data_or_secret_files():
    forbidden_suffixes = {".json", ".csv", ".xlsx", ".xls", ".env", ".lock"}
    for path in PREVIEW_ROOT.rglob("*"):
        if path.is_file() and path.name != "README.md":
            assert path.suffix.lower() not in forbidden_suffixes, f"unexpected file: {path}"


def test_windows_services_manifest_has_eight_services():
    data = _load_json(DEPLOY / "manifests" / "windows-services.json")
    services = data["services"]
    assert len(services) == 8
    names = {s["service_name"] for s in services}
    expected = {
        "HC-TKP-Public", "HC-TCP-Public", "HC-YQ-Public", "HC-AGM-Public",
        "HC-TKP-Staff", "HC-TCP-Staff", "HC-AGM-Staff", "HC-Dashboard",
    }
    assert names == expected
    ports = {s["port"] for s in services}
    assert ports == {8006, 8301, 8302, 8303, 8304, 8321, 8322, 8324}


def test_network_map_ports_match_production():
    data = _load_json(DEPLOY / "manifests" / "network-map.json")
    port_apps = {
        b["internal_port"]: b["application"]
        for b in data["bindings"]
        if b.get("internal_port")
    }
    assert port_apps[8301] == "tkp"
    assert port_apps[8302] == "tcp"
    assert port_apps[8303] == "yq"
    assert port_apps[8304] == "agm"
    assert port_apps[8321] == "tkp_staff"
    assert port_apps[8322] == "tcp_staff"
    assert port_apps[8324] == "agm_staff"
    assert port_apps[8006] == "dashboard"


def test_vps_mappings_are_provider_neutral():
    blobs = []
    for manifest in (DEPLOY / "manifests").glob("*.json"):
        blobs.append(manifest.read_text(encoding="utf-8"))
    blobs.append(ENV_EXAMPLE.read_text(encoding="utf-8"))
    combined = "\n".join(blobs)
    for forbidden in FORBIDDEN_VPS_SUBSTRINGS:
        assert forbidden not in combined, f"forbidden substring in VPS mappings: {forbidden}"
    assert r"C:\HC" in combined


def test_initialize_script_creates_layout_in_temp_dir():
    with tempfile.TemporaryDirectory() as tmp:
        result = _run_ps1(INIT_SCRIPT, "-Root", tmp)
        assert result.returncode == 0, result.stderr or result.stdout
        assert (Path(tmp) / "apps" / "tkp").is_dir()
        assert (Path(tmp) / "data" / "agm").is_dir()
        assert (Path(tmp) / "logs" / "ingest").is_dir()


def test_initialize_script_is_idempotent():
    with tempfile.TemporaryDirectory() as tmp:
        first = _run_ps1(INIT_SCRIPT, "-Root", tmp)
        second = _run_ps1(INIT_SCRIPT, "-Root", tmp)
        assert first.returncode == 0
        assert second.returncode == 0
        assert "Skipped:" in second.stdout


def test_layout_validator_passes_on_initialized_temp_dir():
    with tempfile.TemporaryDirectory() as tmp:
        init = _run_ps1(INIT_SCRIPT, "-Root", tmp)
        assert init.returncode == 0
        validate = _run_ps1(TEST_SCRIPT, "-Root", tmp)
        assert validate.returncode == 0, validate.stdout + validate.stderr
        assert "VALID:" in validate.stdout


def test_layout_validator_fails_on_empty_dir():
    with tempfile.TemporaryDirectory() as tmp:
        result = _run_ps1(TEST_SCRIPT, "-Root", tmp)
        assert result.returncode == 1
        assert "INVALID:" in result.stdout


def test_vps_resolver_profile_still_coherent():
    import tearsheet_paths as tp

    paths = tp.load_tearsheet_paths(
        env={tp.HC_APP_ENV_VAR: "vps-production"},
        module_dir=REPO_ROOT,
    )
    assert str(paths.data_root).startswith(r"C:\HC")
    assert str(paths.tkp_state_path).startswith(r"C:\HC\data\tkp")
