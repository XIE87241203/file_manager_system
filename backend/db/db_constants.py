class DBConstants:
    """
    用途：数据库表名及列名常量类，统一管理所有数据库结构相关的硬编码字符串
    """

    DB_VERSION: int = 26  # 当前数据库版本，升级至 26 以支持图片与视频分辨率

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
        COL_FILE_TYPE: str = 'file_type'           # 新增：文件类型 (如 video, image, document, etc.)
        COL_VIDEO_DURATION: str = 'video_duration' # 新增：视频时长 (秒)
        COL_VIDEO_CODEC: str = 'video_codec'       # 新增：视频编码 (如 h264, h265, etc.)
        COL_RECYCLE_BIN_TIME: str = 'recycle_bin_time'
        COL_THUMBNAIL_PATH: str = 'thumbnail_path'
        COL_SCAN_TIME: str = 'scan_time'
        COL_FILE_MTIME: str = 'file_mtime'         # 新增：文件最后修改时间（用于相册时间轴分组）
        COL_FILE_EXIF_TIME: str = 'file_exif_time' # 新增：EXIF 拍摄时间/视频创建时间（相册优先使用）
        COL_FILE_LOCATION: str = 'file_location'   # 新增：拍摄地点（EXIF GPS / 视频 ISO 6709 坐标文本）
        COL_MEDIA_WIDTH: str = 'media_width'       # 新增：图片或视频显示宽度（像素）
        COL_MEDIA_HEIGHT: str = 'media_height'     # 新增：图片或视频显示高度（像素）
        # 已检查但确实不存在的媒体信息标记，避免每次手动补全都重复读取同一文件
        NO_INFO_VALUE: str = '__NO_INFO__'
        # 相册实际排序时间表达式：优先 EXIF/拍摄时间，缺失时回退文件修改时间；无信息标记按空值处理
        ALBUM_TIME_EXPRESSION: str = (
            f"COALESCE(NULLIF({COL_FILE_EXIF_TIME}, '{NO_INFO_VALUE}'), "
            f"NULLIF({COL_FILE_MTIME}, '{NO_INFO_VALUE}'))"
        )
        # 相册逻辑排序字段名（非真实列，仅用于接口参数与排序表达式映射）
        ALBUM_TIME_FIELD: str = 'album_time'

    class HistoryFileIndex:
        """用途：history_file_index 表相关的常量"""
        TABLE_NAME: str = 'history_file_index'
        COL_ID: str = 'id'
        COL_FILE_PATH: str = 'file_path'
        COL_FILE_NAME: str = 'file_name'
        COL_FILE_MD5: str = 'file_md5'
        COL_FILE_SIZE: str = 'file_size'
        COL_FILE_TYPE: str = 'file_type'           # 新增：文件类型
        COL_VIDEO_DURATION: str = 'video_duration' # 新增：视频时长
        COL_VIDEO_CODEC: str = 'video_codec'       # 新增：视频编码
        COL_SCAN_TIME: str = 'scan_time'
        COL_DELETE_TIME: str = 'delete_time'

    class VideoFeature:
        """用途：video_features 表相关的常量"""
        TABLE_NAME: str = 'video_features'
        COL_ID: str = 'id'
        COL_FILE_MD5: str = 'file_md5'
        COL_VIDEO_HASHES: str = 'video_hashes'
        COL_DURATION: str = 'duration'

    class ImageFeature:
        """用途：image_features 表相关的常量（图片感知哈希缓存）"""
        TABLE_NAME: str = 'image_features'
        COL_ID: str = 'id'
        COL_FILE_MD5: str = 'file_md5'
        COL_IMAGE_HASH: str = 'image_hash'

    class DuplicateCheckMeta:
        """用途：duplicate_check_meta 表相关的常量（记录最近一次查重完成时间与耗时）"""
        TABLE_NAME: str = 'duplicate_check_meta'
        COL_ID: str = 'id'
        COL_LAST_CHECK_TIME: str = 'last_check_time'
        COL_LAST_CHECK_DURATION: str = 'last_check_duration'

    class DuplicateGroup:
        """用途：duplicate_groups 表相关的常量"""
        TABLE_GROUPS: str = 'duplicate_groups'
        COL_GRP_ID_PK: str = 'id'
        COL_GRP_GROUP_NAME: str = 'group_name'
        COL_GRP_CREATE_TIME: str = 'create_time'

    class DuplicateFile:
        """用途 : duplicate_files 表相关的常量"""
        TABLE_FILES: str = 'duplicate_files'
        COL_FILE_ID_PK: str = 'id'
        COL_FILE_GROUP_ID: str = 'group_id'
        COL_FILE_PATH: str = 'file_path'            # 修改：使用 file_path 关联
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

    class OrganizeSetting:
        """用途：organize_settings 表相关的常量（整理模块专用设置，单行记录，列表字段以 JSON 文本存储）"""
        TABLE_NAME: str = 'organize_settings'
        COL_ID: str = 'id'
        COL_PENDING_DIRS: str = 'pending_dirs'      # 待整理目录列表 (JSON 数组文本)
        COL_ORGANIZED_DIR: str = 'organized_dir'    # 已整理目录 (整理完成后文件转移至此)
        COL_EXTENSIONS: str = 'extensions'          # 需要整理的后缀名列表 (JSON 数组文本)
        COL_RENAME_SCRIPT_PATH: str = 'rename_script_path'  # 文件名整理脚本路径 (空串表示默认脚本)
        COL_SIZE_OP: str = 'size_op'                # 文件大小筛选比较符 (gt 大于 / lt 小于，空串表示不启用)
        COL_SIZE_VALUE: str = 'size_value'          # 文件大小筛选数值 (不大于 0 表示不启用)
        COL_SIZE_UNIT: str = 'size_unit'            # 文件大小筛选单位 (KB / MB / GB)
        COL_UPDATE_TIME: str = 'update_time'

    class OrganizeRecord:
        """用途：organize_records 表相关的常量（整理历史，每整理一个文件记录一条）"""
        TABLE_NAME: str = 'organize_records'
        COL_ID: str = 'id'
        COL_ORIGINAL_PATH: str = 'original_path'      # 原文件完整路径
        COL_ORIGINAL_NAME: str = 'original_name'      # 原文件名 (含后缀)
        COL_ORGANIZED_PATH: str = 'organized_path'    # 整理后文件完整路径
        COL_ORGANIZED_NAME: str = 'organized_name'    # 整理后文件名 (含后缀)
        COL_ORGANIZE_TIME: str = 'organize_time'

    class FaceIndexState:
        """用途：face_file_index_state 表相关的常量（记录图片已处理状态，含无脸图片）"""
        TABLE_NAME: str = 'face_file_index_state'
        COL_ID: str = 'id'
        COL_FILE_PATH: str = 'file_path'
        COL_FILE_MD5: str = 'file_md5'
        COL_PIPELINE_VERSION: str = 'pipeline_version'
        COL_FACE_COUNT: str = 'face_count'
        COL_PROCESSED_AT: str = 'processed_at'

    class FaceRecognitionQueue:
        """用途：face_recognition_queue 表相关的常量（按文件路径去重的待识别图片队列）"""
        TABLE_NAME: str = 'face_recognition_queue'
        COL_ID: str = 'id'
        COL_FILE_PATH: str = 'file_path'
        COL_FILE_MD5: str = 'file_md5'
        COL_QUEUED_AT: str = 'queued_at'

    class FaceEmbedding:
        """用途：face_embeddings 表相关的常量（一张图片中的每个人脸独立一行）"""
        TABLE_NAME: str = 'face_embeddings'
        COL_ID: str = 'id'
        COL_FILE_PATH: str = 'file_path'
        COL_FILE_MD5: str = 'file_md5'
        COL_FACE_INDEX: str = 'face_index'
        COL_BBOX_X: str = 'bbox_x'
        COL_BBOX_Y: str = 'bbox_y'
        COL_BBOX_WIDTH: str = 'bbox_width'
        COL_BBOX_HEIGHT: str = 'bbox_height'
        COL_CONFIDENCE: str = 'confidence'
        COL_EMBEDDING: str = 'embedding'
        COL_PIPELINE_VERSION: str = 'pipeline_version'
        COL_CREATED_AT: str = 'created_at'

    class Repository:
        """用途：repositories 主表相关的常量（多仓库元数据，存于独立主数据库）"""
        TABLE_NAME: str = 'repositories'
        COL_ID: str = 'id'
        COL_NAME: str = 'name'
        COL_CONFIG: str = 'config'
        COL_DB_FILE: str = 'db_file'
        COL_CREATE_TIME: str = 'create_time'

    class User:
        """用途：users 主表相关的常量（全局用户账户，存于独立主数据库，登录不分仓库）"""
        TABLE_NAME: str = 'users'
        COL_ID: str = 'id'
        COL_USERNAME: str = 'username'              # 登录名（唯一）
        COL_PASSWORD_HASH: str = 'password_hash'    # PBKDF2 加盐慢哈希
        COL_IS_ADMIN: str = 'is_admin'              # 是否管理员（1 是 / 0 否）
        COL_CREATE_TIME: str = 'create_time'
        COL_UPDATE_TIME: str = 'update_time'

    class UserChangelogRead:
        """用途：user_changelog_reads 表相关的常量（记录全局用户最后看过的更新日志版本）"""
        TABLE_NAME: str = 'user_changelog_reads'
        COL_USER_ID: str = 'user_id'
        COL_VERSION: str = 'version'
        COL_READ_TIME: str = 'read_time'

    class UserRepositoryPermission:
        """用途：user_repository_permissions 表相关的常量（系统使用者与仓库的授权关系，存于主数据库）"""
        TABLE_NAME: str = 'user_repository_permissions'
        COL_USER_ID: str = 'user_id'
        COL_REPO_ID: str = 'repo_id'
        COL_PERMISSION: str = 'permission'
        PERMISSION_ADMIN: str = 'admin'
        PERMISSION_MEMBER: str = 'member'

    class LoginHistory:
        """用途：login_history 表相关的常量（全局用户登录历史，存于独立主数据库，按用户追溯登录记录）"""
        TABLE_NAME: str = 'login_history'
        COL_ID: str = 'id'
        COL_USER_ID: str = 'user_id'                # 关联 users.id（无物理外键，删除用户时同步清理）
        COL_USERNAME: str = 'username'              # 登录名快照（便于追溯）
        COL_LOGIN_TIME: str = 'login_time'          # 登录成功时间
        COL_IP: str = 'ip'                          # 登录来源 IP
