from __future__ import annotations

import json
import os
import re
import time
from collections.abc import Iterator
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()


def get_client() -> OpenAI | None:
    key = os.getenv("OPENAI_API_KEY", "").strip()
    if not key or key.startswith("sk-your"):
        return None
    base = os.getenv("OPENAI_BASE_URL", "").strip() or None
    return OpenAI(api_key=key, base_url=base)


def get_model() -> str:
    return os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip() or "gpt-4o-mini"


def mock_llm_enabled() -> bool:
    return os.getenv("MOCK_LLM", "").lower() in ("1", "true", "yes")


def chat_completion(system: str, user: str, temperature: float = 0.3) -> str:
    if mock_llm_enabled() or get_client() is None:
        return _mock_response(system, user)
    client = get_client()
    assert client is not None
    r = client.chat.completions.create(
        model=get_model(),
        temperature=temperature,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    return (r.choices[0].message.content or "").strip()


def chat_completion_stream(
    system: str,
    user: str,
    temperature: float = 0.3,
    chunk_size: int = 8,
) -> Iterator[str]:
    """面向用户可见文案的流式输出（逐段 yield 字符串）。"""
    if mock_llm_enabled() or get_client() is None:
        text = _mock_response(system, user)
        for i in range(0, len(text), chunk_size):
            time.sleep(0.012)
            yield text[i : i + chunk_size]
        return
    client = get_client()
    assert client is not None
    stream = client.chat.completions.create(
        model=get_model(),
        temperature=temperature,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        stream=True,
    )
    for chunk in stream:
        delta = chunk.choices[0].delta
        if delta and delta.content:
            yield delta.content


def extract_json_object(text: str) -> dict[str, Any]:
    text = text.strip()
    m = re.search(r"\{[\s\S]*\}", text)
    if not m:
        raise ValueError("响应中未找到 JSON 对象")
    return json.loads(m.group())


def _mock_response(system: str, user: str) -> str:
    if "严格输出 JSON" in system or "JSON" in system[:200]:
        return json.dumps(
            {
                "extracted_slots": [
                    {
                        "name": "mock_slot",
                        "value": user[:80],
                        "confidence": 0.5,
                        "is_new": True,
                    }
                ],
                "evaluation": {
                    "quality": "vague",
                    "engagement": "medium",
                    "intent_type": "answer",
                    "user_exit_intent": False,
                },
                "advice": {
                    "should_probe": True,
                    "probe_focus": "mock_slot",
                    "should_advance_suggestion": False,
                },
            },
            ensure_ascii=False,
        )
    if "就餐体验报告" in system or "用户体验报告" in system or "润色" in system:
        return (
            "## 1. 总体评价\n\n"
            "- （演示模式）基于结构化 Slot 的占位润色。\n\n"
            "## 2. 核心维度分析\n\n"
            "### 维度 A\n\n"
            "- 待接入真实模型后根据 Slot 生成。\n\n"
            "## 3. 改进建议\n\n"
            "- 请配置 OPENAI_API_KEY 后重新生成报告。\n"
        )
    return (
        "（演示模式）感谢您的回复。能再具体说说您的感受吗？"
        if "PROBE" in user or "追问" in system
        else "（演示模式）好的，我们继续下一个话题。"
    )
