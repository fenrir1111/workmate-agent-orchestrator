"""把 semantic-sql-guard 的 /ask 封装成一个可注册工具（Text2SQL 工具）。

用法：
    from sql_guard_adapter import make_sql_guard_tool
    reg.register(Tool(name="sql_guard", handler=make_sql_guard_tool(...)))

流程步骤：
    {"id": "q1", "name": "SQL查询", "tool": "sql_guard",
     "args": {"question": "一季度华东区域营收", "role": "finance"}}
"""

from __future__ import annotations

import json
import urllib.request
from typing import Any, Callable


def make_sql_guard_tool(
    base_url: str = "http://127.0.0.1:8000",
    timeout: float = 10.0,
) -> Callable[[dict], Any]:
    def handler(args: dict) -> Any:
        payload = {
            "question": args.get("question", ""),
            "role": args.get("role", "analyst"),
        }
        req = urllib.request.Request(
            base_url.rstrip("/") + "/ask",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))

    return handler


if __name__ == "__main__":
    from agent_orchestrator.models import Tool
    from agent_orchestrator.tools.registry import ToolRegistry

    reg = ToolRegistry()
    reg.register(Tool(name="sql_guard", handler=make_sql_guard_tool(),
                      description="语义SQL网关查询"))
    out = reg.get("sql_guard").invoke({"question": "一季度华东区域营收", "role": "finance"})
    print(out)
