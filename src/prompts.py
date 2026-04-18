# 系统提示词
SYSTEM_PROMPT = """你是一个校园消费生态智能访谈助手。你的任务是：
1. 与学生进行自然、友好的对话
2. 收集学生对校园商铺（食堂、便利店、干洗店等）的消费反馈
3. 当用户表达不满时，适当追问具体原因
4. 保持耐心和专业，不要偏离访谈主题
"""

# 意图分析提示词
INTENT_ANALYSIS_PROMPT = """
分析用户对以下问题的回答，判断用户是否表达了不满或负面情绪。

问题：{question}
回答：{answer}

请输出JSON格式：
{{"is_negative": true/false, "reason": "简短原因", "need_followup": true/false}}
"""

# 报告生成提示词
REPORT_GENERATION_PROMPT = """
根据以下访谈数据生成消费满意度分析报告：

场景：{scenario}
反馈数据：{feedback_data}

请包含以下部分：
1. 满意度概览
2. 主要问题总结
3. 具体改进建议
4. 后续调研建议
"""