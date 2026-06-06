"""P0 manifest gate for Java snapshot parity coverage.

The manifest does not replay every snapshot itself. It keeps the always-on
Python gate honest by proving that active Java snapshot lanes point to real
fixtures/tests, while planned lanes carry explicit Java export requirements.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

PYTHON_REPO_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = (
    PYTHON_REPO_ROOT / "tests" / "fixtures" / "java_snapshot_parity_manifest.json"
)

REQUIRED_FEATURES = {
    "composeQuery",
    "scriptRuntimeTool",
    "formula",
    "timeWindow",
    "pivotDomainTransport",
    "governance",
    "domainFixtures",
}


def _load_manifest() -> dict[str, Any]:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def _java_worktree_candidates(manifest: dict[str, Any]) -> list[Path]:
    candidates: list[Path] = []
    env_name = manifest.get("javaWorktreeEnv")
    if env_name and os.environ.get(env_name):
        candidates.append(Path(os.environ[env_name]))

    for raw_path in manifest.get("defaultJavaWorktrees", []):
        candidates.append((PYTHON_REPO_ROOT / raw_path).resolve())
    return candidates


def _resolve_java_resource(manifest: dict[str, Any], relative_path: str) -> Path | None:
    for candidate in _java_worktree_candidates(manifest):
        resource = candidate / relative_path
        if resource.exists():
            return resource
    return None


def test_manifest_schema_and_feature_coverage() -> None:
    manifest = _load_manifest()

    assert manifest["schemaVersion"] == 1
    entries = manifest.get("entries", [])
    assert entries

    ids = [entry["id"] for entry in entries]
    assert len(ids) == len(set(ids))

    features = {entry["feature"] for entry in entries}
    assert REQUIRED_FEATURES.issubset(features)


def test_active_manifest_entries_point_to_executable_python_evidence() -> None:
    manifest = _load_manifest()

    active_entries = [
        entry for entry in manifest["entries"] if entry["status"] == "active"
    ]
    assert active_entries

    for entry in active_entries:
        for relative_path in entry.get("pythonFixtures", []):
            assert (PYTHON_REPO_ROOT / relative_path).exists(), (
                f"{entry['id']} fixture missing: {relative_path}"
            )
        for relative_path in entry.get("pythonSnapshots", []):
            assert (PYTHON_REPO_ROOT / relative_path).exists(), (
                f"{entry['id']} snapshot missing: {relative_path}"
            )
        for relative_path in entry.get("pythonTests", []):
            assert (PYTHON_REPO_ROOT / relative_path).exists(), (
                f"{entry['id']} test missing: {relative_path}"
            )


def test_active_java_owned_resources_are_available_when_declared() -> None:
    manifest = _load_manifest()

    for entry in manifest["entries"]:
        java_resource = entry.get("javaResource")
        if entry["status"] != "active" or not java_resource:
            continue
        resolved = _resolve_java_resource(manifest, java_resource)
        assert resolved is not None, (
            f"{entry['id']} Java resource missing: {java_resource}. "
            "Set FOGGY_JAVA_WORKTREE or check out the Java worktree next to "
            f"{PYTHON_REPO_ROOT.name}."
        )


def test_planned_manifest_entries_have_java_export_requirements() -> None:
    manifest = _load_manifest()

    planned_entries = [
        entry for entry in manifest["entries"] if entry["status"] == "planned"
    ]
    assert planned_entries

    for entry in planned_entries:
        assert entry.get("javaExportNeeded"), (
            f"{entry['id']} must describe required Java snapshot exports"
        )
        assert entry.get("plannedPythonTests"), (
            f"{entry['id']} must reserve the Python replay test target"
        )
