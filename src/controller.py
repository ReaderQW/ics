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
                session.state = InterviewState.COMPLETED
                return self._get_completion_message()
        
        elif session.state == InterviewState.FOLLOWUP:
            # 返回追问问题
            if session.current_slot_index < len(self.config.slots):
                slot = self.config.slots[session.current_slot_index]
                return slot.get("followup_question")
        
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
            "need_followup": False
        }
        
        # 保存对话历史
        session.conversation_history.append({"role": "user", "content": user_input})
        
        if session.state == InterviewState.ASKING:
            current_slot = self.config.slots[session.current_slot_index]
            slot_name = current_slot.get("name")
            
            # 存储原始回答
            slot_value = SlotValue(
                slot_name=slot_name,
                raw_response=user_input
            )
            
            # 检查是否需要追问
            triggers = current_slot.get("followup_trigger", [])
            need_followup = self.analyzer.needs_followup(user_input, triggers)
            
            if need_followup and current_slot.get("followup_question"):
                slot_value.need_followup = True
                session.slots_collected[slot_name] = slot_value
                session.state = InterviewState.FOLLOWUP
                result["need_followup"] = True
                result["next_question"] = current_slot.get("followup_question")
            else:
                # 提取关键信息
                extracted = self.analyzer.extract_key_info(user_input, slot_name)
                if extracted:
                    slot_value.extracted_value = extracted
                
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