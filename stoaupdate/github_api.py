"""GitHub API client — unified HTTP calls + redirect validation."""

import json
import urllib.request
import urllib.error

from stoacore.utils import validate_download_url


def github_api(path_suffix):
    """统一的 GitHub API 调用（模块级，前后台共用）。
    path_suffix 如 '/releases/latest' 或 '/releases?per_page=100'。
    返回 (data, error_message)。"""
    url = "https://api.github.com/repos/zenhabitt/claude-session-manager" + path_suffix
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "S.T.O.A.-Update-Check/1.0", "Accept": "application/vnd.github+json"}
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            return (json.loads(resp.read().decode("utf-8")), None)
    except json.JSONDecodeError as e:
        return (None, f"Parse error: {e}")
    except (urllib.request.URLError, ValueError, OSError) as e:
        return (None, f"Network error: {e}")




class _ValidatingRedirectHandler(urllib.request.HTTPRedirectHandler):
    """HTTP 重定向处理器：验证每次重定向目标是否为可信域名。"""
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not validate_download_url(newurl, strict=False):
            raise urllib.request.HTTPError(req.full_url, code,
                                           "Redirect to untrusted domain", headers, fp)
        return urllib.request.HTTPRedirectHandler.redirect_request(
            self, req, fp, code, msg, headers, newurl)
