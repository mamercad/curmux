#!/usr/bin/env python3
"""curmux menu bar launcher (macOS). Run via: curmux menubar start."""

import atexit
import os
import shutil
import signal
import ssl
import subprocess
import sys
import threading
import urllib.request
import webbrowser
from pathlib import Path

try:
    import rumps
except ImportError:
    print("curmux menubar requires rumps. Install with: pip install rumps", file=sys.stderr)
    sys.exit(1)

_PID_FILE = os.environ.get("CURMUX_MENUBAR_PID_FILE", "").strip()

# Config path: $XDG_CONFIG_HOME/curmux/menubar.conf or ~/.config/curmux/menubar.conf
def _config_path():
    xdg = os.environ.get("XDG_CONFIG_HOME", "").strip()
    if xdg:
        return Path(xdg) / "curmux" / "menubar.conf"
    return Path.home() / ".config" / "curmux" / "menubar.conf"


def _load_config():
    """Return dict with port (int), no_tls (bool)."""
    out = {"port": 8833, "no_tls": False}
    path = _config_path()
    if not path.exists():
        return out
    try:
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if ":" in line:
                key, _, val = line.partition(":")
                key, val = key.strip().lower(), val.strip().lower()
                if key == "port":
                    try:
                        out["port"] = int(val)
                    except ValueError:
                        pass
                elif key in ("no_tls", "no tls"):
                    out["no_tls"] = val in ("true", "1", "yes")
    except OSError:
        pass
    return out


def _curmux_bin():
    return shutil.which("curmux") or "curmux"


def _base_url(config):
    scheme = "http" if config["no_tls"] else "https"
    return f"{scheme}://localhost:{config['port']}"


# Process for curmux serve; set from background thread, read from main (timer)
_serve_proc = None
_serve_lock = threading.Lock()


def _serve_running_from_proc():
    """True if we started serve and it is still running."""
    with _serve_lock:
        p = _serve_proc
    return p is not None and p.poll() is None


def _serve_running(base_url):
    """True if serve is running: either we started it, or the dashboard URL responds."""
    if _serve_running_from_proc():
        return True
    try:
        ctx = ssl.create_default_context()
        if base_url.startswith("https"):
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
        urllib.request.urlopen(base_url, timeout=2, context=ctx)
        return True
    except Exception:
        return False


def _remove_pid_file():
    if _PID_FILE:
        try:
            Path(_PID_FILE).unlink(missing_ok=True)
        except OSError:
            pass


def _start_serve_thread(app, config):
    global _serve_proc
    with _serve_lock:
        if _serve_proc is not None and _serve_proc.poll() is None:
            return
    argv = [_curmux_bin(), "serve", "--port", str(config["port"])]
    if config["no_tls"]:
        argv.append("--no-tls")
    try:
        proc = subprocess.Popen(
            argv,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        with _serve_lock:
            _serve_proc = proc
    except Exception as e:
        rumps.notification("curmux", "Start serve failed", str(e), sound=False)


def _kill_serve_on_port(port):
    """Kill process(es) listening on port (e.g. curmux serve started from terminal)."""
    try:
        r = subprocess.run(
            ["lsof", "-i", f":{port}", "-t"],
            capture_output=True,
            text=True,
            timeout=2,
        )
        if r.returncode != 0 or not r.stdout.strip():
            return
        for pid_str in r.stdout.strip().splitlines():
            try:
                pid = int(pid_str.strip())
                os.kill(pid, signal.SIGTERM)
            except (ValueError, OSError, ProcessLookupError):
                pass
    except (OSError, subprocess.TimeoutExpired):
        pass


def _stop_serve(config=None):
    global _serve_proc
    with _serve_lock:
        p = _serve_proc
        _serve_proc = None
    if p is not None:
        try:
            p.terminate()
            p.wait(timeout=5)
        except (OSError, subprocess.TimeoutExpired):
            try:
                p.kill()
            except OSError:
                pass
        return
    if config is not None:
        _kill_serve_on_port(config["port"])


def main():
    if _PID_FILE:
        Path(_PID_FILE).parent.mkdir(parents=True, exist_ok=True)
        Path(_PID_FILE).write_text(str(os.getpid()))
        atexit.register(_remove_pid_file)
    atexit.register(_stop_serve)

    config = _load_config()
    base_url = _base_url(config)

    app = rumps.App("curmux", title="\u25cb", quit_button=None)  # ○ until timer sets state

    start_item = rumps.MenuItem("Start serve", callback=None)
    stop_item = rumps.MenuItem("Stop serve", callback=None)

    def start_serve_cb(_):
        def run():
            _start_serve_thread(app, config)
        threading.Thread(target=run, daemon=True).start()

    def stop_serve_cb(_):
        _stop_serve(config)

    def open_dashboard_cb(_):
        webbrowser.open(base_url)

    start_item.set_callback(start_serve_cb)
    stop_item.set_callback(None)

    app.menu = [
        start_item,
        stop_item,
        rumps.MenuItem("Open Dashboard", callback=open_dashboard_cb),
        rumps.separator,
        rumps.MenuItem("Quit", callback=lambda _: rumps.quit_application()),
    ]

    def update_serve_menu(_):
        running = _serve_running(base_url)
        app.title = "\U0001f7e2" if running else "\u25cb"  # green circle when running, ○ when stopped
        start_item.set_callback(None if running else start_serve_cb)
        stop_item.set_callback(stop_serve_cb if running else None)

    rumps.Timer(update_serve_menu, interval=2).start()

    app.run()


if __name__ == "__main__":
    main()
