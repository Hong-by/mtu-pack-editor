from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tk_pack_builder.adapters import RpfmAdapter


PACK_PATH = Path("/Users/hong/Downloads/my_hero.pack")
OUTPUT_PATH = ROOT / "work" / "rpfm_character_row_add_smoke.pack"
TABLE_PATH = "db/character_generation_templates_tables/_mtu_characters"
SOURCE_TEMPLATE = "3k_mtu_template_historical_chen_jiu_hero_wood"
NEW_TEMPLATE = "hby_template_clone_smoke_chen_jiu_hero_wood"


def main() -> int:
    if OUTPUT_PATH.exists():
        OUTPUT_PATH.unlink()

    session = RpfmAdapter().open_pack(PACK_PATH)
    verify = None
    try:
        rows = session.read_table(TABLE_PATH)
        if any(row.get("key") == NEW_TEMPLATE for row in rows):
            raise RuntimeError(f"Smoke key already exists: {NEW_TEMPLATE}")

        source = next(row for row in rows if row["key"] == SOURCE_TEMPLATE)
        clone = dict(source)
        clone["key"] = NEW_TEMPLATE
        clone["weight"] = 0.0
        clone["min_spawn_round"] = 999
        clone["max_spawn_round"] = 999
        rows.append(clone)

        session.replace_table(TABLE_PATH, rows)
        session.save_as_pack(OUTPUT_PATH)

        verify = RpfmAdapter().open_pack(OUTPUT_PATH)
        verified_rows = verify.read_table(TABLE_PATH)
        verified = next(row for row in verified_rows if row.get("key") == NEW_TEMPLATE)
    finally:
        if verify is not None:
            verify.close()
        session.close()

    print(
        json.dumps(
            {
                "ok": verified["key"] == NEW_TEMPLATE,
                "output": str(OUTPUT_PATH),
                "table": TABLE_PATH,
                "sourceTemplate": SOURCE_TEMPLATE,
                "newTemplate": NEW_TEMPLATE,
                "verified": {
                    "key": verified["key"],
                    "art_set_override": verified["art_set_override"],
                    "subtype": verified["subtype"],
                    "weight": verified["weight"],
                    "min_spawn_round": verified["min_spawn_round"],
                    "max_spawn_round": verified["max_spawn_round"],
                },
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
