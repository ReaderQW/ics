# src/models.py
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from enum import Enum
from datetime import datetime
import json

class InterviewState(str, Enum):
    GREETING = "greeting"
    ASKING = "asking"
    FOLLOWUP = "followup"
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
    start_time: datetime = Field(default_factory=datetime.now)
    end_time: Optional[datetime] = None
    state: InterviewState = InterviewState.GREETING  # 默认值
    current_slot_index: int = 0
    slots_collected: Dict[str, SlotValue] = Field(default_factory=dict)
    conversation_history: List[Dict[str, str]] = Field(default_factory=list)
    is_complete: bool = False

class ScenarioConfig(BaseModel):
    scenario_name: str
    scenario_type: str
    greeting: str
    farewell: str
    slots: List[Dict[str, Any]]


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
    if 'state' in data and isinstance(data['state'], str):
        data['state'] = InterviewState(data['state'])
    if 'start_time' in data and isinstance(data['start_time'], str):
        data['start_time'] = datetime.fromisoformat(data['start_time'])
    if 'end_time' in data and data['end_time'] and isinstance(data['end_time'], str):
        data['end_time'] = datetime.fromisoformat(data['end_time'])
    return data