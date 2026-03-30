from __future__ import annotations

from typing import Any

from src.llm_client import chat_completion, extract_json_object
from src.models import (
    AdviceResult,
    AnalyzerOutput,
    EvaluationResult,
    SlotDefinition,
    SlotResult,
)
from src.prompts import ANALYZER_SYSTEM, build_analyzer_user_payload


def analyze_user_input(
    user_input: str,
    current_slots: list[SlotDefinition],
    collected_data: dict[str, Any],
) -> AnalyzerOutput:
    slots_def = [s.model_dump() for s in current_slots]
    # 当前阶段相关快照：只传本阶段 slot 名
    names = {s.name for s in current_slots}
    snapshot = {k: v for k, v in collected_data.items() if k in names}

    user = build_analyzer_user_payload(user_input, slots_def, snapshot)
    raw = chat_completion(ANALYZER_SYSTEM, user, temperature=0.2)
    data = extract_json_object(raw)
    return _parse_analyzer(data)


def _parse_analyzer(data: dict[str, Any]) -> AnalyzerOutput:
    slots_raw = data.get("extracted_slots") or []
    extracted: list[SlotResult] = []
    for x in slots_raw:
        if not isinstance(x, dict) or "name" not in x:
            continue
        extracted.append(
            SlotResult(
                name=str(x["name"]),
                value=x.get("value"),
                confidence=float(x.get("confidence", 0.5)),
                is_new=bool(x.get("is_new", True)),
            )
        )

    ev = data.get("evaluation") or {}
    evaluation = EvaluationResult(
        quality="vague" if ev.get("quality") == "vague" else "clear",
        engagement=_engagement(ev.get("engagement")),
        intent_type=_intent(ev.get("intent_type")),
        user_exit_intent=bool(ev.get("user_exit_intent", False)),
    )

    ad = data.get("advice") or {}
    advice = AdviceResult(
        should_probe=bool(ad.get("should_probe", False)),
        probe_focus=ad.get("probe_focus"),
        should_advance_suggestion=bool(ad.get("should_advance_suggestion", False)),
    )

    return AnalyzerOutput(
        extracted_slots=extracted,
        evaluation=evaluation,
        advice=advice,
    )


def _engagement(v: Any) -> str:
    if v in ("high", "medium", "low"):
        return v
    return "medium"


def _intent(v: Any) -> str:
    if v in ("answer", "off_topic", "user_question", "refusal"):
        return v
    return "answer"
