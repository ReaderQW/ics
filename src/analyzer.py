import re
from typing import Dict, Any, Optional
from .llm_client import LLMClient

class Analyzer:
    def __init__(self):
        self.llm_client = LLMClient()
        self.invalid_tokens = [
            "傻", "蠢", "垃圾", "去死", "废物", "脑残", "滚", "你妈", "操", "妈的", "艹",
            "sb", "s b", "nmsl", "fuck", "shit"
        ]

    def assess_slot_response(self, user_input: str, slot: Dict[str, Any]) -> Dict[str, Any]:
        """评估当前槽位回答是否相关、是否充分、是否需要追问。"""
        question = slot.get("question", "")
        followup_question = slot.get("followup_question", "")
        triggers = slot.get("followup_trigger", [])

        # 优先使用 LLM 判断，失败后自动回退到规则。
        llm_result = self.llm_client.assess_response(
            question=question,
            user_input=user_input,
            followup_triggers=triggers,
        )
        if llm_result:
            text = user_input.strip()
            normalized = {
                "is_relevant": bool(llm_result.get("is_relevant", True)),
                "is_sufficient": bool(llm_result.get("is_sufficient", True)),
                "need_followup": bool(llm_result.get("need_followup", False)),
                "extracted": (llm_result.get("extracted") or "").strip() or None,
                "reason": (llm_result.get("reason") or "").strip(),
                "redirect_message": (llm_result.get("redirect_message") or "").strip(),
            }

            # 宽松修正：明确给出态度/比较/原因的一句话就视为充分
            key_cues = [
                "贵", "便宜", "合理", "能接受", "还可以", "一般", "不好", "好吃", "难吃", "太久", "排队", "缺货", "服务",
                "相比", "比", "因为", "尤其", "窗口", "档口"
            ]
            if len(text) >= 8 and any(cue in text for cue in key_cues):
                normalized["is_sufficient"] = True

            # 触发词命中时优先走追问，不要一直原题重问
            if any(t in text for t in triggers) and followup_question:
                normalized["need_followup"] = True

            if normalized["need_followup"] and followup_question:
                normalized["followup_question"] = followup_question
            return normalized

        # 规则兜底
        text = user_input.strip()
        off_topic_patterns = ["你是谁", "你哪位", "你是?", "你是谁啊", "在吗", "hello", "hi"]
        is_off_topic = any(p in text.lower() for p in off_topic_patterns)
        is_sufficient = len(text) >= 5 and text not in {"行", "还行", "一般", "不知道"}
        need_followup = self.needs_followup(user_input, triggers)

        return {
            "is_relevant": not is_off_topic,
            "is_sufficient": is_sufficient,
            "need_followup": need_followup,
            "extracted": self.extract_key_info(user_input, slot.get("name", "")),
            "reason": "回答还不够具体" if (not is_sufficient or is_off_topic) else "",
            "redirect_message": "我是校园消费调研助手，我们继续当前问题～",
            "followup_question": followup_question if need_followup and followup_question else "",
        }
    
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
        
        return False

    def is_invalid_text(self, user_input: str) -> bool:
        """过滤辱骂、无意义刷屏和明显无效输入"""
        text = user_input.strip().lower()
        if not text:
            return True

        if text in {"...", "。", "？", "-", "无", "不知道", "不清楚"}:
            return True

        if re.fullmatch(r"([a-zA-Z\u4e00-\u9fa5])\1{4,}", text):
            return True

        return any(token in text for token in self.invalid_tokens)

    def is_confirmation_positive(self, user_input: str) -> bool:
        text = user_input.strip()
        positive_patterns = ["是", "对", "确认", "没问题", "可以", "同意", "准确", "正确"]
        return any(p in text for p in positive_patterns)

    def is_confirmation_negative(self, user_input: str) -> bool:
        text = user_input.strip()
        negative_patterns = ["不是", "不对", "有误", "不准确", "不太对", "不完全", "需要修改", "要补充"]
        return any(p in text for p in negative_patterns)