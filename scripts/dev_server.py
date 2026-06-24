from __future__ import annotations

import argparse
import socket
import subprocess
import sys
import time
import webbrowser
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RPFM_SERVER = ROOT / "work" / "rpfm-master" / "target" / "debug" / "rpfm_server"


def main() -> int:
    parser = argparse.ArgumentParser(description="Start the MTU editor web UI and RPFM server together.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--web-port", default=8765, type=int)
    parser.add_argument("--rpfm-port", default=45127, type=int)
    parser.add_argument("--rpfm-server", default=DEFAULT_RPFM_SERVER, type=Path)
    parser.add_argument("--no-rpfm", action="store_true", help="Start only the web UI.")
    parser.add_argument("--open-browser", action="store_true", help="Open the web UI in the default browser.")
    args = parser.parse_args()

    processes: list[subprocess.Popen[bytes]] = []
    try:
        if args.no_rpfm:
            print("RPFM server skipped.")
        elif port_open(args.host, args.rpfm_port):
            print(f"RPFM server already running on {args.host}:{args.rpfm_port}.")
        else:
            processes.append(start_rpfm(args.rpfm_server, args.host, args.rpfm_port))

        if port_open(args.host, args.web_port):
            print(f"Web UI already running at http://{args.host}:{args.web_port}.")
        else:
            processes.append(start_web(args.host, args.web_port))

        wait_for_port(args.host, args.web_port, "Web UI")
        if not args.no_rpfm:
            wait_for_port(args.host, args.rpfm_port, "RPFM server")

        print()
        url = f"http://{args.host}:{args.web_port}"
        print(f"MTU editor ready: {url}")
        if args.open_browser:
            webbrowser.open(url)
        print("Press Ctrl+C to stop servers started by this launcher.")

        while processes:
            for process in list(processes):
                code = process.poll()
                if code is not None:
                    processes.remove(process)
                    print(f"Child process exited with code {code}.")
                    if code != 0:
                        return code
            time.sleep(0.5)
        return 0
    except KeyboardInterrupt:
        print("\nStopping servers...")
        return 0
    finally:
        for process in processes:
            terminate(process)


def start_rpfm(binary: Path, host: str, port: int) -> subprocess.Popen[bytes]:
    if not binary.is_file():
        raise SystemExit(
            f"RPFM server binary not found: {binary}\n"
            "Build it first from work/rpfm-master, or pass --rpfm-server."
        )
    print(f"Starting RPFM server: {binary}")
    env = None
    return subprocess.Popen([str(binary)], cwd=binary.parent.parent.parent, env=env)


def start_web(host: str, port: int) -> subprocess.Popen[bytes]:
    print(f"Starting web UI: http://{host}:{port}")
    return subprocess.Popen(
        [
            sys.executable,
            "-m",
            "tk_pack_builder.web",
            "--host",
            host,
            "--port",
            str(port),
        ],
        cwd=ROOT,
    )


def port_open(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=0.4):
            return True
    except OSError:
        return False


def wait_for_port(host: str, port: int, label: str) -> None:
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        if port_open(host, port):
            return
        time.sleep(0.25)
    raise SystemExit(f"{label} did not become ready on {host}:{port}.")


def terminate(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


if __name__ == "__main__":
    raise SystemExit(main())
