from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tk_pack_builder.asset_manifest import build_asset_manifest  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a v0.1.5 internal asset manifest from extracted assets.")
    parser.add_argument(
        "--materials",
        type=Path,
        default=ROOT / "work" / "internal_materials" / "materials.v015.json",
    )
    parser.add_argument("--asset-root", type=Path, default=ROOT / "work" / "assets")
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "work" / "internal_materials" / "asset_manifest.v015.json",
    )
    parser.add_argument(
        "--pack-root",
        action="append",
        type=Path,
        dest="pack_roots",
        default=None,
        help="Pack file or directory used only to map extracted asset source ids back to known packs.",
    )
    args = parser.parse_args()

    pack_roots = args.pack_roots or [
        ROOT / "work" / "packs",
        ROOT / "work" / "packs" / "refs",
        ROOT / "work" / "legacy_template",
    ]
    manifest = build_asset_manifest(
        materials_path=args.materials.resolve(),
        asset_root=args.asset_root.resolve(),
        pack_roots=[path.resolve() for path in pack_roots],
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "ok": True,
        "manifest": str(args.output),
        **manifest["summary"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
