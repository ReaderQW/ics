from __future__ import annotations

import os
from pathlib import Path

import streamlit as st

from src.analyzer import analyze_user_input
from src.config_loader import load_interview_outline, load_product_info
from src.controller import update_state
from src.data_manager import (
    all_required_filled,
    first_missing_required_slot,
    update_collected_data,
)
from src.generator import stream_generate_opening, stream_generate_response
from src.models import ConversationState, LogicSignal
from src.report import stream_generate_report

ROOT = Path(__file__).resolve().parent
DEFAULT_PRODUCT = ROOT / "config" / "product_info.json"
DEFAULT_OUTLINE = ROOT / "config" / "interview_outline.json"


def _chat_tail(messages: list, max_chars: int = 1200) -> str:
    parts: list[str] = []
    total = 0
    for m in reversed(messages[-12:]):
        line = f"{m['role']}: {m['content']}"
        total += len(line)
        parts.append(line)
        if total >= max_chars:
            break
    return "\n".join(reversed(parts))


def _init_session() -> None:
    if "initialized" in st.session_state:
        return
    st.session_state.initialized = True
    st.session_state.product = load_product_info(
        os.getenv("PRODUCT_CONFIG", str(DEFAULT_PRODUCT))
    )
    st.session_state.outline = load_interview_outline(
        os.getenv("OUTLINE_CONFIG", str(DEFAULT_OUTLINE))
    )
    st.session_state.messages = []
    st.session_state.conversation_state = ConversationState.INITIALIZING
    st.session_state.current_stage_idx = 0
    st.session_state.stage_turn_count = 0
    st.session_state.probe_depth = 0
    st.session_state.collected_data: dict = {}
    st.session_state.started = False
    st.session_state.report_md: str | None = None
    st.session_state.opening_stream_pending = False
    st.session_state.report_stream_pending = False


def _current_stage():
    idx = st.session_state.current_stage_idx
    return st.session_state.outline.stages[idx]


def _start_interview() -> None:
    ss = st.session_state
    ss.started = True
    ss.conversation_state = ConversationState.INTERVIEWING
    ss.current_stage_idx = 0
    ss.stage_turn_count = 0
    ss.probe_depth = 0
    ss.collected_data = {}
    ss.messages = []
    ss.report_md = None
    ss.opening_stream_pending = True
    ss.report_stream_pending = False
    ss.pop("pending_chat_prompt", None)


def _reply_stream_kwargs(user_text: str) -> tuple[dict, object]:
    """
    在已将用户消息写入 messages 之后调用。
    返回 (stream_generate_response 的关键字参数, post_stream 可调用对象)，post_stream 在流式结束后执行。
    """
    ss = st.session_state
    state = ss.conversation_state
    stage = ss.outline.stages[ss.current_stage_idx]
    slots = stage.slots

    if state in (ConversationState.INTERVIEWING, ConversationState.PROBING):
        ss.stage_turn_count += 1

    analysis = analyze_user_input(user_text, slots, ss.collected_data)
    ss.collected_data = update_collected_data(
        ss.collected_data, analysis.extracted_slots, slots
    )

    stage_filled = all_required_filled(ss.collected_data, slots)
    missing = first_missing_required_slot(ss.collected_data, slots)
    probe_focus = analysis.advice.probe_focus or missing

    next_state, signal = update_state(
        current_state=state,
        evaluation=analysis.evaluation,
        advice=analysis.advice,
        stage_turn_count=ss.stage_turn_count,
        probe_depth=ss.probe_depth,
        current_stage_idx=ss.current_stage_idx,
        total_stages=len(ss.outline.stages),
        stage_required_filled=stage_filled,
    )

    if next_state == ConversationState.PROBING:
        ss.probe_depth += 1
    elif state == ConversationState.PROBING and next_state == ConversationState.INTERVIEWING:
        ss.probe_depth = 0
    elif signal == LogicSignal.NEXT_STAGE:
        ss.probe_depth = 0
    elif signal == LogicSignal.OFF_TOPIC_BACK:
        ss.probe_depth = 0

    next_sg = None
    if signal == LogicSignal.NEXT_STAGE and ss.current_stage_idx + 1 < len(ss.outline.stages):
        next_sg = ss.outline.stages[ss.current_stage_idx + 1].goal

    tail = _chat_tail(ss.messages)

    gen_kw = dict(
        conversation_state=next_state.value,
        logic_signal=signal.value,
        stage_goal=stage.goal,
        collected_data=ss.collected_data,
        product_info=ss.product,
        current_slots=slots,
        last_user_input=user_text,
        probe_focus=probe_focus,
        chat_tail=tail,
        next_stage_goal=next_sg,
    )

    def post_stream() -> None:
        if next_state == ConversationState.OFF_TOPIC_HANDLING:
            ss.conversation_state = ConversationState.INTERVIEWING
        else:
            ss.conversation_state = next_state
        if signal == LogicSignal.NEXT_STAGE:
            ss.current_stage_idx += 1
            ss.stage_turn_count = 0
            ss.probe_depth = 0

    return gen_kw, post_stream


def main() -> None:
    st.set_page_config(
        page_title="智能体访谈客服 · 南开食堂",
        page_icon="🎙️",
        layout="wide",
    )
    _init_session()
    ss = st.session_state

    st.markdown(
        """
<style>
  .print-area { max-width: 880px; margin: 0 auto; }
  @media print {
    .no-print, header[data-testid="stHeader"], footer { display: none !important; }
    .block-container { padding-top: 0 !important; max-width: 100% !important; }
  }
</style>
""",
        unsafe_allow_html=True,
    )

    col_main, col_side = st.columns([2, 1], gap="large")

    with col_side:
        st.markdown("### 会话状态")
        st.code(ss.conversation_state.value, language="text")
        st.metric("当前阶段索引", ss.current_stage_idx + 1)
        st.caption(
            f"共 {len(ss.outline.stages)} 个阶段 · "
            f"阶段轮次 {ss.stage_turn_count} · "
            f"追问深度 {ss.probe_depth}"
        )
        st.markdown("### 已归档 Slot")
        st.json(ss.collected_data, expanded=False)

        st.markdown("---")
        st.markdown("### 操作")
        if st.button("开始 / 重置访谈", type="primary"):
            _start_interview()
            st.rerun()

        if ss.conversation_state == ConversationState.FINISHED:
            if st.button("生成就餐体验报告（流式润色）"):
                ss.report_stream_pending = True
                st.rerun()

    with col_main:
        st.title("智能体访谈客服")
        st.caption("Python + Streamlit · 状态机 · Analyzer 非流式 / Generator 与报告流式输出")
        summ = ss.product.summary
        st.markdown(
            f"**访谈主题**：{ss.product.name} — "
            f"{summ if len(summ) <= 100 else summ[:100] + '…'}"
        )

        if not ss.started:
            st.info("点击右侧「开始 / 重置访谈」以流式加载开场白与首问。")
        else:
            # 由页面底部的 chat_input 写入，rerun 后在此消费，保证输入框在布局最下方
            reply_prompt: str | None = ss.pop("pending_chat_prompt", None)
            if (
                reply_prompt
                and ss.conversation_state != ConversationState.FINISHED
                and ss.conversation_state != ConversationState.WRAPPING_UP
            ):
                ss.messages.append({"role": "user", "content": reply_prompt})

            for m in ss.messages:
                with st.chat_message(m["role"]):
                    st.markdown(m["content"])

            # 放在历史消息之后，避免同一次 run 里开场白既流式又按历史再渲染一遍
            if ss.opening_stream_pending:
                ss.opening_stream_pending = False
                stage = _current_stage()
                tail = _chat_tail(ss.messages)
                with st.chat_message("assistant"):
                    acc: list[str] = []

                    def opening_gen():
                        for c in stream_generate_opening(
                            stage.goal, ss.product, stage.slots, tail
                        ):
                            acc.append(c)
                            yield c

                    st.write_stream(opening_gen)
                    ss.messages.append({"role": "assistant", "content": "".join(acc)})

            if (
                reply_prompt
                and ss.conversation_state != ConversationState.FINISHED
                and ss.conversation_state != ConversationState.WRAPPING_UP
            ):
                gen_kw, post_stream = _reply_stream_kwargs(reply_prompt)
                with st.chat_message("assistant"):
                    acc2: list[str] = []

                    def reply_gen():
                        for c in stream_generate_response(**gen_kw):
                            acc2.append(c)
                            yield c

                    st.write_stream(reply_gen)
                    ss.messages.append({"role": "assistant", "content": "".join(acc2)})
                post_stream()

        if ss.report_stream_pending:
            ss.report_stream_pending = False
            st.markdown("---")
            st.markdown('<div class="no-print"><strong>报告生成中（流式）</strong></div>', unsafe_allow_html=True)
            acc: list[str] = []

            def report_gen():
                for c in stream_generate_report(ss.collected_data, ss.product):
                    acc.append(c)
                    yield c

            st.write_stream(report_gen)
            ss.report_md = "".join(acc)

        if ss.report_md:
            st.markdown("---")
            st.markdown(
                '<div class="print-area no-print"><strong>报告预览（浏览器打印可存 PDF）</strong></div>',
                unsafe_allow_html=True,
            )
            st.markdown(ss.report_md)

        if ss.started and ss.conversation_state != ConversationState.FINISHED:
            if prompt := st.chat_input("请输入您的回答…"):
                if ss.conversation_state == ConversationState.WRAPPING_UP:
                    ss.messages.append({"role": "user", "content": prompt})
                    ss.conversation_state = ConversationState.FINISHED
                    ss.messages.append(
                        {
                            "role": "assistant",
                            "content": "好的，非常感谢您抽出时间完成本次访谈，祝您一切顺利！",
                        }
                    )
                    st.rerun()
                ss.pending_chat_prompt = prompt
                st.rerun()


if __name__ == "__main__":
    main()
