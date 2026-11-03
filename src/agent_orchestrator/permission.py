"""权限治理：流级 / 步骤级 / 工具级 三级角色白名单。

设计原则：白名单为空 = 任意角色放行；叠加不替代企业 IAM，
依赖外部身份源同步角色，本模块只负责"白名单判定"。
"""

from __future__ import annotations

from .models import FlowDefinition, StepSpec, Tool


def role_in(allowed: list[str], role: str) -> bool:
    """空白名单 = 任意角色；否则要求 role 命中。"""
    if not allowed:
        return True
    return role in allowed


def flow_allowed(flow: FlowDefinition, role: str) -> tuple[bool, str]:
    """流级白名单校验。"""
    if not role_in(flow.allowed_roles, role):
        return False, f"角色 {role} 不在流程白名单 {flow.allowed_roles}"
    return True, ""


def step_allowed(step: StepSpec, role: str) -> tuple[bool, str]:
    """步骤级白名单校验（每个节点可单独限权，如"仅 admin 可发布"）。"""
    if not role_in(step.allowed_roles, role):
        return False, f"角色 {role} 无权限执行步骤 {step.id}"
    return True, ""


def tool_allowed(tool: Tool | None, role: str) -> tuple[bool, str]:
    """工具级角色门槛（高危工具可要求特定角色才可调）。"""
    if tool is None:
        return True, ""
    if not role_in(tool.required_roles, role):
        return False, f"角色 {role} 无权限调用工具 {tool.name}"
    return True, ""
