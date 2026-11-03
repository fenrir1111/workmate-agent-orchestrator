from agent_orchestrator.models import (
    STEP_SUCCEEDED,
    STEP_WAITING_APPROVAL,
    FlowDefinition,
    FlowRun,
    StepResult,
    StepSpec,
)


def test_flow_roundtrip():
    flow = FlowDefinition(
        id="f", name="n", version="0.2.0", allowed_roles=["a"], sla_ms=100,
        steps=[
            StepSpec(id="s1", name="x", tool="t", args={"k": "v"}, max_attempts=2,
                     timeout=1.5, requires_approval=True, allowed_roles=["a"],
                     condition={"prev": "s0", "field": "x", "op": "eq", "value": 1},
                     sla_ms=5)
        ],
    )
    flow2 = FlowDefinition.from_dict(flow.to_dict())
    assert flow2.id == "f"
    assert flow2.allowed_roles == ["a"]
    assert flow2.steps[0].args == {"k": "v"}
    assert flow2.steps[0].max_attempts == 2
    assert flow2.steps[0].requires_approval is True


def test_run_snapshot_roundtrip():
    run = FlowRun(run_id="r1", flow_id="f", role="a", inputs={"x": 1})
    run.add_result(StepResult(step_id="s1", status=STEP_SUCCEEDED,
                              output={"n": 2}, duration_ms=3))
    run2 = FlowRun.from_snapshot(run.to_snapshot())
    assert run2.role == "a"
    assert run2.inputs == {"x": 1}
    assert run2.results["s1"].output == {"n": 2}
    assert run2.result_order == ["s1"]


def test_waiting_step_id():
    run = FlowRun(run_id="r", flow_id="f", role="a")
    assert run.waiting_step_id is None
    run.add_result(StepResult(step_id="s1", status=STEP_WAITING_APPROVAL))
    assert run.waiting_step_id == "s1"
