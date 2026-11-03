from agent_orchestrator.engine.orchestrator import Orchestrator
from agent_orchestrator.models import (
    ST_ABORTED,
    ST_SUCCEEDED,
    ST_WAITING_APPROVAL,
    STEP_SUCCEEDED,
    STEP_SKIPPED,
    FlowDefinition,
    StepSpec,
)


def test_run_waiting_then_approve(orch, invoice_flow):
    run = orch.run(invoice_flow, "finance", auto_approve=False)
    assert run.status == ST_WAITING_APPROVAL
    assert run.waiting_step_id == "approve"
    run2 = orch.approve(run.run_id, approver="lead")
    assert run2.status == ST_SUCCEEDED
    assert run2.results["approve"].status == STEP_SUCCEEDED


def test_auto_approve_completes(orch, invoice_flow):
    run = orch.run(invoice_flow, "finance", auto_approve=True)
    assert run.status == ST_SUCCEEDED
    assert run.results["approve"].status == STEP_SUCCEEDED


def test_small_amount_skips_approval(orch):
    flow = FlowDefinition(
        id="inv-small", allowed_roles=["finance"],
        steps=[
            StepSpec(id="ocr", tool="ocr_invoice", args={"file": "invoice_500.pdf"}),
            StepSpec(id="compliance", tool="check_compliance",
                     args={"amount": "{{steps.ocr.amount}}"}),
            StepSpec(id="approve", tool="noop", requires_approval=True,
                     condition={"prev": "compliance", "field": "approval_required",
                                "op": "eq", "value": True}),
            StepSpec(id="notify", tool="send_notification", args={"to": "x"}),
        ],
    )
    run = orch.run(flow, "finance")
    assert run.status == ST_SUCCEEDED
    assert run.results["approve"].status == STEP_SKIPPED


def test_flow_level_permission_abort(orch, invoice_flow):
    run = orch.run(invoice_flow, "viewer")
    assert run.status == ST_ABORTED
    assert "白名单" in run.error


def test_reject(orch, invoice_flow):
    run = orch.run(invoice_flow, "finance")
    assert run.status == ST_WAITING_APPROVAL
    run2 = orch.reject(run.run_id, reason="金额存疑")
    assert run2.status == ST_ABORTED
    assert run2.results["approve"].status == "ABORTED"


def test_snapshot_restore_and_resume(orch, invoice_flow):
    run = orch.run(invoice_flow, "finance")
    assert run.status == ST_WAITING_APPROVAL
    snap = orch.snapshot(run.run_id)
    # 模拟跨进程：全新编排器恢复
    orch2 = Orchestrator()
    restored = orch2.restore(snap, invoice_flow)
    assert restored.status == ST_WAITING_APPROVAL
    finished = orch2.approve(restored.run_id)
    assert finished.status == ST_SUCCEEDED


def test_export_plan_json(orch, invoice_flow):
    run = orch.run(invoice_flow, "finance")
    orch.approve(run.run_id)
    pkg = orch.export_plan(run.run_id)
    assert pkg["flow"]["id"] == "inv"
    assert pkg["run"]["status"] == ST_SUCCEEDED
    assert len(pkg["run"]["steps"]) == 4


def test_export_plan_markdown(orch, invoice_flow):
    run = orch.run(invoice_flow, "finance")
    orch.approve(run.run_id)
    md = orch.export_plan_markdown(run.run_id)
    assert "方案包" in md
    assert "人工审批节点" in md
