class DBConstants:
    """
    用途：数据库表名及列名常量类，统一管理所有数据库结构相关的硬编码字符串
    """

    DB_VERSION: int = 10  # 当前数据库版本，升级至 10 以支持 file_name 列

    class SimilarityType:
        """用途：查重相似度类型常量"""
        MD5: str = 'md5'
        HASH: str = 'hash'
        VIDEO_FEATURE: str = 'video_feature'

    class VersionInfo:
        """用途：version_info 表相关的常量"""
        TABLE_NAME: str = 'version_info'
        COL_VERSION: str = 'version'

    class FileIndex:
        """用途：file_index 表相关的常量"""
        TABLE_NAME: str = 'file_index'
        COL_ID: str = 'id'
        COL_FILE_PATH: str = 'file_path'
        COL_FILE_NAME: str = 'file_name'
        COL_FILE_MD5: str = 'file_md5'
        COL_FILE_SIZE: str = 'file_size'
        COL_RECYCLE_BIN_TIME: str = 'recycle_bin_time'
        COL_THUMBNAIL_PATH: str = 'thumbnail_path'
        COL_SCAN_TIME: str = 'scan_time'

    class HistoryFileIndex:
        """用途：history_file_index 表相关的常量"""
        TABLE_NAME: str = 'history_file_index'
        COL_ID: str = 'id'
        COL_FILE_PATH: str = 'file_path'
        COL_FILE_NAME: str = 'file_name'
        COL_FILE_MD5: str = 'file_md5'
        COL_FILE_SIZE: str = 'file_size'
        COL_SCAN_TIME: str = 'scan_time'
        COL_DELETE_TIME: str = 'delete_time'

    class VideoFeature:
        """用途：video_features 表相关的常量"""
        TABLE_NAME: str = 'video_features'
        COL_ID: str = 'id'
        COL_FILE_MD5: str = 'file_md5'
        COL_VIDEO_HASHES: str = 'video_hashes'
        COL_DURATION: str = 'duration'

    class DuplicateGroup:
        """用途：duplicate_groups 表相关的常量"""
        TABLE_GROUPS: str = 'duplicate_groups'
        COL_GRP_ID_PK: str = 'id'
        COL_GRP_GROUP_NAME: str = 'group_name'

    class DuplicateFile:
        """用途 : duplicate_files 表相关的常量"""
        TABLE_FILES: str = 'duplicate_files'
        COL_FILE_ID_PK: str = 'id'
        COL_FILE_GROUP_ID: str = 'group_id'
        COL_FILE_ID: str = 'file_id'
        COL_SIMILARITY_TYPE: str = 'similarity_type' # 相似类型：md5, hash
        COL_SIMILARITY_RATE: str = 'similarity_rate' # 相似率：0.0-1.0

    class AlreadyEnteredFile:
        """用途：already_entered_file 表相关的常量（原 ignore_file）"""
        TABLE_NAME: str = 'already_entered_file'
        COL_ID: str = 'id'
        COL_FILE_NAME: str = 'file_name'
        COL_ADD_TIME: str = 'add_time'

    class PendingEntryFile:
        """用途：pending_entry_file 表相关的常量"""
        TABLE_NAME: str = 'pending_entry_file'
        COL_ID: str = 'id'
        COL_FILE_NAME: str = 'file_name'
        COL_ADD_TIME: str = 'add_time'

    class FileRepoDetail:
        """用途：file_repo_detail 表相关的常量 (文件仓库详情)"""
        TABLE_NAME: str = 'file_repo_detail'
        COL_ID: str = 'id'
        COL_TOTAL_COUNT: str = 'total_count'
        COL_TOTAL_SIZE: str = 'total_size'
        COL_UPDATE_TIME: str = 'update_time'

    class BatchCheckResult:
        """用途：batch_check_results 表相关的常量 (批量检测结果)"""
        TABLE_NAME: str = 'batch_check_results'
        COL_ID: str = 'id'
        COL_NAME: str = 'name'
        COL_SOURCE: str = 'source'
        COL_DETAIL: str = 'detail'
