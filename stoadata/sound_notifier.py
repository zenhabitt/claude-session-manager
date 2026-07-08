"""
Play a system beep when a Claude Code session transitions from busy → idle.

Subscribes to the session monitor's event bus — completely decoupled from UI.
Plugin sessions (status="plugin") are naturally excluded since they never emit "busy".

Enabled/disabled in real-time via set_enabled() — no restart required.
"""

import subprocess
import threading

from stoacore.event_bus import bus

_enabled = False  # Start disabled — user turns on in settings


def set_enabled(flag: bool):
    """Enable or disable busy→idle alert sounds in real-time."""
    global _enabled
    _enabled = flag


def is_enabled():
    return _enabled


def _on_status_changed(data):
    if not _enabled:
        return
    if data and data.get("old") == "busy" and data.get("new") == "idle":
        threading.Thread(target=_beep, daemon=True).start()


def _beep():
    try:
        subprocess.run(
            ["afplay", "/System/Library/Sounds/Glass.aiff"],
            capture_output=True, timeout=3
        )
    except Exception:
        pass


bus.on("session:status_changed", _on_status_changed)
