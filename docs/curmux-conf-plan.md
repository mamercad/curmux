# Plan: .curmux.conf — layout-driven sessions

## Goal

Support a project-level config file (`.curmux.conf`) that defines how curmux creates a tmux session: optional pre-launch hook, rows/panes with sizes and commands, pane titles and env, and optional theme overrides. One session is created per config; panes can run arbitrary commands (editor, dev server, tests, shell, or cursor-agent).

## Use cases

- **Dev layout:** Editor + shell + dev server + test runner in a reproducible layout.
- **Curmux-agent layout:** One or more panes run `cursor-agent` with curmux env vars injected. For **sub-agent / multi-agent** layouts (multiple agent panes), each pane gets a distinct `CURMUX_SESSION` (via optional `agent_id` or derived id) so they can claim different tasks and coordinate via the board and messages.
- **Before hook:** e.g. `pnpm install` or `docker compose up -d` so the session starts with deps ready.

## File location and discovery

- **Primary:** `.curmux.conf` in the session working directory (the `--dir` used when starting, or cwd for `curmux layout`).
- **Override:** Optional `curmux layout --config /path/to/file` or `-c` to use another path.
- **Format:** YAML. No new runtime dependency: parse with stdlib or a small inline parser (e.g. key-value and list parsing). If we want full YAML, we can document “requires PyYAML when using .curmux.conf” or ship a minimal YAML subset (indent-based blocks, key: value, - list) to stay zero-deps.

## Schema (formal)

```yaml
# Required. Becomes the tmux session name (curmux prefix applied by curmux).
name: project-name

# Optional. Single shell command run once before creating the session, in session directory.
# Non-zero exit: abort session creation (or warn and continue — TBD).
before: pnpm install

# Required. List of rows. Order = top to bottom. At least one row, each with at least one pane.
rows:
  - size: 70%              # optional; row height as percentage (1-100). Default: equal split.
    panes:
      - title: Editor       # optional; pane border title (tmux pane-border-status / pane border format)
        command: vim        # optional; command to run in pane (default: shell)
        size: 60%           # optional; pane width within row (%). Default: equal split.
        dir: apps/web       # optional; subdir under session root. Default: session root.
        focus: true         # optional; focus: true or focused: true — which pane is active when you attach. Default: first pane.
        env:                 # optional; key-value env for this pane
          PORT: 3000
      - title: Agent
        command: agent      # reserved: runs Cursor Agent; curmux injects CURMUX_* env
        agent_id: main      # optional; distinct identity when multiple agent panes (sub-agent layouts)
        row_span: 2         # optional; pane spans 2 rows (e.g. right column full height)
      - title: Shell        # command omitted => $SHELL

  - panes:                  # size omitted => equal row height; row 2 has one fewer pane where row_span applied
      - title: Dev Server
        command: pnpm dev
      - title: Tests
        command: pnpm test

# Optional. Tmux style overrides for this session (session options or global for session).
# Values: tmux colour names (e.g. colour75, colour238, default) or hex.
theme:
  accent: colour75
  border: colour238
  bg: colour235
  fg: colour248
```

### Schema rules (validation)

- `name`: non-empty string; must be a valid tmux session name (curmux will prefix).
- `before`: string; run with `sh -c '...'` in session directory.
- `rows`: list of at least one row. Each row:
  - `size`: optional number or "N%"; 0 < N <= 100; default 100/len(rows).
  - `panes`: list of at least one pane. Each pane:
    - `title`: optional string.
    - `command`: optional string; default no command (interactive shell).
    - `size`: optional "N%" for pane width in row; default equal.
    - `dir`: optional string; relative to session root.
    - `focus`: optional boolean; only first `focus: true` wins. `focused: true` is an alias. Default: first pane gets focus when you attach.
    - `row_span`: optional integer (default 1); number of rows this pane spans. When &gt; 1, the pane is created in the first row and extends downward; following rows omit a pane slot for it (layout engine creates by splitting so one pane spans).
    - `agent_id`: optional string; when `command: agent`, this is the agent identity (`CURMUX_SESSION`). Must be unique among agent panes. Omitted: single agent → use config name; multiple agents → derived ids (e.g. `{name}-0`, `{name}-1`). See “Sub-agent / multi-agent layouts”.
    - `env`: optional map string -> string.
- `theme`: optional map; keys and values are tmux option names and colour values (no validation beyond “pass through to tmux”).

### Reserved command: `agent`

- **`command: agent`** — Reserved value meaning "run Cursor Agent" (the `cursor-agent` TUI binary). Curmux expands this to the same invocation used by `curmux start` and injects `CURMUX_SESSION`, `CURMUX_API_URL`, and `CURMUX_CONTEXT` into the pane environment so the agent can use the task board and API. Use this when a pane in the layout should be a curmux-coordinated agent; omit or use another command for shells, editors, and dev servers.

### Sub-agent / multi-agent layouts

When a layout has **more than one pane** with `command: agent`, each agent pane must have a **distinct identity** (`CURMUX_SESSION`) so they can claim different tasks, send messages to each other, and appear as separate agents on the board and in the API.

- **Optional pane field:** `agent_id` (string). When `command: agent`, this is the agent identity used for `CURMUX_SESSION` and in `CURMUX_CONTEXT`. Must be unique among agent panes in the same layout.
- **When `agent_id` is omitted:** If there is only one agent pane in the layout, use the config `name` as `CURMUX_SESSION` (same as today). If there are multiple agent panes, curmux derives distinct identities (e.g. `{name}-0`, `{name}-1` by pane index) so each pane gets a unique `CURMUX_SESSION`.
- **Validation:** If `agent_id` is set, it must be non-empty and unique across panes with `command: agent` in this config.
- **Watchdog:** When resolving “which panes are agent” for a layout session, store or derive the identity per pane so the watchdog can match status to the correct pane; agent_id (or derived id) is the logical agent name for that pane.

## Behaviour (high level)

1. **Resolve config:** Find `.curmux.conf` (or path from `-c`). Parse YAML; validate; abort on error with clear message.
2. **Session root:** Directory of the config file (or `--dir` if different). All relative `dir` in panes are under this root.
3. **Before hook:** If `before` is set, run it in session root; if it fails, abort (or warn and continue — decide in impl).
4. **Create session:** Use `name` (with curmux prefix) as tmux session name.
   - First pane: `tmux new-session -d -s <name> -c <root> [env and command for first pane]`.
   - Remaining panes: for each row and pane, `tmux split-window` (horizontal or vertical per row), set size, set pane title, set `dir` and `env`, run `command`. When a pane has **`row_span` &gt; 1**, create it in the first row and extend it downward (following rows do not add a pane in that column); the layout engine chooses creation order so one pane spans (e.g. build left column, then split right, then split left column vertically).
   - When `command` is **`agent`**: replace with the same cursor-agent invocation used by `curmux start`, and inject `CURMUX_SESSION`, `CURMUX_API_URL`, `CURMUX_CONTEXT` into that pane’s environment. `CURMUX_SESSION` is the pane’s `agent_id` if set, else the config `name` (single agent pane) or a derived id (multiple agent panes) so each agent has a distinct identity for the task board and messages.
   - Layout: use `split-window -h` / `split-window -v` and `select-layout` or `resize-pane` to approximate row/pane sizes (and row-span).
5. **Focus:** Select the pane with `focus: true` (or first pane) with `tmux select-pane -t <target>`.
6. **Theme:** Apply `theme` entries via `tmux set-option -t <session> ...` (or session options) so only this session is styled.

## Tmux mapping (concise)

- Session: `tmux new-session -d -s <name> -c <cwd> [cmd]` for first pane.
- New pane in same window: `tmux split-window -t <session> -h` or `-v` (then `resize-pane -t <pane> -x 60%` or similar for %). **Row-span:** to get one pane spanning multiple rows, create in order (e.g. new-session with top-left pane, split-window -h for right column, select left pane, split-window -v for bottom-left) so the right pane naturally spans full height.
- Pane title: `tmux select-pane -t <pane> -T "Editor"`.
- Pane cwd: `tmux send-keys -t <pane> 'cd apps/web' C-m` (or create pane with `-c` when supported).
- Pane env: prepend to command, e.g. `env PORT=3000 vim`, or use tmux’s `send-keys` to export and then run command.
- Focus: `tmux select-pane -t <session>:0.<pane_index>` (or equivalent).
- Theme: `tmux set-option -t <session> pane-active-border-style "fg=colour75"` etc.; map our `theme` keys to tmux option names (document which keys we support).

## CLI surface (settled)

- **Command:** `curmux layout` — create a tmux session from `.curmux.conf` and **register it** in the DB so it is first-class: appears in `curmux ls`, stoppable with `curmux stop <name>`, and subject to the watchdog when `curmux serve` is running.
- **Options:**
  - `-c PATH` — config file path (default: `.curmux.conf` in cwd).
  - `--dir PATH` — session root (default: directory of the config file).
- **Session name:** Always from config’s `name` (curmux prefix applied to the tmux session name). No positional override.
- **Registration:** On create, insert a row into `sessions` (same table as `curmux start`) with `name`, `directory`, and a way to mark the session as a layout session (e.g. `layout` flag or `config_path` column) so the watchdog can treat it differently (see below).

## Watchdog for layout sessions

Layout sessions are registered; the watchdog (when `curmux serve` is running) must apply to them so agent panes are not second-class. Extension:

- For sessions marked as layout sessions, the watchdog **finds the pane(s) that run `command: agent`** (from stored config path or metadata, or by re-reading the config).
- It runs the **same status detection and restart logic** on those panes only (e.g. cursor-agent exited → restart that pane with `--continue`; yolo auto-accept, etc.). Other panes (nvim, lazygit, pnpm dev) are not watched or restarted.
- So: layout sessions get full watchdog behavior for agent panes; non-agent panes are left as-is.

## Web UI and API

Layout sessions are registered and appear in the dashboard. The following changes keep the UI and API consistent with multi-pane layouts.

- **Sessions list (GET /api/sessions):** For layout sessions, include a `layout: true` (or similar) flag and, when available, **per–agent-pane status** so the dashboard can show each agent’s state (e.g. “curmux (main: idle, runner: working)”). The watchdog already tracks status per agent pane; expose that in the session payload (e.g. `agent_panes: [{ "agent_id": "main", "status": "idle" }, ...]`). Session cards in the UI can show a “Layout” badge and, for layout sessions, expand or list agent panes with their status instead of a single `detected_status`.
- **Peek (GET /api/sessions/{name}/peek):** Today `tmux capture-pane -t <session>` captures the **focused** pane. For layout sessions, support an optional **`pane`** query parameter (e.g. pane index or agent_id) so the user can choose which pane to view (nvim, agent, lazygit). If omitted, keep current behavior (focused pane). Dashboard: in the Peek modal, when the session is a layout, show a pane selector (dropdown or tabs) so the user can switch which pane’s output is shown.
- **Send (POST /api/sessions/{name}/send):** Today keys are sent to the session target; tmux sends to the **focused** pane. For layout sessions, support an optional **`pane`** in the request body (pane index or agent_id) so the user can target a specific pane (e.g. “send to agent”). If omitted, keep current behavior (focused pane). Dashboard: when opening send for a layout session, optionally let the user pick which pane to send to (default: focused).
- **Status (GET /api/sessions/{name}/status):** For layout sessions, return per-pane or per–agent-pane status (e.g. `layout: true`, `panes: [{ "pane_index": 0, "title": "nvim" }, { "pane_index": 1, "agent_id": "main", "status": "idle" }]`) so the UI and API consumers can show status per agent. Single-pane sessions keep the current shape (`status`, `running`) for backward compatibility.

**Implementation notes:** Backend needs to know which sessions are layout sessions and, for those, pane indices and agent_id mapping (from stored config or metadata). Tmux supports `capture-pane -t <session>:0.<pane_index>` and `send-keys -t <session>:0.<pane_index>` for per-pane targeting.

## Theme key mapping (proposal)

Map schema keys to tmux options (session or window level):

| Schema key | Tmux option / note |
|------------|---------------------|
| accent     | pane-active-border-style fg= |
| border     | pane-border-style fg= |
| bg         | pane default background (if supported) |
| fg         | pane default foreground (if supported) |

(Exact option names to be confirmed against tmux man; some may be window or global.)

## Order of work

| Step | What | Notes |
|------|------|--------|
| 1 | Define schema (this doc) and add example `.curmux.conf` in repo (e.g. `docs/example.curmux.conf`). | Done in plan. |
| 2 | Choose YAML: minimal parser (zero-deps) vs PyYAML. If minimal, implement small parser for the subset we need. | Prefer zero-deps; document if PyYAML required. |
| 3 | Implement config load + validate (path, parse, validate name/rows/panes/sizes). | Single function or small module in curmux. |
| 4 | Implement layout engine: given parsed config + session root, produce sequence of tmux commands (new-session, split-window, resize-pane, select-pane -T, send-keys, set-option). Support `row_span` via creation order. For each agent pane, assign distinct `CURMUX_SESSION` (from `agent_id` or derived id when multiple agents). | Can start with equal splits, then add % sizes. |
| 5 | Implement `before` hook (run in session root, fail or warn). | |
| 6 | Implement theme application (map keys to tmux set-option). | |
| 7 | Add CLI `curmux layout [-c CONFIG] [--dir PATH]`; session name from config.name. **Register** layout session in DB (mark as layout, store config path or equivalent so watchdog can find agent panes). | |
| 8 | Extend watchdog for layout sessions: when polling a layout session, find pane(s) with `command: agent`, run same status detection and restart (and yolo) logic on those panes only. | Re-use existing status detection and restart code; add path to resolve “which panes are agent” from config. |
| 9 | Web UI and API: sessions list expose layout flag and per–agent-pane status; peek/send support optional pane; status endpoint returns per-pane/agent status for layout sessions. Dashboard: layout badge, pane selector in Peek, optional pane target for Send. | See "Web UI and API" section. |
| 10 | Docs: README section, AGENTS.md note, and in-file help for `curmux layout`. | |
| 11 | Tests: unit tests for parser/validation; optional integration test (run layout in temp dir, check pane count / titles). | |

## Out of scope (later)

- Multiple windows (tabs) per session; schema could be extended with `windows:` and `rows` per window.
- `curmux start myproject` automatically using .curmux.conf from myproject’s dir (start-from-config); layout is a separate command for now.
- Watchdog for **non-agent** panes (e.g. restart `pnpm dev` on exit); only agent panes in layout sessions get restart logic.

## Example file (canonical)

The canonical example is the repo’s own layout: left column 70% width (nvim top 70% height, lazygit bottom 30% height), right column 30% width with Cursor Agent full height. Same content as repo root `.curmux.conf` and `docs/example.curmux.conf`:

```yaml
# Left: nvim (70%×70%) + lazygit (70%×30%). Right: agent (30%×100%).
name: curmux

rows:
  - size: 70%
    panes:
      - title: nvim
        command: nvim
        size: 70%
      - title: Agent
        command: agent
        size: 30%
        row_span: 2
  - size: 30%
    panes:
      - title: lazygit
        command: lazygit
        size: 70%
```
