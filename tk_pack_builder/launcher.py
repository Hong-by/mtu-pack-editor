from __future__ import annotations

import argparse
import os
import socket
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path

from tk_pack_builder.rpfm_runtime import resolve_rpfm_server


def main() -> int:
    parser = argparse.ArgumentParser(description="Start MTU Pack Editor.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=8765, type=int)
    parser.add_argument("--rpfm-port", default=45127, type=int)
    parser.add_argument("--no-rpfm", action="store_true")
    parser.add_argument("--prestart-rpfm", action="store_true")
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()

    root = _app_root()
    os.environ["TK_PACK_EDITOR_ROOT"] = str(root)

    from tk_pack_builder.web import run_server

    rpfm_process: subprocess.Popen[bytes] | None = None
    try:
        if args.prestart_rpfm and not args.no_rpfm and not _port_open(args.host, args.rpfm_port):
            rpfm_process = _start_rpfm(root)

        if not _port_open(args.host, args.port):
            thread = threading.Thread(
                target=run_server,
                args=(args.host, args.port),
                daemon=True,
            )
            thread.start()

        _wait_for_port(args.host, args.port, "Web UI")
        url = f"http://{args.host}:{args.port}/"
        print(f"MTU Pack Editor ready: {url}")
        if not args.no_browser:
            webbrowser.open(url)

        while True:
            if rpfm_process is not None and rpfm_process.poll() not in {None, 0}:
                print(f"RPFM server exited with code {rpfm_process.returncode}.")
                rpfm_process = None
            time.sleep(0.5)
    except KeyboardInterrupt:
        return 0
    finally:
        if rpfm_process is not None and rpfm_process.poll() is None:
            rpfm_process.terminate()
    return 0


def _app_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]


def _start_rpfm(root: Path) -> subprocess.Popen[bytes] | None:
    fallback = Path("E:/rpfm-v5.0.3-x86_64-pc-windows-msvc/rpfm_server.exe")
    binary = resolve_rpfm_server(root, fallback)
    if not binary.is_file():
        print(f"RPFM server not bundled: {binary}")
        return None
    print(f"Starting RPFM server: {binary}")
    creationflags = 0
    if os.name == "nt":
        creationflags = subprocess.CREATE_NO_WINDOW
    return subprocess.Popen(
        [str(binary)],
        cwd=binary.parent,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=creationflags,
    )


def _port_open(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=0.4):
            return True
    except OSError:
        return False


def _wait_for_port(host: str, port: int, label: str) -> None:
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        if _port_open(host, port):
            return
        time.sleep(0.2)
    raise RuntimeError(f"{label} did not become ready on {host}:{port}.")


if __name__ == "__main__":
    raise SystemExit(main())
