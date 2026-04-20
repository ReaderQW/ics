import json
import os
import uuid
from datetime import datetime
from typing import List, Optional

from .models import ReportRecord, ReportType, CustomEncoder


class ReportRepository:
    """报告仓库：负责报告记录的持久化、查询、重命名、删除。"""

    def __init__(self, storage_dir: str = "data/reports"):
        self.storage_dir = storage_dir
        os.makedirs(self.storage_dir, exist_ok=True)

    def create_base_report(
        self,
        scenario_type: str,
        shop_name: Optional[str],
        session_id: str,
        content_markdown: str,
    ) -> ReportRecord:
        report_id = str(uuid.uuid4())[:8]
        record = ReportRecord(
            report_id=report_id,
            report_type=ReportType.BASE,
            display_name=f"b#{report_id}",
            scenario_type=scenario_type,
            shop_name=shop_name,
            session_id=session_id,
            content_markdown=content_markdown,
        )
        self.save(record)
        return record

    def create_summary_report(
        self,
        scenario_type: str,
        shop_name: Optional[str],
        source_report_ids: List[str],
        content_markdown: str,
    ) -> ReportRecord:
        report_id = str(uuid.uuid4())[:8]
        record = ReportRecord(
            report_id=report_id,
            report_type=ReportType.SUMMARY,
            display_name=f"s#{report_id}",
            scenario_type=scenario_type,
            shop_name=shop_name,
            source_report_ids=source_report_ids,
            content_markdown=content_markdown,
        )
        self.save(record)
        return record

    def save(self, record: ReportRecord) -> str:
        record.updated_at = datetime.now()
        file_path = os.path.join(self.storage_dir, f"{record.report_id}.json")
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(record.model_dump(), f, ensure_ascii=False, indent=2, cls=CustomEncoder)
        return file_path

    def get(self, report_id: str) -> Optional[ReportRecord]:
        file_path = os.path.join(self.storage_dir, f"{report_id}.json")
        if not os.path.exists(file_path):
            return None
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return ReportRecord(**data)

    def list_reports(self) -> List[ReportRecord]:
        records: List[ReportRecord] = []
        for name in os.listdir(self.storage_dir):
            if not name.endswith(".json"):
                continue
            try:
                with open(os.path.join(self.storage_dir, name), "r", encoding="utf-8") as f:
                    data = json.load(f)
                records.append(ReportRecord(**data))
            except Exception:
                continue
        return sorted(records, key=lambda r: r.created_at, reverse=True)

    def rename(self, report_id: str, new_name: str, max_len: int = 40) -> bool:
        record = self.get(report_id)
        if not record:
            return False
        safe_name = (new_name or "").strip()[:max_len]
        if not safe_name:
            return False
        record.display_name = safe_name
        self.save(record)
        return True

    def delete(self, report_id: str) -> bool:
        file_path = os.path.join(self.storage_dir, f"{report_id}.json")
        if os.path.exists(file_path):
            os.remove(file_path)
            return True
        return False

    def delete_many(self, report_ids: List[str]) -> int:
        count = 0
        for rid in report_ids:
            if self.delete(rid):
                count += 1
        return count
