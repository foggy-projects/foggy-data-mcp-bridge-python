from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from foggy.dataset_model.impl.loader import load_models_from_directory

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REGISTRY_DATA = REPO_ROOT.parent.parent / "foggy-model-registry" / "data"
REGISTRY_DATA = Path(
    os.environ.get("FOGGY_MODEL_REGISTRY_DATA", str(DEFAULT_REGISTRY_DATA))
)
PULL_SCRIPT = REPO_ROOT / "scripts" / "pull-odoo-models.py"
DRIFT_SCRIPT = REPO_ROOT / "scripts" / "check-model-drift.py"


@pytest.mark.parametrize(
    ("edition", "package", "expected_names"),
    [
        (
            "community",
            "foggy.odoo.community",
            {
                "OdooAccountPaymentBillMatchModel",
                "OdooAccountPaymentBillMatchQueryModel",
                "OdooPurchaseDocumentFlowModel",
                "OdooPurchaseDocumentFlowQueryModel",
                "OdooSaleDocumentFlowModel",
                "OdooSaleDocumentFlowQueryModel",
            },
        ),
        (
            "pro",
            "foggy.odoo.pro",
            {
                "OdooAccountPaymentBillMatchModel",
                "OdooAccountPaymentBillMatchQueryModel",
                "OdooMrpProductionModel",
                "OdooMrpProductionQueryModel",
                "OdooProjectTaskModel",
                "OdooProjectTaskQueryModel",
                "OdooPurchaseDocumentFlowModel",
                "OdooPurchaseDocumentFlowQueryModel",
                "OdooSaleDocumentFlowModel",
                "OdooSaleDocumentFlowQueryModel",
            },
        ),
    ],
)
def test_odoo_registry_consumer_pull_drift_and_loader_readonly(
    tmp_path: Path,
    edition: str,
    package: str,
    expected_names: set[str],
) -> None:
    if not REGISTRY_DATA.is_dir():
        pytest.skip(f"local model registry data not found: {REGISTRY_DATA}")

    output_dir = tmp_path / edition
    output_dir.mkdir()
    pull_command = [
        sys.executable,
        str(PULL_SCRIPT),
        "--registry",
        str(REGISTRY_DATA),
        "--edition",
        edition,
        "--channel",
        "stable",
        "--output",
        str(output_dir),
    ]
    if edition == "pro":
        pull_command.extend(["--key", "local-readonly"])

    pull = subprocess.run(
        pull_command,
        cwd=REPO_ROOT,
        capture_output=True,
        check=False,
        text=True,
    )
    assert pull.returncode == 0, pull.stderr

    drift = subprocess.run(
        [sys.executable, str(DRIFT_SCRIPT), "--model-dir", str(output_dir)],
        cwd=REPO_ROOT,
        capture_output=True,
        check=False,
        text=True,
    )
    assert drift.returncode == 0, drift.stderr
    assert "OK: Model directory matches lock file." in drift.stdout

    lock = json.loads((output_dir / "models.lock.json").read_text(encoding="utf-8"))
    assert lock["package"] == package
    assert lock["version"] == "1.1.10"
    assert lock["checksum"].startswith("sha256:")
    assert lock["content_checksum"].startswith("sha256:")

    models = load_models_from_directory(str(output_dir), namespace="odoo")
    loaded_names = {model.name for model in models}
    assert len(loaded_names) == len(models)
    assert {f"odoo:{name}" for name in expected_names}.issubset(loaded_names)
