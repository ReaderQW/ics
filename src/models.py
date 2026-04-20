# src/models.py
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from enum import Enum
from datetime import datetime
import json


class ReportType(str, Enum):
    BASE = "base"
    SUMMARY = "summary"

class InterviewState(str, Enum):
    GREETING = "greeting"
    ASKING = "asking"
    FOLLOWUP = "followup"
    CONFIRMING = "confirming"
    COMPLETED = "completed"
    FAREWELL = "farewell"

class SlotValue(BaseModel):
    slot_name: str
    raw_response: str
    extracted_value: Optional[str] = None
    need_followup: bool = False
    followup_asked: bool = False

class InterviewSession(BaseModel):
    session_id: str
    scenario_type: str
    shop_name: Optional[str] = None
    start_time: datetime = Field(default_factory=datetime.now)
    end_time: Optional[datetime] = None
    state: InterviewState = InterviewState.GREETING  # 默认值
    current_slot_index: int = 0
    slots_collected: Dict[str, SlotValue] = Field(default_factory=dict)
    slot_retry_counts: Dict[str, int] = Field(default_factory=dict)
    conversation_history: List[Dict[str, str]] = Field(default_factory=list)
    confirmation_summary: Optional[str] = None
    awaiting_correction: bool = False
    correction_notes: List[str] = Field(default_factory=list)
    invalid_input_count: int = 0
    report_id: Optional[str] = None
    is_complete: bool = False

class ScenarioConfig(BaseModel):
    scenario_name: str
    scenario_type: str
    greeting: str
    farewell: str
    shop_options: List[str] = Field(default_factory=list)
    slots: List[Dict[str, Any]]


class SlotDefinition(BaseModel):
    name: str
    type: str = "single"
    required: bool = True
    allow_overwrite: bool = True


class ProductInfo(BaseModel):
    name: str
    summary: str
    target_users: Optional[str] = ""
    version: Optional[str] = ""

    def as_context_text(self) -> str:
        return (
            f"名称：{self.name}\n"
            f"简介：{self.summary}\n"
            f"目标用户：{self.target_users or '未提供'}\n"
            f"版本：{self.version or '未提供'}"
        )


class ReportRecord(BaseModel):
    report_id: str
    report_type: ReportType
    display_name: str
    scenario_type: str
    shop_name: Optional[str] = None
    session_id: Optional[str] = None
    source_report_ids: List[str] = Field(default_factory=list)
    content_markdown: str
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


# 自定义JSON编码器，处理枚举类型
class CustomEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Enum):
            return obj.value
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)


def decode_session(data: dict) -> dict:
    """解码会话数据，将字符串状态转换回枚举"""
    if 'slot_retry_counts' not in data or not isinstance(data.get('slot_retry_counts'), dict):
        data['slot_retry_counts'] = {}
    if 'state' in data and isinstance(data['state'], str):
        data['state'] = InterviewState(data['state'])
    if 'start_time' in data and isinstance(data['start_time'], str):
        data['start_time'] = datetime.fromisoformat(data['start_time'])
    if 'end_time' in data and data['end_time'] and isinstance(data['end_time'], str):
        data['end_time'] = datetime.fromisoformat(data['end_time'])
    return data