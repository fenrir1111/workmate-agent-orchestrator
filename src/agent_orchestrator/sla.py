"""SLA 评估：流级 / 步骤级 目标耗时判定。"""

from __future__ import annotations


def evaluate_run_sla(flow_sla_ms: int, total_ms: int) -> dict:
    """流级 SLA：未设目标（<=0）时 met/breached 为 None。"""
    if flow_sla_ms <= 0:
        return {"sla_target_ms": 0, "met": None, "breached": None}
    met = total_ms <= flow_sla_ms
    return {"sla_target_ms": flow_sla_ms, "met": met, "breached": (not met)}


def evaluate_step_sla(step_sla_ms: int, duration_ms: int) -> dict:
    """步骤级 SLA：未设目标（<=0）时 met 为 None。"""
    if step_sla_ms <= 0:
        return {"sla_target_ms": 0, "met": None}
    return {"sla_target_ms": step_sla_ms, "met": duration_ms <= step_sla_ms}
