"""CDP Browser Daemon — Persistent Chrome via Chrome DevTools Protocol.

Usage:
    from blackreach.browser_cdp import ensure_daemon, stop_daemon
    ws_url = ensure_daemon()           # starts Chrome if needed, returns ws:// url
    stop_daemon()                      # best-effort cleanup

Architecture:
    - Chrome launched once with --remote-debugging-port=9222
    - Playwright connects via connect_over_cdp(ws_url)
    - Chrome stays alive across multiple agent runs
    - Same trick as browser-use/browser-harness
"""

import atexit
import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from typing import Optional

CDP_PORT = int(os.environ.get("BR_CDP_PORT", "9222"))
CDP_HTTP = f"http://127.0.0.1:{CDP_PORT}"

_CHROMIUM_PATH: Optional[str] = None


def _find_chromium() -> str:
    global _CHROMIUM_PATH
    if _CHROMIUM_PATH is not None:
        return _CHROMIUM_PATH

    # 1. Playwright chromium
    try:
        import playwright
        pw_root = Path(playwright.__file__).parent
        for pattern in ("*/chromium", "*/chrome*"):
            hits = list(pw_root.rglob(pattern.split("/")[-1]))
            for c in hits:
                if c.is_file() and os.access(c, os.X_OK):
                    _CHROMIUM_PATH = str(c)
                    return _CHROMIUM_PATH
    except Exception:
        pass

    # 2. System Chrome / Chromium
    for name in ("chromium", "chromium-browser", "google-chrome", "google-chrome-stable", "chrome"):
        path = shutil.which(name)
        if path:
            _CHROMIUM_PATH = path
            return _CHROMIUM_PATH

    # 3. Flatpak / common paths
    for p in (
        "/app/bin/chromium",
        "/usr/bin/chromium",
        "/usr/bin/google-chrome",
        "/usr/bin/google-chrome-stable",
        "/var/lib/flatpak/exports/bin/com.google.Chrome",
    ):
        if Path(p).exists():
            _CHROMIUM_PATH = p
            return _CHROMIUM_PATH

    raise RuntimeError(
        "No Chrome/Chromium found. Install one:\n"
        "  playwright install chromium\n"
        "  or: sudo pacman -S chromium"
    )


def _port_open(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=1):
            return True
    except OSError:
        return False


def _cdp_responding(timeout: float = 3.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            req = urllib.request.urlopen(f"{CDP_HTTP}/json/version", timeout=1)
            data = json.loads(req.read())
            return bool(data.get("webSocketDebuggerUrl"))
        except Exception:
            time.sleep(0.2)
    return False


def _resolve_ws() -> str:
    with urllib.request.urlopen(f"{CDP_HTTP}/json/version", timeout=5) as resp:
        data = json.loads(resp.read())
    return data["webSocketDebuggerUrl"]


# ---------------------------------------------------------------------------
# Daemon manager
# ---------------------------------------------------------------------------

class CDPBrowerDaemon:
    """Manages a persistent Chrome process with CDP port."""

    def __init__(
        self,
        port: int = CDP_PORT,
        headless: bool = False,
        data_dir: Optional[Path] = None,
    ):
        self.port = port
        self.headless = headless
        self.data_dir = data_dir or Path.home() / ".config/blackreach-chrome"
        self._proc: Optional[subprocess.Popen] = None
        self._ws_url: Optional[str] = None
        self._owned = False

        if _port_open(port) and _cdp_responding():
            self._ws_url = _resolve_ws()

    @property
    def ws_url(self) -> str:
        if self._ws_url is None:
            self.start()
            self._ws_url = _resolve_ws()
        return self._ws_url

    @property
    def ready(self) -> bool:
        return _port_open(self.port) and _cdp_responding(timeout=1.0)

    def start(self) -> None:
        if self.ready:
            self._ws_url = _resolve_ws()
            return

        chrome = _find_chromium()
        self.data_dir.mkdir(parents=True, exist_ok=True)

        args = [
            chrome,
            f"--remote-debugging-port={self.port}",
            f"--user-data-dir={self.data_dir}",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-background-timer-throttling",
            "--disable-backgrounding-occluded-windows",
            "--disable-renderer-backgrounding",
            "--disable-background-networking",
            "--disable-breakpad",
            "--disable-default-apps",
            "--disable-sync",
            "--metrics-recording-only",
            "--enable-automation",
            "--password-store=basic",
            "--use-mock-keychain",
            "--force-color-profile=srgb",
        ]
        if self.headless:
            args.append("--headless=new")

        env = os.environ.copy()
        env.pop("LD_PRELOAD", None)

        self._proc = subprocess.Popen(
            args,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
            env=env,
        )
        self._owned = True

        if not _cdp_responding(timeout=30):
            self._proc.kill()
            raise RuntimeError(
                f"Chrome did not expose CDP on port {self.port} within 30s."
            )
        self._ws_url = _resolve_ws()
        atexit.register(self.stop)

    def stop(self) -> None:
        if not self._owned or self._proc is None:
            return
        try:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._proc.kill()
                self._proc.wait(timeout=3)
        except Exception:
            pass
        finally:
            self._proc = None
            self._owned = False
            self._ws_url = None

    def __del__(self):
        self.stop()


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

_daemon_singleton: Optional[CDPBrowerDaemon] = None


def ensure_daemon(
    port: int = CDP_PORT,
    headless: bool = False,
    data_dir: Optional[Path] = None,
) -> str:
    """Ensure CDP Chrome is running, return its websocket URL."""
    global _daemon_singleton
    if _daemon_singleton is None:
        _daemon_singleton = CDPBrowerDaemon(port=port, headless=headless, data_dir=data_dir)
    return _daemon_singleton.ws_url


def stop_daemon(port: int = CDP_PORT) -> bool:
    """Best-effort stop of Chrome on the given port."""
    lsof = shutil.which("lsof")
    if not lsof:
        return False
    try:
        out = subprocess.check_output(
            [lsof, "-ti", f":{port}"],
            text=True,
            stderr=subprocess.DEVNULL,
        )
        pids = [int(p.strip()) for p in out.strip().split("\n") if p.strip()]
        for pid in pids:
            try:
                os.kill(pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
        time.sleep(0.5)
        for pid in pids:
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        return True
    except subprocess.CalledProcessError:
        return False


def daemon_status() -> dict:
    """Check if a CDP Chrome is running and return info."""
    if _port_open(CDP_PORT):
        try:
            ws = _resolve_ws()
            return {"running": True, "port": CDP_PORT, "ws_url": ws}
        except Exception as e:
            return {"running": False, "port": CDP_PORT, "error": str(e)}
    return {"running": False, "port": CDP_PORT}
