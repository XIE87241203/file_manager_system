from backend.db.processor.already_entered_file_processor import AlreadyEnteredFileProcessor
from backend.db.processor.duplicate_group_processor import DuplicateGroupDBModuleProcessor
from backend.db.processor.file_index_processor import FileIndexProcessor
from backend.db.processor.history_file_index_processor import HistoryFileIndexProcessor
from backend.db.processor.pending_entry_file_processor import PendingEntryFileProcessor
from backend.db.processor.video_feature_processor import VideoFeatureProcessor


class ProcessorManager:
    """
    用途：数据库处理器管理器，负责统一管理所有的数据库处理器实例
    """
    _instance = None

    def __new__(cls):
        """
        用途：实现单例模式
        入参说明：无
        返回值说明：ProcessorManager 实例
        """
        if cls._instance is None:
            cls._instance = super(ProcessorManager, cls).__new__(cls)
            cls._instance._init_processors()
        return cls._instance

    def _init_processors(self) -> None:
        """
        用途：初始化所有处理器
        入参说明：无
        返回值说明：无
        """
        self.file_index_processor: FileIndexProcessor = FileIndexProcessor()
        self.history_file_index_processor: HistoryFileIndexProcessor = HistoryFileIndexProcessor()
        self.video_feature_processor: VideoFeatureProcessor = VideoFeatureProcessor()
        self.duplicate_group_processor: DuplicateGroupDBModuleProcessor = DuplicateGroupDBModuleProcessor()
        self.already_entered_file_processor: AlreadyEnteredFileProcessor = AlreadyEnteredFileProcessor()
        self.pending_entry_file_processor: PendingEntryFileProcessor = PendingEntryFileProcessor()


processor_manager = ProcessorManager()
