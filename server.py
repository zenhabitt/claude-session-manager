#!/usr/bin/env python3
"""
Claude Code Session Manager
Lightweight GUI for browsing, previewing, deleting, and restoring Claude Code sessions.
Zero dependencies — pure Python stdlib + browser frontend.

Features:
  - Browse & search all Claude Code sessions
  - Preview conversation content
  - Delete → Trash (recoverable)
  - Restore from trash or permanently delete
  - i18n: Simplified Chinese & English

Usage:
    python3 server.py
    # Opens http://localhost:8742 in your browser automatically
"""

import http.server
import json
import os
import webbrowser
import urllib.parse
import threading
import shutil
import time
import subprocess
from pathlib import Path

# ── Config ────────────────────────────────────────────────────────────

CLAUDE_PROJECTS_DIR = os.path.expanduser("~/.claude/projects")
TRASH_DIR = os.path.expanduser("~/.claude/session-manager/trash")
PORT = 8742
HOST = "127.0.0.1"


# ═══════════════════════════════════════════════════════════════════════
#  Session Data Layer
# ═══════════════════════════════════════════════════════════════════════

class SessionManager:

    _active_ids_cache = set()
    _active_ids_time = 0

    @staticmethod
    def _get_active_session_ids():
        """Find session IDs that have a running claude process.
        Returns (resumed_ids, has_bare_claude) tuple.
        """
        now = time.time()
        if now - SessionManager._active_ids_time < 1:
            return SessionManager._active_ids_cache  # cached

        ids = set()
        bare_count = 0
        try:
            result = subprocess.run(
                ["ps", "aux"], capture_output=True, text=True, timeout=3
            )
            import re
            for line in result.stdout.split("\n"):
                if "claude" not in line or "Session Manager" in line or "server.py" in line:
                    continue
                # Match: claude --resume <id> or claude -r <id>
                m = re.search(r"claude\s+(?:--resume|-r)\s+([a-f0-9-]{36})", line)
                if m:
                    ids.add(m.group(1))
                elif re.search(r"\bclaude\b", line) and "claude-code" not in line:
                    bare_count += 1
        except Exception:
            pass

        SessionManager._active_ids_cache = (ids, bare_count)
        SessionManager._active_ids_time = now
        return (ids, bare_count)

    @staticmethod
    def list_all():
        sessions = []
        projects_dir = Path(CLAUDE_PROJECTS_DIR)
        if not projects_dir.exists():
            return sessions

        for jsonl_file in projects_dir.glob("*/*.jsonl"):
            session_id = jsonl_file.stem
            project_dir = jsonl_file.parent.name if jsonl_file.parent != projects_dir else "(root)"
            project_name = SessionManager._decode_project(project_dir)

            info = SessionManager._parse_metadata(jsonl_file)
            info["id"] = session_id
            info["project"] = project_name
            info["filepath"] = str(jsonl_file)
            stat = jsonl_file.stat()
            info["size_bytes"] = stat.st_size
            info["size"] = SessionManager._format_size(stat.st_size)
            info["mtime"] = stat.st_mtime
            info["date"] = SessionManager._format_time(stat.st_mtime)
            # Active: only by running process (mtime unreliable — CC touches old files)
            resumed_ids, bare_count = SessionManager._get_active_session_ids()
            info["active"] = session_id in resumed_ids
            sessions.append(info)

        # Sort by mtime descending first
        sessions.sort(key=lambda s: -s["mtime"])

        # Each bare claude process (no explicit --resume <id>) matches the most-recent
        # non-resumed sessions, in order. E.g. 2 bare processes → top 2 non-resumed active.
        if bare_count > 0:
            for s in sessions:
                if s["active"] and s["id"] not in resumed_ids:
                    s["active"] = False
            n = 0
            for s in sessions:
                if s["id"] not in resumed_ids:
                    s["active"] = True
                    n += 1
                    if n >= bare_count:
                        break

        # Re-sort: active sessions first, then by mtime
        sessions.sort(key=lambda s: (not s["active"], -s["mtime"]))
        return sessions

    @staticmethod
    def _decode_project(dirname):
        if dirname == "(root)":
            return "~"
        home_prefix = f"Users-{os.environ.get('USER', 'zhanghaotian')}"
        if dirname.startswith(home_prefix):
            rest = dirname[len(home_prefix):]
            if rest.startswith("-"):
                rest = rest[1:]
            return ("~/" + rest) if rest else "~"
        return dirname.replace("-", "/")

    @staticmethod
    def _parse_metadata(filepath):
        ai_title = ""
        first_user_msg = ""
        msg_count = 0
        last_time = ""
        model = ""
        cwd = ""
        branch = ""
        total_tokens = 0
        turn_count = 0

        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                msg_count += 1
                try:
                    d = json.loads(line)
                except (json.JSONDecodeError, ValueError):
                    continue

                t = d.get("type", "")
                if t == "ai-title":
                    title = d.get("aiTitle", "")
                    if title:
                        ai_title = title
                elif t == "user" and not first_user_msg:
                    content = d.get("message", {}).get("content", "")
                    if isinstance(content, str):
                        clean = content.strip()
                        if clean and not clean.startswith("<"):
                            first_user_msg = clean[:120]
                    elif isinstance(content, list):
                        for item in content:
                            if isinstance(item, dict) and item.get("type") == "text":
                                first_user_msg = item["text"][:120]
                                break
                elif t == "assistant":
                    m = d.get("message", {})
                    model = m.get("model", model)
                    usage = m.get("usage", {})
                    total_tokens += usage.get("input_tokens", 0) + usage.get("output_tokens", 0)
                elif t == "system" and d.get("subtype") == "turn_duration":
                    turn_count += 1

                ts = d.get("timestamp", "")
                if ts:
                    last_time = ts
                cwd = d.get("cwd", cwd) or cwd
                branch = d.get("gitBranch", branch) or branch

        title = ai_title or first_user_msg or "(empty conversation)"
        if len(title) > 80:
            title = title[:77] + "..."

        return {
            "title": title,
            "messages": msg_count,
            "turns": turn_count,
            "tokens": total_tokens,
            "last_time": last_time[:19] if last_time else "",
            "model": model,
            "cwd": cwd,
            "branch": branch,
        }

    @staticmethod
    def get_preview(filepath, max_messages=40):
        """Return structured conversation preview with typed content parts."""
        messages = []
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    d = json.loads(line)
                except (json.JSONDecodeError, ValueError):
                    continue

                t = d.get("type", "")
                role = None
                parts = []

                if t == "user":
                    c = d.get("message", {}).get("content", "")
                    if isinstance(c, str):
                        if c.strip().startswith("<"):
                            continue
                        parts = [{"type": "text", "content": c.strip()[:500]}]
                    elif isinstance(c, list):
                        for item in c:
                            if isinstance(item, dict):
                                if item.get("type") == "text":
                                    parts.append({"type": "text", "content": item["text"][:500]})
                                elif item.get("type") == "tool_result":
                                    result_text = str(item.get("content", ""))
                                    is_error = item.get("is_error", False)
                                    parts.append({
                                        "type": "tool_result",
                                        "content": result_text[:500],
                                        "is_error": is_error
                                    })
                    if parts:
                        role = "user"

                elif t == "assistant":
                    raw_parts = d.get("message", {}).get("content", [])
                    for part in raw_parts:
                        if not isinstance(part, dict):
                            continue
                        pt = part.get("type", "")
                        if pt == "text":
                            parts.append({"type": "text", "content": part["text"]})
                        elif pt == "thinking":
                            parts.append({"type": "thinking", "content": part.get("thinking", "")[:300]})
                        elif pt == "tool_use":
                            inp = part.get("input", {})
                            # Simplify tool input for display
                            inp_simple = {}
                            for k, v in inp.items():
                                if isinstance(v, str) and len(v) > 200:
                                    inp_simple[k] = v[:197] + "..."
                                else:
                                    inp_simple[k] = v
                            parts.append({
                                "type": "tool_use",
                                "name": part.get("name", "?"),
                                "input": json.dumps(inp_simple, ensure_ascii=False, indent=2)
                            })
                    if parts:
                        role = "assistant"

                elif t == "ai-title":
                    parts = [{"type": "title", "content": d.get("aiTitle", "")}]
                    role = "title"

                if role and parts:
                    messages.append({"role": role, "parts": parts})

                if len(messages) >= max_messages * 2:
                    break
        return messages

    # ── Trash Operations ──────────────────────────────────────────

    @staticmethod
    def move_to_trash(filepath):
        """Move a session to trash with metadata for recovery."""
        path = Path(filepath)
        if not path.exists():
            return False, "File not found"

        session_id = path.stem
        trash_path = Path(TRASH_DIR) / session_id
        trash_path.mkdir(parents=True, exist_ok=True)

        # Read metadata before moving
        meta = SessionManager._parse_metadata(path)

        # Save metadata about original location
        trash_meta = {
            "id": session_id,
            "title": meta["title"],
            "original_path": str(path),
            "original_parent": str(path.parent),
            "messages": meta["messages"],
            "size": SessionManager._format_size(path.stat().st_size),
            "size_bytes": path.stat().st_size,
            "date": SessionManager._format_time(path.stat().st_mtime),
            "deleted_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "deleted_ts": time.time(),
        }

        # Move jsonl to trash
        try:
            shutil.move(str(path), str(trash_path / f"{session_id}.jsonl"))
        except OSError as e:
            return False, f"Move failed: {e}"

        # Move subagent dir if exists
        subagent_dir = path.parent / session_id
        if subagent_dir.exists() and subagent_dir.is_dir():
            try:
                shutil.move(str(subagent_dir), str(trash_path / session_id))
            except OSError:
                pass  # non-critical

        # Write metadata
        meta_file = trash_path / "metadata.json"
        with open(meta_file, "w") as f:
            json.dump(trash_meta, f, ensure_ascii=False)

        return True, "Moved to trash"

    @staticmethod
    def list_trash():
        """List all sessions in trash."""
        items = []
        trash = Path(TRASH_DIR)
        if not trash.exists():
            return items

        for entry in sorted(trash.iterdir(), reverse=True):
            if not entry.is_dir():
                continue
            meta_file = entry / "metadata.json"
            if meta_file.exists():
                try:
                    with open(meta_file) as f:
                        meta = json.load(f)
                    items.append(meta)
                except (json.JSONDecodeError, OSError):
                    pass
        items.sort(key=lambda x: x.get("deleted_ts", 0), reverse=True)
        return items

    @staticmethod
    def restore_from_trash(session_id):
        """Restore a session from trash to its original location."""
        trash_path = Path(TRASH_DIR) / session_id
        meta_file = trash_path / "metadata.json"

        if not meta_file.exists():
            return False, "Trash metadata not found"

        try:
            with open(meta_file) as f:
                meta = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            return False, f"Metadata read error: {e}"

        original_dir = Path(meta["original_parent"])
        jsonl_src = trash_path / f"{session_id}.jsonl"
        jsonl_dst = original_dir / f"{session_id}.jsonl"
        subagent_src = trash_path / session_id
        subagent_dst = original_dir / session_id

        if not jsonl_src.exists():
            return False, "Trash JSONL file missing"

        # Ensure original directory exists
        original_dir.mkdir(parents=True, exist_ok=True)

        errors = []
        try:
            shutil.move(str(jsonl_src), str(jsonl_dst))
        except OSError as e:
            errors.append(f"jsonl: {e}")

        if subagent_src.exists():
            try:
                if subagent_dst.exists():
                    shutil.rmtree(subagent_dst)
                shutil.move(str(subagent_src), str(subagent_dst))
            except OSError as e:
                errors.append(f"subagent: {e}")

        if errors:
            return False, "; ".join(errors)

        # Clean up trash directory
        try:
            shutil.rmtree(trash_path)
        except OSError:
            pass

        return True, "Restored"

    @staticmethod
    def delete_permanently(session_id):
        """Permanently delete a session from trash."""
        trash_path = Path(TRASH_DIR) / session_id
        if not trash_path.exists():
            return False, "Not found in trash"

        try:
            shutil.rmtree(trash_path)
            return True, "Permanently deleted"
        except OSError as e:
            return False, str(e)

    @staticmethod
    def _format_size(size_bytes):
        if size_bytes < 1024:
            return f"{size_bytes}B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes/1024:.0f}K"
        elif size_bytes < 1024 * 1024 * 1024:
            return f"{size_bytes/(1024*1024):.1f}M"
        return f"{size_bytes/(1024*1024*1024):.1f}G"

    @staticmethod
    def _format_time(ts):
        import datetime
        dt = datetime.datetime.fromtimestamp(ts)
        now = datetime.datetime.now()
        diff = now - dt
        if diff.days == 0:
            return f"Today {dt.strftime('%H:%M')}"
        elif diff.days == 1:
            return f"Yesterday {dt.strftime('%H:%M')}"
        elif diff.days < 7:
            return f"{diff.days}d ago {dt.strftime('%H:%M')}"
        return dt.strftime("%Y-%m-%d %H:%M")


# ═══════════════════════════════════════════════════════════════════════
#  Frontend — i18n strings
# ═══════════════════════════════════════════════════════════════════════

I18N = {
    "zh": {
        "appTitle": "Claude 会话管理器",
        "sessions": "个会话",
        "searchPlaceholder": "搜索会话...",
        "sortTime": "时间",
        "sortSize": "大小",
        "sortMessages": "消息数",
        "allSessions": "所有会话",
        "runningSessions": "运行中",
        "listTab": "会话列表",
        "trashTab": "回收站",
        "trashEmpty": "回收站是空的",
        "selectHint": "点击左侧会话查看详情",
        "delete": "删除",
        "stop": "停止",
        "stopConfirmTitle": "确认停止",
        "stopConfirmMsg": "这会终止该会话正在运行的 Claude 进程。<br>会话文件不会被删除，你稍后可以继续对话。",
        "confirmStopBtn": "停止进程",
        "stopped": "已终止进程",
        "restore": "恢复",
        "permDelete": "彻底删除",
        "cancel": "取消",
        "confirm": "确认",
        "deleteConfirmTitle": "确认删除",
        "deleteConfirmMsg": "此操作会将会话移入回收站。你可以稍后在回收站中恢复或彻底删除。",
        "permDeleteConfirmTitle": "彻底删除",
        "permDeleteConfirmMsg": "此操作不可撤销！会话文件将被永久删除，无法恢复。",
        "restoreConfirmTitle": "恢复会话",
        "restoreConfirmMsg": "将会话恢复到原始位置。",
        "sessionId": "会话 ID",
        "project": "项目",
        "branch": "分支",
        "model": "模型",
        "messages": "消息数",
        "turns": "轮次",
        "tokens": "Token 数",
        "lastActive": "最后活动",
        "size": "大小",
        "deletedAt": "删除时间",
        "loading": "加载中...",
        "noMessages": "没有找到消息",
        "loadFailed": "加载预览失败",
        "deleted": "已删除",
        "deleted1": "已删除",
        "restored": "已恢复",
        "permDeleted": "已彻底删除",
        "confirmDeleteBtn": "确认删除",
        "confirmRestoreBtn": "确认恢复",
        "confirmPermDeleteBtn": "确认彻底删除",
        "language": "En",
        "batchBar": "已选择",
        "batchDelete": "批量删除",
        "refresh": "刷新",
        "newChat": "新对话",
        "newChatStarted": "已在新终端中打开",
        "resume": "继续对话",
        "resumed": "已在新终端中打开",
    },
    "en": {
        "appTitle": "Claude Session Manager",
        "sessions": "sessions",
        "searchPlaceholder": "Search sessions...",
        "sortTime": "Time",
        "sortSize": "Size",
        "sortMessages": "Messages",
        "allSessions": "All Sessions",
        "runningSessions": "Running",
        "listTab": "Sessions",
        "trashTab": "Trash",
        "trashEmpty": "Trash is empty",
        "selectHint": "Select a session to view details",
        "delete": "Delete",
        "stop": "Stop",
        "stopConfirmTitle": "Stop Session",
        "stopConfirmMsg": "This will terminate the running Claude process.<br>The session file will NOT be deleted — you can resume it later.",
        "confirmStopBtn": "Stop Process",
        "stopped": "Process terminated",
        "restore": "Restore",
        "permDelete": "Delete Forever",
        "cancel": "Cancel",
        "confirm": "Confirm",
        "deleteConfirmTitle": "Confirm Delete",
        "deleteConfirmMsg": "This will move the session to trash. You can restore it or permanently delete it later from the trash.",
        "permDeleteConfirmTitle": "Delete Forever",
        "permDeleteConfirmMsg": "This action is irreversible! The session file will be permanently deleted and cannot be recovered.",
        "restoreConfirmTitle": "Restore Session",
        "restoreConfirmMsg": "Restore this session to its original location.",
        "sessionId": "Session ID",
        "project": "Project",
        "branch": "Branch",
        "model": "Model",
        "messages": "Messages",
        "turns": "turns",
        "tokens": "Tokens",
        "lastActive": "Last active",
        "size": "Size",
        "deletedAt": "Deleted at",
        "loading": "Loading...",
        "noMessages": "No messages found",
        "loadFailed": "Failed to load preview",
        "deleted": "Deleted",
        "deleted1": "Deleted",
        "restored": "Restored",
        "permDeleted": "Permanently deleted",
        "confirmDeleteBtn": "Move to Trash",
        "confirmRestoreBtn": "Restore",
        "confirmPermDeleteBtn": "Delete Forever",
        "language": "中文",
        "batchBar": "selected",
        "batchDelete": "Delete selected",
        "refresh": "Refresh",
        "newChat": "New Chat",
        "newChatStarted": "Opened in new terminal",
        "resume": "Continue",
        "resumed": "Opened in new terminal",
    },
}


# ═══════════════════════════════════════════════════════════════════════
#  Frontend (HTML/CSS/JS)
# ═══════════════════════════════════════════════════════════════════════

FRONTEND = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Claude Session Manager</title>
<style>
  :root {
    --bg: #1a1b1e; --surface: #25262b; --surface2: #2c2e33; --border: #373a40;
    --text: #c1c2c5; --text-dim: #909296; --text-bright: #e0e0e0;
    --accent: #6c8aff; --accent-hover: #8ba3ff;
    --danger: #ff6b6b; --danger-hover: #ff8787; --danger-bg: rgba(255,107,107,0.08);
    --success: #69db7c; --warn: #ffd43b;
    --radius: 8px;
    --font: -apple-system, BlinkMacSystemFont, "SF Pro Text", "Segoe UI", sans-serif;
    --mono: "SF Mono", "Fira Code", "JetBrains Mono", monospace;
  }
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body {
    font-family: var(--font); background: var(--bg); color: var(--text);
    height: 100vh; display: flex; flex-direction: column; overflow: hidden;
  }

  /* ── Header ── */
  header {
    background: var(--surface); border-bottom: 1px solid var(--border);
    padding: 0 20px; height: 48px; display: flex; align-items: center;
    justify-content: space-between; flex-shrink: 0; user-select: none;
  }
  header h1 { font-size: 14px; font-weight: 600; color: var(--text-bright); }
  .header-right { display: flex; align-items: center; gap: 16px; }
  .header-stats { font-size: 12px; color: var(--text-dim); }
  .header-stats span { color: var(--accent); font-weight: 600; }
  .lang-btn {
    font-size: 11px; padding: 3px 10px; border: 1px solid var(--border);
    border-radius: 4px; background: transparent; color: var(--text-dim);
    cursor: pointer; font-family: var(--font); transition: all .15s;
  }
  .lang-btn:hover { color: var(--text); border-color: var(--text-dim); }
  .lang-btn:active { background: var(--accent); color: #fff; border-color: var(--accent); }

  /* ── Main Layout ── */
  .main { display: flex; flex: 1; overflow: hidden; }

  /* ── Left Panel ── */
  .panel-left {
    width: 390px; min-width: 310px; border-right: 1px solid var(--border);
    display: flex; flex-direction: column; background: var(--surface);
  }
  .search-bar { padding: 12px; flex-shrink: 0; }
  .search-bar input {
    width: 100%; padding: 8px 12px; border: 1px solid var(--border);
    border-radius: 6px; background: var(--bg); color: var(--text);
    font-size: 13px; font-family: var(--font); outline: none; transition: border-color .15s;
  }
  .search-bar input:focus { border-color: var(--accent); }
  .search-bar input::placeholder { color: var(--text-dim); }

  .tab-bar {
    display: flex; padding: 0 12px 8px; gap: 2px; flex-shrink: 0;
  }
  .tab-bar button {
    flex: 1; padding: 6px 0; border: none; border-bottom: 2px solid transparent;
    background: transparent; color: var(--text-dim); font-size: 12px;
    font-family: var(--font); cursor: pointer; transition: all .15s;
  }
  .tab-bar button:hover { color: var(--text); }
  .tab-bar button.active {
    color: var(--accent); border-bottom-color: var(--accent);
  }
  .tab-bar .badge {
    background: var(--danger-bg); color: var(--danger);
    font-size: 10px; padding: 1px 6px; border-radius: 8px; margin-left: 4px;
  }

  .sort-bar {
    display: flex; gap: 4px; padding: 0 12px 8px; flex-shrink: 0;
  }
  .sort-bar button {
    padding: 4px 10px; border: 1px solid var(--border); border-radius: 4px;
    background: transparent; color: var(--text-dim); font-size: 11px;
    cursor: pointer; font-family: var(--font); transition: all .15s;
  }
  .sort-bar button:hover { color: var(--text); border-color: var(--text-dim); }
  .sort-bar button.active { background: var(--accent); border-color: var(--accent); color: #fff; }

  .session-list { flex: 1; overflow-y: auto; padding: 0 8px 8px; }
  .section-header {
    font-size: 10px; font-weight: 600; text-transform: uppercase;
    letter-spacing: 0.8px; color: var(--success); padding: 8px 12px 4px;
    user-select: none;
  }
  .section-divider {
    border-top: 1px solid var(--border); margin: 6px 12px 10px;
  }
  .session-list::-webkit-scrollbar { width: 5px; }
  .session-list::-webkit-scrollbar-thumb { background: var(--border); border-radius: 3px; }

  .session-card {
    padding: 10px 12px; margin-bottom: 2px; border-radius: 6px;
    cursor: pointer; transition: background .12s; border: 1px solid transparent;
    position: relative;
  }
  .session-card:hover { background: var(--surface2); }
  .session-card.selected { background: var(--surface2); border-color: var(--accent); }
  .session-card.active {
    border-color: rgba(105,219,124,0.25);
    animation: breathe 2.5s ease-in-out infinite;
  }
  @keyframes breathe {
    0%, 100% { box-shadow: 0 0 0 rgba(105,219,124,0); }
    50% { box-shadow: 0 0 8px rgba(105,219,124,0.15); }
  }
  .session-card .active-dot {
    display: inline-block; width: 6px; height: 6px; border-radius: 50%;
    background: var(--success); margin-right: 4px; vertical-align: middle;
    animation: breathe-dot 1.5s ease-in-out infinite;
  }
  @keyframes breathe-dot {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.3; }
  }
  .session-card .title {
    font-size: 13px; font-weight: 500; color: var(--text-bright);
    margin-bottom: 3px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
    padding-right: 60px;
  }
  .session-card .meta {
    font-size: 11px; color: var(--text-dim); display: flex; gap: 10px; flex-wrap: wrap;
  }
  .session-card .project-tag {
    font-size: 10px; background: rgba(108,138,255,0.12); color: var(--accent);
    padding: 1px 6px; border-radius: 3px; max-width: 180px;
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  }
  .session-card .card-actions {
    position: absolute; right: 6px; top: 50%; transform: translateY(-50%);
    display: none; gap: 4px;
  }
  .session-card:hover .card-actions { display: flex; }
  .card-btn {
    display: flex; align-items: center; gap: 3px;
    padding: 3px 7px; border: 1px solid var(--border); border-radius: 4px;
    background: var(--surface); color: var(--text-dim); font-size: 11px;
    cursor: pointer; font-family: var(--font); transition: all .12s; white-space: nowrap;
  }
  .card-btn:hover { color: var(--text); border-color: var(--text-dim); }
  .card-btn.danger { background: var(--danger-bg); color: var(--danger); border-color: transparent; }
  .card-btn.danger:hover { background: var(--danger); color: #fff; border-color: var(--danger); }
  .card-btn.restore:hover { background: rgba(105,219,124,0.08); color: var(--success); border-color: var(--success); }

  /* ── Right Panel ── */
  .panel-right {
    flex: 1; display: flex; flex-direction: column; background: var(--bg); overflow: hidden;
  }
  .empty-state {
    flex: 1; display: flex; align-items: center; justify-content: center;
    flex-direction: column; color: var(--text-dim); gap: 8px;
  }
  .empty-state .icon { font-size: 48px; opacity: 0.25; }
  .empty-state p { font-size: 14px; }

  .detail { flex: 1; display: flex; flex-direction: column; overflow: hidden; }
  .detail-header {
    padding: 16px 20px 12px; border-bottom: 1px solid var(--border); flex-shrink: 0;
  }
  .detail-header .session-title {
    font-size: 16px; font-weight: 600; color: var(--text-bright);
    margin-bottom: 10px; word-break: break-word;
  }
  .detail-top-row {
    display: flex; align-items: center; gap: 12px;
  }
  .detail-top-row .info-details { flex: 1; min-width: 0; cursor: default; }
  .detail-top-row .detail-actions {
    display: flex; gap: 6px; flex-shrink: 0; padding-top: 2px;
  }
  .info-summary {
    font-size: 16px; font-weight: 600; color: var(--text-bright);
    cursor: pointer; user-select: none; outline: none;
    word-break: break-word; white-space: normal;
    margin-bottom: 6px;
    display: flex; align-items: center; gap: 8px;
    line-height: 26px;
  }
  .info-summary::-webkit-details-marker { display: none; }
  .info-toggle-icon {
    display: inline-flex; align-items: center; justify-content: center;
    width: 26px; height: 26px; flex-shrink: 0;
    border: 1px solid var(--border); border-radius: 5px;
    font-size: 13px; color: var(--text-dim); line-height: 1;
    transition: transform 0.2s ease, border-color 0.15s, color 0.15s;
  }
  .info-summary:hover .info-toggle-icon {
    border-color: var(--text-dim); color: var(--text);
  }
  .info-details[open] .info-toggle-icon {
    transform: rotate(90deg);
  }
  .info-details[open] .info-summary { margin-bottom: 10px; }
  .info-grid {
    display: grid; grid-template-columns: auto 1fr; gap: 3px 12px; font-size: 12px;
  }
  .info-grid .label { color: var(--text-dim); white-space: nowrap; }
  .info-grid .value { color: var(--text); font-family: var(--mono); font-size: 11px; word-break: break-all; }
  .detail-header .actions {
    margin-top: 12px; display: flex; gap: 8px; flex-wrap: wrap;
  }
  .btn {
    display: inline-flex; align-items: center; gap: 5px;
    padding: 6px 14px; border-radius: 5px; border: 1px solid var(--border);
    font-size: 12px; font-family: var(--font); cursor: pointer; transition: all .12s;
    background: transparent; color: var(--text); white-space: nowrap;
  }
  .btn:hover { background: var(--surface2); }
  .btn-danger {
    background: var(--danger-bg); color: var(--danger); border-color: transparent;
  }
  .btn-danger:hover { background: var(--danger); color: #fff; }
  .btn-restore {
    background: rgba(105,219,124,0.08); color: var(--success); border-color: transparent;
  }
  .btn-restore:hover { background: var(--success); color: #000; }
  .btn-confirming {
    animation: pulse .6s infinite alternate;
  }
  @keyframes pulse { from { opacity: 0.75; } to { opacity: 1; } }

  .conversation-preview {
    flex: 1; overflow-y: auto; padding: 12px 20px;
  }
  .conversation-preview::-webkit-scrollbar { width: 5px; }
  .conversation-preview::-webkit-scrollbar-thumb { background: var(--border); border-radius: 3px; }

  .msg { margin-bottom: 12px; padding: 8px 12px; border-radius: 6px; font-size: 12px; line-height: 1.55; word-break: break-word; }
  .msg.user { background: var(--surface); border-left: 2px solid var(--accent); }
  .msg.assistant { background: var(--surface); border-left: 2px solid var(--success); }
  .msg.title { background: transparent; border-left: 2px solid var(--text-dim); font-style: italic; color: var(--text-dim); font-size: 11px; }
  .msg .role-label { font-size: 10px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 6px; }
  .msg.user .role-label { color: var(--accent); }
  .msg.assistant .role-label { color: var(--success); }
  .msg.title .role-label { color: var(--text-dim); }

  /* ── Content part types (terminal-like) ── */
  .part-text { color: var(--text); }
  .part-text p { margin: 0 0 4px; }
  .part-text h2, .part-text h3, .part-text h4 { color: var(--text-bright); margin: 8px 0 4px; font-size: 13px; }
  .part-text strong { color: var(--text-bright); }
  .part-text code { background: var(--surface2); padding: 1px 5px; border-radius: 3px; font-family: var(--mono); font-size: 11px; color: var(--accent); }
  .part-text pre { background: var(--bg); border: 1px solid var(--border); border-radius: 4px; padding: 8px; overflow-x: auto; font-family: var(--mono); font-size: 11px; margin: 4px 0; }
  .part-text a { color: var(--accent); }
  .part-text table { border-collapse: collapse; margin: 4px 0; font-size: 11px; }
  .part-text th, .part-text td { border: 1px solid var(--border); padding: 3px 8px; text-align: left; }
  .part-text th { background: var(--surface2); color: var(--text-bright); }
  .part-text hr { border: none; border-top: 1px solid var(--border); margin: 8px 0; }
  .part-text blockquote { border-left: 2px solid var(--text-dim); padding-left: 8px; color: var(--text-dim); margin: 4px 0; }

  .part-thinking { margin: 2px 0; }
  .part-thinking summary { cursor: pointer; color: #b0a0d0; font-size: 10px; font-weight: 500; user-select: none; opacity: 0.7; }
  .part-thinking summary:hover { opacity: 1; }
  .part-thinking .thinking-content { color: #a098c0; font-style: italic; font-size: 11px; padding: 4px 8px; border-left: 2px solid #6a5acd; margin-top: 2px; }

  .part-tool { background: rgba(108,138,255,0.06); border: 1px solid rgba(108,138,255,0.15); border-radius: 4px; padding: 6px 10px; margin: 4px 0; font-family: var(--mono); font-size: 11px; }
  .part-tool .tool-name { color: var(--accent); font-weight: 600; }
  .part-tool .tool-input { color: var(--text-dim); margin-top: 2px; white-space: pre-wrap; word-break: break-all; }
  .part-tool-result { background: rgba(108,138,255,0.04); border: 1px solid rgba(108,138,255,0.1); border-radius: 4px; padding: 4px 10px; margin: 2px 0; font-size: 11px; color: var(--text-dim); max-height: 80px; overflow-y: auto; }
  .part-tool-result.error { border-color: rgba(255,107,107,0.2); color: var(--danger); }

  /* ── Modal ── */
  .modal-overlay {
    position: fixed; inset: 0; background: rgba(0,0,0,0.6);
    display: none; align-items: center; justify-content: center; z-index: 100;
  }
  .modal-overlay.show { display: flex; }
  .modal {
    background: var(--surface); border: 1px solid var(--border);
    border-radius: 10px; padding: 24px; max-width: 440px; width: 90%; text-align: center;
  }
  .modal h3 { font-size: 15px; color: var(--text-bright); margin-bottom: 8px; }
  .modal p { font-size: 13px; color: var(--text-dim); margin-bottom: 20px; line-height: 1.5; }
  .modal .modal-actions { display: flex; gap: 8px; justify-content: center; flex-wrap: wrap; }
  .modal .highlight { color: var(--text-bright); font-weight: 600; }

  /* ── Toast ── */
  .toast-container {
    position: fixed; bottom: 20px; right: 20px; z-index: 200;
    display: flex; flex-direction: column; gap: 8px;
  }
  .toast {
    padding: 10px 16px; border-radius: 6px; font-size: 13px;
    color: #fff; animation: slideIn .25s ease;
    max-width: 320px; box-shadow: 0 4px 12px rgba(0,0,0,0.3);
  }
  .toast.success { background: #2b8a3e; }
  .toast.info { background: #1971c2; }
  .toast.error { background: #c92a2a; }
  @keyframes slideIn { from { opacity: 0; transform: translateX(20px); } to { opacity: 1; transform: translateX(0); } }
</style>
</head>
<body>

<header>
  <h1>▸ <span id="app-title">Claude Session Manager</span></h1>
  <div class="header-right">
    <button class="lang-btn" onclick="newSession()" title="New chat" style="border-color:var(--accent);color:var(--accent)">+ <span data-i18n="newChat">New Chat</span></button>
    <button class="lang-btn" id="refresh-btn" onclick="refreshData()" title="Refresh">&#8635; <span data-i18n="refresh">Refresh</span></button>
    <div class="header-stats"><span id="session-count">0</span> <span id="sessions-label">sessions</span></div>
    <button class="lang-btn" id="lang-btn" onclick="toggleLang()">En</button>
  </div>
</header>

<div class="main">
  <!-- Left Panel -->
  <div class="panel-left">
    <div class="search-bar">
      <input type="text" id="search" data-i18n-placeholder="searchPlaceholder"
             oninput="renderList()" autofocus>
    </div>
    <div class="tab-bar">
      <button class="active" data-tab="list" onclick="switchTab('list')">
        <span data-i18n="listTab">Sessions</span>
      </button>
      <button data-tab="trash" onclick="switchTab('trash')">
        <span data-i18n="trashTab">Trash</span>
        <span class="badge" id="trash-badge" style="display:none">0</span>
      </button>
    </div>
    <div class="session-list" id="session-list"></div>
  </div>

  <!-- Right Panel -->
  <div class="panel-right" id="panel-right">
    <div class="empty-state">
      <div class="icon">&#9635;</div>
      <p data-i18n="selectHint">Select a session to view details</p>
    </div>
  </div>
</div>

<!-- Confirm Modal -->
<div class="modal-overlay" id="modal">
  <div class="modal">
    <h3 id="modal-title">Confirm</h3>
    <p id="modal-msg"></p>
    <div class="modal-actions">
      <button class="btn" id="modal-cancel" onclick="closeModal()"><span data-i18n="cancel">Cancel</span></button>
      <button class="btn btn-danger" id="modal-confirm" onclick="modalCallback()"><span data-i18n="confirmDeleteBtn">Move to Trash</span></button>
    </div>
  </div>
</div>

<div class="toast-container" id="toast-container"></div>

<script>
// ═══════════════════════════════════════════════════════════════════
//  i18n
// ═══════════════════════════════════════════════════════════════════
const I18N = """ + json.dumps(I18N, ensure_ascii=False) + r""";
let LANG = localStorage.getItem('csm-lang') || 'zh';

function t(key) {
  return (I18N[LANG] && I18N[LANG][key]) || I18N['en'][key] || key;
}

function applyLang() {
  document.querySelectorAll('[data-i18n]').forEach(el => {
    const key = el.getAttribute('data-i18n');
    el.textContent = t(key);
  });
  document.querySelectorAll('[data-i18n-placeholder]').forEach(el => {
    el.placeholder = t(el.getAttribute('data-i18n-placeholder'));
  });
  document.getElementById('lang-btn').textContent = t('language');
  document.getElementById('sessions-label').textContent = t('sessions');
  document.getElementById('app-title').textContent = t('appTitle');
  // Update current detail view if any
  if (currentDetailType === 'session') updateSessionDetail();
  else if (currentDetailType === 'trash') updateTrashDetail();
  else updateEmptyState();
}

function toggleLang() {
  LANG = LANG === 'zh' ? 'en' : 'zh';
  localStorage.setItem('csm-lang', LANG);
  // Update sort buttons
  document.querySelectorAll('#sort-bar button').forEach(b => {
    const sortKey = b.getAttribute('data-sort');
    b.textContent = t(sortKey === 'time' ? 'sortTime' : sortKey === 'size' ? 'sortSize' : 'sortMessages');
  });
  renderList();
  updateTrashBadge();
  applyLang();
}

// ═══════════════════════════════════════════════════════════════════
//  State
// ═══════════════════════════════════════════════════════════════════
let sessions = [];
let trashItems = [];
let selectedId = null;
let selectedType = 'session'; // 'session' | 'trash'
let sortBy = 'time';
let currentTab = 'list';
let modalCallback = null;
let currentDetailType = null;

// ═══════════════════════════════════════════════════════════════════
//  API
// ═══════════════════════════════════════════════════════════════════
async function api(path, method = 'GET') {
  const url = path + (path.includes('?') ? '&' : '?') + '_=' + Date.now();
  const res = await fetch(url, { method, cache: 'no-store' });
  return res.json();
}

// ═══════════════════════════════════════════════════════════════════
//  Init
// ═══════════════════════════════════════════════════════════════════
async function init() {
  sessions = await api('/api/sessions');
  trashItems = await api('/api/trash');
  document.getElementById('session-count').textContent = sessions.length;
  renderList();
  updateTrashBadge();
  applyLang();

  // Auto-refresh every 2s: session list + current detail view
  setInterval(async () => {
    const newSessions = await api('/api/sessions');
    const newTrash = await api('/api/trash');
    const changed = JSON.stringify(newSessions) !== JSON.stringify(sessions) ||
                    JSON.stringify(newTrash) !== JSON.stringify(trashItems);
    if (changed) {
      sessions = newSessions;
      trashItems = newTrash;
      document.getElementById('session-count').textContent = sessions.length;
      updateTrashBadge();
      renderList();
    }
    // Also refresh current detail panel if one is open (append-only, no flash)
    if (selectedId && currentTab === 'list') {
      refreshPreview(selectedId);
    } else if (selectedId && currentTab === 'trash') {
      selectTrashItem(selectedId);
    }
  }, 2000);
}
init();

// ═══════════════════════════════════════════════════════════════════
//  Tab switching
// ═══════════════════════════════════════════════════════════════════
function switchTab(tab) {
  currentTab = tab;
  selectedId = null;
  selectedType = 'session';
  document.querySelectorAll('.tab-bar button').forEach(b => b.classList.remove('active'));
  document.querySelector(`[data-tab="${tab}"]`).classList.add('active');


  // Reload data
  reloadData().then(() => {
    renderList();
    updateEmptyState();
  });
}

async function refreshData() {
  sessions = await api('/api/sessions');
  trashItems = await api('/api/trash');

  if (currentTab === 'list') {
    document.getElementById('session-count').textContent = sessions.length;
  }
  updateTrashBadge();
  renderList();

  // Refresh detail panel if a session is selected
  if (selectedId && currentTab === 'list') {
    selectSession(selectedId);
  } else if (selectedId && currentTab === 'trash') {
    selectTrashItem(selectedId);
  }
}

async function reloadData() {
  if (currentTab === 'list') {
    sessions = await api('/api/sessions');
    document.getElementById('session-count').textContent = sessions.length;
  } else {
    trashItems = await api('/api/trash');
  }
  updateTrashBadge();
}

function updateTrashBadge() {
  const badge = document.getElementById('trash-badge');
  if (trashItems.length > 0) {
    badge.style.display = 'inline';
    badge.textContent = trashItems.length;
  } else {
    badge.style.display = 'none';
  }
}

// ═══════════════════════════════════════════════════════════════════
//  Render List
// ═══════════════════════════════════════════════════════════════════
function renderList() {
  const query = (document.getElementById('search')?.value || '').toLowerCase();
  const container = document.getElementById('session-list');

  if (currentTab === 'list') {
    let filtered = sessions.filter(s => {
      if (!query) return true;
      return (s.title || '').toLowerCase().includes(query)
        || (s.project || '').toLowerCase().includes(query)
        || (s.model || '').toLowerCase().includes(query);
    });

    const actives = filtered.filter(s => s.active);

    // Sort active sessions by mtime (latest first)
    actives.sort((a, b) => b.mtime - a.mtime);

    // Sort ALL sessions by user's choice for bottom section
    const sorted = [...filtered];
    if (sortBy === 'time') sorted.sort((a, b) => b.mtime - a.mtime);
    else if (sortBy === 'size') sorted.sort((a, b) => b.size_bytes - a.size_bytes);
    else if (sortBy === 'messages') sorted.sort((a, b) => b.messages - a.messages);

    const renderCard = (s) => {
      const sel = s.id === selectedId ? ' selected' : '';
      const act = s.active ? ' active' : '';
      const dot = s.active ? '<span class="active-dot"></span>' : '';
      return `<div class="session-card${sel}${act}" data-id="${s.id}" onclick="selectSession('${s.id}')">
        <div class="title">${dot}${esc(s.title)}</div>
        <div class="meta">
          <span>${s.date}</span><span>${s.messages} msgs</span><span>${s.size}</span>
          <span class="project-tag">${esc(s.project)}</span>
        </div>
        <div class="card-actions">
          <button class="card-btn danger" onclick="event.stopPropagation(); ${s.active ? `askStopSession('${s.id}')` : `askDeleteSession('${s.id}')`}">&#x2715; ${s.active ? t('stop') : t('delete')}</button>
        </div>
      </div>`;
    };

    let html = '';
    if (actives.length > 0) {
      html += `<div class="section-header">🟢 ${t('runningSessions')}</div>`;
      html += actives.map(renderCard).join('');
    }
    html += `<div class="sort-bar" id="sort-bar" style="padding:4px 12px 8px">
      <button class="${sortBy==='time'?'active':''}" data-sort="time" onclick="setSort('time', this)">${t('sortTime')}</button>
      <button class="${sortBy==='size'?'active':''}" data-sort="size" onclick="setSort('size', this)">${t('sortSize')}</button>
      <button class="${sortBy==='messages'?'active':''}" data-sort="messages" onclick="setSort('messages', this)">${t('sortMessages')}</button>
    </div>`;
    html += `<div class="section-header">${t('allSessions')}</div>`;
    html += sorted.map(renderCard).join('');
    container.innerHTML = html;

  } else {
    // Trash tab
    let filtered = trashItems.filter(item => {
      if (!query) return true;
      return (item.title || '').toLowerCase().includes(query)
        || (item.id || '').toLowerCase().includes(query);
    });

    if (filtered.length === 0) {
      container.innerHTML = `<div style="padding:40px;text-align:center;color:var(--text-dim);font-size:13px">${t('trashEmpty')}</div>`;
    } else {
      container.innerHTML = filtered.map(item => {
        const sel = item.id === selectedId ? ' selected' : '';
        return `<div class="session-card${sel}" data-id="${item.id}" onclick="selectTrashItem('${item.id}')">
          <div class="title">${esc(item.title)}</div>
          <div class="meta">
            <span>${item.date}</span><span>${item.messages} msgs</span><span>${item.size}</span>
            <span style="color:var(--warn)">${t('deletedAt')}: ${item.deleted_at}</span>
          </div>
          <div class="card-actions">
            <button class="card-btn restore" onclick="event.stopPropagation(); askRestore('${item.id}')">&#8634; ${t('restore')}</button>
            <button class="card-btn danger" onclick="event.stopPropagation(); askPermDelete('${item.id}')">&#x2715; ${t('permDelete')}</button>
          </div>
        </div>`;
      }).join('');
    }
  }
}

function esc(str) {
  const div = document.createElement('div');
  div.textContent = str || '';
  return div.innerHTML;
}

function renderParts(parts) {
  if (!parts || parts.length === 0) return '';
  return parts.map(p => {
    switch (p.type) {
      case 'text':
        return `<div class="part-text">${renderMarkdown(p.content)}</div>`;
      case 'thinking':
        const thinkId = 'think-' + Math.random().toString(36).slice(2,8);
        return `<details class="part-thinking">
          <summary>💭 Thinking</summary>
          <div class="thinking-content">${esc(p.content)}</div>
        </details>`;
      case 'tool_use':
        return `<div class="part-tool">
          <div class="tool-name">⚙ ${esc(p.name)}</div>
          ${p.input ? `<div class="tool-input">${esc(p.input)}</div>` : ''}
        </div>`;
      case 'tool_result':
        return `<div class="part-tool-result${p.is_error ? ' error' : ''}">${esc(p.content)}</div>`;
      case 'title':
        return `<em>${esc(p.content)}</em>`;
      default:
        return esc(String(p.content || ''));
    }
  }).join('');
}

function renderMarkdown(str) {
  const escaped = esc(str);

  // Protect code blocks and inline code from further processing
  const codeBlocks = [];
  let html = escaped
    // Fenced code blocks ```...```
    .replace(/```(\w*)\n?([\s\S]*?)```/g, (_, lang, code) => {
      codeBlocks.push(`<pre><code>${code.trim()}</code></pre>`);
      return `%%CODEBLOCK_${codeBlocks.length - 1}%%`;
    })
    // Inline code `...`
    .replace(/`([^`\n]+?)`/g, (_, code) => {
      codeBlocks.push(`<code>${code}</code>`);
      return `%%CODEBLOCK_${codeBlocks.length - 1}%%`;
    });

  // Apply markdown rules to non-code text
  html = html
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/__(.+?)__/g, '<strong>$1</strong>')
    .replace(/(?<!\*)\*([^*\n]+?)\*(?!\*)/g, '<em>$1</em>')
    .replace(/(?<!_)_([^_\n]+?)_(?!_)/g, '<em>$1</em>')
    .replace(/^### (.+)$/gm, '<h4>$1</h4>')
    .replace(/^## (.+)$/gm, '<h3>$1</h3>')
    .replace(/^# (.+)$/gm, '<h2>$1</h2>')
    .replace(/^[\-*] (.+)$/gm, '<li>$1</li>')
    .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank">$1</a>')
    .replace(/\n\n/g, '<br><br>')
    .replace(/\n/g, '<br>');

  // Restore protected code blocks
  codeBlocks.forEach((block, i) => {
    html = html.replace(`%%CODEBLOCK_${i}%%`, block);
  });

  return html;
}

function setSort(key, btn) {
  sortBy = key;
  document.querySelectorAll('#sort-bar button').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  renderList();
}

// ═══════════════════════════════════════════════════════════════════
//  Session Detail (list tab)
// ═══════════════════════════════════════════════════════════════════
async function selectSession(id) {
  selectedId = id;
  selectedType = 'session';
  currentDetailType = 'session';
  renderList();

  const s = sessions.find(s => s.id === id);
  if (!s) return;

  const panel = document.getElementById('panel-right');
  panel.innerHTML = `
    <div class="detail">
      <div class="detail-header">
        <div class="detail-top-row">
          <details class="info-details">
            <summary class="info-summary"><span class="info-toggle-icon">▶</span> <span>${esc(s.title)}</span></summary>
            <div class="info-grid">
            <span class="label">${t('sessionId')}</span><span class="value">${s.id}</span>
            <span class="label">${t('project')}</span><span class="value">${esc(s.project)}</span>
            <span class="label">${t('branch')}</span><span class="value">${s.branch || '—'}</span>
            <span class="label">${t('model')}</span><span class="value">${s.model || '—'}</span>
            <span class="label">${t('messages')}</span><span class="value">${s.messages} (${s.turns} ${t('turns')})</span>
            <span class="label">${t('tokens')}</span><span class="value">${(s.tokens || 0).toLocaleString()}</span>
            <span class="label">${t('lastActive')}</span><span class="value">${s.last_time || s.date}</span>
            <span class="label">${t('size')}</span><span class="value">${s.size}</span>
          </div>
          </details>
          <div class="detail-actions">
            ${s.active ? '' : `<button class="btn" onclick="resumeSession('${s.id}')" style="color:var(--accent);border-color:var(--accent)">&#9654; ${t('resume')}</button>`}
            <button class="btn btn-danger" id="detail-delete-btn" onclick="${s.active ? `askStopSession('${s.id}')` : `askDeleteSession('${s.id}')`}">&#x2715; ${s.active ? t('stop') : t('delete')}</button>
          </div>
        </div>
      </div>
      <div class="conversation-preview" id="conversation-preview">${t('loading')}</div>
    </div>
  `;

  try {
    const msgs = await api(`/api/sessions/${id}/preview`);
    const preview = document.getElementById('conversation-preview');
    if (!msgs || msgs.length === 0) {
      preview.innerHTML = `<p style="color:var(--text-dim);padding:20px;text-align:center">${t('noMessages')}</p>`;
      return;
    }
    preview.innerHTML = msgs.map(m => `
      <div class="msg ${m.role}">
        <div class="role-label">${m.role === 'title' ? 'TITLE' : m.role.toUpperCase()}</div>
        ${renderParts(m.parts || [])}
      </div>
    `).join('');
  } catch (e) {
    document.getElementById('conversation-preview').innerHTML = `<p style="color:var(--danger);padding:20px">${t('loadFailed')}</p>`;
  }
}

async function refreshPreview(id) {
  const container = document.getElementById('conversation-preview');
  if (!container) return;
  try {
    const msgs = await api(`/api/sessions/${id}/preview`);
    if (!msgs || msgs.length === 0) return;
    // Only append new messages — avoid rebuilding entire DOM
    const existingCount = container.querySelectorAll('.msg').length;
    if (msgs.length <= existingCount) return; // nothing new
    const newMsgs = msgs.slice(existingCount);
    const scrollAtBottom = container.scrollTop + container.clientHeight >= container.scrollHeight - 40;
    container.insertAdjacentHTML('beforeend', newMsgs.map(m => `
      <div class="msg ${m.role}">
        <div class="role-label">${m.role === 'title' ? 'TITLE' : m.role.toUpperCase()}</div>
        ${renderParts(m.parts || [])}
      </div>
    `).join(''));
    // Auto-scroll only if already at bottom
    if (scrollAtBottom) container.scrollTop = container.scrollHeight;
  } catch (e) {}
}

function updateSessionDetail() {
  const s = sessions.find(s => s.id === selectedId);
  if (s) selectSession(s.id);
}

// ═══════════════════════════════════════════════════════════════════
//  Trash Detail
// ═══════════════════════════════════════════════════════════════════
function selectTrashItem(id) {
  selectedId = id;
  selectedType = 'trash';
  currentDetailType = 'trash';
  renderList();

  const item = trashItems.find(t => t.id === id);
  if (!item) return;

  const panel = document.getElementById('panel-right');
  panel.innerHTML = `
    <div class="detail">
      <div class="detail-header">
        <div class="session-title">${esc(item.title)}</div>
        <div class="info-grid">
          <span class="label">${t('sessionId')}</span><span class="value">${item.id}</span>
          <span class="label">${t('messages')}</span><span class="value">${item.messages}</span>
          <span class="label">${t('size')}</span><span class="value">${item.size}</span>
          <span class="label">${t('deletedAt')}</span><span class="value">${item.deleted_at}</span>
        </div>
        <div class="actions">
          <button class="btn btn-restore" onclick="askRestore('${item.id}')">&#8634; ${t('restore')}</button>
          <button class="btn btn-danger" onclick="askPermDelete('${item.id}')">&#x2715; ${t('permDelete')}</button>
        </div>
      </div>
      <div class="conversation-preview" style="padding:20px;color:var(--text-dim);text-align:center">
        <p>${t('restoreConfirmMsg')}</p>
      </div>
    </div>
  `;
}

function updateTrashDetail() {
  const item = trashItems.find(t => t.id === selectedId);
  if (item) selectTrashItem(item.id);
}

function updateEmptyState() {
  document.getElementById('panel-right').innerHTML = `
    <div class="empty-state">
      <div class="icon">&#9635;</div>
      <p data-i18n="selectHint">${t('selectHint')}</p>
    </div>`;
  currentDetailType = null;
}

// ═══════════════════════════════════════════════════════════════════
//  New Session
// ═══════════════════════════════════════════════════════════════════
async function newSession() {
  try {
    const res = await api('/api/new-session', 'POST');
    if (res.success) {
      toast(t('newChatStarted'), 'success');
    } else {
      toast(res.message || 'Failed', 'error');
    }
  } catch (e) {
    toast(e.message, 'error');
  }
}

// ═══════════════════════════════════════════════════════════════════
//  Resume Session
// ═══════════════════════════════════════════════════════════════════
async function resumeSession(id) {
  try {
    const res = await api(`/api/sessions/${id}/resume`, 'POST');
    if (res.success) {
      toast(t('resumed'), 'success');
    } else {
      toast(res.message || 'Failed', 'error');
    }
  } catch (e) {
    toast(e.message, 'error');
  }
}

// ═══════════════════════════════════════════════════════════════════
//  Stop Session
// ═══════════════════════════════════════════════════════════════════
function askStopSession(id) {
  const s = sessions.find(s => s.id === id);
  const body = `${t('stopConfirmMsg')}<br><br><b class="highlight">${esc(s?.title || id)}</b>`;

  showModal(t('stopConfirmTitle'), body, t('confirmStopBtn'), 'danger', async () => {
    closeModal();
    try {
      const res = await api(`/api/sessions/${id}/stop`, 'POST');
      if (res.success) {
        toast(t('stopped'), 'success');
      } else {
        toast(res.message || 'Failed', 'error');
      }
    } catch (e) {
      toast(e.message, 'error');
    }
  });
}

// ═══════════════════════════════════════════════════════════════════
//  Delete Session → Trash
// ═══════════════════════════════════════════════════════════════════
function askDeleteSession(id) {
  const s = sessions.find(s => s.id === id);
  const body = `${t('deleteConfirmMsg')}<br><br><b class="highlight">${esc(s?.title || id)}</b><br>
    <span style="color:var(--text-dim);font-size:11px">${s?.messages || 0} msgs &middot; ${s?.size || ''}</span>`;

  showModal(t('deleteConfirmTitle'), body, t('confirmDeleteBtn'), 'danger', async () => {
    closeModal();
    try {
      const res = await api(`/api/sessions/${id}`, 'DELETE');
      if (res.success) {
        sessions = sessions.filter(s => s.id !== id);
        trashItems = await api('/api/trash');
        if (selectedId === id) { selectedId = null; updateEmptyState(); }
        document.getElementById('session-count').textContent = sessions.length;
        updateTrashBadge();
        renderList();
        toast(t('deleted'), 'success');
      } else {
        toast(res.message || 'Failed', 'error');
      }
    } catch (e) {
      toast(e.message, 'error');
    }
  });
}

// ═══════════════════════════════════════════════════════════════════
//  Restore from Trash
// ═══════════════════════════════════════════════════════════════════
function askRestore(id) {
  const item = trashItems.find(t => t.id === id);
  const body = `${t('restoreConfirmMsg')}<br><br><b class="highlight">${esc(item?.title || id)}</b>`;

  showModal(t('restoreConfirmTitle'), body, t('confirmRestoreBtn'), 'restore', async () => {
    closeModal();
    try {
      const res = await api(`/api/trash/${id}/restore`, 'POST');
      if (res.success) {
        sessions = await api('/api/sessions');
        trashItems = await api('/api/trash');
        if (selectedId === id) { selectedId = null; updateEmptyState(); }
        document.getElementById('session-count').textContent = sessions.length;
        updateTrashBadge();
        renderList();
        toast(t('restored'), 'success');
      } else {
        toast(res.message || 'Failed', 'error');
      }
    } catch (e) {
      toast(e.message, 'error');
    }
  });
}

// ═══════════════════════════════════════════════════════════════════
//  Permanent Delete from Trash
// ═══════════════════════════════════════════════════════════════════
function askPermDelete(id) {
  const item = trashItems.find(t => t.id === id);
  const body = `<b style="color:var(--danger)">${t('permDeleteConfirmMsg')}</b><br><br>
    <b class="highlight">${esc(item?.title || id)}</b><br>
    <span style="color:var(--text-dim);font-size:11px">${item?.messages || 0} msgs &middot; ${item?.size || ''}</span>`;

  showModal(t('permDeleteConfirmTitle'), body, t('confirmPermDeleteBtn'), 'danger', async () => {
    closeModal();
    try {
      const res = await api(`/api/trash/${id}`, 'DELETE');
      if (res.success) {
        trashItems = trashItems.filter(t => t.id !== id);
        if (selectedId === id) { selectedId = null; updateEmptyState(); }
        updateTrashBadge();
        renderList();
        toast(t('permDeleted'), 'success');
      } else {
        toast(res.message || 'Failed', 'error');
      }
    } catch (e) {
      toast(e.message, 'error');
    }
  });
}

// ═══════════════════════════════════════════════════════════════════
//  Modal
// ═══════════════════════════════════════════════════════════════════
function showModal(title, msg, btnText, btnStyle, callback) {
  document.getElementById('modal-title').textContent = title;
  document.getElementById('modal-msg').innerHTML = msg;
  const confirmBtn = document.getElementById('modal-confirm');
  confirmBtn.textContent = btnText;
  confirmBtn.className = 'btn';
  if (btnStyle === 'danger') confirmBtn.classList.add('btn-danger');
  else if (btnStyle === 'restore') confirmBtn.classList.add('btn-restore');
  modalCallback = callback;
  document.getElementById('modal').classList.add('show');
}

function closeModal() {
  document.getElementById('modal').classList.remove('show');
  modalCallback = null;
}

document.getElementById('modal').addEventListener('click', function(e) {
  if (e.target === this) closeModal();
});

// ═══════════════════════════════════════════════════════════════════
//  Toast
// ═══════════════════════════════════════════════════════════════════
function toast(msg, type) {
  const container = document.getElementById('toast-container');
  const el = document.createElement('div');
  el.className = `toast ${type || 'info'}`;
  el.textContent = msg;
  container.appendChild(el);
  setTimeout(() => { el.remove(); }, 2500);
}

// ═══════════════════════════════════════════════════════════════════
//  Keyboard shortcuts
// ═══════════════════════════════════════════════════════════════════
document.addEventListener('keydown', e => {
  if (e.key === 'Escape') closeModal();
  if ((e.metaKey || e.ctrlKey) && e.key === 'f') {
    e.preventDefault();
    document.getElementById('search')?.focus();
  }
  if ((e.metaKey || e.ctrlKey) && e.key === 'r') {
    e.preventDefault();
    refreshData();
  }
});
</script>
</body>
</html>"""


# ═══════════════════════════════════════════════════════════════════════
#  HTTP Server
# ═══════════════════════════════════════════════════════════════════════

class RequestHandler(http.server.BaseHTTPRequestHandler):

    def log_message(self, format, *args):
        pass  # quiet

    # ── Routing ────────────────────────────────────────────────────

    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path

        if path == "/":
            return self._serve_html()
        elif path == "/api/sessions":
            return self._json(SessionManager.list_all())
        elif path.startswith("/api/sessions/") and path.endswith("/preview"):
            session_id = path.rsplit("/", 2)[-2]
            filepath = self._find_session_path(session_id)
            return self._json(SessionManager.get_preview(filepath)) if filepath else self._error(404, "Not found")
        elif path == "/api/trash":
            return self._json(SessionManager.list_trash())
        else:
            return self._error(404, "Not found")

    def do_DELETE(self):
        path = urllib.parse.urlparse(self.path).path

        if path.startswith("/api/sessions/"):
            session_id = path.rsplit("/", 1)[-1]
            filepath = self._find_session_path(session_id)
            if not filepath:
                return self._error(404, "Session not found")
            success, msg = SessionManager.move_to_trash(filepath)
            return self._json({"success": success, "message": msg})
        elif path.startswith("/api/trash/"):
            session_id = path.rsplit("/", 1)[-1]
            success, msg = SessionManager.delete_permanently(session_id)
            return self._json({"success": success, "message": msg})
        else:
            return self._error(404, "Not found")

    def do_POST(self):
        path = urllib.parse.urlparse(self.path).path

        if path.startswith("/api/trash/") and path.endswith("/restore"):
            session_id = path.rsplit("/", 2)[-2]
            success, msg = SessionManager.restore_from_trash(session_id)
            return self._json({"success": success, "message": msg})
        elif path.startswith("/api/sessions/") and path.endswith("/resume"):
            session_id = path.rsplit("/", 2)[-2]
            return self._resume_session(session_id)
        elif path.startswith("/api/sessions/") and path.endswith("/stop"):
            session_id = path.rsplit("/", 2)[-2]
            return self._stop_session(session_id)
        elif path == "/api/new-session":
            return self._new_session()
        else:
            return self._error(404, "Not found")

    def do_OPTIONS(self):
        self._cors()
        self.send_response(200)
        self.end_headers()

    # ── Response Helpers ────────────────────────────────────────────

    def _serve_html(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        self.end_headers()
        self.wfile.write(FRONTEND.encode("utf-8"))

    def _json(self, data):
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self._cors()
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8"))

    def _error(self, code, msg):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self._cors()
        self.end_headers()
        self.wfile.write(json.dumps({"error": msg}).encode("utf-8"))

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, DELETE, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _new_session(self):
        """Open a new Terminal window to start a fresh Claude Code session."""
        # Default to user's home directory
        cwd = os.path.expanduser("~")
        script = f'''
            tell application "Terminal"
                do script "cd {cwd} && claude"
                activate
            end tell
        '''
        import subprocess
        try:
            subprocess.run(["osascript", "-e", script], check=True, capture_output=True, text=True)
            return self._json({"success": True, "message": "Starting new session"})
        except subprocess.CalledProcessError as e:
            return self._json({"success": False, "message": f"Failed to launch: {e.stderr.strip()}"})

    def _resume_session(self, session_id):
        """Open a new Terminal window to resume a Claude Code session."""
        filepath = self._find_session_path(session_id)
        if not filepath:
            return self._error(404, f"Session not found: {session_id}")

        meta = SessionManager._parse_metadata(filepath)
        cwd = meta.get("cwd") or os.path.expanduser("~")

        # Build AppleScript to open Terminal and run claude --resume
        script = f'''
            tell application "Terminal"
                do script "cd {cwd} && claude --resume {session_id}"
                activate
            end tell
        '''
        import subprocess
        try:
            subprocess.run(["osascript", "-e", script], check=True, capture_output=True, text=True)
            return self._json({"success": True, "message": f"Resuming session {session_id}"})
        except subprocess.CalledProcessError as e:
            return self._json({"success": False, "message": f"Failed to launch: {e.stderr.strip()}"})

    def _stop_session(self, session_id):
        """Kill the claude process tied to this session, close its Terminal window."""
        import subprocess, re
        try:
            result = subprocess.run(["ps", "-eo", "pid,ppid,command"], capture_output=True, text=True, timeout=3)
            target_pids = []
            shell_ppids = set()
            has_bare = False

            for line in result.stdout.split("\n"):
                if "claude" not in line or "Session Manager" in line:
                    continue
                if "vscode" in line or "claude-code" in line:
                    continue

                parts = line.split(None, 2)
                if len(parts) < 3:
                    continue
                pid, ppid, cmd = parts

                # Exact match: --resume <id> or -r <id>
                m = re.search(r"(?:--resume|-r)\s+([a-f0-9-]{36})", cmd)
                if m and m.group(1) == session_id:
                    target_pids.append(pid)
                    shell_ppids.add(ppid)
                # Track bare claude processes (no session ID in command)
                elif re.search(r"\bclaude\b", cmd) and "--resume" not in cmd and "-r" not in cmd:
                    has_bare = True
                elif re.search(r"claude\s+-r\b", cmd) and not re.search(r"[a-f0-9-]{36}", cmd):
                    has_bare = True

            # If no exact match but bare claude exists and this session is the active one,
            # kill the bare claude process
            if not target_pids and has_bare:
                sessions = SessionManager.list_all()
                active_ids = [s["id"] for s in sessions if s.get("active")]
                if session_id in active_ids:
                    # Re-parse to find bare claude PIDs
                    for line in result.stdout.split("\n"):
                        if "claude" not in line or "Session Manager" in line:
                            continue
                        if "vscode" in line or "claude-code" in line:
                            continue
                        parts = line.split(None, 2)
                        if len(parts) < 3:
                            continue
                        pid, ppid, cmd = parts
                        if (re.search(r"\bclaude\b", cmd) and "--resume" not in cmd and "-r" not in cmd) or \
                           (re.search(r"claude\s+-r\b", cmd) and not re.search(r"[a-f0-9-]{36}", cmd)):
                            target_pids.append(pid)
                            shell_ppids.add(ppid)

            if not target_pids:
                return self._json({"success": False, "message": "No matching process found"})

            # SIGTERM to claude for graceful shutdown
            for pid in target_pids:
                subprocess.run(["kill", pid], capture_output=True)

            # Wait for claude to save state
            import time as _time
            _time.sleep(2)

            # Close Terminal windows by killing parent shells
            for ppid in shell_ppids:
                subprocess.run(["kill", "-9", ppid], capture_output=True)

            return self._json({"success": True, "message": "Stopped"})
        except Exception as e:
            return self._json({"success": False, "message": str(e)})

    def _find_session_path(self, session_id):
        for s in SessionManager.list_all():
            if s["id"] == session_id:
                return s["filepath"]
        return None


# ═══════════════════════════════════════════════════════════════════════
#  Entry Point
# ═══════════════════════════════════════════════════════════════════════

def main():
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

    server = http.server.HTTPServer((HOST, PORT), RequestHandler)
    url = f"http://localhost:{PORT}"

    # Only auto-open browser in standalone mode; .app launcher handles this
    if not os.environ.get("CSM_NO_BROWSER"):
        print(f"  ▼  Opening {url}")
        def open_browser():
            webbrowser.open(url)
        threading.Timer(0.3, open_browser).start()
    else:
        print(f"  Server ready at {url}")

    print(f"  Press Ctrl+C to stop")
    print()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  Shutting down...")
        server.shutdown()
        print("  Goodbye!\n")


if __name__ == "__main__":
    main()
