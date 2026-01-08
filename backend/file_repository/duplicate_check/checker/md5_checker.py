from typing import List, Dict
from backend.file_repository.duplicate_check.checker.base_checker import BaseDuplicateChecker
from backend.db.file_index_processor import FileIndexDBModel
from backend.model.db.duplicate_group_db_model import DuplicateGroupDBModule


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
            file_info (FileIndex): 文件索引对象。
        """
        md5 = file_info.file_md5
        if not md5:
            return

        if md5 not in self.md5_groups:
            self.md5_groups[md5] = []
        self.md5_groups[md5].append(file_info)

    def get_results(self) -> List[DuplicateGroupDBModule]:
        """
        用途：获取 MD5 重复的分组结果。
        返回值说明：
            List[DuplicateGroupDBModule]: 重复文件组列表。
        """
        results = []
        for md5, files in self.md5_groups.items():
            if len(files) > 1:
                duplicate_files = [
                    f.id for f in files
                ]
                group = DuplicateGroupDBModule(
                    group_name=md5,
                    file_ids=duplicate_files
                )
                results.append(group)
        return results

    def is_supported(self, file_extension: str) -> bool:
        """
        用途：查询该检查器是否支持处理指定后缀名的文件。
        入参说明：
            file_extension (str): 文件后缀名（带点，如 '.mp4'）。
        返回值说明：
            bool: 默认检查器作为兜底，通常在分发逻辑中最后判断，这里返回 True 表示支持所有类型。
        """
        return True
