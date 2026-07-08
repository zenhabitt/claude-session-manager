"""
S.T.O.A. — 配置常量 & 配置文件读写
"""

import datetime
import json
import os

VERSION = "v2.2.0"
MIN_ROLLBACK_VERSION = "v2.2.0"  # 禁止回退到低于此版本的 release（没有自动更新系统）
CLAUDE_PROJECTS_DIR = os.path.expanduser("~/.claude/projects")  # Claude 会话数据目录
TRASH_DIR = os.path.expanduser("~/.claude/session-manager/trash")  # 回收站目录
CONFIG_DIR = os.path.expanduser("~/.claude/session-manager")  # 配置目录
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")  # 配置文件路径
PORT = 8742  # HTTP 服务端口
HOST = "127.0.0.1"  # 仅监听本地，不对外暴露
SERVER_STARTED_AT = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")  # 服务启动时间戳


def read_config():
    """读取配置文件，返回 dict。文件不存在时返回默认配置。"""
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError, ValueError):
        return {"auto_check_updates": True, "last_check_time": None, "sound_enabled": False}


def write_config(config):
    """写入配置文件（原子写入：先写 .tmp 再 os.replace）。"""
    os.makedirs(CONFIG_DIR, exist_ok=True)
    tmp = CONFIG_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
    os.replace(tmp, CONFIG_FILE)
