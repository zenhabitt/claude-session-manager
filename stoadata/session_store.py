"""Session data layer — read, parse, manage Claude Code session files."""

import json
import os
import re
import time
import shutil
import datetime
from collections import Counter
from pathlib import Path

from stoacore.config import CLAUDE_PROJECTS_DIR, TRASH_DIR, CONFIG_DIR, CONFIG_FILE
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

    # ── 配置读写 ────────────────────────────────────────────────────

    @staticmethod
    def _read_config():
        """读取配置文件，返回 dict。文件不存在时返回默认配置。"""
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError, ValueError):
            return {"auto_check_updates": True, "last_check_time": None, "sound_enabled": False}

    @staticmethod
    def _write_config(config):
        """写入配置文件。自动创建父目录。"""
        os.makedirs(CONFIG_DIR, exist_ok=True)
        tmp = CONFIG_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        os.replace(tmp, CONFIG_FILE)

