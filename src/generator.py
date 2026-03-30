from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any

from src.llm_client import chat_completion, chat_completion_stream
from src.models import ProductInfo, SlotDefinition
from src.prompts import GENERATOR_SYSTEM, build_generator_user_payload


def generate_response(
    conversation_state: str,
    logic_signal: str,
    stage_goal: str,
    collected_data: dict[str, Any],
    product_info: ProductInfo,
    current_slots: list[SlotDefinition],
    last_user_input: str,
    probe_focus: str | None,
    chat_tail: str,
    next_stage_goal: str | None = None,
) -> str:
    checklist = [
        {
            "name": s.name,
            "type": s.type,
            "required": s.required,
        }
        for s in current_slots
    ]
    checklist_text = json.dumps(checklist, ensure_ascii=False, indent=2)
    collected_summary = json.dumps(collected_data, ensure_ascii=False, indent=2)

    user = build_generator_user_payload(
        conversation_state=conversation_state,
        logic_signal=logic_signal,
        stage_goal=stage_goal,
        product_context=product_info.as_context_text(),
        checklist_text=checklist_text,
        collected_summary=collected_summary,
        last_user_input=last_user_input,
        probe_focus=probe_focus,
        chat_tail=chat_tail,
        next_stage_goal=next_stage_goal,
    )
    return chat_completion(GENERATOR_SYSTEM, user, temperature=0.7)


def stream_generate_response(
    conversation_state: str,
    logic_signal: str,
    stage_goal: str,
    collected_data: dict[str, Any],
    product_info: ProductInfo,
    current_slots: list[SlotDefinition],
    last_user_input: str,
    probe_focus: str | None,
    chat_tail: str,
    next_stage_goal: str | None = None,
) -> Iterator[str]:
    checklist = [
        {
            "name": s.name,
            "type": s.type,
            "required": s.required,
        }
        for s in current_slots
    ]
    checklist_text = json.dumps(checklist, ensure_ascii=False, indent=2)
    collected_summary = json.dumps(collected_data, ensure_ascii=False, indent=2)

    user = build_generator_user_payload(
        conversation_state=conversation_state,
        logic_signal=logic_signal,
        stage_goal=stage_goal,
        product_context=product_info.as_context_text(),
        checklist_text=checklist_text,
        collected_summary=collected_summary,
        last_user_input=last_user_input,
        probe_focus=probe_focus,
        chat_tail=chat_tail,
        next_stage_goal=next_stage_goal,
    )
    yield from chat_completion_stream(GENERATOR_SYSTEM, user, temperature=0.7)


def generate_opening(
    stage_goal: str,
    product_info: ProductInfo,
    current_slots: list[SlotDefinition],
    chat_tail: str,
) -> str:
    return generate_response(
        conversation_state="INTERVIEWING",
        logic_signal="OPENING",
        stage_goal=stage_goal,
        collected_data={},
        product_info=product_info,
        current_slots=current_slots,
        last_user_input="（访谈刚刚开始，用户尚未发言）",
        probe_focus=None,
        chat_tail=chat_tail,
    )


def stream_generate_opening(
    stage_goal: str,
    product_info: ProductInfo,
    current_slots: list[SlotDefinition],
    chat_tail: str,
) -> Iterator[str]:
    yield from stream_generate_response(
        conversation_state="INTERVIEWING",
        logic_signal="OPENING",
        stage_goal=stage_goal,
        collected_data={},
        product_info=product_info,
        current_slots=current_slots,
        last_user_input="（访谈刚刚开始，用户尚未发言）",
        probe_focus=None,
        chat_tail=chat_tail,
    )
