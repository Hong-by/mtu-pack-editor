from __future__ import annotations

from pathlib import Path

from tk_pack_builder.internal_materials import MaterialPackSession


NEEDLES = [
    "3k_main_template_historical_dong_bai_hero_metal",
    "3k_main_hero_special_water_lady_dong_bai",
    "3k_mtu_lady_dong_bai",
    "3k_mtu_hero_special_water_lady_gongsun_jinting",
    "3k_main_general_metal_generic",
    "3k_main_general_generic_metal",
    "3k_main_hero_generic_metal",
    "3k_main_general_generic_water_strategist",
    "3k_main_hero_generic_water_strategist",
]


def main() -> None:
    session = MaterialPackSession.open(Path("work/internal_materials/materials.v015.json"))
    try:
        for table_path in session.list_tables():
            lower_path = table_path.lower()
            if not any(
                token in lower_path
                for token in [
                    "land_units",
                    "retinue",
                    "campaign_character_art",
                    "unit_abil",
                    "abilities",
                ]
            ):
                continue
            rows = session.read_table(table_path)
            hits = [
                row for row in rows
                if any(needle.lower() in " ".join(map(str, row.values())).lower() for needle in NEEDLES)
            ]
            if hits:
                print("TABLE", table_path, "rows", len(rows), "hits", len(hits))
                for row in hits[:40]:
                    print(" ", row)
    finally:
        session.close()


if __name__ == "__main__":
    main()
