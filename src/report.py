from typing import Dict, Any, List
from datetime import datetime
from .llm_client import LLMClient
from .models import InterviewSession

class ReportGenerator:
    def __init__(self):
        self.llm_client = LLMClient()
    
    def generate_report(self, session: InterviewSession, scenario_config) -> str:
        """生成访谈报告"""
        
        # 构建报告内容
        report = f"""# 消费满意度调研报告

## 基本信息

| 项目 | 内容 |
|------|------|
| 调研场景 | {scenario_config.scenario_name} |
| 会话ID | {session.session_id} |
| 开始时间 | {session.start_time.strftime('%Y-%m-%d %H:%M:%S')} |
| 完成时间 | {session.end_time.strftime('%Y-%m-%d %H:%M:%S') if session.end_time else '进行中'} |
| 访谈状态 | {'已完成' if session.is_complete else '未完成'} |

## 反馈详情

"""
        
        # 添加各槽位反馈
        for slot_name, slot_value in session.slots_collected.items():
            report += f"### {slot_name}\n\n"
            report += f"- **原始回答**: {slot_value.raw_response}\n"
            if slot_value.extracted_value:
                report += f"- **关键信息**: {slot_value.extracted_value}\n"
            if slot_value.need_followup:
                report += f"- **已追问**: 是\n"
            report += "\n"
        
        # 添加对话摘要
        report += "## 对话摘要\n\n"
        for msg in session.conversation_history:
            role = "**用户**" if msg['role'] == 'user' else "**助手**"
            report += f"{role}: {msg['content']}\n\n"
        
        # 使用LLM生成分析建议
        if session.is_complete:
            analysis = self.llm_client.generate_report({
                "scenario_type": session.scenario_type,
                "slots_collected": session.slots_collected,
                "conversation_history": session.conversation_history
            })
            report += "\n## AI分析建议\n\n"
            report += analysis
        
        return report
    
    def save_report(self, report: str, session_id: str) -> str:
        """保存报告到文件"""
        import os
        os.makedirs("reports", exist_ok=True)
        
        filename = f"reports/report_{session_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(report)
        
        return filename