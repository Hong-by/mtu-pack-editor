from __future__ import annotations

from pathlib import Path

from tk_pack_builder.adapters import adapter_for
from tk_pack_builder.web import _ensure_rpfm_server


def main() -> None:
    pack_path = Path("output/my_hero_patch.pack").resolve()
    _ensure_rpfm_server()
    session = adapter_for("rpfm").open_pack(pack_path)
    try:
        print("PACK", pack_path)
        files = session.list_files()
        print("FILES hby/ui/script/loc")
        for packed_file in files:
            if (
                "hby_" in packed_file
                or packed_file.startswith("ui/characters/hby")
                or packed_file.startswith("text/")
                or packed_file.startswith("script/")
            ):
                print(" ", packed_file)

        print("\nLOC")
        for loc_file in session.list_loc_files():
            loc = session.read_loc(loc_file)
            print(" ", loc_file, len(loc))
            for key, value in loc.items():
                if "hby" in key or "names_" in key or "ceo" in key:
                    print("   ", key, "=>", value)

        aliases = [
            "character_generation_templates",
            "character_generation_template_game_mode_details",
            "campaign_character_art_sets",
            "campaign_character_arts",
            "names",
            "land_units",
            "unit_armour_types",
            "melee_weapons",
            "projectiles",
            "ceo_initial_datas",
            "ceos",
            "ceo_nodes",
            "retinues",
            "retinue_slot_initial_units",
            "cai_retinues_to_aspects",
            "land_units_to_unit_abilites_junctions",
        ]
        for alias in aliases:
            try:
                rows = session.read_table(alias)
            except Exception as exc:
                print("\nTABLE", alias, "ERR", exc)
                continue
            hits = []
            for row in rows:
                haystack = " ".join(str(value) for value in row.values())
                if (
                    "hby_" in haystack
                    or "dy_Tiger" in haystack
                    or "Tiger of Jiangdong" in haystack
                    or "공손" in haystack
                    or "3k_main_hero_generic_water_strategist" in haystack
                    or "3k_main_general_generic_water_strategist" in haystack
                ):
                    hits.append(row)
            print("\nTABLE", alias, "rows", len(rows), "hits", len(hits))
            display_rows = hits if hits else rows[:30]
            for row in display_rows[:30]:
                print(" ", row)
    finally:
        session.close()


if __name__ == "__main__":
    main()
