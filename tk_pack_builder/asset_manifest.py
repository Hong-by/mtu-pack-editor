from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".dds"}
SHARED_IMAGE_TOKENS = {"generic", "shared", "common", "scripted"}


@dataclass(frozen=True)
class AssetFile:
    source_id: str
    packed_path: str
    file_path: Path
    size_bytes: int
    sha1: str


def build_asset_manifest(
    materials_path: Path,
    asset_root: Path,
    pack_roots: list[Path],
) -> dict[str, Any]:
    materials = _read_json(materials_path)
    asset_files = inventory_asset_files(asset_root)
    assets_by_path: dict[str, list[AssetFile]] = {}
    for asset in asset_files:
        assets_by_path.setdefault(asset.packed_path.lower(), []).append(asset)

    source_map = source_id_map(pack_roots)
    templates = _table_rows(materials, "character_generation_templates")
    art_rows = _table_rows(materials, "campaign_character_arts")
    art_by_set: dict[str, list[dict[str, Any]]] = {}
    for row in art_rows:
        art_set_id = str(row.get("art_set_id") or "")
        if art_set_id:
            art_by_set.setdefault(art_set_id, []).append(row)

    unique_characters: dict[str, Any] = {}
    shared_or_generic_assets: dict[str, Any] = {}
    reachable_paths: set[str] = set()
    missing_sets: list[dict[str, str]] = []

    for template in templates:
        if template.get("unique") is not True:
            continue
        character_key = str(template.get("key") or "")
        art_set_id = str(template.get("art_set_override") or "")
        rows = _adult_art_rows(art_by_set.get(art_set_id, []))
        character_paths: set[str] = set()
        image_roots: set[str] = set()
        image_refs: list[dict[str, str]] = []
        for row in rows:
            for field, kind in (("portrait", "halfbody_large"), ("card", "unitcards")):
                image_key = str(row.get(field) or "").strip("/")
                if not image_key:
                    continue
                found = find_character_image_path(assets_by_path, image_key, kind)
                image_refs.append({"field": field, "key": image_key, "kind": kind, "foundPath": found or ""})
                if not found:
                    continue
                root = character_asset_root(found)
                if not root:
                    continue
                image_roots.add(root)
                for asset in assets_under_character_root(assets_by_path, root):
                    if is_shared_or_generic_path(asset.packed_path):
                        shared_or_generic_assets.setdefault(asset.packed_path, asset_entry(asset, source_map))
                        continue
                    character_paths.add(asset.packed_path)
                    reachable_paths.add(asset.packed_path)
        if not character_paths:
            missing_sets.append({
                "characterKey": character_key,
                "artSetId": art_set_id,
            })
        unique_characters[character_key] = {
            "characterKey": character_key,
            "artSetId": art_set_id,
            "imageRoots": sorted(image_roots),
            "imageRefs": image_refs,
            "assetCount": len(character_paths),
            "assets": {
                path: asset_entry(assets_by_path[path.lower()][0], source_map)
                for path in sorted(character_paths)
            },
        }

    owned_external_assets: dict[str, Any] = {}
    orphan_cached_assets: dict[str, Any] = {}
    for asset in asset_files:
        if asset.packed_path in reachable_paths or asset.packed_path in shared_or_generic_assets:
            continue
        entry = asset_entry(asset, source_map)
        bucket = owned_external_assets if is_owned_external_path(asset.packed_path) else orphan_cached_assets
        bucket.setdefault(asset.packed_path, entry)

    return {
        "schemaVersion": 1,
        "baseline": materials.get("baseline", "v0.1.5"),
        "createdAt": time.time(),
        "materialsPath": str(materials_path),
        "assetRoot": str(asset_root),
        "summary": {
            "inventoriedAssetCount": len(asset_files),
            "uniqueCharacterCount": len(unique_characters),
            "uniqueCharacterAssetCount": sum(item["assetCount"] for item in unique_characters.values()),
            "sharedOrGenericAssetCount": len(shared_or_generic_assets),
            "ownedExternalAssetCount": len(owned_external_assets),
            "orphanCachedAssetCount": len(orphan_cached_assets),
            "missingUniqueImageSetCount": len(missing_sets),
        },
        "sources": {
            source_id: str(path)
            for source_id, path in sorted(source_map.items())
        },
        "uniqueCharacterAssets": unique_characters,
        "sharedOrGenericAssets": shared_or_generic_assets,
        "ownedExternalAssets": owned_external_assets,
        "orphanCachedAssets": orphan_cached_assets,
        "missingUniqueImageSets": missing_sets,
    }


def inventory_asset_files(asset_root: Path) -> list[AssetFile]:
    if not asset_root.is_dir():
        return []
    assets: list[AssetFile] = []
    for source_dir in sorted(path for path in asset_root.iterdir() if path.is_dir()):
        source_id = source_dir.name
        for file_path in sorted(source_dir.rglob("*")):
            if not file_path.is_file() or file_path.suffix.lower() not in IMAGE_EXTENSIONS:
                continue
            packed_path = _normalize_path(file_path.relative_to(source_dir).as_posix())
            assets.append(AssetFile(
                source_id=source_id,
                packed_path=packed_path,
                file_path=file_path,
                size_bytes=file_path.stat().st_size,
                sha1=_file_sha1(file_path),
            ))
    return assets


def source_id_map(pack_roots: list[Path]) -> dict[str, Path]:
    mapping: dict[str, Path] = {}
    for root in pack_roots:
        if root.is_file() and root.suffix.lower() == ".pack":
            paths = [root]
        elif root.is_dir():
            paths = sorted(root.glob("*.pack"))
        else:
            paths = []
        for path in paths:
            source_id = hashlib.sha1(str(path.resolve()).encode("utf-8", errors="ignore")).hexdigest()[:12]
            mapping[source_id] = path.resolve()
    return mapping


def find_character_image_path(
    assets_by_path: dict[str, list[AssetFile]],
    image_key: str,
    image_kind: str,
) -> str | None:
    normalized = image_key.strip("/")
    image_name = normalized.rsplit("/", 1)[-1]
    preferred = [
        f"ui/characters/{normalized}/stills/{image_kind}/{normalized}.png",
        f"ui/characters/{normalized}/stills/{image_kind}/large/{normalized}.png",
        f"ui/characters/{normalized}/stills/{image_kind}/{image_name}.png",
        f"ui/characters/{normalized}/stills/{image_kind}/large/{image_name}.png",
        f"ui/characters/{normalized}/composites/large_panel/norm/noanim.png",
        f"ui/characters/{normalized}/composites/large_panel/norm/norm.png",
        f"ui/characters/{normalized}/composites/large_panel/happy/noanim.png",
        f"ui/characters/{normalized}/composites/large_panel/happy/happy.png",
    ]
    for path in preferred:
        if path.lower() in assets_by_path:
            return assets_by_path[path.lower()][0].packed_path

    suffix = f"/stills/{image_kind.lower()}/{image_name.lower()}.png"
    large_suffix = f"/stills/{image_kind.lower()}/large/{image_name.lower()}.png"
    for key in sorted(assets_by_path):
        if key.endswith(suffix) or key.endswith(large_suffix):
            return assets_by_path[key][0].packed_path
    return None


def character_asset_root(packed_path: str) -> str | None:
    normalized = _normalize_path(packed_path)
    lower = normalized.lower()
    for marker in ("/composites/", "/stills/"):
        if marker in lower and lower.startswith("ui/characters/"):
            return normalized[: lower.index(marker)]
    return None


def assets_under_character_root(
    assets_by_path: dict[str, list[AssetFile]],
    root: str,
) -> list[AssetFile]:
    prefix = f"{root.rstrip('/').lower()}/"
    results: list[AssetFile] = []
    for lower_path, candidates in assets_by_path.items():
        if not lower_path.startswith(prefix):
            continue
        if "/composites/" not in lower_path and "/stills/" not in lower_path:
            continue
        results.extend(candidates)
    return sorted(results, key=lambda asset: (asset.packed_path, asset.source_id))


def is_shared_or_generic_path(path: str) -> bool:
    parts = _path_tokens(path)
    return bool(SHARED_IMAGE_TOKENS.intersection(parts))


def is_owned_external_path(path: str) -> bool:
    lower = path.lower()
    return any(token in lower for token in ("aw_", "lshz_", "bfg_"))


def asset_entry(asset: AssetFile, source_map: dict[str, Path]) -> dict[str, Any]:
    return {
        "sourceId": asset.source_id,
        "sourcePath": str(source_map.get(asset.source_id, "")),
        "packedPath": asset.packed_path,
        "extractedPath": str(asset.file_path),
        "sizeBytes": asset.size_bytes,
        "sha1": asset.sha1,
    }


def _adult_art_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    adult_rows = [row for row in rows if row.get("has_come_of_age") is True]
    return adult_rows or rows[:1]


def _table_rows(materials: dict[str, Any], alias: str) -> list[dict[str, Any]]:
    suffix = f"/{alias}_tables/"
    matches = [
        entry.get("rows", [])
        for path, entry in materials.get("tables", {}).items()
        if suffix in path and isinstance(entry, dict)
    ]
    if not matches:
        return []
    return [dict(row) for row in matches[0] if isinstance(row, dict)]


def _read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _file_sha1(path: Path) -> str:
    digest = hashlib.sha1()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _path_tokens(path: str) -> set[str]:
    normalized = _normalize_path(path).lower()
    tokens: set[str] = set()
    for part in normalized.split("/"):
        tokens.update(token for token in part.replace("-", "_").split("_") if token)
    return tokens


def _normalize_path(path: str) -> str:
    return path.replace("\\", "/").strip("/").lower()
