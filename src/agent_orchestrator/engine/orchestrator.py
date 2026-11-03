"""编排门面：run / approve / reject / snapshot / restore / export-plan。

对外唯一入口。持有一个 ToolRegistry 与运行中任务表（run_id → FlowRun）。
"""

from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Optional

from ..audit import AuditLogger
from ..models import (
    ST_ABORTED,
    ST_PENDING,
    ST_WAITING_APPROVAL,
    STEP_ABORTED,
    FlowDefinition,
    FlowRun,
    StepResult,
)
from ..sla import evaluate_run_sla
from ..tools.builtins import build_default_registry
from ..tools.registry import ToolRegistry
from .executor import Executor
from .state_machine import transition

_STEP_FLAG = {
    "SUCCEEDED": "✅", "FAILED": "❌", "TIMEOUT": "⏱",
    "SKIPPED": "⏭", "WAITING_APPROVAL": "⏸", "ABORTED": "⛔", "PENDING": "·",
}


def load_flows(path: str) -> dict[str, FlowDefinition]:
    """从 JSON 加载流程定义（画布）。"""
    p = Path(path)
    if not p.exists():
        return {}
    data = json.loads(p.read_text(encoding="utf-8"))
    flows: dict[str, FlowDefinition] = {}
    for f in data.get("flows", []):
        flow = FlowDefinition.from_dict(f)
        flows[flow.id] = flow
    return flows


class Orchestrator:
    def __init__(
        self,
        registry: Optional[ToolRegistry] = None,
        audit: Optional[AuditLogger] = None,
    ) -> None:
        self.registry = registry or build_default_registry()
        self.audit = audit
        self._runs: dict[str, FlowRun] = {}
        self._flow_by_run: dict[str, FlowDefinition] = {}
        self._flows: dict[str, FlowDefinition] = {}

    # ---------- 查询 ----------
    def get_run(self, run_id: str) -> FlowRun:
        return self._runs[run_id]

    def list_tools(self) -> list[dict]:
        return [
            {"name": t.name, "description": t.description,
             "required_roles": t.required_roles}
            for t in self.registry.all()
        ]

    # ---------- 执行 ----------
    def run(
        self,
        flow: FlowDefinition,
        role: str,
        auto_approve: bool = False,
        inputs: Optional[dict] = None,
        run_id: Optional[str] = None,
    ) -> FlowRun:
        rid = run_id or f"run-{uuid.uuid4().hex[:10]}"
        run = FlowRun(
            run_id=rid, flow_id=flow.id, flow_version=flow.version,
            role=role, inputs=dict(inputs or {}), status=ST_PENDING,
        )
        self._runs[rid] = run
        self._flow_by_run[rid] = flow
        if auto_approve:
            run._approved = {s.id for s in flow.steps if s.requires_approval}
        executor = Executor(flow, self.registry)
        run = executor.start(run)
        self._audit(run, "finish" if run.is_terminal else "pause")
        return run

    def approve(self, run_id: str, approver: str = "") -> FlowRun:
        run = self._runs[run_id]
        flow = self._flow_by_run[run_id]
        if run.status != ST_WAITING_APPROVAL:
            raise ValueError(f"任务 {run_id} 非待审批状态（当前 {run.status}）")
        waiting = run.waiting_step_id
        if waiting is None:
            raise ValueError("未找到待审批节点")
        run._approved.add(waiting)
        if self.audit:
            self.audit.record(
                {"run_id": run_id, "kind": "approve", "step": waiting,
                 "approver": approver}
            )
        executor = Executor(flow, self.registry)
        run = executor.run_from(run, index=run.current_index)
        self._audit(run, "finish" if run.is_terminal else "pause")
        return run

    def reject(self, run_id: str, reason: str = "", approver: str = "") -> FlowRun:
        run = self._runs[run_id]
        waiting = run.waiting_step_id
        if waiting is None:
            raise ValueError("未找到待审批节点")
        run.add_result(
            StepResult(step_id=waiting, status=STEP_ABORTED,
                       error=reason or "已驳回")
        )
        run.total_duration_ms = int((time.time() - run.started_at) * 1000)
        run.error = reason or "已驳回"
        transition(run, ST_ABORTED)
        run.finished_at = time.time()
        if self.audit:
            self.audit.record(
                {"run_id": run_id, "kind": "reject", "step": waiting,
                 "approver": approver, "reason": reason}
            )
        self._audit(run, "finish")
        return run

    # ---------- 快照 / 恢复 ----------
    def snapshot(self, run_id: str) -> dict:
        return self._runs[run_id].to_snapshot()

    def restore(self, snapshot: dict, flow: FlowDefinition) -> FlowRun:
        run = FlowRun.from_snapshot(snapshot)
        self._runs[run.run_id] = run
        self._flow_by_run[run.run_id] = flow
        return run

    # ---------- 方案包导出 ----------
    def export_plan(self, run_id: str) -> dict:
        run = self._runs[run_id]
        flow = self._flow_by_run[run_id]
        sla = evaluate_run_sla(flow.sla_ms, run.total_duration_ms)
        return {
            "package_version": "0.1.0",
            "exported_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "flow": flow.to_dict(),
            "run": {
                "run_id": run.run_id, "role": run.role, "status": run.status,
                "total_duration_ms": run.total_duration_ms, "error": run.error,
                "sla": sla,
                "steps": [run.results[sid].to_dict() for sid in run.result_order],
            },
        }

    def export_plan_markdown(self, run_id: str) -> str:
        pkg = self.export_plan(run_id)
        f, r = pkg["flow"], pkg["run"]
        lines = [
            f"# Agent 方案包｜{f['name'] or f['id']}",
            "",
            f"- 版本：{f['version']}",
            f"- 导出时间：{pkg['exported_at']}",
            f"- 执行角色：{r['role']}",
            f"- 执行状态：{r['status']}",
            f"- 总耗时：{r['total_duration_ms']}ms",
        ]
        sla = r["sla"]
        if sla.get("met") is not None:
            lines.append(f"- SLA：{'达标' if sla['met'] else '超时'}（目标 {sla['sla_target_ms']}ms）")
        lines += ["", "## 流程步骤"]
        for s in r["steps"]:
            flag = _STEP_FLAG.get(s["status"], "·")
            line = f"- {flag} `{s['step_id']}` {s['name']}（{s['status']}，{s['duration_ms']}ms）"
            if s.get("skip_reason"):
                line += f"，{s['skip_reason']}"
            if s.get("error"):
                line += f"，{s['error']}"
            lines.append(line)
        lines += ["", "## 权限白名单"]
        lines.append(f"- 流程级角色白名单：{f['allowed_roles'] or '任意'}")
        for st in f["steps"]:
            if st.get("allowed_roles"):
                lines.append(f"- 步骤 {st['id']}：{st['allowed_roles']}")
            if st.get("requires_approval"):
                lines.append(f"- 步骤 {st['id']}：🔒 人工审批节点")
        lines.append("")
        return "\n".join(lines)

    # ---------- 审计 ----------
    def _audit(self, run: FlowRun, kind: str) -> None:
        if self.audit:
            self.audit.record(
                {"run_id": run.run_id, "flow_id": run.flow_id, "role": run.role,
                 "kind": kind, "status": run.status,
                 "total_duration_ms": run.total_duration_ms}
            )
