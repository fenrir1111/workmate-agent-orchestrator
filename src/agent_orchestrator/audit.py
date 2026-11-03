from __future__ import annotations

import json
import threading
import time
from collections import deque
from pathlib import Path


class AuditLogger:
    """任务审计：JSONL 落盘 + 内存环形缓冲。"""

    def __init__(self, path: str = "", max_buffer: int = 500) -> None:
        self.path = Path(path) if path else None
        self.max_buffer = max_buffer
        self._buf: deque = deque(maxlen=max_buffer)
        self._lock = threading.Lock()

    def record(self, event: dict) -> None:
        entry = {"ts": time.strftime("%Y-%m-%d %H:%M:%S"), **event}
        with self._lock:
            self._buf.appendleft(entry)
            if self.path is not None:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                with self.path.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def recent(self, limit: int = 50) -> list[dict]:
        with self._lock:
            return list(self._buf)[:limit]
