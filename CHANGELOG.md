# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.1] - 2026-03-11

### Fixed

- Ruff SIM118: use `key in dict` instead of `key in dict.keys()` in row serialization

## [0.2.0] - 2026-03-10

### Added

- `update` command (alias: `set`) for partial session updates — change `--dir`, `--yolo`, `--no-yolo`, `--model`, `--worktree`, `--no-worktree` without re-registering
- `rm` command (aliases: `remove`, `del`) to delete sessions — stops tmux if running, cleans up messages, alerts, and task assignments

## [0.1.0] - 2026-03-10

### Added

- Single-file `curmux` executable — CLI, REST API, web dashboard, and watchdog
- Session management: `register`, `start`, `stop`, `attach`, `peek`, `send`, `exec`, `ls`
- Self-healing watchdog: auto-restart exited agents, auto-accept confirmations in yolo mode, stuck detection
- SQLite-backed task board with atomic claiming (CAS): `board add`, `board claim`, `board done`
- Web dashboard with session cards, live peek modal, kanban board, and alerts feed
- REST API for sessions, tasks, shared memory, and inter-agent messaging
- `--yolo`, `--model`, `--worktree` flags for session configuration
- Prefix matching for session names
- Auto-generated TLS (mkcert or self-signed fallback)
- One-line install via `install.sh` or direct `curl`
- GitHub Actions CI: ruff lint/format, shellcheck, pre-commit, pytest (Python 3.9 + 3.12)
- Pre-commit hooks: yaml/json check, trailing whitespace, ruff, gitleaks, commitlint, shellcheck
- EditorConfig and ruff.toml for consistent formatting
- 27 tests covering database, sessions, task board, memory, messages, status detection, tmux, and alerts
- Commitlint config enforcing conventional commits
- SVG dashboard diagrams (sessions, board, peek)
- MIT license

### Fixed

- Use `cursor-agent` binary instead of `cursor agent` (opens IDE instead of TUI)
- Pass tmux commands as single shell string via `shlex.quote`

[Unreleased]: https://github.com/mamercad/curmux/compare/v0.2.1...HEAD
[0.2.1]: https://github.com/mamercad/curmux/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/mamercad/curmux/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/mamercad/curmux/releases/tag/v0.1.0
