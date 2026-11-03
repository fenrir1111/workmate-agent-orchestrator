from agent_orchestrator.engine.executor import evaluate_condition, render_args
from agent_orchestrator.models import (
    ST_FAILED,
    STEP_SUCCEEDED,
    STEP_SKIPPED,
    STEP_TIMEOUT,
    FlowDefinition,
    FlowRun,
    StepResult,
    StepSpec,
)


def test_render_args_template(orch, invoice_flow):
    run = FlowRun(run_id="r", flow_id="inv", role="finance", inputs={"file": "a_5.pdf"})
    run.add_result(StepResult(step_id="ocr", status=STEP_SUCCEEDED, output={"amount": 5.0}))
    rendered = render_args(
        {"q": "{{steps.ocr.amount}}", "r": "{{role}}",
         "f": "{{flow.id}}", "i": "{{inputs.file}}"},
        run, invoice_flow,
    )
    assert rendered["q"] == "5.0"
    assert rendered["r"] == "finance"
    assert rendered["f"] == "inv"
    assert rendered["i"] == "a_5.pdf"


def test_evaluate_condition_ops():
    results = {"a": StepResult(step_id="a", status=STEP_SUCCEEDED, output={"x": 10})}
    assert evaluate_condition({"prev": "a", "field": "x", "op": "gt", "value": 5}, results)
    assert not evaluate_condition({"prev": "a", "field": "x", "op": "gt", "value": 15}, results)
    assert evaluate_condition({}, results) is True
    assert evaluate_condition({"prev": "missing", "field": "x", "op": "not_exists"}, results)
    assert evaluate_condition({"prev": "a", "field": "x", "op": "ne", "value": 10}, results) is False


def test_retry_succeeds(orch):
    flow = FlowDefinition(
        id="f", steps=[
            StepSpec(id="flaky", tool="flaky_tool",
                     args={"fail_times": 2, "key": "t1"},
                     max_attempts=3, backoff=0.01)
        ]
    )
    run = orch.run(flow, "admin")
    assert run.results["flaky"].status == STEP_SUCCEEDED
    assert run.results["flaky"].attempts == 3


def test_timeout(orch):
    flow = FlowDefinition(
        id="f", steps=[
            StepSpec(id="slow", tool="slow_tool", args={"sleep": 0.3},
                     timeout=0.05, on_failure="fail")
        ]
    )
    run = orch.run(flow, "admin")
    assert run.results["slow"].status == STEP_TIMEOUT
    assert run.status == ST_FAILED


def test_step_permission_skip(orch, report_flow):
    run = orch.run(report_flow, "analyst")
    assert run.results["publish"].status == STEP_SKIPPED
    assert "无权限" in run.results["publish"].skip_reason
    assert run.status == "SUCCEEDED"
