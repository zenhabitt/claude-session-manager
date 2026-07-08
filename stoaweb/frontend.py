"""S.T.O.A. — Frontend HTML/CSS/JS single-page application."""

import json
from stoaweb.i18n import I18N

FRONTEND = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>S.T.O.A.</title>
<link rel="icon" type="image/png" href="data:image/png;base64,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">
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
  .settings-toggle { display: flex; align-items: center; justify-content: space-between; padding: 6px 12px; font-size: 12px; color: var(--text); cursor: pointer; font-family: var(--font); }
  .settings-toggle input[type="checkbox"] { accent-color: var(--accent); }
  .settings-menu button:disabled,
  .settings-menu button.btn-disabled { opacity: .35; cursor: pointer; }
  .settings-update-dot { display: inline-block; width: 6px; height: 6px; border-radius: 50%; background: #FD151B; margin-left: 4px; vertical-align: middle; }
  .settings-advanced-group { display: none; }
  .settings-advanced-group.open { display: block; }
  .settings-advanced-group .settings-toggle,
  .settings-advanced-group button { padding-left: 24px; }

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
        <button type="button" onclick="quitServer();toggleSettings()"><span data-i18n="quitBtn">Quit S.T.O.A.</span></button>
        <button type="button" onclick="checkUpdate();toggleSettings()"><span data-i18n="checkUpdateBtn">Check for Updates</span></button>
        <div class="settings-sep"></div>
        <button type="button" id="advanced-toggle-btn" onclick="toggleAdvancedMenu()">
          <span data-i18n="advancedSettings">Advanced</span>
        </button>
        <div class="settings-advanced-group" id="advanced-group">
          <label class="settings-toggle">
            <span data-i18n="autoCheckLabel">Auto-check updates</span>
            <input type="checkbox" id="auto-check-toggle" onchange="toggleAutoCheck(this.checked)">
          </label>
          <label class="settings-toggle">
            <span data-i18n="soundLabel">Busy→idle alert sound</span>
            <input type="checkbox" id="sound-toggle" onchange="toggleSound(this.checked)">
          </label>
          <button type="button" id="rollback-btn" onclick="rollbackVersion();toggleSettings()" class="btn-disabled">
            <span data-i18n="rollbackBtn">Rollback to</span> <span id="rollback-ver">—</span>
          </button>
        </div>
        <div class="settings-sep"></div>
        <div class="settings-info"><div>Server up since</div><div id="server-started-at">—</div></div>
        <div class="settings-sep"></div>
        <div class="settings-info" style="padding-top:0">%%VERSION%%</div>
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
function toggleAdvancedMenu() {
  document.getElementById('advanced-group').classList.toggle('open');
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
async function api(path, method = 'GET', body) {
  const opts = { method, cache: 'no-store' };
  if (body !== undefined) {
    opts.headers = {'Content-Type': 'application/json'};
    opts.body = JSON.stringify(body);
  }
  const res = await fetch(path, opts);
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
  initSettings();
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
        onClick: `switchTab('list',true);selectedId='${jsesc(a.id)}';currentDetailType='session';reloadData().then(()=>{renderList();selectSession('${jsesc(a.id)}');})`,
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
        onClick: `switchTab('list',true);selectedId='${jsesc(r.id)}';currentDetailType='session';reloadData().then(()=>{renderList();selectSession('${jsesc(r.id)}');})`,
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

async function quitServer() {
  toast(t('quitMsg'), 'info');
  await new Promise(r => setTimeout(r, 1000));
  try { await api('/api/quit', 'POST'); } catch(e) { /* expected */ }
  // 替换页面内容为退出提示
  document.body.innerHTML = '<div style="display:flex;align-items:center;justify-content:center;height:100vh;font-family:-apple-system,sans-serif;color:#888;font-size:18px">S.T.O.A. 已退出 &mdash; 请关闭此标签页</div>';
}

// ── 更新系统 ──

async function checkUpdate() {
  try {
    const res = await api('/api/check-update?force=1');
    if (res.has_update && res.download_url) {
      const msg = t('updateMsg').replace('{version}', esc(res.latest_version || '')).replace('{current}', esc(res.current_version || ''));
      showModal(t('updateAvailable'), msg, t('updateAndRestart'), 'danger', () => {
        closeModal();
        doUpdate(res.download_url);
      });
    } else {
      toast(t('upToDate'), 'success');
    }
  } catch(e) {
    toast(t('checkFailed'), 'error');
  }
}

async function doUpdate(downloadUrl) {
  toast(t('downloading'), 'info');
  try {
    const res = await api('/api/update-and-restart', 'POST', {download_url: downloadUrl});
    if (res.success) {
      setTimeout(() => { hardReload(); }, 2000);
    } else {
      toast(res.message || t('updateFailed'), 'error');
    }
  } catch(e) {
    setTimeout(() => { hardReload(); }, 2000);
  }
}

async function rollbackVersion() {
  const ver = document.getElementById('rollback-ver').textContent;
  if (!ver || ver === '—') {
    toast(t('noRollback'), 'info');
    return;
  }
  const msg = t('rollbackConfirmMsg').replace('{version}', esc(ver));
  showModal(t('rollbackConfirmTitle'), msg, t('rollbackBtn'), 'danger', async () => {
    closeModal();
    try {
      const res = await api('/api/rollback', 'POST');
      if (res.success) {
        setTimeout(() => { hardReload(); }, 2000);
      } else {
        toast(res.message || t('updateFailed'), 'error');
      }
    } catch(e) {
      setTimeout(() => { hardReload(); }, 2000);
    }
  });
}

async function toggleAutoCheck(enabled) {
  try {
    await api('/api/config', 'POST', {auto_check_updates: enabled});
  } catch(e) { /* ignore */ }
}

async function toggleSound(enabled) {
  try {
    await api('/api/config', 'POST', {sound_enabled: enabled});
  } catch(e) { /* ignore */ }
}

async function initSettings() {
  // 三个独立请求并行加载
  const [config, rollbackInfo, updateCache] = await Promise.allSettled([
    api('/api/config'),
    api('/api/rollback-available'),
    api('/api/check-update'),
  ]);

  if (config.status === 'fulfilled') {
    document.getElementById('auto-check-toggle').checked = !!config.value.auto_check_updates;
    document.getElementById('sound-toggle').checked = !!config.value.sound_enabled;
  }

  if (rollbackInfo.status === 'fulfilled' && rollbackInfo.value.available) {
    document.getElementById('rollback-btn').classList.remove('btn-disabled');
    document.getElementById('rollback-ver').textContent = rollbackInfo.value.version;
  }

  if (updateCache.status === 'fulfilled' && updateCache.value.has_update) {
    const btn = document.querySelector('[data-i18n="settingsBtn"]');
    if (btn && !btn.querySelector('.settings-update-dot')) {
      const dot = document.createElement('span');
      dot.className = 'settings-update-dot';
      btn.appendChild(dot);
    }
  }
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
    const result = await api(`/api/sessions/search?q=${encodeURIComponent(query)}`);
    contentMatchIds = Array.isArray(result) ? result : [];
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
      onClick: `selectSession('${jsesc(s.id)}')`,
      metaTags: [
        { cls: 'date', text: s.date },
        { cls: 'msgs', text: s.messages + ' msgs' },
        { cls: 'size', text: s.size },
        { cls: 'project', text: s.project },
      ],
      actionsHtml: `<button type="button" class="card-btn danger" onclick="event.stopPropagation(); ${s.active ? `askStopSession('${jsesc(s.id)}')` : `askDeleteSession('${jsesc(s.id)}')`}">&#x2715; ${s.active ? t('stop') : t('delete')}</button>`
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
        onClick: `selectTrashItem('${jsesc(item.id)}')`,
        metaTags: [
          { cls: 'date', text: item.date },
          { cls: 'msgs', text: item.messages + ' msgs' },
          { cls: 'size', text: item.size },
          { style: 'background:rgba(240,160,48,0.15);color:#f0a030', text: t('deletedAt') + ': ' + item.deleted_at },
        ],
        actionsHtml: `<button type="button" class="card-btn restore" onclick="event.stopPropagation(); askRestore('${jsesc(item.id)}')">&#8634; ${t('restore')}</button><button type="button" class="card-btn danger" onclick="event.stopPropagation(); askPermDelete('${jsesc(item.id)}')">&#x2715; ${t('permDelete')}</button>`
      })).join('');
    }
  }
}

function esc(str) {
  const div = document.createElement('div');
  div.textContent = str || '';
  return div.innerHTML;
}

function jsesc(str) {
  // 转义 JS 字符串内的特殊字符（用于 onclick 等 JS 上下文）
  return (str || '').replace(/\\/g, '\\\\').replace(/'/g, "\\'").replace(/"/g, '\\"');
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
            ${s.active ? `<button type="button" class="btn" onclick="askRestartSession('${jsesc(s.id)}')" style="color:var(--warn);border-color:var(--warn)">&#8635; ${t('restart')}</button>` : ''}
            ${s.active ? '' : `<button type="button" class="btn" onclick="resumeSession('${jsesc(s.id)}')" style="color:var(--accent);border-color:var(--accent)">&#9654; ${t('resume')}</button>`}
            <button type="button" class="btn btn-danger" id="detail-delete-btn" onclick="${s.active ? `askStopSession('${jsesc(s.id)}')` : `askDeleteSession('${jsesc(s.id)}')`}">&#x2715; ${s.active ? t('stop') : t('delete')}</button>
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