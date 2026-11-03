"""核心领域模型：Tool / StepSpec / FlowDefinition / StepResult / FlowRun。

FlowRun 是**可快照、可恢复**的任务运行态，是状态机、审批、恢复、导出的载体。
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional


# ---------- 流程运行状态（FlowRun.status） ----------
ST_PENDING = "PENDING"
ST_RUNNING = "RUNNING"
ST_WAITING_APPROVAL = "WAITING_APPROVAL"
ST_SUCCEEDED = "SUCCEEDED"
ST_FAILED = "FAILED"
ST_TIMEOUT = "TIMEOUT"
ST_ABORTED = "ABORTED"

TERMINAL_STATUSES = {ST_SUCCEEDED, ST_FAILED, ST_TIMEOUT, ST_ABORTED}

# ---------- 步骤执行状态（StepResult.status） ----------
STEP_PENDING = "PENDING"
STEP_SUCCEEDED = "SUCCEEDED"
STEP_FAILED = "FAILED"
STEP_TIMEOUT = "TIMEOUT"
STEP_SKIPPED = "SKIPPED"
STEP_WAITING_APPROVAL = "WAITING_APPROVAL"
STEP_ABORTED = "ABORTED"


@dataclass
class Tool:
    """一个可被流程步骤调用的工具。

    - handler: (args: dict) -> Any，进程内函数（POC）或 HTTP 适配器（见 examples）。
    - required_roles: 工具级角色门槛（空 = 任意角色可调用）。
    """

    name: str
    description: str = ""
    handler: Optional[Callable[[dict], Any]] = None
    required_roles: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.handler is None:
            self.handler = self._default_handler

    def _default_handler(self, args: dict) -> Any:
        return {"ok": True, "tool": self.name, "args": args}

    def invoke(self, args: dict) -> Any:
        return self.handler(args)


@dataclass
class StepSpec:
    """流程中的一个节点定义。"""

    id: str
    name: str = ""
    tool: str = ""
    args: dict = field(default_factory=dict)
    max_attempts: int = 1          # 最大尝试次数（含首次）
    backoff: float = 0.0           # 重试间隔（秒，确定性）
    timeout: float = 5.0           # 单步超时（秒）
    requires_approval: bool = False  # 是否为人工审批节点（HITL）
    on_failure: str = "fail"       # fail | continue
    allowed_roles: list[str] = field(default_factory=list)  # 空 = 任意角色
    condition: dict = field(default_factory=dict)  # 前置条件门 {prev, field, op, value}
    sla_ms: int = 0                # 单步 SLA 目标（0 = 继承流级）

    def to_dict(self) -> dict:
        return {
            "id": self.id, "name": self.name, "tool": self.tool,
            "args": self.args, "max_attempts": self.max_attempts,
            "backoff": self.backoff, "timeout": self.timeout,
            "requires_approval": self.requires_approval,
            "on_failure": self.on_failure, "allowed_roles": self.allowed_roles,
            "condition": self.condition, "sla_ms": self.sla_ms,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "StepSpec":
        return cls(
            id=d["id"], name=d.get("name", ""), tool=d.get("tool", ""),
            args=dict(d.get("args", {})), max_attempts=d.get("max_attempts", 1),
            backoff=d.get("backoff", 0.0), timeout=d.get("timeout", 5.0),
            requires_approval=d.get("requires_approval", False),
            on_failure=d.get("on_failure", "fail"),
            allowed_roles=list(d.get("allowed_roles", [])),
            condition=dict(d.get("condition", {})), sla_ms=d.get("sla_ms", 0),
        )


@dataclass
class FlowDefinition:
    """一条数字员工流程（画布）定义。"""

    id: str
    name: str = ""
    version: str = "0.1.0"
    description: str = ""
    steps: list[StepSpec] = field(default_factory=list)
    allowed_roles: list[str] = field(default_factory=list)  # 流级角色白名单
    sla_ms: int = 0  # 流级 SLA 目标（毫秒，0 = 无）

    @property
    def step_ids(self) -> list[str]:
        return [s.id for s in self.steps]

    def step_map(self) -> dict[str, StepSpec]:
        return {s.id: s for s in self.steps}

    def to_dict(self) -> dict:
        return {
            "id": self.id, "name": self.name, "version": self.version,
            "description": self.description,
            "steps": [s.to_dict() for s in self.steps],
            "allowed_roles": self.allowed_roles, "sla_ms": self.sla_ms,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "FlowDefinition":
        return cls(
            id=d["id"], name=d.get("name", ""), version=d.get("version", "0.1.0"),
            description=d.get("description", ""),
            steps=[StepSpec.from_dict(s) for s in d.get("steps", [])],
            allowed_roles=list(d.get("allowed_roles", [])), sla_ms=d.get("sla_ms", 0),
        )


@dataclass
class StepResult:
    """单个节点的执行结果。"""

    step_id: str
    name: str = ""
    tool: str = ""
    status: str = STEP_PENDING
    attempts: int = 0
    duration_ms: int = 0
    output: Any = None
    error: str = ""
    skip_reason: str = ""

    def to_dict(self) -> dict:
        return {
            "step_id": self.step_id, "name": self.name, "tool": self.tool,
            "status": self.status, "attempts": self.attempts,
            "duration_ms": self.duration_ms, "output": self.output,
            "error": self.error, "skip_reason": self.skip_reason,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "StepResult":
        return cls(
            step_id=d["step_id"], name=d.get("name", ""), tool=d.get("tool", ""),
            status=d.get("status", STEP_PENDING), attempts=d.get("attempts", 0),
            duration_ms=d.get("duration_ms", 0), output=d.get("output"),
            error=d.get("error", ""), skip_reason=d.get("skip_reason", ""),
        )


@dataclass
class FlowRun:
    """一次流程运行的可恢复状态。"""

    run_id: str
    flow_id: str
    flow_version: str = ""
    role: str = ""
    inputs: dict = field(default_factory=dict)
    status: str = ST_PENDING
    current_index: int = 0
    results: dict[str, StepResult] = field(default_factory=dict)
    result_order: list[str] = field(default_factory=list)
    created_at: str = ""
    started_at: float = 0.0
    finished_at: float = 0.0
    total_duration_ms: int = 0
    error: str = ""
    _approved: set = field(default_factory=set)  # 内部：已审批通过的人工节点

    def __post_init__(self) -> None:
        if not self.created_at:
            self.created_at = time.strftime("%Y-%m-%d %H:%M:%S")

    def add_result(self, r: StepResult) -> None:
        if r.step_id not in self.results:
            self.result_order.append(r.step_id)
        self.results[r.step_id] = r

    @property
    def is_terminal(self) -> bool:
        return self.status in TERMINAL_STATUSES

    @property
    def waiting_step_id(self) -> Optional[str]:
        for sid in self.result_order:
            if self.results[sid].status == STEP_WAITING_APPROVAL:
                return sid
        return None

    def report(self) -> dict:
        """执行报告（执行日志视图）。"""
        return {
            "run_id": self.run_id, "flow_id": self.flow_id, "role": self.role,
            "status": self.status, "current_index": self.current_index,
            "total_duration_ms": self.total_duration_ms, "error": self.error,
            "steps": [self.results[sid].to_dict() for sid in self.result_order],
        }

    def to_snapshot(self) -> dict:
        """序列化为快照（可落盘 / 跨进程恢复，尤其用于 WAITING_APPROVAL 挂起）。"""
        return {
            "run_id": self.run_id, "flow_id": self.flow_id,
            "flow_version": self.flow_version, "role": self.role,
            "inputs": self.inputs, "status": self.status,
            "current_index": self.current_index,
            "results": {sid: self.results[sid].to_dict() for sid in self.result_order},
            "result_order": list(self.result_order),
            "created_at": self.created_at, "started_at": self.started_at,
            "finished_at": self.finished_at,
            "total_duration_ms": self.total_duration_ms, "error": self.error,
            "approved": sorted(self._approved),
        }

    @classmethod
    def from_snapshot(cls, d: dict) -> "FlowRun":
        run = cls(
            run_id=d["run_id"], flow_id=d["flow_id"],
            flow_version=d.get("flow_version", ""), role=d.get("role", ""),
            inputs=dict(d.get("inputs", {})), status=d.get("status", ST_PENDING),
            current_index=d.get("current_index", 0),
            created_at=d.get("created_at", ""), started_at=d.get("started_at", 0.0),
            finished_at=d.get("finished_at", 0.0),
            total_duration_ms=d.get("total_duration_ms", 0), error=d.get("error", ""),
        )
        run._approved = set(d.get("approved", []))
        run.result_order = list(d.get("result_order", []))
        for sid in run.result_order:
            run.results[sid] = StepResult.from_dict(d["results"][sid])
        return run
