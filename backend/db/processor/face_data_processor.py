import sqlite3
from contextlib import nullcontext
from typing import List, Optional, Tuple

from backend.common.i18n_utils import t
from backend.common.log_utils import LogUtils
from backend.common.file_type_enum import FileType
from backend.db.db_constants import DBConstants
from backend.db.db_manager import db_manager
from backend.db.processor.base_db_processor import BaseDBProcessor
from backend.model.db.face_embedding_db_model import FaceEmbeddingDBModel
from backend.model.db.face_file_index_state_db_model import FaceFileIndexStateDBModel
from backend.model.db.face_queue_item_db_model import FaceQueueItemDBModel
from backend.model.db.file_index_db_model import FileIndexDBModel
from backend.model.face_index_result import FaceIndexSummaryResult
from backend.model.file_move_info import FileMoveInfo


class FaceDataProcessor:
    """
    用途说明：人脸索引数据处理器，统一维护图片处理状态、多人脸特征和增量查询。
    关联方式：使用 file_path 而非文件索引主键，避免 INSERT OR REPLACE 重建索引后人脸数据失联。
    """

    @staticmethod
    def get_pending_images(pipeline_version: str, after_file_path: str = '',
                           limit: int = 200) -> List[FileIndexDBModel]:
        """
        用途说明：按文件路径游标分批获取尚未按指定流水线成功处理的相册图片。
        入参说明：
            pipeline_version (str): 模型与处理流水线版本。
            after_file_path (str): 上一批最后一个文件路径，空字符串表示从开头读取。
            limit (int): 单批最大记录数，建议 100～1000。
        返回值说明：List[FileIndexDBModel] - 按文件路径升序排列的待处理图片列表。
        """
        state = DBConstants.FaceIndexState
        file_index = DBConstants.FileIndex
        query: str = f"""
            SELECT f.* FROM {file_index.TABLE_NAME} f
            LEFT JOIN {state.TABLE_NAME} s ON s.{state.COL_FILE_PATH} = f.{file_index.COL_FILE_PATH}
            WHERE f.{file_index.COL_FILE_TYPE} = ?
              AND (f.{file_index.COL_RECYCLE_BIN_TIME} IS NULL OR f.{file_index.COL_RECYCLE_BIN_TIME} = '')
              AND f.{file_index.COL_FILE_PATH} > ?
              AND (s.{state.COL_FILE_PATH} IS NULL
                   OR s.{state.COL_FILE_MD5} != f.{file_index.COL_FILE_MD5}
                   OR s.{state.COL_PIPELINE_VERSION} != ?)
            ORDER BY f.{file_index.COL_FILE_PATH} ASC
            LIMIT ?
        """
        rows: List[dict] = BaseDBProcessor._execute(
            query,
            (FileType.IMAGE.value, after_file_path, pipeline_version, limit),
            is_query=True
        )
        return [FileIndexDBModel(**row) for row in rows]

    @staticmethod
    def enqueue_pending_images(pipeline_version: str) -> bool:
        """
        用途说明：把当前仓库全部尚未按指定流水线处理的图片加入队列，并按文件路径去重。
        入参说明：pipeline_version (str) - 当前模型与处理流水线版本。
        返回值说明：bool - 是否完成批量入队；队列中已有路径只更新 MD5，不重复插入。
        """
        state = DBConstants.FaceIndexState
        file_index = DBConstants.FileIndex
        queue = DBConstants.FaceRecognitionQueue
        pending_filter: str = (
            f"f.{file_index.COL_FILE_TYPE} = ? "
            f"AND (f.{file_index.COL_RECYCLE_BIN_TIME} IS NULL OR f.{file_index.COL_RECYCLE_BIN_TIME} = '') "
            f"AND (s.{state.COL_FILE_PATH} IS NULL "
            f"OR s.{state.COL_FILE_MD5} != f.{file_index.COL_FILE_MD5} "
            f"OR s.{state.COL_PIPELINE_VERSION} != ?)"
        )
        try:
            with db_manager.transaction() as conn:
                BaseDBProcessor._execute(
                    f"INSERT OR IGNORE INTO {queue.TABLE_NAME} "
                    f"({queue.COL_FILE_PATH}, {queue.COL_FILE_MD5}) "
                    f"SELECT f.{file_index.COL_FILE_PATH}, f.{file_index.COL_FILE_MD5} "
                    f"FROM {file_index.TABLE_NAME} f "
                    f"LEFT JOIN {state.TABLE_NAME} s ON s.{state.COL_FILE_PATH} = f.{file_index.COL_FILE_PATH} "
                    f"WHERE {pending_filter}",
                    (FileType.IMAGE.value, pipeline_version),
                    conn=conn
                )
                BaseDBProcessor._execute(
                    f"UPDATE {queue.TABLE_NAME} AS q "
                    f"SET {queue.COL_FILE_MD5} = ("
                    f"SELECT f.{file_index.COL_FILE_MD5} FROM {file_index.TABLE_NAME} f "
                    f"LEFT JOIN {state.TABLE_NAME} s ON s.{state.COL_FILE_PATH} = f.{file_index.COL_FILE_PATH} "
                    f"WHERE f.{file_index.COL_FILE_PATH} = q.{queue.COL_FILE_PATH} AND {pending_filter}) "
                    f"WHERE EXISTS ("
                    f"SELECT 1 FROM {file_index.TABLE_NAME} f "
                    f"LEFT JOIN {state.TABLE_NAME} s ON s.{state.COL_FILE_PATH} = f.{file_index.COL_FILE_PATH} "
                    f"WHERE f.{file_index.COL_FILE_PATH} = q.{queue.COL_FILE_PATH} AND {pending_filter})",
                    (FileType.IMAGE.value, pipeline_version, FileType.IMAGE.value, pipeline_version),
                    conn=conn
                )
            return True
        except Exception as e:
            LogUtils.error(t('face_queue_enqueue_failed_log', error=str(e)))
            return False

    @staticmethod
    def enqueue_images(images: List[FileIndexDBModel]) -> bool:
        """
        用途说明：批量加入索引阶段发现的图片，file_path 唯一约束保证重复扫描不会重复入队。
        入参说明：images (List[FileIndexDBModel]) - 已成功写入文件索引的图片记录。
        返回值说明：bool - 是否完成去重入队。
        """
        queue = DBConstants.FaceRecognitionQueue
        data: List[tuple] = [
            (item.file_path, item.file_md5)
            for item in images
            if item.file_type == FileType.IMAGE.value
            and item.file_path
            and (item.recycle_bin_time is None or item.recycle_bin_time == '')
        ]
        if not data:
            return True
        query: str = (
            f"INSERT INTO {queue.TABLE_NAME} ({queue.COL_FILE_PATH}, {queue.COL_FILE_MD5}) "
            f"VALUES (?, ?) ON CONFLICT({queue.COL_FILE_PATH}) DO UPDATE SET "
            f"{queue.COL_FILE_MD5} = excluded.{queue.COL_FILE_MD5} "
            f"WHERE {queue.TABLE_NAME}.{queue.COL_FILE_MD5} != excluded.{queue.COL_FILE_MD5}"
        )
        try:
            BaseDBProcessor._execute_batch(query, data)
            return True
        except Exception as e:
            LogUtils.error(t('face_queue_enqueue_failed_log', error=str(e)))
            return False

    @staticmethod
    def get_queued_images(after_queue_id: int = 0, limit: int = 200) -> List[FaceQueueItemDBModel]:
        """
        用途说明：按队列主键游标分批读取有效图片，避免把整个队列加载到内存。
        入参说明：after_queue_id (int) - 上一批最后一个队列 ID；limit (int) - 单批最大数量。
        返回值说明：List[FaceQueueItemDBModel] - 已按队列 ID 升序排列的待识别图片。
        """
        queue = DBConstants.FaceRecognitionQueue
        file_index = DBConstants.FileIndex
        query: str = f"""
            SELECT q.* FROM {queue.TABLE_NAME} q
            INNER JOIN {file_index.TABLE_NAME} f ON f.{file_index.COL_FILE_PATH} = q.{queue.COL_FILE_PATH}
            WHERE q.{queue.COL_ID} > ?
              AND f.{file_index.COL_FILE_TYPE} = ?
              AND (f.{file_index.COL_RECYCLE_BIN_TIME} IS NULL OR f.{file_index.COL_RECYCLE_BIN_TIME} = '')
            ORDER BY q.{queue.COL_ID} ASC
            LIMIT ?
        """
        rows: List[dict] = BaseDBProcessor._execute(
            query, (after_queue_id, FileType.IMAGE.value, limit), is_query=True
        )
        return [FaceQueueItemDBModel(**row) for row in rows]

    @staticmethod
    def get_queue_count() -> int:
        """
        用途说明：获取当前仓库待识别队列中的有效图片数量，不加载队列明细。
        入参说明：无。
        返回值说明：int - 未移入回收站且仍存在文件索引的队列图片数量。
        """
        queue = DBConstants.FaceRecognitionQueue
        file_index = DBConstants.FileIndex
        query: str = f"""
            SELECT COUNT(*) AS count
            FROM {queue.TABLE_NAME} q
            INNER JOIN {file_index.TABLE_NAME} f
              ON f.{file_index.COL_FILE_PATH} = q.{queue.COL_FILE_PATH}
            WHERE f.{file_index.COL_FILE_TYPE} = ?
              AND {file_index.active_condition('f')}
        """
        row: Optional[dict] = BaseDBProcessor._execute(
            query, (FileType.IMAGE.value,), is_query=True, fetch_one=True
        )
        return int(row['count']) if row else 0

    @staticmethod
    def delete_queue_item(queue_id: int, file_md5: str,
                          conn: Optional[sqlite3.Connection] = None) -> bool:
        """
        用途说明：处理完成后按队列 ID 和 MD5 出队，避免误删处理期间重新入队的新版本。
        入参说明：
            queue_id (int): 队列主键。
            file_md5 (str): 本次处理使用的 MD5。
            conn (Optional[sqlite3.Connection]): 可选的外部事务连接。
        返回值说明：bool - 是否完成出队。
        """
        queue = DBConstants.FaceRecognitionQueue
        try:
            with (db_manager.transaction() if conn is None else nullcontext(conn)) as tx:
                BaseDBProcessor._execute(
                    f"DELETE FROM {queue.TABLE_NAME} WHERE {queue.COL_ID} = ? AND {queue.COL_FILE_MD5} = ?",
                    (queue_id, file_md5),
                    conn=tx
                )
            return True
        except Exception as e:
            LogUtils.error(t('face_queue_delete_failed_log', error=str(e)))
            return False

    @staticmethod
    def delete_queue_by_paths(file_paths: List[str],
                              conn: Optional[sqlite3.Connection] = None) -> bool:
        """
        用途说明：文件删除、改名或移入回收站时，按路径批量移除队列项。
        入参说明：
            file_paths (List[str]): 需要移除的图片完整路径。
            conn (Optional[sqlite3.Connection]): 可选的外部事务连接。
        返回值说明：bool - 是否完成队列清理。
        """
        try:
            FaceDataProcessor.delete_queue_by_paths_count(file_paths, conn=conn)
            return True
        except Exception as e:
            LogUtils.error(t('face_queue_delete_failed_log', error=str(e)))
            return False

    @staticmethod
    def delete_queue_by_paths_count(file_paths: List[str],
                                    conn: Optional[sqlite3.Connection] = None) -> int:
        """
        用途说明：按路径批量移除待识别队列并返回实际删除数量，可参与文件生命周期事务。
        入参说明：file_paths (List[str]) - 待移除队列的图片路径；conn (Optional[sqlite3.Connection]) - 外部事务连接。
        返回值说明：int - 实际删除的队列记录数。
        """
        if not file_paths:
            return 0
        queue: type = DBConstants.FaceRecognitionQueue
        affected_rows: int = 0
        batch_size: int = 500
        with (db_manager.transaction() if conn is None else nullcontext(conn)) as tx:
            for start in range(0, len(file_paths), batch_size):
                batch: List[str] = file_paths[start:start + batch_size]
                placeholders: str = ','.join('?' for _ in batch)
                affected_rows += BaseDBProcessor._execute(
                    f"DELETE FROM {queue.TABLE_NAME} WHERE {queue.COL_FILE_PATH} IN ({placeholders})",
                    tuple(batch),
                    conn=tx
                )
        return affected_rows

    @staticmethod
    def clear_queue(conn: Optional[sqlite3.Connection] = None) -> bool:
        """
        用途说明：清空当前仓库的待识别队列，可参与调用方事务。
        入参说明：conn (Optional[sqlite3.Connection]) - 可选的外部事务连接。
        返回值说明：bool - 是否清空成功。
        """
        queue = DBConstants.FaceRecognitionQueue
        try:
            with (db_manager.transaction() if conn is None else nullcontext(conn)) as tx:
                BaseDBProcessor._execute(f"DELETE FROM {queue.TABLE_NAME}", conn=tx)
            return True
        except Exception as e:
            LogUtils.error(t('face_queue_clear_failed_log', error=str(e)))
            return False

    @staticmethod
    def get_index_summary(pipeline_version: str) -> FaceIndexSummaryResult:
        """
        用途说明：统计当前仓库的图片总数、待处理数量与已保存人脸数量，避免加载全表。
        入参说明：pipeline_version (str) - 当前模型与处理流水线版本。
        返回值说明：FaceIndexSummaryResult - 图片与增量处理统计结果。
        """
        state = DBConstants.FaceIndexState
        file_index = DBConstants.FileIndex
        face = DBConstants.FaceEmbedding
        queue = DBConstants.FaceRecognitionQueue
        query: str = f"""
            SELECT
                (SELECT COUNT(*) FROM {file_index.TABLE_NAME}
                 WHERE {file_index.COL_FILE_TYPE} = ?
                   AND ({file_index.COL_RECYCLE_BIN_TIME} IS NULL OR {file_index.COL_RECYCLE_BIN_TIME} = '')) AS total,
                (SELECT COUNT(*) FROM {file_index.TABLE_NAME} f
                 LEFT JOIN {state.TABLE_NAME} s ON s.{state.COL_FILE_PATH} = f.{file_index.COL_FILE_PATH}
                 WHERE f.{file_index.COL_FILE_TYPE} = ?
                   AND (f.{file_index.COL_RECYCLE_BIN_TIME} IS NULL OR f.{file_index.COL_RECYCLE_BIN_TIME} = '')
                   AND (s.{state.COL_FILE_PATH} IS NULL
                        OR s.{state.COL_FILE_MD5} != f.{file_index.COL_FILE_MD5}
                        OR s.{state.COL_PIPELINE_VERSION} != ?)) AS pending,
                (SELECT COUNT(*) FROM {queue.TABLE_NAME} q
                 INNER JOIN {file_index.TABLE_NAME} fq
                   ON fq.{file_index.COL_FILE_PATH} = q.{queue.COL_FILE_PATH}
                 WHERE {file_index.active_condition('fq')}) AS queued,
                (SELECT COUNT(*) FROM {face.TABLE_NAME} fe
                 INNER JOIN {file_index.TABLE_NAME} ff
                   ON ff.{file_index.COL_FILE_PATH} = fe.{face.COL_FILE_PATH}
                 WHERE {file_index.active_condition('ff')}) AS faces
        """
        row: Optional[dict] = BaseDBProcessor._execute(
            query,
            (FileType.IMAGE.value, FileType.IMAGE.value, pipeline_version),
            is_query=True,
            fetch_one=True
        )
        if row is None:
            return FaceIndexSummaryResult()
        return FaceIndexSummaryResult(
            total=int(row['total']),
            pending=int(row['pending']),
            queued=int(row['queued']),
            faces=int(row['faces'])
        )

    @staticmethod
    def save_file_result(file_info: FileIndexDBModel, faces: List[FaceEmbeddingDBModel],
                         pipeline_version: str, queue_id: Optional[int] = None,
                         queued_md5: Optional[str] = None) -> bool:
        """
        用途说明：原子替换单张图片的人脸特征与处理状态，无脸图片也写入完成状态。
        入参说明：
            file_info (FileIndexDBModel): 已识别的图片索引记录。
            faces (List[FaceEmbeddingDBModel]): 该图片识别出的全部人脸，一人一条。
            pipeline_version (str): 本次模型与处理流水线版本。
            queue_id (Optional[int]): 本次消费的队列主键；为空时表示直接识别。
            queued_md5 (Optional[str]): 入队时的 MD5，用于安全出队。
        返回值说明：bool - 特征、状态与匹配队列项是否在同一个事务中保存成功。
        """
        try:
            with db_manager.transaction() as conn:
                if not FaceDataProcessor.delete_by_path(file_info.file_path, conn=conn, remove_queue=False):
                    raise RuntimeError(t('face_data_save_failed'))
                if faces:
                    face = DBConstants.FaceEmbedding
                    query: str = f"""
                        INSERT INTO {face.TABLE_NAME} (
                            {face.COL_FILE_PATH}, {face.COL_FILE_MD5}, {face.COL_FACE_INDEX},
                            {face.COL_BBOX_X}, {face.COL_BBOX_Y}, {face.COL_BBOX_WIDTH}, {face.COL_BBOX_HEIGHT},
                            {face.COL_CONFIDENCE}, {face.COL_EMBEDDING}, {face.COL_PIPELINE_VERSION},
                            {face.COL_CREATED_AT}
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    """
                    data: List[tuple] = [
                        (
                            item.file_path, item.file_md5, item.face_index,
                            item.bbox_x, item.bbox_y, item.bbox_width, item.bbox_height,
                            item.confidence, item.embedding, item.pipeline_version
                        )
                        for item in faces
                    ]
                    BaseDBProcessor._execute_batch(query, data, conn=conn)

                state = DBConstants.FaceIndexState
                state_query: str = f"""
                    INSERT INTO {state.TABLE_NAME} (
                        {state.COL_FILE_PATH}, {state.COL_FILE_MD5}, {state.COL_PIPELINE_VERSION},
                        {state.COL_FACE_COUNT}, {state.COL_PROCESSED_AT}
                    ) VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT({state.COL_FILE_PATH}) DO UPDATE SET
                        {state.COL_FILE_MD5} = excluded.{state.COL_FILE_MD5},
                        {state.COL_PIPELINE_VERSION} = excluded.{state.COL_PIPELINE_VERSION},
                        {state.COL_FACE_COUNT} = excluded.{state.COL_FACE_COUNT},
                        {state.COL_PROCESSED_AT} = CURRENT_TIMESTAMP
                """
                BaseDBProcessor._execute(
                    state_query,
                    (file_info.file_path, file_info.file_md5, pipeline_version, len(faces)),
                    conn=conn
                )
                if queue_id is not None and queued_md5 is not None:
                    if not FaceDataProcessor.delete_queue_item(queue_id, queued_md5, conn=conn):
                        raise RuntimeError(t('face_queue_delete_failed'))
            return True
        except Exception as e:
            LogUtils.error(t('face_data_save_failed_log', path=file_info.file_path, error=str(e)))
            return False

    @staticmethod
    def delete_by_path(file_path: str, conn: Optional[sqlite3.Connection] = None,
                       remove_queue: bool = True) -> bool:
        """
        用途说明：删除指定文件路径的人脸特征、处理状态，并按需移除待识别队列项。
        入参说明：
            file_path (str): 文件索引完整路径。
            conn (Optional[sqlite3.Connection]): 可选的外部事务连接。
            remove_queue (bool): 是否同步移除该路径的队列项。
        返回值说明：bool - 是否完成清理。
        """
        try:
            FaceDataProcessor.delete_by_paths([file_path], conn=conn, remove_queue=remove_queue)
            return True
        except Exception as e:
            LogUtils.error(t('face_data_delete_failed_log', path=file_path, error=str(e)))
            return False

    @staticmethod
    def delete_by_paths(file_paths: List[str], conn: Optional[sqlite3.Connection] = None,
                        remove_queue: bool = True) -> int:
        """
        用途说明：批量删除人脸特征、处理状态及待识别队列，供文件生命周期事务统一调用。
        入参说明：
            file_paths (List[str]): 待清理的文件完整路径列表。
            conn (Optional[sqlite3.Connection]): 可选的外部事务连接。
            remove_queue (bool): 是否同步移除待识别队列项。
        返回值说明：int - 三张人脸相关表中实际删除的记录数。
        """
        if not file_paths:
            return 0
        face: type = DBConstants.FaceEmbedding
        state: type = DBConstants.FaceIndexState
        queue: type = DBConstants.FaceRecognitionQueue
        tables: List[Tuple[str, str]] = [
            (face.TABLE_NAME, face.COL_FILE_PATH),
            (state.TABLE_NAME, state.COL_FILE_PATH)
        ]
        if remove_queue:
            tables.append((queue.TABLE_NAME, queue.COL_FILE_PATH))

        affected_rows: int = 0
        batch_size: int = 500
        with (db_manager.transaction() if conn is None else nullcontext(conn)) as tx:
            for start in range(0, len(file_paths), batch_size):
                batch: List[str] = file_paths[start:start + batch_size]
                placeholders: str = ','.join('?' for _ in batch)
                for table_name, path_column in tables:
                    affected_rows += BaseDBProcessor._execute(
                        f"DELETE FROM {table_name} WHERE {path_column} IN ({placeholders})",
                        tuple(batch),
                        conn=tx
                    )
        return affected_rows

    @staticmethod
    def update_file_paths(changes: List[FileMoveInfo], conn: Optional[sqlite3.Connection] = None) -> int:
        """
        用途说明：批量迁移人脸特征、处理状态和队列路径，文件内容未变时无需重新识别人脸。
        入参说明：changes (List[FileMoveInfo]) - 文件路径变更列表；conn (Optional[sqlite3.Connection]) - 外部事务连接。
        返回值说明：int - 实际更新的人脸相关记录数。
        """
        if not changes:
            return 0
        face: type = DBConstants.FaceEmbedding
        state: type = DBConstants.FaceIndexState
        queue: type = DBConstants.FaceRecognitionQueue
        tables: List[Tuple[str, str]] = [
            (face.TABLE_NAME, face.COL_FILE_PATH),
            (state.TABLE_NAME, state.COL_FILE_PATH),
            (queue.TABLE_NAME, queue.COL_FILE_PATH)
        ]
        affected_rows: int = 0
        with (db_manager.transaction() if conn is None else nullcontext(conn)) as tx:
            for change in changes:
                if change.old_path == change.new_path:
                    continue
                # 新路径可能存在旧版本遗留数据，先清理再迁移，避免唯一约束冲突。
                FaceDataProcessor.delete_by_paths([change.new_path], conn=tx)
                for table_name, path_column in tables:
                    affected_rows += BaseDBProcessor._execute(
                        f"UPDATE {table_name} SET {path_column} = ? WHERE {path_column} = ?",
                        (change.new_path, change.old_path),
                        conn=tx
                    )
        return affected_rows

    @staticmethod
    def cleanup_orphan_data(conn: Optional[sqlite3.Connection] = None) -> bool:
        """
        用途说明：清理文件索引中已不存在的人脸特征与处理状态，不触碰历史索引表。
        入参说明：conn (Optional[sqlite3.Connection]) - 可选的外部事务连接。
        返回值说明：bool - 是否完成清理。
        """
        try:
            with (db_manager.transaction() if conn is None else nullcontext(conn)) as tx:
                file_index = DBConstants.FileIndex
                face = DBConstants.FaceEmbedding
                state = DBConstants.FaceIndexState
                queue = DBConstants.FaceRecognitionQueue
                BaseDBProcessor._execute(
                    f"DELETE FROM {face.TABLE_NAME} WHERE NOT EXISTS ("
                    f"SELECT 1 FROM {file_index.TABLE_NAME} f "
                    f"WHERE f.{file_index.COL_FILE_PATH} = {face.TABLE_NAME}.{face.COL_FILE_PATH})",
                    conn=tx
                )
                BaseDBProcessor._execute(
                    f"DELETE FROM {state.TABLE_NAME} WHERE NOT EXISTS ("
                    f"SELECT 1 FROM {file_index.TABLE_NAME} f "
                    f"WHERE f.{file_index.COL_FILE_PATH} = {state.TABLE_NAME}.{state.COL_FILE_PATH})",
                    conn=tx
                )
                BaseDBProcessor._execute(
                    f"DELETE FROM {queue.TABLE_NAME} WHERE NOT EXISTS ("
                    f"SELECT 1 FROM {file_index.TABLE_NAME} f "
                    f"WHERE f.{file_index.COL_FILE_PATH} = {queue.TABLE_NAME}.{queue.COL_FILE_PATH})",
                    conn=tx
                )
            return True
        except Exception as e:
            LogUtils.error(t('face_data_orphan_cleanup_failed_log', error=str(e)))
            return False

    @staticmethod
    def clear_all_data(conn: Optional[sqlite3.Connection] = None) -> bool:
        """
        用途说明：清空当前仓库的人脸特征、图片处理状态和待识别队列，使下次开始可以重新识别。
        入参说明：conn (Optional[sqlite3.Connection]) - 可选的外部事务连接。
        返回值说明：bool - 三张人脸队列表是否清空成功。
        """
        try:
            with (db_manager.transaction() if conn is None else nullcontext(conn)) as tx:
                face = DBConstants.FaceEmbedding
                state = DBConstants.FaceIndexState
                queue = DBConstants.FaceRecognitionQueue
                BaseDBProcessor._execute(f"DELETE FROM {face.TABLE_NAME}", conn=tx)
                BaseDBProcessor._execute(f"DELETE FROM {state.TABLE_NAME}", conn=tx)
                BaseDBProcessor._execute(f"DELETE FROM {queue.TABLE_NAME}", conn=tx)
            return True
        except Exception as e:
            LogUtils.error(t('face_data_clear_failed_log', error=str(e)))
            return False
