import os
import time
from typing import Optional

from src.utils.log_utils import logger
from src.video_duplicate_check.utils.video_cache_manager import VideoCacheManager
from src.video_duplicate_check.utils.video_similarity_Tree import VideoSimilarityTree
from src.video_duplicate_check.utils.video_analyzer import VideoAnalyzer


class VideoDuplicateChecker:

    def __init__(self, path: str):
        self.path = path
        self.cache_manager = VideoCacheManager()
        pass

    def start(self):
        start_time = time.time()

        self.cache_manager.open_db()
        # 获取 VideoAnalyzer 单例并初始化数据库链接
        analyzer = VideoAnalyzer()
        analyzer.set_cache_manager(self.cache_manager)

        try:
            tree = VideoSimilarityTree(analyzer)

            video_extensions = ['.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv']

            for root, dirs, files in os.walk(self.path):
                for file in files:
                    logger.info(f"正在处理文件: {file}")
                    if any(file.lower().endswith(ext) for ext in video_extensions):
                        video_path = os.path.join(root, file)
                        tree.add_video(video_path)

            similar_groups = tree.get_similar_video_groups()

            if not similar_groups:
                logger.info("未发现相似视频分组。")
            else:
                logger.info("--- 相似视频分组结果 ---")
                for i, group in enumerate(similar_groups):
                    logger.info(f"分组 {i + 1}:")
                    for video in group:
                        logger.info(f"  - {video.path} (时长: {video.duration:.2f}s)")
            self.cache_manager.clear_video_info_cache()
        finally:
            # 在遍历结束后关闭数据库链接
            self.cache_manager.close_db()

        end_time = time.time()
        logger.info(f"main() 运行总耗时: {end_time - start_time:.2f} 秒")



