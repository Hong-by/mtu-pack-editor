from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


INTERNAL_MATERIAL_CACHE_VERSION = 26


def _fingerprint(path: Path) -> dict[str, Any]:
    resolved = path.resolve()
    stat = resolved.stat()
    return {
        "path": str(resolved),
        "mtimeNs": stat.st_mtime_ns,
        "sizeBytes": stat.st_size,
    }


def _local_asset_token(app_dir: Path) -> str:
    root = app_dir / "work" / "assets" / "hby_generated_character_sets"
    count = 0
    latest_mtime_ns = 0
    total_size = 0
    if root.is_dir():
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            stat = path.stat()
            count += 1
            latest_mtime_ns = max(latest_mtime_ns, stat.st_mtime_ns)
            total_size += stat.st_size
    return f"hby-assets:{count}:{latest_mtime_ns}:{total_size}"


def _runtime_internal_token(app_dir: Path) -> dict[str, Any]:
    paths = [
        app_dir / "work" / "internal_materials" / "materials.v015.json",
        app_dir / "work" / "internal_materials" / "asset_manifest.v015.json",
        app_dir / "_internal" / "tk_pack_builder" / "data" / "assembly_kit_title_effects.ko.json",
        app_dir / "_internal" / "tk_pack_builder" / "data" / "assembly_kit_skill_effects.ko.json",
    ]
    return {
        "version": INTERNAL_MATERIAL_CACHE_VERSION,
        "localAssets": _local_asset_token(app_dir),
        "sources": {
            str(path.resolve()): _fingerprint(path)
            for path in paths
            if path.is_file()
        },
    }


def _rewrite_json(path: Path, payload: dict[str, Any]) -> None:
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    temporary.replace(path)


def stamp_runtime_cache(app_dir: Path) -> None:
    app_dir = app_dir.resolve()
    internal_token = _runtime_internal_token(app_dir)

    summary_path = app_dir / "work" / "internal_materials" / "materials.v015.summary.json"
    if summary_path.is_file():
        summary_payload = json.loads(summary_path.read_text(encoding="utf-8-sig"))
        summary_payload["cache"] = internal_token
        _rewrite_json(summary_path, summary_payload)

    snapshot_path = app_dir / "work" / "reference_snapshot.json"
    if snapshot_path.is_file():
        snapshot_payload = json.loads(snapshot_path.read_text(encoding="utf-8-sig"))
        snapshot_payload["assetCacheToken"] = internal_token["localAssets"]
        snapshot_payload["internalMaterialToken"] = internal_token
        _rewrite_json(snapshot_path, snapshot_payload)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--app-dir", type=Path, required=True)
    args = parser.parse_args()
    stamp_runtime_cache(args.app_dir)


if __name__ == "__main__":
    main()
