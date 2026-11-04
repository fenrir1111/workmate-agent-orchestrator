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

def test_no_relative_imports_in_streamlit_app():
    """静态扫描：页面脚本任何位置都不允许相对导入（包括 if / 函数内的延迟导入）。

    Streamlit 以「独立脚本」执行本文件，无 __package__。顶层相对导入在启动时就炸，
    但藏在条件分支里的延迟导入更隐蔽——只有用户点到那个分支才炸，
    AppTest 初始渲染和 HTTP 200 健康检查都发现不了。
    """
    import ast

    tree = ast.parse(APP.read_text(encoding="utf-8"))
    bad = [
        "L{}: from {}{} import ...".format(n.lineno, "." * n.level, n.module or "")
        for n in ast.walk(tree)
        if isinstance(n, ast.ImportFrom) and n.level and n.level > 0
    ]
    assert not bad, (
        "streamlit_app.py 存在相对导入，Streamlit 独立脚本模式会 ImportError：\n"
        + "\n".join(bad)
    )


def test_primary_action_runs_without_exception():
    """点一次主按钮，覆盖初始渲染走不到的交互分支（防「首屏绿、一点就炸」）。"""
    pytest.importorskip("streamlit", reason="未安装 streamlit，跳过可视化后台冒烟")

    from streamlit.testing.v1 import AppTest

    at = AppTest.from_file(str(APP), default_timeout=60).run()
    assert at.button, "页面没有任何按钮，无法做交互冒烟"
    at.button[0].click().run()

    if at.exception:
        msgs = "\n".join(str(e.message) + "\n" + str(e.stack_trace) for e in at.exception)
        pytest.fail("点击主按钮后 Streamlit 应用抛异常：\n" + msgs)
