"""步骤执行器：参数模板渲染 → 条件门 → 人工审批门 → 工具调用（重试/超时）→ 结果落盘。"""

from __future__ import annotations

import re
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
from dataclasses import dataclass
from typing import Any, Callable, Optional

from ..models import (
    FlowDefinition,
    FlowRun,
    ST_RUNNING,
    ST_SUCCEEDED,
    ST_WAITING_APPROVAL,
    STEP_FAILED,
    STEP_SUCCEEDED,
    STEP_SKIPPED,
    STEP_TIMEOUT,
    STEP_WAITING_APPROVAL,
    StepResult,
    StepSpec,
)
from ..permission import flow_allowed, step_allowed, tool_allowed
from .state_machine import transition

# 共享线程池：超时后不阻塞主流程（被超时的任务在后台自行结束）
_WORKER = ThreadPoolExecutor(max_workers=8, thread_name_prefix="orch-step")
_TEMPLATE = re.compile(r"\{\{([^}]+)\}\}")


def render_args(
    args: Any, run: FlowRun, flow: FlowDefinition
) -> Any:
    """把 `{{role}}` / `{{flow.id}}` / `{{inputs.x}}` / `{{steps.<id>}}` /
    `{{steps.<id>.<field>}}` 渲染为实际值。非字符串保持原样。"""

    def resolve(path: str) -> Any:
        path = path.strip()
        if path == "role":
            return run.role
        if path == "flow.id":
            return flow.id
        if path.startswith("inputs."):
            return run.inputs.get(path[len("inputs."):])
        if path.startswith("steps."):
            rest = path[len("steps."):]
            if "." in rest:
                step_id, field_name = rest.split(".", 1)
            else:
                step_id, field_name = rest, None
            res = run.results.get(step_id)
            if res is None:
                return None
            val = res.output
            if field_name is not None and isinstance(val, dict):
                return val.get(field_name)
            return val
        return path  # 未识别 → 原样保留

    def walk(node: Any) -> Any:
        if isinstance(node, dict):
            return {k: walk(v) for k, v in node.items()}
        if isinstance(node, list):
            return [walk(v) for v in node]
        if isinstance(node, str):
            return _TEMPLATE.sub(lambda m: str(resolve(m.group(1))), node)
        return node

    return walk(args)


def _num(x: Any) -> float:
    try:
        return float(x)
    except (TypeError, ValueError):
        return 0.0


def evaluate_condition(cond: dict, results: dict[str, StepResult]) -> bool:
    """简单条件门：{prev, field, op, value}。空条件恒真。

    op 支持 eq / ne / gt / lt / contains / exists / not_exists。
    """
    if not cond:
        return True
    prev_id = cond.get("prev")
    op = cond.get("op", "eq")
    expect = cond.get("value")
    field_name = cond.get("field")
    res = results.get(prev_id)
    val = res.output if res is not None else None
    if field_name is not None and isinstance(val, dict):
        val = val.get(field_name)
    if op == "exists":
        return val is not None
    if op == "not_exists":
        return val is None
    if op == "contains":
        return expect in (val if isinstance(val, (list, str, set)) else [])
    if op == "gt":
        return _num(val) > _num(expect)
    if op == "lt":
        return _num(val) < _num(expect)
    if op == "ne":
        return val != expect
    return val == expect  # eq


@dataclass
class _StepOutcome:
    result: StepResult
    pause: bool = False  # 是否需要暂停等待人工审批


class Executor:
    def __init__(self, flow: FlowDefinition, registry) -> None:
        self.flow = flow
        self.registry = registry

    # ---------- 入口 ----------
    def start(self, run: FlowRun) -> FlowRun:
        """校验流级权限并从头执行。"""
        ok, reason = flow_allowed(self.flow, run.role)
        if not ok:
            run.error = reason
            transition(run, "ABORTED")
            run.finished_at = time.time()
            return run
        run.started_at = time.time()
        return self.run_from(run)

    def run_from(self, run: FlowRun, index: Optional[int] = None) -> FlowRun:
        """从 index（默认 run.current_index）继续执行；遇到人工节点则暂停返回。"""
        if run.status != ST_RUNNING:
            transition(run, ST_RUNNING)
        run.current_index = run.current_index if index is None else index

        while run.current_index < len(self.flow.steps):
            step = self.flow.steps[run.current_index]
            outcome = self._execute_step(run, step)
            run.add_result(outcome.result)

            if outcome.pause:
                transition(run, ST_WAITING_APPROVAL)
                return run
            # 失败且 on_failure=fail → 流程失败
            if outcome.result.status in (STEP_FAILED, STEP_TIMEOUT) and step.on_failure == "fail":
                run.total_duration_ms = int((time.time() - run.started_at) * 1000)
                run.error = f"步骤 {step.id} 失败: {outcome.result.error}"
                transition(run, "FAILED")
                run.finished_at = time.time()
                return run

            run.current_index += 1

        run.total_duration_ms = int((time.time() - run.started_at) * 1000)
        transition(run, ST_SUCCEEDED)
        run.finished_at = time.time()
        return run

    # ---------- 单步 ----------
    def _call_with_timeout(self, handler: Callable, args: Any, timeout: float) -> Any:
        fut = _WORKER.submit(handler, args)
        return fut.result(timeout=timeout)

    def _execute_step(self, run: FlowRun, step: StepSpec) -> _StepOutcome:
        base = StepResult(step_id=step.id, name=step.name, tool=step.tool)

        # 1. 步骤级权限
        ok, reason = step_allowed(step, run.role)
        if not ok:
            base.status = STEP_SKIPPED
            base.skip_reason = reason
            return _StepOutcome(base)

        # 2. 条件门
        if not evaluate_condition(step.condition, run.results):
            base.status = STEP_SKIPPED
            base.skip_reason = "条件不满足"
            return _StepOutcome(base)

        # 3. 人工审批门（已审批过则不再暂停）
        if step.requires_approval and step.id not in run._approved:
            base.status = STEP_WAITING_APPROVAL
            return _StepOutcome(base, pause=True)

        # 4. 工具级权限
        tool = self.registry.get(step.tool)
        ok, reason = tool_allowed(tool, run.role)
        if not ok:
            base.status = STEP_FAILED
            base.error = reason
            return _StepOutcome(base)

        # 5. 执行：渲染参数 → 重试 → 超时
        rendered = render_args(step.args, run, self.flow)
        start = time.monotonic()
        status = STEP_FAILED
        last_error = ""
        output: Any = None
        for attempt in range(1, max(step.max_attempts, 1) + 1):
            base.attempts = attempt
            try:
                output = self._call_with_timeout(tool.invoke, rendered, step.timeout)
                status = STEP_SUCCEEDED
                break
            except FuturesTimeout:
                status = STEP_TIMEOUT
                last_error = f"超时（>{step.timeout}s）"
                break  # 超时不重试
            except Exception as e:  # noqa: BLE001
                status = STEP_FAILED
                last_error = f"{type(e).__name__}: {e}"
            if attempt < step.max_attempts and step.backoff > 0:
                time.sleep(step.backoff)

        base.status = status
        base.output = output
        base.error = "" if status == STEP_SUCCEEDED else last_error
        base.duration_ms = int((time.monotonic() - start) * 1000)
        return _StepOutcome(base)
