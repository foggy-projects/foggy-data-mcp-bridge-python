# P1-1 Semantic Scale Namespace Opt-Out Or Live Result Parity

Date: 2026-06-09

## Goal

Close the remaining semantic scale evidence gap after P0-30/P0-32/P0-33/P0-35
by choosing one bounded P1 path: namespace-level opt-out parity or live
DB/result parity.

## Current Coverage

Python already covers:

- `semanticScaleFactor` model loading for properties and measures,
- scaled SQL helper literal formatting,
- V3 metadata exposure,
- fail-closed carrier-column validation,
- Java-exported neutral semantic-scale snapshot replay,
- explicit HAVING aggregate-alias strictness and field-collision refusal.

## Gap

Java has namespace/application-level control for disabling semantic scale while
loading the same TM. Python has no recorded equivalent config parity in the
active P0 lane. Python also has no current live DB/result parity evidence for
semantic scale beyond SQL/metadata snapshots.

## Options

1. Add Python namespace opt-out parity.
   - Best when runtime deployments need a compatibility switch.
   - Requires config/loader/service boundary design.
2. Add live DB/result parity evidence.
   - Best when product confidence in scaled numeric results is the priority.
   - Requires SQLite mandatory evidence and optional MySQL/Postgres profile
     gates.

## Non-Scope

- Changing existing semantic scale SQL semantics without a failing snapshot.
- Adding arbitrary SQL fragment support.
- Odoo model refresh.

## Acceptance

- Chosen path has a small design note, focused tests, and versioned progress.
- Existing P0 semantic scale snapshot replay remains green.
- Any optional external DB lane skips with explicit prerequisites when the DB
  is unavailable.
