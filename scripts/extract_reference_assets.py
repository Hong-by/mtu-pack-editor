from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tk_pack_builder.adapters import adapter_for
from tk_pack_builder.web import (
    ROOT,
    _ensure_rpfm_server,
    _extracted_asset_path,
    _fallback_pack_path,
    _real_packed_asset_path,
    _write_extracted_asset,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract referenced character images to work/assets.")
    parser.add_argument("--snapshot", type=Path, default=ROOT / "work" / "reference_snapshot.json")
    parser.add_argument("--internal-db-dir", type=Path, default=ROOT / "work" / "internal_dbs")
    args = parser.parse_args()

    grouped: dict[str, set[str]] = {}
    if args.snapshot.is_file():
        snapshot = json.loads(args.snapshot.read_text(encoding="utf-8"))
        characters = snapshot.get("characters", {}).get("pack", {}).get("characters", [])
        _collect_character_assets(grouped, characters)
    if args.internal_db_dir.is_dir():
        for db_path in sorted(args.internal_db_dir.glob("*.json")):
            payload = json.loads(db_path.read_text(encoding="utf-8"))
            summary = payload.get("summary")
            if not isinstance(summary, dict):
                continue
            default_source = payload.get("sourcePack")
            _collect_character_assets(grouped, summary.get("characters", []), default_source)
            _collect_character_assets(grouped, summary.get("artSets", []), default_source)

    total = 0
    skipped = 0
    for original_source, packed_paths in sorted(grouped.items()):
        source_path = Path(original_source)
        actual_path = source_path if source_path.is_file() else _fallback_pack_path(source_path)
        if actual_path is None:
            skipped += len(packed_paths)
            print(f"skip missing source: {source_path} ({len(packed_paths)} asset(s))")
            continue
        _ensure_rpfm_server()
        session = adapter_for("rpfm").open_pack(actual_path)
        try:
            for packed_path in sorted(packed_paths):
                real_packed_path = _real_packed_asset_path(packed_path)
                try:
                    data = session.read_file_bytes(real_packed_path)
                except Exception as error:
                    skipped += 1
                    print(f"skip missing asset: {real_packed_path} from {actual_path}: {error}")
                    continue
                _write_extracted_asset(_extracted_asset_path(source_path, packed_path), data)
                if real_packed_path != packed_path:
                    _write_extracted_asset(_extracted_asset_path(source_path, real_packed_path), data)
                if actual_path != source_path:
                    _write_extracted_asset(_extracted_asset_path(actual_path, packed_path), data)
                    if real_packed_path != packed_path:
                        _write_extracted_asset(_extracted_asset_path(actual_path, real_packed_path), data)
                total += 1
        finally:
            close = getattr(session, "close", None)
            if callable(close):
                close()
    print(f"extracted={total} skipped={skipped}")
    return 0


def _collect_character_assets(
    grouped: dict[str, set[str]],
    rows: list[dict[str, object]],
    default_source: object = None,
) -> None:
    for row in rows:
        if not isinstance(row, dict):
            continue
        row_source = (
            row.get("portraitImageSourcePath")
            or row.get("cardImageSourcePath")
            or default_source
        )
        for image_key, source_key in (
            ("portraitImagePath", "portraitImageSourcePath"),
            ("cardImagePath", "cardImageSourcePath"),
        ):
            image_path = row.get(image_key)
            source_path = row.get(source_key) or row_source
            if image_path and source_path:
                grouped.setdefault(str(source_path), set()).add(str(image_path))
        for asset in row.get("imageAssets") or []:
            if not isinstance(asset, dict):
                continue
            path = asset.get("path")
            source_path = asset.get("sourcePath") or row_source
            if path and source_path:
                grouped.setdefault(str(source_path), set()).add(str(path))


if __name__ == "__main__":
    raise SystemExit(main())
