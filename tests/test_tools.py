import pytest

from agent_orchestrator.tools.builtins import (
    _check_compliance,
    _classify_intent,
    _generate_report,
    _ocr_invoice,
    build_default_registry,
)


def test_ocr_amount_parse():
    out = _ocr_invoice({"file": "invoice_12500.00.pdf"})
    assert out["amount"] == 12500.0
    assert out["invoice_no"] == "INV-12500"


def test_check_compliance_thresholds():
    assert _check_compliance({"amount": 15000})["approval_required"] is True
    assert _check_compliance({"amount": 5000})["approval_required"] is True
    assert _check_compliance({"amount": 3000})["approval_required"] is False


def test_classify_intent():
    assert _classify_intent({"text": "发票报销"})["intent"] == "reimbursement"
    assert _classify_intent({"text": "资金流水" })["intent"] == "fund_audit"


def test_registry_register_and_missing():
    reg = build_default_registry()
    assert reg.has("query_db")
    assert reg.has("rag_gateway") is False
    with pytest.raises(KeyError):
        reg.get("nope")


def test_generate_report():
    out = _generate_report({"title": "月报", "sections": ["a", "b"]})
    assert "月报" in out["markdown"]
    assert out["char_count"] == len(out["markdown"])
