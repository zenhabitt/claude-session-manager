"""
S.T.O.A. — 事件总线
轻量级发布/订阅模式，模块间解耦通信。
"""

class EventBus:
    def __init__(self):
        self._listeners: dict[str, list] = {}

    def on(self, event: str, callback):
        """订阅事件。callback 接收一个 data 参数（dict 或 None）。"""
        self._listeners.setdefault(event, []).append(callback)

    def off(self, event: str, callback):
        """取消订阅。"""
        lst = self._listeners.get(event)
        if lst:
            try:
                lst.remove(callback)
            except ValueError:
                pass

    def emit(self, event: str, data=None):
        """广播事件。单个订阅者的异常不影响其他订阅者。"""
        for cb in self._listeners.get(event, []):
            try:
                cb(data)
            except Exception:
                pass


# 模块级单例，跨模块共享
bus = EventBus()
