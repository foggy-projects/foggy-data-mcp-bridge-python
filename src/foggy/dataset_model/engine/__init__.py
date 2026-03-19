"""Engine package for semantic layer query execution."""

from foggy.dataset_model.engine.expression import (
    SqlExp,
    SqlLiteralExp,
    SqlColumnExp,
    SqlBinaryExp,
    SqlUnaryExp,
    SqlInExp,
    SqlBetweenExp,
    SqlFunctionExp,
    SqlCaseExp,
    SqlOperator,
    col,
    lit,
    and_,
    or_,
)
from foggy.dataset_model.engine.hierarchy import (
    HierarchyOperator,
    HierarchyDirection,
    ChildrenOfOperator,
    DescendantsOfOperator,
    SelfAndDescendantsOfOperator,
    AncestorsOfOperator,
    SelfAndAncestorsOfOperator,
    SiblingsOfOperator,
    LevelOperator,
)

__all__ = [
    # Expression classes
    "SqlExp",
    "SqlLiteralExp",
    "SqlColumnExp",
    "SqlBinaryExp",
    "SqlUnaryExp",
    "SqlInExp",
    "SqlBetweenExp",
    "SqlFunctionExp",
    "SqlCaseExp",
    "SqlOperator",
    # Expression helpers
    "col",
    "lit",
    "and_",
    "or_",
    # Hierarchy operators
    "HierarchyOperator",
    "HierarchyDirection",
    "ChildrenOfOperator",
    "DescendantsOfOperator",
    "SelfAndDescendantsOfOperator",
    "AncestorsOfOperator",
    "SelfAndAncestorsOfOperator",
    "SiblingsOfOperator",
    "LevelOperator",
]