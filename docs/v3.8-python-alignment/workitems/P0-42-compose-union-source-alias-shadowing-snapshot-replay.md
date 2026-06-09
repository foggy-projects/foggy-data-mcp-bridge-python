# P0-42 Compose Union Source Alias Shadowing Snapshot Replay

Date: 2026-06-09

## Goal

Close the P0-37 compose alias follow-up for engine-neutral cases that do not
touch Odoo business models:

- projected column aliases must not shadow visible source aliases,
- union-as-source must expose only the union result alias for qualified refs,
- union branch source aliases must fail closed after the union boundary,
- SQL Server embedded join fallback must not emit `FROM (WITH`.

## Scope

Java snapshot additions:

- `source-alias-shadowed-by-projected-alias-refused`
- `union-branch-source-alias-ref-refused`
- `union-result-alias-qualified-ref-postgres`
- MySQL8 and SQL Server qualified source-alias slice/order markers

Python alignment:

- replay the Java fixture through `compile_plan_to_sql`,
- add focused join and union regression coverage,
- keep union branch aliases hidden while allowing the union result alias,
- reject projected aliases that shadow visible source aliases before SQL
  rendering,
- use SQL Server subquery composition when a composed join source is embedded
  by a derived query.

## Non-Scope

- Stable relation reuse beyond the source-alias/union boundary fixed here.
- Aggregate join implementation.
- Odoo domain packs, registry pulls, or generated business model refresh.

## Acceptance

- Java snapshot exporter compiles and produces the new cases.
- Python focused join/union tests pass.
- Python Java compose snapshot replay plus manifest passes.
- Full Python pytest remains green or any environmental failure is recorded.
