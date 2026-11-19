import csv
import io
from datetime import datetime, timezone
from typing import Iterator, List

from backend.common.i18n_utils import t
from backend.common.log_utils import LogUtils
from backend.db.processor_manager import processor_manager
from backend.model.db.organize_record_db_model import OrganizeRecordDBModel
from backend.organize.organize_models import OrganizeRecordPageResult, OrganizeRecordResult


class OrganizeRecordService:
    """
    用途：整理记录业务服务类，负责整理记录的分页查询与 CSV 导出内容生成。
    说明：记录按仓库隔离，存储于当前仓库数据库的 organize_records 表；
        数据库整理时间为 UTC（CURRENT_TIMESTAMP），对外展示/导出统一转换为本地时间。
    """

    def get_page(self, page: int, page_size: int) -> OrganizeRecordPageResult:
        """
        用途说明：分页查询当前仓库的整理记录，按整理时间倒序（时间越靠后排序越靠前）。
        入参说明：
            page (int): 页码，从 1 开始（由路由层夹取保证合法）。
            page_size (int): 每页条数（由路由层夹取保证合法）。
        返回值说明：OrganizeRecordPageResult - 分页结果对象，items 内时间已转换为本地时间字符串。
        """
        total: int = processor_manager.organize_record_processor.count_records()
        models: List[OrganizeRecordDBModel] = processor_manager.organize_record_processor.get_records_page(page, page_size)
        items: List[OrganizeRecordResult] = [
            OrganizeRecordResult(
                id=model.id or 0,
                original_path=model.original_path or '',
                original_name=model.original_name or '',
                organized_path=model.organized_path or '',
                organized_name=model.organized_name or '',
                organize_time=self._to_local_time(model.organize_time)
            )
            for model in models
        ]
        return OrganizeRecordPageResult(total=total, page=page, page_size=page_size, items=items)

    def iter_csv_chunks(self, chunk_size: int = 500) -> Iterator[str]:
        """
        用途说明：生成整理记录 CSV 导出的文本块迭代器（流式导出，避免一次性载入全表）。
            首块为 UTF-8 BOM + 表头（序号/整理后文件名/整理前文件名/整理时间，随语言切换），
            后续每块最多包含 chunk_size 条记录，序号按倒序从 1 连续编号。
        入参说明：chunk_size (int): 单批记录条数，默认 500（符合分批处理 100-1000 条的规范）。
        返回值说明：Iterator[str] - CSV 文本块迭代器；中途异常会记录日志并结束迭代（已输出部分保留）。
        """
        # 首块：BOM 保证 Excel 正确识别 UTF-8 中文 + 表头行
        header_buf: io.StringIO = io.StringIO()
        header_writer = csv.writer(header_buf)
        header_writer.writerow([
            t('organize_records_csv_header_seq'),
            t('organize_records_csv_header_organized'),
            t('organize_records_csv_header_original'),
            t('organize_records_csv_header_time')
        ])
        yield '\ufeff' + header_buf.getvalue()

        seq: int = 0
        try:
            for chunk in processor_manager.organize_record_processor.iter_record_chunks(chunk_size):
                buf: io.StringIO = io.StringIO()
                writer = csv.writer(buf)
                for model in chunk:
                    seq += 1
                    writer.writerow([
                        seq,
                        model.organized_name or '',
                        model.original_name or '',
                        self._to_local_time(model.organize_time)
                    ])
                yield buf.getvalue()
        except Exception as e:
            # 流式响应已开始输出，无法再改为 JSON 错误；记录日志并停止迭代，由前端感知下载异常
            LogUtils.error(t('organize_records_export_error', error=str(e)))
            return

    @staticmethod
    def _to_local_time(raw: str) -> str:
        """
        用途说明：将数据库 UTC 时间字符串转换为服务器本地时间字符串（格式保持 YYYY-MM-DD HH:MM:SS）。
        入参说明：raw (str): 数据库 organize_time 原始值（UTC，可能为 None/空/异常格式）。
        返回值说明：str - 本地时间字符串；无法解析时原样返回，空值返回空串。
        """
        if not raw:
            return ''
        try:
            utc_dt: datetime = datetime.strptime(raw, '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc)
            return utc_dt.astimezone().strftime('%Y-%m-%d %H:%M:%S')
        except (TypeError, ValueError):
            return raw


# 创建全局唯一的整理记录服务实例，供路由层统一调用
organizeRecordService: OrganizeRecordService = OrganizeRecordService()