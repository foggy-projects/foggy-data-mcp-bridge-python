# S2 Formula Parity Snapshot CI Solidification — Progress

## 文档作用

- doc_type: progress
- intended_for: execution-agent / reviewer / signoff-owner
- purpose: 记录 post-v1.5 Stage 2 formula parity snapshot CI/artifact 固化、drift detection、测试证据和剩余 CI 接线假设

**Status**: ✅ Complete

## Artifact/Checkout Convention

### Java → Python Snapshot Flow

```
┌─────────────────────────────────────────────────────────────────┐
│  Java: mvn test -pl foggy-dataset-model                        │
│        -Dtest=FormulaParitySnapshotTest                        │
│                                                                │
│  Writes to:                                                    │
│    1. ../foggy-data-mcp-bridge-python/tests/integration/       │
│       _parity_snapshot.json  (direct cross-repo write)         │
│    2. target/parity/_parity_snapshot.json  (CI artifact copy)  │
└───────────────────────┬─────────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────────┐
│  Python: python -m pytest tests/integration/                   │
│          test_formula_parity.py -q                              │
│                                                                │
│  Consumes: tests/integration/_parity_snapshot.json             │
│                                                                │
│  Tests:                                                        │
│    - test_snapshot_schema_integrity  (schema + source + count)  │
│    - test_snapshot_covers_full_catalog  (staleness detection)   │
│    - test_committed_snapshot_not_hand_edited  (integrity)       │
│    - test_parity_matches_java_snapshot  (strict SQL compare)   │
│    - test_python_matches_catalog × N  (catalog-driven parity)  │
└─────────────────────────────────────────────────────────────────┘
```

### CI Integration Options

No CI workflow files exist in this repo yet. When CI is added, use one of:

| Option | Description |
|--------|-------------|
| **(a) Mono-checkout** | Both repos under the same workspace root. Java job runs first, writes snapshot directly. Python job reads committed snapshot or freshly written one. |
| **(b) Artifact upload** | Java job uploads `target/parity/_parity_snapshot.json` as a CI artifact. Python job downloads it to `tests/integration/` before `pytest`. |
| **(c) Committed baseline** | Python always consumes the committed snapshot in git. Staleness is detected by `test_snapshot_covers_full_catalog`. Developers regenerate manually after catalog changes. |

**Current default**: Option (c) — committed baseline with drift detection.

### Regeneration Command

When the Java catalog (`formula-parity-expressions.json`) changes:

```bash
cd <java-worktree>
mvn test -pl foggy-dataset-model -Dtest=FormulaParitySnapshotTest
```

This writes the snapshot directly to `tests/integration/_parity_snapshot.json`.

## Drift Detection

Three new tests catch snapshot staleness or hand-editing:

| Test | Detects |
|------|---------|
| `test_snapshot_schema_integrity` | Corrupt/wrong schema_version, wrong source, insufficient entries |
| `test_snapshot_covers_full_catalog` | Missing catalog entries — triggers when catalog is expanded but snapshot not regenerated |
| `test_committed_snapshot_not_hand_edited` | Orphan entries or unexpected fields in snapshot rows |

### Skip Behavior

When `_parity_snapshot.json` is absent:
- All 4 snapshot tests are **skipped** with a clear regeneration message.
- The 44+ catalog-driven tests still run and guard Python-side parity.

When `_parity_snapshot.json` is present:
- All 50 tests run — no skips.

## Test Results

```
tests/integration/test_formula_parity.py — 50 passed, 0 skipped
Full regression                          — 3316 passed, 0 xfailed
```

Latest verification by root controller:

```
mvn test -pl foggy-dataset-model -Dtest=FormulaParitySnapshotTest
  -> BUILD SUCCESS; three surefire lanes, each 5 tests / 0 skipped
python -m pytest tests\integration\test_formula_parity.py -q
  -> 50 passed
python -m pytest -q
  -> 3316 passed
```

## Stage 1 Cleanup

Fixed 5 trailing blank line issues from Stage 1 that `git diff --check` flagged:
- `authority/__init__.py`
- `compilation/compiler.py`
- `tests/compose/compilation/conftest.py`
- `tests/compose/compilation/test_join.py`
- `tests/compose/compilation/test_union.py`

## Remaining CI Wiring

- No CI config exists yet — when added, document the chosen option (a/b/c) in the workflow file.
- The `target/parity/` local copy in the Java repo is ready for artifact upload in option (b).
- The committed snapshot serves as a reliable fallback and is always validated for structural integrity.

## Execution Check-in

- completed_work: Python formula parity test now has explicit snapshot schema, catalog coverage, and integrity checks; Java snapshot generation was re-verified.
- touched_code_paths:
  - `tests/integration/test_formula_parity.py`
  - `docs/v1.5/S2-formula-parity-snapshot-ci-progress.md`
- self_check:
  - artifact convention documented: yes
  - strict compare preserved: yes
  - committed snapshot drift detection present: yes
  - CI assumptions recorded: yes
  - experience impact: N/A, backend regression infrastructure only
- self_check_conclusion: self-check-only is sufficient for Stage 2 because no product semantics changed; formal acceptance can be compact evidence-based signoff if required.
- acceptance_readiness: ready for acceptance; only external CI workflow wiring remains out of scope.
- consolidated_quality_gate: `docs/v1.5/quality/S1-S2-post-v1.5-followup-implementation-quality.md`, decision `ready-with-risks` because Stage 1 Java mirror remains pending.
