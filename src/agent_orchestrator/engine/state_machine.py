"""流程运行状态机：只允许合法的状态流转。"""

from __future__ import annotations

from ..models import (
    ST_ABORTED,
    ST_FAILED,
    ST_PENDING,
    ST_RUNNING,
    ST_SUCCEEDED,
    ST_TIMEOUT,
    ST_WAITING_APPROVAL,
)

ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    ST_PENDING: {ST_RUNNING, ST_ABORTED, ST_SUCCEEDED},
    ST_RUNNING: {
        ST_RUNNING, ST_WAITING_APPROVAL, ST_SUCCEEDED,
        ST_FAILED, ST_TIMEOUT, ST_ABORTED,
    },
    ST_WAITING_APPROVAL: {ST_RUNNING, ST_ABORTED},
    ST_SUCCEEDED: set(),
    ST_FAILED: set(),
    ST_TIMEOUT: set(),
    ST_ABORTED: set(),
}


class InvalidTransition(Exception):
    pass


def assert_transition(src: str, dst: str) -> None:
    if dst not in ALLOWED_TRANSITIONS.get(src, set()):
        raise InvalidTransition(f"非法状态流转: {src} -> {dst}")


def transition(run, dst: str) -> None:
    """在 FlowRun 上执行一次带校验的状态流转。"""
    assert_transition(run.status, dst)
    run.status = dst
