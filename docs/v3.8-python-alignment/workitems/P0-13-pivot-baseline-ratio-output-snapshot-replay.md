# P0-13 Pivot BaselineRatio Output Snapshot Replay

Date: 2026-06-06

## Goal

Extend the active real SQLite Pivot output snapshot lane with Java-aligned
`baselineRatio` output cases and make Python replay them through the engine.

This item stays on the ordinary rows + columns Pivot path:

- flat rows + columns with `baselineRatio(baseline=first)`
- grid rows + columns with `baselineRatio(baseline=last)`

Tree/cascade, non-additive auxiliary requery, and Odoo business fixtures remain
separate follow-up work.

## Java Current Contract

Java Pivot V9 supports mixed metric items:

- native metric shorthand, for example `"salesAmount"`
- derived `baselineRatio` metric object, for example
  `{"name":"index","type":"baselineRatio","of":"salesAmount","axis":"columns","baseline":"first"}`

Java computes `baselineRatio` as `current[of] / baselineCell[of]` for the same
row-axis key. The baseline column is selected from the global sorted columns
axis domain. Missing numerator, missing baseline, zero baseline, subtotal rows,
and grand-total rows emit `null`.

## Python Gap

Before this workitem, Python exposed the DTO/schema language for
`baselineRatio`, but runtime still rejected the metric type and the DTO axis
validator only allowed `rows`. The active Java output snapshot lane also lacked
baselineRatio output cases.

## Implementation Scope

Production code:

- `src/foggy/mcp_spi/semantic.py`
  - align `PivotMetricItem` validation with Java:
    `baselineRatio` requires `axis=columns` and `baseline=first|last`
  - keep `parentShare` restricted to rows axis
- `src/foggy/dataset_model/semantic/pivot/executor.py`
  - include the `baselineRatio.of` native metric in SQL output
  - return baselineRatio metrics as a sidecar for post-processing
- `src/foggy/dataset_model/semantic/pivot/baseline_ratio.py`
  - compute first/last columns-axis baseline ratios in memory
  - return `None` for subtotal/grand-total rows, missing values, and zero
    baselines
- `src/foggy/dataset_model/semantic/service.py`
  - apply baselineRatio after ordinary Pivot totals/parentShare and before grid
    shaping

Java snapshot producer:

- `JavaPivotOutputSnapshotTest.java`
  - add flat `baselineRatio(first)` and grid `baselineRatio(last)` cases

Python replay:

- `tests/integration/test_java_pivot_output_snapshot_parity.py`
  - canonicalize arbitrary object-derived metric names in flat output

Python fixture:

- `tests/fixtures/java_pivot_output_snapshot_parity.json`
  - now contains twelve cases, including flat/grid baselineRatio output cases

## Acceptance

Required focused checks:

- Java exporter target:
  `mvn test -P!multi-db -pl foggy-dataset-model -Dtest=JavaPivotOutputSnapshotTest`
- Python replay:
  `.venv/bin/python -m pytest tests/integration/test_java_pivot_output_snapshot_parity.py -q`
- P0 manifest and affected Pivot lanes:
  `.venv/bin/python -m pytest tests/integration/test_java_snapshot_parity_manifest.py tests/integration/test_java_pivot_domain_snapshot_parity.py tests/integration/test_java_pivot_output_snapshot_parity.py tests/test_dataset_model/test_pivot_parent_share.py tests/test_dataset_model/test_pivot_v9_cascade_validation.py tests/test_dataset_model/test_pivot_v9_contract_shell.py -q`

## Current Verification

Passed:

- Focused Python replay and affected Pivot contracts:
  `17 passed in 0.53s`
- Scoped ruff for the new baselineRatio module and modified executor:
  `All checks passed!`
- Full Python pytest baseline:
  `4041 passed, 232 skipped, 43 warnings in 17.19s`

The Java exporter could not complete in this workspace because
`foggy-dataset-model` testCompile failed on existing module classpath problems
outside this test, including compose/runtime, inline-expression, preagg, and
query-execution classes. The failure happened before
`JavaPivotOutputSnapshotTest` executed.

## Follow-Ups

- Re-run the Java exporter once the Java module testCompile baseline is clean.
- Add non-additive auxiliary requery output snapshot cases.
- Add large-domain threshold/fail-closed snapshot cases.
- Add pivot/domain governance propagation snapshots.
