import re
from typing import Dict, Any, Optional
from .llm_client import LLMClient

class Analyzer:
    def __init__(self):
        self.llm_client = LLMClient()
    
    def extract_key_info(self, user_input: str, slot_name: str) -> Optional[str]:
        """从用户输入中提取关键信息"""
        # 简单的关键词提取
        if slot_name == "price_satisfaction":
            patterns = {
                "满意": "满意",
                "贵": "认为价格偏高",
                "便宜": "认为价格实惠",
                "合理": "认为价格合理"
            }
            for key, value in patterns.items():
                if key in user_input:
                    return value
        
        if slot_name == "taste_satisfaction":
            patterns = {
                "好吃": "满意口味",
                "不好吃": "不满意口味",
                "一般": "口味一般"
            }
            for key, value in patterns.items():
                if key in user_input:
                    return value
        
        return None
    
    def needs_followup(self, user_input: str, triggers: list) -> bool:
        """判断是否需要追问"""
        # 检查触发词
        for trigger in triggers:
            if trigger in user_input:
                return True
        
        # 检查负面情绪词
        negative_words = ["差", "烂", "失望", "不行", "糟糕", "后悔"]
        for word in negative_words:
            if word in user_input:
                return True
        
        # 短回答（可能是敷衍）
        if len(user_input.strip()) < 5:
            return True
        
        return False