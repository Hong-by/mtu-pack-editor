from __future__ import annotations

import hashlib
from collections import defaultdict
from pathlib import Path

from tk_pack_builder.adapters import adapter_for
from tk_pack_builder.web import _ensure_rpfm_server


ALIASES = [
    "character_generation_templates",
    "character_generation_template_game_mode_details",
    "campaign_character_art_sets",
    "campaign_character_arts",
    "land_units",
    "unit_armour_types",
    "retinues",
    "retinue_slot_initial_units",
    "land_units_to_unit_abilites_junctions",
]


def row_key(row: dict) -> str:
    return str(row.get("key") or row.get("Key") or row.get("id") or row.get("Id") or "")


def contains_hby(row: dict) -> bool:
    return "hby_" in " ".join(str(value) for value in row.values())


def first_existing(row: dict, names: list[str]) -> object:
    for name in names:
        if name in row:
            return row.get(name)
    return None


def compact(row: dict) -> dict:
    keys = [
        "key",
        "art_set_override",
        "spawn_age_range",
        "subtype",
        "weight",
        "min_spawn_round",
        "max_spawn_round",
        "template",
        "game_mode",
        "attribute_set",
        "skill_set_override",
        "retinue",
        "initial_ceos",
        "art_set_id",
        "art_set",
        "portrait",
        "card",
        "agent_type",
        "culture",
        "subculture",
        "faction",
        "is_custom",
        "is_male",
        "agent_subtype",
        "campaign_map_scale",
        "armour_value",
        "audio_type",
        "unit",
        "melee_attack",
        "charge_bonus",
        "morale",
        "unit_category",
        "class",
    ]
    return {key: row.get(key) for key in keys if key in row}


def main() -> None:
    pack_path = Path("output/my_hero_patch.pack").resolve()
    data = pack_path.read_bytes()
    print(f"PACK {pack_path}")
    print(f"SIZE {len(data)}")
    print(f"SHA256 {hashlib.sha256(data).hexdigest()[:16]}")
    print(f"MTIME {pack_path.stat().st_mtime}")

    _ensure_rpfm_server()
    session = adapter_for("rpfm").open_pack(pack_path)
    try:
        files = session.list_files()
        image_files = [path for path in files if path.startswith("ui/characters/")]
        image_folders = defaultdict(int)
        for path in image_files:
            parts = path.split("/")
            if len(parts) >= 3:
                image_folders[parts[2]] += 1
        print("\nIMAGE_FOLDERS")
        for folder, count in sorted(image_folders.items()):
            print(f"  {folder}: {count}")

        tables = {}
        for alias in ALIASES:
            try:
                tables[alias] = session.read_table(alias)
            except Exception as exc:
                print(f"\nTABLE {alias} ERROR {exc}")
                tables[alias] = []

        print("\nHBY_ROWS")
        for alias in ALIASES:
            rows = [row for row in tables[alias] if contains_hby(row)]
            print(f"\n[{alias}] {len(rows)}")
            for row in rows[:20]:
                print(" ", compact(row))

        template_rows = [
            row for row in tables["character_generation_templates"]
            if row_key(row).startswith("hby_template_")
        ]
        print("\nLINK_CHECK")
        for template in template_rows:
            template_key = row_key(template)
            art_set = str(template.get("art_set_override") or "")
            detail_rows = [
                row for row in tables["character_generation_template_game_mode_details"]
                if str(first_existing(row, ["template", "character_generation_template"])) == template_key
            ]
            art_set_rows = [
                row for row in tables["campaign_character_art_sets"]
                if row_key(row) == art_set or str(row.get("art_set_id") or "") == art_set
            ]
            art_rows = [
                row for row in tables["campaign_character_arts"]
                if str(row.get("art_set") or row.get("art_set_id") or "") == art_set
            ]
            tokens = set()
            for row in art_rows:
                for column in ("portrait", "card"):
                    value = str(row.get(column) or "").strip("/")
                    if value:
                        tokens.add(value.split("/")[0])
            print(f"  template={template_key} art_set={art_set}")
            print(f"    details={[(row.get('game_mode'), row.get('retinue')) for row in detail_rows]}")
            print(f"    art_set_rows={len(art_set_rows)} {compact(art_set_rows[0]) if art_set_rows else None}")
            print(f"    art_tokens={sorted(tokens)}")
            for token in sorted(tokens):
                print(f"    image_folder[{token}]={image_folders.get(token, 0)}")
    finally:
        session.close()


if __name__ == "__main__":
    main()
