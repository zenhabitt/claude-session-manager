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
import sys
import webbrowser
import urllib.parse
import threading
import shutil
import time
import subprocess
import re
import datetime
from collections import Counter
from pathlib import Path

# ── 配置 ────────────────────────────────────────────────────────────
# Claude 会话数据存储在 ~/.claude/projects/ 下，按项目目录组织
# 每个会话是一个 .jsonl 文件，每行一条 JSON 记录

CLAUDE_PROJECTS_DIR = os.path.expanduser("~/.claude/projects")  # Claude 会话数据目录
TRASH_DIR = os.path.expanduser("~/.claude/session-manager/trash")  # 回收站目录
PORT = 8742  # HTTP 服务端口
HOST = "127.0.0.1"  # 仅监听本地，不对外暴露
SERVER_STARTED_AT = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")  # 服务启动时间戳


# ═══════════════════════════════════════════════════════════════════════
#  会话数据层 — 负责读取、解析、管理 Claude 会话文件
# ═══════════════════════════════════════════════════════════════════════

class SessionManager:
    """会话管理器：提供会话列表、预览、删除、恢复等核心数据操作"""

    _session_pid_cache = {}  # {session_id: pid} — 仅存活进程
    _session_data_cache = {}  # {session_id: full_data} — 完整 PID 文件数据

    @staticmethod
    def _read_session_pid_files():
        """读取 ~/.claude/sessions/*.json 文件，一次性提取所有字段并缓存。
        下游调用者无需重复打开和解析这些文件。"""
        ids = set()
        pid_map = {}
        data_map = {}
        sessions_dir = os.path.expanduser("~/.claude/sessions")
        if os.path.isdir(sessions_dir):
            try:
                fnames = os.listdir(sessions_dir)
            except OSError:
                fnames = []
            for fname in fnames:
                if not fname.endswith(".json"):
                    continue
                fpath = os.path.join(sessions_dir, fname)
                # 最多重试 3 次，防止 Claude 正在写入时读到截断 JSON
                for attempt in range(3):
                    try:
                        with open(fpath, "r", encoding="utf-8") as f:
                            data = json.load(f)
                        pid = data.get("pid")
                        sid = data.get("sessionId")
                        if pid and sid:
                            try:
                                os.kill(pid, 0)
                            except PermissionError:
                                pass  # 无权限检测，保守认为存活
                            except OSError:
                                break  # ESRCH: 进程已死，跳过
                            else:
                                ids.add(sid)
                            pid_map[sid] = pid
                            data_map[sid] = data
                        break
                    except (OSError, json.JSONDecodeError, ValueError):
                        if attempt < 2:
                            time.sleep(0.05)
                        # 最后一次也失败则静默跳过该文件
        SessionManager._session_pid_cache = pid_map
        SessionManager._session_data_cache = data_map
        return ids, pid_map

    @staticmethod
    def _get_active_session_ids():
        """获取当前所有活跃会话的 ID 集合。
        直接读取 Claude 的 PID→session 映射文件，不使用缓存，
        确保与系统实际状态同步。"""
        ids, pid_map = SessionManager._read_session_pid_files()
        return ids

    @staticmethod
    def list_all():
        """列出所有会话，包含元数据摘要。
        遍历 ~/.claude/projects/*/ 下所有 .jsonl 文件，
        解析每条会话的标题、消息数、token 数、模型等元数据。
        活跃会话排在最前面，按修改时间倒序排列。"""
        sessions = []
        projects_dir = Path(CLAUDE_PROJECTS_DIR)
        if not projects_dir.exists():
            return sessions

        active_ids = SessionManager._get_active_session_ids()  # 同时填充 pid_cache + data_cache

        # 从缓存读取 status（已在 _read_session_pid_files 中一次性提取）
        active_status = {}
        for sid in SessionManager._session_data_cache:
            pdata = SessionManager._session_data_cache[sid]
            raw = pdata.get("status")
            active_status[sid] = raw if raw else "plugin"

        seen_ids = set()  # 记录已处理的会话 ID，用于后续补充新生活跃会话

        # 遍历所有项目目录下的 .jsonl 文件
        for jsonl_file in projects_dir.glob("*/*.jsonl"):
            session_id = jsonl_file.stem  # 文件名（不含扩展名）即会话 ID
            seen_ids.add(session_id)
            project_dir = jsonl_file.parent.name if jsonl_file.parent != projects_dir else "(root)"
            project_name = SessionManager._decode_project(project_dir)  # 将目录名解码为可读路径

            info = SessionManager._parse_metadata(jsonl_file)  # 解析 JSONL 文件提取元数据
            info["id"] = session_id
            info["project"] = project_name
            info["filepath"] = str(jsonl_file)
            info["project_dir"] = project_dir
            stat = jsonl_file.stat()
            info["size_bytes"] = stat.st_size
            info["size"] = SessionManager._format_size(stat.st_size)
            info["mtime"] = stat.st_mtime
            info["date"] = SessionManager._format_time(stat.st_mtime)
            info["active"] = session_id in active_ids  # 通过 PID 映射精准判断是否活跃
            info["status"] = active_status.get(session_id, "idle") if info["active"] else ""

            # 跳过空会话：从未聊过天、进程已退出、仅含元数据
            if not info["active"] and info["messages"] <= 2 and info["title"] == "(empty conversation)":
                continue
            sessions.append(info)

        # 补充尚未生成 JSONL 文件的新生会话（刚启动但还没写入任何消息）
        for sid in active_ids:
            if sid not in seen_ids:
                sessions.append({
                    "id": sid,
                    "title": "(new session)",
                    "project": "~",
                    "project_dir": "(root)",
                    "filepath": "",
                    "size_bytes": 0,
                    "size": "—",
                    "mtime": time.time(),
                    "date": "Just started",
                    "active": True,
                    "status": active_status.get(sid, "idle"),
                    "messages": 0,
                    "turns": 0,
                    "tokens": 0,
                    "model": "",
                    "last_time": "",
                    "branch": "",
                })

        # 排序：活跃会话在前，然后按修改时间倒序
        sessions.sort(key=lambda s: (not s["active"], -s["mtime"]))
        return sessions

    @staticmethod
    def get_dashboard():
        """Return aggregated dashboard statistics."""
        sessions = SessionManager.list_all()
        # list_all() 内部已调用 _get_active_session_ids() 填充 _session_pid_cache
        pid_map = SessionManager._session_pid_cache

        total_messages = 0
        total_tokens = 0
        total_turns = 0
        model_counter = Counter()
        model_tokens = Counter()
        active_list = []
        recent = []

        for s in sessions:
            total_messages += s.get("messages", 0)
            total_tokens += s.get("tokens", 0)
            total_turns += s.get("turns", 0)
            model = s.get("model") or "(unknown)"
            model_counter[model] += 1
            model_tokens[model] += s.get("tokens", 0)

            if s["active"]:
                pid = pid_map.get(s["id"])
                status = "idle"
                cwd = s.get("project", "~")
                uptime_seconds = 0
                last_activity = s.get("last_time") or ""
                # 从缓存读取实时状态（_read_session_pid_files 已一次性提取）
                pdata = SessionManager._session_data_cache.get(s["id"], {})
                if pdata:
                    raw_status = pdata.get("status")
                    status = raw_status if raw_status else "plugin"
                    cwd = pdata.get("cwd", cwd)
                    started = pdata.get("startedAt", 0)
                    if started:
                        uptime_seconds = int((time.time() * 1000 - started) / 1000)
                    last_act = pdata.get("updatedAt", 0)
                    if last_act:
                        last_activity = datetime.datetime.fromtimestamp(
                            last_act / 1000
                        ).strftime("%Y-%m-%d %H:%M:%S")

                active_list.append({
                    "id": s["id"],
                    "title": s["title"],
                    "model": model,
                    "status": status,
                    "cwd": cwd,
                    "uptime_seconds": uptime_seconds,
                    "last_activity": last_activity,
                    "messages": s.get("messages", 0),
                })

        # Recent sessions (top 5 by mtime)
        all_sorted = sorted(sessions, key=lambda s: s.get("mtime", 0), reverse=True)
        for s in all_sorted[:5]:
            recent.append({
                "id": s["id"],
                "title": s["title"],
                "model": s.get("model") or "(unknown)",
                "last_time": s.get("last_time") or s.get("date", ""),
                "active": s["active"],
            })

        # Model stats sorted by usage
        model_stats = []
        for model, count in model_counter.most_common():
            model_stats.append({
                "model": model,
                "sessions": count,
                "tokens": model_tokens.get(model, 0),
            })

        return {
            "overview": {
                "total_sessions": len(sessions),
                "active_sessions": sum(1 for s in sessions if s["active"]),
                "busy_sessions": sum(1 for a in active_list if a["status"] == "busy"),
                "idle_sessions": sum(1 for a in active_list if a["status"] == "idle"),
                "total_messages": total_messages,
                "total_tokens": total_tokens,
                "total_turns": total_turns,
            },
            "active_list": active_list,
            "model_stats": model_stats,
            "recent_sessions": recent,
        }

    @staticmethod
    def _decode_project(dirname):
        """将项目目录名解码为可读的文件路径。
        Claude 将项目路径编码为目录名：/Users/foo/bar → -Users-foo-bar
        解码后还原为 ~/foo/bar 形式在前端展示。"""
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
        """解析 JSONL 会话文件，提取元数据摘要。
        流式读取文件，提取：AI 生成的标题、用户首条消息、
        消息总数、token 用量、模型名称、工作目录、Git 分支等。
        不会将整个文件加载到内存，适合大文件快速扫描。"""
        ai_title = ""       # AI 自动生成的会话标题
        first_user_msg = "" # 用户第一条消息（标题备选）
        msg_count = 0       # 消息总行数
        last_time = ""      # 最后一条消息的时间戳
        model = ""          # 使用的模型
        cwd = ""            # 工作目录
        branch = ""         # Git 分支
        total_tokens = 0    # 总 token 消耗（输入+输出）
        turn_count = 0      # 对话轮次

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
                    # 取用户第一条非空、非系统指令的消息作为标题备选
                    content = d.get("message", {}).get("content", "")
                    if isinstance(content, str):
                        clean = content.strip()
                        if clean and not clean.startswith("<"):
                            first_user_msg = clean[:120]
                    elif isinstance(content, list):
                        for item in content:
                            if isinstance(item, dict) and item.get("type") == "text":
                                first_user_msg = (item.get("text") or "")[:120]
                                break
                elif t == "assistant":
                    m = d.get("message", {})
                    model = m.get("model", model)
                    usage = m.get("usage", {})
                    total_tokens += usage.get("input_tokens", 0) + usage.get("output_tokens", 0)
                elif t == "system" and d.get("subtype") == "turn_duration":
                    turn_count += 1  # 每轮对话结束时 Claude 会写入一条 turn_duration 记录

                ts = d.get("timestamp", "")
                if ts:
                    last_time = ts
                cwd = d.get("cwd", cwd) or cwd
                branch = d.get("gitBranch", branch) or branch

        # 标题优先级：AI 标题 > 用户首条消息 > 占位文本
        title = ai_title or first_user_msg or "(empty conversation)"
        if len(title) > 80:
            title = title[:79] + "…"

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
    def get_preview(filepath, max_messages=400, after_line=0, query=None):
        """获取会话预览内容（用于右侧详情面板和实时刷新）。
        参数:
            filepath: JSONL 文件路径
            max_messages: 最大返回消息数（使用 deque 限制内存）
            after_line: 增量刷新用，仅返回该行之后的消息
            query: 内容搜索关键词，匹配的消息会标记 _match: true
        返回:
            {messages: [...], first_match_line: int}"""
        from collections import deque
        messages = deque(maxlen=max_messages)  # 固定容量队列，自动丢弃最旧消息
        first_match_line = 0  # 第一个匹配行的行号，供前端导航跳转
        q = (query or "").strip().lower()
        with open(filepath, "r", encoding="utf-8") as f:
            for line_no, line in enumerate(f, 1):
                # 增量刷新模式下跳过已加载的行，但仍需检测搜索匹配
                if after_line > 0 and line_no <= after_line:
                    if q and not first_match_line and q in line.lower():
                        first_match_line = line_no
                    continue
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
                            continue  # 跳过系统指令消息（以 < 开头）
                        parts = [{"type": "text", "content": c.strip()[:500]}]
                    elif isinstance(c, list):
                        for item in c:
                            if isinstance(item, dict):
                                if item.get("type") == "text":
                                    parts.append({"type": "text", "content": (item.get("text") or "")[:500]})
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
                            inp_simple = {}
                            for k, v in inp.items():
                                if isinstance(v, str) and len(v) > 200:
                                    inp_simple[k] = v[:199] + "…"  # 截断过长的输入
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
                    msg = {"role": role, "parts": parts, "_line": line_no}
                    if q:
                        # 仅匹配 user/assistant 的 TEXT 内容，避免 thinking/tool 产生误匹配
                        for p in parts:
                            if p.get("type") == "text" and q in p.get("content", "").lower():
                                msg["_match"] = True
                                if not first_match_line:
                                    first_match_line = line_no
                                break
                    messages.append(msg)

        # 返回 dict 格式，前端可访问 first_match_line 用于搜索结果导航
        return {"messages": list(messages), "first_match_line": first_match_line}

    # ── 回收站操作 ──────────────────────────────────────────

    @staticmethod
    def move_to_trash(filepath):
        """将会话移入回收站，同时保存元数据以便恢复。
        删除时会话文件从原始项目目录移动到 ~/.claude/session-manager/trash/，
        同时保存 metadata.json 记录原始路径、标题、删除时间等信息。"""
        path = Path(filepath)
        if not path.exists():
            return False, "File not found"

        session_id = path.stem
        trash_path = Path(TRASH_DIR) / session_id
        trash_path.mkdir(parents=True, exist_ok=True)

        # 在移动前读取元数据
        meta = SessionManager._parse_metadata(path)

        # 保存原始位置信息，以便恢复
        trash_meta = {
            "id": session_id,
            "title": meta["title"],
            "original_path": str(path),       # 原始文件路径
            "original_parent": str(path.parent),  # 原始项目目录
            "messages": meta["messages"],
            "size": SessionManager._format_size(path.stat().st_size),
            "size_bytes": path.stat().st_size,
            "date": SessionManager._format_time(path.stat().st_mtime),
            "deleted_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "deleted_ts": time.time(),
        }

        # 将 JSONL 文件移入回收站
        try:
            shutil.move(str(path), str(trash_path / f"{session_id}.jsonl"))
        except OSError as e:
            return False, f"Move failed: {e}"

        # 同时移动子 agent 目录（如果存在）
        subagent_dir = path.parent / session_id
        if subagent_dir.exists() and subagent_dir.is_dir():
            try:
                shutil.move(str(subagent_dir), str(trash_path / session_id))
            except OSError:
                pass  # 子目录移动失败不影响主流程

        # 写入元数据文件，供恢复时使用
        meta_file = trash_path / "metadata.json"
        with open(meta_file, "w") as f:
            json.dump(trash_meta, f, ensure_ascii=False)

        return True, "Moved to trash"

    @staticmethod
    def list_trash():
        """列出回收站中的所有会话。"""
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
        """从回收站恢复会话到原始位置。
        读取 metadata.json 获取原始路径，将会话文件和子 agent 目录移回。"""
        if not SessionManager._validate_session_id(session_id):
            return False, "Invalid session ID"
        trash_path = Path(TRASH_DIR) / session_id
        meta_file = trash_path / "metadata.json"

        if not meta_file.exists():
            return False, "Trash metadata not found"

        try:
            with open(meta_file) as f:
                meta = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            return False, f"Metadata read error: {e}"

        original_parent = meta.get("original_parent")
        if not original_parent:
            return False, "Invalid metadata: missing original_parent"
        original_dir = Path(original_parent)
        jsonl_src = trash_path / f"{session_id}.jsonl"
        jsonl_dst = original_dir / f"{session_id}.jsonl"
        subagent_src = trash_path / session_id
        subagent_dst = original_dir / session_id

        if not jsonl_src.exists():
            return False, "Trash JSONL file missing"

        # 确保原始目录存在（可能已被删除）
        original_dir.mkdir(parents=True, exist_ok=True)

        errors = []
        try:
            shutil.move(str(jsonl_src), str(jsonl_dst))
        except OSError as e:
            errors.append(f"jsonl: {e}")

        if subagent_src.exists():
            try:
                if subagent_dst.exists():
                    shutil.rmtree(subagent_dst)  # 先删除已存在的目录（冲突处理）
                shutil.move(str(subagent_src), str(subagent_dst))
            except OSError as e:
                errors.append(f"subagent: {e}")

        if errors:
            return False, "; ".join(errors)

        # 恢复成功后清理回收站目录
        try:
            shutil.rmtree(trash_path)
        except OSError:
            pass

        return True, "Restored"

    @staticmethod
    def delete_permanently(session_id):
        """从回收站彻底删除会话（不可逆操作）。"""
        if not SessionManager._validate_session_id(session_id):
            return False, "Invalid session ID"
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
        """将字节数格式化为人类可读的大小字符串（B/K/M/G）。"""
        if size_bytes < 1024:
            return f"{size_bytes}B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes/1024:.0f}K"
        elif size_bytes < 1024 * 1024 * 1024:
            return f"{size_bytes/(1024*1024):.1f}M"
        return f"{size_bytes/(1024*1024*1024):.1f}G"

    @staticmethod
    def _format_time(ts):
        """将 Unix 时间戳格式化为友好的相对时间显示。
        - 今天: "Today HH:MM"
        - 昨天: "Yesterday HH:MM"
        - 一周内: "Xd ago HH:MM"
        - 更早: "YYYY-MM-DD HH:MM" """
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

    _SESSION_ID_RE = re.compile(r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$')

    @classmethod
    def _validate_session_id(cls, session_id):
        """验证 session_id 是否为合法 UUID 格式，防止 glob 注入。"""
        return bool(cls._SESSION_ID_RE.match(session_id))


# ═══════════════════════════════════════════════════════════════════════
#  前端 — 国际化字符串
# ═══════════════════════════════════════════════════════════════════════

I18N = {
    "zh": {
        "appTitle": "S.T.O.A.",
        "sessions": "个会话",
        "searchPlaceholder": "搜索会话…",
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
        "restart": "重启",
        "restartConfirmTitle": "确认重启",
        "restartConfirmMsg": "这会先停止当前会话，再重新启动。",
        "confirmRestartBtn": "重启会话",
        "restarted": "正在重启…",
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
        "loading": "加载中…",
        "noData": "暂无数据",
        "failed": "操作失败",
        "prevMatch": "上一个",
        "nextMatch": "下一个",
        "noMessages": "没有找到消息",
        "loadFailed": "加载预览失败",
        "deleted": "已删除",
        "restored": "已恢复",
        "permDeleted": "已彻底删除",
        "confirmDeleteBtn": "确认删除",
        "confirmRestoreBtn": "确认恢复",
        "confirmPermDeleteBtn": "确认彻底删除",
        "language": "En",
        "themeWarm": "暖金",
        "themeCool": "冷蓝",
        "batchBar": "已选择",
        "batchDelete": "批量删除",
        "refresh": "刷新",
        "settingsBtn": "设置",
        "themeLabel": "切换主题",
        "langLabel": "English / 中文",
        "restartBtn": "重启 S.T.O.A.",
        "scrollToBottom": "回到底部",
        "newChat": "新对话",
        "newChatStarted": "已在新终端中打开",
        "newSessionPlaceholder": "新会话",
        "resume": "继续对话",
        "resumed": "已在新终端中打开",
        "narrowHint1": "预览窗过窄",
        "narrowHint2": "请调整浏览器宽度，或折叠左侧栏",
        "dashboardTab": "仪表盘",
        "dashboardOverview": "概览",
        "totalSessions": "总会话",
        "activeSessions": "活跃会话",
        "totalMessages": "总消息",
        "totalTokens": "总 Token",
        "busyStatus": "处理中",
        "idleStatus": "空闲",
        "pluginStatus": "插件活跃",
        "modelUsage": "模型用量",
        "recentActivity": "最近活动",
        "uptime": "运行时长",
        "showNonDialogue": "显示过程信息",
        "hideNonDialogue": "隐藏过程信息",
        "searchContent": "搜索会话内容",
        "searchContentFound": "找到 {n} 个匹配会话",
        "searchContentNone": "未找到匹配的对话内容",
    },
    "en": {
        "appTitle": "S.T.O.A.",
        "sessions": "sessions",
        "searchPlaceholder": "Search sessions…",
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
        "restart": "Restart",
        "restartConfirmTitle": "Restart Session",
        "restartConfirmMsg": "This will stop the current session and restart it.",
        "confirmRestartBtn": "Restart Session",
        "restarted": "Restarting…",
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
        "loading": "Loading…",
        "noData": "No data",
        "failed": "Failed",
        "prevMatch": "Previous",
        "nextMatch": "Next",
        "noMessages": "No messages found",
        "loadFailed": "Failed to load preview",
        "deleted": "Deleted",
        "restored": "Restored",
        "permDeleted": "Permanently deleted",
        "confirmDeleteBtn": "Move to Trash",
        "confirmRestoreBtn": "Restore",
        "confirmPermDeleteBtn": "Delete Forever",
        "language": "中文",
        "themeWarm": "Warm",
        "themeCool": "Cool",
        "batchBar": "selected",
        "batchDelete": "Delete selected",
        "refresh": "Refresh",
        "settingsBtn": "Settings",
        "themeLabel": "Toggle Theme",
        "langLabel": "English / 中文",
        "restartBtn": "Restart S.T.O.A.",
        "scrollToBottom": "Scroll to bottom",
        "newChat": "New Chat",
        "newChatStarted": "Opened in new terminal",
        "newSessionPlaceholder": "New Session",
        "resume": "Continue",
        "resumed": "Opened in new terminal",
        "narrowHint1": "Preview too narrow",
        "narrowHint2": "Resize window or collapse sidebar",
        "dashboardTab": "Dashboard",
        "dashboardOverview": "Overview",
        "totalSessions": "Total Sessions",
        "activeSessions": "Active",
        "totalMessages": "Total Messages",
        "totalTokens": "Total Tokens",
        "busyStatus": "Busy",
        "idleStatus": "Idle",
        "pluginStatus": "Plugin Active",
        "modelUsage": "Model Usage",
        "recentActivity": "Recent Activity",
        "uptime": "Uptime",
        "showNonDialogue": "Show process info",
        "hideNonDialogue": "Hide process info",
        "searchContent": "Search in messages",
        "searchContentFound": "{n} sessions found",
        "searchContentNone": "No matches in messages",
    },
}


# ═══════════════════════════════════════════════════════════════════════
#  前端 (HTML/CSS/JS) — 单文件内嵌 Web 界面
# ═══════════════════════════════════════════════════════════════════════

FRONTEND = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>S.T.O.A.</title>
<link rel="icon" type="image/png" href="data:image/png;base64,/9j/4AAQSkZJRgABAQAASABIAAD/4QCwRXhpZgAATU0AKgAAAAgABQESAAMAAAABAAEAAAEaAAUAAAABAAAASgEbAAUAAAABAAAAUgEoAAMAAAABAAIAAIdpAAQAAAABAAAAWgAAAAAAAABIAAAAAQAAAEgAAAABAAaQAAAHAAAABDAyMjGRAQAHAAAABAECAwCgAAAHAAAABDAxMDCgAgAEAAAAAQAAAECgAwAEAAAAAQAAAECkBgADAAAAAQAAAAAAAAAA/+ICKElDQ19QUk9GSUxFAAEBAAACGGFwcGwEAAAAbW50clJHQiBYWVogB+YAAQABAAAAAAAAYWNzcEFQUEwAAAAAQVBQTAAAAAAAAAAAAAAAAAAAAAAAAPbWAAEAAAAA0y1hcHBsAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAKZGVzYwAAAPwAAAAwY3BydAAAASwAAABQd3RwdAAAAXwAAAAUclhZWgAAAZAAAAAUZ1hZWgAAAaQAAAAUYlhZWgAAAbgAAAAUclRSQwAAAcwAAAAgY2hhZAAAAewAAAAsYlRSQwAAAcwAAAAgZ1RSQwAAAcwAAAAgbWx1YwAAAAAAAAABAAAADGVuVVMAAAAUAAAAHABEAGkAcwBwAGwAYQB5ACAAUAAzbWx1YwAAAAAAAAABAAAADGVuVVMAAAA0AAAAHABDAG8AcAB5AHIAaQBnAGgAdAAgAEEAcABwAGwAZQAgAEkAbgBjAC4ALAAgADIAMAAyADJYWVogAAAAAAAA9tUAAQAAAADTLFhZWiAAAAAAAACD3wAAPb////+7WFlaIAAAAAAAAEq/AACxNwAACrlYWVogAAAAAAAAKDgAABELAADIuXBhcmEAAAAAAAMAAAACZmYAAPKnAAANWQAAE9AAAApbc2YzMgAAAAAAAQxCAAAF3v//8yYAAAeTAAD9kP//+6L///2jAAAD3AAAwG7/wAARCABAAEADASIAAhEBAxEB/8QAHwAAAQUBAQEBAQEAAAAAAAAAAAECAwQFBgcICQoL/8QAtRAAAgEDAwIEAwUFBAQAAAF9AQIDAAQRBRIhMUEGE1FhByJxFDKBkaEII0KxwRVS0fAkM2JyggkKFhcYGRolJicoKSo0NTY3ODk6Q0RFRkdISUpTVFVWV1hZWmNkZWZnaGlqc3R1dnd4eXqDhIWGh4iJipKTlJWWl5iZmqKjpKWmp6ipqrKztLW2t7i5usLDxMXGx8jJytLT1NXW19jZ2uHi4+Tl5ufo6erx8vP09fb3+Pn6/8QAHwEAAwEBAQEBAQEBAQAAAAAAAAECAwQFBgcICQoL/8QAtREAAgECBAQDBAcFBAQAAQJ3AAECAxEEBSExBhJBUQdhcRMiMoEIFEKRobHBCSMzUvAVYnLRChYkNOEl8RcYGRomJygpKjU2Nzg5OkNERUZHSElKU1RVVldYWVpjZGVmZ2hpanN0dXZ3eHl6goOEhYaHiImKkpOUlZaXmJmaoqOkpaanqKmqsrO0tba3uLm6wsPExcbHyMnK0tPU1dbX2Nna4uPk5ebn6Onq8vP09fb3+Pn6/9sAQwACAgICAgIDAgIDBQMDAwUGBQUFBQYIBgYGBgYICggICAgICAoKCgoKCgoKDAwMDAwMDg4ODg4PDw8PDw8PDw8P/9sAQwECAgIEBAQHBAQHEAsJCxAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQ/90ABAAE/9oADAMBAAIRAxEAPwD6siuBLneQTjpXWaLaG8uYoufm7DpivHLPWBLOql8A4GK+gvhpbpfakHJLBF5+tAFLxd4cJKzpHhQMflXzP408M+ZbyOiZ5OeK/RnUtB+1WpUKOnHFeCa14FnuLj7Mg+VyeTwqj1JPQepNAH5B+OvDF5JefZ7aJpZJmwiKCzMTxgKOTmvqb9nD/gn3P4hurfxv8b0a2sFIkh0lDtmmHUG4I+4p/uj5j3xX2v4J8C+D9H1hbvSYE1LUE+9fOuVQ91gB6e79T2r6v0q3dbdRJkk9QOpzQB4r8TLfTPD3hCLwpoa3FhaJD5Fvp+iRA38seNoigx8sCkcGU4wOcqea/mY+M17De/EbWYLXQ4fDsFjM1uljDJ55i8s4PmzZbzZSeXfJy2a/fz9tv4naf8OPhlqVm3iv/hGtR1WB47Wz01UfUrxyMDdI3+qiH8bAZxwG7V/Ny7vIzvJlnbkknJJPUk0Af//Qu6fr+54wG+bqT6n2r7c/Z+1OC/vGhZwzsvAzz71+VWl+JHNyoLgBsc9OPWvs/wDZ7+IfhH/hI7WyTUpbLUFfCSTootpMH7uQcrnsTQB+qsdkCnIr5S+M2u3EviuDwHpLFEWNJrwr1cyZKpx2AGT65r6t1XxBonh7QJvEWt3cdtY28fmSSFhjAHRf7xPQAdTXwd4b1O68ZeOL/wAY3kew6pOXjQ9UiHEa/goGaAPpH4feGUtbaPcnGB2r2KSJoLZ9kbOVU4UEJ+vb61m+HYAtrGgxgCvH/wBp19Ot/hZqZvIbsyTJ5cMlpK0WyQ9DIVYZX2IIPSgD8Qv25PitqHxL+JVxokmn2NjYeG5JLeE2jLO0zE/PJJOAC54wB0Hb1r4KmtiC2RjA7+lfS/jXw7tuJjGnBJ4bk9a8eutIZWOV2kdR6496AP/R+HbbWyHCsSee/NepeG9czcQvB8kgIHBx07181x3Z4I+vHau/8Naq1vcRu/IBAwM9KAP0V8CWev8Aja5tV1rULi8t4GBjikkZkUj0XO3P4V9++EfAU1t5EsEeNo6D09K+DfgP4r04NAHkXzFxkEjI/wD11+n3g3xLp0lrGyuM4oA9K0q2MFuquNpAxXyD+1F4gtNStIdAtZfNWIM0mxzt3Hjay9Mj+tfT2uw6/f2rjwxqEduXAO2RckH1Vh0z6Yr488ffCbx/IbjULi3+17suzRkMT6k9/wBKAPzC8beHmkkcxL1zn1rxG/8ADLE4VcEjn2Ffb/iPQEE7xzIdwzkH1ryq98LZYjyye2RQB//S/MKCTkc4rtdGl2MGU89s150kuNp7muw0mfawI5PvQB9ReCLm+aaH7FIVlJABXg5/Cv1L+FkWqQ6LaR3l0zyyAfeOSM9jX5MeAdZWxuIpjhjH69vwr7y8DfFK4BhPURAKAaAP0j8NalLbxiC4YttIG4/pWv4r8Uadomjz3V3IVypVQjYfcRx/+vFfGn/Cw9Z1DLQz+SGXaQo9Dn8waxdU1vU9ZLTajO07EY5Pp2oA888QWovrua5K58xywz15Oa4WTShIx2qAT0Fesz2ynnP1rLksOQ3pyO1AH//Z">
<style>
  :root, [data-theme="warm"] {
    --bg: #1a1918; --surface: #242321; --surface2: #2d2b28; --border: #383532;
    --text: #c4bbb4; --text-dim: #877f76; --text-bright: #e8e0d8;
    --accent: #c4944a; --accent-hover: #d4a55a;
    --danger: #c46a5e; --danger-hover: #d47a6e; --danger-bg: rgba(196,106,94,0.1);
    --panel-left-width: 360px;
    --success: #7ea882; --warn: #d4a84b;
    --radius: 8px;
    --font: -apple-system, BlinkMacSystemFont, "SF Pro Text", "Segoe UI", sans-serif;
    --mono: "SF Mono", "Fira Code", "JetBrains Mono", monospace;
    --tag-project-bg: rgba(66,202,253,0.15); --tag-project-color: #42CAFD;
  }
  [data-theme="cool"] {
    --bg: #1a1b1e; --surface: #25262b; --surface2: #2c2e33; --border: #373a40;
    --text: #c1c2c5; --text-dim: #909296; --text-bright: #e0e0e0;
    --tag-project-bg: rgba(108,138,255,0.15); --tag-project-color: #8ba3ff;
    --accent: #6c8aff; --accent-hover: #8ba3ff;
    --danger: #ff6b6b; --danger-hover: #ff8787; --danger-bg: rgba(255,107,107,0.08);
    --success: #69db7c; --warn: #ffd43b;
    --radius: 8px;
    --font: -apple-system, BlinkMacSystemFont, "SF Pro Text", "Segoe UI", sans-serif;
    --mono: "SF Mono", "Fira Code", "JetBrains Mono", monospace;
  }

  /* Theme-dependent color overrides */
  [data-theme="warm"] .part-tool { background: rgba(196,148,74,0.06); border-color: rgba(196,148,74,0.15); }
  [data-theme="cool"] .part-tool { background: rgba(108,138,255,0.06); border-color: rgba(108,138,255,0.15); }
  [data-theme="warm"] .part-tool-result { background: rgba(196,148,74,0.04); border-color: rgba(196,148,74,0.1); }
  [data-theme="cool"] .part-tool-result { background: rgba(108,138,255,0.04); border-color: rgba(108,138,255,0.1); }
  [data-theme="warm"] .part-thinking .thinking-content { border-left-color: var(--accent); }
  [data-theme="cool"] .part-thinking .thinking-content { border-left-color: #6a5acd; }
  [data-theme="warm"] .part-tool-result.error { border-color: rgba(196,106,94,0.25); }
  [data-theme="cool"] .part-tool-result.error { border-color: rgba(255,107,107,0.2); }

  /* Base styles that don't depend on theme variables */
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
  header h1 { font-size: 18px; font-weight: 600; color: var(--text-bright); font-family: 'Didot', 'Hoefler Text', 'Palatino Linotype', 'Book Antiqua', 'Palatino', 'Georgia', serif; letter-spacing: 1.5px; }
  .header-right { display: flex; align-items: center; gap: 16px; }
  .lang-btn {
    font-size: 11px; padding: 3px 10px; border: 1px solid var(--border);
    border-radius: 4px; background: transparent; color: var(--text-dim);
    cursor: pointer; font-family: var(--font); transition: background .15s, border-color .15s, color .15s, opacity .15s;
  }
  .lang-btn:hover { color: var(--text); border-color: var(--text-dim); }
  .lang-btn:active { background: var(--accent); color: #fff; border-color: var(--accent); }

  .settings-wrap { position: relative; }
  .settings-menu {
    visibility: hidden; position: absolute; top: 100%; right: 0; margin-top: 6px;
    background: var(--surface); border: 1px solid var(--border); border-radius: 6px;
    padding: 4px; z-index: 100; min-width: 160px;
    box-shadow: 0 8px 24px rgba(0,0,0,0.3);
    transform: translateY(-8px); opacity: 0;
    transition: transform .2s cubic-bezier(.16,1,.3,1), opacity .15s ease-out, visibility .2s;
  }
  .settings-menu.show {
    visibility: visible; transform: translateY(0); opacity: 1;
  }
  .settings-menu button {
    display: block; width: 100%; padding: 6px 12px; border: none;
    background: transparent; color: var(--text); font-size: 12px;
    font-family: var(--font); cursor: pointer; text-align: left; border-radius: 4px;
    transition: background .12s;
  }
  .settings-menu button:hover { background: var(--surface2); }
  .settings-sep { height: 1px; background: var(--border); margin: 4px 8px; }
  .settings-info { padding: 4px 12px; font-size: 10px; color: var(--text-dim); }

  /* ── Main Layout ── */
  .main { display: flex; flex: 1; overflow: hidden; }

  /* ── Left Panel ── */
  .panel-left {
    width: var(--panel-left-width); flex-shrink: 0; background: var(--surface);
    overflow: hidden;
    transition: width .35s cubic-bezier(.16,1,.3,1);
  }
  .panel-left.collapsed { width: 0; }
  .panel-left-inner {
    width: var(--panel-left-width); height: 100%; display: flex; flex-direction: column;
    border-right: 1px solid var(--border);
  }
  .search-bar { display: flex; gap: 6px; padding: 12px; flex-shrink: 0; }
  .search-bar input {
    flex: 1; min-width: 0; padding: 8px 12px; border: 1px solid var(--border);
    border-radius: 6px; background: var(--bg); color: var(--text);
    font-size: 13px; font-family: var(--font); outline: none; transition: border-color .15s;
  }
  .search-bar input:focus { border-color: var(--accent); }
  .search-bar input::placeholder { color: var(--text-dim); }
  .search-bar .content-search-btn {
    padding: 6px 10px; border: 1px solid var(--border); border-radius: 6px;
    background: var(--bg); color: var(--text-dim); cursor: pointer;
    font-size: 13px; white-space: nowrap; transition: border-color .15s, background .15s, color .15s;
    flex-shrink: 0;
  }
  .search-bar .content-search-btn:hover { border-color: var(--accent); color: var(--accent); }
  .search-bar .content-search-btn.active { background: var(--accent); color: #fff; border-color: var(--accent); }

  .search-result-info {
    padding: 0 12px 4px; font-size: 11px; color: var(--accent);
    display: none; flex-shrink: 0;
  }
  .search-result-info.show { display: block; }

  .tab-bar {
    display: flex; padding: 0 12px 8px; gap: 2px; flex-shrink: 0;
    position: relative;
  }
  .tab-bar button {
    flex: 1; padding: 6px 0; border: none;
    background: transparent; color: var(--text-dim); font-size: 12px;
    font-family: var(--font); cursor: pointer; transition: color .15s;
    position: relative; z-index: 1;
  }
  .tab-bar button:hover { color: var(--text); }
  .tab-bar button.active { color: var(--accent); }
  .tab-indicator {
    position: absolute; bottom: 8px; height: 2px;
    background: var(--accent); border-radius: 1px;
    transition: left .2s cubic-bezier(.4,0,.2,1), width .2s cubic-bezier(.4,0,.2,1);
    z-index: 0;
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
    cursor: pointer; font-family: var(--font); transition: background .15s, border-color .15s, color .15s, opacity .15s;
  }
  .sort-bar button:hover { color: var(--text); border-color: var(--text-dim); }
  .sort-bar button.active { background: var(--accent); border-color: var(--accent); color: #fff; }

  .tab-strip-wrapper { flex: 1; overflow: hidden; position: relative; }
  .tab-strip { display: flex; height: 100%; transition: transform .35s cubic-bezier(.16,1,.3,1); }
  .tab-panel { width: 100%; flex-shrink: 0; overflow-y: auto; }

  .session-list { height: 100%; overflow-y: auto; padding: 0 20px 8px; }

  /* ── Dashboard ── */
  .dashboard-panel { height: 100%; overflow-y: auto; padding: 12px 16px; }
  .dash-cards { margin-bottom: 16px; }
  .dash-card { display: flex; justify-content: space-between; align-items: center; padding: 10px 14px; background: var(--surface); border: 1px solid var(--border); border-radius: 6px; margin-bottom: 4px; }
  .dash-card .num { font-size: 18px; font-weight: 700; color: var(--text-bright); }
  .dash-card .lbl { font-size: 11px; color: var(--text-dim); }

  .dash-section { margin-bottom: 16px; }
  .dash-section h3 { font-size: 12px; color: var(--text-dim); text-transform: uppercase; letter-spacing: 0.6px; margin-bottom: 8px; border-bottom: 1px solid var(--border); padding-bottom: 4px; }

  .dash-active-item { display: flex; align-items: center; gap: 10px; padding: 8px 12px; background: var(--surface); border: 1px solid var(--border); border-radius: 6px; margin-bottom: 4px; cursor: pointer; transition: background .15s, box-shadow .4s ease-out; position: relative; transform-style: preserve-3d; }
  .dash-active-item:hover { background: var(--surface2); box-shadow: 0 12px 36px rgba(0,0,0,0.4); z-index: 10; }
  .dash-active-item .status-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
  .dash-active-item .status-dot.busy { background: #FD151B; animation: pulse-dot 1s ease-in-out infinite; }
  .dash-active-item .status-dot.idle { background: #7AFDD6; animation: none; }
  .dash-active-item .status-dot.plugin { background: #F00699; animation: none; }
  .dash-active-item .info { flex: 1; min-width: 0; }
  .dash-active-item .info .name { font-size: 13px; color: var(--text); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .dash-active-item .info .meta-wrap { margin-top: 2px; overflow: hidden; position: relative; }
  .dash-active-item .info .meta { display: inline-flex; gap: 4px; white-space: nowrap; }

  .dash-model-row { display: flex; align-items: center; gap: 10px; padding: 6px 0; font-size: 12px; border-bottom: 1px solid var(--border); }
  .dash-model-row:last-child { border-bottom: none; }
  .dash-model-row .mname { flex: 1; color: var(--text); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .dash-model-row .mtokens { width: 70px; text-align: right; color: var(--text-dim); flex-shrink: 0; font-size: 11px; }

  .dash-empty { color: var(--text-dim); font-size: 12px; padding: 8px 0; }

  .section-header {
    font-size: 12px; color: var(--text-dim); text-transform: uppercase;
    letter-spacing: 0.6px; margin-bottom: 8px; border-bottom: 1px solid var(--border);
    padding: 8px 12px 4px; user-select: none;
  }
  .session-list::-webkit-scrollbar { width: 5px; }
  .session-list::-webkit-scrollbar-thumb { background: var(--border); border-radius: 3px; }

  .session-card {
    display: flex; align-items: center; gap: 10px; padding: 8px 12px;
    background: var(--surface); border: 1px solid var(--border); border-radius: 6px;
    margin-bottom: 4px; cursor: pointer; transition: background .15s, box-shadow .4s ease-out;
    position: relative; transform-style: preserve-3d;
  }
  .session-card:hover {
    background: var(--surface2);
    box-shadow: 0 12px 36px rgba(0,0,0,0.4);
    z-index: 10;
  }
  .session-card.selected { background: var(--surface2); border-color: var(--accent); }
  .session-card .status-dot {
    width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0;
    background: var(--text-dim);
  }
  .session-card.active .status-dot { background: #7AFDD6; animation: pulse-dot 1.5s ease-in-out infinite; }
  .session-card.active .status-dot.busy { background: #FD151B; animation: pulse-dot 1s ease-in-out infinite; }
  .session-card.active .status-dot.idle { background: #7AFDD6; animation: none; }
  .session-card.active .status-dot.plugin { background: #F00699; animation: none; }
  @keyframes pulse-dot { 0%, 100% { opacity: 1; } 50% { opacity: 0.4; } }
  .session-card .info { flex: 1; min-width: 0; overflow: hidden; }
  .session-card .info .name {
    font-size: 13px; color: var(--text); white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  }
  .session-card .info .meta-wrap {
    margin-top: 2px; overflow: hidden; position: relative;
  }
  .session-card .info .meta {
    display: inline-flex; gap: 4px; white-space: nowrap; transition: transform .2s ease-out;
  }
  .meta-tag {
    display: inline-block; padding: 0 5px; border-radius: 3px; font-size: 10px;
    line-height: 16px; flex-shrink: 0;
  }
  .meta-tag.date { background: rgba(15,113,115,0.15); color: #0F7173; }
  .meta-tag.msgs { background: rgba(218,65,103,0.15); color: #DA4167; }
  .meta-tag.size { background: rgba(143,179,57,0.15); color: #8FB339; }
  .meta-tag.project { background: var(--tag-project-bg); color: var(--tag-project-color); }
  .session-card .card-actions {
    display: none; gap: 4px; flex-shrink: 0;
  }
  .session-card:hover .card-actions { display: flex; }
  .card-btn {
    display: flex; align-items: center; gap: 3px;
    padding: 3px 7px; border: 1px solid var(--border); border-radius: 4px;
    background: var(--surface); color: var(--text-dim); font-size: 11px;
    cursor: pointer; font-family: var(--font); transition: background .12s, border-color .12s, color .12s; white-space: nowrap;
  }
  .card-btn:hover { color: var(--text); border-color: var(--text-dim); }
  .card-btn.danger { background: var(--danger-bg); color: var(--danger); border-color: transparent; }
  .card-btn.danger:hover { background: var(--danger); color: #fff; border-color: var(--danger); }
  .card-btn.restore:hover { background: rgba(105,219,124,0.08); color: var(--success); border-color: var(--success); }

  /* ── Right Panel ── */
  .panel-right {
    flex: 1; min-width: 400px; display: flex; flex-direction: column; background: var(--bg); overflow: hidden; position: relative;
  }
  .panel-right.too-narrow .detail,
  .panel-right.too-narrow .empty-state,
  .panel-right.too-narrow .dashboard-panel { filter: grayscale(1) blur(4px); opacity: 0.3; pointer-events: none; }

  .narrow-alert-wrap {
    max-height: 0; overflow: hidden; transition: max-height .35s cubic-bezier(.16,1,.3,1);
  }
  .narrow-alert-wrap.show { max-height: 90px; }
  .narrow-alert {
    display: flex; align-items: center; gap: 10px;
    margin: 8px 12px 4px; padding: 10px 14px;
    background: var(--surface2); border: 1px solid var(--accent); border-radius: 6px;
    font-size: 12px; color: var(--text);
  }
  .narrow-alert p { flex: 1; margin: 0; }
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
    display: flex; align-items: flex-start; gap: 12px;
  }
  .detail-top-row .info-details { flex: 1; min-width: 0; cursor: default; padding-top: 2px; }
  .detail-top-row .detail-actions {
    display: flex; gap: 6px; flex-shrink: 0;
  }
  .info-summary {
    font-size: 16px; font-weight: 600; color: var(--text-bright);
    cursor: pointer; user-select: none; outline: none;
    white-space: nowrap; overflow-x: auto;
    margin-bottom: 6px;
    display: flex; align-items: center; gap: 8px;
    line-height: 26px;
  }
  .info-summary::-webkit-scrollbar { display: none; }
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
    font-size: 12px; font-family: var(--font); cursor: pointer; transition: background .12s, border-color .12s, color .12s, opacity .12s;
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
  .conversation-preview {
    flex: 1; overflow-y: auto; padding: 12px 20px;
  }
  .conversation-preview::-webkit-scrollbar { width: 5px; }
  .conversation-preview::-webkit-scrollbar-thumb { background: var(--border); border-radius: 3px; }

  .scroll-to-bottom {
    position: absolute; bottom: 16px; right: 16px;
    display: none; padding: 5px 14px; border-radius: 16px; border: 1px solid var(--border);
    background: var(--surface); color: var(--accent); font-size: 11px;
    font-family: var(--font); cursor: pointer; z-index: 10;
    box-shadow: 0 2px 8px rgba(0,0,0,0.2);
  }
  .scroll-to-bottom:hover { background: var(--surface2); border-color: var(--accent); }
  .scroll-to-bottom.show { display: block; }

  .match-nav {
    display: flex; align-items: center; gap: 4px; padding: 4px 14px;
    background: var(--surface2); border-bottom: 1px solid var(--border);
    font-size: 11px; color: var(--text-dim); font-family: var(--font); flex-shrink: 0;
  }
  .match-nav button {
    padding: 2px 8px; border: 1px solid var(--border); border-radius: 4px;
    background: var(--bg); color: var(--text); cursor: pointer; font-size: 11px; line-height: 1;
  }
  .match-nav button:hover { border-color: var(--accent); color: var(--accent); }
  #match-counter { flex: 1; }

  mark.search-highlight {
    background: #e01b84; color: #fff; border-radius: 2px; padding: 1px 2px; font-weight: 700;
  }

  .msg { margin-bottom: 12px; padding: 8px 12px; border-radius: 6px; font-size: 12px; line-height: 1.55; word-break: break-word; }
  .msg.user { background: var(--surface); border-left: 2px solid var(--accent); }
  .msg.assistant { background: var(--surface); border-left: 2px solid var(--success); }
  .msg.title { background: transparent; border-left: 2px solid var(--text-dim); font-style: italic; color: var(--text-dim); font-size: 11px; }
  .msg .role-label { font-size: 10px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 6px; }
  .msg.user .role-label { color: var(--accent); }
  .msg.assistant .role-label { color: var(--success); }
  .msg.title .role-label { color: var(--text-dim); }

  .msg.search-match { box-shadow: 0 0 0 2px var(--accent); border-radius: 6px; animation: match-pulse .6s ease-in-out 3; background: var(--surface2); }
  @keyframes match-pulse { 0%, 100% { box-shadow: 0 0 0 2px var(--accent); } 50% { box-shadow: 0 0 0 4px var(--accent), 0 0 8px var(--accent); } }

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

  /* Hide non-dialogue parts (thinking, tool use, tool result) */
  .hide-non-dialogue .part-thinking,
  .hide-non-dialogue .part-tool,
  .hide-non-dialogue .part-tool-result { display: none; }
  /* Also hide entire messages that have no conversation text */
  .hide-non-dialogue .msg.no-text { display: none; }

  .part-thinking { margin: 2px 0; }
  .part-thinking summary { cursor: pointer; color: var(--text-dim); font-size: 10px; font-weight: 500; user-select: none; opacity: 0.7; }
  .part-thinking summary:hover { opacity: 1; color: var(--text); }
  .part-thinking .thinking-content { color: var(--text-dim); font-style: italic; font-size: 11px; padding: 4px 8px; border-left: 2px solid var(--accent); margin-top: 2px; }

  .part-tool { background: rgba(196,148,74,0.06); border: 1px solid rgba(196,148,74,0.15); border-radius: 4px; padding: 6px 10px; margin: 4px 0; font-family: var(--mono); font-size: 11px; }
  .part-tool .tool-name { color: var(--accent); font-weight: 600; }
  .part-tool .tool-input { color: var(--text-dim); margin-top: 2px; white-space: pre-wrap; word-break: break-all; }
  .part-tool-result { background: rgba(196,148,74,0.04); border: 1px solid rgba(196,148,74,0.1); border-radius: 4px; padding: 4px 10px; margin: 2px 0; font-size: 11px; color: var(--text-dim); max-height: 80px; overflow-y: auto; }
  .part-tool-result.error { border-color: rgba(196,106,94,0.25); color: var(--danger); }

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
  <div style="display:flex;align-items:center;gap:12px">
    <button type="button" class="lang-btn" id="collapse-btn" onclick="togglePanel()" title="Toggle sidebar">&#9776;</button>
    <h1><span id="app-title">S.T.O.A.</span></h1>
  </div>
  <div class="header-right">
    <button type="button" class="lang-btn" onclick="newSession()" title="New chat" style="border-color:var(--accent);color:var(--accent)">+ <span data-i18n="newChat">New Chat</span></button>
    <button type="button" class="lang-btn" id="refresh-btn" onclick="hardReload()" title="Refresh">&#8635; <span data-i18n="refresh">Refresh</span></button>
    <div class="settings-wrap" id="settings-wrap">
      <button type="button" class="lang-btn" onclick="toggleSettings()"><span data-i18n="settingsBtn">Settings</span></button>
      <div class="settings-menu" id="settings-menu">
        <button type="button" onclick="toggleTheme();toggleSettings()"><span data-i18n="themeLabel">Theme</span></button>
        <button type="button" onclick="toggleLang();toggleSettings()"><span data-i18n="langLabel">Language</span></button>
        <button type="button" onclick="restartServer();toggleSettings()"><span data-i18n="restartBtn">Restart S.T.O.A.</span></button>
        <div class="settings-sep"></div>
        <div class="settings-info"><div>Server up since</div><div id="server-started-at">—</div></div>
      </div>
    </div>
  </div>
</header>

<div class="main">
  <!-- Left Panel -->
  <div class="panel-left">
    <div class="panel-left-inner">
    <div class="narrow-alert-wrap" id="narrow-alert-wrap">
      <div class="narrow-alert">
        <div>
          <p data-i18n="narrowHint1">预览窗过窄</p>
          <p data-i18n="narrowHint2">请调整浏览器宽度，或折叠左侧栏</p>
        </div>
      </div>
    </div>
    <div class="search-bar">
      <input type="text" id="search" name="search" autocomplete="off" data-i18n-placeholder="searchPlaceholder"
             oninput="onSearchInput()" autofocus>
      <button type="button" class="content-search-btn" id="content-search-btn"
              data-i18n="searchContent" onclick="contentSearch()">搜索会话内容</button>
    </div>
    <div class="search-result-info" id="search-result-info"></div>
    <div class="tab-bar">
      <div class="tab-indicator" id="tab-indicator"></div>
      <button type="button" class="active" data-tab="dashboard" onclick="switchTab('dashboard')">
        <span data-i18n="dashboardTab">Dashboard</span>
      </button>
      <button type="button" data-tab="list" onclick="switchTab('list')">
        <span data-i18n="listTab">Sessions</span>
      </button>
      <button type="button" data-tab="trash" onclick="switchTab('trash')">
        <span data-i18n="trashTab">Trash</span>
        <span class="badge" id="trash-badge" style="display:none">0</span>
      </button>
    </div>
    <div class="tab-strip-wrapper">
      <div class="tab-strip" id="tab-strip">
        <div class="tab-panel" id="tab-panel-dashboard">
          <div class="dashboard-panel" id="dashboard-panel"></div>
        </div>
        <div class="tab-panel" id="tab-panel-list">
          <div class="session-list" id="session-list"></div>
        </div>
        <div class="tab-panel" id="tab-panel-trash">
          <div class="session-list" id="trash-list"></div>
        </div>
      </div>
    </div>
    </div>
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
      <button type="button" class="btn" id="modal-cancel" onclick="closeModal()"><span data-i18n="cancel">Cancel</span></button>
      <button type="button" class="btn btn-danger" id="modal-confirm" onclick="modalCallback()"><span data-i18n="confirmDeleteBtn">Move to Trash</span></button>
    </div>
  </div>
</div>

<div class="toast-container" id="toast-container"></div>

<script>
// ═══════════════════════════════════════════════════════════════════
//  i18n
// ═══════════════════════════════════════════════════════════════════
const I18N = """ + json.dumps(I18N, ensure_ascii=False) + r""";
let LANG = (function(){ try { return localStorage.getItem('csm-lang'); } catch(e) {} return null; })() || 'zh';

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
  document.querySelectorAll('[data-i18n-title]').forEach(el => {
    el.title = t(el.getAttribute('data-i18n-title'));
  });
  document.getElementById('app-title').textContent = t('appTitle');
  // Update current detail view if any
  if (currentDetailType === 'session') updateSessionDetail();
  else if (currentDetailType === 'trash') updateTrashDetail();
  else updateEmptyState();
  // Re-render dashboard if active (it uses t() for dynamic i18n)
  if (currentTab === 'dashboard') renderDashboard();
}

function togglePanel() {
  document.querySelector('.panel-left')?.classList.toggle('collapsed');
  setTimeout(() => { checkNarrow(); moveTabIndicator(currentTab); }, 350);
}

// Detect when right panel is too narrow
function checkNarrow() {
  const pr = document.getElementById('panel-right');
  const alert = document.getElementById('narrow-alert-wrap');
  const pl = document.querySelector('.panel-left');
  if (!pr || !alert) return;
  const collapsed = pl && pl.classList.contains('collapsed');
  const panelWidth = parseInt(getComputedStyle(document.documentElement).getPropertyValue('--panel-left-width')) || 360;
  const leftW = collapsed ? 0 : panelWidth;
  const available = window.innerWidth - leftW;
  const tooNarrow = available < 400;
  pr.classList.toggle('too-narrow', tooNarrow);
  alert.classList.toggle('show', tooNarrow);
}
window.addEventListener('resize', () => { checkNarrow(); moveTabIndicator(currentTab); });

let THEME = (function(){ try { return localStorage.getItem('csm-theme'); } catch(e) {} return null; })() || 'warm';
function applyTheme() {
  document.documentElement.setAttribute('data-theme', THEME);
}
function toggleTheme() {
  THEME = THEME === 'warm' ? 'cool' : 'warm';
  try { localStorage.setItem('csm-theme', THEME); } catch(e) {}
  applyTheme();
}

function toggleSettings() {
  document.getElementById('settings-menu').classList.toggle('show');
}
document.addEventListener('click', e => {
  const wrap = document.getElementById('settings-wrap');
  if (wrap && !wrap.contains(e.target)) {
    document.getElementById('settings-menu').classList.remove('show');
  }
});

function toggleLang() {
  LANG = LANG === 'zh' ? 'en' : 'zh';
  try { localStorage.setItem('csm-lang', LANG); } catch(e) {}
  applyTheme();  // theme button text uses t()
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
let sortBy = 'time';
let currentTab = 'dashboard';
let contentMatchIds = null; // non-null when content search is active → filter by these IDs
let modalCallback = null;
let currentDetailType = null;

// ═══════════════════════════════════════════════════════════════════
//  API
// ═══════════════════════════════════════════════════════════════════
async function api(path, method = 'GET') {
  const res = await fetch(path, { method, cache: 'no-store' });
  return res.json();
}

// ═══════════════════════════════════════════════════════════════════
//  Init
// ═══════════════════════════════════════════════════════════════════
async function loadServerTime() {
  try {
    const s = await api('/api/status');
    document.getElementById('server-started-at').textContent = s.started_at;
  } catch(e) {}
}

function resolvePlaceholder(newSessions) {
  if (!window._placeholder) return;
  const prevIds = window._prevActiveIds || new Set();
  const realMatch = newSessions.find(s =>
    s.active && !prevIds.has(s.id) && !s._placeholder
  );
  if (realMatch) {
    window._placeholder = null;
    window._prevActiveIds = null;
    if (selectedId === '__placeholder__') selectedId = realMatch.id;
  } else {
    newSessions.unshift(window._placeholder);
  }
}

async function init() {
  applyTheme();
  sessions = await api('/api/sessions');
  trashItems = await api('/api/trash');
  renderList();
  loadDashboard();
  updateTrashBadge();
  loadServerTime();
  applyLang();
  moveTabIndicator('dashboard');

  // Auto-refresh every 2s
  setInterval(async () => {
    const newSessions = await api('/api/sessions');
    const newTrash = await api('/api/trash');
    resolvePlaceholder(newSessions);
    const changed = JSON.stringify(newSessions) !== JSON.stringify(sessions) ||
                    JSON.stringify(newTrash) !== JSON.stringify(trashItems);
    if (changed) {
      sessions = newSessions;
      trashItems = newTrash;
      updateTrashBadge();
      if (contentMatchIds !== null) {
        const q = (document.getElementById('search')?.value || '').trim();
        if (q) {
          try { contentMatchIds = await api(`/api/sessions/search?q=${encodeURIComponent(q)}`); }
          catch { /* keep existing results on error */ }
        }
      }
      renderList();
    }
    if (selectedId && currentTab === 'list') {
      refreshPreview(selectedId);
    } else if (selectedId && currentTab === 'trash') {
      selectTrashItem(selectedId);
    } else if (currentTab === 'dashboard') {
      loadDashboard();
    }
  }, 2000);
}
init();
setTimeout(checkNarrow, 500);

// ═══════════════════════════════════════════════════════════════════
//  Tab switching
// ═══════════════════════════════════════════════════════════════════
// ═══════════════════════════════════════════════════════════════════
//  Dashboard
// ═══════════════════════════════════════════════════════════════════
let dashboardData = null;

async function loadDashboard() {
  try { dashboardData = await api('/api/dashboard'); }
  catch { dashboardData = null; }
  renderDashboard();
}

function renderDashboard() {
  const panel = document.getElementById('dashboard-panel');
  if (!panel) return;
  const d = dashboardData;
  if (!d || !d.overview) { panel.innerHTML = `<p style="color:var(--text-dim);padding:20px">${t('loading')}</p>`; return; }

  const o = d.overview;
  const fmtTokens = (n) => n >= 1e6 ? (n/1e6).toFixed(1)+'M' : n >= 1e3 ? (n/1e3).toFixed(1)+'K' : String(n);
  const fmtUptime = (s) => {
    if (s < 60) return s+'s';
    if (s < 3600) return Math.floor(s/60)+'m';
    return Math.floor(s/3600)+'h '+Math.floor((s%3600)/60)+'m';
  };

  let html = '';

  // ── Overview Cards ──
  html += '<div class="dash-cards">';
  html += `<div class="dash-card"><div class="lbl">${t('totalSessions')}</div><div class="num">${o.total_sessions}</div></div>`;
  html += `<div class="dash-card"><div class="lbl">${t('activeSessions')}</div><div class="num">${o.active_sessions}</div></div>`;
  html += `<div class="dash-card"><div class="lbl">${t('totalMessages')}</div><div class="num">${o.total_messages.toLocaleString()}</div></div>`;
  html += `<div class="dash-card"><div class="lbl">${t('totalTokens')}</div><div class="num">${fmtTokens(o.total_tokens)}</div></div>`;
  html += '</div>';

  // ── Model Usage ──
  html += '<div class="dash-section"><h3>'+t('modelUsage')+'</h3>';
  if (d.model_stats.length === 0) {
    html += `<div class="dash-empty">${t('noData')}</div>`;
  } else {
    for (const m of d.model_stats) {
      html += `<div class="dash-model-row">`;
      html += `<span class="mname">${esc(m.model)}</span>`;
      html += `<span class="mtokens">${fmtTokens(m.tokens)}</span>`;
      html += `</div>`;
    }
  }
  html += '</div>';

  // ── Active Sessions Monitor ──
  html += '<div class="dash-section"><h3>'+t('activeSessions')+'</h3>';
  if (d.active_list.length === 0) {
    html += `<div class="dash-empty">${t('noData')}</div>`;
  } else {
    for (const a of d.active_list) {
      const s = a.status;
      const dotClass = s === 'busy' ? 'busy' : s === 'plugin' ? 'plugin' : 'idle';
      const statusLabel = s === 'busy' ? t('busyStatus') : s === 'plugin' ? t('pluginStatus') : t('idleStatus');
      const statusColor = s === 'busy' ? 'background:rgba(253,21,27,0.15);color:#FD151B'
        : s === 'plugin' ? 'background:rgba(240,0,105,0.15);color:#F00699'
        : 'background:rgba(122,253,214,0.15);color:#7AFDD6';
      html += renderSessionCard({
        cardClass: 'dash-active-item',
        dotClass: dotClass,
        title: a.title,
        dataId: a.id,
        onClick: `switchTab('list',true);selectedId='${a.id}';currentDetailType='session';reloadData().then(()=>{renderList();selectSession('${a.id}');})`,
        metaTags: [
          { cls: 'project', text: a.model },
          { style: statusColor, text: statusLabel },
          { cls: 'date', text: t('uptime') + ': ' + fmtUptime(a.uptime_seconds) },
        ]
      });
    }
  }
  html += '</div>';

  // ── Recent Activity ──
  html += '<div class="dash-section"><h3>'+t('recentActivity')+'</h3>';
  if (d.recent_sessions.length === 0) {
    html += `<div class="dash-empty">${t('noData')}</div>`;
  } else {
    for (const r of d.recent_sessions) {
      const ractive = d.active_list.find(a => a.id === r.id);
      const rdotClass = ractive ? ractive.status : '';
      const rdotStyle = ractive ? '' : 'background:var(--text-dim)';
      html += renderSessionCard({
        cardClass: 'dash-active-item',
        dotClass: rdotClass,
        dotStyle: rdotStyle,
        title: r.title,
        dataId: r.id,
        onClick: `switchTab('list',true);selectedId='${r.id}';currentDetailType='session';reloadData().then(()=>{renderList();selectSession('${r.id}');})`,
        metaTags: [
          { cls: 'project', text: r.model },
          { cls: 'date', text: r.last_time },
        ]
      });
    }
  }
  html += '</div>';

  panel.innerHTML = html;
}

const TAB_ORDER = { dashboard: 0, list: 1, trash: 2 };

function moveTabIndicator(tab) {
  const btn = document.querySelector(`[data-tab="${tab}"]`);
  const ind = document.getElementById('tab-indicator');
  if (!btn || !ind) return;
  ind.style.left = btn.offsetLeft + 'px';
  ind.style.width = btn.offsetWidth + 'px';
}

function switchTab(tab, keepSelection) {
  if (tab === currentTab) return;
  currentTab = tab;
  if (!keepSelection) selectedId = null;
  document.querySelectorAll('.tab-bar button').forEach(b => b.classList.remove('active'));
  document.querySelector(`[data-tab="${tab}"]`).classList.add('active');
  moveTabIndicator(tab);

  const strip = document.getElementById('tab-strip');
  if (strip) {
    strip.style.transform = `translateX(-${TAB_ORDER[tab] * 100}%)`;
  }

  if (tab === 'dashboard') {
    loadDashboard();
    updateEmptyState();
  } else {
    reloadData().then(() => { renderList(); if (!keepSelection) updateEmptyState(); });
  }
}

function hardReload() {
  const url = new URL(window.location.href);
  url.searchParams.set('_', Date.now());
  window.location.href = url.toString();
}

async function restartServer() {
  try { await api('/api/restart', 'POST'); } catch(e) { /* expected */ }
  setTimeout(() => { hardReload(); }, 1500);
}

async function refreshData() {
  sessions = await api('/api/sessions');
  trashItems = await api('/api/trash');
  resolvePlaceholder(sessions);

  updateTrashBadge();
  renderList();

  if (selectedId && currentTab === 'list') {
    selectSession(selectedId);
  } else if (selectedId && currentTab === 'trash') {
    selectTrashItem(selectedId);
  }
}

async function reloadData() {
  if (currentTab === 'list') {
    sessions = await api('/api/sessions');
  } else if (currentTab === 'trash') {
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
//  Search
// ═══════════════════════════════════════════════════════════════════
function onSearchInput() {
  // Clear content search when user types (back to fast filter mode)
  if (contentMatchIds !== null) {
    contentMatchIds = null;
    const btn = document.getElementById('content-search-btn');
    if (btn) { btn.classList.remove('active'); btn.textContent = t('searchContent'); }
    const info = document.getElementById('search-result-info');
    if (info) info.classList.remove('show');
  }
  renderList();
}

async function contentSearch() {
  const input = document.getElementById('search');
  const query = (input?.value || '').trim();
  const btn = document.getElementById('content-search-btn');
  const info = document.getElementById('search-result-info');

  if (contentMatchIds !== null) {
    // Toggle off: already in content search mode, switch back
    contentMatchIds = null;
    if (btn) { btn.classList.remove('active'); btn.textContent = t('searchContent'); }
    if (info) info.classList.remove('show');
    renderList();
    return;
  }

  if (!query) return;

  if (btn) {
    btn.textContent = '⏳';
    btn.classList.add('active');
  }
  if (info) { info.textContent = t('loading'); info.classList.add('show'); }

  const t0 = Date.now();
  try {
    contentMatchIds = await api(`/api/sessions/search?q=${encodeURIComponent(query)}`);
  } catch {
    contentMatchIds = [];
  }

  // Ensure loading indicator shows for at least 300ms
  const elapsed = Date.now() - t0;
  if (elapsed < 300) await new Promise(r => setTimeout(r, 300 - elapsed));

  // Always keep active state — show result count
  const count = contentMatchIds ? contentMatchIds.length : 0;
  if (btn) {
    btn.classList.add('active');
    btn.textContent = count > 0 ? `${t('searchContent')} (${count})` : t('searchContent');
    btn.title = count > 0
      ? t('searchContentFound').replace('{n}', count)
      : t('searchContentNone');
  }
  if (info) {
    info.textContent = count > 0
      ? t('searchContentFound').replace('{n}', count)
      : t('searchContentNone');
    info.classList.add('show');
  }
  renderList();

  // Flash the session list to signal results
  const list = document.getElementById('session-list');
  if (list) { list.style.transition = 'opacity .1s'; list.style.opacity = '0.5'; requestAnimationFrame(() => { list.style.opacity = '1'; }); }
}

// Shared card renderer — used by session list, dashboard active/recent, and trash.
// All four contexts share the same DOM structure; only data fields and actions differ.
function renderSessionCard(opts) {
  // opts: { cardClass, extraClasses, dotClass, dotStyle, title, dataId, onClick, metaTags, actionsHtml }
  const dotHtml = opts.dotClass !== undefined
    ? `<div class="status-dot${opts.dotClass ? ' ' + opts.dotClass : ''}"${opts.dotStyle ? ` style="${opts.dotStyle}"` : ''}></div>`
    : '';
  const tagsHtml = (opts.metaTags || []).map(t => {
    const cls = t.cls ? `meta-tag ${t.cls}` : 'meta-tag';
    const style = t.style ? ` style="${t.style}"` : '';
    return `<span class="${cls}"${style}>${esc(t.text)}</span>`;
  }).join('');
  const actionsHtml = opts.actionsHtml ? `<div class="card-actions">${opts.actionsHtml}</div>` : '';
  const cls = opts.cardClass + (opts.extraClasses || '');
  return `<div class="${cls}" data-id="${opts.dataId}" onclick="${opts.onClick}">
    ${dotHtml}
    <div class="info">
      <div class="name">${esc(opts.title)}</div>
      <div class="meta-wrap"><div class="meta">${tagsHtml}</div></div>
    </div>
    ${actionsHtml}
  </div>`;
}

// ═══════════════════════════════════════════════════════════════════
//  Render List
// ═══════════════════════════════════════════════════════════════════
function renderList() {
  const query = (document.getElementById('search')?.value || '').toLowerCase();

  // ── Session list panel ──
  const listContainer = document.getElementById('session-list');
  if (listContainer) {
    let filtered = sessions.filter(s => {
      if (contentMatchIds !== null) return contentMatchIds.includes(s.id);
      if (!query) return true;
      return (s.title || '').toLowerCase().includes(query)
        || (s.project || '').toLowerCase().includes(query)
        || (s.model || '').toLowerCase().includes(query)
        || (s.id || '').toLowerCase().includes(query)
        || (s.date || '').toLowerCase().includes(query);
    });

    const actives = filtered.filter(s => s.active);
    actives.sort((a, b) => b.mtime - a.mtime);

    const sorted = [...filtered];
    if (sortBy === 'time') sorted.sort((a, b) => b.mtime - a.mtime);
    else if (sortBy === 'size') sorted.sort((a, b) => b.size_bytes - a.size_bytes);
    else if (sortBy === 'messages') sorted.sort((a, b) => b.messages - a.messages);

    const renderCard = (s) => renderSessionCard({
      cardClass: 'session-card',
      extraClasses: (s.id === selectedId ? ' selected' : '') + (s.active ? ' active' : ''),
      dotClass: s.status || '',
      title: s.title,
      dataId: s.id,
      onClick: `selectSession('${s.id}')`,
      metaTags: [
        { cls: 'date', text: s.date },
        { cls: 'msgs', text: s.messages + ' msgs' },
        { cls: 'size', text: s.size },
        { cls: 'project', text: s.project },
      ],
      actionsHtml: `<button type="button" class="card-btn danger" onclick="event.stopPropagation(); ${s.active ? `askStopSession('${s.id}')` : `askDeleteSession('${s.id}')`}">&#x2715; ${s.active ? t('stop') : t('delete')}</button>`
    });

    let html = '';
    if (actives.length > 0) {
      html += `<div class="section-header">${t('activeSessions')}</div>`;
      html += actives.map(renderCard).join('');
    }
    html += `<div class="sort-bar" id="sort-bar" style="padding:4px 12px 8px">
      <button type="button" class="${sortBy==='time'?'active':''}" data-sort="time" onclick="setSort('time', this)">${t('sortTime')}</button>
      <button type="button" class="${sortBy==='size'?'active':''}" data-sort="size" onclick="setSort('size', this)">${t('sortSize')}</button>
      <button type="button" class="${sortBy==='messages'?'active':''}" data-sort="messages" onclick="setSort('messages', this)">${t('sortMessages')}</button>
    </div>`;
    html += `<div class="section-header">${t('allSessions')}</div>`;
    html += sorted.map(renderCard).join('');
    listContainer.innerHTML = html;
  }

  // ── Trash panel ──
  const trashContainer = document.getElementById('trash-list');
  if (trashContainer) {
    let filtered = trashItems.filter(item => {
      if (!query) return true;
      return (item.title || '').toLowerCase().includes(query)
        || (item.id || '').toLowerCase().includes(query);
    });

    if (filtered.length === 0) {
      trashContainer.innerHTML = `<div style="padding:40px;text-align:center;color:var(--text-dim);font-size:13px">${t('trashEmpty')}</div>`;
    } else {
      trashContainer.innerHTML = filtered.map(item => renderSessionCard({
        cardClass: 'session-card',
        extraClasses: item.id === selectedId ? ' selected' : '',
        title: item.title,
        dataId: item.id,
        onClick: `selectTrashItem('${item.id}')`,
        metaTags: [
          { cls: 'date', text: item.date },
          { cls: 'msgs', text: item.messages + ' msgs' },
          { cls: 'size', text: item.size },
          { style: 'background:rgba(240,160,48,0.15);color:#f0a030', text: t('deletedAt') + ': ' + item.deleted_at },
        ],
        actionsHtml: `<button type="button" class="card-btn restore" onclick="event.stopPropagation(); askRestore('${item.id}')">&#8634; ${t('restore')}</button><button type="button" class="card-btn danger" onclick="event.stopPropagation(); askPermDelete('${item.id}')">&#x2715; ${t('permDelete')}</button>`
      })).join('');
    }
  }
}

function esc(str) {
  const div = document.createElement('div');
  div.textContent = str || '';
  return div.innerHTML;
}

// Check if a message has any text-type part (actual conversation)
function hasTextPart(parts) {
  return parts && parts.some(p => p.type === 'text');
}

// Highlight search query in escaped HTML text.
// Uses split-then-esc approach to avoid entity issues.
function highlightText(text, query) {
  if (!query || !text) return esc(text);
  const escapedQuery = query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const regex = new RegExp(`(${escapedQuery})`, 'gi');
  const parts = String(text).split(regex);
  return parts.map((part, i) => {
    if (i % 2 === 1) return `<mark class="search-highlight">${esc(part)}</mark>`;
    return esc(part);
  }).join('');
}

function renderParts(parts, query) {
  if (!parts || parts.length === 0) return '';
  return parts.map(p => {
    switch (p.type) {
      case 'text':
        return `<div class="part-text">${renderMarkdown(p.content, query)}</div>`;
      case 'thinking':
        const thinkId = 'think-' + (++window._thinkCounter || (window._thinkCounter = 1));
        return `<details class="part-thinking">
          <summary>💭 Thinking</summary>
          <div class="thinking-content">${highlightText(p.content, query)}</div>
        </details>`;
      case 'tool_use':
        return `<div class="part-tool">
          <div class="tool-name">⚙ ${esc(p.name)}</div>
          ${p.input ? `<div class="tool-input">${highlightText(p.input, query)}</div>` : ''}
        </div>`;
      case 'tool_result':
        return `<div class="part-tool-result${p.is_error ? ' error' : ''}">${highlightText(String(p.content), query)}</div>`;
      case 'title':
        return `<em>${highlightText(p.content, query)}</em>`;
      default:
        return esc(String(p.content || ''));
    }
  }).join('');
}

function renderMarkdown(str, query) {
  // Always escape first, then process markdown on clean text
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

  // Apply search highlight BEFORE markdown on escaped text
  if (query) {
    const escapedQuery = query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    html = html.replace(new RegExp(escapedQuery, 'gi'), '<mark class="search-highlight">$&</mark>');
  }

  // Apply markdown rules to text (won't touch <mark> tags since they use angle brackets)
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

function toggleNonDialogue() {
  const detail = document.querySelector('.detail');
  const btn = document.getElementById('toggle-non-dialogue-btn');
  if (!detail || !btn) return;
  const hidden = detail.classList.toggle('hide-non-dialogue');
  btn.textContent = hidden ? t('showNonDialogue') : t('hideNonDialogue');
}

// ═══════════════════════════════════════════════════════════════════
//  Search Match Navigation
// ═══════════════════════════════════════════════════════════════════
function updateMatchCounter() {
  const counter = document.getElementById('match-counter');
  const total = window._matchEls ? window._matchEls.length : 0;
  if (counter) {
    counter.textContent = total > 0 ? `${window._matchIdx + 1} / ${total}` : '0 / 0';
  }
}

function navigateMatch(dir) {
  // dir: 1 = next, -1 = prev
  if (!window._matchEls || window._matchEls.length === 0) return;
  window._matchIdx += dir;
  if (window._matchIdx >= window._matchEls.length) window._matchIdx = 0;
  if (window._matchIdx < 0) window._matchIdx = window._matchEls.length - 1;
  window._matchEls[window._matchIdx].scrollIntoView({ block: 'center', behavior: 'smooth' });
  updateMatchCounter();
}

// ═══════════════════════════════════════════════════════════════════
//  Session Detail (list tab)
// ═══════════════════════════════════════════════════════════════════
async function selectSession(id) {
  selectedId = id;
  currentDetailType = 'session';
  renderList();

  const s = sessions.find(s => s.id === id);
  if (!s) return;

  const searchQuery = (contentMatchIds !== null) ? (document.getElementById('search')?.value || '').trim() : '';

  const panel = document.getElementById('panel-right');
  panel.innerHTML = `
    <div class="detail hide-non-dialogue">
      <div class="detail-header">
        <div class="detail-top-row">
          <details class="info-details">
            <summary class="info-summary"><span class="info-toggle-icon">▶</span> <span>${esc(s.title)}</span></summary>
            <div class="info-grid">
            <span class="label">${t('sessionId')}</span><span class="value">${s.id}</span>
            <span class="label">${t('project')}</span><span class="value">${esc(s.project)}</span>
            <span class="label">${t('branch')}</span><span class="value">${esc(s.branch) || '—'}</span>
            <span class="label">${t('model')}</span><span class="value">${esc(s.model) || '—'}</span>
            <span class="label">${t('messages')}</span><span class="value">${s.messages} (${s.turns} ${t('turns')})</span>
            <span class="label">${t('tokens')}</span><span class="value">${(s.tokens || 0).toLocaleString()}</span>
            <span class="label">${t('lastActive')}</span><span class="value">${s.last_time || s.date}</span>
            <span class="label">${t('size')}</span><span class="value">${s.size}</span>
          </div>
          </details>
          <div class="detail-actions">
            <button type="button" class="btn" id="toggle-non-dialogue-btn" onclick="toggleNonDialogue()" style="color:var(--text-dim);border-color:var(--border)">${t('showNonDialogue')}</button>
            ${s.active ? `<button type="button" class="btn" onclick="askRestartSession('${s.id}')" style="color:var(--warn);border-color:var(--warn)">&#8635; ${t('restart')}</button>` : ''}
            ${s.active ? '' : `<button type="button" class="btn" onclick="resumeSession('${s.id}')" style="color:var(--accent);border-color:var(--accent)">&#9654; ${t('resume')}</button>`}
            <button type="button" class="btn btn-danger" id="detail-delete-btn" onclick="${s.active ? `askStopSession('${s.id}')` : `askDeleteSession('${s.id}')`}">&#x2715; ${s.active ? t('stop') : t('delete')}</button>
          </div>
        </div>
      </div>
      ${searchQuery ? `<div class="match-nav" id="match-nav"><span id="match-counter"></span><button type="button" onclick="navigateMatch(-1)" data-i18n-title="prevMatch">▲</button><button type="button" onclick="navigateMatch(1)" data-i18n-title="nextMatch">▼</button></div>` : ''}
      <div class="conversation-preview" id="conversation-preview" onscroll="updateScrollButton()">${t('loading')}</div>
      <button type="button" class="scroll-to-bottom" id="scroll-to-bottom-btn" onclick="scrollToLatest()">↓ ${t('scrollToBottom')}</button>
    </div>
  `;

  try {
    const qs = searchQuery ? `?q=${encodeURIComponent(searchQuery)}` : '';
    const data = await api(`/api/sessions/${id}/preview${qs}`);
    // Handle new dict format: {messages: [...], first_match_line: N}
    const msgs = Array.isArray(data) ? data : (data.messages || []);
    const firstMatchLine = Array.isArray(data) ? 0 : (data.first_match_line || 0);

    const preview = document.getElementById('conversation-preview');
    if (!msgs || msgs.length === 0) {
      preview.innerHTML = `<p style="color:var(--text-dim);padding:20px;text-align:center">${t('noMessages')}</p>`;
      return;
    }
    preview.innerHTML = msgs.map(m => `
      <div class="msg ${m.role}${m._match ? ' search-match' : ''}${!hasTextPart(m.parts) ? ' no-text' : ''}" data-line="${m._line || ''}">
        <div class="role-label">${m.role === 'title' ? 'TITLE' : m.role.toUpperCase()}</div>
        ${renderParts(m.parts || [], searchQuery)}
      </div>
    `).join('');
    // Track last line number for incremental refresh
    const lastMsg = msgs[msgs.length - 1];
    window._lastLine = lastMsg ? (lastMsg._line || 0) : 0;

    // Navigation state for match jumping
    window._matchEls = preview.querySelectorAll('.msg.search-match');
    window._matchIdx = -1;

    // Update counter & navigate to first match if in content search mode
    if (searchQuery) {
      updateMatchCounter();
      navigateMatch(1); // jump to first match
    } else {
      quickScrollToBottom(preview, 200);
    }
  } catch (e) {
    document.getElementById('conversation-preview').innerHTML = `<p style="color:var(--danger);padding:20px">${t('loadFailed')}</p>`;
  }
}

async function refreshPreview(id) {
  const container = document.getElementById('conversation-preview');
  if (!container) return;
  try {
    const afterLine = window._lastLine || 0;
    const searchQuery = (contentMatchIds !== null) ? (document.getElementById('search')?.value || '').trim() : '';
    const queryPart = searchQuery ? `&q=${encodeURIComponent(searchQuery)}` : '';
    const data = await api(`/api/sessions/${id}/preview?after=${afterLine}${queryPart}`);
    const msgs = Array.isArray(data) ? data : (data.messages || []);
    if (!msgs || msgs.length === 0) return;
    // Update last line tracker
    window._lastLine = msgs[msgs.length - 1]._line || afterLine;
    // Append only — never rebuild, never disrupt scroll
    const btn = document.getElementById('scroll-to-bottom-btn'); const atBottom = !btn || !btn.classList.contains('show');
    container.insertAdjacentHTML('beforeend', msgs.map(m => `
      <div class="msg ${m.role}${m._match ? ' search-match' : ''}${!hasTextPart(m.parts) ? ' no-text' : ''}" data-line="${m._line || ''}">
        <div class="role-label">${m.role === 'title' ? 'TITLE' : m.role.toUpperCase()}</div>
        ${renderParts(m.parts || [], searchQuery)}
      </div>
    `).join(''));
    if (atBottom) container.scrollTop = container.scrollHeight;
    updateScrollButton();
    // Refresh match navigation state for any newly appended matches
    if (searchQuery) {
      window._matchEls = container.querySelectorAll('.msg.search-match');
      updateMatchCounter();
    }
  } catch (e) { console.error('refreshPreview failed:', e); }
}

function updateScrollButton() {
  const container = document.getElementById('conversation-preview');
  const btn = document.getElementById('scroll-to-bottom-btn');
  if (!container || !btn) return;
  const atBottom = container.scrollTop + container.clientHeight >= container.scrollHeight - 50;
  if (atBottom) {
    btn.classList.remove('show');
  } else {
    btn.classList.add('show');
  }
}

function quickScrollToBottom(container, duration) {
  // Cancel any in-flight scroll animation on this container
  if (container._scrollRafId) { cancelAnimationFrame(container._scrollRafId); container._scrollRafId = null; }
  const start = container.scrollTop;
  const end = container.scrollHeight - container.clientHeight;
  const startTime = performance.now();
  function step(now) {
    const elapsed = now - startTime;
    const progress = Math.min(elapsed / duration, 1);
    const eased = 1 - Math.pow(1 - progress, 3);
    container.scrollTop = start + (end - start) * eased;
    if (progress < 1) container._scrollRafId = requestAnimationFrame(step);
  }
  container._scrollRafId = requestAnimationFrame(step);
}

function scrollToLatest() {
  const container = document.getElementById('conversation-preview');
  if (container) {
    container.scrollTo({ top: container.scrollHeight, behavior: 'smooth' });
    container.addEventListener('scrollend', updateScrollButton, { once: true });
  }
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
          <button type="button" class="btn btn-restore" onclick="askRestore('${item.id}')">&#8634; ${t('restore')}</button>
          <button type="button" class="btn btn-danger" onclick="askPermDelete('${item.id}')">&#x2715; ${t('permDelete')}</button>
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
    // Remember which sessions are already active, so we can identify the new one
    window._prevActiveIds = new Set(sessions.filter(s => s.active).map(s => s.id));
    const res = await api('/api/new-session', 'POST');
    if (res.success) {
      toast(t('newChatStarted'), 'success');
      // Store placeholder globally so refreshData preserves it
      window._placeholder = {
        id: '__placeholder__',
        title: t('newSessionPlaceholder'),
        active: true,
        date: t('newSessionPlaceholder'),
        messages: 0,
        turns: 0,
        tokens: 0,
        size: '—',
        size_bytes: 0,
        mtime: Date.now() / 1000,
        last_time: '',
        model: '',
        cwd: '',
        branch: '',
        project: '~',
        _placeholder: true,
      };
      sessions.unshift(window._placeholder);
            renderList(); loadDashboard();
    } else {
      toast(res.message || t('failed'), 'error');
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
      // Immediately mark active + re-render detail with Stop button
      const s = sessions.find(s => s.id === id);
      if (s) s.active = true;
      renderList();
      if (selectedId === id) selectSession(id);
      // Full server refresh after 2s for accuracy
      setTimeout(async () => {
        sessions = await api('/api/sessions');
        trashItems = await api('/api/trash');
                updateTrashBadge();
        renderList(); loadDashboard();
        if (selectedId) selectSession(selectedId);
      }, 2000);
    } else {
      toast(res.message || t('failed'), 'error');
    }
  } catch (e) {
    toast(e.message, 'error');
  }
}

// ═══════════════════════════════════════════════════════════════════
//  Stop Session
// ═══════════════════════════════════════════════════════════════════
function askRestartSession(id) {
  const s = sessions.find(s => s.id === id);
  const body = `${t('restartConfirmMsg')}<br><br><b class="highlight">${esc(s?.title || id)}</b>`;
  showModal(t('restartConfirmTitle'), body, t('confirmRestartBtn'), 'danger', async () => {
    closeModal();
    try {
      const res = await api(`/api/sessions/${id}/restart`, 'POST');
      if (res.success) {
        sessions = await api('/api/sessions');
        renderList(); loadDashboard();
        if (selectedId === id) selectSession(id);
        toast(t('restarted'), 'success');
      } else {
        toast(res.message || t('failed'), 'error');
      }
    } catch (e) {
      toast(e.message, 'error');
    }
  });
}

function askStopSession(id) {
  const s = sessions.find(s => s.id === id);
  const body = `${t('stopConfirmMsg')}<br><br><b class="highlight">${esc(s?.title || id)}</b>`;

  showModal(t('stopConfirmTitle'), body, t('confirmStopBtn'), 'danger', async () => {
    closeModal();
    try {
      const res = await api(`/api/sessions/${id}/stop`, 'POST');
      if (res.success) {
        sessions = await api('/api/sessions');
        renderList(); loadDashboard();
        if (selectedId === id) selectSession(id);
        toast(t('stopped'), 'success');
      } else {
        toast(res.message || t('failed'), 'error');
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
                updateTrashBadge();
        renderList(); loadDashboard();
        toast(t('deleted'), 'success');
      } else {
        toast(res.message || t('failed'), 'error');
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
                updateTrashBadge();
        renderList(); loadDashboard();
        toast(t('restored'), 'success');
      } else {
        toast(res.message || t('failed'), 'error');
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
        renderList(); loadDashboard();
        toast(t('permDeleted'), 'success');
      } else {
        toast(res.message || t('failed'), 'error');
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

// macOS Dock-style meta scroll + Steam card tilt
function bindCardTilt(container) {
  if (!container) return;
  container.addEventListener('mousemove', e => {
    const card = e.target.closest('.session-card, .dash-active-item');
    if (!card) return;
    // Meta scroll
    const meta = card.querySelector('.meta');
    const wrap = card.querySelector('.meta-wrap');
    if (meta && wrap) {
      const overflow = meta.scrollWidth - wrap.clientWidth;
      if (overflow > 0) {
        const rect = card.getBoundingClientRect();
        const rawPct = (e.clientX - rect.left) / rect.width;
        const pct = rawPct < 0.30 ? 0 : (rawPct - 0.30) / 0.70;
        meta.style.transform = `translateX(${-(overflow + 40) * pct}px)`;
      }
    }
    // Card tilt — follows cursor like a floating card
    const r = card.getBoundingClientRect();
    const cx = (e.clientX - r.left) / r.width - 0.5;
    const cy = (e.clientY - r.top) / r.height - 0.5;
    card.style.transform = `perspective(400px) rotateY(${cx * 12}deg) rotateX(${-cy * 8}deg) scale(1.04)`;
  });
  container.addEventListener('mouseout', e => {
    const card = e.target.closest('.session-card, .dash-active-item');
    if (!card) return;
    if (card.contains(e.relatedTarget)) return;
    const meta = card.querySelector('.meta');
    if (meta) meta.style.transform = '';
    card.style.transform = '';
  });
}
bindCardTilt(document.getElementById('session-list'));
bindCardTilt(document.getElementById('trash-list'));
bindCardTilt(document.getElementById('dashboard-panel'));
</script>
</body>
</html>"""


# ═══════════════════════════════════════════════════════════════════════
#  HTTP 服务器 — 纯 Python 标准库实现，路由分发与 API 处理
# ═══════════════════════════════════════════════════════════════════════

class RequestHandler(http.server.BaseHTTPRequestHandler):
    """HTTP 请求处理器：RESTful API 路由 + 静态前端页面"""

    def log_message(self, format, *args):
        pass  # 静默模式，不输出请求日志

    # ── 路由分发 ────────────────────────────────────────────────────

    def do_GET(self):
        """GET 请求路由"""
        path = urllib.parse.urlparse(self.path).path

        if path == "/":
            return self._serve_html()
        elif path == "/api/sessions":
            return self._json(SessionManager.list_all())
        elif path == "/api/dashboard":
            return self._json(SessionManager.get_dashboard())
        elif path.startswith("/api/sessions/") and path.endswith("/preview"):
            # 获取会话预览内容，支持增量刷新（after_line）和搜索（q）
            session_id = path.rsplit("/", 2)[-2]
            qs = urllib.parse.urlparse(self.path).query
            params = urllib.parse.parse_qs(qs)
            try: after_line = int(params.get("after", [0])[0])
            except (ValueError, IndexError): after_line = 0
            query = params.get("q", [None])[0]
            filepath = self._find_session_path(session_id)
            return self._json(SessionManager.get_preview(filepath, after_line=after_line, query=query)) if filepath else self._error(404, "Not found")
        elif path == "/api/sessions/search":
            # 全文搜索：用 grep 在所有会话 JSONL 文件中搜索关键词
            qs = urllib.parse.urlparse(self.path).query
            params = urllib.parse.parse_qs(qs)
            query = params.get("q", [""])[0]
            return self._search_content(query)
        elif path == "/api/trash":
            return self._json(SessionManager.list_trash())
        elif path == "/api/status":
            return self._json({"status": "ok", "started_at": SERVER_STARTED_AT})
        else:
            return self._error(404, "Not found")

    def do_DELETE(self):
        """DELETE 请求路由"""
        path = urllib.parse.urlparse(self.path).path

        if path.startswith("/api/sessions/"):
            # 删除会话 → 移入回收站
            session_id = path.rsplit("/", 1)[-1]
            filepath = self._find_session_path(session_id)
            if not filepath:
                return self._error(404, "Session not found")
            success, msg = SessionManager.move_to_trash(filepath)
            return self._json({"success": success, "message": msg})
        elif path.startswith("/api/trash/"):
            # 彻底删除回收站中的会话
            session_id = path.rsplit("/", 1)[-1]
            success, msg = SessionManager.delete_permanently(session_id)
            return self._json({"success": success, "message": msg})
        else:
            return self._error(404, "Not found")

    def do_POST(self):
        """POST 请求路由"""
        path = urllib.parse.urlparse(self.path).path

        if path.startswith("/api/trash/") and path.endswith("/restore"):
            # 从回收站恢复会话
            session_id = path.rsplit("/", 2)[-2]
            success, msg = SessionManager.restore_from_trash(session_id)
            return self._json({"success": success, "message": msg})
        elif path.startswith("/api/sessions/") and path.endswith("/resume"):
            # 继续会话：在新终端窗口运行 claude --resume
            session_id = path.rsplit("/", 2)[-2]
            return self._resume_session(session_id)
        elif path.startswith("/api/sessions/") and path.endswith("/stop"):
            # 停止会话：kill 对应 PID 的 Claude 进程
            session_id = path.rsplit("/", 2)[-2]
            return self._stop_session(session_id)
        elif path.startswith("/api/sessions/") and path.endswith("/restart"):
            # 重启会话：先 kill 再 resume
            session_id = path.rsplit("/", 2)[-2]
            return self._restart_session(session_id)
        elif path == "/api/new-session":
            # 新建会话：打开终端运行 claude
            return self._new_session()
        elif path == "/api/restart":
            return self._restart_server()
        else:
            return self._error(404, "Not found")

    def do_OPTIONS(self):
        """CORS 预检请求处理"""
        self.send_response(200)
        self.end_headers()

    # ── 响应辅助方法 ────────────────────────────────────────────

    def _serve_html(self):
        """返回内嵌的单页 Web 应用"""
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        self.end_headers()
        self.wfile.write(FRONTEND.encode("utf-8"))

    def _json(self, data):
        """返回 JSON 格式响应"""
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8"))

    def _error(self, code, msg):
        """返回错误响应"""
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"error": msg}).encode("utf-8"))

    def _search_content(self, query):
        """使用 grep 在所有会话 JSONL 文件中全文搜索关键词。
        返回包含匹配文本的会话 ID 列表。
        优点：基于 grep 的纯文本搜索，比逐文件 Python 解析快 10x+。"""
        if not query or not query.strip():
            return self._json([])
        # 使用 subprocess.run 的列表形式，自动处理参数转义，防止注入
        pattern = query.strip()
        try:
            result = subprocess.run(
                ["grep", "-rIlF", "--", pattern, CLAUDE_PROJECTS_DIR],
                # -r: 递归    -I: 忽略二进制    -l: 只输出文件名    -F: 固定字符串（非正则）
                capture_output=True, text=True, timeout=10
            )
            if result.returncode not in (0, 1):  # 0=找到匹配, 1=未找到
                return self._json([])
            # 从文件路径中提取会话 ID（UUID 格式，36 字符）
            ids = []
            for line in result.stdout.strip().split("\n"):
                if line:
                    name = Path(line).stem  # 去掉 .jsonl 扩展名
                    if len(name) == 36:  # 标准 UUID 长度
                        ids.append(name)
            return self._json(list(set(ids)))  # 去重
        except subprocess.TimeoutExpired:
            return self._json([])
        except (OSError, ValueError) as e:
            return self._json({"error": str(e)})

    @staticmethod
    def _run_osascript(cwd, claude_args):
        """通过 AppleScript 在 Terminal 中运行 claude 命令。"""
        safe_cwd = cwd.replace('\\', '\\\\').replace('"', '\\"')
        if claude_args:
            safe_args = claude_args.replace('\\', '\\\\').replace('"', '\\"')
        else:
            safe_args = ""
        script = f'''
            tell application "Terminal"
                do script "cd \\"{safe_cwd}\\" && claude {safe_args}"
                activate
            end tell
        '''
        subprocess.run(["osascript", "-e", script], check=True, capture_output=True, text=True)

    def _new_session(self):
        """通过 AppleScript 打开新 Terminal 窗口启动全新 Claude Code 会话。"""
        try:
            self._run_osascript(os.path.expanduser("~"), "")
            return self._json({"success": True, "message": "Starting new session"})
        except subprocess.CalledProcessError as e:
            return self._json({"success": False, "message": f"Failed to launch: {e.stderr.strip()}"})

    def _restart_server(self):
        """重启 S.T.O.A. 服务：先关闭监听 socket 释放端口，再启动新进程，然后退出。"""
        script_path = os.path.realpath(__file__)
        env = os.environ.copy()
        env["CSM_NO_BROWSER"] = "1"
        # 先响应客户端，再处理重启
        self._json({"success": True, "message": "Restarting..."})
        self.wfile.flush()
        started = False
        try:
            self.server.server_close()
            with open("/tmp/claude-session-manager.log", "a") as log_file:
                subprocess.Popen(
                    [sys.executable, script_path],
                    stdin=subprocess.DEVNULL, stdout=log_file, stderr=log_file,
                    start_new_session=True, env=env, close_fds=True
                )
            started = True
        finally:
            if started:
                os._exit(0)

    def _kill_pid(self, pid, poll_exit=False):
        """发送 kill 信号并可选轮询确认退出。返回 (success, message)。"""
        try:
            result = subprocess.run(["kill", str(pid)], capture_output=True, timeout=3)
        except subprocess.TimeoutExpired:
            return False, "Process did not respond — try again"
        except (OSError, ValueError, subprocess.SubprocessError) as e:
            return False, str(e)
        # kill 返回非零时检查是否为「进程不存在」
        if result.returncode != 0:
            if b"No such process" in result.stderr:
                return True, "Already stopped"
            return False, result.stderr.decode().strip() or "Failed to stop"
        # 轮询确认进程退出
        if poll_exit:
            deadline = time.time() + 3
            while time.time() < deadline:
                try:
                    os.kill(pid, 0)
                except OSError:
                    break
                time.sleep(0.1)
            else:
                return False, "Process did not exit — try stop first"
        return True, "Stopped"

    def _restart_session(self, session_id):
        """重启会话：先发送 kill 信号终止进程，确认退出后再恢复。"""
        SessionManager._get_active_session_ids()
        pid = SessionManager._session_pid_cache.get(session_id)
        if pid:
            ok, msg = self._kill_pid(pid, poll_exit=True)
            if not ok:
                return self._json({"success": False, "message": msg})
        return self._resume_session(session_id)

    def _resume_session(self, session_id):
        """通过 AppleScript 打开终端并运行 claude --resume 恢复已有会话。"""
        filepath = self._find_session_path(session_id)
        if not filepath:
            return self._error(404, f"Session not found: {session_id}")

        proj_dir = Path(filepath).parent.name
        decoded = SessionManager._decode_project(proj_dir)
        cwd = os.path.expanduser(decoded)
        if not os.path.isdir(cwd):
            cwd = os.path.expanduser("~")

        try:
            self._run_osascript(cwd, f"--resume {session_id}")
            return self._json({"success": True, "message": f"Resuming session {session_id}"})
        except subprocess.CalledProcessError as e:
            return self._json({"success": False, "message": f"Failed to launch: {e.stderr.strip()}"})

    def _stop_session(self, session_id):
        """通过 Claude 的 PID 映射精确 kill 对应会话的进程。"""
        SessionManager._get_active_session_ids()
        pid = SessionManager._session_pid_cache.get(session_id)
        if not pid:
            return self._json({"success": False, "message": "No matching process found"})
        ok, msg = self._kill_pid(pid)
        return self._json({"success": ok, "message": msg})


    def _find_session_path(self, session_id):
        """根据会话 ID 查找对应的 JSONL 文件路径。"""
        if not self._validate_session_id(session_id):
            return None
        for f in Path(CLAUDE_PROJECTS_DIR).glob(f"*/{session_id}.jsonl"):
            return str(f)
        return None


# ═══════════════════════════════════════════════════════════════════════
#  入口 — 启动 HTTP 服务器
# ═══════════════════════════════════════════════════════════════════════

def main():
    """S.T.O.A. 主入口：启动 HTTP 服务器，自动打开浏览器。"""
    print()
    print("  ╔══════════════════════════════════╗")
    print("  ║   Claude Code Session Manager   ║")
    print("  ╚══════════════════════════════════╝")
    print()

    # 确保回收站目录存在
    os.makedirs(TRASH_DIR, exist_ok=True)

    # 启动时扫描会话状态
    sessions = SessionManager.list_all()
    trash_count = len(SessionManager.list_trash())
    print(f"  Sessions: {len(sessions)}  |  Trash: {trash_count}")
    print()

    # 创建 HTTP 服务器，监听 127.0.0.1:8742
    http.server.HTTPServer.allow_reuse_address = True
    server = http.server.HTTPServer((HOST, PORT), RequestHandler)
    url = f"http://localhost:{PORT}"

    # 自动打开浏览器（.app 启动器模式下通过 CSM_NO_BROWSER 环境变量跳过）
    if not os.environ.get("CSM_NO_BROWSER"):
        print(f"  ▼  Opening {url}")
        def open_browser():
            webbrowser.open(url)
        threading.Timer(0.3, open_browser).start()  # 延迟 0.3 秒确保服务器就绪
    else:
        print(f"  Server ready at {url}")

    print(f"  Press Ctrl+C to stop")
    print()

    try:
        server.serve_forever()  # 阻塞运行，直到收到 SIGINT
    except KeyboardInterrupt:
        print("\n  Shutting down…")
        server.shutdown()
        print("  Goodbye!\n")


if __name__ == "__main__":
    main()
