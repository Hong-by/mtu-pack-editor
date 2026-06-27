from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tk_pack_builder.adapters import adapter_for  # noqa: E402
from tk_pack_builder.delta_builder import build_delta_pack_from_materials  # noqa: E402
from tk_pack_builder.internal_materials import MaterialPackSession  # noqa: E402
from tk_pack_builder.recipe import load_recipe  # noqa: E402
from tk_pack_builder.web import _ensure_rpfm_server  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a pack using internal material rows as the source.")
    parser.add_argument("--recipe", type=Path, default=ROOT / "examples" / "recipe.character-clone.json")
    parser.add_argument("--materials", type=Path, default=ROOT / "work" / "internal_materials" / "materials.v015.json")
    parser.add_argument(
        "--writer-template",
        type=Path,
        default=ROOT / "work" / "packs" / "my_hero.pack",
        help="Temporary RPFM writer/template pack. Data rows come from --materials.",
    )
    parser.add_argument("--output", type=Path, default=ROOT / "work" / "internal_materials" / "material_build.pack")
    args = parser.parse_args()

    recipe = load_recipe(args.recipe)
    source_session = MaterialPackSession.open(args.materials.resolve())

    _ensure_rpfm_server()
    writer_session = adapter_for("rpfm").open_pack(args.writer_template.resolve())
    try:
        messages = build_delta_pack_from_materials(source_session, writer_session, recipe, args.output.resolve())
    finally:
        writer_session.close()

    print(json.dumps({
        "ok": not any(message.get("level") == "error" for message in messages),
        "output": str(args.output.resolve()),
        "messages": messages,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
