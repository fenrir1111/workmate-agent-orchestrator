"""全链路 demo：无需起服务，直接跑数字员工编排。

运行： uv run python -m agent_orchestrator.demo
覆盖：工具路由、角色白名单（流/步骤/工具三级）、状态机、失败重试、超时、
条件分支、人工介入（HITL）、执行日志、SLA、任务快照、方案包导出。
"""

from __future__ import annotations

from .audit import AuditLogger
from .config import get_settings
from .engine.orchestrator import Orchestrator, load_flows
from .models import FlowDefinition, StepSpec
from .sla import evaluate_run_sla
from .tools.builtins import reset_flaky


def _print_steps(run) -> None:
    for sid in run.result_order:
        r = run.results[sid]
        note = r.skip_reason or r.error
        print(f"   - {r.status:<16} {sid}  ({r.duration_ms}ms"
              f", attempts={r.attempts})" + (f"  {note}" if note else ""))


def main() -> None:
    s = get_settings()
    orch = Orchestrator(audit=AuditLogger(path=s.audit_log_path))
    flows = load_flows(s.flows_path)
    reset_flaky()
    print("=" * 72)
    print("workmate-agent-orchestrator 全链路 demo")
    print("=" * 72)
    print(f"已加载流程: {list(flows.keys())}")
    print(f"已注册工具: {orch.registry.names()}")

    # [1] 发票报销（finance，金额 15000 → 超阈值 → 停在人工审批）
    print("\n[1] 发票报销审批流（role=finance, 金额 15000 → 触发人工审批）")
    run = orch.run(flows["invoice-reimbursement"], "finance",
                   inputs={"file": "invoice_15000.00.pdf", "applicant": "zhangsan"})
    print(f"  状态: {run.status}  待审批节点: {run.waiting_step_id}")
    _print_steps(run)

    # [2] 审批通过 → 继续 → 完成
    print("\n[2] 审批通过 → 继续执行")
    run = orch.approve(run.run_id, approver="finance-lead")
    print(f"  状态: {run.status}  总耗时 {run.total_duration_ms}ms")
    _print_steps(run)
    sla = evaluate_run_sla(flows["invoice-reimbursement"].sla_ms, run.total_duration_ms)
    print(f"  SLA: {'达标' if sla['met'] else '超时'}（目标 {sla['sla_target_ms']}ms）")

    # [3] 小额发票（500 → 不触发审批 → 自动完成）
    print("\n[3] 小额发票（金额 500 → 条件门不满足 → 跳过审批 → 自动完成）")
    run2 = orch.run(flows["invoice-reimbursement"], "finance",
                    inputs={"file": "invoice_500.00.pdf", "applicant": "lisi"})
    print(f"  状态: {run2.status}")
    _print_steps(run2)

    # [4] 越权角色（viewer → 流级白名单拦截）
    print("\n[4] 越权角色（role=viewer, 不在流程白名单 [finance, admin]）")
    run3 = orch.run(flows["invoice-reimbursement"], "viewer",
                    inputs={"file": "invoice_100.pdf"})
    print(f"  状态: {run3.status}  原因: {run3.error}")

    # [5] 数据报表（analyst → publish 仅 admin → 步骤级跳过）
    print("\n[5] 数据报表流（role=analyst, publish 仅 admin → 步骤级权限跳过）")
    run4 = orch.run(flows["data-report"], "analyst",
                    inputs={"query": "q1", "title": "季度报表", "subscriber": "team"})
    _print_steps(run4)
    print(f"  状态: {run4.status}")

    # [6] 重试 + 超时（内联流程）
    print("\n[6] 重试 / 超时（内联演示）")
    reset_flaky()
    rf = FlowDefinition(
        id="demo-retry", name="重试演示",
        steps=[StepSpec(id="flaky", name="抖动调用", tool="flaky_tool",
                        args={"fail_times": 2, "key": "demo-1"},
                        max_attempts=3, backoff=0.01)])
    rr = orch.run(rf, "admin")
    r = rr.results["flaky"]
    print(f"  flaky(前2次失败,max_attempts=3): {r.status}  attempts={r.attempts}")

    rt = orch.run(
        FlowDefinition(id="demo-timeout", name="超时演示",
                       steps=[StepSpec(id="slow", name="慢调用", tool="slow_tool",
                                       args={"sleep": 0.5}, timeout=0.05,
                                       on_failure="fail")]),
        "admin")
    r2 = rt.results["slow"]
    print(f"  slow(sleep 0.5s, timeout 0.05s): {r2.status}  {r2.error}")

    # [7] 导出方案包
    print("\n[7] 导出 Agent 方案包（markdown）")
    print(orch.export_plan_markdown(run.run_id))

    print("-" * 72)
    print(f"审计记录 {len(orch.audit.recent(200))} 条 → {s.audit_log_path}")


if __name__ == "__main__":
    main()
