from __future__ import annotations

import argparse
import json
import sys
from html import escape
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tk_pack_builder.asset_manifest import inventory_asset_files  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a simple HTML gallery for extracted character assets.")
    parser.add_argument("--asset-root", type=Path, default=ROOT / "work" / "assets")
    parser.add_argument(
        "--source-id",
        action="append",
        dest="source_ids",
        help="Limit gallery to one or more extracted asset source ids. Can be passed multiple times.",
    )
    parser.add_argument("--title", default="MTU Asset Gallery")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-groups", type=int, default=300)
    args = parser.parse_args()

    assets = inventory_asset_files(args.asset_root.resolve())
    source_ids = set(args.source_ids or [])
    if source_ids:
        assets = [asset for asset in assets if asset.source_id in source_ids]
    groups: dict[str, list[Any]] = {}
    for asset in assets:
        root = character_root(asset.packed_path)
        if not root:
            continue
        groups.setdefault(root, []).append(asset)

    html = render_gallery(args.title, groups, args.max_groups)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(html, encoding="utf-8")
    print(json.dumps({
        "ok": True,
        "output": str(args.output),
        "sourceIds": sorted(source_ids),
        "assetCount": len(assets),
        "groupCount": len(groups),
    }, ensure_ascii=False, indent=2))


def character_root(path: str) -> str:
    lower = path.lower()
    if not lower.startswith("ui/characters/"):
        return ""
    for marker in ("/composites/", "/stills/"):
        if marker in lower:
            return path[: lower.index(marker)]
    parts = path.split("/")
    return "/".join(parts[:3]) if len(parts) >= 3 else ""


def render_gallery(title: str, groups: dict[str, list[Any]], max_groups: int) -> str:
    css = """
body{font-family:Segoe UI,Malgun Gothic,sans-serif;margin:24px;background:#f6f4ef;color:#25231e}
h1{font-size:22px}.summary{margin:0 0 18px;color:#5b574c}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:14px}
.card{background:white;border:1px solid #d8d2c4;border-radius:8px;padding:12px}
.title{font-weight:700;font-size:14px;margin-bottom:4px;word-break:break-all}
.meta{font-size:12px;color:#716b5d;margin-bottom:10px;word-break:break-all}
.imgs{display:grid;grid-template-columns:repeat(4,1fr);gap:8px}
.imgbox{background:#eee9dd;border:1px solid #ded7c8;min-height:70px;display:flex;align-items:center;justify-content:center;overflow:hidden}
.imgbox img{max-width:100%;max-height:160px;display:block}
.path{font-size:10px;color:#5f5a50;word-break:break-all;margin-top:4px}
"""
    ordered = sorted(groups.items(), key=lambda item: item[0].lower())[:max_groups]
    parts = [
        "<!doctype html><meta charset=\"utf-8\">",
        f"<title>{escape(title)}</title>",
        f"<style>{css}</style>",
        f"<h1>{escape(title)}</h1>",
        f"<p class=\"summary\">groups {len(groups)} / showing {len(ordered)} / assets {sum(len(v) for v in groups.values())}</p>",
        "<div class=\"grid\">",
    ]
    for root, assets in ordered:
        previews = preview_assets(assets)
        parts.append("<section class=\"card\">")
        parts.append(f"<div class=\"title\">{escape(root)}</div>")
        parts.append(f"<div class=\"meta\">assets: {len(assets)}</div>")
        parts.append("<div class=\"imgs\">")
        for asset in previews:
            src = asset.file_path.resolve().as_uri()
            parts.append(
                f"<div><div class=\"imgbox\"><img src=\"{src}\"></div>"
                f"<div class=\"path\">{escape(asset.packed_path)}</div></div>"
            )
        parts.append("</div></section>")
    parts.append("</div>")
    return "\n".join(parts)


def preview_assets(assets: list[Any]) -> list[Any]:
    priority = [
        "/stills/halfbody_large/",
        "/stills/unitcards/",
        "/composites/large_panel/norm/",
        "/composites/large_panel/happy/",
        "/composites/small_panel/",
    ]
    picked: list[Any] = []
    seen: set[str] = set()
    for marker in priority:
        for asset in sorted(assets, key=lambda item: item.packed_path.lower()):
            if marker not in asset.packed_path.lower() or asset.packed_path in seen:
                continue
            picked.append(asset)
            seen.add(asset.packed_path)
            if len(picked) >= 8:
                return picked
    for asset in sorted(assets, key=lambda item: item.packed_path.lower()):
        if asset.packed_path in seen:
            continue
        picked.append(asset)
        if len(picked) >= 8:
            break
    return picked


if __name__ == "__main__":
    main()
