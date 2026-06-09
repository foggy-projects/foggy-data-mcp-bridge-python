from pathlib import Path

from foggy.dataset_model.semantic.formula_compiler import FormulaCompiler
from foggy.dataset_model.semantic.formula_dialect import SqlDialect
from scripts.audit_qm_formulas import audit_file, iter_formula_occurrences


def test_iter_formula_occurrences_joins_multiline_string_literals() -> None:
    text = """
    {
      formula: "sum(if(move$moveType == 'out_invoice'"
        + " && move$state == 'posted',"
        + " amountResidual, 0))",
    }
    """

    formulas = iter_formula_occurrences(text)

    assert len(formulas) == 1
    assert formulas[0].expression == (
        "sum(if(move$moveType == 'out_invoice'"
        " && move$state == 'posted',"
        " amountResidual, 0))"
    )


def test_audit_file_skips_window_formulas(tmp_path: Path) -> None:
    qm = tmp_path / "WindowQueryModel.qm"
    qm.write_text(
        """
        exports.queryModel = {
          fieldGroups: [{
            items: [{
              name: 'salesRank',
              formula: 'RANK()',
              partitionBy: ['product$categoryName'],
              windowOrderBy: [{ field: 'salesAmount', dir: 'desc' }],
              type: 'INTEGER'
            }]
          }]
        };
        """,
        encoding="utf-8",
    )

    report = audit_file(qm, FormulaCompiler(SqlDialect.of("mysql")))

    assert report.total == 1
    assert report.passed == 0
    assert report.failed == 0
    assert report.skipped == 1
    assert report.formula_rows[0].status == "skip"
