"""Audit QM formula expressions against FormulaCompiler v1 whitelist.

v1.4 M4 Step 4.2 (REQ-FORMULA-EXTEND):
  - Scan every ``*.qm`` file under the configured roots
  - Extract the ``formula:`` string from each calculated field / measure
  - Try to compile each expression with ``FormulaCompiler`` (dry-run with
    a pass-through field resolver; the compiler only verifies AST
    white-list + parser correctness, not field existence)
  - Also count ``filter_condition`` / ``filterCondition`` usage — the
    authoritative answer should be 0 (the field is deprecated in M4)
  - Emit a Markdown compatibility report

This script doubles as the canary for any new calc that slips past Spec
v1 — once ``_build_calculated_field_sql`` is on the compiler path
(Step 4.1), any formula that fails here would fail at runtime too.

Usage::

    # Scan the default roots (Python demo + Odoo Pro authority)
    python scripts/audit_qm_formulas.py

    # Scan a custom root (e.g. a standalone Odoo Pro clone)
    python scripts/audit_qm_formulas.py --root ../foggy-odoo-bridge-pro/foggy_mcp_pro/setup/foggy-models/

    # Print a pretty-printed report file
    python scripts/audit_qm_formulas.py --out docs/v1.4/audit-qm-formulas.md
"""

from __future__ import annotations

import argparse
import re
import sys
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

# Ensure the package is importable when running the script from repo root.
_REPO_ROOT = Path(__file__).resolve().parents[1]
_SRC = _REPO_ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from foggy.dataset_model.semantic.formula_compiler import FormulaCompiler  # noqa: E402
from foggy.dataset_model.semantic.formula_dialect import SqlDialect  # noqa: E402
from foggy.dataset_model.semantic.formula_errors import FormulaError  # noqa: E402

# ---------------------------------------------------------------------------
# Default scan roots
# ---------------------------------------------------------------------------

# The Python demo models ship with a small set of QMs used by the
# in-memory SQLite harness.  The Odoo Pro authority hosts the live
# calculated-field definitions the pro gateway consumes.  Both are
# in-scope for M4 compatibility auditing.
DEFAULT_ROOTS = [
    _REPO_ROOT / "src" / "foggy" / "demo",
    _REPO_ROOT.parent / "foggy-odoo-bridge-pro" / "foggy_mcp_pro" / "setup" / "foggy-models",
]


# ---------------------------------------------------------------------------
# Regex patterns
# ---------------------------------------------------------------------------

# ``filter_condition: '...'`` / ``filterCondition: '...'`` / ``filter_condition: "..."``
_FILTER_COND_RE = re.compile(
    r"""\b(?:filter_condition|filterCondition)\s*:\s*(?P<quote>['"])(?P<expr>(?:\\.|(?!(?P=quote)).)*)(?P=quote)""",
    re.MULTILINE,
)

_FORMULA_KEY_RE = re.compile(r"\bformula\s*:")
_WINDOW_KEYS = ("partitionBy", "windowOrderBy", "windowFrame")


# ---------------------------------------------------------------------------
# Data shape
# ---------------------------------------------------------------------------


@dataclass
class FormulaRow:
    """One formula entry from a QM file."""

    qm_file: Path
    line: int
    expression: str
    status: str  # "pass" | "fail" | "skip"
    error: str | None = None


@dataclass
class QmReport:
    """Aggregate per-QM-file report."""

    qm_file: Path
    formula_rows: list[FormulaRow] = field(default_factory=list)
    filter_condition_count: int = 0

    @property
    def total(self) -> int:
        return len(self.formula_rows)

    @property
    def passed(self) -> int:
        return sum(1 for r in self.formula_rows if r.status == "pass")

    @property
    def failed(self) -> int:
        return sum(1 for r in self.formula_rows if r.status == "fail")

    @property
    def skipped(self) -> int:
        return sum(1 for r in self.formula_rows if r.status == "skip")


@dataclass
class FormulaOccurrence:
    """Parsed ``formula:`` occurrence from a JS-like QM file."""

    line: int
    expression: str
    end_offset: int


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------


def _pass_through_resolver(name: str) -> str:
    """Identity resolver: return the semantic name verbatim.

    The compiler only uses this to emit the ``VariableExpression`` output;
    AST validation happens before resolver invocation for non-field
    nodes, so the resolver being pass-through does not mask validator
    errors.  Field existence is intentionally out of scope — QM audit
    runs without loading the associated TM.
    """
    return name


def _offset_to_line(text: str, offset: int) -> int:
    """1-based line number for a character offset."""
    return text.count("\n", 0, offset) + 1


def _skip_ws(text: str, offset: int) -> int:
    while offset < len(text) and text[offset].isspace():
        offset += 1
    return offset


def _parse_quoted_js_string(text: str, offset: int) -> tuple[str, int] | None:
    if offset >= len(text) or text[offset] not in ("'", '"'):
        return None

    quote = text[offset]
    offset += 1
    out: list[str] = []
    while offset < len(text):
        ch = text[offset]
        if ch == "\\" and offset + 1 < len(text):
            out.append(ch)
            out.append(text[offset + 1])
            offset += 2
            continue
        if ch == quote:
            return "".join(out), offset + 1
        out.append(ch)
        offset += 1
    return None


def iter_formula_occurrences(text: str) -> list[FormulaOccurrence]:
    """Extract ``formula:`` string expressions, including ``"a" + "b"`` forms.

    QM files are JavaScript-like model definitions rather than strict JSON.
    A regex is sufficient for simple one-line values, but production Odoo
    formulas commonly split long conditional aggregates across concatenated
    string literals.  The scanner stays narrow: it only parses quoted literals
    joined by ``+`` immediately after a ``formula:`` key.
    """
    out: list[FormulaOccurrence] = []
    for match in _FORMULA_KEY_RE.finditer(text):
        offset = _skip_ws(text, match.end())
        parts: list[str] = []
        parsed = _parse_quoted_js_string(text, offset)
        if parsed is None:
            continue
        part, offset = parsed
        parts.append(part)

        while True:
            next_offset = _skip_ws(text, offset)
            if next_offset >= len(text) or text[next_offset] != "+":
                offset = next_offset
                break
            parsed = _parse_quoted_js_string(text, _skip_ws(text, next_offset + 1))
            if parsed is None:
                offset = next_offset
                break
            part, offset = parsed
            parts.append(part)

        out.append(FormulaOccurrence(
            line=_offset_to_line(text, match.start()),
            expression="".join(parts),
            end_offset=offset,
        ))
    return out


def _is_window_formula(text: str, formula: FormulaOccurrence) -> bool:
    next_formula = text.find("formula", formula.end_offset)
    next_item = text.find("\n                {", formula.end_offset)
    end_candidates = [i for i in (next_formula, next_item) if i != -1]
    probe_end = min(end_candidates) if end_candidates else min(len(text), formula.end_offset + 800)
    return any(key in text[formula.end_offset:probe_end] for key in _WINDOW_KEYS)


def iter_qm_files(roots: Iterable[Path]) -> list[Path]:
    """Collect ``*.qm`` paths from a list of roots (recursive)."""
    seen: set[Path] = set()
    out: list[Path] = []
    for root in roots:
        if not root.exists():
            continue
        for p in root.rglob("*.qm"):
            rp = p.resolve()
            if rp not in seen:
                seen.add(rp)
                out.append(p)
    out.sort()
    return out


def audit_file(qm_path: Path, compiler: FormulaCompiler) -> QmReport:
    """Audit a single QM file; return per-file report."""
    text = qm_path.read_text(encoding="utf-8")
    report = QmReport(qm_file=qm_path)

    for formula in iter_formula_occurrences(text):
        expr = formula.expression
        line_no = formula.line
        if _is_window_formula(text, formula):
            report.formula_rows.append(FormulaRow(
                qm_file=qm_path, line=line_no, expression=expr, status="skip",
                error="window formula; covered by window-function path",
            ))
            continue
        try:
            compiler.compile(expr, _pass_through_resolver)
            report.formula_rows.append(FormulaRow(
                qm_file=qm_path, line=line_no, expression=expr, status="pass",
            ))
        except FormulaError as e:
            report.formula_rows.append(FormulaRow(
                qm_file=qm_path, line=line_no, expression=expr,
                status="fail", error=f"{type(e).__name__}: {e}",
            ))
        except Exception as e:  # pragma: no cover — defensive
            report.formula_rows.append(FormulaRow(
                qm_file=qm_path, line=line_no, expression=expr,
                status="fail", error=f"{type(e).__name__}: {e}",
            ))

    report.filter_condition_count = sum(1 for _ in _FILTER_COND_RE.finditer(text))
    return report


def audit_roots(roots: Iterable[Path], dialect: str = "mysql") -> list[QmReport]:
    """Audit every QM under the given roots and return per-file reports."""
    compiler = FormulaCompiler(SqlDialect.of(dialect))
    reports: list[QmReport] = []
    for qm in iter_qm_files(roots):
        # Skip files without any interesting keywords — cheap optimisation
        # that also avoids emitting noisy empty rows.
        text = qm.read_text(encoding="utf-8")
        if "formula" not in text and "filter_condition" not in text and "filterCondition" not in text:
            continue
        reports.append(audit_file(qm, compiler))
    return reports


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------


def render_markdown(reports: list[QmReport], roots: list[Path]) -> str:
    """Produce a Markdown compatibility report."""
    lines: list[str] = []
    lines.append("# QM Formula Compatibility Audit")
    lines.append("")
    lines.append("Scan roots:")
    lines.append("")
    for r in roots:
        exists = "(ok)" if r.exists() else "(missing)"
        lines.append(f"- `{r}` {exists}")
    lines.append("")
    lines.append("## Summary")
    lines.append("")

    total_formulas = sum(r.total for r in reports)
    total_pass = sum(r.passed for r in reports)
    total_fail = sum(r.failed for r in reports)
    total_skip = sum(r.skipped for r in reports)
    total_filter_cond = sum(r.filter_condition_count for r in reports)

    lines.append(f"- QM files with formulas: **{len(reports)}**")
    lines.append(f"- Formula expressions: **{total_formulas}**")
    lines.append(f"- Compiler-compatible: **{total_pass}**")
    lines.append(f"- Compiler-incompatible: **{total_fail}**")
    lines.append(f"- Window-formula skipped: **{total_skip}**")
    lines.append(f"- `filter_condition` usages: **{total_filter_cond}**  (expected 0)")
    lines.append("")

    lines.append("## Per-file breakdown")
    lines.append("")
    lines.append("| QM file | formulas | pass | fail | skip | filter_condition |")
    lines.append("|---|---:|---:|---:|---:|---:|")
    for report in reports:
        lines.append(
            f"| `{report.qm_file}` | {report.total} | {report.passed} | "
            f"{report.failed} | {report.skipped} | {report.filter_condition_count} |"
        )
    lines.append("")

    if total_fail > 0:
        lines.append("## Incompatible formulas")
        lines.append("")
        lines.append("Each row is a formula the compiler rejected.  Fix "
                     "before removing the legacy string-substitution fallback.")
        lines.append("")
        lines.append("| QM file | line | expression | error |")
        lines.append("|---|---:|---|---|")
        for report in reports:
            for row in report.formula_rows:
                if row.status == "fail":
                    # Escape vertical bars so markdown tables don't break.
                    expr_safe = row.expression.replace("|", "\\|")
                    err_safe = (row.error or "").replace("|", "\\|")
                    lines.append(
                        f"| `{row.qm_file}` | {row.line} | "
                        f"`{expr_safe}` | {err_safe} |"
                    )
        lines.append("")

    if total_skip > 0:
        lines.append("## Skipped window formulas")
        lines.append("")
        lines.append("These formulas have window metadata and are validated by the")
        lines.append("window-function query path instead of the scalar/aggregate")
        lines.append("FormulaCompiler whitelist audit.")
        lines.append("")
        lines.append("| QM file | line | expression | reason |")
        lines.append("|---|---:|---|---|")
        for report in reports:
            for row in report.formula_rows:
                if row.status == "skip":
                    expr_safe = row.expression.replace("|", "\\|")
                    reason_safe = (row.error or "").replace("|", "\\|")
                    lines.append(
                        f"| `{row.qm_file}` | {row.line} | "
                        f"`{expr_safe}` | {reason_safe} |"
                    )
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit QM formulas against FormulaCompiler v1.")
    parser.add_argument(
        "--root", dest="roots", action="append", type=Path,
        help="Scan root (repeatable). Defaults: Python demo + Odoo Pro authority.",
    )
    parser.add_argument(
        "--dialect", default="mysql",
        choices=["mysql", "postgres", "postgresql", "sqlserver", "mssql", "sqlite"],
        help="SQL dialect for compile (default mysql; does not affect audit pass/fail).",
    )
    parser.add_argument(
        "--out", type=Path, default=None,
        help="Output Markdown path. Defaults to stdout.",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="List the files that would be scanned and exit.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    roots: list[Path] = args.roots if args.roots else list(DEFAULT_ROOTS)
    roots = [r.resolve() for r in roots]

    files = iter_qm_files(roots)

    if args.dry_run:
        print(f"Would scan {len(files)} QM file(s):")
        for f in files:
            print(f"  {f}")
        return 0

    reports = audit_roots(roots, dialect=args.dialect)
    md = render_markdown(reports, roots)

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(md, encoding="utf-8")
        print(f"Wrote report: {args.out}")
    else:
        sys.stdout.write(md)

    # Non-zero exit when anything failed, so CI can gate on it.
    total_fail = sum(r.failed for r in reports)
    return 0 if total_fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
