from typing import List, Dict

from backend.db.db_constants import DBConstants
from backend.file_repository.duplicate_check.checker.base_checker import BaseDuplicateChecker
from backend.model.db.duplicate_group_db_model import DuplicateGroupDBModel, DuplicateFileDBModel
from backend.model.db.file_index_db_model import FileIndexDBModel


class MD5Checker(BaseDuplicateChecker):
    """
    用途：默认的 MD5 查重检查器。
    """

    def __init__(self):
        # 用于存储 MD5 分组的字典: {md5: [FileIndex, ...]}
        self.md5_groups: Dict[str, List[FileIndexDBModel]] = {}

    def add_file(self, file_info: FileIndexDBModel) -> None:
        """
        用途：根据 MD5 进行分组录入。
        入参说明：
            file_info (FileIndexDBModel): 文件索引对象。
        """
        md5: str = file_info.file_md5
        if not md5:
            return

        if md5 not in self.md5_groups:
            self.md5_groups[md5] = []
        self.md5_groups[md5].append(file_info)

    def get_results(self) -> List[DuplicateGroupDBModel]:
        """
        用途：获取 MD5 重复的分组结果。
        返回值说明：
            List[DuplicateGroupDBModel]: 重复文件组列表。
        """
        results: List[DuplicateGroupDBModel] = []
        for md5, files in self.md5_groups.items():
            if len(files) > 1:
                # 构造 DuplicateFileDBModel 列表
                duplicate_files: List[DuplicateFileDBModel] = [
                    DuplicateFileDBModel(
                        file_id=f.id,
                        similarity_type=DBConstants.SimilarityType.MD5,
                        similarity_rate=1.0
                    ) for f in files
                ]
                group: DuplicateGroupDBModel = DuplicateGroupDBModel(
                    group_name=md5,
                    files=duplicate_files
                )
                results.append(group)
        return results

    def is_supported(self, file_path: str) -> bool:
        """
        用途：查询该检查器是否支持处理指定路径的文件。
        入参说明：
            file_path (str): 文件完整路径。
        返回值说明：
            bool: 默认检查器作为兜底，通常在分发逻辑中最后判断，这里返回 True 表示支持所有类型。
        """
        return True
