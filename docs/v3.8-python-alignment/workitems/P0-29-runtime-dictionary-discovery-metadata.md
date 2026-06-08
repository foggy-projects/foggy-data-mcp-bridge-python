# P0-29 Runtime Dictionary Discovery Metadata

Date: 2026-06-08

## Goal

Align Python metadata with Java's field-level `dictionaryDiscovery` contract so
low-cardinality runtime values can be exposed to LLM metadata only when a model
explicitly opts in.

## Scope

- Python dictionary contract:
  `src/foggy/dataset_model/definitions/dict_def.py`
- TM loader parsing and fail-closed validation:
  `src/foggy/dataset_model/impl/loader/__init__.py`
- V3 JSON/markdown metadata runtime discovery:
  `src/foggy/dataset_model/semantic/service.py`
- Regression coverage:
  `tests/test_dataset_model/test_dictionary_discovery_metadata.py`

## Contract

- `dictionaryDiscovery.enabled` is opt-in and defaults to disabled.
- `strategy` supports `group_by` and `distinct`.
- `maxValues` defaults to 50 and is capped at 500.
- `refreshTtlSeconds` defaults to 3600 and cannot be negative.
- `exposeToLlm=false` or `sensitive=true` returns `valuesStatus=not_exposed`
  and does not query runtime values.
- Runtime query failures are sanitized as
  `error=runtime dictionary discovery failed`.
- Metadata respects visible-field trimming and does not query hidden fields.
- Discovery cache is scoped by request context to avoid namespace/user leakage.

## Explicit Non-Scope

- Static dictionary governance replacement.
- Business-domain aliases beyond the generic alias/value mapping contract.
- Semantic scale / monetary unit conversion.
- Odoo model registry promotion.

## Acceptance

- JSON metadata includes runtime values, counts, truncation, sampled timestamp,
  and governed aliases for sampled fields.
- Markdown metadata includes sampled runtime values and aliases.
- Sensitive, hidden, and failed discovery cases are fail-closed.
- Loader rejects invalid enabled discovery definitions.
- Focused pytest coverage passes.
