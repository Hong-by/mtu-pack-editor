from __future__ import annotations

import os
import shutil
import socket
import subprocess
import time
from pathlib import Path
from typing import Any

from .rpfm_runtime import (
    prepare_rpfm_config_redirect,
    resolve_rpfm_server,
    rpfm_process_environment,
)


ROOT = Path(os.environ.get("TK_PACK_EDITOR_ROOT", Path(__file__).resolve().parents[1])).resolve()
RPFM_SERVER_CANDIDATES = [
    ROOT / "work" / "rpfm-dist" / "rpfm_server.exe",
    Path("E:/rpfm-v5.0.3-x86_64-pc-windows-msvc/rpfm_server.exe"),
] if os.name == "nt" else [
    ROOT / "work" / "rpfm-master" / "target" / "debug" / "rpfm_server",
]
DEFAULT_RPFM_SERVER = next((path for path in RPFM_SERVER_CANDIDATES if path.is_file()), RPFM_SERVER_CANDIDATES[0])
RPFM_PROCESS: subprocess.Popen[bytes] | None = None
RPFM_LOG_HANDLE: Any | None = None
RPFM_LOG_MAX_BYTES = 16 * 1024 * 1024

def _ensure_rpfm_server() -> None:
    global RPFM_PROCESS, RPFM_LOG_HANDLE
    if _port_open("127.0.0.1", 45127):
        return
    if os.environ.get("MTU_RPFM_EXTERNAL_ONLY") == "1":
        raise ValueError("RPFM server is not running on 127.0.0.1:45127.")
    if RPFM_PROCESS is not None and RPFM_PROCESS.poll() is None:
        _wait_for_port("127.0.0.1", 45127)
        return
    rpfm_server = resolve_rpfm_server(ROOT, DEFAULT_RPFM_SERVER)
    if not rpfm_server.is_file():
        raise ValueError(f"RPFM server binary not found: {rpfm_server}")
    _stop_stale_rpfm_processes(rpfm_server.name)
    # This bundled RPFM build requires a fresh, non-existing redirected config
    # directory on every launch. Reusing its previous target causes WinError
    # 183; omitting the redirect makes it collide with its default path.
    prepare_rpfm_config_redirect(ROOT, rpfm_server.parent)
    log_path = ROOT / "work" / "rpfm-server.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    if RPFM_LOG_HANDLE is not None and not RPFM_LOG_HANDLE.closed:
        RPFM_LOG_HANDLE.close()
    try:
        if log_path.is_file() and log_path.stat().st_size > RPFM_LOG_MAX_BYTES:
            log_path.unlink()
    except OSError:
        # Log cleanup must never prevent pack creation. The warning-only
        # logging level still stops the file from growing further.
        pass
    RPFM_LOG_HANDLE = log_path.open("ab")
    creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    RPFM_PROCESS = subprocess.Popen(
        [str(rpfm_server)],
        cwd=rpfm_server.parent,
        env=_rpfm_env(),
        stdout=RPFM_LOG_HANDLE,
        stderr=RPFM_LOG_HANDLE,
        creationflags=creationflags,
    )
    _wait_for_port("127.0.0.1", 45127)


def _stop_stale_rpfm_processes(process_name: str) -> None:
    if os.name != "nt":
        return
    subprocess.run(
        ["taskkill", "/F", "/IM", process_name],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    time.sleep(0.5)


def _rotate_rpfm_config_dir() -> None:
    if os.name != "nt":
        return
    local_roots = [
        Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")),
        Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming")),
        Path.home() / "AppData" / "Local",
        Path.home() / "AppData" / "Roaming",
        _rpfm_local_appdata_root(),
        ROOT / "work" / "rpfm-local-appdata" / "config",
    ]
    for local_appdata in local_roots:
        config_dir = local_appdata / "FrodoWazEre" / "rpfm" / "config"
        if not config_dir.exists():
            continue
        backup = config_dir.with_name(f"config.mtu-backup-{int(time.time())}")
        try:
            config_dir.rename(backup)
        except OSError:
            shutil.rmtree(config_dir, ignore_errors=True)


def _rpfm_local_appdata_root() -> Path:
    return ROOT / "work" / "rpfm-local-appdata"


def _rpfm_env() -> dict[str, str]:
    blocked_prefixes = ("PYINSTALLER_", "PYI_", "PYTHON")
    blocked_keys = {"TK_PACK_EDITOR_ROOT", "_MEIPASS"}
    env = {}
    for key, value in os.environ.items():
        upper = key.upper()
        if upper in blocked_keys or any(upper.startswith(prefix) for prefix in blocked_prefixes):
            continue
        if upper == "PATH" and any(existing.upper() == "PATH" for existing in env):
            continue
        env[key] = value
    runtime_env = rpfm_process_environment(ROOT, env)
    # The server's INFO trace serialises every decoded/saved DB command.  A
    # large multi-character build can otherwise write hundreds of megabytes
    # of duplicate diagnostic text while the same payload crosses WebSocket.
    runtime_env["RUST_LOG"] = os.environ.get("TK_RPFM_LOG_LEVEL", "warn")
    return runtime_env


def _port_open(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=0.4):
            return True
    except OSError:
        return False


def _wait_for_port(host: str, port: int) -> None:
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        if _port_open(host, port):
            return
        time.sleep(0.2)
    raise ValueError(f"RPFM server did not become ready on {host}:{port}.")


def _close_session(session: Any) -> None:
    close = getattr(session, "close", None)
    if callable(close):
        close()
