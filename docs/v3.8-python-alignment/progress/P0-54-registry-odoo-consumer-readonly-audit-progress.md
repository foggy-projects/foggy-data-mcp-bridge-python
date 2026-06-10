# P0-54 Registry Odoo Consumer Readonly Audit Progress

## 2026-06-10

Status: complete.

Changes:

- Added `tests/integration/test_odoo_registry_consumer_readonly.py`.
- The test pulls `foggy.odoo.community@1.1.10` and `foggy.odoo.pro@1.1.10`
  from the local registry into pytest temp directories.
- The test runs `scripts/check-model-drift.py` against each temp output and
  loads both outputs through `load_models_from_directory(..., namespace="odoo")`.
- The test verifies representative new `1.1.10` TM/QM names:
  `OdooAccountPaymentBillMatch*`, `OdooPurchaseDocumentFlow*`,
  `OdooSaleDocumentFlow*`, plus pro-only `OdooMrpProduction*` and
  `OdooProjectTask*`.
- The committed `src/foggy/demo/models/odoo` generated directory was not
  updated.

Evidence:

- Manual temp-dir audit passed for both editions:
  community loaded `30` names and pro loaded `34` names from
  `/Users/fengjianguang/foggy-projects/foggy-model-registry/data`.
- Community temp lock:
  `foggy.odoo.community@1.1.10`,
  bundle checksum
  `sha256:9786929c84b0a4073c998210d4dde5255f7b4582a4042640ac7f34103cb17543`,
  content checksum
  `sha256:4ca273a9d215c0e1d521c9b023f58f5c751061c9164b1a5ae12888f823162574`.
- Pro temp lock:
  `foggy.odoo.pro@1.1.10`,
  bundle checksum
  `sha256:e821093622e8dbc1006d63648bee5fbf37d0f7763d5b9d492c0eb144d35bf2a6`,
  content checksum
  `sha256:1a26e46d695a7c46134317e61436c24a4a7fde763b3a8e654b699212f90ec5af`.
- Focused pytest passed:
  `.venv/bin/python -m pytest tests/integration/test_odoo_registry_consumer_readonly.py -q`
  with `2 passed in 1.18s`.
- Ruff passed:
  `.venv/bin/ruff check tests/integration/test_odoo_registry_consumer_readonly.py`.
- Current committed demo Odoo directory still fails drift check by design:
  `foggy.odoo.community@1.1.9` lock expects
  `sha256:93a4a5bee662baf1892a68e6196fdca9057a0215c66b97ad92de6ff48888219b`,
  while the directory is
  `sha256:584aa35377f23690f77670a203bb01a1d405c44d835550d88c1ecd2e762c39e4`.

Follow-up:

- Keep Odoo pack/direct-runner work deferred until the user explicitly approves
  a generated Odoo model refresh or a separate fixture-pack lane.
