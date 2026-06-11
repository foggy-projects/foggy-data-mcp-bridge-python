"""Validate the planned Java QueryModel aggregate-join snapshot contract."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

CONTRACT_PATH = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "java_querymodel_aggregate_join_snapshot_contract.json"
)
MANIFEST_PATH = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "java_snapshot_parity_manifest.json"
)

REQUIRED_CASE_IDS = {
    "aggregate-join-left-measure-not-multiplied",
    "aggregate-join-sql-shape-sqlite",
    "aggregate-join-missing-right-key-groupby-refusal",
    "aggregate-join-fixed-rhs-filter",
    "aggregate-join-runtime-extdata-filter",
    "aggregate-join-runtime-extdata-missing-refusal",
    "aggregate-join-and-pushdown-diagnostics",
    "aggregate-join-or-outer-only-diagnostics",
    "aggregate-join-denied-source-column-refusal",
    "aggregate-join-metadata-lineage",
}


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def test_contract_schema_and_required_cases() -> None:
    contract = _load_json(CONTRACT_PATH)

    assert contract["schemaVersion"] == 1
    assert contract["feature"] == "queryModelAggregateJoin"
    assert contract["status"] == "contractOnly"
    assert contract["source"] == "JavaQueryModelAggregateJoinSnapshotTest"

    required_envelope = set(contract["requiredEnvelopeFields"])
    assert {"schemaVersion", "feature", "source", "cases"}.issubset(required_envelope)

    case_ids = {case["id"] for case in contract["requiredCases"]}
    assert REQUIRED_CASE_IDS.issubset(case_ids)


def test_contract_pins_diagnostics_and_metadata_lineage() -> None:
    contract = _load_json(CONTRACT_PATH)

    diagnostic = contract["diagnosticContract"]
    assert set(diagnostic["requiredDecisionValues"]) == {
        "pushed",
        "retained",
        "refused",
    }
    assert {"decision", "field", "op", "target"}.issubset(
        set(diagnostic["requiredFields"])
    )

    assert {
        "aggregation",
        "sourceCaption",
        "sourceMeasure",
        "sourceAlias",
        "sourceExpression",
        "aggregateExpression",
        "sourceColumn",
    }.issubset(set(contract["metadataLineageRequiredKeys"]))


def test_manifest_tracks_aggregate_join_as_planned_lane() -> None:
    manifest = _load_json(MANIFEST_PATH)
    entries = {
        entry["id"]: entry
        for entry in manifest["entries"]
    }
    entry = entries["querymodel-aggregate-join-neutral-snapshots"]

    assert entry["feature"] == "queryModelAggregateJoin"
    assert entry["status"] == "planned"
    assert entry["contractFixture"] == (
        "tests/fixtures/java_querymodel_aggregate_join_snapshot_contract.json"
    )
    assert entry["javaExporter"] == (
        "foggy-dataset-model/src/test/java/com/foggyframework/dataset/db/model/parity/"
        "JavaQueryModelAggregateJoinSnapshotTest.java"
    )
    assert entry["javaExporterStatus"] == "ready"
    assert entry["javaSnapshotOutput"] == (
        "foggy-dataset-model/target/parity/_querymodel_aggregate_join_snapshot.json"
    )
    assert entry["javaExportNeeded"]
    assert entry["plannedPythonTests"]
