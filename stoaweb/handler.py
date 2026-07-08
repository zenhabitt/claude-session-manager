"""HTTP request handler — all API routes and response helpers."""

import http.server
import json
import os
import sys
import shlex
import subprocess
import threading
import time
import datetime
import urllib.parse
import urllib.request
from pathlib import Path

from stoacore.config import VERSION, PORT, HOST, TRASH_DIR, CONFIG_DIR, CONFIG_FILE, CLAUDE_PROJECTS_DIR, MIN_ROLLBACK_VERSION, SERVER_STARTED_AT, read_config, write_config
from stoacore.utils import parse_version, compare_versions, get_app_path, validate_download_url
from stoadata.session_store import SessionManager
from stoaweb.i18n import I18N
from stoaweb.frontend import FRONTEND
from stoaupdate.github_api import github_api, _ValidatingRedirectHandler


# Update check cache (module-level, shared across requests)
_update_check_cache = None
_rollback_info_cache = None


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
        elif path == "/api/check-update":
            qs = urllib.parse.urlparse(self.path).query
            params = urllib.parse.parse_qs(qs)
            force = params.get("force", ["0"])[0] == "1"
            return self._check_update(force=force)
        elif path == "/api/config":
            return self._get_config()
        elif path == "/api/rollback-available":
            return self._rollback_available()
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
        elif path == "/api/quit":
            return self._quit_server()
        elif path == "/api/update-and-restart":
            return self._update_and_restart()
        elif path == "/api/rollback":
            return self._rollback()
        elif path == "/api/config":
            return self._set_config()
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
        self.wfile.write(FRONTEND.replace("%%VERSION%%", VERSION).encode("utf-8"))

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

    def _read_body(self):
        """读取 POST 请求 body 并解析为 JSON。解析失败返回 None。"""
        try:
            length = int(self.headers.get("Content-Length", 0))
            if length == 0:
                return {}
            raw = self.rfile.read(length)
            return json.loads(raw.decode("utf-8"))
        except (json.JSONDecodeError, ValueError, OSError):
            return None

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
            if result.returncode == 2:  # grep 错误（目录不存在、权限拒绝等）
                return self._json({"error": result.stderr.strip()})
            if result.returncode == 1:  # 未找到匹配
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
        """通过 AppleScript 在 Terminal 中运行 claude 命令。
        使用 shlex 防止 shell 元字符注入，同时保证多词参数正确拆分。"""
        safe_cwd = shlex.quote(cwd)
        if claude_args:
            safe_args = ' '.join(shlex.quote(a) for a in shlex.split(claude_args))
        else:
            safe_args = ""
        script = f'''
            tell application "Terminal"
                do script "cd {safe_cwd} && claude {safe_args}"
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

    # ── 更新系统 ──────────────────────────────────────────────────

    _update_lock = threading.Lock()  # 保护 _update_check_cache 和 config 并发读写

    def _download_dmg(self, url, dest_path):
        """分块下载 DMG 文件，带超时。每次重定向都重新验证目标 URL。
        成功返回 True，失败返回错误信息。"""
        opener = urllib.request.build_opener(_ValidatingRedirectHandler())
        try:
            with opener.open(url, timeout=30) as resp:
                with open(dest_path, 'wb') as f:
                    while True:
                        chunk = resp.read(8192)
                        if not chunk:
                            break
                        f.write(chunk)
            return (True, None)
        except (OSError, ValueError) as e:
            return (False, f"Download failed: {e}")

    def _find_previous_release(self, releases):
        """从 release 列表中找到可回退的上一版本。
        返回 (tag_name, release_dict, dmg_url) 或 None。"""
        # 收集所有稳定版版本号
        tags = []
        for rel in releases:
            if rel.get("prerelease"):
                continue
            tag = rel.get("tag_name", "")
            if parse_version(tag):
                tags.append((tag, rel))
        if not tags:
            return None

        if parse_version(VERSION) is None:
            return None

        # 按版本降序排列，找到低于当前版本且不低于最低回退版本的最高版本
        for tag, rel in sorted(tags, key=lambda x: parse_version(x[0]) or (0,), reverse=True):
            if compare_versions(tag, VERSION) < 0 and compare_versions(tag, MIN_ROLLBACK_VERSION) >= 0:
                # 找到 DMG 链接
                for asset in rel.get("assets", []):
                    if asset.get("name", "").endswith(".dmg"):
                        return (tag, rel, asset.get("browser_download_url"))
                # 该版本无 DMG，继续检查更早的版本
        return None

    def _install_dmg_and_restart(self, dmg_path, action_name="Update"):
        """挂载 DMG → 原子替换 .app → 卸载 → 重启。"""
        app_path = get_app_path()
        if not app_path:
            return self._json({"success": False, "message": "Not running from .app bundle — operation not supported"})

        # 1. 挂载 DMG（使用 -mountpoint 精确控制挂载位置）
        mount_point = "/tmp/stoa-mount"
        try:
            os.makedirs(mount_point, exist_ok=True)
            result = subprocess.run(
                ["hdiutil", "attach", dmg_path, "-nobrowse", "-readonly",
                 "-mountpoint", mount_point],
                capture_output=True, text=True, timeout=30
            )
            if result.returncode != 0:
                raise OSError(result.stderr.strip())
        except (subprocess.TimeoutExpired, OSError) as e:
            return self._json({"success": False, "message": f"Mount failed: {e}"})

        new_app = os.path.join(mount_point, "S.T.O.A..app")
        tmp_app = app_path + ".new"

        install_ok = False
        try:
            # 2. 先拷贝新 .app 到临时路径（不删除旧版本）
            subprocess.run(["ditto", new_app, tmp_app], check=True, timeout=30)
            # 3. 原子替换：用 rename 交换新旧 .app
            old_tmp = app_path + ".old"
            if os.path.exists(old_tmp):
                subprocess.run(["rm", "-rf", old_tmp], check=True, timeout=10)
            os.rename(app_path, old_tmp)
            os.rename(tmp_app, app_path)
            # 4. 清理旧版本
            subprocess.run(["rm", "-rf", old_tmp], check=True, timeout=10)
            install_ok = True
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError, OSError) as e:
            # 安装失败：如果旧 .app 被移走了但新 .app 没到位，恢复旧版本
            if not os.path.exists(app_path):
                old_tmp = app_path + ".old"
                if os.path.exists(old_tmp):
                    try:
                        os.rename(old_tmp, app_path)
                    except OSError:
                        pass
                elif os.path.exists(tmp_app):
                    try:
                        os.rename(tmp_app, app_path)
                    except OSError:
                        pass
            return self._json({"success": False, "message": f"Install failed: {e}"})
        finally:
            # 清理临时文件
            if not install_ok:
                for p in [tmp_app, app_path + ".old"]:
                    if os.path.exists(p):
                        try:
                            subprocess.run(["rm", "-rf", p], timeout=10)
                        except (subprocess.TimeoutExpired, OSError):
                            pass
            # 卸载 DMG
            try:
                subprocess.run(["hdiutil", "detach", mount_point], capture_output=True, timeout=10)
            except (subprocess.TimeoutExpired, OSError):
                pass
            # 清理 DMG 和临时挂载点
            try:
                os.remove(dmg_path)
            except OSError:
                pass
            try:
                os.rmdir(mount_point)
            except OSError:
                pass

        # 5. 重启服务（先启动新进程，成功后才关闭旧 socket）
        self._json({"success": True, "message": f"{action_name} complete, restarting..."})
        self.wfile.flush()
        self._restart_self()

    def _restart_self(self):
        """先尝试启动新进程，成功后才关闭当前 socket 并退出。"""
        # __file__ 是 stoaweb/handler.py，需向上找到项目根目录的 server.py
        script_path = os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), 'server.py')
        env = os.environ.copy()
        env["CSM_NO_BROWSER"] = "1"
        # 先启动新进程
        try:
            with open("/tmp/claude-session-manager.log", "a") as log_file:
                new_proc = subprocess.Popen(
                    [sys.executable, script_path],
                    stdin=subprocess.DEVNULL, stdout=log_file, stderr=log_file,
                    start_new_session=True, env=env, close_fds=True
                )
        except (OSError, ValueError):
            return  # 启动失败，当前进程继续运行
        # 新进程启动成功，再关闭旧 socket 并退出
        try:
            self.server.server_close()
        except OSError:
            pass
        os._exit(0)

    def _check_update(self, force=False):
        """检查 GitHub Releases 是否有新版本。force=True 时忽略 7 天间隔。"""
        global _update_check_cache
        with self._update_lock:
            config = SessionManager._read_config()
        now = datetime.datetime.now()

        # 非强制模式下，7 天内不重复检查
        if not force and config.get("last_check_time"):
            try:
                last = datetime.datetime.strptime(config["last_check_time"], "%Y-%m-%d %H:%M:%S")
                if (now - last).days < 7:
                    with self._update_lock:
                        cached = _update_check_cache
                    if cached is not None:
                        return self._json(cached)
                    # 缓存为空（后台检查未执行或失败），继续执行实际检查
            except (ValueError, TypeError):
                pass

        result = {"has_update": False, "current_version": VERSION,
                  "checked_at": now.strftime("%Y-%m-%d %H:%M:%S")}

        release, err = github_api("/releases/latest")
        if err:
            result["error"] = "network_error"
        elif not release.get("tag_name"):
            result["error"] = "parse_error"
        else:
            latest_tag = release["tag_name"]
            cmp = compare_versions(latest_tag, VERSION)
            if cmp is None:
                result["error"] = "parse_error"
            elif cmp > 0:
                dmg_url = None
                for asset in release.get("assets", []):
                    if asset.get("name", "").endswith(".dmg"):
                        dmg_url = asset.get("browser_download_url")
                        break
                # 只在有 DMG 时才报告有更新
                if dmg_url:
                    result["has_update"] = True
                    result["latest_version"] = latest_tag
                    result["download_url"] = dmg_url
                    result["release_notes"] = release.get("body", "")

        # 自动检查时更新 last_check_time 并缓存结果（同一锁内，原子操作）
        if not force:
            with self._update_lock:
                config = SessionManager._read_config()
                config["last_check_time"] = now.strftime("%Y-%m-%d %H:%M:%S")
                SessionManager._write_config(config)
                _update_check_cache = result
        else:
            with self._update_lock:
                _update_check_cache = result

        return self._json(result)

    def _update_and_restart(self):
        """下载最新 DMG、替换 .app、重启服务。"""
        body = self._read_body()
        if body is None:
            return self._error(400, "Invalid request body")
        download_url = body.get("download_url", "")
        if not validate_download_url(download_url):
            return self._error(400, "Invalid download URL")

        dmg_path = "/tmp/stoa-update.dmg"
        ok, err = self._download_dmg(download_url, dmg_path)
        if not ok:
            return self._json({"success": False, "message": err})

        return self._install_dmg_and_restart(dmg_path, "Update")

    def _rollback_available(self):
        """查询是否有可回退的上一个版本。结果缓存在模块级变量中（跨请求共享）。"""
        global _rollback_info_cache
        if _rollback_info_cache is not None:
            return self._json(_rollback_info_cache)

        releases, err = github_api("/releases?per_page=100")
        if err:
            return self._json({"available": False, "error": err})

        prev = self._find_previous_release(releases)
        with self._update_lock:
            if prev is None or not prev[2]:
                _rollback_info_cache = {"available": False}
            else:
                _rollback_info_cache = {
                    "available": True,
                    "version": prev[0],
                    "download_url": prev[2],
                }
        return self._json(_rollback_info_cache)

    def _rollback(self):
        """回退到上一个版本：从 GitHub 下载上一个 release 的 DMG 并安装。"""
        releases, err = github_api("/releases?per_page=100")
        if err:
            return self._json({"success": False, "message": f"Cannot check releases: {err}"})

        prev = self._find_previous_release(releases)
        if prev is None:
            return self._json({"success": False, "message": "No previous version available"})

        tag, rel, dmg_url = prev
        if not dmg_url:
            return self._json({"success": False, "message": "No DMG found for previous release"})

        if not validate_download_url(dmg_url):
            return self._json({"success": False, "message": "Invalid download URL for previous release"})

        dmg_path = "/tmp/stoa-rollback.dmg"
        ok, err = self._download_dmg(dmg_url, dmg_path)
        if not ok:
            return self._json({"success": False, "message": err})

        return self._install_dmg_and_restart(dmg_path, "Rollback")

    def _get_config(self):
        """返回当前配置。"""
        config = SessionManager._read_config()
        return self._json({
            "auto_check_updates": config.get("auto_check_updates", True),
            "last_check_time": config.get("last_check_time"),
            "sound_enabled": config.get("sound_enabled", False),
        })

    def _set_config(self):
        """更新配置。"""
        body = self._read_body()
        if body is None:
            return self._error(400, "Invalid request body")
        with self._update_lock:
            config = SessionManager._read_config()
            if "auto_check_updates" in body:
                config["auto_check_updates"] = bool(body["auto_check_updates"])
            if "sound_enabled" in body:
                config["sound_enabled"] = bool(body["sound_enabled"])
            SessionManager._write_config(config)
        # 实时生效：通知 sound_notifier 模块
        if "sound_enabled" in body:
            from stoadata.sound_notifier import set_enabled
            set_enabled(config["sound_enabled"])
        return self._json({"success": True})

    def _restart_server(self):
        """重启 S.T.O.A. 服务。"""
        self._json({"success": True, "message": "Restarting..."})
        self.wfile.flush()
        self._restart_self()

    def _quit_server(self):
        """关闭 S.T.O.A. 服务（不重启）。"""
        self._json({"success": True, "message": "Shutting down..."})
        self.wfile.flush()

        # 用 AppleScript 关闭浏览器中 S.T.O.A. 的标签页
        # 每个浏览器独立尝试，失败则静默跳过（浏览器未安装/不支持 AppleScript）
        close_tabs_script = (
            'repeat with w in windows\n'
            '  repeat with t in tabs of w\n'
            '    if URL of t starts with "http://localhost:8742" then close t\n'
            '  end repeat\n'
            'end repeat'
        )
        browsers = [
            "Safari",
            "Google Chrome",
            "Microsoft Edge",
            "Brave Browser",
            "Arc",
            "Opera",
            "Firefox",
            "Vivaldi",
        ]
        for browser in browsers:
            try:
                subprocess.run(
                    ["osascript", "-e", f'tell application "{browser}" to {close_tabs_script}'],
                    capture_output=True, timeout=3
                )
            except (subprocess.TimeoutExpired, OSError):
                pass  # 该浏览器未响应或未安装，静默跳过

        try:
            self.server.server_close()
        except OSError:
            pass
        os._exit(0)

    def _kill_pid(self, pid, poll_exit=False):
        """发送 kill 信号并可选轮询确认退出。返回 (success, message)。"""
        try:
            result = subprocess.run(["kill", str(pid)], capture_output=True, timeout=3)
        except subprocess.TimeoutExpired:
            return False, "Process did not respond — try again"
        except (OSError, ValueError, subprocess.SubprocessError) as e:
            return False, str(e)
        # kill 返回非零时，用 os.kill 检测进程是否真的不存在（locale 无关）
        if result.returncode != 0:
            try:
                os.kill(pid, 0)
            except OSError:
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
        if not SessionManager._validate_session_id(session_id):
            return None
        for f in Path(CLAUDE_PROJECTS_DIR).glob(f"*/{session_id}.jsonl"):
            return str(f)
        return None