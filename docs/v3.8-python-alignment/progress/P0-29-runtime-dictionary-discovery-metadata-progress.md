# P0-29 Runtime Dictionary Discovery Metadata Progress

Date: 2026-06-08

## Completed

- Added Java-aligned Python `DbDictionaryDiscoveryDef`,
  `DictionaryDiscoveryResult`, and alias/value entry models.
- Added TM loader support for `dictionaryDiscovery` / `dictionary_discovery`
  on dimensions, dimension properties, and properties.
- Added runtime discovery metadata to V3 JSON metadata and single/multi-model
  markdown metadata.
- Added fail-closed handling for sensitive fields, hidden fields, unavailable
  executors, query errors, invalid loader definitions, and context-scoped cache
  isolation.
- Corrected the alignment plan distinction between runtime dictionary discovery
  and semantic scale / money units.

## Verification

Passed:

- `.venv/bin/python -m pytest tests/test_dataset_model/test_dictionary_discovery_metadata.py -q`
  - `7 passed in 0.48s`
- `.venv/bin/python -m pytest tests/test_dataset_model/test_dictionary_discovery_metadata.py tests/test_metadata_v3_cross_model_governance.py tests/test_mcp/test_list_models_tool.py tests/test_mcp/test_mcp_rpc_router.py tests/integration/test_java_snapshot_parity_manifest.py -q`
  - `51 passed, 1 warning in 0.86s`
- `.venv/bin/python -m pytest -q`
  - `4055 passed, 232 skipped, 51 warnings in 17.68s`

Pending:

- Java/Python neutral fixture export for dictionary discovery, if this becomes
  part of the cross-language snapshot catalog.

## Notes

- This is an engine metadata capability. Domain-specific aliases remain model
  authoring data and should live in TM/QM or industry model packs, not in the
  engine core.
