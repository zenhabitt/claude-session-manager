"""Session monitor — polls PID files and emits events on state changes."""

import time
import threading

from stoacore.event_bus import bus
from .session_store import SessionManager


class SessionMonitor:
    """后台线程：每 2 秒扫描 ~/.claude/sessions/*.json，检测状态变化并广播事件。"""

    def __init__(self, interval=2):
        self._bus = bus
        self._interval = interval
        self._last_status = {}  # {session_id: "busy"|"idle"|"plugin"}

    def start(self):
        """启动后台轮询线程（daemon，不阻塞主进程退出）。"""
        t = threading.Thread(target=self._loop, daemon=True)
        t.start()

    def _loop(self):
        while True:
            try:
                SessionManager._get_active_session_ids()  # 刷新 _session_data_cache
                data = SessionManager._session_data_cache
                current = {}
                for sid in data:
                    raw = data[sid].get("status")
                    current[sid] = raw if raw else "plugin"

                # 检测新增
                for sid, status in current.items():
                    if sid not in self._last_status:
                        self._bus.emit("session:appeared", {
                            "id": sid, "status": status, "data": data.get(sid, {})
                        })
                    elif status != self._last_status[sid]:
                        self._bus.emit("session:status_changed", {
                            "id": sid, "old": self._last_status[sid], "new": status
                        })

                # 检测消失
                for sid in list(self._last_status):
                    if sid not in current:
                        self._bus.emit("session:disappeared", {"id": sid})

                self._last_status = current
            except Exception as e:
                import sys
                print(f"[monitor] Polling error: {e}", file=sys.stderr)
                time.sleep(self._interval * 2)
                continue
            time.sleep(self._interval)


# 模块级单例
monitor = SessionMonitor()
