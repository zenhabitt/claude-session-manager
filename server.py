#!/usr/bin/env python3
"""
S.T.O.A. — Session Timeline Organizer & Archiver
Modular architecture: stoacore → stoadata + stoaupdate → stoaweb → server
"""

import http.server
import json
import os
import socket
import sys
import threading
import webbrowser
import urllib.request
import datetime
from collections import Counter
from pathlib import Path

from stoacore.config import PORT, HOST, TRASH_DIR, CONFIG_DIR, CONFIG_FILE, VERSION, CLAUDE_PROJECTS_DIR, MIN_ROLLBACK_VERSION, SERVER_STARTED_AT, read_config, write_config
from stoacore.utils import parse_version, compare_versions, get_app_path, validate_download_url
from stoadata.session_store import SessionManager
from stoadata.monitor import monitor
import stoadata.sound_notifier  # 注册事件：busy→idle 提示音
from stoadata.sound_notifier import set_enabled as set_sound_enabled
from stoaweb.handler import RequestHandler


def main():
    """S.T.O.A. 主入口：启动 HTTP 服务器，自动打开浏览器。"""
    print()
    print("  ╔══════════════════════════════════╗")
    print("  ║   Claude Code Session Manager   ║")
    print("  ╚══════════════════════════════════╝")
    print()

    os.makedirs(TRASH_DIR, exist_ok=True)
    sessions = SessionManager.list_all()
    trash_count = len(SessionManager.list_trash())
    print(f"  Sessions: {len(sessions)}  |  Trash: {trash_count}")
    print()

    # Start session monitor (event-driven base)
    monitor.start()

    # Restore sound notifier state from config
    config = read_config()
    set_sound_enabled(config.get("sound_enabled", False))

    # Auto-check for updates in background
    def _auto_check_update():
        import stoaweb.handler as h
        config = read_config()
        if not config.get("auto_check_updates", True):
            return
        last_str = config.get("last_check_time")
        if last_str:
            try:
                last = datetime.datetime.strptime(last_str, "%Y-%m-%d %H:%M:%S")
                if (datetime.datetime.now() - last).days < 7:
                    return
            except (ValueError, TypeError):
                pass
        now = datetime.datetime.now()
        has_update = False
        latest_version = None
        dmg_url = None
        release_notes = ""
        error_msg = None
        from stoaupdate.github_api import github_api
        release, err = github_api("/releases/latest")
        if not err and release:
            latest_tag = release.get("tag_name", "")
            if latest_tag:
                cmp = compare_versions(latest_tag, VERSION)
                if cmp is not None and cmp > 0:
                    for asset in release.get("assets", []):
                        if asset.get("name", "").endswith(".dmg"):
                            dmg_url = asset.get("browser_download_url")
                            has_update = True
                            latest_version = latest_tag
                            release_notes = release.get("body", "")
                            break
        else:
            error_msg = err
        with RequestHandler._update_lock:
            h._update_check_cache = {
                "has_update": has_update,
                "current_version": VERSION,
                "latest_version": latest_version,
                "download_url": dmg_url,
                "release_notes": release_notes,
                "checked_at": now.strftime("%Y-%m-%d %H:%M:%S"),
                "error": error_msg,
            }
            config = read_config()
            if config.get("auto_check_updates", True):
                config["last_check_time"] = now.strftime("%Y-%m-%d %H:%M:%S")
                write_config(config)
    threading.Thread(target=_auto_check_update, daemon=True).start()

    http.server.HTTPServer.allow_reuse_address = True
    server = http.server.HTTPServer((HOST, PORT), RequestHandler)
    server.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
    url = f"http://localhost:{PORT}"

    if not os.environ.get("CSM_NO_BROWSER"):
        print(f"  ▼  Opening {url}")
        threading.Timer(0.3, lambda: webbrowser.open(url)).start()
    else:
        print(f"  Server ready at {url}")
    print(f"  Press Ctrl+C to stop\n")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  Shutting down…")
        server.shutdown()
        print("  Goodbye!\n")


if __name__ == "__main__":
    main()
