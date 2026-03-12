# Plan: Mac menu bar launcher for `curmux serve`

## Goal

A small macOS menu bar app that runs in the background and lets you start/stop `curmux serve` and open the dashboard without keeping a terminal window open. One-click "Start", "Open Dashboard", "Stop" from the menu bar.

## Scope

- **Menu bar item** — Icon + dropdown menu.
- **Actions:**
  - **Start serve** — Run `curmux serve` with options from config (port, `--no-tls`) in the background; update menu to show "Stop serve".
  - **Stop serve** — Kill the curmux serve process.
  - **Open Dashboard** — Open the dashboard URL in the default browser (scheme and port from config: `http` when `no_tls`, else `https`; default port 8833).
  - **Attach to …** — Submenu of sessions; each item launches the user’s **configurable terminal** and runs `tmux attach -t curmux-<session-name>` so they attach to that session in one click.
  - **Quit** — Stop serve if running, exit the launcher.
- **State:** Menu reflects whether serve is running (e.g. "● Running" vs "○ Stopped", or enable/disable Start vs Stop).
- **Single instance:** Launcher runs once; no need to support multiple curmux serve instances from the same launcher.

**CLI verb:** `curmux menubar {start|stop|status}` so the launcher is started and queried from the same tool.

- **`curmux menubar start`** — Launch the menu bar app (run the rumps script). Detach so the terminal returns; the app keeps running in the menu bar. If already running, no-op or warn.
- **`curmux menubar stop`** — Stop the running menu bar app (send SIGTERM to the process). PID file under `$XDG_RUNTIME_DIR/curmux/menubar.pid` (fallback when unset: `~/.curmux/menubar.pid`).
- **`curmux menubar status`** — Print whether the menu bar app is running; optionally whether `curmux serve` is running (if we can infer it from the same PID file or the app’s state). Exit 0 if running, non-zero if not.

## Out of scope (for now)

- Configuring port/TLS from the launcher **UI** (user edits config file; no in-app settings dialog).
- Linux/Windows (menu bar is macOS-specific).
- Embedding the dashboard inside the app (open in browser is enough).

## Extensibility (post-MVP)

The launcher should be **extensible** so we can add more curmux features later without reworking the structure. Not part of MVP, but the design should accommodate:

- **Board** — e.g. “Open Board” (dashboard #board) or a submenu “Board” with quick actions (list tasks, open board in browser). URL from config (scheme + port). (future)
- **Alerts** — e.g. “Alerts” submenu or “Open Alerts” (dashboard #alerts); or poll GET /api/alerts and show unread count in the menu bar icon/tooltip (future).
- **Stream** — e.g. “Open Stream” (dashboard #stream) or “Recent API calls” submenu backed by GET /api/stream (future).

**MVP** = Start/Stop serve, Open Dashboard, Attach to …, Quit. No board/alerts/stream in the first version. Keep the menu layout and config (e.g. one main menu built from a list of “sections”) so we can add these as extra items or submenus later without changing the core app shape.

## Implementation: Python + rumps

We will implement the launcher as a **Python + rumps** app (Ridiculously Uncomplicated macOS Python Statusbar apps, PyObjC-based). One script, same ecosystem as curmux; no Xcode. Requires `pip install rumps`; subprocess work (start serve, attach) runs in threads so the menu stays responsive.

**Layout:** `menubar/curmux_menubar.py`, optional `menubar/requirements.txt`. User runs `curmux menubar start` (CLI invokes the script and detaches); optionally package as .app via py2app later.

**Sketch:** On start, track one serve process (PID). Menu: Start serve / Stop serve, Open Dashboard, Attach to … (submenu), Quit. Start serve: build argv from config (port, --no-tls), `Popen` in a daemon thread. Open Dashboard: build URL from config and `webbrowser.open(url)`. Use a timer or thread to poll process liveness and refresh menu state.

## Implementation details

1. **Locate curmux** — `shutil.which("curmux")` or `sys.executable` + same dir as script; prefer PATH so it uses the user’s installed curmux.
2. **Process management** — `Popen([curmux_bin, "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)` so it’s a separate process group; store `proc` and `proc.pid`. On Stop: `proc.terminate()` then `proc.wait(timeout=5)` or `proc.kill()`.
3. **Threading** — Start serve in a `threading.Thread(target=..., daemon=True)` so the rumps callback returns immediately; use a lock or a simple "serving" flag to avoid double-start. Poll `proc.poll() is not None` to detect exit and update menu (e.g. rumps timer every 2–5 s).
4. **Menu structure:**
   - Title: "curmux" or icon (simple text "●" when running, "○" when stopped, or a small image).
   - "Start serve" (enabled when not running) / "Stop serve" (enabled when running).
   - "Open Dashboard" (always; opens dashboard URL from config).
   - "Attach to …" → submenu of sessions (each item: "Attach to &lt;name&gt;").
   - Separator.
   - "Quit".
5. **Serve options (config):** Read from the same config file: **`port`** (default `8833`), **`no_tls`** (default `false`). When starting serve, run `curmux serve --port <port>` and add `--no-tls` when `no_tls` is true. When opening the dashboard or calling the API (e.g. for Attach session list), use base URL `http://localhost:<port>` if `no_tls` else `https://localhost:<port>`. So the user controls `--no-tls` (and port) by editing `~/.config/curmux/menubar.conf`; no UI for it in MVP.
6. **Packaging:** README section: "Menu bar launcher (macOS): `pip install rumps` then `python3 menubar/curmux_menubar.py`." Optional: py2app or brief note on building a .app.
7. **Extensibility:** Build the menu from a small list of sections (e.g. serve actions, attach submenu, links, quit) so post-MVP we can insert Board, Alerts, Stream as extra sections or “Open Board” / “Open Alerts” / “Open Stream” items (or submenus) without refactoring.

## Attach to … (configurable terminal)

- **Submenu:** "Attach to …" expands to one menu item per **session** (e.g. "Attach to curmux", "Attach to myproject"). Clicking an item launches the configured terminal and attaches to that session.
- **Session list:** When serve is running, GET `<base_url>/api/sessions` (base URL from config: scheme + port, e.g. `http://localhost:8833` when `no_tls`) to list sessions; build the submenu from that. When serve is not running, show the submenu as disabled or with a single item "Start serve first". Optional: when serve is stopped, read session names from `~/.curmux/curmux.db` so "Attach to …" still works (user can attach without starting the dashboard); if we don’t want to depend on SQLite in the menubar app, keep "Attach" only when serve is running.
- **Configurable terminal:** User chooses which app is used to run `tmux attach -t curmux-<name>`. Config file: `$XDG_CONFIG_HOME/curmux/menubar.conf` (when `XDG_CONFIG_HOME` is unset, use `~/.config/curmux/menubar.conf`).
  - **`terminal`** (string): One of a known set of identifiers, e.g. `Terminal`, `iTerm`, `WezTerm`, `Warp`, or a custom command template (see below). Default: `Terminal` (macOS Terminal.app).
  - Optional **`terminal_command`**: Shell command template; `{cmd}` is replaced with the attach command (e.g. `tmux attach -t curmux-mysession`). Example: `open -a iTerm -e '{cmd}'` or `wezterm start -- {cmd}`. If set, this overrides `terminal`.
- **How we launch:**
  - **Terminal.app:** AppleScript: `tell application "Terminal" to do script "<attach command>"` (new window with that command).
  - **iTerm:** AppleScript or `open -a iTerm` with appropriate args; or `osascript -e 'tell application "iTerm" to create window with default profile'` and then run the command (iTerm’s API varies).
  - **WezTerm:** `wezterm start -- tmux attach -t curmux-<name>` (if wezterm is on PATH).
  - **Warp / others:** Either add a known template or rely on `terminal_command` so the user can supply `open -a Warp -e '{cmd}'` or similar.
- **Implementation:** Map `terminal` to a built-in template (e.g. `Terminal` → run osascript with "do script …"); if `terminal_command` is set, `subprocess.run(["sh", "-c", template.format(cmd="tmux attach -t curmux-" + session_name)])`. Run in a thread so the menu doesn’t block.

## CLI: `curmux menubar {start|stop|status}`

- **start** — Resolve path to `menubar/curmux_menubar.py` (relative to curmux script or install). Run it with `python3` in a detached process (e.g. `subprocess.Popen(..., start_new_session=True)`, close stdio so the terminal returns). Write child PID to the PID file (path below). If PID file exists and that process is alive, no-op or print "already running". The menubar app removes the PID file on exit (atexit or on Quit) so we don’t leave a stale file.
- **stop** — Read PID from the PID file; send SIGTERM; remove PID file. If no file or process gone, print "not running" and exit 0 (idempotent).
- **status** — If PID file exists and process is alive, print "running" (and optionally PID); exit 0. Else print "stopped"; exit 1 (or 0 for "not running", depending on scriptability preference).

**PID file path:** `$XDG_RUNTIME_DIR/curmux/menubar.pid` when `XDG_RUNTIME_DIR` is set; otherwise `~/.curmux/menubar.pid`. CLI and menubar app both use this (same env resolution). Create parent directory if needed.

The main `curmux` script gains a subparser: `curmux menubar` with subcommands `start`, `stop`, `status`. On macOS only (or no-op with a message on other platforms).

## File layout

- `menubar/curmux_menubar.py` — Single-file rumps app. Invoked by `curmux menubar start` (curmux CLI runs it).
- PID file: `$XDG_RUNTIME_DIR/curmux/menubar.pid` when set, else `~/.curmux/menubar.pid`; used by CLI and menubar app for stop/status.
- Config: `$XDG_CONFIG_HOME/curmux/menubar.conf` (default `~/.config/curmux/menubar.conf`) for **serve** (`port`, `no_tls`), **terminal** (`terminal`, optional `terminal_command`). Example:
  - `port: 8833` (default)
  - `no_tls: true` to use `http` and pass `--no-tls` to `curmux serve`
  - `terminal: Terminal` (or `iTerm`, `WezTerm`, `Warp`)
  - `terminal_command: "wezterm start -- {cmd}"` (optional override)
- `menubar/README.md` or a section in main README — `curmux menubar start` / stop / status; optional .app build; config keys.
- Optional: `menubar/requirements.txt` with `rumps`.

## Order of work

| Step | What |
|------|------|
| 1 | Add `curmux menubar` subparser with `start`, `stop`, `status`. Implement start (run menubar script detached, write PID file), stop (read PID, SIGTERM, remove file), status (read PID, report running/stopped). PID file: $XDG_RUNTIME_DIR/curmux/menubar.pid (fallback ~/.curmux/menubar.pid). |
| 2 | Add `menubar/curmux_menubar.py`: rumps app, menu items Start/Stop, Open Dashboard, Quit. On startup, write own PID to the same PID file (or CLI writes it only when starting the child). |
| 3 | Implement serve start/stop in app: find curmux, Popen in thread (argv from config), store process; stop: terminate process; update menu state. Optional timer: poll process and update menu if it exits externally. |
| 4 | Attach: "Attach to …" submenu; when serve running, GET /api/sessions and build one item per session. |
| 5 | Config: read menubar.conf for `port` (8833), `no_tls` (false), `terminal` (default Terminal), optional `terminal_command`. Use port + no_tls when starting serve and when building dashboard/API URLs; implement terminal launch for Terminal.app and at least one other (e.g. WezTerm). |
| 6 | On "Attach to &lt;name&gt;": run configured terminal with `tmux attach -t curmux-&lt;name&gt;` in a thread. |
| 7 | Docs: README section "Menu bar launcher (macOS)" — `curmux menubar start` / stop / status, rumps dependency, config. |

## Summary

- **Scrap:** Launch-terminal / "Terminal" button plan (removed).
- **New:** Mac menu bar launcher for `curmux serve`: **`curmux menubar start`** (launch), **`curmux menubar stop`** (quit launcher), **`curmux menubar status`** (running or not). Launcher menu: Start/Stop serve, Open Dashboard, **Attach to …** (submenu; configurable terminal), Quit. Config: `~/.config/curmux/menubar.conf` (port, no_tls, terminal). Implement with Python + rumps; PID file for stop/status; optional .app packaging later.
