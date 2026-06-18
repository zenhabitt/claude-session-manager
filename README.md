# Claude Session Manager

Lightweight macOS GUI for managing Claude Code chat sessions — browse, preview, delete, restore, and resume conversations.

**Zero dependencies.** Single Python script + browser frontend. Packs into a native macOS `.app`.

## Features

- 📋 **Browse** all Claude Code sessions across projects
- 🔍 **Search & filter** by title, project, or model
- 👁 **Preview** conversation content
- 🗑 **Delete → Trash** (recoverable, not permanent)
- ♻️ **Restore** or permanently delete from trash
- ▶ **Resume** any session in a new terminal
- 🌐 **i18n** — English & 简体中文
- 📦 **Native macOS .app** — Launchpad, Dock icon, universal binary

## Screenshot

![screenshot](https://via.placeholder.com/800x500/25262b/c1c2c5?text=Claude+Session+Manager+Screenshot)

## Requirements

- macOS 13.0+
- Python 3 (Homebrew or python.org)

## Quick Start

```bash
# Clone and run
git clone https://github.com/zenhabitt/claude-session-manager.git
cd claude-session-manager
python3 server.py
```

Opens http://localhost:8742 in your browser.

## Build macOS App

```bash
bash build_app.sh --dmg
```

Outputs `build/Claude Session Manager.app` and `build/Claude Session Manager.dmg`.

## Install

### From DMG
1. Download `Claude Session Manager.dmg` from [Releases](../../releases)
2. Open and drag the app to `/Applications`

### From source
```bash
bash build_app.sh --dmg
cp -R "build/Claude Session Manager.app" /Applications/
```

## Uninstall

Drag the app to Trash, or:
```bash
bash uninstall.sh
```

## How It Works

- **Backend**: Python stdlib HTTP server serving a REST API
- **Frontend**: Single-page HTML/CSS/JS rendered in browser
- **App launcher**: Minimal Cocoa/ObjC stub that participates in macOS event loop
- **Data source**: Reads `~/.claude/projects/*/*.jsonl` session files

All data stays local. No network requests, no telemetry.

## Project Structure

```
claude-session-manager/
├── server.py          # Main application (backend + frontend)
├── build_app.sh       # macOS .app & .dmg build script
├── uninstall.sh       # Cleanup script
├── .gitignore
├── LICENSE
└── README.md
```

## License

MIT
