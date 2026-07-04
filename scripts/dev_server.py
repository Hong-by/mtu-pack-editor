from __future__ import annotations

import argparse
import os
import socket
import subprocess
import sys
import webbrowser
from pathlib import Path
import time


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RPFM_SERVER = (
    ROOT / "work" / "rpfm-dist" / "rpfm_server.exe"
    if os.name == "nt"
    else ROOT / "work" / "rpfm-master" / "target" / "debug" / "rpfm_server"
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Start the MTU editor web UI and RPFM server together.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--web-port", default=8765, type=int)
    parser.add_argument("--rpfm-port", default=45127, type=int)
    parser.add_argument("--rpfm-server", default=DEFAULT_RPFM_SERVER, type=Path)
    parser.add_argument("--no-rpfm", action="store_true", help="Start only the web UI.")
    parser.add_argument(
        "--external-rpfm",
        action="store_true",
        help="Use an already-running RPFM server on the configured port and never start one.",
    )
    parser.add_argument("--open-browser", action="store_true", help="Open the web UI in the default browser.")
    args = parser.parse_args()

    processes: list[subprocess.Popen[bytes]] = []
    rpfm_process: subprocess.Popen[bytes] | None = None
    try:
        if args.external_rpfm:
            os.environ["MTU_RPFM_EXTERNAL_ONLY"] = "1"
            if port_open(args.host, args.rpfm_port):
                print(f"Using external RPFM server on {args.host}:{args.rpfm_port}.")
            else:
                print(f"External RPFM server not running on {args.host}:{args.rpfm_port}.")
        elif args.no_rpfm:
            print("RPFM server skipped.")
        elif port_open(args.host, args.rpfm_port):
            print(f"RPFM server already running on {args.host}:{args.rpfm_port}.")
        else:
            stop_stale_rpfm_processes(args.rpfm_server.name)
            rpfm_process = start_rpfm(args.rpfm_server, args.host, args.rpfm_port)
            processes.append(rpfm_process)

        if port_open(args.host, args.web_port):
            print(f"Web UI already running at http://{args.host}:{args.web_port}.")
        else:
            processes.append(start_web(args.host, args.web_port))

        wait_for_port(args.host, args.web_port, "Web UI")
        if not args.no_rpfm and not args.external_rpfm:
            if wait_for_port(args.host, args.rpfm_port, "RPFM server", raise_on_timeout=False):
                print(f"RPFM server ready on {args.host}:{args.rpfm_port}.")
            else:
                print(f"RPFM server is not running on {args.host}:{args.rpfm_port}. Pack generation will fail until it is started.")
                if rpfm_process is not None and rpfm_process.poll() is not None and rpfm_process in processes:
                    processes.remove(rpfm_process)

        print()
        url = f"http://{args.host}:{args.web_port}"
        print(f"MTU editor ready: {url}")
        if args.open_browser:
            webbrowser.open(url)
        print("Press Ctrl+C to stop servers started by this launcher.")

        if not processes:
            while True:
                time.sleep(0.5)

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
    redirect_root = ROOT / "work" / "rpfm-runtime-config"
    redirect_root.mkdir(parents=True, exist_ok=True)
    redirect_path = redirect_root / f"config-{int(time.time() * 1000)}"
    (binary.parent / "config_folder.txt").write_text(str(redirect_path), encoding="utf-8")
    print(f"Starting RPFM server: {binary}")
    return subprocess.Popen([str(binary)], cwd=binary.parent)


def stop_stale_rpfm_processes(process_name: str) -> None:
    if os.name != "nt":
        return
    subprocess.run(
        ["taskkill", "/F", "/IM", process_name],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    time.sleep(0.5)


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


def wait_for_port(host: str, port: int, label: str, raise_on_timeout: bool = True) -> bool:
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        if port_open(host, port):
            return True
        time.sleep(0.25)
    if raise_on_timeout:
        raise SystemExit(f"{label} did not become ready on {host}:{port}.")
    return False


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
