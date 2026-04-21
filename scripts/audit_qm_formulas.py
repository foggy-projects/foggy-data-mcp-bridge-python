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
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional

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

# ``formula: '...'`` / ``formula: "..."`` — matches single and double quoted
# string literals on a single line.  Escaped quotes are preserved.
_FORMULA_RE = re.compile(
    r"""\bformula\s*:\s*(?P<quote>['"])(?P<expr>(?:\\.|(?!(?P=quote)).)*)(?P=quote)""",
    re.MULTILINE,
)

# ``filter_condition: '...'`` / ``filterCondition: '...'`` / ``filter_condition: "..."``
_FILTER_COND_RE = re.compile(
    r"""\b(?:filter_condition|filterCondition)\s*:\s*(?P<quote>['"])(?P<expr>(?:\\.|(?!(?P=quote)).)*)(?P=quote)""",
    re.MULTILINE,
)


# ---------------------------------------------------------------------------
# Data shape
# ---------------------------------------------------------------------------


@dataclass
class FormulaRow:
    """One formula entry from a QM file."""

    qm_file: Path
    line: int
    expression: str
    status: str  # "pass" | "fail"
    error: Optional[str] = None


@dataclass
class QmReport:
    """Aggregate per-QM-file report."""

    qm_file: Path
    formula_rows: List[FormulaRow] = field(default_factory=list)
    filter_condition_count: int = 0

    @property
    def total(self) -> int:
        return len(self.formula_rows)

    @property
    def passed(self) -> int:
        return sum(1 for r in self.formula_rows if r.status == "pass")

    @property
    def failed(self) -> int:
        return self.total - self.passed


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


def iter_qm_files(roots: Iterable[Path]) -> List[Path]:
    """Collect ``*.qm`` paths from a list of roots (recursive)."""
    seen: set[Path] = set()
    out: List[Path] = []
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

    for m in _FORMULA_RE.finditer(text):
        expr = m.group("expr")
        line_no = _offset_to_line(text, m.start())
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


def audit_roots(roots: Iterable[Path], dialect: str = "mysql") -> List[QmReport]:
    """Audit every QM under the given roots and return per-file reports."""
    compiler = FormulaCompiler(SqlDialect.of(dialect))
    reports: List[QmReport] = []
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


def render_markdown(reports: List[QmReport], roots: List[Path]) -> str:
    """Produce a Markdown compatibility report."""
    lines: List[str] = []
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
    total_filter_cond = sum(r.filter_condition_count for r in reports)

    lines.append(f"- QM files with formulas: **{len(reports)}**")
    lines.append(f"- Formula expressions: **{total_formulas}**")
    lines.append(f"- Compiler-compatible: **{total_pass}**")
    lines.append(f"- Compiler-incompatible: **{total_fail}**")
    lines.append(f"- `filter_condition` usages: **{total_filter_cond}**  (expected 0)")
    lines.append("")

    lines.append("## Per-file breakdown")
    lines.append("")
    lines.append("| QM file | formulas | pass | fail | filter_condition |")
    lines.append("|---|---:|---:|---:|---:|")
    for report in reports:
        lines.append(
            f"| `{report.qm_file}` | {report.total} | {report.passed} | "
            f"{report.failed} | {report.filter_condition_count} |"
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

    return "\n".join(lines).rstrip() + "\n"


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def _parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
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


def main(argv: Optional[List[str]] = None) -> int:
    args = _parse_args(argv)
    roots: List[Path] = args.roots if args.roots else list(DEFAULT_ROOTS)
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
