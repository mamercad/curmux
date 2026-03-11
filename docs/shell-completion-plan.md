# Plan: Shell completion for curmux

**Task:** curmux-DCB96C — *shell completion*  
**Claimed by:** curmux2

## Goal

Add Bash and Zsh completion so users get tab-completion for subcommands, session names, and task IDs. Single-file, stdlib-only.

## 1. Entry point

- Add a **`completion`** subcommand: `curmux completion bash` and `curmux completion zsh`.
- Each prints the corresponding completion script to stdout so users can:
  - **Bash:** `source <(curmux completion bash)` or install to `~/.local/share/bash-completion/completions/curmux` (or equivalent).
  - **Zsh:** `source <(curmux completion zsh)` or add to `fpath` and use `compdef`.

## 2. Completion surface

| Context | Completions |
|--------|-------------|
| After `curmux ` | Subcommands: `register`, `start`, `stop`, `update`, `rm`, `attach`, `peek`, `send`, `exec`, `ls`, `list`, `board`, `serve` |
| After `curmux board ` | Subcommands: `add`, `claim`, `done`, `list`, `ls` |
| Session name (positional) | For `start`, `stop`, `update`, `attach`, `peek`, `send`: session names from DB. For `exec`: same (new or existing). |
| After `curmux board claim ` or `curmux board done ` | Task IDs from DB (e.g. todo for claim; any for done). |
| `board add --project` | Optional: distinct `project` values from existing tasks. |
| Flags | Rely on shell default (e.g. `--dir` file completion) or omit for v1. |

## 3. Implementation approach

- **Internal helper:** a hidden or internal subcommand (e.g. `_complete` or a `completion`-time only path) that:
  - Is invoked by the generated script with the current line/words and point.
  - **Bash:** receives `COMP_LINE` and `COMP_POINT` (or equivalent), parses to determine what is being completed.
  - **Zsh:** receives `$words`-style input (e.g. as separate args).
  - Outputs one completion per line to stdout; script uses this to set `COMPREPLY` (Bash) or `compadd` (Zsh).

- **Parsing:** from the token list and cursor position, derive:
  - Top-level subcommand (if any).
  - Board subcommand (if under `board`).
  - Which positional we’re in (e.g. first positional = session name or task_id).
  - Whether we’re completing an option (e.g. `--project`) — optional for v1.

- **Data:**
  - Session names: `get_db()` → `SELECT name FROM sessions ORDER BY name`.
  - Task IDs: `get_db()` → `SELECT id FROM tasks` (and optionally status for claim vs done).
  - Projects: `SELECT DISTINCT project FROM tasks WHERE project != ''`.

- **No new deps:** keep everything in the single `curmux` script; completion logic can live in a small block that runs only when the completion entry point is used.

## 4. Steps (implementation order)

1. Add `completion` subparser with `shell` positional: `bash` | `zsh`.
2. Implement `_complete` (or equivalent) that:
   - Takes `shell`, then bash/zsh-specific args (line + point, or words).
   - Parses and determines context (command, board action, positional index).
   - Returns session names, task IDs, or subcommand list as appropriate.
3. Generate Bash script that:
   - Uses `complete -C 'curmux _complete bash ...'` or a wrapper that sets `COMPREPLY` from `curmux _complete bash "$COMP_LINE" $COMP_POINT`.
4. Generate Zsh script that:
   - Defines `_curmux` and uses `compdef _curmux curmux`; completion function calls `curmux _complete zsh` with words and feeds result to `compadd`.
5. Document in README: how to source or install the completion script for Bash and Zsh.

## 5. Edge cases and mitigation

| Edge case | Mitigation |
|-----------|------------|
| **DB not available** | Wrap any completion path that needs the DB in `try/except`. On `Exception` (e.g. no `~/.curmux/curmux.db` or DB locked), return no completions and exit 0. Do not print errors to stdout (the shell would treat them as completion candidates). Optionally log a short message to stderr so `source <(curmux completion bash)` doesn’t show it in normal use. |
| **Empty DB** | Same as above: queries return empty lists; completion helper prints nothing and exits 0. Shell shows no completions or falls back to default (e.g. filenames). |
| **Prefix matching** | Completion helper always receives the “current word” being completed (Bash: from `COMP_LINE`/`COMP_POINT`; Zsh: word at cursor). Filter every candidate list by that prefix before printing: e.g. `[n for n in session_names if n.startswith(current_word)]` for sessions; same for task IDs and subcommands. Never suggest completions that don’t match what the user has typed. |
| **Aliases** | Define completion only in terms of canonical subcommands (`ls`, `rm`, `board`, `update`, etc.). Do not branch on alias names (`list`, `remove`, `del`, `set`, `board ls`). Suggest only the canonical form; the existing parser already accepts aliases, so behavior is correct either way. |

## 6. Out of scope (v1)

- Fish completion (can add later with same `_complete` data).
- Completing flag values (e.g. `--format text|json`) beyond `--project`.
- Completing directory for `--dir` (leave to shell default).
