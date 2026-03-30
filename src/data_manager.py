from __future__ import annotations

from typing import Any

from src.models import SlotDefinition, SlotResult


def update_collected_data(
    collected_data: dict[str, Any],
    extracted_slots: list[SlotResult],
    current_slots: list[SlotDefinition],
) -> dict[str, Any]:
    """根据 allow_overwrite 与 slot type 更新归档。"""
    slot_map = {s.name: s for s in current_slots}
    out = dict(collected_data)

    for item in extracted_slots:
        if item.name not in slot_map:
            continue
        spec = slot_map[item.name]
        if item.confidence < 0.35:
            continue

        existing = out.get(item.name)
        if existing is not None and not spec.allow_overwrite:
            continue

        if spec.type == "multiple":
            prev = out.get(item.name)
            if prev is None:
                out[item.name] = [item.value]
            elif isinstance(prev, list):
                merged = list(prev)
                if item.value not in merged:
                    merged.append(item.value)
                out[item.name] = merged
            else:
                out[item.name] = [prev, item.value] if prev != item.value else [prev]
        else:
            out[item.name] = item.value

    return out


def stage_coverage_ratio(
    collected_data: dict[str, Any],
    current_slots: list[SlotDefinition],
) -> tuple[int, int]:
    """返回 (已满足 required 的数量, required 总数)。"""
    required = [s for s in current_slots if s.required]
    if not required:
        return (1, 1)
    ok = 0
    for s in required:
        v = collected_data.get(s.name)
        if v is None:
            continue
        if s.type == "multiple":
            if isinstance(v, list) and len(v) > 0:
                ok += 1
        else:
            if v != "" and v is not None:
                ok += 1
    return (ok, len(required))


def all_required_filled(
    collected_data: dict[str, Any],
    current_slots: list[SlotDefinition],
) -> bool:
    ok, total = stage_coverage_ratio(collected_data, current_slots)
    return ok >= total and total > 0


def first_missing_required_slot(
    collected_data: dict[str, Any],
    current_slots: list[SlotDefinition],
) -> str | None:
    for s in current_slots:
        if not s.required:
            continue
        v = collected_data.get(s.name)
        if s.type == "multiple":
            if not isinstance(v, list) or len(v) == 0:
                return s.name
        else:
            if v is None or v == "":
                return s.name
    return None
