import unicodedata

from pypinyin import Style, lazy_pinyin


class FilenameSortUtils:
    """
    用途说明：统一文件名首字母计算，供数据库排序、接口返回与前端字母尺分组共用。
    """

    @staticmethod
    def get_initial(file_name: str) -> str:
        """
        用途说明：提取文件名首个有效字符的排序首字母；中文取拼音首字母，英文字母取大写，其余归入 #。
        入参说明：file_name (str): 文件名，允许为空。
        返回值说明：str: 单个大写英文字母或 #。
        """
        text: str = (file_name or "").strip()
        if not text:
            return '#'
        first_char: str = text[0]
        pinyin_letters: list[str] = lazy_pinyin(first_char, style=Style.FIRST_LETTER)
        candidate: str = pinyin_letters[0].upper() if pinyin_letters else ''
        if len(candidate) == 1 and 'A' <= candidate <= 'Z':
            return candidate
        normalized: str = unicodedata.normalize('NFKC', first_char).upper()
        if len(normalized) == 1 and 'A' <= normalized <= 'Z':
            return normalized
        return '#'
