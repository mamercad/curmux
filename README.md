# curmux — Cursor Agent Multiplexer

Run parallel `cursor agent` TUI sessions with a self-healing watchdog, shared task board, and web dashboard. Single file. No external dependencies beyond Python 3 + tmux.

```bash
git clone https://github.com/mamercad/curmux && cd curmux && ./install.sh
curmux register myproject --dir ~/project --yolo
curmux start myproject
curmux serve   # → https://localhost:8833
```

---

## Why curmux?

| Problem | curmux's solution |
|---------|-------------------|
| Can't run multiple cursor agents at once | **tmux-backed sessions** — each agent in its own pane |
| Agent crashes or exits mid-task | **Self-healing watchdog** — auto-restarts with `--continue` |
| Agents duplicate work | **Task board** — SQLite-backed atomic claiming |
| No visibility across sessions | **Web dashboard** — live status, peek, send |
| Agents can't coordinate | **REST API** — shared memory, messaging, task delegation |

## Features

- **Parallel agents** — register and run many `cursor agent` sessions, each in tmux
- **Watchdog** — detects exited/stuck agents, auto-restarts in yolo mode, auto-accepts confirmations
- **Task board** — SQLite-backed kanban with atomic task claiming (CAS)
- **Web dashboard** — session cards, live peek, send bar, task board, alerts
- **REST API** — full CRUD for sessions, tasks, memory, messages
- **Worktree isolation** — `--worktree` flag for per-agent branch isolation
- **Prefix matching** — `curmux attach my` resolves to `myproject`
- **Zero external deps** — Python 3 stdlib only (sqlite3, http.server, ssl, threading)
- **Single file** — one executable, edit it, extend it

## Requirements

- Python 3.8+
- tmux
- [Cursor CLI](https://cursor.sh) (`cursor agent`)

## Install

```bash
git clone https://github.com/mamercad/curmux && cd curmux && ./install.sh
```

Or manually:

```bash
curl -fsSL https://raw.githubusercontent.com/mamercad/curmux/main/curmux -o /usr/local/bin/curmux
chmod +x /usr/local/bin/curmux
```

## CLI

```bash
curmux register <name> --dir <path> [--yolo] [--model sonnet-4] [--worktree]
curmux start <name>
curmux stop <name>
curmux attach <name>          # attach to tmux session
curmux peek <name>            # view output without attaching
curmux send <name> <text>     # send text to a session
curmux exec <name> --dir <path> [--yolo] -- <prompt>
curmux ls [--format json]     # list sessions
curmux board list             # show task board
curmux board add --title "..." [--project PRJ]
curmux board claim TASK-ID --agent <name>
curmux board done TASK-ID
curmux serve [--port 8833]    # web dashboard + watchdog
```

Session names support prefix matching — `curmux peek my` resolves to `myproject` if unambiguous.

## Watchdog

When `curmux serve` is running, the watchdog checks all sessions every 15 seconds:

| Condition | Action |
|-----------|--------|
| Agent exited to shell prompt (yolo mode) | Auto-restarts with `cursor agent --continue` |
| Agent waiting for confirmation (yolo mode) | Auto-accepts after 30s |
| Agent idle for 10+ minutes | Pushes a `stuck` alert |

## REST API

All endpoints available at `https://localhost:8833/api/`.

```bash
# List sessions
curl -sk https://localhost:8833/api/sessions

# Peek at output
curl -sk https://localhost:8833/api/sessions/myproject/peek?lines=50

# Send text to a session
curl -sk -X POST -H 'Content-Type: application/json' \
  -d '{"text":"implement the auth endpoint"}' \
  https://localhost:8833/api/sessions/myproject/send

# Create a task
curl -sk -X POST -H 'Content-Type: application/json' \
  -d '{"title":"Add login endpoint","project":"API"}' \
  https://localhost:8833/api/tasks

# Claim a task
curl -sk -X POST -H 'Content-Type: application/json' \
  -d '{"agent":"worker-1"}' \
  https://localhost:8833/api/tasks/API-A1B2C3/claim

# Shared memory
curl -sk -X POST -H 'Content-Type: application/json' \
  -d '{"key":"db_schema","value":"users(id,email,hash)"}' \
  https://localhost:8833/api/memory
```

## Data

All state lives in `~/.curmux/`:

```
~/.curmux/
├── curmux.db     # SQLite (sessions, tasks, messages, memory, alerts)
├── tls/          # Auto-generated TLS certs
└── logs/         # Session logs
```

## License

MIT
