"""内置工具（确定性、离线、零依赖）：用于 POC / 单测 / demo。

真实落地时把这些 handler 替换为真实实现（SQL 连接、RAG 检索、
HTTP 接口、消息通知），或用 examples/ 里的适配器封装 rag-gateway /
semantic-sql-guard 等其它底座服务。
"""

from __future__ import annotations

import time
from typing import Any

from .registry import ToolRegistry


# ---------- 业务工具（确定性模拟） ----------
def _classify_intent(args: dict) -> dict:
    text = args.get("text", "")
    if "发票" in text or "报销" in text:
        intent = "reimbursement"
    elif "巡检" in text or "安全" in text:
        intent = "safety_inspection"
    elif "资金" in text or "纪检" in text:
        intent = "fund_audit"
    else:
        intent = "general"
    return {"intent": intent, "confidence": 0.86}


def _ocr_invoice(args: dict) -> dict:
    """从文件名里解析金额（如 invoice_12500.00.pdf → 12500.0），确定性可测。"""
    file_name = str(args.get("file", ""))
    amount = 0.0
    for part in file_name.replace(".pdf", "").replace(".png", "").split("_"):
        try:
            amount = float(part)
            break
        except ValueError:
            continue
    if amount <= 0.0:
        amount = 1000.0
    return {
        "invoice_no": f"INV-{int(amount)}",
        "amount": amount,
        "fields": {"vendor": "示例供应商", "date": "2026-07-20"},
    }


def _check_compliance(args: dict) -> dict:
    amount = float(args.get("amount", 0.0))
    if amount > 10000:
        level, approval = "high", True
    elif amount > 3000:
        level, approval = "medium", True
    else:
        level, approval = "low", False
    return {"risk_level": level, "approval_required": approval, "amount": amount}


def _query_db(args: dict) -> dict:
    rows = [
        {"dept": "财务部", "budget_left": 520000},
        {"dept": "生产部", "budget_left": 130000},
    ]
    return {"row_count": len(rows), "rows": rows}


def _rag_search(args: dict) -> dict:
    return {
        "answer": "（示例）相关制度要点：需按流程审批后执行。",
        "sources": ["制度-001", "制度-003"],
        "hits": 2,
    }


def _generate_report(args: dict) -> dict:
    title = args.get("title", "报告")
    sections = args.get("sections", [])
    md = f"# {title}\n\n" + "\n".join(f"- {s}" for s in sections)
    return {"markdown": md, "char_count": len(md)}


def _send_notification(args: dict) -> dict:
    return {
        "sent": True,
        "channel": args.get("channel", "email"),
        "to": args.get("to", ""),
        "message_id": "msg-0001",
    }


def _llm_summarize(args: dict) -> dict:
    text = str(args.get("text", ""))
    return {"summary": f"（示例摘要）{text[:20]}…", "char_count": len(text)}


def _noop(args: dict) -> dict:
    """占位工具：常用于人工审批节点被批准后"落一个动作"。"""
    return {"approved": True, "note": args.get("summary", "")}


# ---------- 演示/测试专用 ----------
def _slow_tool(args: dict) -> dict:
    time.sleep(float(args.get("sleep", 0.0)))
    return {"ok": True}


def _flaky_tool(args: dict) -> dict:
    """前 fail_times 次抛异常、之后成功。用 key 隔离计数（单测请传不同 key）。"""
    fail_times = int(args.get("fail_times", 0))
    key = args.get("key", "default")
    if not hasattr(_flaky_tool, "_calls"):  # type: ignore[attr-defined]
        _flaky_tool._calls = {}  # type: ignore[attr-defined]
    calls = _flaky_tool._calls  # type: ignore[attr-defined]
    calls[key] = calls.get(key, 0) + 1
    if calls[key] <= fail_times:
        raise RuntimeError(f"模拟瞬时失败（第 {calls[key]} 次）")
    return {"ok": True, "call_no": calls[key]}


def reset_flaky() -> None:
    """清空抖动工具计数（单测隔离用）。"""
    if hasattr(_flaky_tool, "_calls"):  # type: ignore[attr-defined]
        _flaky_tool._calls.clear()  # type: ignore[attr-defined]


def build_default_registry() -> ToolRegistry:
    reg = ToolRegistry()
    reg.register_handler("classify_intent", _classify_intent, description="意图识别")
    reg.register_handler("ocr_invoice", _ocr_invoice, description="发票OCR识别（模拟）")
    reg.register_handler("check_compliance", _check_compliance, description="合规/审批阈值判断")
    reg.register_handler("query_db", _query_db, description="数据库查询（模拟）")
    reg.register_handler("rag_search", _rag_search, description="RAG检索（模拟）")
    reg.register_handler("generate_report", _generate_report, description="生成报告")
    reg.register_handler("send_notification", _send_notification, description="消息通知")
    reg.register_handler("llm_summarize", _llm_summarize, description="LLM摘要")
    reg.register_handler("noop", _noop, description="占位动作")
    reg.register_handler("slow_tool", _slow_tool, description="慢工具（超时演示）")
    reg.register_handler("flaky_tool", _flaky_tool, description="抖动工具（重试演示）")
    return reg
