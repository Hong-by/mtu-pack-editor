from __future__ import annotations

import os
import shutil
import hashlib
from pathlib import Path


def bundled_rpfm_dir(root: Path) -> Path:
    return root / "work" / "rpfm-dist"


def runtime_rpfm_dir(root: Path | None = None) -> Path:
    if root is not None:
        return Path(root) / "work" / "rpfm-runtime"
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        return base / "MTUPackEditor" / "rpfm-runtime"
    return Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "mtu-pack-editor" / "rpfm-runtime"


def rpfm_process_environment(
    root: Path,
    environ: dict[str, str] | None = None,
) -> dict[str, str]:
    env = dict(os.environ if environ is None else environ)
    config_root = Path(root) / "work" / "rpfm-local-appdata"
    config_root.mkdir(parents=True, exist_ok=True)
    if os.name == "nt":
        env["APPDATA"] = str(config_root)
        env["LOCALAPPDATA"] = str(config_root)
    else:
        env["XDG_CONFIG_HOME"] = str(config_root)
    return env


def ensure_rpfm_config_redirect(
    root: Path,
    environ: dict[str, str] | None = None,
) -> Path:
    # Clear redirects left by older editor builds only from the application-
    # owned work directory. RPFM resolves its official config directory using
    # Windows Known Folders, so never assume these environment hints relocate
    # or authorize the user's standalone RPFM config.
    env = rpfm_process_environment(root, environ)
    # Older bundled launches could materialize Windows' Local/Roaming split
    # below our isolated root and leave redirects in all four of these forms:
    #
    #   Local/FrodoWazEre/rpfm/config_folder.txt
    #   Local/FrodoWazEre/rpfm/config/config_folder.txt
    #   Roaming/FrodoWazEre/rpfm/config_folder.txt
    #   Roaming/FrodoWazEre/rpfm/config/config_folder.txt
    #
    # RPFM may discover any one of them before consulting the environment we
    # pass to the child process. Clear every stale redirect, but only below
    # the application-owned work directory so user RPFM settings are never
    # touched.
    isolated_root = Path(root) / "work" / "rpfm-local-appdata"
    if isolated_root.is_dir():
        for stale_redirect in isolated_root.rglob("config_folder.txt"):
            if stale_redirect.is_file():
                stale_redirect.unlink()
        stale_config_dirs = sorted(
            (
                path
                for path in isolated_root.rglob("config")
                if path.is_dir()
            ),
            key=lambda path: len(path.parts),
            reverse=True,
        )
        for stale_config_dir in stale_config_dirs:
            if not any(stale_config_dir.iterdir()):
                stale_config_dir.rmdir()

    return isolated_root


def rpfm_default_config_dir(
    environ: dict[str, str] | None = None,
) -> Path:
    env = os.environ if environ is None else environ
    if os.name == "nt":
        appdata = Path(
            env.get("APPDATA", Path.home() / "AppData" / "Roaming")
        )
        return appdata / "FrodoWazEre" / "rpfm"
    config_root = Path(
        env.get("XDG_CONFIG_HOME", Path.home() / ".config")
    )
    return config_root / "rpfm"


def prepare_rpfm_config_redirect(
    root: Path,
    executable_dir: Path | None = None,
    environ: dict[str, str] | None = None,
) -> Path:
    """Remove obsolete editor-owned RPFM config redirects before launch.

    RPFM resolves its official config directory through Windows Known Folders,
    so APPDATA overrides are not reliable. Never rewrite the user's standalone
    RPFM redirect here; only remove files inside the packaged runtime and the
    editor's own work directory.
    """
    env = rpfm_process_environment(root, environ)
    config_dir = ensure_rpfm_config_redirect(root, env)
    if executable_dir is not None:
        executable_redirect = Path(executable_dir) / "config_folder.txt"
        if executable_redirect.is_file():
            executable_redirect.unlink()
    return config_dir


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
