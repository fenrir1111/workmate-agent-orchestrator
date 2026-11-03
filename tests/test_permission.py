from agent_orchestrator.models import FlowDefinition, StepSpec, Tool
from agent_orchestrator.permission import flow_allowed, role_in, step_allowed, tool_allowed


def test_role_in_empty_is_any():
    assert role_in([], "anyone") is True


def test_role_in_match():
    assert role_in(["a", "b"], "a") is True
    assert role_in(["a", "b"], "c") is False


def test_flow_allowed():
    flow = FlowDefinition(id="f", allowed_roles=["finance"])
    assert flow_allowed(flow, "finance")[0] is True
    ok, reason = flow_allowed(flow, "viewer")
    assert ok is False and "白名单" in reason


def test_flow_empty_roles_allows_any():
    flow = FlowDefinition(id="f", allowed_roles=[])
    assert flow_allowed(flow, "whoever")[0] is True


def test_step_allowed():
    step = StepSpec(id="publish", allowed_roles=["admin"])
    assert step_allowed(step, "admin")[0] is True
    assert step_allowed(step, "analyst")[0] is False


def test_tool_allowed():
    tool = Tool(name="t", required_roles=["finance"])
    assert tool_allowed(tool, "finance")[0] is True
    assert tool_allowed(tool, "hr")[0] is False
    assert tool_allowed(None, "any")[0] is True
