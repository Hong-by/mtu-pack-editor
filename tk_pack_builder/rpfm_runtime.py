from __future__ import annotations

import os
import shutil
import hashlib
from pathlib import Path


def bundled_rpfm_dir(root: Path) -> Path:
    return root / "work" / "rpfm-dist"


def runtime_rpfm_dir(root: Path | None = None) -> Path:
    if os.name == "nt" and root is not None:
        drive_runtime = Path(root.anchor) / "MTU_RPFM_Runtime"
        try:
            drive_runtime.mkdir(parents=True, exist_ok=True)
            return drive_runtime
        except OSError:
            pass
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        return base / "MTUPackEditor" / "rpfm-runtime"
    return Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "mtu-pack-editor" / "rpfm-runtime"


def resolve_rpfm_server(root: Path, fallback: Path | None = None) -> Path:
    bundled = bundled_rpfm_dir(root)
    source = bundled if (bundled / _server_name()).is_file() else None
    if source is None and fallback is not None and fallback.is_file():
        source = fallback.parent
    if source is None:
        return bundled / _server_name()
    return prepare_rpfm_runtime(source, root) / _server_name()


def prepare_rpfm_runtime(source_dir: Path, root: Path | None = None) -> Path:
    target_dir = runtime_rpfm_dir(root)
    source_exe = source_dir / _server_name()
    target_exe = target_dir / _server_name()
    marker = target_dir / ".source-stamp"
    stamp = _source_stamp(source_exe)
    if target_exe.is_file() and marker.is_file() and marker.read_text(encoding="utf-8", errors="ignore") == stamp:
        return target_dir
    if target_exe.is_file() and _source_stamp(target_exe) == stamp:
        marker.write_text(stamp, encoding="utf-8")
        return target_dir

    target_dir.parent.mkdir(parents=True, exist_ok=True)
    if target_dir.exists():
        try:
            shutil.rmtree(target_dir)
        except PermissionError:
            if target_exe.is_file():
                marker.write_text(_source_stamp(target_exe), encoding="utf-8")
                return target_dir
            raise
    ignore = shutil.ignore_patterns("*.pdb")
    shutil.copytree(source_dir, target_dir, ignore=ignore)
    marker.write_text(stamp, encoding="utf-8")
    return target_dir


def _server_name() -> str:
    return "rpfm_server.exe" if os.name == "nt" else "rpfm_server"


def _source_stamp(path: Path) -> str:
    stat = path.stat()
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return f"{stat.st_size}|{digest.hexdigest()}"
