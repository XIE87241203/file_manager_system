class SimilarityType:
    """
    用途：查重相似度类型常量，属于跨模块共享的领域概念。
    放置于通用层，供模型层、持久化层与查重器统一引用，避免模型层反向依赖数据库层。
    """
    MD5: str = 'md5'
    HASH: str = 'hash'
    VIDEO_FEATURE: str = 'video_feature'