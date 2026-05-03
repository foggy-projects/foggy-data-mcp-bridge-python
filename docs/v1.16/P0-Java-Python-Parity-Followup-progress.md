# P0 Java/Python Parity Follow-Up Progress

## 文档作用

- doc_type: progress
- status: initialized
- intended_for: root-controller / execution-agent / reviewer / signoff-owner
- purpose: 跟踪 v1.16 Java/Python parity follow-up intake 的逐项确认、测试要求和后续衔接。

## Version

- version: v1.16
- source_doc: `docs/v1.16/P0-Java-Python-Parity-Followup-Confirmation.md`
- current_phase: intake

## Development Progress

| Item | Status | Decision | Next Step |
|---|---|---|---|
| JP-FU-01 CALCULATE SQL Server oracle | pending-confirmation | TBD | Confirm whether SQL Server CALCULATE should become a public parity claim. |
| JP-FU-02 Stable relation join/union as source | pending-confirmation | TBD | Confirm business demand and whether design should start. |
| JP-FU-03 Pivot SQL Server cascade oracle | pending-confirmation | TBD | Confirm whether to wait for Java implementation or continue refusal. |
| JP-FU-04 Pivot MySQL5.7 live evidence | pending-confirmation | TBD | Confirm support policy for MySQL5.7. |
| JP-FU-05 tree+cascade semantic spec | pending-confirmation | TBD | Confirm semantic-design investment. |
| JP-FU-06 outer Pivot cache | pending-confirmation | TBD | Confirm whether telemetry justifies cache design. |

## Testing Progress

Current baseline:

- v1.15 stable relation matrix: `16 passed in 1.21s`.
- v1.15 Pivot cascade/refusal/totals matrix: `44 passed in 1.66s`.
- v1.15 full regression: `3977 passed in 17.98s`.

Future test tracking:

| Item | Required Test Status | Notes |
|---|---|---|
| JP-FU-01 | not-run | Needs SQL Server CALCULATE oracle only if accepted. |
| JP-FU-02 | not-run | Needs four-dialect relation source oracle only if accepted. |
| JP-FU-03 | not-run | Needs SQL Server cascade oracle only if accepted. |
| JP-FU-04 | not-run | Needs live MySQL5.7 refusal/oracle only if accepted. |
| JP-FU-05 | not-run | Needs semantic oracle matrix after design. |
| JP-FU-06 | not-run | Needs cache correctness/performance tests after design. |

## Experience Progress

- N/A. No UI or user-facing workflow change in this planning stage.

## Acceptance Criteria Checklist

| Criterion | Status |
|---|---|
| All six follow-up items are documented | done |
| Each item has a suggested iteration | done |
| Each item has confirmation questions | done |
| Each item has required tests if accepted | done |
| No item is marked implementation-ready without review | done |
| Current v1.15 parity signoff remains unchanged | done |

## Blockers

- none for documentation intake.

## Handoff Notes

Before starting any implementation:

- Update this progress doc with the chosen item decision.
- Create a dedicated item requirement/plan package.
- Do not implement directly from the intake matrix.
