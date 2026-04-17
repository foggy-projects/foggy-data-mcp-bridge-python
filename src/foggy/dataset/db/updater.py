"""
数据库更新器接口

基于 Java DbUpdater 迁移
"""

import logging
from abc import ABC, abstractmethod
from typing import List, Optional, Any, TYPE_CHECKING
from enum import IntEnum

if TYPE_CHECKING:
    from foggy.dataset.table.sql_table import SqlTable
    from foggy.dataset.table.sql_column import SqlColumn

_logger = logging.getLogger(__name__)


class ExecutionMode(IntEnum):
    """执行模式"""
    NORMAL = 1      # 正常模式，出错抛异常
    SKIP_ERROR = 2  # 跳过错误模式


class SqlObject(ABC):
    """SQL 对象基类"""

    @abstractmethod
    def get_create_script(self) -> str:
        """获取创建脚本"""
        pass

    @abstractmethod
    def get_modify_script(self) -> str:
        """获取修改脚本"""
        pass


class DbUpdater(ABC):
    """
    数据库更新器接口

    用于执行数据库 DDL 操作（创建表、修改表、创建索引等）。
    """

    @abstractmethod
    def add_db_object(self, db_object: SqlObject) -> None:
        """
        添加数据库对象到执行队列

        Args:
            db_object: 数据库对象
        """
        pass

    @abstractmethod
    def add_create_script(self, db_object: SqlObject) -> None:
        """
        添加创建脚本

        Args:
            db_object: 数据库对象
        """
        pass

    @abstractmethod
    def add_modify_script(self, db_object: SqlObject) -> None:
        """
        添加修改脚本

        Args:
            db_object: 数据库对象
        """
        pass

    @abstractmethod
    def clear(self) -> None:
        """清空执行队列"""
        pass

    @abstractmethod
    def execute(self, mode: int = ExecutionMode.NORMAL) -> None:
        """
        执行所有脚本

        Args:
            mode: 执行模式

        Raises:
            SQLException: 执行失败
        """
        pass

    @abstractmethod
    def add_index(self, table: 'SqlTable', column: 'SqlColumn') -> None:
        """
        添加索引

        Args:
            table: 表对象
            column: 列对象
        """
        pass


class JdbcUpdater(DbUpdater):
    """
    JDBC 更新器实现

    使用 JDBC（或 Python 的数据库驱动）执行数据库操作。
    """

    def __init__(self, connection: Optional[Any] = None):
        """
        初始化更新器

        Args:
            connection: 数据库连接
        """
        self._connection = connection
        self._scripts: List[str] = []
        self._db_objects: List[SqlObject] = []

    def set_connection(self, connection: Any) -> None:
        """设置数据库连接"""
        self._connection = connection

    def add_db_object(self, db_object: SqlObject) -> None:
        """添加数据库对象"""
        self._db_objects.append(db_object)

    def add_create_script(self, db_object: SqlObject) -> None:
        """添加创建脚本"""
        script = db_object.get_create_script()
        if script:
            self._scripts.append(script)

    def add_modify_script(self, db_object: SqlObject) -> None:
        """添加修改脚本"""
        script = db_object.get_modify_script()
        if script:
            self._scripts.append(script)

    def clear(self) -> None:
        """清空执行队列"""
        self._scripts.clear()
        self._db_objects.clear()

    def execute(self, mode: int = ExecutionMode.NORMAL) -> None:
        """
        执行所有脚本

        Args:
            mode: 执行模式

        Raises:
            Exception: 执行失败
        """
        if not self._connection:
            raise ValueError("Database connection not set")

        errors = []

        for script in self._scripts:
            try:
                self._execute_script(script)
            except Exception as e:
                if mode == ExecutionMode.SKIP_ERROR:
                    errors.append(str(e))
                else:
                    raise

        if errors:
            _logger.warning("Execution completed with %d errors", len(errors))

    def add_index(self, table: 'SqlTable', column: 'SqlColumn') -> None:
        """添加索引"""
        index_name = f"idx_{table.name}_{column.name}"
        script = f"CREATE INDEX {index_name} ON {table.name} ({column.name})"
        self._scripts.append(script)

    def _execute_script(self, script: str) -> None:
        """执行单个脚本"""
        if hasattr(self._connection, 'execute'):
            # 异步连接
            import asyncio
            asyncio.get_event_loop().run_until_complete(
                self._connection.execute(script)
            )
        else:
            # 同步连接
            cursor = self._connection.cursor()
            cursor.execute(script)
            self._connection.commit()
            cursor.close()

    async def execute_async(self, mode: int = ExecutionMode.NORMAL) -> None:
        """
        异步执行所有脚本

        Args:
            mode: 执行模式
        """
        if not self._connection:
            raise ValueError("Database connection not set")

        errors = []

        for script in self._scripts:
            try:
                await self._execute_script_async(script)
            except Exception as e:
                if mode == ExecutionMode.SKIP_ERROR:
                    errors.append(str(e))
                else:
                    raise

        if errors:
            _logger.warning("Execution completed with %d errors", len(errors))

    async def _execute_script_async(self, script: str) -> None:
        """异步执行单个脚本"""
        await self._connection.execute(script)