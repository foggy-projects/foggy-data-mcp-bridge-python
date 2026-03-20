"""
TM/QM 文件加载器

基于 Java TableModelLoaderManagerImpl 迁移
支持从文件加载 TM（表模型）和 QM（查询模型）定义。
"""

import os
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from abc import ABC, abstractmethod

import yaml
from pydantic import BaseModel, Field

from foggy.dataset_model.definitions.base import (
    ColumnType,
    AggregationType,
    DimensionType,
    DbColumnDef,
)
from foggy.dataset_model.definitions.measure import DbMeasureDef, MeasureType
from foggy.dataset_model.definitions.query_model import DbQueryModelDef
from foggy.dataset_model.impl.model import (
    DbTableModelImpl,
    DbModelDimensionImpl,
    DbModelMeasureImpl,
)

logger = logging.getLogger(__name__)


class TableModelLoader(ABC):
    """表模型加载器接口"""

    @abstractmethod
    def load(self, definition: Dict[str, Any], context: "ModelLoadContext") -> DbTableModelImpl:
        pass

    @abstractmethod
    def get_type_name(self) -> str:
        pass


class ModelLoadContext(BaseModel):
    """模型加载上下文"""

    datasource: str = "default"
    schema_name: Optional[str] = None
    validate_on_load: bool = True
    fail_on_error: bool = False
    loaded_models: Dict[str, DbTableModelImpl] = Field(default_factory=dict)
    namespace: Optional[str] = None

    model_config = {"extra": "allow"}


class JdbcTableModelLoader(TableModelLoader):
    """JDBC 表模型加载器"""

    def load(self, definition: Dict[str, Any], context: ModelLoadContext) -> DbTableModelImpl:
        model_name = definition.get("name", "unknown")
        logger.info(f"Loading JDBC table model: {model_name}")

        model = DbTableModelImpl(
            name=model_name,
            alias=definition.get("alias"),
            description=definition.get("description"),
            source_table=definition.get("tableName", ""),
            source_schema=definition.get("schema"),
            source_datasource=definition.get("dataSourceName", context.datasource),
        )

        self._load_dimensions(model, definition, context)
        self._load_measures(model, definition, context)
        self._load_properties(model, definition, context)

        if definition.get("primaryKey"):
            pk = definition["primaryKey"]
            model.primary_key = pk if isinstance(pk, list) else [pk]

        if context.validate_on_load:
            errors = model.validate()
            if errors and context.fail_on_error:
                raise ValueError(f"Model validation failed: {errors}")

        return model

    def get_type_name(self) -> str:
        return "jdbc"

    def _load_dimensions(self, model: DbTableModelImpl, definition: Dict[str, Any], context: ModelLoadContext) -> None:
        for dim_def in definition.get("dimensions", []):
            if not dim_def:
                continue

            dim_name = dim_def.get("name")
            if not dim_name:
                continue

            dim_type = DimensionType.REGULAR
            if dim_def.get("type", "").lower() in ("datetime", "date", "time"):
                dim_type = DimensionType.TIME
            elif dim_def.get("parentKey"):
                dim_type = DimensionType.HIERARCHY

            dimension = DbModelDimensionImpl(
                name=dim_name,
                alias=dim_def.get("alias"),
                column=dim_def.get("column", dim_name),
                table=dim_def.get("tableName"),
                dimension_type=dim_type,
                data_type=self._parse_column_type(dim_def.get("type", "string")),
                is_hierarchical=bool(dim_def.get("parentKey")),
                hierarchy_table=dim_def.get("closureTableName"),
                parent_column=dim_def.get("parentKey"),
                level_column=dim_def.get("childKey"),
                visible=dim_def.get("visible", True),
                sortable=dim_def.get("sortable", True),
                filterable=dim_def.get("filterable", True),
                groupable=dim_def.get("groupable", True),
                dictionary=dim_def.get("dictClass"),
            )
            model.add_dimension(dimension)

    def _load_measures(self, model: DbTableModelImpl, definition: Dict[str, Any], context: ModelLoadContext) -> None:
        for measure_def in definition.get("measures", []):
            if not measure_def:
                continue

            measure_name = measure_def.get("name")
            if not measure_name:
                continue

            measure_type = MeasureType.CALCULATED if measure_def.get("expression") else MeasureType.BASIC

            agg_str = measure_def.get("aggregation", "sum").upper()
            agg_type = AggregationType.SUM
            for at in AggregationType:
                if at.value.upper() == agg_str:
                    agg_type = at
                    break

            measure = DbModelMeasureImpl(
                name=measure_name,
                alias=measure_def.get("alias"),
                column=measure_def.get("column"),
                table=measure_def.get("tableName"),
                measure_type=measure_type,
                aggregation=agg_type,
                distinct=measure_def.get("distinct", False),
                expression=measure_def.get("expression"),
                format_pattern=measure_def.get("format"),
                unit=measure_def.get("unit"),
                decimals=measure_def.get("decimals", 2),
                visible=measure_def.get("visible", True),
            )
            model.add_measure(measure)

    def _load_properties(self, model: DbTableModelImpl, definition: Dict[str, Any], context: ModelLoadContext) -> None:
        for prop_def in definition.get("properties", []):
            if not prop_def:
                continue

            prop_name = prop_def.get("name")
            if not prop_name:
                continue

            column = DbColumnDef(
                name=prop_name,
                alias=prop_def.get("alias"),
                column_type=self._parse_column_type(prop_def.get("type", "string")),
                nullable=prop_def.get("nullable", True),
                primary_key=prop_def.get("primaryKey", False),
                comment=prop_def.get("description"),
            )
            model.columns[prop_name] = column

    def _parse_column_type(self, type_str: str) -> ColumnType:
        type_lower = type_str.lower()
        type_mapping = {
            "string": ColumnType.STRING, "str": ColumnType.STRING, "varchar": ColumnType.STRING, "text": ColumnType.STRING,
            "int": ColumnType.INTEGER, "integer": ColumnType.INTEGER,
            "long": ColumnType.LONG, "bigint": ColumnType.LONG,
            "float": ColumnType.FLOAT, "double": ColumnType.DOUBLE,
            "decimal": ColumnType.DECIMAL, "numeric": ColumnType.DECIMAL,
            "bool": ColumnType.BOOLEAN, "boolean": ColumnType.BOOLEAN,
            "date": ColumnType.DATE, "datetime": ColumnType.DATETIME,
            "timestamp": ColumnType.TIMESTAMP, "time": ColumnType.TIME,
            "json": ColumnType.JSON, "array": ColumnType.ARRAY, "object": ColumnType.OBJECT,
        }
        return type_mapping.get(type_lower, ColumnType.STRING)


class TableModelLoaderManager:
    """表模型加载器管理器"""

    def __init__(self, model_dirs: Optional[List[str]] = None, validate_on_load: bool = True, fail_on_error: bool = False):
        self._model_dirs = model_dirs or []
        self._validate_on_load = validate_on_load
        self._fail_on_error = fail_on_error
        self._loaders: Dict[str, TableModelLoader] = {}
        self._model_cache: Dict[str, DbTableModelImpl] = {}
        self._qm_cache: Dict[str, DbQueryModelDef] = {}
        self.register_loader(JdbcTableModelLoader())

    def register_loader(self, loader: TableModelLoader) -> None:
        self._loaders[loader.get_type_name()] = loader

    def add_model_dir(self, directory: str) -> None:
        if directory not in self._model_dirs:
            self._model_dirs.append(directory)

    def clear_cache(self, namespace: Optional[str] = None) -> None:
        if namespace is None:
            self._model_cache.clear()
            self._qm_cache.clear()
        else:
            prefix = f"{namespace}:"
            self._model_cache = {k: v for k, v in self._model_cache.items() if not k.startswith(prefix)}
            self._qm_cache = {k: v for k, v in self._qm_cache.items() if not k.startswith(prefix)}

    def load_model(self, name: str, namespace: Optional[str] = None) -> DbTableModelImpl:
        full_name = f"{namespace}:{name}" if namespace else name

        if full_name in self._model_cache:
            return self._model_cache[full_name]

        model_file = self._find_model_file(name, "tm", namespace)
        if not model_file:
            raise FileNotFoundError(f"Model file not found: {name}")

        definition = self._load_definition(model_file)
        context = ModelLoadContext(
            datasource=definition.get("dataSourceName", "default"),
            schema_name=definition.get("schema"),
            validate_on_load=self._validate_on_load,
            fail_on_error=self._fail_on_error,
            namespace=namespace,
        )

        model_type = definition.get("type", "jdbc")
        loader = self._loaders.get(model_type)
        if not loader:
            raise ValueError(f"Loader not found for type: {model_type}")

        model = loader.load(definition, context)
        self._model_cache[full_name] = model
        return model

    def load_query_model(self, name: str, namespace: Optional[str] = None) -> DbQueryModelDef:
        full_name = f"{namespace}:{name}" if namespace else name

        if full_name in self._qm_cache:
            return self._qm_cache[full_name]

        qm_file = self._find_model_file(name, "qm", namespace)
        if not qm_file:
            raise FileNotFoundError(f"Query model file not found: {name}")

        definition = self._load_definition(qm_file)
        qm = DbQueryModelDef(
            name=definition.get("name", name),
            alias=definition.get("alias"),
            description=definition.get("description"),
            table_model=definition.get("tableModel"),
        )
        self._qm_cache[full_name] = qm
        return qm

    def _find_model_file(self, name: str, model_type: str, namespace: Optional[str] = None) -> Optional[str]:
        for model_dir in self._model_dirs:
            base_path = Path(model_dir)
            if namespace:
                ns_path = base_path / namespace
                if ns_path.exists():
                    base_path = ns_path

            for ext in [".yaml", ".yml", ".json"]:
                file_path = base_path / f"{name}.{model_type}{ext}"
                if file_path.exists():
                    return str(file_path)
        return None

    def _load_definition(self, file_path: str) -> Dict[str, Any]:
        path = Path(file_path)
        with open(path, "r", encoding="utf-8") as f:
            if path.suffix in (".yaml", ".yml"):
                return yaml.safe_load(f)
            return json.load(f)

    def get_model(self, name: str, namespace: Optional[str] = None) -> Optional[DbTableModelImpl]:
        full_name = f"{namespace}:{name}" if namespace else name
        return self._model_cache.get(full_name)

    def list_models(self, namespace: Optional[str] = None) -> List[str]:
        if namespace is None:
            return list(self._model_cache.keys())
        prefix = f"{namespace}:"
        return [k for k in self._model_cache if k.startswith(prefix)]


_global_loader: Optional[TableModelLoaderManager] = None


def get_loader() -> TableModelLoaderManager:
    global _global_loader
    if _global_loader is None:
        _global_loader = TableModelLoaderManager()
    return _global_loader


def init_loader(model_dirs: Optional[List[str]] = None, validate_on_load: bool = True, fail_on_error: bool = False) -> TableModelLoaderManager:
    global _global_loader
    _global_loader = TableModelLoaderManager(model_dirs=model_dirs, validate_on_load=validate_on_load, fail_on_error=fail_on_error)
    return _global_loader


__all__ = [
    "TableModelLoader",
    "JdbcTableModelLoader",
    "TableModelLoaderManager",
    "ModelLoadContext",
    "get_loader",
    "init_loader",
]