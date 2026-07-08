"""S.T.O.A. — 工具函数"""

import re
import urllib.parse
from pathlib import Path


def parse_version(v):
    """将 'v2.1.0' 或 '2.1.0-beta' 解析为 (parts_tuple, is_prerelease)。
    is_prerelease 为 True 表示带有 -alpha/-beta/-rc 等预发布后缀。
    +build 后缀视为稳定版。解析失败返回 None。"""
    v = v.lstrip("v")
    # 分离预发布标记：v2.1.0-beta.1 → 2.1.0 + -beta.1
    base, sep, pre = v.partition('-')
    if not sep:
        base, sep, pre = v.partition('+')  # +build 后缀视为稳定版
    try:
        parts = tuple(int(x) for x in base.split("."))
        if len(parts) < 2:
            return None
        return (parts, bool(sep and not v.partition('+')[1]))
    except (ValueError, TypeError):
        return None


def compare_versions(v1, v2):
    """比较两个版本号字符串。逐段比较，缺失段视为 0。
    数字部分相同时，预发布版 < 稳定版（如 v2.2.0-beta < v2.2.0）。
    返回 -1 (v1<v2), 0 (相等), 1 (v1>v2), 或 None (无法比较)。"""
    r1, r2 = parse_version(v1), parse_version(v2)
    if r1 is None or r2 is None:
        return None
    p1, pre1 = r1
    p2, pre2 = r2
    max_len = max(len(p1), len(p2))
    for i in range(max_len):
        a = p1[i] if i < len(p1) else 0
        b = p2[i] if i < len(p2) else 0
        if a < b:
            return -1
        if a > b:
            return 1
    # 数字部分相等，预发布版 < 稳定版
    if pre1 and not pre2:
        return -1
    if pre2 and not pre1:
        return 1
    return 0


def get_app_path():
    """从 __file__ 向上找到 .app bundle 路径。如果不是从 .app 内运行则返回 None。
    向上遍历目录树查找 Contents/Resources/ 结构，兼容调用者位于子目录的情况。"""
    p = Path(__file__).resolve()
    for ancestor in p.parents:
        if ancestor.name == "Resources":
            contents = ancestor.parent
            if contents.name == "Contents":
                app = contents.parent
                if app.name.endswith(".app") and app.is_dir():
                    return str(app)
    return None


# GitHub CDN 域名（release asset 下载时会 302 重定向到这些主机）
_GITHUB_CDN_HOSTS = {"objects.githubusercontent.com", "github-releases.githubusercontent.com"}


def validate_download_url(url, strict=True):
    """校验下载 URL 是否指向合法的 GitHub release asset。"""
    if not url:
        return False
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https":
        return False
    if strict:
        return (parsed.netloc == "github.com" and
                parsed.path.startswith("/zenhabitt/claude-session-manager/releases/download/"))
    else:
        return (parsed.netloc == "github.com" or
                parsed.netloc in _GITHUB_CDN_HOSTS)
