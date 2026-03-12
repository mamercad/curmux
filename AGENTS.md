# curmux

Single-file Cursor Agent multiplexer. Everything lives in the `curmux` executable (Python 3 + stdlib).

## Structure

- `curmux` — CLI, server, watchdog, and inline web dashboard (single file)
- `install.sh` — copies `curmux` to `/usr/local/bin`
- `docs/` — SVG diagrams for README

## Data

All runtime state in `~/.curmux/curmux.db` (SQLite WAL mode). Tables: `sessions`, `tasks`, `messages`, `memory`, `alerts`, `stream`.

## Workflow

- **Lifecycle**: `register` → `update` (partial changes) → `start` → `stop` → `rm` (delete)
- **Layout**: `curmux layout [-c CONFIG] [--dir PATH]` — create a multi-pane session from `.curmux.conf` (register + tmux layout); requires PyYAML
- **Lists**: `curmux ls` or `curmux list` (sessions); `curmux board ls` or `curmux board list` (tasks)
- **Test changes**: `./curmux --help`, `./curmux ls`, `./curmux serve --no-tls --port 9999`
- **Validate syntax**: `python3 -c "import ast; ast.parse(open('curmux').read())"`
- **Commit after every completed task.** Don't batch unrelated changes.
- **When you complete a claimed board task:** call `POST /api/tasks/{id}/done` (and commit). Do not skip marking done—the board is the source of truth for what's left.

## Architecture

The CLI and web server share the same SQLite database. The watchdog runs as a background thread when `curmux serve` is active, polling tmux sessions every 15 seconds.

Key patterns:
- Sessions run `cursor-agent` (the standalone TUI binary) inside tmux; user's `~/.tmux.conf` is used (curmux does not override)
- `tmux_capture()` reads pane output for status detection
- `_detect_status()` pattern-matches against known cursor agent TUI states
- `tmux_new_session()` passes the command as a single shell string via `shlex.quote`
- `tmux_send_keys()` sends text with `-l` (literal) then `C-m` (carriage return) so Cursor Agent TUI submits; plain Enter can be sent as LF and interpreted as newline-in-input
- Watchdog auto-restarts exited agents with `--continue` and auto-accepts confirmations in yolo mode
- REST API serves both the web dashboard and agent-to-agent coordination
- All HTML/CSS/JS is inlined in the `DASHBOARD_HTML` constant
- sqlite3.Row iterates over column values, not keys; use `dict(r)` for row→JSON in API and CLI
- Version: `get_version()` from git when in repo; `VERSION` fallback; install.sh and release workflow bake version into artifact

## Agent coordination

Cursor agents running in curmux-managed sessions can coordinate via the REST API. The API is available only when `curmux serve` is running.

**Task-based workflow**: For non-trivial work, use the kanban board (task board). If no suitable task exists, ask the user whether one should be created. Create tasks via the API or dashboard, claim one at a time with your session as `agent`, do the work, then mark the task done. Avoid tackling multi-step work without creating and claiming tasks first.

**Planning before implementation**: Before implementing non-trivial work, write a plan to `docs/<meaningful-name>.md` (e.g. `docs/api-auth-plan.md`). In the plan, identify work that can be parallelized and assign it to multiple sessions—create new curmux sessions where appropriate so several agents can run in parallel. Then execute the plan (claim board tasks, spin up sessions as needed, implement).

**Board task checklist** (when working on a kanban item; use `CURMUX_SESSION` and `CURMUX_API_URL` from env):
1. **Claim**: `GET {CURMUX_API_URL}/api/tasks?status=todo` → pick a task → `POST {CURMUX_API_URL}/api/tasks/{id}/claim` with body `{"agent": "<CURMUX_SESSION>"}`.
2. **Done**: When the task is finished, `POST {CURMUX_API_URL}/api/tasks/{id}/done` (then commit). Do not skip—the board is the source of truth.

**Base URL**: `https://localhost:{port}` (TLS by default) or `http://localhost:{port}` with `--no-tls`. Default port: **8833**. No authentication (local use only). Send `Content-Type: application/json` for request bodies.

**Session identity**: curmux sets `CURMUX_SESSION`, `CURMUX_API_URL`, and `CURMUX_CONTEXT` in the process environment when starting a session. Use `CURMUX_SESSION` as `agent` when claiming tasks and as `sender` when posting messages; use `CURMUX_API_URL` as the base for all API requests; read `CURMUX_CONTEXT` for a short hint (API base, session, full API reference, agents doc). Full reference: GET /api/docs. Agents doc (this file): GET /api/agents.

### Environment

When the process is started by curmux (`curmux start` or `curmux exec`), these variables are set:

| Variable | Description |
|----------|-------------|
| `CURMUX_SESSION` | Session name. Use as `agent` when claiming tasks and as `sender` in messages. |
| `CURMUX_API_URL` | Base URL (default `http://localhost:8833`). |
| `CURMUX_CONTEXT` | Short hint: "You're in curmux. API base: … Your session: … Full API reference: GET …/api/docs. Agents doc: GET …/api/agents". |

They are only set when the process is started by curmux.

### Sessions

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/sessions` | List all sessions. Each item: `name`, `directory`, `yolo`, `model`, `worktree`, `running`, `detected_status`, plus DB fields. Layout sessions include `layout: true` and `agent_panes: [{agent_id, status}]`. |
| GET | `/api/sessions/{name}/status` | Status for one session: `name`, `status`, `running`. Layout sessions return `layout: true` and `panes: [{pane_index, agent_id, status}]`. |
| GET | `/api/sessions/{name}/peek?lines=200&pane=` | Recent pane output. Optional `pane` (pane index or agent_id) for layout sessions. |
| POST | `/api/sessions/{name}/send` | Send keys to session. Body: `{"text": "..."}`. Optional `"pane": index or agent_id` for layout sessions. |

### Task board

Agents should work from the task board for all non-trivial work. If no task exists for the work at hand, ask the user if a task should be created. Then: break the work into tasks, create them (POST /api/tasks or dashboard), claim one (POST /api/tasks/{id}/claim), complete it, then **POST /api/tasks/{id}/done** before claiming another. Closure for a claimed task: (1) mark done via the API, (2) commit. Skipping the done call leaves the board out of sync.

Tasks have status: `todo` → `claimed` → `done`. Filter by `status` and optionally `project`.

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/tasks?project=&status=` | List tasks. Query params optional: `project`, `status` (todo/claimed/done). |
| POST | `/api/tasks` | Create task. Body: `{"project": "", "title": "", "description": ""}`. Returns `{"ok": true, "id": "..."}`. |
| POST | `/api/tasks/{id}/claim` | Claim a todo task atomically. Body: `{"agent": "<session-name>"}`. Returns 409 if not todo. |
| POST | `/api/tasks/{id}/done` | Mark task done. |
| PATCH | `/api/tasks/{id}` | Update task. Body: `{"status": "todo"|"claimed"|"done", "claimed_by": ""}` (claimed_by optional). 400 if invalid status, 404 if not found. |
| DELETE | `/api/tasks/{id}` | Delete a task. |

### Memory (shared key-value)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/memory` | List all keys and values. |
| GET | `/api/memory?key=<key>` | Get one value (empty object if missing). |
| POST | `/api/memory` | Set or overwrite. Body: `{"key": "", "value": ""}`. |

### Messages (agent-to-agent)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/messages` | List recent messages (limit 100). |
| GET | `/api/messages?recipient=<name>` | Messages for one session. |
| POST | `/api/messages` | Send. Body: `{"sender": "", "recipient": "", "body": ""}`. |

### Alerts

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/alerts?limit=50` | Recent alerts (e.g. start/stop events). |

### Agents doc

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/agents` | Returns AGENTS.md (this file) as text/markdown. |

### Stream (API call log)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/stream?limit=50` | Recent API calls (timestamp, caller, method, path). |

Optional request header **X-Curmux-Session** identifies the caller in the dashboard Stream tab.

### API reference (GET /api/docs)

When the server is running, GET /api/docs returns the full API reference. Use GET {CURMUX_API_URL}/api/docs so the reference is unambiguous regardless of repo.

### Optional seed (--seed)

You can start sessions with `curmux start <name> --seed` or `curmux exec <name> --dir <path> --seed` to send a one-line prompt so the agent reads CURMUX_CONTEXT from the environment.

### Layout sessions

Sessions created with `curmux layout` use a `.curmux.conf` YAML file (see `docs/curmux-conf-plan.md`). They are registered like normal sessions and get the same watchdog for panes with `command: agent`. Per-pane options: `focus: true` or `focused: true` to set which pane is active when you attach (default: first pane). Multiple agent panes get distinct `CURMUX_SESSION` via `agent_id` (or derived ids) so they can claim different tasks. The dashboard shows a Layout badge and per-agent status; Peek and Send support an optional `pane` (agent_id or index).
