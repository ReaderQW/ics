from __future__ import annotations

import json
from pathlib import Path

from src.models import InterviewOutline, ProductInfo


def load_product_info(path: str | Path) -> ProductInfo:
    p = Path(path)
    with p.open(encoding="utf-8") as f:
        data = json.load(f)
    return ProductInfo.model_validate(data)


def load_interview_outline(path: str | Path) -> InterviewOutline:
    p = Path(path)
    with p.open(encoding="utf-8") as f:
        data = json.load(f)
    return InterviewOutline.model_validate(data)
