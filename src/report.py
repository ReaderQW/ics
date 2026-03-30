from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any

from src.llm_client import chat_completion, chat_completion_stream
from src.models import ProductInfo
from src.prompts import REPORT_POLISH_SYSTEM, build_report_user_payload

DEFAULT_MARKDOWN_TEMPLATE = """# 就餐体验报告（草稿 — 仅含 Slot 事实）

**主题**: {{product_name}}

## 结构化访谈数据

```json
{{collected_json}}
```

---
*以下章节将由模型在严禁幻觉的前提下润色*
"""


def fill_markdown_template(
    template: str,
    collected_data: dict[str, Any],
    product_info: ProductInfo,
) -> str:
    return (
        template.replace("{{product_name}}", product_info.name)
        .replace("{{collected_json}}", json.dumps(collected_data, ensure_ascii=False, indent=2))
    )


def generate_report(
    collected_data: dict[str, Any],
    product_info: ProductInfo,
    markdown_template: str | None = None,
) -> tuple[str, bytes | None]:
    """
    返回 (report_md, report_pdf)。
    PDF 可选：当前为 None，前端使用浏览器打印 Markdown 渲染区域即可。
    """
    tpl = markdown_template or DEFAULT_MARKDOWN_TEMPLATE
    filled = fill_markdown_template(tpl, collected_data, product_info)
    user = build_report_user_payload(filled, product_info.as_context_text())
    polished = chat_completion(REPORT_POLISH_SYSTEM, user, temperature=0.4)
    return polished, None


def stream_generate_report(
    collected_data: dict[str, Any],
    product_info: ProductInfo,
    markdown_template: str | None = None,
) -> Iterator[str]:
    tpl = markdown_template or DEFAULT_MARKDOWN_TEMPLATE
    filled = fill_markdown_template(tpl, collected_data, product_info)
    user = build_report_user_payload(filled, product_info.as_context_text())
    yield from chat_completion_stream(REPORT_POLISH_SYSTEM, user, temperature=0.4)
