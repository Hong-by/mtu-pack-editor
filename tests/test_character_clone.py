from __future__ import annotations

import unittest
from typing import Any

from tk_pack_builder.character_clone import apply_character_clones, apply_character_patches
from tk_pack_builder.recipe import CharacterClone, CharacterPatch


class FakePackSession:
    def __init__(self, tables: dict[str, list[dict[str, Any]]]) -> None:
        self.tables = {key: [dict(row) for row in rows] for key, rows in tables.items()}

    def list_tables(self) -> list[str]:
        return list(self.tables)

    def read_table(self, table_name: str) -> list[dict[str, Any]]:
        return [dict(row) for row in self.tables[table_name]]

    def replace_table(self, table_name: str, rows: list[dict[str, Any]]) -> None:
        self.tables[table_name] = [dict(row) for row in rows]


def _legacy_character_session() -> FakePackSession:
    return FakePackSession({
        "db/character_generation_templates_tables/_mtu_characters": [
            {
                "key": "source_template",
                "art_set_override": "source_art",
                "spawn_age_range": "source_age",
                "forename": "1",
                "is_male": False,
                "subtype": "3k_general_fire",
            },
        ],
        "db/character_generation_template_game_mode_details_tables/_mtu_characters": [
            {
                "character_generation_template": "source_template",
                "game_mode": "historical",
                "initial_ceos": "source_initial",
                "retinue": "source_retinue",
                "skill_set_override": "source_skillset",
            },
        ],
        "db/campaign_character_art_sets_tables/_mtu_characters": [
            {"art_set_id": "source_art", "is_male": False},
        ],
        "db/campaign_character_arts_tables/_mtu_characters": [
            {"art_set_id": "source_art", "age": 16, "has_come_of_age": True},
        ],
        "db/character_generation_spawn_age_ranges_tables/_mtu_characters": [
            {"key": "source_age"},
        ],
        "db/ceo_initial_datas_tables/_mtu_characters_ceo": [
            {"key": "source_initial"},
        ],
    })


class CharacterCloneLegacyPathTest(unittest.TestCase):
    def test_apply_character_clones_fills_missing_romance_detail(self) -> None:
        session = _legacy_character_session()

        apply_character_clones(
            session,
            [CharacterClone(
                new_template_key="hby_template_new",
                source_template_key="source_template",
                detail_source_template_key="source_template",
                new_art_set_id=None,
                art_set_source_id=None,
                new_age_range_key=None,
                age_range_source_key=None,
                new_initial_ceo_key=None,
                initial_ceo_source_key=None,
                template_overrides={},
                detail_overrides={},
                art_set_overrides={},
                art_overrides={},
                age_range_overrides={},
                image_assets=[],
            )],
        )

        details = [
            row for row in session.read_table("db/character_generation_template_game_mode_details_tables/_mtu_characters")
            if row["character_generation_template"] == "hby_template_new"
        ]
        self.assertEqual({row["game_mode"] for row in details}, {"historical", "romance"})
        self.assertEqual({row["initial_ceos"] for row in details}, {"source_initial"})

    def test_apply_character_patches_fills_missing_romance_detail(self) -> None:
        session = _legacy_character_session()

        apply_character_patches(
            session,
            [CharacterPatch(
                template_key="source_template",
                template_overrides={},
                detail_overrides={"historical": {"retinue": "hby_retinue"}},
            )],
        )

        details = [
            row for row in session.read_table("db/character_generation_template_game_mode_details_tables/_mtu_characters")
            if row["character_generation_template"] == "source_template"
        ]
        by_mode = {row["game_mode"]: row for row in details}
        self.assertEqual(set(by_mode), {"historical", "romance"})
        self.assertEqual(by_mode["historical"]["retinue"], "hby_retinue")
        self.assertEqual(by_mode["romance"]["retinue"], "hby_retinue")
        self.assertEqual(by_mode["romance"]["skill_set_override"], "source_skillset")


if __name__ == "__main__":
    unittest.main()
