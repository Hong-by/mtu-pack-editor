from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from html import escape
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tk_pack_builder.asset_manifest import inventory_asset_files, source_id_map  # noqa: E402


ELEMENTS = {"earth", "fire", "metal", "water", "wood"}
GENDERS = {"male", "female"}
GENERIC_TOKENS = {
    "generic",
    "shared",
    "common",
    "scripted",
    "placeholder",
    "placeholder_ui",
    "baby",
    "child",
    "children",
    "kid",
    "kids",
    "infant",
    "toddler",
    "face",
    "faces",
    "prop",
    "props",
}
ROLE_ROOTS = {
    "water_strategist",
    "water_strategist_ban",
    "nanman",
    "yellow_turban",
    "yt_healer",
    "yt_scholar",
    "yt_veteran",
    "healer",
    "scholar",
    "veteran",
    "eunuchs",
}
UNIQUE_HINTS = (
    "hero_special_",
    "_historical",
    "historical_",
    "lady_",
    "king_",
    "emperor_",
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Report likely generic/non-unique extracted character asset folders.")
    parser.add_argument("--asset-root", type=Path, default=ROOT / "work" / "assets")
    parser.add_argument(
        "--output-json",
        type=Path,
        default=ROOT / "work" / "internal_materials" / "generic_asset_candidates.v015.json",
    )
    parser.add_argument(
        "--output-html",
        type=Path,
        default=ROOT / "work" / "internal_materials" / "generic_asset_candidates.v015.html",
    )
    parser.add_argument(
        "--pack-root",
        action="append",
        type=Path,
        dest="pack_roots",
        default=None,
    )
    args = parser.parse_args()

    pack_roots = args.pack_roots or [
        ROOT / "work" / "packs",
        ROOT / "work" / "packs" / "refs",
        ROOT / "work" / "legacy_template",
    ]
    source_map = source_id_map([path.resolve() for path in pack_roots])
    assets = inventory_asset_files(args.asset_root.resolve())
    groups = group_assets(assets, source_map)
    payload = {
        "schemaVersion": 1,
        "assetRoot": str(args.asset_root.resolve()),
        "summary": {
            "candidateGroupCount": len(groups),
            "candidateAssetCount": sum(group["assetCount"] for group in groups),
            "reasons": Counter(reason for group in groups for reason in group["reasons"]),
            "sources": Counter(group["sourceId"] for group in groups),
        },
        "groups": groups,
    }
    payload["summary"]["reasons"] = dict(payload["summary"]["reasons"])
    payload["summary"]["sources"] = dict(payload["summary"]["sources"])

    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    args.output_html.write_text(render_html(payload), encoding="utf-8")
    print(json.dumps({
        "ok": True,
        "json": str(args.output_json),
        "html": str(args.output_html),
        **payload["summary"],
    }, ensure_ascii=False, indent=2))


def group_assets(assets: list[Any], source_map: dict[str, Path]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[Any]] = {}
    for asset in assets:
        root = character_root(asset.packed_path)
        if not root:
            continue
        grouped.setdefault((asset.source_id, root), []).append(asset)

    candidates: list[dict[str, Any]] = []
    for (source_id, root), items in sorted(grouped.items(), key=lambda item: (item[0][0], item[0][1])):
        reasons = classify_generic_root(root)
        if not reasons:
            continue
        previews = preview_assets(items)
        candidates.append({
            "sourceId": source_id,
            "sourcePath": str(source_map.get(source_id, "")),
            "root": root,
            "assetCount": len(items),
            "bytes": sum(asset.size_bytes for asset in items),
            "reasons": reasons,
            "previewAssets": [
                {
                    "packedPath": asset.packed_path,
                    "extractedPath": str(asset.file_path),
                    "sizeBytes": asset.size_bytes,
                }
                for asset in previews
            ],
        })
    return candidates


def classify_generic_root(root: str) -> list[str]:
    parts = [part for part in root.lower().split("/") if part]
    if len(parts) < 3 or parts[:2] != ["ui", "characters"]:
        return []
    tail = parts[2:]
    first = tail[0]
    joined = "/".join(tail)
    tokens = set()
    for part in tail:
        tokens.update(token for token in re.split(r"[_\-/]+", part) if token)

    if looks_unique(first, joined, tokens):
        child_reasons = child_or_placeholder_reasons(tokens, tail)
        return child_reasons

    reasons: list[str] = []
    if first in ELEMENTS and len(tail) >= 2 and tail[1] in GENDERS:
        reasons.append("element_gender_root")
    if is_role_root(first) and any(part in GENDERS for part in tail[1:3]):
        reasons.append("role_gender_root")
    if GENERIC_TOKENS.intersection(tokens) or first in GENERIC_TOKENS:
        reasons.append("generic_token")
    if child_or_placeholder_reasons(tokens, tail):
        reasons.extend(child_or_placeholder_reasons(tokens, tail))
    return sorted(set(reasons))


def looks_unique(first: str, joined: str, tokens: set[str]) -> bool:
    if first.startswith(("3k_", "ep_", "lb_", "mh_", "aw_", "lshz_", "bfg_")):
        return True
    if any(hint in joined for hint in UNIQUE_HINTS):
        return True
    if "hero" in tokens and "special" in tokens:
        return True
    return False


def is_role_root(value: str) -> bool:
    if value in ROLE_ROOTS:
        return True
    return bool(re.match(r"^(?:yt|ytr|yellow_turban|nanman|bandit|han)_(?:healer|scholar|veteran|strategist|eunuch|eunuchs)$", value))


def child_or_placeholder_reasons(tokens: set[str], tail: list[str]) -> list[str]:
    reasons: list[str] = []
    child_tokens = {"baby", "child", "children", "kid", "kids", "infant", "toddler"}
    if child_tokens.intersection(tokens):
        reasons.append("child_or_baby")
    if tail and tail[0] == "placeholder_ui":
        reasons.append("placeholder_ui")
    return reasons


def character_root(path: str) -> str:
    lower = path.lower()
    if not lower.startswith("ui/characters/"):
        return ""
    for marker in ("/composites/", "/stills/"):
        if marker in lower:
            return path[: lower.index(marker)]
    parts = path.split("/")
    return "/".join(parts[:3]) if len(parts) >= 3 else ""


def preview_assets(assets: list[Any]) -> list[Any]:
    markers = [
        "/stills/halfbody_large/",
        "/stills/unitcards/",
        "/composites/large_panel/",
        "/composites/small_panel/",
    ]
    picked: list[Any] = []
    seen: set[str] = set()
    for marker in markers:
        for asset in sorted(assets, key=lambda item: item.packed_path.lower()):
            if marker in asset.packed_path.lower() and asset.packed_path not in seen:
                picked.append(asset)
                seen.add(asset.packed_path)
                if len(picked) >= 6:
                    return picked
    return picked


def render_html(payload: dict[str, Any]) -> str:
    css = """
body{font-family:Segoe UI,Malgun Gothic,sans-serif;margin:24px;background:#f6f4ef;color:#25231e}
h1{font-size:22px}.summary{color:#5b574c;margin-bottom:18px}.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(360px,1fr));gap:14px}
.card{background:white;border:1px solid #d8d2c4;border-radius:8px;padding:12px}.title{font-weight:700;font-size:14px;word-break:break-all}
.meta{font-size:12px;color:#716b5d;margin:6px 0 10px;word-break:break-all}.badge{display:inline-block;background:#eee0c4;border:1px solid #d4c39b;border-radius:4px;padding:2px 5px;margin:2px;font-size:11px}
.imgs{display:grid;grid-template-columns:repeat(3,1fr);gap:8px}.imgbox{background:#eee9dd;border:1px solid #ded7c8;min-height:72px;display:flex;align-items:center;justify-content:center;overflow:hidden}
.imgbox img{max-width:100%;max-height:150px}.path{font-size:10px;color:#5f5a50;word-break:break-all;margin-top:4px}
"""
    summary = payload["summary"]
    html = [
        "<!doctype html><meta charset=\"utf-8\">",
        "<title>Generic Asset Candidates</title>",
        f"<style>{css}</style>",
        "<h1>Generic / 비고유 asset 후보</h1>",
        (
            f"<p class=\"summary\">groups {summary['candidateGroupCount']} / "
            f"assets {summary['candidateAssetCount']}</p>"
        ),
        "<div class=\"grid\">",
    ]
    for group in payload["groups"]:
        html.append("<section class=\"card\">")
        html.append(f"<div class=\"title\">{escape(group['root'])}</div>")
        badges = "".join(f"<span class=\"badge\">{escape(reason)}</span>" for reason in group["reasons"])
        html.append(
            f"<div class=\"meta\">source: {escape(group['sourceId'])}<br>"
            f"{escape(group.get('sourcePath') or 'UNKNOWN')}<br>"
            f"assets: {group['assetCount']} / bytes: {group['bytes']}<br>{badges}</div>"
        )
        html.append("<div class=\"imgs\">")
        for asset in group["previewAssets"]:
            src = Path(asset["extractedPath"]).resolve().as_uri()
            html.append(
                f"<div><div class=\"imgbox\"><img src=\"{src}\"></div>"
                f"<div class=\"path\">{escape(asset['packedPath'])}</div></div>"
            )
        html.append("</div></section>")
    html.append("</div>")
    return "\n".join(html)


if __name__ == "__main__":
    main()
