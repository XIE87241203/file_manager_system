import sqlite3
from abc import ABC, abstractmethod
from typing import List

from backend.model.file_lifecycle_result import FileIndexChangeResult
from backend.model.file_move_info import FileMoveInfo


class FileIndexLifecycleAdapter(ABC):
    """
    用途：文件相关索引的生命周期适配器基类，统一移动、永久删除、回收站和恢复操作。
    """

    index_name: str = ''

    @abstractmethod
    def move(self, changes: List[FileMoveInfo], conn: sqlite3.Connection) -> FileIndexChangeResult:
        """
        用途说明：在文件移动后同步索引路径。
        入参说明：changes (List[FileMoveInfo]) - 路径变更列表；conn (sqlite3.Connection) - 调用方事务连接。
        返回值说明：FileIndexChangeResult - 当前索引的影响行数。
        """

    @abstractmethod
    def delete(self, file_paths: List[str], conn: sqlite3.Connection) -> FileIndexChangeResult:
        """
        用途说明：在文件永久删除后清理索引数据。
        入参说明：file_paths (List[str]) - 文件路径列表；conn (sqlite3.Connection) - 调用方事务连接。
        返回值说明：FileIndexChangeResult - 当前索引的影响行数。
        """

    @abstractmethod
    def recycle(self, file_paths: List[str], conn: sqlite3.Connection) -> FileIndexChangeResult:
        """
        用途说明：在文件移入回收站后处理索引副作用。
        入参说明：file_paths (List[str]) - 文件路径列表；conn (sqlite3.Connection) - 调用方事务连接。
        返回值说明：FileIndexChangeResult - 当前索引的影响行数。
        """

    @abstractmethod
    def restore(self, file_paths: List[str], conn: sqlite3.Connection) -> FileIndexChangeResult:
        """
        用途说明：在文件从回收站恢复后处理索引副作用。
        入参说明：file_paths (List[str]) - 文件路径列表；conn (sqlite3.Connection) - 调用方事务连接。
        返回值说明：FileIndexChangeResult - 当前索引的影响行数。
        """
