"""FastAPI 服务入口。

接口：
- POST /run          执行流程（带角色，可选 auto_approve / inputs）
- POST /approve      审批通过人工节点
- POST /reject       驳回人工节点
- POST /snapshot     导出任务快照
- POST /export-plan  导出 Agent 方案包（json / markdown）
- GET  /runs/{run_id}  任务状态
- GET  /runs/{run_id}/report  执行报告（执行日志）
- GET  /flows        流程列表
- GET  /tools        工具注册表
- GET  /health       健康检查
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from .audit import AuditLogger
from .config import get_settings
from .engine.orchestrator import Orchestrator, load_flows


class RunRequest(BaseModel):
    flow_id: str = Field(..., examples=["invoice-reimbursement"])
    role: str = Field("finance", description="执行角色（用于白名单）")
    auto_approve: bool = Field(False, description="自动审批（跳过人工节点）")
    inputs: dict = Field(default_factory=dict, description="运行时输入")


class ApproveRequest(BaseModel):
    run_id: str
    approver: str = ""


class RejectRequest(BaseModel):
    run_id: str
    reason: str = ""
    approver: str = ""


class SnapshotRequest(BaseModel):
    run_id: str


class ExportRequest(BaseModel):
    run_id: str
    fmt: str = Field("json", description="json | markdown")


def _default_orchestrator() -> Orchestrator:
    s = get_settings()
    orch = Orchestrator(audit=AuditLogger(path=s.audit_log_path))
    orch._flows = load_flows(s.flows_path)
    return orch


def build_app(orch: Optional[Orchestrator] = None) -> FastAPI:
    o = orch or _default_orchestrator()

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        yield

    app = FastAPI(
        title="workmate-agent-orchestrator",
        description="轻量企业数字员工编排平台｜工具路由·角色白名单·状态机·人工介入·审计·SLA·方案包",
        version="0.1.0",
        lifespan=lifespan,
    )

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok", "flows": len(o._flows), "tools": len(o.registry.names())}

    @app.get("/flows")
    def flows() -> list[dict]:
        return [
            {"id": f.id, "name": f.name, "version": f.version,
             "steps": f.step_ids, "allowed_roles": f.allowed_roles, "sla_ms": f.sla_ms}
            for f in o._flows.values()
        ]

    @app.get("/tools")
    def tools() -> list[dict]:
        return o.list_tools()

    @app.post("/run")
    def run(req: RunRequest) -> dict:
        flow = o._flows.get(req.flow_id)
        if flow is None:
            raise HTTPException(404, f"流程 {req.flow_id} 不存在")
        run = o.run(flow, req.role, auto_approve=req.auto_approve, inputs=req.inputs)
        return run.report()

    @app.post("/approve")
    def approve(req: ApproveRequest) -> dict:
        try:
            run = o.approve(req.run_id, approver=req.approver)
        except ValueError as e:
            raise HTTPException(409, str(e))
        return run.report()

    @app.post("/reject")
    def reject(req: RejectRequest) -> dict:
        try:
            run = o.reject(req.run_id, reason=req.reason, approver=req.approver)
        except ValueError as e:
            raise HTTPException(409, str(e))
        return run.report()

    @app.post("/snapshot")
    def snapshot(req: SnapshotRequest) -> dict:
        if req.run_id not in o._runs:
            raise HTTPException(404, "任务不存在")
        return o.snapshot(req.run_id)

    @app.post("/export-plan")
    def export_plan(req: ExportRequest) -> dict:
        if req.run_id not in o._runs:
            raise HTTPException(404, "任务不存在")
        if req.fmt == "markdown":
            return {"markdown": o.export_plan_markdown(req.run_id)}
        return o.export_plan(req.run_id)

    @app.get("/runs/{run_id}")
    def run_state(run_id: str) -> dict:
        run = o._runs.get(run_id)
        if run is None:
            raise HTTPException(404, "任务不存在")
        return {"run_id": run.run_id, "status": run.status,
                "current_index": run.current_index, "error": run.error}

    @app.get("/runs/{run_id}/report")
    def report(run_id: str) -> dict:
        run = o._runs.get(run_id)
        if run is None:
            raise HTTPException(404, "任务不存在")
        return run.report()

    return app


app = build_app()
