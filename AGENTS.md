# curmux

Single-file Cursor Agent multiplexer. Everything lives in the `curmux` executable (Python 3 + stdlib).

## Structure

- `curmux` — CLI, server, watchdog, and inline web dashboard (single file)
- `install.sh` — copies `curmux` to `/usr/local/bin`

## Data

All runtime state in `~/.curmux/curmux.db` (SQLite WAL mode). Tables: `sessions`, `tasks`, `messages`, `memory`, `alerts`.

## Workflow

- **Test changes**: `./curmux --help`, `./curmux ls`, `./curmux serve --no-tls --port 9999`
- **Validate syntax**: `python3 -c "import ast; ast.parse(open('curmux').read())"`
- **Commit after every completed task.** Don't batch unrelated changes.

## Architecture

The CLI and web server share the same SQLite database. The watchdog runs as a background thread when `curmux serve` is active, polling tmux sessions every 15 seconds.

Key patterns:
- `tmux_capture()` reads pane output for status detection
- `_detect_status()` pattern-matches against known cursor agent TUI states
- Watchdog auto-restarts exited agents with `--continue` and auto-accepts confirmations in yolo mode
- REST API serves both the web dashboard and agent-to-agent coordination
- All HTML/CSS/JS is inlined in the `DASHBOARD_HTML` constant

## Agent coordination

Cursor agents coordinate via the REST API (available when `curmux serve` is running):
- Claim tasks atomically: `POST /api/tasks/{id}/claim`
- Share context: `POST /api/memory` with `{key, value}`
- Send messages: `POST /api/messages` with `{sender, recipient, body}`
- Check peer status: `GET /api/sessions/{name}/status`
