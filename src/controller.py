# src/controller.py
from typing import Dict, Any, Optional
from .models import InterviewSession, InterviewState, SlotValue
from .analyzer import Analyzer
from .llm_client import LLMClient

class Controller:
    def __init__(self, config):
        self.config = config
        self.analyzer = Analyzer()
        self.llm_client = LLMClient()
    
    def get_next_question(self, session: InterviewSession) -> Optional[str]:
        """根据当前状态获取下一个问题"""
        # 防御性检查：确保state是InterviewState类型
        if isinstance(session.state, str):
            session.state = InterviewState(session.state)
        
        if session.state == InterviewState.GREETING:
            session.state = InterviewState.ASKING
            return self.config.greeting
        
        elif session.state == InterviewState.ASKING:
            if session.current_slot_index < len(self.config.slots):
                slot = self.config.slots[session.current_slot_index]
                return slot.get("question")
            else:
                session.state = InterviewState.CONFIRMING
                session.confirmation_summary = self._build_confirmation_summary(session)
                return self._build_confirmation_prompt(session.confirmation_summary)
        
        elif session.state == InterviewState.FOLLOWUP:
            # 返回追问问题
            if session.current_slot_index < len(self.config.slots):
                slot = self.config.slots[session.current_slot_index]
                return slot.get("followup_question")

        elif session.state == InterviewState.CONFIRMING:
            if session.confirmation_summary is None:
                session.confirmation_summary = self._build_confirmation_summary(session)
            return self._build_confirmation_prompt(session.confirmation_summary)
        
        elif session.state == InterviewState.COMPLETED:
            session.state = InterviewState.FAREWELL
            return self.config.farewell
        
        return None
    
    def process_response(self, session: InterviewSession, user_input: str) -> Dict[str, Any]:
        """处理用户响应"""
        # 防御性检查：确保state是InterviewState类型
        if isinstance(session.state, str):
            session.state = InterviewState(session.state)
        
        result = {
            "next_question": None,
            "slot_updated": False,
            "need_followup": False,
            "is_invalid": False
        }

        # 自动过滤辱骂与无效输入
        if self.analyzer.is_invalid_text(user_input):
            session.invalid_input_count += 1
            result["is_invalid"] = True
            result["next_question"] = "我先帮你过滤了这条无效内容。为了保证访谈质量，请用文明且具体的描述再回答一次。"
            return result
        
        # 保存对话历史
        session.conversation_history.append({"role": "user", "content": user_input})
        
        if session.state == InterviewState.ASKING:
            current_slot = self.config.slots[session.current_slot_index]
            slot_name = current_slot.get("name")
            retry_map = getattr(session, "slot_retry_counts", None)
            if not isinstance(retry_map, dict):
                try:
                    session.slot_retry_counts = {}
                    retry_map = session.slot_retry_counts
                except Exception:
                    retry_map = {}
            retry_count = retry_map.get(slot_name, 0)

            assessment = self.analyzer.assess_slot_response(user_input, current_slot)
            if not assessment.get("is_relevant", True):
                redirect = assessment.get("redirect_message") or "我是校园消费调研助手，我们继续当前问题～"
                result["next_question"] = f"{redirect}\n\n{current_slot.get('question')}"
                return result

            # 存储原始回答
            slot_value = SlotValue(
                slot_name=slot_name,
                raw_response=user_input
            )

            if assessment.get("extracted"):
                slot_value.extracted_value = assessment.get("extracted")

            # 检查是否需要追问
            need_followup = bool(assessment.get("need_followup"))

            if need_followup and current_slot.get("followup_question"):
                retry_map[slot_name] = 0
                if hasattr(session, "slot_retry_counts"):
                    session.slot_retry_counts = retry_map
                slot_value.need_followup = True
                session.slots_collected[slot_name] = slot_value
                session.state = InterviewState.FOLLOWUP
                result["need_followup"] = True
                result["next_question"] = current_slot.get("followup_question")
            else:
                if not assessment.get("is_sufficient", True):
                    # 最多只要求补充一次，避免用户被卡死在单题
                    if retry_count < 1:
                        retry_map[slot_name] = retry_count + 1
                        if hasattr(session, "slot_retry_counts"):
                            session.slot_retry_counts = retry_map
                        result["next_question"] = f"收到，你可以再补充一句简短原因吗？\n\n{current_slot.get('question')}"
                        return result

                if not slot_value.extracted_value:
                    extracted = self.analyzer.extract_key_info(user_input, slot_name)
                    if extracted:
                        slot_value.extracted_value = extracted

                retry_map[slot_name] = 0
                if hasattr(session, "slot_retry_counts"):
                    session.slot_retry_counts = retry_map
                session.slots_collected[slot_name] = slot_value
                session.current_slot_index += 1
                result["slot_updated"] = True
                result["next_question"] = self.get_next_question(session)
        
        elif session.state == InterviewState.FOLLOWUP:
            # 处理追问的回答
            current_slot = self.config.slots[session.current_slot_index]
            slot_name = current_slot.get("name")
            
            if slot_name in session.slots_collected:
                session.slots_collected[slot_name].extracted_value = user_input
                session.slots_collected[slot_name].followup_asked = True
            
            # 移动到下一个槽位
            session.current_slot_index += 1
            session.state = InterviewState.ASKING
            result["next_question"] = self.get_next_question(session)

        elif session.state == InterviewState.CONFIRMING:
            if session.awaiting_correction:
                session.correction_notes.append(user_input)
                session.awaiting_correction = False
                session.confirmation_summary = self._build_confirmation_summary(session)
                result["next_question"] = (
                    "已记录你的补充。\n\n"
                    + self._build_confirmation_prompt(session.confirmation_summary)
                )
            elif self.analyzer.is_confirmation_positive(user_input):
                session.is_complete = True
                session.state = InterviewState.COMPLETED
                result["next_question"] = self.get_next_question(session)
            elif self.analyzer.is_confirmation_negative(user_input):
                session.awaiting_correction = True
                result["next_question"] = "收到，请告诉我哪些观点需要修改或补充，我会更新摘要后再次请你确认。"
            else:
                result["next_question"] = "如果你确认摘要准确，请回复“确认”；如果需要修改，请回复“需要修改”。"
        
        elif session.state == InterviewState.COMPLETED:
            session.is_complete = True
            result["next_question"] = self.get_next_question(session)
        
        # 保存助手的回复
        if result["next_question"]:
            session.conversation_history.append(
                {"role": "assistant", "content": result["next_question"]}
            )
        
        return result
    
    def _get_completion_message(self) -> str:
        return "太好了！我们已经收集了足够的反馈信息。"

    def _build_confirmation_summary(self, session: InterviewSession) -> str:
        lines = ["### 观点确认摘要"]
        for idx, slot in enumerate(self.config.slots, start=1):
            slot_name = slot.get("name")
            question = slot.get("question", slot_name)
            slot_value = session.slots_collected.get(slot_name)
            answer = slot_value.extracted_value if slot_value and slot_value.extracted_value else (
                slot_value.raw_response if slot_value else "（未采集）"
            )
            lines.append(f"{idx}. {question}：{answer}")

        if session.correction_notes:
            lines.append("\n补充说明：")
            for note in session.correction_notes[-3:]:
                lines.append(f"- {note}")

        return "\n".join(lines)

    def _build_confirmation_prompt(self, summary: str) -> str:
        return (
            f"{summary}\n\n"
            "请确认以上总结是否准确。\n"
            "- 回复“确认”结束访谈\n"
            "- 回复“需要修改”补充观点"
        )