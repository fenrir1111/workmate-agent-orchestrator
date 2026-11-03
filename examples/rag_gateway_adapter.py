"""把 enterprise-rag-gateway 的 /query 封装成一个可注册工具。

用法：
    from agent_orchestrator.tools.registry import ToolRegistry
    from rag_gateway_adapter import make_rag_gateway_tool
    reg = build_default_registry()
    reg.register(make_rag_gateway_tool(base_url="http://127.0.0.1:8000"))

然后在流程步骤里用 `tool: "rag_gateway"`：
    {"id": "search", "name": "RAG检索", "tool": "rag_gateway",
     "args": {"question": "{{inputs.text}}", "tenant_id": "corp", "roles": ["hr"]}}
"""

from __future__ import annotations

import urllib.request
from typing import Any, Callable


def make_rag_gateway_tool(
    base_url: str = "http://127.0.0.1:8000",
    tenant_id: str = "corp",
    timeout: float = 10.0,
    name: str = "rag_gateway",
) -> Callable[[dict], Any]:
    """返回一个 (args: dict) -> dict 的闭包，供 ToolRegistry 注册。"""

    def handler(args: dict) -> Any:
        import json

        payload = {
            "question": args.get("question", ""),
            "user_id": args.get("user_id", "u-agent"),
            "tenant_id": args.get("tenant_id", tenant_id),
            "roles": args.get("roles", []),
            "org": args.get("org", ""),
        }
        req = urllib.request.Request(
            base_url.rstrip("/") + "/query",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))

    return handler


if __name__ == "__main__":
    # 简单自测：起一个 rag-gateway 后，直接调用
    from agent_orchestrator.models import Tool
    from agent_orchestrator.tools.registry import ToolRegistry

    reg = ToolRegistry()
    reg.register(Tool(name="rag_gateway", handler=make_rag_gateway_tool(),
                      description="企业RAG网关检索"))
    out = reg.get("rag_gateway").invoke(
        {"question": "涉密文件的借阅要求？", "roles": ["national"]}
    )
    print(out)
