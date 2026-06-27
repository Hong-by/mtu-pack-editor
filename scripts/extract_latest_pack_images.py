from __future__ import annotations

from pathlib import Path

from tk_pack_builder.adapters import adapter_for
from tk_pack_builder.web import _ensure_rpfm_server


def main() -> None:
    pack_path = Path("output/my_hero_patch.pack").resolve()
    output_dir = Path("work/test-output/latest_pack_images")
    output_dir.mkdir(parents=True, exist_ok=True)
    _ensure_rpfm_server()
    session = adapter_for("rpfm").open_pack(pack_path)
    try:
        for packed_path in session.list_files():
            if not packed_path.startswith("ui/characters/hby_"):
                continue
            if not (
                "/stills/halfbody_large/" in packed_path
                or "/stills/unitcards/" in packed_path
                or "/composites/large_panel/norm/" in packed_path
            ):
                continue
            target = output_dir / packed_path.replace("/", "__")
            target.write_bytes(session.read_file_bytes(packed_path))
            print(target)
    finally:
        session.close()


if __name__ == "__main__":
    main()
