import sys
from pathlib import Path

# 保证无需安装也能导入 src 包（hatchling 安装后不影响）
SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import pytest

from agent_orchestrator.engine.orchestrator import Orchestrator
from agent_orchestrator.models import FlowDefinition, StepSpec
from agent_orchestrator.tools.builtins import build_default_registry, reset_flaky


@pytest.fixture(autouse=True)
def _clean_flaky():
    reset_flaky()
    yield


@pytest.fixture
def registry():
    return build_default_registry()


@pytest.fixture
def orch():
    """全新编排器（无共享状态，含默认工具）。"""
    return Orchestrator()


@pytest.fixture
def invoice_flow():
    return FlowDefinition(
        id="inv", name="发票报销", version="0.1.0",
        allowed_roles=["finance", "admin"],
        steps=[
            StepSpec(id="ocr", name="OCR", tool="ocr_invoice",
                     args={"file": "invoice_15000.00.pdf"}),
            StepSpec(id="compliance", name="合规", tool="check_compliance",
                     args={"amount": "{{steps.ocr.amount}}"}),
            StepSpec(id="approve", name="审批", tool="noop", requires_approval=True,
                     condition={"prev": "compliance", "field": "approval_required",
                                "op": "eq", "value": True}),
            StepSpec(id="notify", name="通知", tool="send_notification",
                     args={"to": "x"}),
        ])


@pytest.fixture
def report_flow():
    return FlowDefinition(
        id="rep", name="报表", allowed_roles=["analyst", "admin"],
        steps=[
            StepSpec(id="query", name="查询", tool="query_db"),
            StepSpec(id="publish", name="发布", tool="noop", allowed_roles=["admin"]),
        ])
