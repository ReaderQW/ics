from __future__ import annotations

from src.models import AdviceResult, ConversationState, EvaluationResult, LogicSignal


MAX_STAGE_TURNS = 3
MAX_PROBE_CHAIN = 2


def update_state(
    current_state: ConversationState,
    evaluation: EvaluationResult,
    advice: AdviceResult,
    stage_turn_count: int,
    probe_depth: int,
    current_stage_idx: int,
    total_stages: int,
    stage_required_filled: bool,
) -> tuple[ConversationState, LogicSignal]:
    """
    信号优先级：
    P0 Exit -> WRAPPING_UP
    P1 Anomaly -> OFF_TOPIC_HANDLING + OFF_TOPIC_BACK
    P2 Probe -> PROBING + PROBE
    P3 Advance -> NEXT_STAGE 或最后一阶段 -> WRAPPING_UP
    默认：同阶段继续 INTERVIEWING + PROBE（下一问）
    """
    if evaluation.user_exit_intent:
        return ConversationState.WRAPPING_UP, LogicSignal.WRAP_CONFIRM

    if current_state in (ConversationState.INTERVIEWING, ConversationState.PROBING):
        if evaluation.intent_type in ("off_topic", "user_question"):
            return ConversationState.OFF_TOPIC_HANDLING, LogicSignal.OFF_TOPIC_BACK

    can_probe = stage_turn_count < MAX_STAGE_TURNS and probe_depth < MAX_PROBE_CHAIN
    need_probe = (
        (evaluation.quality == "vague" or advice.should_probe)
        and can_probe
        and not stage_required_filled
    )

    if need_probe:
        return ConversationState.PROBING, LogicSignal.PROBE

    should_advance = (
        stage_required_filled
        or stage_turn_count >= MAX_STAGE_TURNS
        or advice.should_advance_suggestion
    )

    if should_advance:
        if current_stage_idx >= total_stages - 1:
            return ConversationState.WRAPPING_UP, LogicSignal.WRAP_CONFIRM
        return ConversationState.INTERVIEWING, LogicSignal.NEXT_STAGE

    if current_state == ConversationState.PROBING:
        return ConversationState.INTERVIEWING, LogicSignal.PROBE

    return ConversationState.INTERVIEWING, LogicSignal.PROBE
