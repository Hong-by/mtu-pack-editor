from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tk_pack_builder.web import (  # noqa: E402
    ROOT,
    _extracted_asset_path,
    _fallback_pack_path,
    _find_extracted_asset,
    _real_packed_asset_path,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Audit image-set candidates against extracted work/assets cache."
    )
    parser.add_argument("--snapshot", type=Path, default=ROOT / "work" / "reference_snapshot.json")
    parser.add_argument("--internal-db-dir", type=Path, default=ROOT / "work" / "internal_dbs")
    parser.add_argument("--output", type=Path, default=ROOT / "work" / "image_set_audit.json")
    args = parser.parse_args()

    candidates = list(_iter_candidates(args.snapshot, args.internal_db_dir))
    rows = [_audit_candidate(candidate) for candidate in candidates]

    incomplete_required = [
        row for row in rows
        if row["missingRequired"]
    ]
    incomplete_assets = [
        row for row in rows
        if row["missingAssets"]
    ]
    by_source: dict[str, dict[str, int]] = {}
    for row in rows:
        source = row["sourcePath"] or "(internal/no-source)"
        item = by_source.setdefault(source, {"total": 0, "missingRequired": 0, "missingAssets": 0})
        item["total"] += 1
        if row["missingRequired"]:
            item["missingRequired"] += 1
        if row["missingAssets"]:
            item["missingAssets"] += 1

    payload = {
        "counts": {
            "candidates": len(rows),
            "missingRequired": len(incomplete_required),
            "missingAssets": len(incomplete_assets),
        },
        "bySource": by_source,
        "missingRequired": incomplete_required,
        "missingAssets": incomplete_assets,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(payload["counts"], ensure_ascii=False, indent=2))
    print("Top sources with missing required:")
    for source, stats in sorted(
        by_source.items(),
        key=lambda item: item[1]["missingRequired"],
        reverse=True,
    )[:12]:
        if stats["missingRequired"]:
            print(f"  {stats['missingRequired']:4d}/{stats['total']:4d} {source}")
    print(f"Wrote {args.output}")
    return 0


def _iter_candidates(snapshot_path: Path, internal_db_dir: Path):
    if snapshot_path.is_file():
        payload = json.loads(snapshot_path.read_text(encoding="utf-8"))
        pack = payload.get("characters", {}).get("pack", {})
        yield from _rows_from_summary(pack, str(snapshot_path), None)
    if internal_db_dir.is_dir():
        for db_path in sorted(internal_db_dir.glob("*.json")):
            payload = json.loads(db_path.read_text(encoding="utf-8"))
            summary = payload.get("summary")
            if not isinstance(summary, dict):
                continue
            yield from _rows_from_summary(summary, str(db_path), payload.get("sourcePack"))


def _rows_from_summary(summary: dict[str, Any], source_label: str, default_source: Any):
    for group in ("characters", "artSets"):
        rows = summary.get(group)
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, dict):
                continue
            if not (row.get("portraitImagePath") or row.get("cardImagePath") or row.get("imageAssets")):
                continue
            yield {
                "sourceLabel": source_label,
                "group": group,
                "key": row.get("key") or row.get("artSet") or row.get("label"),
                "label": row.get("displayName") or row.get("label") or row.get("key"),
                "portraitImagePath": row.get("portraitImagePath") or "",
                "portraitSourcePath": row.get("portraitImageSourcePath") or "",
                "cardImagePath": row.get("cardImagePath") or "",
                "cardSourcePath": row.get("cardImageSourcePath") or "",
                "imageAssets": row.get("imageAssets") or [],
                "defaultSource": default_source or "",
            }


def _audit_candidate(candidate: dict[str, Any]) -> dict[str, Any]:
    source_path = (
        candidate.get("portraitSourcePath")
        or candidate.get("cardSourcePath")
        or candidate.get("defaultSource")
        or ""
    )
    missing_required = []
    for field, source_field in (
        ("portraitImagePath", "portraitSourcePath"),
        ("cardImagePath", "cardSourcePath"),
    ):
        path = str(candidate.get(field) or "")
        if not path:
            missing_required.append({"field": field, "path": "", "reason": "empty"})
            continue
        item_source = str(candidate.get(source_field) or source_path)
        if not _asset_cached(item_source, path):
            missing_required.append({"field": field, "path": path, "sourcePath": item_source})

    missing_assets = []
    for asset in candidate.get("imageAssets") or []:
        if not isinstance(asset, dict):
            continue
        path = str(asset.get("path") or "")
        if not path:
            continue
        item_source = str(asset.get("sourcePath") or source_path)
        if not item_source:
            continue
        if not _asset_cached(item_source, path):
            missing_assets.append({"path": path, "sourcePath": item_source})

    return {
        "sourceLabel": candidate["sourceLabel"],
        "group": candidate["group"],
        "key": candidate["key"],
        "label": candidate["label"],
        "sourcePath": source_path,
        "portraitImagePath": candidate["portraitImagePath"],
        "cardImagePath": candidate["cardImagePath"],
        "missingRequired": missing_required,
        "missingAssets": missing_assets,
    }


def _asset_cached(source_path: str, packed_path: str) -> bool:
    real_path = _real_packed_asset_path(packed_path)
    if source_path:
        source = Path(source_path)
        candidates = [source]
        fallback = _fallback_pack_path(source)
        if fallback is not None and fallback != source:
            candidates.append(fallback)
        for candidate in candidates:
            if _extracted_asset_path(candidate, packed_path).is_file():
                return True
            if real_path != packed_path and _extracted_asset_path(candidate, real_path).is_file():
                return True
        return False
    return bool(_find_extracted_asset(packed_path) or _find_extracted_asset(real_path))


if __name__ == "__main__":
    raise SystemExit(main())
