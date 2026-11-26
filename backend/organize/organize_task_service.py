import os
import shutil
import threading
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Set

from backend.common.i18n_utils import t
from backend.common.log_utils import LogUtils
from backend.common.repo_context import get_current_repo_id
from backend.common.utils import Utils
from backend.db.db_operations import DBOperations
from backend.db.processor_manager import processor_manager
from backend.file_repository.file_info_service import FileInfoService
from backend.file_repository.file_service import FileService
from backend.model.db.file_index_db_model import FileIndexDBModel
from backend.model.db.organize_record_db_model import OrganizeRecordDBModel
from backend.organize.organize_models import (
    OrganizePendingFileInfo,
    OrganizePendingResult,
    OrganizeSaveResult,
    OrganizeTaskRemoveResult,
    OrganizeTaskStartResult,
)
from backend.organize.organize_service import organizeService
from backend.organize.rename_script import rename_file_names

# 文件名非法字符（Windows 保留字符 + 路径分隔符单独校验）
_INVALID_NAME_CHARS: str = '<>:"|?*'


@dataclass
class OrganizeTaskSession:
    """
    用途：单个仓库的整理任务内存会话，保存剩余待整理文件队列。
    字段说明：
        repo_id (int): 会话所属仓库 ID。
        queue (List[str]): 剩余待整理文件完整路径列表（按路径排序，顺序即整理顺序）。
        queue_set (Set[str]): 队列路径集合，用于 O(1) 校验预览/保存权限。
        total (int): 本次任务扫描到的文件总数。
        organized_dir (str): 已整理目录绝对路径。
        script_path (str): 生效的整理脚本路径（默认脚本已解析为实际路径）。
        status (str): processing 可操作 / paused 已暂停；停止时直接移除会话。
    """
    repo_id: int = 0
    queue: List[str] = field(default_factory=list)
    queue_set: Set[str] = field(default_factory=set)
    total: int = 0
    organized_dir: str = ''
    script_path: str = ''
    status: str = 'processing'


class OrganizeTaskService:
    """
    用途：整理任务业务服务类，负责待整理文件扫描、分页列表、预览校验与改名移动入库。
    说明：任务会话按仓库隔离存于内存；服务重启后由前端重新发起 start 扫描。
    """

    def __init__(self) -> None:
        """
        用途说明：初始化会话容器与全局锁（waitress 多线程下保护队列读写）。
        入参说明：无。
        返回值说明：无。
        """
        self._sessions: Dict[int, OrganizeTaskSession] = {}
        self._lock: threading.Lock = threading.Lock()

    def start(self) -> OrganizeTaskStartResult:
        """
        用途说明：扫描当前仓库整理设置中的待整理目录（含子目录），按后缀名或文件大小筛选并排除已整理目录，建立任务会话。
            筛选规则：后缀名匹配的文件始终纳入；后缀名不匹配但大小满足设置条件（大于/小于阈值）的文件也纳入。
        入参说明：无（仓库与设置由当前请求上下文决定）。
        返回值说明：OrganizeTaskStartResult - 总数/剩余数/已整理目录。
        异常说明：ValueError - 未配置待整理目录或已整理目录时抛出。
        """
        settings = organizeService.get_settings()
        if not settings.pending_dirs:
            raise ValueError(t('organize_task_no_dirs'))
        if not settings.organized_dir:
            raise ValueError(t('organize_task_no_target'))
        organized_abs: str = os.path.normcase(os.path.abspath(settings.organized_dir))
        exts: Set[str] = set(settings.extensions)
        # 文件大小筛选阈值（字节），0 表示未启用；启用时作为后缀不匹配文件的补充纳入通道
        size_threshold: int = organizeService.size_threshold_bytes(
            settings.size_op, settings.size_value, settings.size_unit)

        paths: List[str] = []
        for pending_dir in settings.pending_dirs:
            if not os.path.isdir(pending_dir):
                LogUtils.error(t('organize_task_dir_missing', path=pending_dir))
                continue
            for root, dirs, files in os.walk(pending_dir):
                root_abs: str = os.path.normcase(os.path.abspath(root))
                # 已整理目录位于待整理目录内部时，整棵子树跳过，避免把整理结果再次扫入
                if self._is_under(root_abs, organized_abs):
                    dirs[:] = []
                    continue
                dirs[:] = [d for d in dirs
                           if not self._is_under(os.path.normcase(os.path.abspath(os.path.join(root, d))), organized_abs)]
                for file_name in files:
                    full_path: str = os.path.join(root, file_name)
                    ext_matched: bool = os.path.splitext(file_name)[1].lower() in exts
                    size_matched: bool = False
                    if not ext_matched and size_threshold > 0:
                        file_size: int = self._safe_size(full_path)
                        size_matched = (file_size > size_threshold if settings.size_op == 'gt'
                                        else file_size < size_threshold)
                    if ext_matched or size_matched:
                        paths.append(full_path)
        paths.sort(key=lambda p: os.path.normcase(p))

        # 排除已移入回收站的文件：整理页删除后重新扫描不再出现（用户从回收站恢复后会再次纳入）
        try:
            recycle_paths: Set[str] = DBOperations.get_recycle_bin_paths_under(settings.pending_dirs)
        except Exception as e:
            LogUtils.error(t('organize_task_recycle_query_error', error=str(e)))
            recycle_paths = set()
        if recycle_paths:
            paths = [p for p in paths if p not in recycle_paths]

        repo_id: int = get_current_repo_id()
        with self._lock:
            self._sessions[repo_id] = OrganizeTaskSession(
                repo_id=repo_id,
                queue=paths,
                queue_set=set(paths),
                total=len(paths),
                status='processing',
                organized_dir=os.path.abspath(settings.organized_dir),
                script_path=settings.rename_script_path
            )
        LogUtils.info(t('organize_task_started', total=len(paths)))
        return OrganizeTaskStartResult(total=len(paths), remaining=len(paths),
                                       organized_dir=settings.organized_dir)

    def pending(self, page: int, page_size: int) -> OrganizePendingResult:
        """
        用途说明：分页返回剩余待整理文件列表，条目附带类型/大小/整理脚本建议文件名。
        入参说明：
            page (int): 页码（从 1 开始，路由层已夹取）。
            page_size (int): 每页条数（路由层已夹取）。
        返回值说明：OrganizePendingResult - 分页结果与文件信息列表。
        异常说明：ValueError - 任务未启动时抛出。
        """
        session: OrganizeTaskSession = self._get_session()
        with self._lock:
            snapshot: List[str] = list(session.queue)
            total: int = session.total
            script_path: str = session.script_path
        chunk: List[str] = snapshot[(page - 1) * page_size: (page - 1) * page_size + page_size]
        names: List[str] = [os.path.basename(p) for p in chunk]
        # 批量调用整理脚本生成建议文件名；脚本失败时回退为原文件名，不阻断整理流程
        try:
            suggestions: List[str] = rename_file_names(script_path, names) if names else []
        except Exception as e:
            LogUtils.error(t('organize_task_suggestion_fallback', error=str(e)))
            suggestions = list(names)
        items: List[OrganizePendingFileInfo] = []
        for path, name, suggestion in zip(chunk, names, suggestions):
            items.append(OrganizePendingFileInfo(
                path=path,
                name=name,
                file_type=self._detect_type(path),
                size=self._safe_size(path),
                suggestion=suggestion
            ))
        return OrganizePendingResult(total=total, remaining=len(snapshot),
                                     page=page, page_size=page_size, items=items)

    def validate_preview(self, path: str) -> str:
        """
        用途说明：校验预览请求的文件必须属于当前任务待整理队列，防止任意路径读取。
        入参说明：path (str) - 请求预览的文件完整路径（Query 参数）。
        返回值说明：str - 校验通过的文件路径。
        异常说明：ValueError - 任务未启动/文件不在队列/文件已不存在时抛出。
        """
        session: OrganizeTaskSession = self._get_session()
        with self._lock:
            in_queue: bool = path in session.queue_set
        if not in_queue:
            raise ValueError(t('organize_task_preview_denied'))
        if not os.path.isfile(path):
            raise ValueError(t('organize_task_file_missing'))
        return path

    def save(self, path: str, new_name: str, user: str) -> OrganizeSaveResult:
        """
        用途说明：将待整理文件按新文件名移动到已整理目录，写入整理历史并从队列移除。
            新文件名不含后缀：保存时自动拼接原文件后缀，防止用户误改后缀；
            若输入末尾已带原后缀（忽略大小写）则先去重，避免出现双后缀。
        入参说明：
            path (str) - 待整理文件完整路径（须在当前队列中）。
            new_name (str) - 整理后文件名（不含后缀，来自用户输入）。
            user (str) - 操作用户名，用于日志。
        返回值说明：OrganizeSaveResult - 剩余数量/总数/整理后路径与文件名（文件名含原后缀）。
        异常说明：ValueError - 文件名非法/不在队列/目标重名/移动失败时抛出。
        """
        session: OrganizeTaskSession = self._get_session()
        self._ensure_processing(session)
        name: str = (new_name or '').strip()
        # 原文件后缀：保存时强制保留，用户输入仅作为文件名主体
        original_ext: str = os.path.splitext(path)[1]
        if original_ext and name.lower().endswith(original_ext.lower()):
            name = name[:-len(original_ext)].rstrip()
        if (not name or '/' in name or '\\' in name or name in ('.', '..')
                or any(ch in name for ch in _INVALID_NAME_CHARS)
                or any(ord(ch) < 32 for ch in name)
                or name.endswith('.') or name.endswith(' ')):
            raise ValueError(t('organize_task_name_invalid'))
        final_name: str = name + original_ext

        with self._lock:
            if session.status != 'processing':
                raise ValueError(t('organize_task_paused'))
            if path not in session.queue_set:
                raise ValueError(t('organize_task_not_in_queue'))
            dest: str = os.path.join(session.organized_dir, final_name)
            if os.path.exists(dest):
                raise ValueError(t('organize_task_target_exists', name=final_name))
            os.makedirs(session.organized_dir, exist_ok=True)
            try:
                shutil.move(path, dest)
            except Exception as e:
                LogUtils.error(t('organize_task_move_error', error=str(e)))
                raise ValueError(t('organize_task_move_error', error=str(e)))
            # 写入整理历史；失败仅记日志不阻断（文件已移动成功）
            try:
                processor_manager.organize_record_processor.insert_record(OrganizeRecordDBModel(
                    original_path=path,
                    original_name=os.path.basename(path),
                    organized_path=dest,
                    organized_name=final_name
                ))
            except Exception as e:
                LogUtils.error(t('organize_task_record_error', error=str(e)))
            # 同步文件索引：已入索引的文件移动后更新路径（未入索引的由方法内部过滤跳过，不阻断整理）
            FileService.update_file_index_path(path, dest)
            session.queue.remove(path)
            session.queue_set.discard(path)
            remaining: int = len(session.queue)
            total: int = session.total
        LogUtils.info(t('organize_task_saved_log', user=user, src=path, dst=dest))
        return OrganizeSaveResult(remaining=remaining, total=total,
                                  organized_path=dest, organized_name=final_name)

    def skip(self, path: str, user: str) -> OrganizeTaskRemoveResult:
        """
        用途说明：跳过当前待整理文件：仅从本次任务队列移除，不移动文件、不写数据库。
            下次启动整理任务重新扫描时，该文件仍会再次出现。
        入参说明：
            path (str) - 待跳过的文件完整路径（须在当前队列中）。
            user (str) - 操作用户名，用于日志。
        返回值说明：OrganizeTaskRemoveResult - 跳过后的剩余数量与总数。
        异常说明：ValueError - 文件不在当前任务队列中时抛出。
        """
        session: OrganizeTaskSession = self._get_session()
        self._ensure_processing(session)
        with self._lock:
            if session.status != 'processing':
                raise ValueError(t('organize_task_paused'))
            if path not in session.queue_set:
                raise ValueError(t('organize_task_not_in_queue'))
            session.queue.remove(path)
            session.queue_set.discard(path)
            remaining: int = len(session.queue)
            total: int = session.total
        LogUtils.info(t('organize_task_skip_log', user=user, path=path))
        return OrganizeTaskRemoveResult(remaining=remaining, total=total)

    def move_to_recycle_bin(self, path: str, user: str) -> OrganizeTaskRemoveResult:
        """
        用途说明：将当前待整理文件移入回收站（与文件仓库删除行为一致：只打标记、不删物理文件），
            并从本次任务队列移除；文件可在回收站页面查看与恢复。
            文件不在文件索引中时（未扫描过），补建索引记录并直接带上回收站时间，保证回收站可见。
        入参说明：
            path (str) - 待移入回收站的文件完整路径（须在当前队列中）。
            user (str) - 操作用户名，用于日志。
        返回值说明：OrganizeTaskRemoveResult - 移除后的剩余数量与总数。
        异常说明：ValueError - 文件不在队列中/文件不存在且无法补建索引/写入回收站失败时抛出。
        """
        session: OrganizeTaskSession = self._get_session()
        self._ensure_processing(session)
        # 数据库操作与队列移除共用会话锁，确保暂停返回后不会再发生回收站写入。
        with self._lock:
            if session.status != 'processing' or path not in session.queue_set:
                raise ValueError(t('organize_task_paused') if session.status != 'processing'
                                 else t('organize_task_not_in_queue'))

            # 1. 已在文件索引中：直接打回收站标记（同步清理查重分组关联）
            existing: Optional[FileIndexDBModel] = DBOperations.get_file_by_path(path)
            if existing is not None:
                ok: bool = DBOperations.batch_move_to_recycle_bin([path])
            else:
                # 2. 未索引的文件：补建索引记录（复用扫描同一套信息提取），插入时直接带回收站时间
                info: Optional[FileIndexDBModel] = FileInfoService.get_file_info(path)
                if info is None:
                    raise ValueError(t('organize_task_file_missing'))
                info.recycle_bin_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                ok = DBOperations.batch_insert_files_index([info])
            if not ok:
                raise ValueError(t('organize_task_recycle_failed'))

            session.queue.remove(path)
            session.queue_set.discard(path)
            remaining: int = len(session.queue)
            total: int = session.total
        LogUtils.info(t('organize_task_recycle_log', user=user, path=path))
        return OrganizeTaskRemoveResult(remaining=remaining, total=total)

    def pause_task(self, repo_id: Optional[int] = None) -> bool:
        """
        用途说明：暂停指定仓库的手动整理会话；暂停时仍可查看列表，但保存、跳过和移入回收站会被拒绝。
        入参说明：repo_id (Optional[int]) - 目标仓库；为空时使用当前请求仓库。
        返回值说明：bool - 存在可暂停的整理会话时返回 True。
        """
        target_repo_id: int = get_current_repo_id() if repo_id is None else repo_id
        with self._lock:
            session: Optional[OrganizeTaskSession] = self._sessions.get(target_repo_id)
            if session is None or session.status != 'processing' or not session.queue:
                return False
            session.status = 'paused'
        LogUtils.info(t('organize_task_paused_log', repo_id=target_repo_id))
        return True

    def resume_task(self, repo_id: Optional[int] = None) -> bool:
        """
        用途说明：恢复指定仓库的手动整理会话。
        入参说明：repo_id (Optional[int]) - 目标仓库；为空时使用当前请求仓库。
        返回值说明：bool - 已恢复时返回 True。
        """
        target_repo_id: int = get_current_repo_id() if repo_id is None else repo_id
        with self._lock:
            session: Optional[OrganizeTaskSession] = self._sessions.get(target_repo_id)
            if session is None or session.status != 'paused':
                return False
            session.status = 'processing'
        LogUtils.info(t('organize_task_resumed_log', repo_id=target_repo_id))
        return True

    def stop_task(self, repo_id: Optional[int] = None) -> bool:
        """
        用途说明：结束指定仓库的整理会话并丢弃内存队列，不移动或删除任何物理文件。
        入参说明：repo_id (Optional[int]) - 目标仓库；为空时使用当前请求仓库。
        返回值说明：bool - 已结束整理会话时返回 True。
        """
        target_repo_id: int = get_current_repo_id() if repo_id is None else repo_id
        with self._lock:
            if target_repo_id not in self._sessions:
                return False
            del self._sessions[target_repo_id]
        LogUtils.info(t('organize_task_stopped_log', repo_id=target_repo_id))
        return True

    def _ensure_processing(self, session: OrganizeTaskSession) -> None:
        """
        用途说明：确保整理会话未暂停，防止暂停期间继续移动或移除文件。
        入参说明：session (OrganizeTaskSession) - 当前仓库整理会话。
        返回值说明：无。
        异常说明：ValueError - 会话已暂停时抛出。
        """
        with self._lock:
            if session.status != 'processing':
                raise ValueError(t('organize_task_paused'))

    def list_active_sessions(self) -> List[OrganizeTaskSession]:
        """
        用途说明：返回所有仍有剩余文件的整理会话快照，供统一任务入口聚合。
        入参说明：无。
        返回值说明：List[OrganizeTaskSession] - 会话副本列表。
        """
        with self._lock:
            return [OrganizeTaskSession(repo_id=session.repo_id, queue=list(session.queue),
                                        queue_set=set(session.queue_set),
                                        total=session.total, organized_dir=session.organized_dir,
                                        script_path=session.script_path, status=session.status)
                    for session in self._sessions.values() if session.queue]

    def _get_session(self) -> OrganizeTaskSession:
        """
        用途说明：获取当前仓库的任务会话。
        入参说明：无（仓库由当前请求上下文决定）。
        返回值说明：OrganizeTaskSession - 当前仓库会话。
        异常说明：ValueError - 未启动任务时抛出。
        """
        session = self._sessions.get(get_current_repo_id())
        if session is None:
            raise ValueError(t('organize_task_not_started'))
        return session

    @staticmethod
    def _is_under(path_abs: str, base_abs: str) -> bool:
        """
        用途说明：判断路径是否等于基准目录或位于其内部（均已 normcase+abspath 归一）。
        入参说明：
            path_abs (str) - 待判断的归一化绝对路径。
            base_abs (str) - 基准目录归一化绝对路径。
        返回值说明：bool - 等于或位于内部返回 True。
        """
        return path_abs == base_abs or path_abs.startswith(base_abs + os.sep)

    @staticmethod
    def _detect_type(path: str) -> str:
        """
        用途说明：按后缀判断文件预览类型。
        入参说明：path (str) - 文件完整路径。
        返回值说明：str - image / video / other。
        """
        if Utils.is_image_file(path):
            return 'image'
        if Utils.is_video_file(path):
            return 'video'
        return 'other'

    @staticmethod
    def _safe_size(path: str) -> int:
        """
        用途说明：读取文件字节数，失败时返回 0（不阻断列表展示）。
        入参说明：path (str) - 文件完整路径。
        返回值说明：int - 文件字节数。
        """
        try:
            return os.path.getsize(path)
        except Exception:
            return 0


# 创建全局唯一的整理任务服务实例，供路由层统一调用
organizeTaskService: OrganizeTaskService = OrganizeTaskService()