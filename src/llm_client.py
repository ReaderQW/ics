import os
import json
from openai import OpenAI
from typing import Optional, Dict, Any
from dotenv import load_dotenv

load_dotenv()

class LLMClient:
    def __init__(self):
        self.api_key = os.getenv("LLM_API_KEY")
        self.base_url = os.getenv("LLM_BASE_URL", "https://api.siliconflow.cn/v1")
        self.model = os.getenv("LLM_MODEL", "deepseek-ai/DeepSeek-V3")
        self.timeout_seconds = float(os.getenv("LLM_TIMEOUT_SECONDS", "30"))
        self.client: Optional[OpenAI] = None
        
        if self.api_key:
            self.client = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
                timeout=self.timeout_seconds,
            )
    
    def chat(self, messages: list, temperature: float = 0.7) -> str:
        """发送对话请求"""
        if not self.client:
            return ""
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature
            )
            return response.choices[0].message.content
        except Exception as e:
            print(
                "LLM调用失败: "
                f"{type(e).__name__}: {e}. "
                f"base_url={self.base_url}, model={self.model}. "
                "请检查网络、代理/防火墙、API Key 与 LLM_BASE_URL 是否可达。"
            )
            return ""

    def _extract_json(self, text: str) -> Optional[Dict[str, Any]]:
        if not text:
            return None
        content = text.strip()
        try:
            return json.loads(content)
        except Exception:
            pass

        # 兼容模型返回 ```json ... ```
        if "```" in content:
            start = content.find("{")
            end = content.rfind("}")
            if start != -1 and end != -1 and end > start:
                snippet = content[start:end + 1]
                try:
                    return json.loads(snippet)
                except Exception:
                    return None
        return None

    def assess_response(self, question: str, user_input: str, followup_triggers: list) -> Optional[Dict[str, Any]]:
        """评估回答质量与相关性，用于决定是否追问或拉回主线。"""
        prompt = f"""
你是访谈质量评估器。请判断用户回答是否和当前问题相关、是否充分、是否需要追问。

判定要点（非常重要）：
1) 只要用户明确表达了态度或结论（如“有点贵”“还可以”“能接受”），通常视为 is_sufficient=true。
2) 不要因为“缺少非常细节”就判定不充分；访谈是轻量对话。
3) 如果命中追问触发词（如“贵”“不好吃”），优先 need_followup=true，而不是反复原题重问。
4) 只有明显跑题时，is_relevant=false。

当前问题：{question}
用户回答：{user_input}
追问触发词：{followup_triggers}

仅返回 JSON：
{{
  "is_relevant": true/false,
  "is_sufficient": true/false,
  "need_followup": true/false,
  "extracted": "可用于报告的简短关键信息，没有则空字符串",
  "reason": "一句简短原因",
  "redirect_message": "若跑题，用一句礼貌拉回主线的话；否则空字符串"
}}
"""
        response = self.chat([
            {"role": "system", "content": "你是严格的JSON输出助手，不要输出任何JSON以外内容。"},
            {"role": "user", "content": prompt},
        ], temperature=0.2)
        return self._extract_json(response)
    
    def analyze_intent(self, user_input: str, followup_triggers: list) -> Dict[str, Any]:
        """分析用户意图，判断是否需要追问"""
        trigger_words = [w for w in followup_triggers if w in user_input]
        
        if trigger_words:
            return {
                "need_followup": True,
                "triggered_by": trigger_words,
                "confidence": 0.8
            }
        
        # 使用LLM进行更精细的判断
        prompt = f"""
        分析用户对某个问题的回答，判断是否表达了对现状的不满或负面情绪。
        用户回答："{user_input}"
        
        如果用户表达了不满、抱怨或负面评价，返回 {{"negative": true, "reason": "简短原因"}}
        如果用户表示满意或中性，返回 {{"negative": false, "reason": ""}}
        """
        
        try:
            response = self.chat([
                {"role": "system", "content": "你是一个情绪分析助手，只返回JSON格式。"},
                {"role": "user", "content": prompt}
            ])
            result = self._extract_json(response) or {}
            return {
                "need_followup": result.get("negative", False),
                "triggered_by": [],
                "confidence": 0.7
            }
        except:
            return {"need_followup": False, "triggered_by": [], "confidence": 0.5}
    
    def generate_report(self, session_data: dict) -> str:
        """生成访谈报告"""
        prompt = f"""
        请根据以下访谈数据，生成一份结构化的消费满意度调研报告。
        
        场景类型：{session_data.get('scenario_type', '未知')}
        收集到的反馈：
        {self._format_slots(session_data.get('slots_collected', {}))}
        
        对话历史摘要：
        {self._format_history(session_data.get('conversation_history', []))}
        
        请按以下格式输出Markdown报告：
        ## 调研概览
        ### 基本信息
        - 调研场景：[场景名称]
        - 完成时间：[时间]
        
        ## 满意度分析
        ### 各维度反馈详情
        [逐条列出各槽位的反馈和追问内容]
        
        ## 核心问题总结
        [总结3-5个关键问题]
        
        ## 改进建议
        [针对每个问题提出具体建议]
        """
        
        response = self.chat([
            {"role": "system", "content": "你是一个专业的数据分析报告生成助手。"},
            {"role": "user", "content": prompt}
        ])
        
        return response
    
    def _format_slots(self, slots: dict) -> str:
        lines = []
        for name, value in slots.items():
            if hasattr(value, 'raw_response'):
                lines.append(f"- {name}: {value.raw_response}")
                if hasattr(value, 'extracted_value') and value.extracted_value:
                    lines.append(f"  提炼: {value.extracted_value}")
        return "\n".join(lines) if lines else "暂无详细反馈"
    
    def _format_history(self, history: list) -> str:
        if not history:
            return "暂无对话记录"
        lines = []
        for msg in history[-6:]:  # 只取最后6条
            role = "用户" if msg.get('role') == 'user' else "助手"
            lines.append(f"{role}: {msg.get('content', '')[:100]}")
        return "\n".join(lines)
