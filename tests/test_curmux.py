"""Tests for curmux — Cursor Agent Multiplexer."""

import ast
import importlib.machinery
import importlib.util
import os
import shutil
import subprocess
import time
from pathlib import Path

import pytest


@pytest.fixture()
def curmux():
    """Import curmux as a module from the single-file executable."""
    curmux_path = Path(__file__).parent.parent / "curmux"
    loader = importlib.machinery.SourceFileLoader("curmux", str(curmux_path))
    spec = importlib.util.spec_from_loader("curmux", loader, origin=str(curmux_path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture()
def tmp_data_dir(tmp_path, curmux, monkeypatch):
    """Redirect curmux data to a temp directory."""
    monkeypatch.setattr(curmux, "DATA_DIR", tmp_path)
    monkeypatch.setattr(curmux, "DB_PATH", tmp_path / "curmux.db")
    # Reset thread-local DB connection
    if hasattr(curmux._local, "db"):
        del curmux._local.db
    curmux.init_db()
    return tmp_path


# ── Syntax ───────────────────────────────────────────────────────────────


class TestSyntax:
    def test_valid_python(self):
        src = (Path(__file__).parent.parent / "curmux").read_text()
        ast.parse(src)

    def test_executable_help(self):
        r = subprocess.run(
            [str(Path(__file__).parent.parent / "curmux"), "--help"],
            capture_output=True,
            text=True,
        )
        assert r.returncode == 0
        assert "Cursor Agent Multiplexer" in r.stdout

    def test_version(self):
        r = subprocess.run(
            [str(Path(__file__).parent.parent / "curmux"), "--version"],
            capture_output=True,
            text=True,
        )
        assert r.returncode == 0
        assert "curmux" in r.stdout


# ── Database ─────────────────────────────────────────────────────────────


class TestDatabase:
    def test_init_creates_tables(self, curmux, tmp_data_dir):
        db = curmux.get_db()
        tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        assert {"sessions", "tasks", "messages", "memory", "alerts"}.issubset(tables)

    def test_wal_mode(self, curmux, tmp_data_dir):
        db = curmux.get_db()
        mode = db.execute("PRAGMA journal_mode").fetchone()[0]
        assert mode == "wal"


# ── Session management ───────────────────────────────────────────────────


class TestSessions:
    def test_register_and_list(self, curmux, tmp_data_dir, tmp_path):
        db = curmux.get_db()
        project_dir = str(tmp_path / "project")
        os.makedirs(project_dir)
        db.execute(
            "INSERT INTO sessions (name, directory, yolo, model, worktree) VALUES (?, ?, ?, ?, ?)",
            ("test-session", project_dir, 1, "sonnet-4", 0),
        )
        db.commit()
        row = db.execute("SELECT * FROM sessions WHERE name=?", ("test-session",)).fetchone()
        assert row is not None
        assert row["directory"] == project_dir
        assert row["yolo"] == 1
        assert row["model"] == "sonnet-4"

    def test_resolve_name_exact(self, curmux, tmp_data_dir, tmp_path):
        db = curmux.get_db()
        project_dir = str(tmp_path / "project")
        os.makedirs(project_dir)
        db.execute("INSERT INTO sessions (name, directory) VALUES (?, ?)", ("myproject", project_dir))
        db.commit()
        assert curmux.resolve_name("myproject") == "myproject"

    def test_resolve_name_prefix(self, curmux, tmp_data_dir, tmp_path):
        db = curmux.get_db()
        project_dir = str(tmp_path / "project")
        os.makedirs(project_dir)
        db.execute("INSERT INTO sessions (name, directory) VALUES (?, ?)", ("myproject", project_dir))
        db.commit()
        assert curmux.resolve_name("myp") == "myproject"

    def test_resolve_name_ambiguous(self, curmux, tmp_data_dir, tmp_path):
        db = curmux.get_db()
        project_dir = str(tmp_path / "project")
        os.makedirs(project_dir)
        db.execute("INSERT INTO sessions (name, directory) VALUES (?, ?)", ("myproject", project_dir))
        db.execute("INSERT INTO sessions (name, directory) VALUES (?, ?)", ("myother", project_dir))
        db.commit()
        with pytest.raises(SystemExit):
            curmux.resolve_name("my")

    def test_resolve_name_not_found(self, curmux, tmp_data_dir):
        with pytest.raises(SystemExit):
            curmux.resolve_name("nonexistent")


# ── Task board ───────────────────────────────────────────────────────────


class TestTaskBoard:
    def test_create_task(self, curmux, tmp_data_dir):
        db = curmux.get_db()
        task_id = f"TEST-{curmux._short_id()}"
        db.execute(
            "INSERT INTO tasks (id, project, title, description) VALUES (?, ?, ?, ?)",
            (task_id, "TEST", "Build feature", "A test task"),
        )
        db.commit()
        row = db.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
        assert row["title"] == "Build feature"
        assert row["status"] == "todo"

    def test_claim_task_atomic(self, curmux, tmp_data_dir):
        db = curmux.get_db()
        task_id = f"TEST-{curmux._short_id()}"
        db.execute("INSERT INTO tasks (id, project, title) VALUES (?, ?, ?)", (task_id, "TEST", "Claimable"))
        db.commit()

        row = db.execute(
            "UPDATE tasks SET status='claimed', claimed_by=?, claimed_at=? WHERE id=? AND status='todo' RETURNING *",
            ("agent-1", time.time(), task_id),
        ).fetchone()
        db.commit()
        assert row is not None
        assert row["claimed_by"] == "agent-1"

        # Second claim should fail (already claimed)
        row2 = db.execute(
            "UPDATE tasks SET status='claimed', claimed_by=?, claimed_at=? WHERE id=? AND status='todo' RETURNING *",
            ("agent-2", time.time(), task_id),
        ).fetchone()
        assert row2 is None

    def test_complete_task(self, curmux, tmp_data_dir):
        db = curmux.get_db()
        task_id = f"TEST-{curmux._short_id()}"
        db.execute(
            "INSERT INTO tasks (id, project, title, status) VALUES (?, ?, ?, ?)",
            (task_id, "TEST", "Done task", "claimed"),
        )
        db.commit()
        db.execute("UPDATE tasks SET status='done', completed_at=? WHERE id=?", (time.time(), task_id))
        db.commit()
        row = db.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
        assert row["status"] == "done"
        assert row["completed_at"] is not None


# ── Memory ───────────────────────────────────────────────────────────────


class TestMemory:
    def test_write_and_read(self, curmux, tmp_data_dir):
        db = curmux.get_db()
        db.execute(
            "INSERT OR REPLACE INTO memory (key, value, updated_at) VALUES (?, ?, ?)",
            ("schema", "users(id,email)", time.time()),
        )
        db.commit()
        row = db.execute("SELECT * FROM memory WHERE key=?", ("schema",)).fetchone()
        assert row["value"] == "users(id,email)"

    def test_upsert(self, curmux, tmp_data_dir):
        db = curmux.get_db()
        db.execute("INSERT OR REPLACE INTO memory (key, value, updated_at) VALUES (?, ?, ?)", ("k", "v1", time.time()))
        db.commit()
        db.execute("INSERT OR REPLACE INTO memory (key, value, updated_at) VALUES (?, ?, ?)", ("k", "v2", time.time()))
        db.commit()
        row = db.execute("SELECT * FROM memory WHERE key=?", ("k",)).fetchone()
        assert row["value"] == "v2"


# ── Messages ─────────────────────────────────────────────────────────────


class TestMessages:
    def test_send_and_receive(self, curmux, tmp_data_dir):
        db = curmux.get_db()
        db.execute(
            "INSERT INTO messages (sender, recipient, body) VALUES (?, ?, ?)", ("api", "frontend", "schema changed")
        )
        db.commit()
        rows = db.execute("SELECT * FROM messages WHERE recipient=?", ("frontend",)).fetchall()
        assert len(rows) == 1
        assert rows[0]["body"] == "schema changed"
        assert rows[0]["sender"] == "api"


# ── Status detection ─────────────────────────────────────────────────────


class TestStatusDetection:
    def test_empty_output(self, curmux):
        assert curmux._detect_status("") == "unknown"
        assert curmux._detect_status(None) == "unknown"

    def test_shell_prompt_detected(self, curmux):
        output = "some output\nmark@raven:~/project$ "
        assert curmux._at_shell_prompt(output) is True

    def test_no_shell_prompt(self, curmux):
        output = "Working on something...\nReading files"
        assert curmux._at_shell_prompt(output) is False

    def test_exited_status(self, curmux):
        output = "some agent output\nmark@raven:~/project$ "
        assert curmux._detect_status(output) == "exited"

    def test_working_status(self, curmux):
        output = "Processing request\nthinking about the problem\nGenerating code"
        assert curmux._detect_status(output) == "working"

    def test_error_status(self, curmux):
        output = "Running tests\nTraceback (most recent call last):\n  File error"
        assert curmux._detect_status(output) == "error"


# ── Tmux helpers ─────────────────────────────────────────────────────────


class TestTmux:
    def test_session_name_prefix(self, curmux):
        assert curmux.tmux_session_name("myproject") == "curmux-myproject"

    @pytest.mark.skipif(not shutil.which("tmux"), reason="tmux not installed")
    def test_has_session_false(self, curmux):
        assert curmux.tmux_has_session("nonexistent-session-12345") is False

    @pytest.mark.skipif(not shutil.which("tmux"), reason="tmux not installed")
    def test_new_and_kill_session(self, curmux, tmp_path):
        name = f"test-{os.getpid()}"
        curmux.tmux_new_session(name, ["sleep", "300"], tmp_path)
        try:
            assert curmux.tmux_has_session(name) is True
            output = curmux.tmux_capture(name, 10)
            assert isinstance(output, str)
        finally:
            curmux.tmux_kill_session(name)
        assert curmux.tmux_has_session(name) is False


# ── Alerts ───────────────────────────────────────────────────────────────


class TestAlerts:
    def test_push_alert(self, curmux, tmp_data_dir):
        curmux._push_alert("test_alert", "test-session", "Something happened")
        db = curmux.get_db()
        rows = db.execute("SELECT * FROM alerts").fetchall()
        assert len(rows) == 1
        assert rows[0]["type"] == "test_alert"
        assert rows[0]["session"] == "test-session"

    def test_short_id_uniqueness(self, curmux):
        ids = {curmux._short_id() for _ in range(100)}
        assert len(ids) == 100
