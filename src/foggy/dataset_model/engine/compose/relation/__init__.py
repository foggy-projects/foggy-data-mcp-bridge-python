"""S7a Stable Relation constants and models.

Cross-language parity contract: mirrors Java
``com.foggyframework.dataset.db.model.engine.compose.relation`` package.
"""

from .constants import (
    ReferencePolicy,
    RelationPermissionState,
    RelationWrapStrategy,
    SemanticKind,
)
from .models import (
    CompiledRelation,
    CteItem,
    RelationCapabilities,
    RelationSql,
)

__all__ = [
    "SemanticKind",
    "ReferencePolicy",
    "RelationWrapStrategy",
    "RelationPermissionState",
    "CteItem",
    "RelationSql",
    "RelationCapabilities",
    "CompiledRelation",
]
