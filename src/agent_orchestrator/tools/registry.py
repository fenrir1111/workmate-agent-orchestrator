"""工具注册中心。

真实落地时，把 SQL 工具、RAG 查询、HTTP 接口、消息通知等封装成
`Tool`（handler 为进程内函数或 HTTP 调用闭包）注册进来，
流程步骤通过 `tool` 名称路由到具体工具。见 examples/ 的适配器示例。
"""

from __future__ import annotations

from typing import Any, Callable, Optional

from ..models import Tool


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def register_handler(
        self,
        name: str,
        handler: Callable[[dict], Any],
        description: str = "",
        required_roles: Optional[list[str]] = None,
    ) -> None:
        self.register(
            Tool(name=name, handler=handler, description=description,
                 required_roles=required_roles or [])
        )

    def get(self, name: str) -> Tool:
        if name not in self._tools:
            raise KeyError(f"未注册的工具: {name}")
        return self._tools[name]

    def has(self, name: str) -> bool:
        return name in self._tools

    def names(self) -> list[str]:
        return list(self._tools.keys())

    def all(self) -> list[Tool]:
        return list(self._tools.values())
