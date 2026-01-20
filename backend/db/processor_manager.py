from backend.db.processor.already_entered_file_processor import AlreadyEnteredFileProcessor
from backend.db.processor.batch_check_processor import BatchCheckProcessor
from backend.db.processor.duplicate_group_processor import DuplicateGroupProcessor
from backend.db.processor.file_index_processor import FileIndexProcessor
from backend.db.processor.file_repo_detail_processor import FileRepoDetailProcessor
from backend.db.processor.history_file_index_processor import HistoryFileIndexProcessor
from backend.db.processor.pending_entry_file_processor import PendingEntryFileProcessor
from backend.db.processor.video_feature_processor import VideoFeatureProcessor


class ProcessorManager:
    """
    用途：数据库处理器管理类，负责实例化并统一管理所有表的处理器对象（Processor）。
    """
    _instance = None

    def __new__(cls):
        """
        用途说明：实现单例模式，确保全局只有一个处理器管理器实例，防止重复实例化导致内存浪费。
        入参说明：无
        返回值说明：ProcessorManager 实例
        """
        if cls._instance is None:
            cls._instance = super(ProcessorManager, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        """
        用途说明：初始化各个表的处理器实例。
        入参说明：无
        返回值说明：无
        """
        # 确保初始化逻辑仅执行一次
        if hasattr(self, '_initialized') and self._initialized:
            return

        # 初始化各个表的处理器实例
        self.file_index_processor: FileIndexProcessor = FileIndexProcessor()
        self.history_file_index_processor: HistoryFileIndexProcessor = HistoryFileIndexProcessor()
        self.video_feature_processor: VideoFeatureProcessor = VideoFeatureProcessor()
        self.duplicate_group_processor: DuplicateGroupProcessor = DuplicateGroupProcessor()
        self.already_entered_file_processor: AlreadyEnteredFileProcessor = AlreadyEnteredFileProcessor()
        self.pending_entry_file_processor: PendingEntryFileProcessor = PendingEntryFileProcessor()
        self.file_repo_detail_processor: FileRepoDetailProcessor = FileRepoDetailProcessor()
        self.batch_check_processor: BatchCheckProcessor = BatchCheckProcessor()

        self._initialized: bool = True


# 创建全局唯一的处理器管理器实例，供外部统一调用
processor_manager: ProcessorManager = ProcessorManager()
