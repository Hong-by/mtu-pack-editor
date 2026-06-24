from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tk_pack_builder.adapters import RpfmAdapter


NEW_TEMPLATE = "hby_template_clone_chen_jiu_body_dong_min_art"
NEW_ART_SET = "hby_art_set_clone_dong_min_general"
NEW_AGE = "hby_age_clone_chen_jiu"
NEW_CEO = "hby_ceo_initial_data_clone_chen_jiu"


TABLES = {
    "templates": "db/character_generation_templates_tables/_mtu_characters",
    "details": "db/character_generation_template_game_mode_details_tables/_mtu_characters",
    "art_sets": "db/campaign_character_art_sets_tables/_mtu_characters",
    "arts": "db/campaign_character_arts_tables/_mtu_characters",
    "ages": "db/character_generation_spawn_age_ranges_tables/_mtu_characters",
    "ceos": "db/ceo_initial_datas_tables/_mtu_characters_ceo",
}


def require_one(rows: list[dict], predicate, label: str) -> dict:
    matches = [row for row in rows if predicate(row)]
    if len(matches) != 1:
        raise SystemExit(f"{label}: expected 1 row, found {len(matches)}")
    return matches[0]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("pack", type=Path)
    args = parser.parse_args()

    adapter = RpfmAdapter()
    session = adapter.open_pack(args.pack.resolve())
    try:
        tables = {name: session.read_table(table) for name, table in TABLES.items()}
    finally:
        session.close()

    template = require_one(tables["templates"], lambda row: row.get("key") == NEW_TEMPLATE, "template")
    detail_rows = [row for row in tables["details"] if row.get("character_generation_template") == NEW_TEMPLATE]
    if {row.get("game_mode") for row in detail_rows} != {"historical", "romance"}:
        raise SystemExit(f"details: expected historical and romance rows, found {detail_rows!r}")

    art_set = require_one(tables["art_sets"], lambda row: row.get("art_set_id") == NEW_ART_SET, "art_set")
    art_rows = [row for row in tables["arts"] if row.get("art_set_id") == NEW_ART_SET]
    if not art_rows:
        raise SystemExit("arts: expected at least 1 cloned art row")

    age = require_one(tables["ages"], lambda row: row.get("key") == NEW_AGE, "age")
    ceo = require_one(tables["ceos"], lambda row: row.get("key") == NEW_CEO, "ceo")

    if template.get("art_set_override") != NEW_ART_SET:
        raise SystemExit("template: art_set_override does not point to cloned art set")
    if template.get("spawn_age_range") != NEW_AGE:
        raise SystemExit("template: spawn_age_range does not point to cloned age range")
    if any(row.get("initial_ceos") != NEW_CEO for row in detail_rows):
        raise SystemExit("details: initial_ceos does not point to cloned CEO")

    summary = {
        "template": template["key"],
        "detailRows": len(detail_rows),
        "artSet": art_set["art_set_id"],
        "artRows": len(art_rows),
        "age": age["key"],
        "ceo": ceo["key"],
    }
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
