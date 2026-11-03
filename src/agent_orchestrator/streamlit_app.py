"""Streamlit 可视化后台：流程执行 / 流程画布 / 工具注册表 / 执行日志。

启动： uv run streamlit run src/agent_orchestrator/streamlit_app.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

# Streamlit 以「独立脚本」方式执行本文件（无 __package__），相对导入会直接 ImportError。
# 这里把 src/ 加入 sys.path 并改用绝对导入，保证「clone 即跑」和「已安装」两种场景都能启动。
_SRC = Path(__file__).resolve().parents[1]
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from agent_orchestrator.audit import AuditLogger  # noqa: E402
from agent_orchestrator.config import get_settings  # noqa: E402
from agent_orchestrator.engine.orchestrator import (  # noqa: E402
    Orchestrator,
    load_flows,
)


@st.cache_resource
def _orch():
    s = get_settings()
    o = Orchestrator(audit=AuditLogger(path=s.audit_log_path))
    o._flows = load_flows(s.flows_path)
    return o


st.set_page_config(page_title="数字员工编排", layout="wide")
o = _orch()
st.title("workmate-agent-orchestrator｜轻量企业数字员工编排平台")
st.caption(
    "可视化编排 · 工具注册 · 角色白名单 · 状态机 · 人工介入 · 审计 · SLA —— 可控、可审计、可人工接管"
)

ROLES = ["finance", "admin", "analyst", "viewer", "national", "hr", "prod"]
FLAG = {"SUCCEEDED": "✅", "FAILED": "❌", "TIMEOUT": "⏱",
        "SKIPPED": "⏭", "WAITING_APPROVAL": "⏸", "ABORTED": "⛔", "PENDING": "·"}

tab_run, tab_canvas, tab_tools, tab_log = st.tabs(
    ["① 流程执行", "② 流程画布", "③ 工具注册表", "④ 执行日志/审计"]
)

with tab_run:
    c1, c2, c3 = st.columns([2, 1, 1])
    with c1:
        flow_id = st.selectbox("流程", list(o._flows.keys()))
    with c2:
        role = st.selectbox("执行角色（白名单）", ROLES)
    with c3:
        auto = st.toggle("自动审批（跳过人工节点）", value=False)
    if st.button("执行", type="primary") and flow_id in o._flows:
        run = o.run(o._flows[flow_id], role, auto_approve=auto)
        st.session_state["last_run"] = run.run_id

    run_id = st.session_state.get("last_run")
    if run_id and run_id in o._runs:
        run = o._runs[run_id]
        if run.status == "WAITING_APPROVAL":
            st.warning("⏸ 停在人工审批节点：" + (run.waiting_step_id or "?"))
            b1, b2 = st.columns(2)
            if b1.button("✅ 审批通过"):
                o.approve(run_id, approver="ui")
                st.rerun()
            if b2.button("⛔ 驳回"):
                o.reject(run_id, reason="界面驳回")
                st.rerun()
        rows = [
            {"步骤": r.step_id, "名称": r.name,
             "状态": FLAG.get(r.status, r.status) + " " + r.status,
             "尝试": r.attempts, "耗时ms": r.duration_ms,
             "跳过/原因": r.skip_reason or r.error or ""}
            for r in (run.results[sid] for sid in run.result_order)
        ]
        st.dataframe(rows, hide_index=True)
        st.caption(f"状态 {run.status} · 总耗时 {run.total_duration_ms}ms"
                   f" · 执行 {run.current_index}/{len(o._flows[flow_id].steps)}")

with tab_canvas:
    for fid, flow in o._flows.items():
        st.markdown(f"### {flow.name}（{flow.id}）")
        st.caption(
            f"版本 {flow.version} · 角色白名单 {flow.allowed_roles or '任意'}"
            f" · SLA {flow.sla_ms}ms"
        )
        st.code(" → ".join(s.tool for s in flow.steps))
        for i, step in enumerate(flow.steps):
            tags = []
            if step.requires_approval:
                tags.append("人工审批")
            if step.allowed_roles:
                tags.append("角色:" + "/".join(step.allowed_roles))
            if step.condition:
                tags.append("条件门")
            if step.max_attempts > 1:
                tags.append(f"重试x{step.max_attempts}")
            if 0 < step.timeout < 5:
                tags.append(f"超时{step.timeout}s")
            tag_str = "　" + "·".join(tags) if tags else ""
            st.markdown(f"- **{i + 1}. {step.name}**（`{step.id}` → `{step.tool}`）{tag_str}")

with tab_tools:
    rows = [
        {"name": t.name, "description": t.description,
         "required_roles": "/".join(t.required_roles) or "任意"}
        for t in o.registry.all()
    ]
    st.dataframe(rows, hide_index=True)
    st.caption("真实落地时把 handler 替换为 SQL / RAG / HTTP / 通知实现（见 examples/）。")

with tab_log:
    st.dataframe(o.audit.recent(50), hide_index=True)
