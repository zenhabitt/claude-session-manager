# S.T.O.A. — Session Timeline Organizer & Archiver

> 轻量级 macOS 会话管理工具 / Lightweight macOS session manager for Claude Code

中英双语 / Bilingual — [English below](#english)

---

## 中文

S.T.O.A. 是一个零依赖的 Claude Code 会话管理工具。浏览、预览、删除、恢复、接续你的每一次 AI 对话。

**单个 Python 脚本 + 浏览器前端。** 可打包为原生 macOS `.app`。

### 功能

- 📋 **浏览** 所有项目的 Claude Code 会话
- 🔍 **搜索** 按标题、项目、模型、会话 ID、日期筛选；支持全文搜索对话内容
- 👁 **预览** 对话内容，匹配关键词高亮，上一个/下一个导航
- 🗑 **删除 → 回收站** 可恢复，不永久
- ♻️ **恢复** 或彻底删除
- ▶ **接续** 任意会话到新终端
- 🌐 **中英文切换** English & 简体中文
- 🎨 **双主题** 暖金 / 冷蓝
- 📦 **原生 macOS .app** — Launchpad、Dock 图标、universal binary

### 环境要求

- macOS 13.0+
- Python 3（Homebrew 或 python.org）

### 快速开始

```bash
git clone https://github.com/zenhabitt/claude-session-manager.git
cd claude-session-manager
python3 server.py
```

浏览器打开 http://localhost:8742。

### 构建 macOS 应用

```bash
bash build-csm.sh --dmg
```

输出 `build/S.T.O.A..app` 和 `build/S.T.O.A..dmg`。

如需自定义图标，将 `.icns` 文件放到项目根目录命名为 `icon-custom.icns`，构建脚本会自动使用。

### 安装

**DMG 安装**
1. 从 [Releases](../../releases) 下载 `S.T.O.A..dmg`
2. 打开并拖入 `/Applications`

**源码安装**
```bash
bash build-csm.sh --dmg
cp -R "build/S.T.O.A..app" /Applications/
```

### 卸载

拖入废纸篓，或：
```bash
bash uninstall-csm.sh
```

### 工作原理

- **后端**: Python 标准库 HTTP 服务器，REST API
- **前端**: 单页 HTML/CSS/JS，浏览器渲染
- **启动器**: 最小 Cocoa/ObjC 桩，参与 macOS 事件循环
- **数据源**: 读取 `~/.claude/sessions/<pid>.json`（PID 映射）+ `~/.claude/projects/*/*.jsonl`（会话文件）

所有数据留在本地。无网络请求，无遥测。

### 项目结构

```
claude-session-manager/
├── server.py           # 主程序（后端 + 前端）
├── build-csm.sh        # macOS .app & .dmg 构建脚本
├── uninstall-csm.sh    # 卸载清理脚本
├── icon-custom.icns    # 自定义图标（可选）
├── .gitignore
├── LICENSE
└── README.md
```

### 许可证

MIT

---

<h2 id="english">English</h2>

S.T.O.A. (Session Timeline Organizer & Archiver) is a zero-dependency session manager for Claude Code. Browse, preview, delete, restore, and resume your AI conversations.

**Single Python script + browser frontend.** Packs into a native macOS `.app`.

### Features

- 📋 **Browse** all Claude Code sessions across projects
- 🔍 **Search** by title, project, model, session ID, date; full-text content search with match highlighting
- 👁 **Preview** conversation content with keyword highlighting and prev/next navigation
- 🗑 **Delete → Trash** recoverable, not permanent
- ♻️ **Restore** or permanently delete from trash
- ▶ **Resume** any session in a new terminal
- 🌐 **i18n** — English & 简体中文
- 🎨 **Dual theme** — Warm Gold / Cool Blue
- 📦 **Native macOS .app** — Launchpad, Dock icon, universal binary

### Requirements

- macOS 13.0+
- Python 3 (Homebrew or python.org)

### Quick Start

```bash
git clone https://github.com/zenhabitt/claude-session-manager.git
cd claude-session-manager
python3 server.py
```

Opens http://localhost:8742 in your browser.

### Build macOS App

```bash
bash build-csm.sh --dmg
```

Outputs `build/S.T.O.A..app` and `build/S.T.O.A..dmg`.

To use a custom icon, place an `.icns` file named `icon-custom.icns` in the project root — the build script picks it up automatically.

### Install

**From DMG**
1. Download `S.T.O.A..dmg` from [Releases](../../releases)
2. Open and drag to `/Applications`

**From source**
```bash
bash build-csm.sh --dmg
cp -R "build/S.T.O.A..app" /Applications/
```

### Uninstall

Drag to Trash, or:
```bash
bash uninstall-csm.sh
```

### How It Works

- **Backend**: Python stdlib HTTP server serving a REST API
- **Frontend**: Single-page HTML/CSS/JS rendered in browser
- **Launcher**: Minimal Cocoa/ObjC stub for macOS event loop
- **Data source**: `~/.claude/sessions/<pid>.json` (PID mapping) + `~/.claude/projects/*/*.jsonl` (session files)

All data stays local. No network requests, no telemetry.

### License

MIT
