"""Streamlit 控制台冒烟测试。

Streamlit 把 streamlit_app.py 当「独立脚本」执行（无 __package__），
一旦脚本里用了相对导入（from .config import ...）就会直接 ImportError，
而页面本身仍会返回 HTTP 200 —— 只有真正跑一遍脚本才能发现。

这里用官方 AppTest 真正执行页面，捕获任何异常。
"""

from __future__ import annotations

from pathlib import Path

import pytest

APP = Path(__file__).resolve().parent.parent / "src" / "agent_orchestrator" / "streamlit_app.py"


def test_streamlit_app_runs_without_exception():
    """控制台脚本能被 Streamlit 正常执行（捕获 ImportError / 运行时异常）。"""
    pytest.importorskip("streamlit", reason="未安装 streamlit，跳过可视化后台冒烟")

    from streamlit.testing.v1 import AppTest

    at = AppTest.from_file(str(APP), default_timeout=60)
    at.run()

    if at.exception:
        msgs = "\n".join(str(e.message) + "\n" + str(e.stack_trace) for e in at.exception)
        pytest.fail("Streamlit 应用抛异常：\n" + msgs)


def test_streamlit_app_renders_title_and_tabs():
    """页面标题与页签正常渲染。"""
    pytest.importorskip("streamlit", reason="未安装 streamlit，跳过可视化后台冒烟")

    from streamlit.testing.v1 import AppTest

    at = AppTest.from_file(str(APP), default_timeout=60)
    at.run()

    if at.exception:
        pytest.fail("Streamlit 应用抛异常，无法渲染")

    assert at.title, "页面标题缺失"
    assert len(at.tabs) >= 1, "页签缺失"
