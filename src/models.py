from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


class ConversationState(str, Enum):
    INITIALIZING = "INITIALIZING"
    INTERVIEWING = "INTERVIEWING"
    PROBING = "PROBING"
    OFF_TOPIC_HANDLING = "OFF_TOPIC_HANDLING"
    WRAPPING_UP = "WRAPPING_UP"
    FINISHED = "FINISHED"


class LogicSignal(str, Enum):
    PROBE = "PROBE"
    NEXT_STAGE = "NEXT_STAGE"
    OFF_TOPIC_BACK = "OFF_TOPIC_BACK"
    WRAP_CONFIRM = "WRAP_CONFIRM"
    OPENING = "OPENING"


class SlotDefinition(BaseModel):
    name: str
    type: Literal["single", "multiple"]
    allow_overwrite: bool = False
    required: bool = True


class InterviewStage(BaseModel):
    id: str
    goal: str
    slots: list[SlotDefinition]


class InterviewOutline(BaseModel):
    stages: list[InterviewStage]


class ProductInfo(BaseModel):
    name: str = ""
    summary: str = ""
    target_users: str = ""
    version: str = ""

    def as_context_text(self) -> str:
        parts = [
            f"产品名称: {self.name}",
            f"简介: {self.summary}",
            f"目标用户: {self.target_users}",
            f"版本: {self.version}",
        ]
        return "\n".join(parts)


class SlotResult(BaseModel):
    name: str
    value: Any
    confidence: float = Field(ge=0.0, le=1.0)
    is_new: bool = True


class EvaluationResult(BaseModel):
    quality: Literal["clear", "vague"]
    engagement: Literal["high", "medium", "low"]
    intent_type: Literal["answer", "off_topic", "user_question", "refusal"]
    user_exit_intent: bool = False


class AdviceResult(BaseModel):
    should_probe: bool = False
    probe_focus: str | None = None
    should_advance_suggestion: bool = False


class AnalyzerOutput(BaseModel):
    extracted_slots: list[SlotResult] = Field(default_factory=list)
    evaluation: EvaluationResult
    advice: AdviceResult
