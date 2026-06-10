# P0-54 Registry Odoo Consumer Readonly Audit

## Requirement

Prove that the Python model-registry consumer can consume the current Odoo
`1.1.10` community/pro bundles without updating the committed generated Odoo
model directory.

This closes the P1 validation-infrastructure gap from the alignment plan while
preserving the current phase boundary: no Odoo business-model refresh and no
generated bundle commit.

## Scope

- Pull `foggy.odoo.community@1.1.10` from the local registry into a temp output.
- Pull `foggy.odoo.pro@1.1.10` from the local registry into a temp output using
  a local readonly key value.
- Run `scripts/check-model-drift.py` against each temp output.
- Load each temp output through `load_models_from_directory(..., namespace="odoo")`.
- Assert representative new `1.1.10` TM/QM names are present.
- Keep the existing committed `src/foggy/demo/models/odoo` directory unchanged.

## Non-Goals

- Do not refresh committed Odoo generated models.
- Do not add Odoo domain fixture packs.
- Do not add a full AI domain direct runner.
- Do not change registry bundle content.

## Acceptance

- A focused integration test covers local-registry temp pull, drift check, and
  loader compatibility for community and pro.
- The test skips clearly when the local registry data directory is unavailable.
- Current committed Odoo model drift is recorded, not hidden.
- Focused pytest and ruff pass.
