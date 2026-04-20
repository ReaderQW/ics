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
| 具体店铺 | {session.shop_name or '未指定'} |
| 会话ID | {session.session_id} |
| 开始时间 | {session.start_time.strftime('%Y-%m-%d %H:%M:%S')} |
| 完成时间 | {session.end_time.strftime('%Y-%m-%d %H:%M:%S') if session.end_time else '进行中'} |
| 无效输入过滤次数 | {session.invalid_input_count} |
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

        if session.confirmation_summary:
            report += "## 结束前观点确认\n\n"
            report += f"{session.confirmation_summary}\n\n"

        if session.correction_notes:
            report += "## 用户补充说明\n\n"
            for note in session.correction_notes:
                report += f"- {note}\n"
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
            report += analysis if analysis else "AI 分析暂时不可用，请检查 LLM 配置后重试。"
        
        return report
    
    def save_report(self, report: str, session_id: str) -> str:
        """保存报告到文件"""
        import os
        os.makedirs("reports", exist_ok=True)
        
        filename = f"reports/report_{session_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(report)
        
        return filename

    def generate_summary_report(self, report_contents: List[str], title: str = "批量访谈总结报告") -> str:
        """将多份访谈报告汇总为一份总结报告"""
        if not report_contents:
            return "# 批量访谈总结报告\n\n暂无可汇总的报告内容。"

        merged = "\n\n---\n\n".join(report_contents[:30])
        prompt = f"""
请基于以下多份访谈报告内容，生成一份结构化中文总结报告（Markdown）：

要求：
1. 给出总体满意度倾向
2. 提炼高频问题（按主题归类）
3. 对问题给出可执行改进建议
4. 给出优先级（高/中/低）与原因
5. 最后补充“下一步调研建议”

输出标题使用：# {title}

原始材料：
{merged}
"""

        content = self.llm_client.chat(
            [
                {"role": "system", "content": "你是专业的商户经营分析顾问，擅长多份用户访谈归纳总结。"},
                {"role": "user", "content": prompt},
            ],
            temperature=0.4,
        )

        if not content:
            return f"# {title}\n\nAI 总结暂时不可用，请稍后重试。"
        return content