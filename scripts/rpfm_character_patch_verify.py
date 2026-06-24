from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tk_pack_builder.adapters import RpfmAdapter


TEMPLATE = "3k_mtu_template_historical_chen_jiu_hero_wood"
TEMPLATES_TABLE = "db/character_generation_templates_tables/_mtu_characters"
DETAILS_TABLE = "db/character_generation_template_game_mode_details_tables/_mtu_characters"


def require_one(rows: list[dict], predicate, label: str) -> dict:
    matches = [row for row in rows if predicate(row)]
    if len(matches) != 1:
        raise SystemExit(f"{label}: expected 1 row, found {len(matches)}")
    return matches[0]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("pack", type=Path)
    args = parser.parse_args()

    session = RpfmAdapter().open_pack(args.pack.resolve())
    try:
        templates = session.read_table(TEMPLATES_TABLE)
        details = session.read_table(DETAILS_TABLE)
    finally:
        session.close()

    template = require_one(templates, lambda row: row.get("key") == TEMPLATE, "template")
    historical = require_one(
        details,
        lambda row: row.get("character_generation_template") == TEMPLATE and row.get("game_mode") == "historical",
        "historical detail",
    )
    romance = require_one(
        details,
        lambda row: row.get("character_generation_template") == TEMPLATE and row.get("game_mode") == "romance",
        "romance detail",
    )

    expected = {
        "weight": 42.0,
        "min_spawn_round": 10,
        "max_spawn_round": 120,
        "historical_retinue": "3k_main_general_generic_earth",
        "romance_retinue": "3k_main_hero_generic_earth",
        "historical_skill": "3k_main_skillset_historical_dong_min",
        "romance_skill": "3k_main_skillset_historical_dong_min",
    }
    actual = {
        "weight": template["weight"],
        "min_spawn_round": template["min_spawn_round"],
        "max_spawn_round": template["max_spawn_round"],
        "historical_retinue": historical["retinue"],
        "romance_retinue": romance["retinue"],
        "historical_skill": historical["skill_set_override"],
        "romance_skill": romance["skill_set_override"],
    }
    if actual != expected:
        raise SystemExit(f"patch values mismatch: expected {expected!r}, got {actual!r}")

    print(json.dumps(actual, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
