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
    ClosureTableDef,
    ParentChildDimensionDef,
    HierarchyConditionBuilder,
    HierarchyOperatorRegistry,
    get_default_hierarchy_registry,
)
from foggy.dataset_model.engine.dimension_path import DimensionPath

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
    # Hierarchy models & utilities
    "ClosureTableDef",
    "ParentChildDimensionDef",
    "HierarchyConditionBuilder",
    "HierarchyOperatorRegistry",
    "get_default_hierarchy_registry",
    # Dimension path
    "DimensionPath",
]
