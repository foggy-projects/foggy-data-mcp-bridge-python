# P1-1 Semantic Scale Namespace Opt-Out Or Live Result Parity Progress

Date: 2026-06-09

## Completed

- Recorded the remaining semantic-scale gap as a P1 decision rather than P0
  implementation work.
- Confirmed current P0 scope already has neutral snapshot coverage for helper,
  SQL, metadata, and fail-closed carrier-column behavior.
- Split the next step into two explicit options: namespace opt-out config
  parity or live DB/result parity.

## Follow-Up

Choose one option based on runtime need:

- If deployments need a compatibility switch, implement namespace opt-out.
- If confidence in numeric output is more important, add live result parity
  evidence first.
