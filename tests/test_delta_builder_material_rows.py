from __future__ import annotations

import json
import tempfile
import unittest
import zlib
from collections import defaultdict
from pathlib import Path
from unittest.mock import patch

import tk_pack_builder.delta_builder as delta_builder
from tk_pack_builder.delta_builder import (
    _campaign_start_spawn_script,
    _character_clone_integrity_warnings,
    _collect_attribute_set_clone_rows,
    _collect_character_dependency_rows,
    _collect_character_clone_rows,
    _collect_character_patch_rows,
    _collect_land_unit_clone_rows,
    _collect_stat_patch_rows,
    _db_with_rows,
    _copy_skill_dependency,
    _loc_db_with_rows,
    _merge_source_table_rows,
    _read_rows,
    _spawn_entries_for_clones,
    _unique_lua_ceo_keys,
)
from tk_pack_builder.internal_materials import MaterialPackSession
from tk_pack_builder.recipe import ArmourTypeClone, AttributeSetClone, CharacterClone, CharacterPatch, LandUnitClone, Recipe, StatPatch, recipe_from_dict


class DeltaBuilderMaterialRowsTest(unittest.TestCase):
    def test_exact_table_patch_preserves_source_rows(self) -> None:
        source_db = {
            "table": {
                "definition": {
                    "fields": [
                        {"name": "art_set_id"},
                        {"name": "age"},
                        {"name": "portrait"},
                        {"name": "card"},
                        {"name": "id"},
                    ],
                },
                "table_data": [
                    ["set_a", 16, "old_a/", "old_a", 1],
                    ["set_b", 16, "old_b/", "old_b", 2],
                ],
            },
        }
        rows = _merge_source_table_rows(
            "db/campaign_character_arts_tables/!!ironic_addon_korea",
            source_db,
            [{"art_set_id": "set_a", "age": 16, "portrait": "new_a/", "card": "new_a", "id": 1}],
        )
        db = _db_with_rows(source_db, rows)

        self.assertEqual(len(db["table"]["table_data"]), 2)
        self.assertEqual(db["table"]["table_data"][0][2], "new_a/")
        self.assertEqual(db["table"]["table_data"][1][2], "old_b/")

    def test_character_patch_name_uses_existing_name_group(self) -> None:
        payload = {
            "tables": {
                "db/character_generation_templates_tables/!!ironic_addon_korea_leader_fix": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [{
                        "key": "3k_mod_template_historical_gogukcheon_hero_fire",
                        "forename": "7654410",
                        "family_name": 0,
                        "clan_name": 0,
                        "other_name": 0,
                        "art_set_override": "3k_mod_art_set_historical_go_nammu_general",
                    }],
                },
                "db/character_generation_template_game_mode_details_tables/!!ironic_addon_korea_leader_fix": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [{
                        "character_generation_template": "3k_mod_template_historical_gogukcheon_hero_fire",
                        "game_mode": "historical",
                    }],
                },
                "db/names_tables/data__": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [{"names_group": 221, "type": 1, "gender": 2, "frequency": 1, "id": "unrelated"}],
                },
                "db/names_tables/!!ironic_addon_korea_unique_names_two": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [{"names_group": 342318990, "type": 0, "gender": 0, "frequency": 0, "id": "7654410"}],
                },
            },
            "loc": {},
            "assets": {},
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "materials.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            session = MaterialPackSession.open(path)

        rows_by_table = {}
        loc_rows = {}
        _collect_character_patch_rows(
            session,
            [CharacterPatch(
                template_key="3k_mod_template_historical_gogukcheon_hero_fire",
                display_name="고남무",
                template_overrides={},
                detail_overrides={},
            )],
            {},
            rows_by_table,
            loc_rows,
        )

        names = rows_by_table["db/names_tables/!!ironic_addon_korea_unique_names_two"]
        self.assertEqual(names[0]["names_group"], 342318990)
        self.assertEqual(names[0]["type"], 0)
        self.assertEqual(names[0]["gender"], 0)
        self.assertEqual(loc_rows[f"names_name_{names[0]['id']}"], "고남무")

    def test_character_patch_name_id_avoids_existing_ids(self) -> None:
        template_key = "3k_mod_template_historical_go_gyesu_hero_wood"
        display_name = "고계수"
        colliding_id = str(2_000_000_000 + (zlib.crc32(f"{template_key}:{display_name}".encode("utf-8")) % 100_000_000))
        payload = {
            "tables": {
                "db/character_generation_templates_tables/!!ironic_addon_korea": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [{
                        "key": template_key,
                        "forename": "7654410",
                        "family_name": 0,
                        "clan_name": 0,
                        "other_name": 0,
                        "art_set_override": "3k_mod_art_set_historical_go_gyesu_general",
                    }],
                },
                "db/character_generation_template_game_mode_details_tables/!!ironic_addon_korea": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [{
                        "character_generation_template": template_key,
                        "game_mode": "historical",
                    }],
                },
                "db/names_tables/!!ironic_addon_korea_unique_names_two": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [
                        {"names_group": 342318990, "type": 0, "gender": 0, "frequency": 0, "id": "7654410"},
                        {"names_group": 342318990, "type": 0, "gender": 0, "frequency": 0, "id": colliding_id},
                    ],
                },
            },
            "loc": {},
            "assets": {},
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "materials.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            session = MaterialPackSession.open(path)

        rows_by_table = {}
        loc_rows = {}
        _collect_character_patch_rows(
            session,
            [CharacterPatch(
                template_key=template_key,
                display_name=display_name,
                template_overrides={},
                detail_overrides={},
            )],
            {},
            rows_by_table,
            loc_rows,
        )

        template = rows_by_table["db/character_generation_templates_tables/!!ironic_addon_korea"][0]
        self.assertNotEqual(str(template["forename"]), colliding_id)
        self.assertEqual(loc_rows[f"names_name_{template['forename']}"], display_name)

    def test_mixed_many_character_patches_and_clones_stay_isolated(self) -> None:
        payload = {
            "tables": {
                "db/character_generation_templates_tables/data__": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [
                        {
                            "key": "patch_template_a",
                            "forename": "1001",
                            "family_name": 0,
                            "clan_name": 0,
                            "other_name": 0,
                            "art_set_override": "patch_art_a",
                            "spawn_age_range": "age_patch_a",
                            "is_male": True,
                            "subtype": "3k_general_fire",
                        },
                        {
                            "key": "patch_template_b",
                            "forename": "1002",
                            "family_name": 0,
                            "clan_name": 0,
                            "other_name": 0,
                            "art_set_override": "patch_art_b",
                            "spawn_age_range": "age_patch_b",
                            "is_male": False,
                            "subtype": "3k_general_wood",
                        },
                        {
                            "key": "source_template_a",
                            "forename": "1003",
                            "family_name": 0,
                            "clan_name": 0,
                            "other_name": 0,
                            "art_set_override": "source_art_a",
                            "spawn_age_range": "age_source_a",
                            "is_male": True,
                            "subtype": "3k_general_earth",
                        },
                        {
                            "key": "source_template_b",
                            "forename": "1004",
                            "family_name": 0,
                            "clan_name": 0,
                            "other_name": 0,
                            "art_set_override": "source_art_b",
                            "spawn_age_range": "age_source_b",
                            "is_male": False,
                            "subtype": "3k_general_water",
                        },
                    ],
                },
                "db/character_generation_template_game_mode_details_tables/data__": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [
                        {"character_generation_template": "patch_template_a", "game_mode": "historical", "initial_ceos": "ceo_patch_a"},
                        {"character_generation_template": "patch_template_b", "game_mode": "historical", "initial_ceos": "ceo_patch_b"},
                        {"character_generation_template": "source_template_a", "game_mode": "historical", "initial_ceos": "ceo_source_a"},
                        {"character_generation_template": "source_template_a", "game_mode": "romance", "initial_ceos": "ceo_source_a"},
                        {"character_generation_template": "source_template_b", "game_mode": "historical", "initial_ceos": "ceo_source_b"},
                        {"character_generation_template": "source_template_b", "game_mode": "romance", "initial_ceos": "ceo_source_b"},
                    ],
                },
                "db/names_tables/data__": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [
                        {"names_group": 1, "type": 0, "gender": 0, "frequency": 1, "id": "1001"},
                        {"names_group": 1, "type": 0, "gender": 1, "frequency": 1, "id": "1002"},
                        {"names_group": 1, "type": 0, "gender": 0, "frequency": 1, "id": "1003"},
                        {"names_group": 1, "type": 0, "gender": 1, "frequency": 1, "id": "1004"},
                    ],
                },
                "db/campaign_character_art_sets_tables/data__": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [
                        {"art_set_id": "patch_art_a", "agent_type": "general", "culture": "3k_main_chinese", "is_male": True},
                        {"art_set_id": "patch_art_b", "agent_type": "general", "culture": "3k_main_chinese", "is_male": False},
                        {"art_set_id": "source_art_a", "agent_type": "general", "culture": "3k_main_chinese", "is_male": True},
                        {"art_set_id": "source_art_b", "agent_type": "general", "culture": "3k_main_chinese", "is_male": False},
                    ],
                },
                "db/campaign_character_arts_tables/data__": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [
                        {"art_set_id": "patch_art_a", "age": 16, "level": 0, "season": "none", "id": 1, "portrait": "patch_art_a/", "card": "patch_art_a", "uniform": "uniform_a", "has_come_of_age": True},
                        {"art_set_id": "patch_art_b", "age": 16, "level": 0, "season": "none", "id": 2, "portrait": "patch_art_b/", "card": "patch_art_b", "uniform": "uniform_b", "has_come_of_age": True},
                        {"art_set_id": "source_art_a", "age": 16, "level": 0, "season": "none", "id": 3, "portrait": "source_art_a/", "card": "source_art_a", "uniform": "uniform_c", "has_come_of_age": True},
                        {"art_set_id": "source_art_b", "age": 16, "level": 0, "season": "none", "id": 4, "portrait": "source_art_b/", "card": "source_art_b", "uniform": "uniform_d", "has_come_of_age": True},
                    ],
                },
                "db/character_generation_spawn_age_ranges_tables/data__": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [
                        {"key": "age_patch_a", "birth_year": 160},
                        {"key": "age_patch_b", "birth_year": 161},
                        {"key": "age_source_a", "birth_year": 162},
                        {"key": "age_source_b", "birth_year": 163},
                    ],
                },
                "db/ceo_initial_datas_tables/data__": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [
                        {"key": "ceo_patch_a", "ceo": "patch_ceo_a"},
                        {"key": "ceo_patch_b", "ceo": "patch_ceo_b"},
                        {"key": "ceo_source_a", "ceo": "source_ceo_a"},
                        {"key": "ceo_source_b", "ceo": "source_ceo_b"},
                    ],
                },
            },
            "loc": {},
            "assets": {},
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "materials.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            session = MaterialPackSession.open(path)

        source_dbs: dict[str, dict] = {}
        rows_by_table: dict[str, list[dict]] = {}
        loc_rows: dict[str, str] = {}
        patches = [
            CharacterPatch(
                template_key="patch_template_a",
                display_name="Patch Hero A",
                template_overrides={},
                detail_overrides={},
                art_overrides={"portrait": "patch_image_a/", "card": "patch_image_a"},
            ),
            CharacterPatch(
                template_key="patch_template_b",
                display_name="Patch Hero B",
                template_overrides={},
                detail_overrides={},
                art_overrides={"portrait": "patch_image_b/", "card": "patch_image_b"},
            ),
        ]
        clones = [
            CharacterClone(
                new_template_key="hby_template_a",
                source_template_key="source_template_a",
                detail_source_template_key="source_template_a",
                new_art_set_id="hby_art_a",
                art_set_source_id="source_art_a",
                new_age_range_key="hby_age_a",
                age_range_source_key="age_source_a",
                new_initial_ceo_key=None,
                initial_ceo_source_key="ceo_source_a",
                template_overrides={"subtype": "3k_general_earth"},
                detail_overrides={},
                art_set_overrides={},
                art_overrides={"portrait": "hby_image_a/", "card": "hby_image_a"},
                age_range_overrides={"birth_year": 170},
                spawn_event="campaign_start",
                display_name="Clone Hero A",
            ),
            CharacterClone(
                new_template_key="hby_template_b",
                source_template_key="source_template_b",
                detail_source_template_key="source_template_b",
                new_art_set_id="hby_art_b",
                art_set_source_id="source_art_b",
                new_age_range_key="hby_age_b",
                age_range_source_key="age_source_b",
                new_initial_ceo_key=None,
                initial_ceo_source_key="ceo_source_b",
                template_overrides={"subtype": "3k_general_water", "min_spawn_round": 4},
                detail_overrides={},
                art_set_overrides={},
                art_overrides={"portrait": "hby_image_b/", "card": "hby_image_b"},
                age_range_overrides={"birth_year": 171},
                spawn_event="delayed_join",
                display_name="Clone Hero B",
            ),
        ]

        self.assertEqual(_collect_character_patch_rows(session, patches, source_dbs, rows_by_table, loc_rows), 2)
        self.assertEqual(_collect_character_clone_rows(session, clones, source_dbs, rows_by_table, loc_rows), 2)
        _collect_character_dependency_rows(
            session,
            clones,
            source_dbs,
            rows_by_table,
            [],
            {str(session.pack_path.resolve()): session.pack_key},
        )

        template_rows = {
            row["key"]: row
            for rows in rows_by_table.values()
            for row in rows
            if row.get("key") in {"patch_template_a", "patch_template_b", "hby_template_a", "hby_template_b"}
        }
        self.assertEqual(len(template_rows), 4)
        forenames = {str(row["forename"]) for row in template_rows.values()}
        self.assertEqual(len(forenames), 4)
        self.assertTrue(all(f"names_name_{name_id}" in loc_rows for name_id in forenames))

        detail_rows = [
            row
            for rows in rows_by_table.values()
            for row in rows
            if row.get("character_generation_template") in {"hby_template_a", "hby_template_b"}
        ]
        self.assertEqual(len(detail_rows), 4)
        self.assertEqual(
            {row["initial_ceos"] for row in detail_rows if row["character_generation_template"] == "hby_template_a"},
            {"ceo_source_a"},
        )
        self.assertEqual(
            {row["initial_ceos"] for row in detail_rows if row["character_generation_template"] == "hby_template_b"},
            {"ceo_source_b"},
        )

        art_rows = [
            row
            for rows in rows_by_table.values()
            for row in rows
            if row.get("art_set_id") in {"hby_art_a", "hby_art_b", "patch_art_a", "patch_art_b"}
        ]
        self.assertTrue(any(row.get("portrait") == "hby_image_a/" and row.get("card") == "hby_image_a" for row in art_rows))
        self.assertTrue(any(row.get("portrait") == "hby_image_b/" and row.get("card") == "hby_image_b" for row in art_rows))
        self.assertTrue(any(row.get("portrait") == "patch_image_a/" and row.get("card") == "patch_image_a" for row in art_rows))
        self.assertTrue(any(row.get("portrait") == "patch_image_b/" and row.get("card") == "patch_image_b" for row in art_rows))

        self.assertEqual(_character_clone_integrity_warnings(clones, rows_by_table, loc_rows), [])
        spawn_entries = _spawn_entries_for_clones(clones)
        self.assertEqual(len(spawn_entries), 2)
        self.assertEqual({entry["template"] for entry in spawn_entries}, {"hby_template_a", "hby_template_b"})
        self.assertEqual({entry["turn"] for entry in spawn_entries}, {0, 4})
        self.assertTrue(all(str(entry["saveKey"]).startswith("hby_mtu_pack_editor_player_spawn_v7_") for entry in spawn_entries))
        self.assertTrue(all(str(entry["attemptKey"]).startswith("hby_mtu_pack_editor_player_spawn_attempt_v7_") for entry in spawn_entries))

    def test_loc_writer_skips_empty_loc_template_rows(self) -> None:
        class FakeClient:
            def send(self, command):
                path = command["DecodePackedFile"][1]
                rows = [] if path == "text/empty.loc" else [
                    [{"StringU8": "old_key"}, {"StringU8": "old_text"}, {"Boolean": True}]
                ]
                return {
                    "data": {
                        "LocRFileInfo": [{
                            "table": {
                                "definition": {
                                    "fields": [
                                        {"name": "key"},
                                        {"name": "text"},
                                        {"name": "tooltip"},
                                    ],
                                },
                                "table_data": rows,
                            },
                        }],
                    },
                }

        class FakeSession:
            client = FakeClient()
            pack_key = "pack"

            def list_loc_files(self):
                return ["text/empty.loc", "text/non_empty.loc"]

        loc_db = _loc_db_with_rows(FakeSession(), {"new_key": "new_text"})  # type: ignore[arg-type]

        self.assertEqual(
            loc_db["table"]["table_data"],
            [[{"StringU8": "new_key"}, {"StringU8": "new_text"}, {"Boolean": True}]],
        )

    def test_age_range_clone_same_key_payload_is_remapped_to_new_key(self) -> None:
        recipe = recipe_from_dict({
            "ageRangeClones": [{
                "sourceKey": "3k_main_age_fixed_historical_cao_cao_hero_earth",
                "newKey": "3k_main_age_fixed_historical_cao_cao_hero_earth",
                "overrides": {"birth_year": 155},
            }],
            "characterCloneRecipes": [{
                "newTemplateKey": "hby_template_test",
                "sourceTemplateKey": "source_template",
                "templateOverrides": {
                    "spawn_age_range": "3k_main_age_fixed_historical_cao_cao_hero_earth",
                },
                "detailOverrides": {},
                "artSetOverrides": {},
                "artOverrides": {},
                "ageRangeOverrides": {},
            }],
        })

        new_key = recipe.age_range_clones[0].new_key
        self.assertNotEqual(new_key, "3k_main_age_fixed_historical_cao_cao_hero_earth")
        self.assertTrue(new_key.startswith("hby_age_"))
        self.assertEqual(
            recipe.character_clones[0].template_overrides["spawn_age_range"],
            new_key,
        )

    def test_material_dependency_rows_aggregate_same_table_folder(self) -> None:
        payload = {
            "tables": {
                "db/character_skill_node_sets_tables/_mtu_characters_skills": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [{"key": "mtu_skillset"}],
                },
                "db/character_skill_node_sets_tables/data__": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [{"key": "3k_main_skillset_generic_general_water_strategist"}],
                },
            },
            "loc": {},
            "assets": {},
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "materials.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            session = MaterialPackSession.open(path)

        source_dbs = {}
        rows = _read_rows(session, "db/character_skill_node_sets_tables/_mtu_characters_skills", source_dbs)

        self.assertEqual({row["key"] for row in rows}, {
            "mtu_skillset",
            "3k_main_skillset_generic_general_water_strategist",
        })
        self.assertIn("db/character_skill_node_sets_tables/_mtu_characters_skills", source_dbs)
        self.assertIn("db/character_skill_node_sets_tables/data__", source_dbs)

    def test_attribute_set_clone_falls_back_to_internal_material_rows(self) -> None:
        source_db = {"table": {"definition": {"fields": []}, "table_data": []}}
        internal_payload = {
            "tables": {
                "db/character_attribute_sets_tables/data__": {
                    "db": source_db,
                    "rows": [{"set_name": "3k_main_attribute_set_general_wood_records"}],
                },
                "db/character_attributes_tables/data__": {
                    "db": source_db,
                    "rows": [
                        {
                            "set_name": "3k_main_attribute_set_general_wood_records",
                            "attribute_type": "authority",
                            "base_value": 40,
                        },
                        {
                            "set_name": "3k_main_attribute_set_general_wood_records",
                            "attribute_type": "resolve_records",
                            "base_value": 50,
                        },
                    ],
                },
            },
            "loc": {},
            "assets": {},
        }
        empty_payload = {"tables": {}, "loc": {}, "assets": {}}
        with tempfile.TemporaryDirectory() as tmp:
            internal_path = Path(tmp) / "materials.json"
            internal_path.write_text(json.dumps(internal_payload), encoding="utf-8")
            session_path = Path(tmp) / "empty.json"
            session_path.write_text(json.dumps(empty_payload), encoding="utf-8")
            session = MaterialPackSession.open(session_path)
            original_path = delta_builder.INTERNAL_MATERIALS_PATH
            delta_builder.INTERNAL_MATERIALS_PATH = internal_path
            try:
                rows_by_table = {}
                source_dbs = {}
                created = _collect_attribute_set_clone_rows(
                    session,
                    [AttributeSetClone(
                        source_set_key="3k_main_attribute_set_general_wood_records",
                        new_set_key="hby_attribute_set_wood_records",
                        overrides={"authority": 77},
                    )],
                    source_dbs,
                    rows_by_table,
                )
            finally:
                delta_builder.INTERNAL_MATERIALS_PATH = original_path

        self.assertEqual(created, 1)
        self.assertEqual(
            rows_by_table["db/character_attribute_sets_tables/data__"][0]["set_name"],
            "hby_attribute_set_wood_records",
        )
        attr_rows = rows_by_table["db/character_attributes_tables/data__"]
        self.assertEqual({row["set_name"] for row in attr_rows}, {"hby_attribute_set_wood_records"})
        self.assertEqual(
            next(row for row in attr_rows if row["attribute_type"] == "authority")["base_value"],
            77,
        )
        self.assertIn("db/character_attribute_sets_tables/data__", source_dbs)
        self.assertIn("db/character_attributes_tables/data__", source_dbs)

    def test_existing_skill_dependency_copies_skill_effect_rows(self) -> None:
        tables = {
            "character_skill_node_sets": [
                {"key": "skillset_a", "_sourceTablePath": "db/character_skill_node_sets_tables/data__"},
            ],
            "character_skill_nodes": [
                {
                    "key": "skillset_a_0A",
                    "character_skill_node_set_key": "skillset_a",
                    "character_skill_key": "skill_a",
                    "_sourceTablePath": "db/character_skill_nodes_tables/data__",
                },
            ],
            "character_skill_node_links": [],
            "character_skill_level_to_effects_junctions": [
                {
                    "character_skill_key": "skill_a",
                    "effect_key": "effect_a",
                    "effect_scope": "character_to_character_own",
                    "level": 1,
                    "_sourceTablePath": "db/character_skill_level_to_effects_junctions_tables/data__",
                },
            ],
            "effects": [
                {
                    "effect": "effect_a",
                    "category": "campaign",
                    "_sourceTablePath": "db/effects_tables/data__",
                },
            ],
        }
        table_names = {
            "character_skill_node_sets": "db/character_skill_node_sets_tables/data__",
            "character_skill_nodes": "db/character_skill_nodes_tables/data__",
            "character_skill_node_links": "db/character_skill_node_links_tables/data__",
            "character_skill_level_to_effects_junctions": "db/character_skill_level_to_effects_junctions_tables/data__",
            "effects": "db/effects_tables/data__",
        }
        rows_by_table = {}

        _copy_skill_dependency(tables, table_names, rows_by_table, "skillset_a")

        self.assertIn("db/character_skill_level_to_effects_junctions_tables/data__", rows_by_table)
        self.assertIn("db/effects_tables/data__", rows_by_table)
        self.assertEqual(rows_by_table["db/effects_tables/data__"][0]["effect"], "effect_a")

    def test_campaign_start_spawn_emits_lua_event_observer(self) -> None:
        self.assertEqual(
            delta_builder.CAMPAIGN_SPAWN_SCRIPT_PATH,
            "script/campaign/3k_main_campaign_map/mod/hby_mtu_pack_editor_player_spawn.lua",
        )
        self.assertIn(
            "script/campaign/3k_main_campaign_map/hby_mtu_pack_editor_player_spawn.lua",
            delta_builder.CAMPAIGN_SPAWN_SCRIPT_PATHS,
        )
        self.assertNotIn("/script/campaign/mod/", f"/{delta_builder.CAMPAIGN_SPAWN_SCRIPT_PATH}")

        clone = CharacterClone(
            new_template_key="hby_template_test",
            source_template_key="source",
            detail_source_template_key="source",
            new_art_set_id=None,
            art_set_source_id=None,
            new_age_range_key=None,
            age_range_source_key=None,
            new_initial_ceo_key=None,
            initial_ceo_source_key=None,
            template_overrides={"subtype": "3k_general_water"},
            detail_overrides={},
            art_set_overrides={},
            art_overrides={},
            age_range_overrides={},
            spawn_event="campaign_start",
        )

        script = _campaign_start_spawn_script([clone])
        self.assertIsNotNone(script)
        self.assertIn("hby_template_test", script or "")
        self.assertIn('turn_number >= item.turn', script or "")
        self.assertIn("local function hby_mtu_character_exists(template_key)", script or "")
        self.assertIn("pcall(function() return cm:query_model():character_for_template(template_key) end)", script or "")
        self.assertNotIn("trigger_incident", script or "")
        self.assertIn("local function hby_mtu_direct_spawn_character", script or "")
        self.assertIn("spawn_character_subtype_template_in_faction", script or "")
        self.assertNotIn("create_character_from_template", script or "")
        self.assertIn("local function hby_mtu_prepare_spawned_character", script or "")
        self.assertIn("local function hby_mtu_preflight_spawn_state(faction_key)", script or "")
        self.assertIn("preflight locked generated character", script or "")
        self.assertIn("hby_mtu_preflight_spawn_state(faction_key)", script or "")
        self.assertIn("item.attempt_key", script or "")
        self.assertIn("generated character created", script or "")
        self.assertNotIn("waiting for DB spawn before fallback", script or "")
        self.assertNotIn("waiting for DB event spawn", script or "")
        self.assertIn("generated character spawn pending", script or "")
        self.assertIn("generated character spawn already attempted this turn", script or "")
        self.assertIn("move_to_faction_and_make_recruited", script or "")
        self.assertIn("generated character observed", script or "")
        self.assertIn("generated character spawn failed", script or "")
        self.assertIn("local function hby_mtu_faction_key(value)", script or "")
        self.assertIn("local faction_key = cm:get_local_faction()", script or "")
        self.assertNotIn("ok = true", script or "")
        self.assertIn("pcall(function() return cm:query_model():character_for_template(template_key) end)", script or "")
        self.assertNotIn("spawn_character_to_pool", script or "")
        self.assertNotIn("spawn_character_to_faction", script or "")
        self.assertNotIn("cm:spawn_character", script or "")
        self.assertIn("function hby_mtu_pack_editor_player_spawn", script or "")
        self.assertIn("hby_mtu_player_spawn_listener_registered", script or "")

    def test_campaign_script_applies_ceo_sets_after_spawn(self) -> None:
        clone = CharacterClone(
            new_template_key="hby_template_test",
            source_template_key="source",
            detail_source_template_key="source",
            new_art_set_id=None,
            art_set_source_id=None,
            new_age_range_key=None,
            age_range_source_key=None,
            new_initial_ceo_key=None,
            initial_ceo_source_key=None,
            template_overrides={"subtype": "3k_general_water"},
            detail_overrides={},
            art_set_overrides={},
            art_overrides={},
            age_range_overrides={},
            spawn_event="campaign_start",
            title_ceo_key="3k_main_ceo_career_historical_guan_yu",
            removable_title_ceo_keys=("3k_main_ceo_career_historical_generic_m_wood_general",),
            trait_ceo_keys=("trait_a",),
            removable_trait_ceo_keys=("trait_old",),
            equipment_ceo_keys=("equipment_a",),
            removable_equipment_ceo_keys=("equipment_old",),
        )

        script = _campaign_start_spawn_script([clone])

        self.assertIn(
            'remove_ceos = { "3k_main_ceo_career_historical_generic_m_wood_general", "trait_old" }',
            script or "",
        )
        self.assertIn(
            'title_ceo = "3k_main_ceo_career_historical_guan_yu"',
            script or "",
        )
        self.assertIn(
            'add_ceos = { "trait_a" }',
            script or "",
        )
        self.assertIn("hby_mtu_remove_ceo(ceo_manager, ceo_key)", script or "")
        self.assertIn("hby_mtu_add_ceo(ceo_manager, ceo_key)", script or "")
        self.assertIn("ceo_manager:add_ceos(ceo_key)", script or "")
        self.assertIn("ceo_manager:add_ceo(ceo_key)", script or "")
        self.assertIn("hby_mtu_set_character_title(character, modify_character, ceo_manager, item.title_ceo)", script or "")
        self.assertIn('local category_key = "3k_main_ceo_category_career"', script or "")
        self.assertIn("query_ceo_manager:all_ceos_for_category(category_key)", script or "")
        self.assertIn("if not applied then", script or "")
        self.assertIn("hby_mtu_pack_editor_ceo_sets_v6_", script or "")
        self.assertIn("hby_mtu_apply_ceo_sets()", script or "")
        self.assertIn("cm:force_add_ceo(cqi, ceo_key)", script or "")
        self.assertNotIn("force_add_trait", script or "")
        self.assertIn('equipment_ceos = { "equipment_a" }', script or "")
        self.assertIn('remove_ceos = { "equipment_old" }', script or "")
        self.assertIn("hby_mtu_add_ancillary_to_faction(faction_key, ceo_key)", script or "")
        self.assertIn("hby_mtu_force_equip_ancillary(character, modify_character, ceo_key)", script or "")
        self.assertIn("hby_mtu_pack_editor_equipment_v7_", script or "")
        self.assertIn("hby_mtu_pack_editor_equipment_grant_v7_", script or "")
        self.assertIn('grant_key = "hby_mtu_pack_editor_equipment_grant_v7_', script or "")
        self.assertIn("hby_mtu_apply_equipment_sets", script or "")
        self.assertIn("return #hby_mtu_equipment_characters == 0", script or "")
        self.assertIn("local grant_done = item.grant_key and cm:get_saved_value(item.grant_key)", script or "")
        self.assertIn("cm:set_saved_value(item.grant_key, true)", script or "")
        self.assertIn('output("MTU Pack Editor: enforced equipment set:', script or "")
        self.assertIn("cm:modify_character(character)", script or "")
        self.assertIn("cm:char_lookup_str(character)", script or "")
        self.assertIn("local function hby_mtu_character_lookup(character)", script or "")
        self.assertIn("cm:force_add_ancillary(lookup, ancillary_key, false, true)", script or "")
        self.assertIn("cm:force_equip_ancillary(lookup, ancillary_key, true)", script or "")
        self.assertIn("local function hby_mtu_modify_faction(faction_key)", script or "")
        self.assertIn("modify_faction:ceo_management()", script or "")
        self.assertIn("result ~= false", script or "")

    def test_equipment_set_materializes_custom_initial_ceo_chain(self) -> None:
        tables = {
            "ceo_initial_datas": [
                {"key": "source_initial", "_sourceTablePath": "db/ceo_initial_datas_tables/data__"},
            ],
            "ceo_initial_data_stages": [
                {"key": "source_stage", "_sourceTablePath": "db/ceo_initial_data_stages_tables/data__"},
            ],
            "ceo_initial_data_to_stages": [
                {
                    "ceo_initial_data": "source_initial",
                    "stage": "stage_a",
                    "initial_data_stage": "source_stage",
                    "_sourceTablePath": "db/ceo_initial_data_to_stages_tables/data__",
                },
            ],
            "ceo_initial_data_equipments": [
                {
                    "initial_data_stage": "source_stage",
                    "category": "weapon",
                    "slot_index": 0,
                    "target": "self",
                    "equipped_ceo": "old_weapon",
                    "auto_id": 1,
                    "_sourceTablePath": "db/ceo_initial_data_equipments_tables/data__",
                },
                {
                    "initial_data_stage": "source_stage",
                    "category": "armour",
                    "slot_index": 1,
                    "target": "self",
                    "equipped_ceo": "old_armour",
                    "auto_id": 2,
                    "_sourceTablePath": "db/ceo_initial_data_equipments_tables/data__",
                },
            ],
            "ceo_initial_data_active_ceos": [
                {
                    "initial_data_stage": "source_stage",
                    "active_ceo": "old_weapon",
                    "starting_points_delta": 1,
                    "auto_id": 3,
                    "_sourceTablePath": "db/ceo_initial_data_active_ceos_tables/data__",
                },
                {
                    "initial_data_stage": "source_stage",
                    "active_ceo": "old_armour",
                    "starting_points_delta": 1,
                    "auto_id": 4,
                    "_sourceTablePath": "db/ceo_initial_data_active_ceos_tables/data__",
                },
            ],
        }
        rows_by_table: dict[str, list[dict[str, object]]] = {}

        new_initial = delta_builder._materialize_equipment_initial_ceo(
            tables,
            {},
            {},
            rows_by_table,
            "source_initial",
            "hby_template_test",
            ("new_weapon", "new_armour"),
            ("old_weapon", "old_armour"),
        )

        self.assertTrue(str(new_initial).startswith("hby_mtu_ceo_initial_data_hby_template_test_"))
        detail_initials = rows_by_table["db/ceo_initial_datas_tables/data__"]
        self.assertEqual(detail_initials[0]["key"], new_initial)
        equipment_rows = rows_by_table["db/ceo_initial_data_equipments_tables/data__"]
        self.assertEqual({row["equipped_ceo"] for row in equipment_rows}, {"new_weapon", "new_armour"})
        self.assertTrue(all(row["initial_data_stage"] != "source_stage" for row in equipment_rows))
        active_rows = rows_by_table["db/ceo_initial_data_active_ceos_tables/data__"]
        self.assertEqual({row["active_ceo"] for row in active_rows}, {"new_weapon", "new_armour"})
        self.assertNotIn("old_weapon", {row["active_ceo"] for row in active_rows})

    def test_initial_ceo_materialization_keeps_copied_equipment_and_adds_selected_ceos(self) -> None:
        tables = {
            "ceo_initial_datas": [
                {"key": "source_initial", "_sourceTablePath": "db/ceo_initial_datas_tables/data__"},
            ],
            "ceo_initial_data_stages": [
                {"key": "source_stage", "_sourceTablePath": "db/ceo_initial_data_stages_tables/data__"},
            ],
            "ceo_initial_data_to_stages": [
                {
                    "ceo_initial_data": "source_initial",
                    "stage": "stage_a",
                    "initial_data_stage": "source_stage",
                    "_sourceTablePath": "db/ceo_initial_data_to_stages_tables/data__",
                },
            ],
            "ceo_initial_data_equipments": [
                {
                    "initial_data_stage": "source_stage",
                    "category": "weapon",
                    "slot_index": 0,
                    "target": "self",
                    "equipped_ceo": "old_weapon",
                    "auto_id": 1,
                    "_sourceTablePath": "db/ceo_initial_data_equipments_tables/data__",
                },
                {
                    "initial_data_stage": "source_stage",
                    "category": "armour",
                    "slot_index": 0,
                    "target": "self",
                    "equipped_ceo": "old_armour",
                    "auto_id": 2,
                    "_sourceTablePath": "db/ceo_initial_data_equipments_tables/data__",
                },
            ],
            "ceo_initial_data_active_ceos": [
                {
                    "initial_data_stage": "source_stage",
                    "active_ceo": "old_weapon",
                    "starting_points_delta": 1,
                    "auto_id": 3,
                    "_sourceTablePath": "db/ceo_initial_data_active_ceos_tables/data__",
                },
                {
                    "initial_data_stage": "source_stage",
                    "active_ceo": "old_armour",
                    "starting_points_delta": 1,
                    "auto_id": 4,
                    "_sourceTablePath": "db/ceo_initial_data_active_ceos_tables/data__",
                },
                {
                    "initial_data_stage": "source_stage",
                    "active_ceo": "old_title",
                    "starting_points_delta": 1,
                    "auto_id": 5,
                    "_sourceTablePath": "db/ceo_initial_data_active_ceos_tables/data__",
                },
                {
                    "initial_data_stage": "source_stage",
                    "active_ceo": "old_trait",
                    "starting_points_delta": 1,
                    "auto_id": 6,
                    "_sourceTablePath": "db/ceo_initial_data_active_ceos_tables/data__",
                },
            ],
        }
        rows_by_table: dict[str, list[dict[str, object]]] = {}

        delta_builder._materialize_equipment_initial_ceo(
            tables,
            {},
            {},
            rows_by_table,
            "source_initial",
            "hby_template_test",
            ("new_weapon",),
            ("old_weapon",),
            ("new_title", "new_trait"),
            ("old_title", "old_trait"),
        )

        equipment_rows = rows_by_table["db/ceo_initial_data_equipments_tables/data__"]
        self.assertEqual({row["equipped_ceo"] for row in equipment_rows}, {"new_weapon", "old_armour"})
        active_rows = rows_by_table["db/ceo_initial_data_active_ceos_tables/data__"]
        self.assertEqual(
            {row["active_ceo"] for row in active_rows},
            {"new_weapon", "old_armour", "new_title", "new_trait"},
        )

    def test_equipment_set_keeps_source_initial_when_stage_rows_are_missing(self) -> None:
        tables = {
            "ceo_initial_datas": [
                {"key": "source_initial", "_sourceTablePath": "db/ceo_initial_datas_tables/data__"},
            ],
        }
        rows_by_table: dict[str, list[dict[str, object]]] = {}
        source_dbs: dict[str, dict[str, object]] = {}

        new_initial = delta_builder._materialize_equipment_initial_ceo(
            tables,
            {},
            source_dbs,
            rows_by_table,
            "source_initial",
            "hby_template_schema",
            ("3k_main_ancillary_weapon_test", "3k_main_ancillary_mount_test"),
            (),
            ("3k_main_ceo_career_historical_lady_sun", "3k_main_ceo_trait_personality_direct"),
            (),
        )

        self.assertEqual(new_initial, "source_initial")
        self.assertEqual(source_dbs, {})
        self.assertEqual(rows_by_table, {})

    def test_equipment_kind_does_not_classify_mountains_accessory_as_mount(self) -> None:
        self.assertEqual(
            delta_builder._equipment_kind_from_ceo_key(
                "3k_main_ancillary_accessory_book_of_mountains_and_seas"
            ),
            "accessory",
        )
        self.assertEqual(
            delta_builder._equipment_kind_from_ceo_key("3k_main_ancillary_mount_red_stallion"),
            "mount",
        )

    def test_equipment_materialization_does_not_reuse_wrong_slot_category(self) -> None:
        tables = {
            "ceo_initial_datas": [
                {"key": "source_initial", "_sourceTablePath": "db/ceo_initial_datas_tables/data__"},
            ],
            "ceo_initial_data_stages": [
                {"key": "source_stage", "_sourceTablePath": "db/ceo_initial_data_stages_tables/data__"},
            ],
            "ceo_initial_data_to_stages": [
                {
                    "ceo_initial_data": "source_initial",
                    "stage": 1,
                    "initial_data_stage": "source_stage",
                    "_sourceTablePath": "db/ceo_initial_data_to_stages_tables/data__",
                },
            ],
            "ceo_initial_data_equipments": [
                {
                    "initial_data_stage": "source_stage",
                    "category": "3k_main_ceo_category_ancillary_mount",
                    "slot_index": 0,
                    "target": "3k_main_ceo_equipment_manager_type_character",
                    "equipped_ceo": "old_mount",
                    "auto_id": 1,
                    "_sourceTablePath": "db/ceo_initial_data_equipments_tables/data__",
                },
            ],
            "ceo_initial_data_active_ceos": [
                {
                    "initial_data_stage": "source_stage",
                    "active_ceo": "old_mount",
                    "starting_points_delta": 1,
                    "auto_id": 2,
                    "_sourceTablePath": "db/ceo_initial_data_active_ceos_tables/data__",
                },
            ],
        }
        rows_by_table: dict[str, list[dict[str, object]]] = {}

        delta_builder._materialize_equipment_initial_ceo(
            tables,
            {},
            {},
            rows_by_table,
            "source_initial",
            "hby_template_test",
            (
                "3k_main_ancillary_accessory_book_of_mountains_and_seas",
                "3k_main_ancillary_mount_red_stallion",
            ),
            ("old_mount",),
        )

        equipment_rows = rows_by_table["db/ceo_initial_data_equipments_tables/data__"]
        by_ceo = {row["equipped_ceo"]: row for row in equipment_rows}
        self.assertNotIn("3k_main_ancillary_accessory_book_of_mountains_and_seas", by_ceo)
        self.assertEqual(
            by_ceo["3k_main_ancillary_mount_red_stallion"]["category"],
            "3k_main_ceo_category_ancillary_mount",
        )

    def test_dependency_collection_accepts_materialized_equipment_initial_ceo(self) -> None:
        payload = {
            "tables": {
                "db/character_generation_templates_tables/_mtu_characters": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [{
                        "key": "source_template",
                        "art_set_override": "source_art",
                        "forename": "1",
                        "is_male": False,
                        "subtype": "3k_general_fire",
                        "spawn_age_range": "age",
                    }],
                },
                "db/character_generation_template_game_mode_details_tables/_mtu_characters": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [{
                        "character_generation_template": "source_template",
                        "game_mode": "historical",
                        "initial_ceos": "source_initial",
                        "retinue": "",
                        "attribute_set": "",
                        "skill_set_override": "",
                    }],
                },
                "db/ceo_initial_datas_tables/data__": {
                    "db": {"table": {"definition": {"fields": [{"name": "key"}]}, "table_data": [["source_initial"]]}},
                    "rows": [{"key": "source_initial"}],
                },
                "db/ceo_initial_data_stages_tables/data__": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [{"key": "source_stage"}],
                },
                "db/ceo_initial_data_to_stages_tables/data__": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [{
                        "ceo_initial_data": "source_initial",
                        "stage": 1,
                        "initial_data_stage": "source_stage",
                    }],
                },
                "db/ceo_initial_data_equipments_tables/data__": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [{
                        "initial_data_stage": "source_stage",
                        "category": "3k_main_ceo_category_ancillary_weapon",
                        "slot_index": 0,
                        "target": "3k_main_ceo_equipment_manager_type_character",
                        "equipped_ceo": "old_weapon",
                        "auto_id": 1,
                    }],
                },
                "db/ceo_initial_data_active_ceos_tables/data__": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [{
                        "initial_data_stage": "source_stage",
                        "active_ceo": "old_weapon",
                        "starting_points_delta": 1,
                        "auto_id": 2,
                    }],
                },
                "db/campaign_character_art_sets_tables/_mtu_characters": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [{"art_set_id": "source_art", "is_male": False}],
                },
                "db/campaign_character_arts_tables/_mtu_characters": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [{"art_set_id": "source_art", "age": 16, "has_come_of_age": True}],
                },
                "db/character_generation_spawn_age_ranges_tables/_mtu_characters": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [{"key": "age"}],
                },
                "db/names_tables/data__": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [{"id": "1"}],
                },
            },
            "loc": {},
            "assets": {},
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "materials.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            session = MaterialPackSession.open(path)

        clone = CharacterClone(
            new_template_key="hby_template_source_clone",
            source_template_key="source_template",
            detail_source_template_key="source_template",
            new_art_set_id="hby_art_source_clone",
            art_set_source_id="source_art",
            new_age_range_key=None,
            age_range_source_key=None,
            new_initial_ceo_key=None,
            initial_ceo_source_key=None,
            template_overrides={"subtype": "3k_general_fire"},
            detail_overrides={},
            art_set_overrides={},
            art_overrides={},
            age_range_overrides={},
            image_assets=[],
            equipment_ceo_keys=("new_weapon",),
            removable_equipment_ceo_keys=("old_weapon",),
        )
        rows_by_table = {}
        source_dbs = {}
        opened_pack_keys = {str(session.pack_path.resolve()): session.pack_key}

        _collect_character_clone_rows(session, [clone], source_dbs, rows_by_table, {}, [], opened_pack_keys)

        details = rows_by_table["db/character_generation_template_game_mode_details_tables/_mtu_characters"]
        generated_initial = str(details[0]["initial_ceos"])
        self.assertTrue(generated_initial.startswith("hby_mtu_ceo_initial_data_"))

        _collect_character_dependency_rows(session, [clone], source_dbs, rows_by_table, [], opened_pack_keys)
        equipment_rows = rows_by_table["db/ceo_initial_data_equipments_tables/data__"]
        self.assertIn("new_weapon", {row["equipped_ceo"] for row in equipment_rows})

    def test_campaign_script_can_apply_ceo_sets_without_spawn_entries(self) -> None:
        patch = CharacterPatch(
            template_key="patch_template",
            template_overrides={},
            detail_overrides={},
            title_ceo_key="3k_main_ceo_career_historical_lu_bu",
            trait_ceo_keys=("trait_a",),
            removable_trait_ceo_keys=("trait_old",),
        )

        script = _campaign_start_spawn_script([], [patch])

        self.assertIsNotNone(script)
        self.assertIn('template = "patch_template"', script or "")
        self.assertIn('title_ceo = "3k_main_ceo_career_historical_lu_bu"', script or "")
        self.assertIn('add_ceos = { "trait_a" }', script or "")
        self.assertIn("not hby_mtu_all_ceo_sets_done()", script or "")

    def test_campaign_script_keeps_background_ceos_out_of_runtime_title_slot(self) -> None:
        patch = CharacterPatch(
            template_key="patch_template",
            template_overrides={},
            detail_overrides={},
            title_ceo_key="bg_mtu_character_background_ma_yunlu",
            trait_ceo_keys=("trait_a",),
        )

        script = _campaign_start_spawn_script([], [patch])

        self.assertIsNotNone(script)
        self.assertIn('title_ceo = ""', script or "")
        self.assertIn('add_ceos = { "bg_mtu_character_background_ma_yunlu", "trait_a" }', script or "")

    def test_campaign_script_can_apply_equipment_without_spawn_or_trait_entries(self) -> None:
        patch = CharacterPatch(
            template_key="patch_template",
            template_overrides={},
            detail_overrides={},
            equipment_ceo_keys=("new_weapon", "new_mount"),
            removable_equipment_ceo_keys=("old_weapon",),
        )

        script = _campaign_start_spawn_script([], [patch])

        self.assertIsNotNone(script)
        self.assertIn('equipment_ceos = { "new_weapon", "new_mount" }', script or "")
        self.assertIn('remove_ceos = { "old_weapon" }', script or "")
        self.assertIn("not hby_mtu_all_equipment_sets_done()", script or "")
        self.assertIn("hby_mtu_apply_equipment_sets", script or "")
        self.assertIn("cm:force_equip_ancillary", script or "")
        self.assertIn("cm:force_add_ancillary", script or "")
        self.assertIn("local equipped = false", script or "")
        self.assertNotIn("local ceo_added = false", script or "")
        self.assertIn("return equipped", script or "")
        self.assertIn("return #hby_mtu_equipment_characters == 0", script or "")
        self.assertNotIn("if not cm:get_saved_value(item.save_key) then\n            hby_mtu_apply_equipment_set(item, faction_key)", script or "")
        self.assertNotIn("hby_mtu_force_add_character_ceo(character, modify_character, ceo_manager, ancillary_key)", script or "")

    def test_lua_ceo_key_list_rejects_object_sentinel_values(self) -> None:
        self.assertEqual(
            _unique_lua_ceo_keys([
                {"key": "trait_from_object"},
                "[object Object]",
                "trait_from_object",
                "trait_b",
            ]),
            ["trait_from_object", "trait_b"],
        )

    def test_delayed_join_still_emits_lua_spawner(self) -> None:
        clone = CharacterClone(
            new_template_key="hby_template_test",
            source_template_key="source",
            detail_source_template_key="source",
            new_art_set_id=None,
            art_set_source_id=None,
            new_age_range_key=None,
            age_range_source_key=None,
            new_initial_ceo_key=None,
            initial_ceo_source_key=None,
            template_overrides={"subtype": "3k_general_water", "min_spawn_round": 3},
            detail_overrides={},
            art_set_overrides={},
            art_overrides={},
            age_range_overrides={},
            spawn_event="delayed_join",
        )

        script = _campaign_start_spawn_script([clone])
        self.assertIsNotNone(script)
        self.assertIn("hby_template_test", script or "")

    def test_spawn_entries_use_separate_incidents_per_turn_group(self) -> None:
        immediate = CharacterClone(
            new_template_key="hby_template_now",
            source_template_key="source",
            detail_source_template_key="source",
            new_art_set_id=None,
            art_set_source_id=None,
            new_age_range_key=None,
            age_range_source_key=None,
            new_initial_ceo_key=None,
            initial_ceo_source_key=None,
            template_overrides={"subtype": "3k_general_fire"},
            detail_overrides={},
            art_set_overrides={},
            art_overrides={},
            age_range_overrides={},
            spawn_event="campaign_start",
        )
        delayed = CharacterClone(
            new_template_key="hby_template_later",
            source_template_key="source",
            detail_source_template_key="source",
            new_art_set_id=None,
            art_set_source_id=None,
            new_age_range_key=None,
            age_range_source_key=None,
            new_initial_ceo_key=None,
            initial_ceo_source_key=None,
            template_overrides={"subtype": "3k_general_water", "min_spawn_round": 5},
            detail_overrides={},
            art_set_overrides={},
            art_overrides={},
            age_range_overrides={},
            spawn_event="delayed_join",
        )

        entries = _spawn_entries_for_clones([immediate, delayed])

        self.assertEqual(len(entries), 2)
        self.assertNotEqual(entries[0]["incident"], entries[1]["incident"])
        for entry in entries:
            self.assertEqual({item["category"] for item in entry["incidents"]}, {"historical"})
            self.assertEqual(len(entry["incidents"]), 1)
        self.assertTrue(all(str(entry["saveKey"]).startswith("hby_mtu_pack_editor_player_spawn_v7_") for entry in entries))
        self.assertTrue(all(str(entry["attemptKey"]).startswith("hby_mtu_pack_editor_player_spawn_attempt_v7_") for entry in entries))
        self.assertEqual(entries[1]["turn"], 5)

    def test_spawn_entries_share_incident_for_same_turn_group(self) -> None:
        first = CharacterClone(
            new_template_key="hby_template_first",
            source_template_key="source",
            detail_source_template_key="source",
            new_art_set_id=None,
            art_set_source_id=None,
            new_age_range_key=None,
            age_range_source_key=None,
            new_initial_ceo_key=None,
            initial_ceo_source_key=None,
            template_overrides={"subtype": "3k_general_fire"},
            detail_overrides={},
            art_set_overrides={},
            art_overrides={},
            age_range_overrides={},
            spawn_event="campaign_start",
        )
        second = CharacterClone(
            new_template_key="hby_template_second",
            source_template_key="source",
            detail_source_template_key="source",
            new_art_set_id=None,
            art_set_source_id=None,
            new_age_range_key=None,
            age_range_source_key=None,
            new_initial_ceo_key=None,
            initial_ceo_source_key=None,
            template_overrides={"subtype": "3k_general_water"},
            detail_overrides={},
            art_set_overrides={},
            art_overrides={},
            age_range_overrides={},
            spawn_event="campaign_start",
        )

        entries = _spawn_entries_for_clones([first, second])

        self.assertEqual(entries[0]["incident"], entries[1]["incident"])
        self.assertEqual(entries[0]["incidents"], entries[1]["incidents"])

    def test_event_spawn_clone_keeps_positive_weight_and_preserves_source_age_without_input(self) -> None:
        payload = {
            "tables": {
                "db/character_generation_templates_tables/_mtu_characters": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [{
                        "key": "source_template",
                        "art_set_override": "source_art",
                        "spawn_age_range": "source_age",
                        "forename": "1",
                        "weight": 0,
                        "can_be_born": True,
                        "subtype": "3k_general_fire",
                    }],
                },
                "db/character_generation_template_game_mode_details_tables/_mtu_characters": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [{
                        "character_generation_template": "source_template",
                        "game_mode": "historical",
                        "retinue": "source_retinue",
                    }],
                },
                "db/campaign_character_art_sets_tables/_mtu_characters": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [{"art_set_id": "source_art"}],
                },
                "db/campaign_character_arts_tables/_mtu_characters": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [{"art_set_id": "source_art", "age": "adult", "has_come_of_age": True}],
                },
                "db/character_generation_spawn_age_ranges_tables/_mtu_characters": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [{
                        "key": "source_age",
                        "birth_year": 189,
                        "min_spawn_year": 205,
                        "max_spawn_year": 194,
                        "min_spawn_year_round": 0,
                        "max_spawn_year_round": 999,
                        "min_random_age": 18,
                        "max_random_age": 50,
                        "min_age_for_birth_year": 0,
                        "max_age_for_birth_year": 80,
                        "has_valid_birth_year": True,
                    }],
                },
                "db/names_tables/data__": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [{"id": "1"}],
                },
            },
            "loc": {},
            "assets": {},
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "materials.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            session = MaterialPackSession.open(path)

        rows_by_table = {}
        source_dbs = {}
        loc_rows = {}
        _collect_character_clone_rows(
            session,
            [CharacterClone(
                new_template_key="hby_template_event",
                source_template_key="source_template",
                detail_source_template_key="source_template",
                new_art_set_id=None,
                art_set_source_id=None,
                new_age_range_key=None,
                age_range_source_key=None,
                new_initial_ceo_key=None,
                initial_ceo_source_key=None,
                template_overrides={"subtype": "3k_general_fire", "spawn_age_range": "source_age"},
                detail_overrides={},
                art_set_overrides={},
                art_overrides={},
                age_range_overrides={},
                spawn_event="campaign_start",
            )],
            source_dbs,
            rows_by_table,
            loc_rows,
        )

        template = rows_by_table["db/character_generation_templates_tables/_mtu_characters"][0]
        self.assertEqual(template["weight"], delta_builder.SPAWN_EVENT_TEMPLATE_WEIGHT)
        self.assertIs(template["can_be_born"], False)
        self.assertEqual(template["spawn_age_range"], "source_age")
        self.assertNotIn("db/character_generation_spawn_age_ranges_tables/_mtu_characters", rows_by_table)

    def test_character_clone_preserves_source_voiceover_actor(self) -> None:
        payload = {
            "tables": {
                "db/character_generation_templates_tables/_mtu_characters": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [{
                        "key": "source_template",
                        "art_set_override": "source_art",
                        "spawn_age_range": "source_age",
                        "forename": "1",
                        "is_male": False,
                        "subtype": "3k_general_fire",
                        "voiceover_actor": "vo_actor_group_named_lady_sun",
                    }],
                },
                "db/character_generation_template_game_mode_details_tables/_mtu_characters": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [{
                        "character_generation_template": "source_template",
                        "game_mode": "historical",
                        "retinue": "source_retinue",
                    }],
                },
                "db/campaign_character_art_sets_tables/_mtu_characters": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [{"art_set_id": "source_art", "is_male": False}],
                },
                "db/campaign_character_arts_tables/_mtu_characters": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [{"art_set_id": "source_art", "age": "adult", "has_come_of_age": True}],
                },
                "db/character_generation_spawn_age_ranges_tables/_mtu_characters": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [{"key": "source_age"}],
                },
                "db/names_tables/data__": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [{"id": "1"}],
                },
            },
            "loc": {},
            "assets": {},
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "materials.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            session = MaterialPackSession.open(path)

        rows_by_table = {}
        source_dbs = {}
        loc_rows = {}
        _collect_character_clone_rows(
            session,
            [CharacterClone(
                new_template_key="hby_template_lady_sun_clone",
                source_template_key="source_template",
                detail_source_template_key="source_template",
                new_art_set_id="hby_art_lady_sun_clone",
                art_set_source_id="source_art",
                new_age_range_key=None,
                age_range_source_key=None,
                new_initial_ceo_key=None,
                initial_ceo_source_key=None,
                template_overrides={},
                detail_overrides={},
                art_set_overrides={},
                art_overrides={},
                age_range_overrides={},
            )],
            source_dbs,
            rows_by_table,
            loc_rows,
        )

        template = rows_by_table["db/character_generation_templates_tables/_mtu_characters"][0]
        self.assertIs(template["is_male"], False)
        self.assertEqual(template["voiceover_actor"], "vo_actor_group_named_lady_sun")

    def test_character_clone_display_name_uses_source_name_column(self) -> None:
        payload = {
            "tables": {
                "db/character_generation_templates_tables/_mtu_characters": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [{
                        "key": "source_template",
                        "forename": 0,
                        "family_name": "family_name_id",
                        "clan_name": 0,
                        "other_name": 0,
                        "art_set_override": "source_art",
                        "subtype": "3k_general_earth",
                    }],
                },
                "db/character_generation_template_game_mode_details_tables/_mtu_characters": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [{
                        "character_generation_template": "source_template",
                        "game_mode": "historical",
                        "retinue": "source_retinue",
                    }],
                },
                "db/campaign_character_art_sets_tables/_mtu_characters": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [{"art_set_id": "source_art"}],
                },
                "db/campaign_character_arts_tables/_mtu_characters": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [{"art_set_id": "source_art", "age": "adult", "has_come_of_age": True}],
                },
                "db/character_generation_spawn_age_ranges_tables/_mtu_characters": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [{"key": "age"}],
                },
                "db/names_tables/data__": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [{
                        "id": "family_name_id",
                        "names_group": 221,
                        "type": 1,
                        "gender": 1,
                        "frequency": 0,
                    }],
                },
            },
            "loc": {},
            "assets": {},
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "materials.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            session = MaterialPackSession.open(path)

        rows_by_table = {}
        source_dbs = {}
        loc_rows = {}
        _collect_character_clone_rows(
            session,
            [CharacterClone(
                new_template_key="hby_template_family_name",
                source_template_key="source_template",
                detail_source_template_key="source_template",
                new_art_set_id=None,
                art_set_source_id=None,
                new_age_range_key=None,
                age_range_source_key=None,
                new_initial_ceo_key=None,
                initial_ceo_source_key=None,
                template_overrides={"subtype": "3k_general_earth"},
                detail_overrides={},
                art_set_overrides={},
                art_overrides={},
                age_range_overrides={},
                display_name="새 이름",
            )],
            source_dbs,
            rows_by_table,
            loc_rows,
        )

        template = rows_by_table["db/character_generation_templates_tables/_mtu_characters"][0]
        self.assertEqual(template["forename"], 0)
        self.assertNotEqual(template["family_name"], 0)
        self.assertEqual(template["clan_name"], 0)
        self.assertEqual(template["other_name"], 0)
        name_id = str(template["family_name"])
        name_row = rows_by_table["db/names_tables/data__"][0]
        self.assertEqual(name_row["id"], name_id)
        self.assertEqual(name_row["type"], 1)
        self.assertEqual(name_row["gender"], 1)
        self.assertEqual(name_row["frequency"], 1)
        self.assertEqual(loc_rows[f"names_name_{name_id}"], "새 이름")

    def test_spawn_incident_tables_emit_notification_payload_only(self) -> None:
        clone = CharacterClone(
            new_template_key="hby_template_spawn",
            source_template_key="source",
            detail_source_template_key="source",
            new_art_set_id=None,
            art_set_source_id=None,
            new_age_range_key=None,
            age_range_source_key=None,
            new_initial_ceo_key=None,
            initial_ceo_source_key=None,
            template_overrides={"subtype": "3k_general_fire"},
            detail_overrides={},
            art_set_overrides={},
            art_overrides={},
            age_range_overrides={},
            spawn_event="campaign_start",
        )
        written_tables: dict[str, list[dict[str, object]]] = {}

        def db(fields: list[str], rows: list[list[object]]) -> dict[str, object]:
            return {
                "table": {
                    "definition": {"fields": [{"name": field} for field in fields]},
                    "table_data": rows,
                }
            }

        def source_db_for(path: str) -> dict[str, object]:
            if "incidents_tables" in path:
                return db(
                    ["generate", "key", "ui_image", "prioritised", "event_category"],
                    [[False, "source_incident", "3k_event_giving_jobs", False, "historical"]],
                )
            if "cdir_events_incident_payloads_tables" in path:
                return db(
                    ["id", "incident_key", "payload_key", "value", "target_key"],
                    [
                        [1, "source_incident", "SPAWN_AGENT_OFF_MAP", "", "default"],
                        [2, "source_incident", "LOCATED", "FACTION", "default"],
                    ],
                )
            if "cdir_events_incident_option_junctions_tables" in path:
                return db(
                    ["id", "incident_key", "option_key", "value", "target"],
                    [[1, "source_incident", "CND_FIRST_ROUND", "0", "default"]],
                )
            raise AssertionError(path)

        def capture_db(_session: object, _target_key: str, path: str, _source_db: dict[str, object], rows: list[dict[str, object]]) -> None:
            written_tables[path] = rows

        with (
            patch.object(delta_builder, "_open_pack_reusing_existing", return_value="legacy"),
            patch.object(delta_builder, "_decode_db_from_pack", side_effect=lambda _session, _key, path: source_db_for(path)),
            patch.object(delta_builder, "_write_db_file", side_effect=capture_db),
            patch.object(delta_builder, "_write_loc_file"),
        ):
            written_count = delta_builder._write_spawn_incident_tables(object(), "target", [clone])

        self.assertEqual(written_count, 3)
        incident_rows = written_tables["db/incidents_tables/event"]
        spawn_entry = _spawn_entries_for_clones([clone])[0]
        incident_keys = {item["key"] for item in spawn_entry["incidents"]}
        self.assertEqual({row["key"] for row in incident_rows}, incident_keys)
        self.assertEqual({row["event_category"] for row in incident_rows}, {"historical"})
        self.assertEqual(spawn_entry["incident"], next(item["key"] for item in spawn_entry["incidents"] if item["category"] == "historical"))
        for incident in incident_rows:
            self.assertIs(incident["generate"], True)
            self.assertEqual(incident["ui_image"], "3k_event_ready_for_duty")
        option_rows = written_tables["db/cdir_events_incident_option_junctions_tables/event"]
        self.assertEqual(len(option_rows), 6)
        for incident_key in incident_keys:
            option_values = {
                row["option_key"]: row["value"]
                for row in option_rows
                if row["incident_key"] == incident_key
            }
            self.assertEqual(option_values["CND_FIRST_ROUND"], "0")
            self.assertEqual(option_values["GEN_CND_SELF"], "")
            self.assertEqual(option_values["GEN_TARGET_FACTION"], "")
            self.assertEqual(option_values["CND_UNIQUE"], "")
            self.assertEqual(option_values["VAR_CHANCE"], "50000")
            self.assertEqual(option_values["CND_LAST_ROUND"], "100")
        payloads = written_tables["db/cdir_events_incident_payloads_tables/event"]
        self.assertEqual(len(payloads), 1)
        for incident_key in incident_keys:
            self.assertFalse(
                any(
                    row["incident_key"] == incident_key and row["payload_key"] == "SPAWN_AGENT_OFF_MAP"
                    for row in payloads
                )
            )
            self.assertTrue(
                any(
                    row["incident_key"] == incident_key and row["payload_key"] == "LOCATED" and row["value"] == "FACTION"
                    for row in payloads
                )
            )

    def test_build_delta_pack_emits_incident_spawn_tables_and_observer_lua(self) -> None:
        payload = {
            "tables": {
                "db/character_generation_templates_tables/_mtu_characters": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [{
                        "key": "source_template",
                        "art_set_override": "source_art",
                        "spawn_age_range": "source_age",
                        "forename": "1",
                    }],
                },
                "db/character_generation_template_game_mode_details_tables/_mtu_characters": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [{
                        "character_generation_template": "source_template",
                        "game_mode": "historical",
                    }],
                },
                "db/campaign_character_art_sets_tables/_mtu_characters": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [{"art_set_id": "source_art"}],
                },
                "db/campaign_character_arts_tables/_mtu_characters": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [{"art_set_id": "source_art", "age": 16, "has_come_of_age": True}],
                },
                "db/character_generation_spawn_age_ranges_tables/_mtu_characters": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [{"key": "source_age"}],
                },
                "db/names_tables/data__": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [{"id": "1"}],
                },
            },
            "loc": {},
            "assets": {},
        }

        class FakeClient:
            def send(self, _command: object) -> dict[str, object]:
                return {}

        class FakeWriterSession:
            client = FakeClient()
            pack_key = "writer"
            decoded_db_by_path: dict[str, dict[str, object]] = {}

            def __init__(self, path: Path) -> None:
                self.pack_path = path

            def list_files(self) -> list[str]:
                return []

            def list_loc_files(self) -> list[str]:
                return []

        clone = CharacterClone(
            new_template_key="hby_template_spawn",
            source_template_key="source_template",
            detail_source_template_key="source_template",
            new_art_set_id=None,
            art_set_source_id=None,
            new_age_range_key=None,
            age_range_source_key=None,
            new_initial_ceo_key=None,
            initial_ceo_source_key=None,
            template_overrides={"subtype": "3k_general_fire"},
            detail_overrides={},
            art_set_overrides={},
            art_overrides={},
            age_range_overrides={},
            spawn_event="campaign_start",
        )
        recipe = Recipe(mod_name="test", character_clones=[clone])

        with tempfile.TemporaryDirectory() as tmp:
            material_path = Path(tmp) / "materials.json"
            material_path.write_text(json.dumps(payload), encoding="utf-8")
            source_session = MaterialPackSession.open(material_path)
            output_path = Path(tmp) / "out.pack"
            output_path.write_bytes(b"pack")
            writer_session = FakeWriterSession(Path(tmp) / "writer.pack")

            with (
                patch.object(delta_builder, "_new_delta_pack", return_value="target"),
                patch.object(delta_builder, "_write_db_file"),
                patch.object(delta_builder, "_write_lua_text_file") as write_lua,
                patch.object(delta_builder, "_write_loc_file"),
                patch.object(delta_builder, "_copy_image_assets", return_value=0),
                patch.object(delta_builder, "_write_spawn_incident_tables", return_value=3) as write_incidents,
            ):
                messages = delta_builder.build_delta_pack_from_materials(
                    source_session,
                    writer_session,  # type: ignore[arg-type]
                    recipe,
                    output_path,
                    [],
                )

        write_incidents.assert_called_once()
        self.assertEqual(write_lua.call_count, len(delta_builder.CAMPAIGN_SPAWN_SCRIPT_PATHS))
        written_lua_paths = {call.args[2] for call in write_lua.call_args_list}
        self.assertEqual(written_lua_paths, set(delta_builder.CAMPAIGN_SPAWN_SCRIPT_PATHS))
        self.assertIn("3 spawn incident table(s)", str(messages[-1]["message"]))

    def test_material_land_unit_clone_uses_source_table_path(self) -> None:
        payload = {
            "tables": {
                "db/land_units_tables/_mtu_characters_custom_battles_land_units": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [],
                },
                "db/land_units_tables/data__": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [{
                        "key": "3k_main_hero_generic_water_strategist",
                        "charge_bonus": 34,
                        "dismounted_charge_bonus": 10,
                        "dismounted_melee_attack": 11,
                        "melee_attack": 12,
                        "melee_defence": 13,
                        "morale": 40,
                        "primary_ammo": 13,
                    }],
                },
            },
            "loc": {},
            "assets": {},
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "materials.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            session = MaterialPackSession.open(path)

        rows_by_table = {}
        source_dbs = {}
        created = _collect_land_unit_clone_rows(
            session,
            Recipe(
                mod_name="test",
                equipment_stat_patches=[],
                land_unit_clones=[LandUnitClone(
                    source_key="3k_main_hero_generic_water_strategist",
                    new_key="hby_land_unit_test",
                    overrides={
                        "charge_bonus": 99,
                        "dismounted_charge_bonus": 44,
                        "dismounted_melee_attack": 55,
                        "melee_attack": 66,
                        "melee_defence": 77,
                        "morale": 88,
                    },
                )],
                skill_set_clones=[],
                attribute_set_clones=[],
                age_range_clones=[],
                character_clones=[],
                character_patches=[],
                raw={},
            ),
            source_dbs,
            rows_by_table,
        )

        self.assertEqual(created, 1)
        row = rows_by_table["db/land_units_tables/data__"][0]
        self.assertEqual(row["key"], "hby_land_unit_test")
        self.assertEqual(row["charge_bonus"], 99)
        self.assertEqual(row["dismounted_charge_bonus"], 44)
        self.assertEqual(row["dismounted_melee_attack"], 55)
        self.assertEqual(row["melee_attack"], 66)
        self.assertEqual(row["melee_defence"], 77)
        self.assertEqual(row["morale"], 88)

    def test_material_land_unit_clone_can_create_retinue_chain(self) -> None:
        payload = {
            "tables": {
                "db/land_units_tables/_mtu_characters_custom_battles_land_units": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [],
                },
                "db/land_units_tables/data__": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [{"key": "source_unit", "charge_bonus": 34, "morale": 40, "primary_ammo": 13}],
                },
                "db/main_units_tables/data__": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [{"unit": "source_unit", "land_unit": "source_unit"}],
                },
                "db/retinues_tables/data__": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [{"key": "source_retinue", "template": "template_all"}],
                },
                "db/retinue_slot_initial_units_tables/data__": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [
                        {"retinue": "source_retinue", "slot_index": 0, "initial_unit_record": "source_unit", "campaign": ""},
                        {"retinue": "source_retinue", "slot_index": 1, "initial_unit_record": "support_unit", "campaign": ""},
                    ],
                },
                "db/cai_retinues_to_aspects_tables/data__": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [{"retinue": "source_retinue", "aspect": "water", "weight": 1}],
                },
            },
            "loc": {},
            "assets": {},
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "materials.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            session = MaterialPackSession.open(path)

        rows_by_table = {}
        source_dbs = {}
        _collect_land_unit_clone_rows(
            session,
            Recipe(
                mod_name="test",
                equipment_stat_patches=[],
                land_unit_clones=[LandUnitClone(
                    source_key="source_unit",
                    new_key="hby_land_unit_test",
                    overrides={"charge_bonus": 99},
                    source_retinue_key="source_retinue",
                    new_retinue_key="hby_retinue_test",
                )],
                skill_set_clones=[],
                attribute_set_clones=[],
                age_range_clones=[],
                character_clones=[],
                character_patches=[],
                raw={},
            ),
            source_dbs,
            rows_by_table,
        )

        self.assertEqual(rows_by_table["db/retinues_tables/data__"][0]["key"], "hby_retinue_test")
        main_unit = rows_by_table["db/main_units_tables/data__"][0]
        self.assertEqual(main_unit["unit"], "hby_land_unit_test")
        self.assertEqual(main_unit["land_unit"], "hby_land_unit_test")
        slots = rows_by_table["db/retinue_slot_initial_units_tables/data__"]
        self.assertEqual(slots[0]["retinue"], "hby_retinue_test")
        self.assertEqual(slots[0]["initial_unit_record"], "hby_land_unit_test")
        self.assertEqual(slots[1]["initial_unit_record"], "support_unit")
        self.assertEqual(rows_by_table["db/cai_retinues_to_aspects_tables/data__"][0]["retinue"], "hby_retinue_test")
        self.assertNotIn("db/land_units_to_unit_abilites_junctions_tables/data__", rows_by_table)

    def test_material_land_unit_clone_can_link_new_armour_type(self) -> None:
        payload = {
            "tables": {
                "db/unit_armour_types_tables/data__": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [{"key": "source_armour", "armour_value": 40, "audio_type": "Segmented_Light"}],
                },
                "db/land_units_tables/data__": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [{"key": "source_unit", "armour": "source_armour", "charge_bonus": 34, "morale": 40, "primary_ammo": 13}],
                },
                "db/main_units_tables/data__": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [{"unit": "source_unit", "land_unit": "source_unit"}],
                },
                "db/retinues_tables/data__": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [{"key": "source_retinue", "template": "template_all"}],
                },
                "db/retinue_slot_initial_units_tables/data__": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [{"retinue": "source_retinue", "slot_index": 0, "initial_unit_record": "source_unit", "campaign": ""}],
                },
            },
            "loc": {},
            "assets": {},
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "materials.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            session = MaterialPackSession.open(path)

        rows_by_table = {}
        source_dbs = {}
        delta_builder._collect_armour_type_clone_rows(
            session,
            [ArmourTypeClone(
                source_key="source_armour",
                new_key="hby_armour_test",
                overrides={"armour_value": 80, "audio_type": "Segmented_Heavy"},
            )],
            source_dbs,
            rows_by_table,
        )
        _collect_land_unit_clone_rows(
            session,
            Recipe(
                mod_name="test",
                equipment_stat_patches=[],
                land_unit_clones=[LandUnitClone(
                    source_key="source_unit",
                    new_key="hby_land_unit_test",
                    overrides={"armour": "hby_armour_test"},
                    source_retinue_key="source_retinue",
                    new_retinue_key="hby_retinue_test",
                )],
                skill_set_clones=[],
                attribute_set_clones=[],
                age_range_clones=[],
                character_clones=[],
                character_patches=[],
                raw={},
            ),
            source_dbs,
            rows_by_table,
        )

        armour_row = rows_by_table["db/unit_armour_types_tables/data__"][0]
        self.assertEqual(armour_row["key"], "hby_armour_test")
        self.assertEqual(armour_row["armour_value"], 80)
        land_unit_row = rows_by_table["db/land_units_tables/data__"][0]
        self.assertEqual(land_unit_row["key"], "hby_land_unit_test")
        self.assertEqual(land_unit_row["armour"], "hby_armour_test")

    def test_material_land_unit_clone_creates_fallback_retinue_slot(self) -> None:
        payload = {
            "tables": {
                "db/land_units_tables/data__": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [{"key": "source_unit", "charge_bonus": 34, "morale": 40, "primary_ammo": 13}],
                },
                "db/main_units_tables/data__": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [],
                },
                "db/retinues_tables/data__": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [{"key": "source_retinue", "template": "template_all"}],
                },
                "db/retinue_slot_initial_units_tables/data__": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [],
                },
            },
            "loc": {},
            "assets": {},
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "materials.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            session = MaterialPackSession.open(path)

        rows_by_table = {}
        _collect_land_unit_clone_rows(
            session,
            Recipe(
                mod_name="test",
                equipment_stat_patches=[],
                land_unit_clones=[LandUnitClone(
                    source_key="source_unit",
                    new_key="hby_land_unit_test",
                    overrides={"morale": 88},
                    source_retinue_key="source_retinue",
                    new_retinue_key="hby_retinue_test",
                )],
                skill_set_clones=[],
                attribute_set_clones=[],
                age_range_clones=[],
                character_clones=[],
                character_patches=[],
                raw={},
            ),
            {},
            rows_by_table,
        )

        slot = rows_by_table["db/retinue_slot_initial_units_tables/data__"][0]
        self.assertEqual(slot["retinue"], "hby_retinue_test")
        self.assertEqual(slot["slot_index"], 0)
        self.assertEqual(slot["initial_unit_record"], "hby_land_unit_test")

    def test_material_character_clone_creates_dedicated_art_and_both_mode_details(self) -> None:
        payload = {
            "tables": {
                "db/character_generation_templates_tables/_mtu_characters": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [{"key": "source_template", "art_set_override": "source_art", "forename": "1"}],
                },
                "db/character_generation_template_game_mode_details_tables/_mtu_characters": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [
                        {
                            "character_generation_template": "source_template",
                            "game_mode": "historical",
                            "retinue": "source_retinue",
                            "skill_set_override": "source_unique_skillset",
                        },
                        {
                            "character_generation_template": "source_template",
                            "game_mode": "romance",
                            "retinue": "source_retinue",
                            "skill_set_override": "source_unique_skillset",
                        },
                    ],
                },
                "db/campaign_character_art_sets_tables/_mtu_characters": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [{"art_set_id": "image_art"}],
                },
                "db/campaign_character_arts_tables/_mtu_characters": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [{
                        "art_set_id": "image_art",
                        "age": "adult",
                        "is_female": True,
                        "has_come_of_age": True,
                        "portrait": "old_image/",
                        "card": "old_image",
                        "uniform": "old_uniform",
                    }],
                },
                "db/character_generation_spawn_age_ranges_tables/_mtu_characters": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [{"key": "age"}],
                },
                "db/names_tables/data__": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [{"id": "1"}],
                },
            },
            "loc": {},
            "assets": {},
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "materials.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            session = MaterialPackSession.open(path)

        rows_by_table = {}
        source_dbs = {}
        loc_rows = {}
        _collect_character_clone_rows(
            session,
            [CharacterClone(
                new_template_key="hby_template_new",
                source_template_key="source_template",
                detail_source_template_key="source_template",
                new_art_set_id="hby_art_new",
                art_set_source_id="image_art",
                new_age_range_key=None,
                age_range_source_key=None,
                new_initial_ceo_key=None,
                initial_ceo_source_key=None,
                template_overrides={"art_set_override": "image_art"},
                detail_overrides={
                    "historical": {"retinue": "hby_retinue_new"},
                    "romance": {"retinue": "hby_retinue_new"},
                },
                art_set_overrides={},
                art_overrides={"portrait": "hby_template_new/", "card": "hby_template_new", "uniform": "new_uniform"},
                age_range_overrides={},
                display_name="새 장수",
                image_assets=[],
            )],
            source_dbs,
            rows_by_table,
            loc_rows,
        )

        template = rows_by_table["db/character_generation_templates_tables/_mtu_characters"][0]
        self.assertEqual(template["art_set_override"], "hby_art_new")
        details = rows_by_table["db/character_generation_template_game_mode_details_tables/_mtu_characters"]
        self.assertEqual({row["game_mode"] for row in details}, {"historical", "romance"})
        self.assertTrue(all(row["retinue"] == "hby_retinue_new" for row in details))
        art = rows_by_table["db/campaign_character_arts_tables/_mtu_characters"][0]
        self.assertEqual(art["art_set_id"], "hby_art_new")
        self.assertEqual(art["portrait"], "hby_template_new/")
        self.assertEqual(art["card"], "hby_template_new")
        self.assertEqual(art["uniform"], "new_uniform")

    def test_material_character_clone_fills_missing_romance_detail_from_historical(self) -> None:
        payload = {
            "tables": {
                "db/character_generation_templates_tables/_mtu_characters": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [{"key": "source_template", "art_set_override": "source_art", "forename": "1"}],
                },
                "db/character_generation_template_game_mode_details_tables/_mtu_characters": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [{
                        "character_generation_template": "source_template",
                        "game_mode": "historical",
                        "retinue": "source_retinue",
                        "attribute_set": "source_attribute",
                        "skill_set_override": "source_skillset",
                        "initial_ceos": "source_initial",
                    }],
                },
                "db/campaign_character_art_sets_tables/_mtu_characters": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [{"art_set_id": "source_art"}],
                },
                "db/campaign_character_arts_tables/_mtu_characters": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [{"art_set_id": "source_art", "age": "adult", "has_come_of_age": True}],
                },
                "db/character_generation_spawn_age_ranges_tables/_mtu_characters": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [{"key": "age"}],
                },
                "db/names_tables/data__": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [{"id": "1"}],
                },
            },
            "loc": {},
            "assets": {},
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "materials.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            session = MaterialPackSession.open(path)

        rows_by_table = {}
        source_dbs = {}
        _collect_character_clone_rows(
            session,
            [CharacterClone(
                new_template_key="hby_template_new",
                source_template_key="source_template",
                detail_source_template_key="source_template",
                new_art_set_id="hby_art_new",
                art_set_source_id="source_art",
                new_age_range_key=None,
                age_range_source_key=None,
                new_initial_ceo_key=None,
                initial_ceo_source_key=None,
                template_overrides={},
                detail_overrides={
                    "romance": {
                        "retinue": "romance_retinue",
                        "skill_set_override": "romance_skillset",
                    },
                },
                art_set_overrides={},
                art_overrides={},
                age_range_overrides={},
                image_assets=[],
            )],
            source_dbs,
            rows_by_table,
            {},
        )

        details = rows_by_table["db/character_generation_template_game_mode_details_tables/_mtu_characters"]
        by_mode = {row["game_mode"]: row for row in details}
        self.assertEqual(set(by_mode), {"historical", "romance"})
        self.assertEqual(by_mode["historical"]["retinue"], "source_retinue")
        self.assertEqual(by_mode["historical"]["skill_set_override"], "source_skillset")
        self.assertEqual(by_mode["romance"]["retinue"], "romance_retinue")
        self.assertEqual(by_mode["romance"]["skill_set_override"], "romance_skillset")
        self.assertEqual(by_mode["romance"]["attribute_set"], "source_attribute")
        self.assertEqual(by_mode["romance"]["initial_ceos"], "source_initial")

    def test_material_character_clone_omits_child_art_rows_when_adult_art_exists(self) -> None:
        payload = {
            "tables": {
                "db/character_generation_templates_tables/_mtu_characters": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [{"key": "source_template", "art_set_override": "source_art", "forename": "1"}],
                },
                "db/character_generation_template_game_mode_details_tables/_mtu_characters": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [{"character_generation_template": "source_template", "game_mode": "historical"}],
                },
                "db/campaign_character_art_sets_tables/_mtu_characters": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [{"art_set_id": "source_art"}],
                },
                "db/campaign_character_arts_tables/_mtu_characters": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [
                        {"art_set_id": "source_art", "age": 0, "has_come_of_age": False, "portrait": "baby/", "card": "baby"},
                        {"art_set_id": "source_art", "age": 8, "has_come_of_age": False, "portrait": "child_03_male/", "card": "child_03_male"},
                        {"art_set_id": "source_art", "age": 16, "has_come_of_age": True, "portrait": "adult/", "card": "adult"},
                    ],
                },
                "db/character_generation_spawn_age_ranges_tables/_mtu_characters": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [{"key": "age"}],
                },
                "db/names_tables/data__": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [{"id": "1"}],
                },
            },
            "loc": {},
            "assets": {},
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "materials.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            session = MaterialPackSession.open(path)

        rows_by_table = {}
        source_dbs = {}
        _collect_character_clone_rows(
            session,
            [CharacterClone(
                new_template_key="hby_template_new",
                source_template_key="source_template",
                detail_source_template_key="source_template",
                new_art_set_id="hby_art_new",
                art_set_source_id="source_art",
                new_age_range_key=None,
                age_range_source_key=None,
                new_initial_ceo_key=None,
                initial_ceo_source_key=None,
                template_overrides={},
                detail_overrides={},
                art_set_overrides={},
                art_overrides={"portrait": "hby_adult/", "card": "hby_adult"},
                age_range_overrides={},
                image_assets=[],
            )],
            source_dbs,
            rows_by_table,
            {},
        )

        art_rows = rows_by_table["db/campaign_character_arts_tables/_mtu_characters"]
        self.assertEqual(1, len(art_rows))
        self.assertEqual("hby_art_new", art_rows[0]["art_set_id"])
        self.assertEqual("hby_adult/", art_rows[0]["portrait"])
        self.assertEqual("hby_adult", art_rows[0]["card"])
        self.assertNotIn("baby", {row.get("card") for row in art_rows})
        self.assertNotIn("child_03_male", {row.get("card") for row in art_rows})

    def test_material_character_clone_copies_frontend_character_ceos_to_new_template(self) -> None:
        payload = {
            "tables": {
                "db/character_generation_templates_tables/data__": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [{"key": "3k_main_template_historical_guan_yu_hero_wood", "art_set_override": "source_art", "forename": "1"}],
                },
                "db/character_generation_template_game_mode_details_tables/data__": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [{"character_generation_template": "3k_main_template_historical_guan_yu_hero_wood", "game_mode": "historical"}],
                },
                "db/frontend_character_ceos_tables/data__": {
                    "db": {
                        "table": {
                            "table_name": "data__",
                            "definition": {
                                "fields": [
                                    {"name": "ceo"},
                                    {"name": "frontend_character"},
                                    {"name": "reason"},
                                    {"name": "threshold_points"},
                                ],
                            },
                            "table_data": [
                                ["3k_main_ceo_trait_personality_fraternal", "3k_main_template_historical_guan_yu_hero_wood", "trait", 1],
                            ],
                        },
                    },
                    "rows": [
                        {
                            "ceo": "3k_main_ceo_trait_personality_fraternal",
                            "frontend_character": "3k_main_template_historical_guan_yu_hero_wood",
                            "reason": "trait",
                            "threshold_points": 1,
                        },
                        {
                            "ceo": "3k_main_ceo_trait_personality_honourable",
                            "frontend_character": "3k_main_template_historical_guan_yu_hero_wood",
                            "reason": "trait",
                            "threshold_points": 1,
                        },
                    ],
                },
                "db/campaign_character_art_sets_tables/data__": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [{"art_set_id": "source_art"}],
                },
                "db/campaign_character_arts_tables/data__": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [{"art_set_id": "source_art", "age": 16, "has_come_of_age": True}],
                },
                "db/character_generation_spawn_age_ranges_tables/data__": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [{"key": "age"}],
                },
                "db/names_tables/data__": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [{"id": "1"}],
                },
            },
            "loc": {},
            "assets": {},
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "materials.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            session = MaterialPackSession.open(path)

        rows_by_table = {}
        source_dbs = {}
        _collect_character_clone_rows(
            session,
            [CharacterClone(
                new_template_key="hby_template_guan_yu_clone",
                source_template_key="3k_main_template_historical_guan_yu_hero_wood",
                detail_source_template_key="3k_main_template_historical_guan_yu_hero_wood",
                new_art_set_id="hby_art_guan_yu_clone",
                art_set_source_id="source_art",
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
            source_dbs,
            rows_by_table,
            {},
        )

        rows = rows_by_table["db/frontend_character_ceos_tables/_mtu_characters_ceo"]
        self.assertEqual(
            {row["ceo"] for row in rows},
            {
                "3k_main_ceo_trait_personality_fraternal",
                "3k_main_ceo_trait_personality_honourable",
            },
        )
        self.assertEqual({row["frontend_character"] for row in rows}, {"hby_template_guan_yu_clone"})
        self.assertIn("db/frontend_character_ceos_tables/_mtu_characters_ceo", source_dbs)

    def test_material_character_clone_writes_new_art_rows_to_mtu_table(self) -> None:
        payload = {
            "tables": {
                "db/character_generation_templates_tables/!!ironic_addon_korea_leader_fix": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [{"key": "source_template", "art_set_override": "source_art", "forename": "1"}],
                },
                "db/character_generation_template_game_mode_details_tables/!!ironic_addon_korea_leader_fix": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [{"character_generation_template": "source_template", "game_mode": "historical"}],
                },
                "db/campaign_character_art_sets_tables/!!ironic_addon_korea": {
                    "db": {"table": {"table_name": "!!ironic_addon_korea", "definition": {"fields": []}, "table_data": []}},
                    "rows": [{"art_set_id": "source_art"}],
                },
                "db/campaign_character_arts_tables/!!ironic_addon_korea": {
                    "db": {"table": {"table_name": "!!ironic_addon_korea", "definition": {"fields": []}, "table_data": []}},
                    "rows": [{"art_set_id": "source_art", "age": 16, "has_come_of_age": True, "portrait": "old/", "card": "old"}],
                },
                "db/character_generation_spawn_age_ranges_tables/_mtu_characters": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [{"key": "age"}],
                },
                "db/names_tables/data__": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [{"id": "1"}],
                },
            },
            "loc": {},
            "assets": {},
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "materials.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            session = MaterialPackSession.open(path)

        source_dbs = {}
        rows_by_table = {}
        _collect_character_clone_rows(
            session,
            [CharacterClone(
                new_template_key="hby_template_new",
                source_template_key="source_template",
                detail_source_template_key="source_template",
                new_art_set_id="hby_art_new",
                art_set_source_id="source_art",
                new_age_range_key=None,
                age_range_source_key=None,
                new_initial_ceo_key=None,
                initial_ceo_source_key=None,
                template_overrides={},
                detail_overrides={},
                art_set_overrides={},
                art_overrides={"portrait": "hby_image/", "card": "hby_image"},
                age_range_overrides={},
                image_assets=[],
            )],
            source_dbs,
            rows_by_table,
            {},
        )

        art_rows = rows_by_table["db/campaign_character_arts_tables/_mtu_characters"]
        self.assertEqual(art_rows[0]["art_set_id"], "hby_art_new")
        self.assertEqual(art_rows[0]["portrait"], "hby_image/")
        self.assertNotIn("db/campaign_character_arts_tables/!!ironic_addon_korea", rows_by_table)
        self.assertEqual(source_dbs["db/campaign_character_art_sets_tables/_mtu_characters"]["table"]["table_name"], "_mtu_characters")
        self.assertEqual(source_dbs["db/campaign_character_arts_tables/_mtu_characters"]["table"]["table_name"], "_mtu_characters")

    def test_material_character_clone_rejects_custom_initial_ceo_key(self) -> None:
        payload = {
            "tables": {
                "db/character_generation_templates_tables/_mtu_characters": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [{"key": "source_template", "art_set_override": "source_art", "forename": "1"}],
                },
                "db/character_generation_template_game_mode_details_tables/_mtu_characters": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [{
                        "character_generation_template": "source_template",
                        "game_mode": "historical",
                        "initial_ceos": "3k_main_ceo_initial_data_character_historical_gogukcheon",
                    }],
                },
                "db/ceo_initial_datas_tables/_mtu_characters_ceo": {
                    "db": {"table": {"definition": {"fields": [{"name": "key"}]}, "table_data": [["3k_main_ceo_initial_data_character_historical_gogukcheon"]]}},
                    "rows": [{"key": "3k_main_ceo_initial_data_character_historical_gogukcheon"}],
                },
                "db/campaign_character_art_sets_tables/_mtu_characters": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [{"art_set_id": "source_art"}],
                },
                "db/campaign_character_arts_tables/_mtu_characters": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [{"art_set_id": "source_art", "age": "adult", "has_come_of_age": True}],
                },
                "db/character_generation_spawn_age_ranges_tables/_mtu_characters": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [{"key": "age"}],
                },
                "db/names_tables/data__": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [{"id": "1"}],
                },
            },
            "loc": {},
            "assets": {},
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "materials.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            session = MaterialPackSession.open(path)

        rows_by_table = {}
        source_dbs = {}
        with self.assertRaisesRegex(ValueError, "Creating new initial CEO keys is not supported"):
            _collect_character_clone_rows(
                session,
                [CharacterClone(
                    new_template_key="hby_template_new",
                    source_template_key="source_template",
                    detail_source_template_key="source_template",
                    new_art_set_id=None,
                    art_set_source_id=None,
                    new_age_range_key=None,
                    age_range_source_key=None,
                    new_initial_ceo_key="hby_initial_ceo_new",
                    initial_ceo_source_key="3k_main_ceo_initial_data_character_historical_gogukcheon",
                    template_overrides={},
                    detail_overrides={},
                    art_set_overrides={},
                    art_overrides={},
                    age_range_overrides={},
                    image_assets=[],
                )],
                source_dbs,
                rows_by_table,
                {},
            )

    def test_material_character_clone_reuses_source_initial_ceo_key(self) -> None:
        payload = {
            "tables": {
                "db/character_generation_templates_tables/_mtu_characters": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [{"key": "source_template", "art_set_override": "source_art", "forename": "1"}],
                },
                "db/character_generation_template_game_mode_details_tables/_mtu_characters": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [
                        {
                            "character_generation_template": "source_template",
                            "game_mode": "historical",
                            "initial_ceos": "3k_main_ceo_initial_data_character_historical_records_source",
                        },
                        {
                            "character_generation_template": "source_template",
                            "game_mode": "romance",
                            "initial_ceos": "3k_main_ceo_initial_data_character_historical_romance_source",
                        },
                    ],
                },
                "db/ceo_initial_datas_tables/data__": {
                    "db": {"table": {"definition": {"fields": [{"name": "key"}]}, "table_data": [["3k_main_ceo_initial_data_character_historical_records_source"]]}},
                    "rows": [
                        {"key": "3k_main_ceo_initial_data_character_historical_records_source"},
                        {"key": "3k_main_ceo_initial_data_character_historical_romance_source"},
                    ],
                },
                "db/campaign_character_art_sets_tables/_mtu_characters": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [{"art_set_id": "source_art"}],
                },
                "db/campaign_character_arts_tables/_mtu_characters": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [{"art_set_id": "source_art", "age": "adult", "has_come_of_age": True}],
                },
                "db/character_generation_spawn_age_ranges_tables/_mtu_characters": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [{"key": "age"}],
                },
                "db/names_tables/data__": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [{"id": "1"}],
                },
            },
            "loc": {},
            "assets": {},
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "materials.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            session = MaterialPackSession.open(path)

        clone = CharacterClone(
            new_template_key="hby_template_new",
            source_template_key="source_template",
            detail_source_template_key="source_template",
            new_art_set_id="hby_art_new",
            art_set_source_id="source_art",
            new_age_range_key=None,
            age_range_source_key=None,
            new_initial_ceo_key=None,
            initial_ceo_source_key=None,
            template_overrides={"subtype": "3k_general_fire"},
            detail_overrides={},
            art_set_overrides={},
            art_overrides={},
            age_range_overrides={},
            image_assets=[],
        )
        rows_by_table = {}
        source_dbs = {}
        loc_rows = {}
        opened_pack_keys = {str(session.pack_path.resolve()): session.pack_key}

        _collect_character_clone_rows(session, [clone], source_dbs, rows_by_table, loc_rows)

        details = rows_by_table["db/character_generation_template_game_mode_details_tables/_mtu_characters"]
        by_mode = {row["game_mode"]: row["initial_ceos"] for row in details}
        self.assertEqual(by_mode["historical"], "3k_main_ceo_initial_data_character_historical_records_source")
        self.assertEqual(by_mode["romance"], "3k_main_ceo_initial_data_character_historical_romance_source")

    def test_material_character_clone_uses_explicit_changed_initial_ceo_override(self) -> None:
        payload = {
            "tables": {
                "db/character_generation_templates_tables/_mtu_characters": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [{"key": "source_template", "art_set_override": "source_art", "forename": "1"}],
                },
                "db/character_generation_template_game_mode_details_tables/_mtu_characters": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [{
                        "character_generation_template": "source_template",
                        "game_mode": "historical",
                        "initial_ceos": "3k_main_ceo_initial_data_character_historical_source",
                    }],
                },
                "db/ceo_initial_datas_tables/data__": {
                    "db": {"table": {"definition": {"fields": [{"name": "key"}]}, "table_data": []}},
                    "rows": [
                        {"key": "3k_main_ceo_initial_data_character_historical_source"},
                        {"key": "3k_main_ceo_initial_data_character_historical_changed_title"},
                    ],
                },
                "db/campaign_character_art_sets_tables/_mtu_characters": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [{"art_set_id": "source_art"}],
                },
                "db/campaign_character_arts_tables/_mtu_characters": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [{"art_set_id": "source_art", "age": 16, "has_come_of_age": True}],
                },
                "db/character_generation_spawn_age_ranges_tables/_mtu_characters": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [{"key": "age"}],
                },
                "db/names_tables/data__": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [{"id": "1"}],
                },
            },
            "loc": {},
            "assets": {},
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "materials.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            session = MaterialPackSession.open(path)

        rows_by_table = {}
        source_dbs = {}
        _collect_character_clone_rows(
            session,
            [CharacterClone(
                new_template_key="hby_template_new",
                source_template_key="source_template",
                detail_source_template_key="source_template",
                new_art_set_id="hby_art_new",
                art_set_source_id="source_art",
                new_age_range_key=None,
                age_range_source_key=None,
                new_initial_ceo_key=None,
                initial_ceo_source_key=None,
                template_overrides={"subtype": "3k_general_fire"},
                detail_overrides={
                    "historical": {
                        "initial_ceos": "3k_main_ceo_initial_data_character_historical_changed_title",
                    },
                },
                art_set_overrides={},
                art_overrides={},
                age_range_overrides={},
                image_assets=[],
            )],
            source_dbs,
            rows_by_table,
            {},
        )

        details = rows_by_table["db/character_generation_template_game_mode_details_tables/_mtu_characters"]
        self.assertEqual(
            details[0]["initial_ceos"],
            "3k_main_ceo_initial_data_character_historical_changed_title",
        )

    def test_material_character_clone_keeps_title_initial_when_selected_title_has_no_stage_chain(self) -> None:
        payload = {
            "tables": {
                "db/character_generation_templates_tables/_mtu_characters": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [{"key": "source_template", "art_set_override": "source_art", "forename": "1"}],
                },
                "db/character_generation_template_game_mode_details_tables/_mtu_characters": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [{
                        "character_generation_template": "source_template",
                        "game_mode": "historical",
                        "initial_ceos": "3k_main_ceo_initial_data_character_historical_source",
                    }],
                },
                "db/ceo_initial_datas_tables/data__": {
                    "db": {"table": {"definition": {"fields": [{"name": "key"}]}, "table_data": []}},
                    "rows": [
                        {"key": "3k_main_ceo_initial_data_character_historical_source"},
                        {"key": "3k_main_ceo_initial_data_character_historical_guan_yu"},
                    ],
                },
                "db/campaign_character_art_sets_tables/_mtu_characters": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [{"art_set_id": "source_art"}],
                },
                "db/campaign_character_arts_tables/_mtu_characters": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [{"art_set_id": "source_art", "age": 16, "has_come_of_age": True}],
                },
                "db/character_generation_spawn_age_ranges_tables/_mtu_characters": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [{"key": "age"}],
                },
                "db/names_tables/data__": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [{"id": "1"}],
                },
            },
            "loc": {},
            "assets": {},
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "materials.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            session = MaterialPackSession.open(path)

        rows_by_table = {}
        source_dbs = {}
        _collect_character_clone_rows(
            session,
            [CharacterClone(
                new_template_key="hby_template_new",
                source_template_key="source_template",
                detail_source_template_key="source_template",
                new_art_set_id="hby_art_new",
                art_set_source_id="source_art",
                new_age_range_key=None,
                age_range_source_key=None,
                new_initial_ceo_key=None,
                initial_ceo_source_key=None,
                template_overrides={"subtype": "3k_general_wood"},
                detail_overrides={},
                art_set_overrides={},
                art_overrides={},
                age_range_overrides={},
                image_assets=[],
                title_ceo_key="3k_main_ceo_career_historical_guan_yu",
            )],
            source_dbs,
            rows_by_table,
            {},
        )

        details = rows_by_table["db/character_generation_template_game_mode_details_tables/_mtu_characters"]
        self.assertEqual(details[0]["initial_ceos"], "3k_main_ceo_initial_data_character_historical_source")
        self.assertNotIn("db/ceo_initial_data_active_ceos_tables/data__", rows_by_table)
        initial_rows = rows_by_table["db/ceo_initial_datas_tables/data__"]
        self.assertIn(details[0]["initial_ceos"], {row["key"] for row in initial_rows})

    def test_material_character_clone_embeds_selected_title_traits_and_keeps_equipment_for_lua(self) -> None:
        selected_title = "3k_main_ceo_career_historical_lady_sun"
        selected_initial = "3k_main_ceo_initial_data_character_historical_lady_sun"
        payload = {
            "tables": {
                "db/character_generation_templates_tables/_mtu_characters": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [{
                        "key": "source_template",
                        "art_set_override": "source_art",
                        "forename": "1",
                        "is_male": False,
                        "subtype": "3k_general_fire",
                    }],
                },
                "db/character_generation_template_game_mode_details_tables/_mtu_characters": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [{
                        "character_generation_template": "source_template",
                        "game_mode": "historical",
                        "initial_ceos": "source_initial",
                    }],
                },
                "db/ceo_initial_datas_tables/data__": {
                    "db": {"table": {"definition": {"fields": [{"name": "key"}]}, "table_data": []}},
                    "rows": [
                        {"key": "source_initial"},
                        {"key": selected_initial},
                    ],
                },
                "db/ceo_initial_data_stages_tables/data__": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [{"key": "title_stage"}],
                },
                "db/ceo_initial_data_to_stages_tables/data__": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [{
                        "ceo_initial_data": selected_initial,
                        "stage": 1,
                        "initial_data_stage": "title_stage",
                    }],
                },
                "db/ceo_initial_data_equipments_tables/data__": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [
                        {
                            "initial_data_stage": "title_stage",
                            "category": "weapon",
                            "slot_index": 0,
                            "target": "self",
                            "equipped_ceo": "old_weapon",
                            "auto_id": 1,
                        },
                        {
                            "initial_data_stage": "title_stage",
                            "category": "armour",
                            "slot_index": 0,
                            "target": "self",
                            "equipped_ceo": "old_armour",
                            "auto_id": 2,
                        },
                    ],
                },
                "db/ceo_initial_data_active_ceos_tables/data__": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [
                        {"initial_data_stage": "title_stage", "active_ceo": "old_weapon", "starting_points_delta": 1, "auto_id": 3},
                        {"initial_data_stage": "title_stage", "active_ceo": "old_armour", "starting_points_delta": 1, "auto_id": 4},
                        {"initial_data_stage": "title_stage", "active_ceo": "old_title", "starting_points_delta": 1, "auto_id": 5},
                        {"initial_data_stage": "title_stage", "active_ceo": "old_trait", "starting_points_delta": 1, "auto_id": 6},
                    ],
                },
                "db/campaign_character_art_sets_tables/_mtu_characters": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [{"art_set_id": "source_art"}],
                },
                "db/campaign_character_arts_tables/_mtu_characters": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [{"art_set_id": "source_art", "age": 16, "has_come_of_age": True}],
                },
                "db/character_generation_spawn_age_ranges_tables/_mtu_characters": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [{"key": "age"}],
                },
                "db/names_tables/data__": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [{"id": "1"}],
                },
            },
            "loc": {},
            "assets": {},
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "materials.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            session = MaterialPackSession.open(path)

        rows_by_table = {}
        source_dbs = {}
        _collect_character_clone_rows(
            session,
            [CharacterClone(
                new_template_key="hby_template_new",
                source_template_key="source_template",
                detail_source_template_key="source_template",
                new_art_set_id="hby_art_new",
                art_set_source_id="source_art",
                new_age_range_key=None,
                age_range_source_key=None,
                new_initial_ceo_key=None,
                initial_ceo_source_key=None,
                template_overrides={"subtype": "3k_general_fire"},
                detail_overrides={
                    "historical": {"initial_ceos": selected_initial},
                    "romance": {"initial_ceos": selected_initial},
                },
                art_set_overrides={},
                art_overrides={},
                age_range_overrides={},
                image_assets=[],
                title_ceo_key=None,
                removable_title_ceo_keys=("old_title",),
                trait_ceo_keys=("new_trait",),
                removable_trait_ceo_keys=("old_trait",),
                equipment_ceo_keys=("new_weapon",),
                removable_equipment_ceo_keys=("old_weapon",),
            )],
            source_dbs,
            rows_by_table,
            {},
        )

        details = rows_by_table["db/character_generation_template_game_mode_details_tables/_mtu_characters"]
        self.assertTrue(all(str(row["initial_ceos"]).startswith("hby_mtu_ceo_initial_data_") for row in details))
        equipment_rows = rows_by_table["db/ceo_initial_data_equipments_tables/data__"]
        self.assertEqual({row["equipped_ceo"] for row in equipment_rows}, {"new_weapon", "old_armour"})
        active_rows = rows_by_table["db/ceo_initial_data_active_ceos_tables/data__"]
        self.assertEqual(
            {row["active_ceo"] for row in active_rows},
            {"new_weapon", "old_armour", "new_trait"},
        )

    def test_material_character_clone_derives_named_initial_ceo_from_base_template_when_source_is_generic(self) -> None:
        payload = {
            "tables": {
                "db/character_generation_templates_tables/data__": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [{
                        "key": "3k_main_template_historical_guan_yu_hero_wood",
                        "art_set_override": "source_art",
                        "forename": "1",
                        "is_male": True,
                        "subtype": "3k_general_wood",
                    }],
                },
                "db/character_generation_template_game_mode_details_tables/data__": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [{
                        "character_generation_template": "3k_main_template_historical_guan_yu_hero_wood",
                        "game_mode": "historical",
                        "initial_ceos": "3k_main_ceo_initial_data_character_generic_m_wood_general",
                    }],
                },
                "db/ceo_initial_datas_tables/data__": {
                    "db": {"table": {"definition": {"fields": [{"name": "key"}]}, "table_data": []}},
                    "rows": [
                        {"key": "3k_main_ceo_initial_data_character_generic_m_wood_general"},
                        {"key": "3k_main_ceo_initial_data_character_historical_guan_yu"},
                    ],
                },
                "db/campaign_character_art_sets_tables/data__": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [{"art_set_id": "source_art", "is_male": True}],
                },
                "db/campaign_character_arts_tables/data__": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [{"art_set_id": "source_art", "age": 16, "has_come_of_age": True}],
                },
                "db/character_generation_spawn_age_ranges_tables/data__": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [{"key": "age"}],
                },
                "db/names_tables/data__": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [{"id": "1"}],
                },
            },
            "loc": {},
            "assets": {},
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "materials.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            session = MaterialPackSession.open(path)

        rows_by_table = {}
        source_dbs = {}
        _collect_character_clone_rows(
            session,
            [CharacterClone(
                new_template_key="hby_template_guan_yu_clone",
                source_template_key="3k_main_template_historical_guan_yu_hero_wood",
                detail_source_template_key="3k_main_template_historical_guan_yu_hero_wood",
                new_art_set_id="hby_art_guan_yu_clone",
                art_set_source_id="source_art",
                new_age_range_key=None,
                age_range_source_key=None,
                new_initial_ceo_key=None,
                initial_ceo_source_key=None,
                template_overrides={"subtype": "3k_general_wood"},
                detail_overrides={
                    "historical": {
                        "initial_ceos": "3k_main_ceo_initial_data_character_generic_m_wood_general",
                    },
                },
                art_set_overrides={},
                art_overrides={},
                age_range_overrides={},
                spawn_event="campaign_start",
                image_assets=[],
            )],
            source_dbs,
            rows_by_table,
            {},
        )

        details = rows_by_table["db/character_generation_template_game_mode_details_tables/data__"]
        self.assertEqual(details[0]["initial_ceos"], "3k_main_ceo_initial_data_character_historical_guan_yu")

    def test_initial_ceo_alias_resolves_lady_sun_shangxiang_to_lady_sun(self) -> None:
        tables = {
            "ceo_initial_datas": [
                {"key": "3k_main_ceo_initial_data_character_historical_lady_sun"},
            ],
            "character_generation_template_game_mode_details": [
                {
                    "character_generation_template": "3k_main_template_historical_lady_sun_shangxiang_hero_fire",
                    "game_mode": "historical",
                    "initial_ceos": "3k_main_ceo_initial_data_character_historical_lady_sun",
                },
            ],
        }

        resolved = delta_builder._resolve_non_generic_initial_ceo(
            tables,
            {"ceo_initial_datas": "db/ceo_initial_datas_tables/data__"},
            {},
            "3k_main_ceo_initial_data_character_historical_lady_sun_shangxiang",
            "3k_main_template_historical_lady_sun_shangxiang_hero_fire",
        )

        self.assertEqual(resolved, "3k_main_ceo_initial_data_character_historical_lady_sun")

    def test_initial_ceo_alias_resolves_empress_he_fire_to_dlc04_key(self) -> None:
        tables = {
            "ceo_initial_datas": [
                {"key": "3k_dlc04_ceo_initial_data_character_historical_non_deployable_empress_he_fire"},
            ],
        }

        resolved = delta_builder._resolve_non_generic_initial_ceo(
            tables,
            {"ceo_initial_datas": "db/ceo_initial_datas_tables/data__"},
            {},
            "3k_main_ceo_initial_data_character_historical_empress_he_fire",
            "3k_main_template_historical_zheng_jiang_hero_fire",
        )

        self.assertEqual(
            resolved,
            "3k_dlc04_ceo_initial_data_character_historical_non_deployable_empress_he_fire",
        )

    def test_initial_ceo_alias_resolves_non_deployable_prefix_generically(self) -> None:
        tables = {
            "ceo_initial_datas": [
                {"key": "3k_dlc04_ceo_initial_data_character_historical_non_deployable_example_fire"},
            ],
        }

        resolved = delta_builder._resolve_non_generic_initial_ceo(
            tables,
            {"ceo_initial_datas": "db/ceo_initial_datas_tables/data__"},
            {},
            "3k_main_ceo_initial_data_character_historical_example_fire",
            "3k_main_template_historical_other_hero_fire",
        )

        self.assertEqual(
            resolved,
            "3k_dlc04_ceo_initial_data_character_historical_non_deployable_example_fire",
        )

    def test_initial_ceo_alias_resolves_element_suffix_generically(self) -> None:
        tables = {
            "ceo_initial_datas": [
                {"key": "3k_dlc04_ceo_initial_data_character_historical_example"},
            ],
        }

        resolved = delta_builder._resolve_non_generic_initial_ceo(
            tables,
            {"ceo_initial_datas": "db/ceo_initial_datas_tables/data__"},
            {},
            "3k_main_ceo_initial_data_character_historical_example_fire",
            "3k_main_template_historical_other_hero_fire",
        )

        self.assertEqual(resolved, "3k_dlc04_ceo_initial_data_character_historical_example")

    def test_initial_ceo_alias_resolves_generic_match_from_internal_materials(self) -> None:
        material_key = "3k_dlc04_ceo_initial_data_character_historical_non_deployable_material_fire"
        payload = {
            "tables": {
                "db/ceo_initial_datas_tables/data__": {
                    "db": {
                        "table": {
                            "definition": {"fields": [{"name": "key"}]},
                            "table_data": [[material_key]],
                        },
                    },
                    "rows": [{"key": material_key}],
                },
            },
        }

        with tempfile.TemporaryDirectory() as tmp:
            material_path = Path(tmp) / "materials.json"
            material_path.write_text(json.dumps(payload), encoding="utf-8")
            with patch.object(delta_builder, "INTERNAL_MATERIALS_PATH", material_path):
                tables = {"ceo_initial_datas": []}
                source_dbs = {}
                resolved = delta_builder._resolve_non_generic_initial_ceo(
                    tables,
                    {"ceo_initial_datas": "db/ceo_initial_datas_tables/data__"},
                    source_dbs,
                    "3k_main_ceo_initial_data_character_historical_material_fire",
                    "3k_main_template_historical_other_hero_fire",
                )

        self.assertEqual(resolved, material_key)
        self.assertEqual(tables["ceo_initial_datas"][0]["key"], material_key)

    def test_initial_ceo_dependency_copy_normalizes_alias_from_internal_materials(self) -> None:
        material_key = "3k_dlc04_ceo_initial_data_character_historical_non_deployable_empress_he_fire"
        payload = {
            "tables": {
                "db/ceo_initial_datas_tables/data__": {
                    "db": {
                        "table": {
                            "definition": {"fields": [{"name": "key"}]},
                            "table_data": [[material_key]],
                        },
                    },
                    "rows": [{"key": material_key}],
                },
            },
        }

        with tempfile.TemporaryDirectory() as tmp:
            material_path = Path(tmp) / "materials.json"
            material_path.write_text(json.dumps(payload), encoding="utf-8")
            with patch.object(delta_builder, "INTERNAL_MATERIALS_PATH", material_path):
                tables = {"ceo_initial_datas": []}
                rows_by_table = {}
                delta_builder._copy_initial_ceo_dependency(
                    tables,
                    {"ceo_initial_datas": "db/ceo_initial_datas_tables/data__"},
                    {},
                    rows_by_table,
                    "3k_main_ceo_initial_data_character_historical_empress_he_fire",
                )

        self.assertEqual(tables["ceo_initial_datas"][0]["key"], material_key)
        self.assertEqual(
            rows_by_table["db/ceo_initial_datas_tables/data__"][0]["key"],
            material_key,
        )

    def test_player_spawn_character_clone_preserves_source_initial_ceo(self) -> None:
        payload = {
            "tables": {
                "db/character_generation_templates_tables/_mtu_characters": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [{
                        "key": "3k_mtu_template_historical_lady_guan_yinping_hero_wood",
                        "art_set_override": "source_art",
                        "forename": "1",
                        "is_male": False,
                        "subtype": "3k_general_wood",
                    }],
                },
                "db/character_generation_template_game_mode_details_tables/_mtu_characters": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [{
                        "character_generation_template": "3k_mtu_template_historical_lady_guan_yinping_hero_wood",
                        "game_mode": "historical",
                        "initial_ceos": "3k_mtu_ceo_initial_data_character_historical_lady_guan_yinping",
                    }],
                },
                "db/campaign_character_art_sets_tables/_mtu_characters": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [{"art_set_id": "source_art", "is_male": False}],
                },
                "db/campaign_character_arts_tables/_mtu_characters": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [{"art_set_id": "source_art", "age": 16, "has_come_of_age": True}],
                },
                "db/character_generation_spawn_age_ranges_tables/_mtu_characters": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [{"key": "age"}],
                },
                "db/names_tables/data__": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [{"id": "1"}],
                },
            },
            "loc": {},
            "assets": {},
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "materials.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            session = MaterialPackSession.open(path)

        rows_by_table = {}
        _collect_character_clone_rows(
            session,
            [CharacterClone(
                new_template_key="hby_template_guan_clone",
                source_template_key="3k_mtu_template_historical_lady_guan_yinping_hero_wood",
                detail_source_template_key="3k_mtu_template_historical_lady_guan_yinping_hero_wood",
                new_art_set_id="hby_art_guan_clone",
                art_set_source_id="source_art",
                new_age_range_key=None,
                age_range_source_key=None,
                new_initial_ceo_key=None,
                initial_ceo_source_key=None,
                template_overrides={"subtype": "3k_general_wood"},
                detail_overrides={},
                art_set_overrides={},
                art_overrides={},
                age_range_overrides={},
                spawn_event="campaign_start",
                image_assets=[],
            )],
            {},
            rows_by_table,
            {},
        )

        details = rows_by_table["db/character_generation_template_game_mode_details_tables/_mtu_characters"]
        self.assertEqual(
            details[0]["initial_ceos"],
            "3k_mtu_ceo_initial_data_character_historical_lady_guan_yinping",
        )

    def test_material_character_clone_preserves_historical_initial_ceo_when_gender_changes(self) -> None:
        payload = {
            "tables": {
                "db/character_generation_templates_tables/data__": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [{
                        "key": "source_template",
                        "art_set_override": "male_art",
                        "forename": "1",
                        "is_male": True,
                        "subtype": "3k_general_fire",
                    }],
                },
                "db/character_generation_template_game_mode_details_tables/data__": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [{
                        "character_generation_template": "source_template",
                        "game_mode": "historical",
                        "initial_ceos": "3k_main_ceo_initial_data_character_historical_dong_zhuo",
                    }],
                },
                "db/campaign_character_art_sets_tables/data__": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [
                        {"art_set_id": "male_art", "is_male": True},
                        {"art_set_id": "female_art", "is_male": False},
                    ],
                },
                "db/campaign_character_arts_tables/data__": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [
                        {"art_set_id": "male_art", "age": 16, "has_come_of_age": True},
                        {"art_set_id": "female_art", "age": 16, "has_come_of_age": True},
                    ],
                },
                "db/character_generation_spawn_age_ranges_tables/data__": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [{"key": "age"}],
                },
                "db/ceo_initial_datas_tables/data__": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [{
                        "key": "3k_main_ceo_initial_data_character_historical_dong_zhuo",
                        "ceo": "dong_zhuo_title",
                    }],
                },
                "db/names_tables/data__": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [{"id": "1"}],
                },
            },
            "loc": {},
            "assets": {},
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "materials.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            session = MaterialPackSession.open(path)

        rows_by_table = {}
        _collect_character_clone_rows(
            session,
            [CharacterClone(
                new_template_key="hby_template_new",
                source_template_key="source_template",
                detail_source_template_key="source_template",
                new_art_set_id="hby_art_new",
                art_set_source_id="female_art",
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
            {},
            rows_by_table,
            {},
        )
        _collect_character_dependency_rows(
            session,
            [CharacterClone(
                new_template_key="hby_template_new",
                source_template_key="source_template",
                detail_source_template_key="source_template",
                new_art_set_id="hby_art_new",
                art_set_source_id="female_art",
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
            {},
            rows_by_table,
            [],
            {str(session.pack_path.resolve()): session.pack_key},
        )

        template = rows_by_table["db/character_generation_templates_tables/data__"][0]
        self.assertFalse(template["is_male"])
        details = rows_by_table["db/character_generation_template_game_mode_details_tables/data__"]
        self.assertEqual(
            {row["initial_ceos"] for row in details},
            {"3k_main_ceo_initial_data_character_historical_dong_zhuo"},
        )
        ceo_rows = rows_by_table["db/ceo_initial_datas_tables/data__"]
        self.assertEqual(ceo_rows, [{"key": "3k_main_ceo_initial_data_character_historical_dong_zhuo", "ceo": "dong_zhuo_title"}])

    def test_material_character_clone_falls_back_when_image_only_art_set_is_used_as_model(self) -> None:
        payload = {
            "tables": {
                "db/character_generation_templates_tables/_mtu_characters": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [{"key": "source_template", "art_set_override": "source_art", "forename": "1"}],
                },
                "db/character_generation_template_game_mode_details_tables/_mtu_characters": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [{"character_generation_template": "source_template", "game_mode": "historical"}],
                },
                "db/campaign_character_art_sets_tables/_mtu_characters": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [{"art_set_id": "source_art"}],
                },
                "db/campaign_character_arts_tables/_mtu_characters": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [{"art_set_id": "source_art", "age": 16, "has_come_of_age": True, "portrait": "old/", "card": "old"}],
                },
                "db/character_generation_spawn_age_ranges_tables/_mtu_characters": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [{"key": "age"}],
                },
                "db/names_tables/data__": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [{"id": "1"}],
                },
            },
            "loc": {},
            "assets": {},
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "materials.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            session = MaterialPackSession.open(path)

        rows_by_table = {}
        source_dbs = {}
        _collect_character_clone_rows(
            session,
            [CharacterClone(
                new_template_key="hby_template_new",
                source_template_key="source_template",
                detail_source_template_key="source_template",
                new_art_set_id="hby_art_new",
                art_set_source_id="image_only_stale_virtual_set",
                new_age_range_key=None,
                age_range_source_key=None,
                new_initial_ceo_key=None,
                initial_ceo_source_key=None,
                template_overrides={},
                detail_overrides={},
                art_set_overrides={},
                art_overrides={"portrait": "hby_template_new/", "card": "hby_template_new"},
                age_range_overrides={},
                image_assets=[],
            )],
            source_dbs,
            rows_by_table,
            {},
        )

        template = rows_by_table["db/character_generation_templates_tables/_mtu_characters"][0]
        art = rows_by_table["db/campaign_character_arts_tables/_mtu_characters"][0]
        self.assertEqual(template["art_set_override"], "hby_art_new")
        self.assertEqual(art["art_set_id"], "hby_art_new")
        self.assertEqual(art["portrait"], "hby_template_new/")

    def test_material_character_patch_updates_existing_art_uniform_without_art_set_override(self) -> None:
        payload = {
            "tables": {
                "db/character_generation_templates_tables/_mtu_characters": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [{"key": "source_template", "art_set_override": "source_art", "forename": "1"}],
                },
                "db/character_generation_template_game_mode_details_tables/_mtu_characters": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [
                        {"character_generation_template": "source_template", "game_mode": "historical", "retinue": "source_retinue"},
                        {"character_generation_template": "source_template", "game_mode": "romance", "retinue": "source_retinue"},
                    ],
                },
                "db/campaign_character_art_sets_tables/_mtu_characters": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [{"art_set_id": "source_art"}],
                },
                "db/campaign_character_arts_tables/_mtu_characters": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [{
                        "art_set_id": "source_art",
                        "age": "adult",
                        "is_female": False,
                        "has_come_of_age": True,
                        "portrait": "source_image/",
                        "card": "source_image",
                        "uniform": "old_uniform",
                    }],
                },
                "db/character_generation_spawn_age_ranges_tables/_mtu_characters": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [{"key": "age"}],
                },
                "db/names_tables/_mtu_characters_names": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [{"id": "900"}],
                },
                "db/names_tables/data": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [{"id": "901"}],
                },
                "db/names_tables/data__": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [{"id": "1"}],
                },
            },
            "loc": {},
            "assets": {},
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "materials.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            session = MaterialPackSession.open(path)

        rows_by_table = {}
        source_dbs = {}
        loc_rows = {}
        _collect_character_patch_rows(
            session,
            [CharacterPatch(
                template_key="source_template",
                template_overrides={},
                detail_overrides={},
                display_name="new display",
                art_overrides={"uniform": "new_uniform"},
            )],
            source_dbs,
            rows_by_table,
            loc_rows,
        )

        template = rows_by_table["db/character_generation_templates_tables/_mtu_characters"][0]
        self.assertEqual(template["art_set_override"], "source_art")
        self.assertIn("db/names_tables/data__", rows_by_table)
        art = rows_by_table["db/campaign_character_arts_tables/_mtu_characters"][0]
        self.assertEqual(art["art_set_id"], "source_art")
        self.assertEqual(art["portrait"], "source_image/")
        self.assertEqual(art["card"], "source_image")
        self.assertEqual(art["uniform"], "new_uniform")

    def test_material_character_patch_fills_missing_romance_detail_from_historical(self) -> None:
        payload = {
            "tables": {
                "db/character_generation_templates_tables/_mtu_characters": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [{"key": "source_template", "art_set_override": "source_art", "forename": "1"}],
                },
                "db/character_generation_template_game_mode_details_tables/_mtu_characters": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [{
                        "character_generation_template": "source_template",
                        "game_mode": "historical",
                        "retinue": "source_retinue",
                        "skill_set_override": "source_skillset",
                    }],
                },
                "db/campaign_character_art_sets_tables/_mtu_characters": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [{"art_set_id": "source_art"}],
                },
                "db/campaign_character_arts_tables/_mtu_characters": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [{"art_set_id": "source_art", "age": 16, "has_come_of_age": True}],
                },
                "db/character_generation_spawn_age_ranges_tables/_mtu_characters": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [{"key": "age"}],
                },
                "db/names_tables/data__": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [{"id": "1"}],
                },
            },
            "loc": {},
            "assets": {},
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "materials.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            session = MaterialPackSession.open(path)

        rows_by_table = {}
        source_dbs = {}
        loc_rows = {}
        _collect_character_patch_rows(
            session,
            [CharacterPatch(
                template_key="source_template",
                template_overrides={},
                detail_overrides={"historical": {"retinue": "hby_retinue"}},
            )],
            source_dbs,
            rows_by_table,
            loc_rows,
        )

        details = rows_by_table["db/character_generation_template_game_mode_details_tables/_mtu_characters"]
        by_mode = {row["game_mode"]: row for row in details}
        self.assertEqual(set(by_mode), {"historical", "romance"})
        self.assertEqual(by_mode["historical"]["retinue"], "hby_retinue")
        self.assertEqual(by_mode["romance"]["retinue"], "hby_retinue")
        self.assertEqual(by_mode["romance"]["skill_set_override"], "source_skillset")

    def test_korea_addon_character_patch_updates_mod_and_ironic_template_rows(self) -> None:
        payload = {
            "tables": {
                "db/character_generation_templates_tables/!!ironic_addon_korea_leader_fix": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [
                        {
                            "key": "3k_mod_template_historical_gogukcheon_hero_fire",
                            "art_set_override": "3k_mod_art_set_historical_go_nammu_general",
                            "forename": "1",
                        },
                        {
                            "key": "ironic_template_historical_gogukcheon_hero_fire",
                            "art_set_override": "3k_mod_art_set_historical_go_nammu_general",
                            "forename": "1",
                        },
                    ],
                },
                "db/character_generation_template_game_mode_details_tables/!!ironic_addon_korea_leader_fix": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [
                        {
                            "character_generation_template": "3k_mod_template_historical_gogukcheon_hero_fire",
                            "game_mode": "historical",
                            "retinue": "source_retinue",
                        },
                        {
                            "character_generation_template": "ironic_template_historical_gogukcheon_hero_fire",
                            "game_mode": "historical",
                            "retinue": "source_retinue",
                        },
                    ],
                },
                "db/campaign_character_art_sets_tables/!!ironic_addon_korea_leader_fix": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [{"art_set_id": "3k_mod_art_set_historical_go_nammu_general"}],
                },
                "db/campaign_character_arts_tables/!!ironic_addon_korea": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [{
                        "art_set_id": "3k_mod_art_set_historical_go_nammu_general",
                        "age": "adult",
                        "is_female": False,
                        "has_come_of_age": True,
                        "portrait": "go_nammu/",
                        "card": "go_nammu",
                    }],
                },
                "db/names_tables/data__": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [{"id": "1"}],
                },
            },
            "loc": {},
            "assets": {},
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "materials.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            session = MaterialPackSession.open(path)

        rows_by_table = {}
        source_dbs = {}
        loc_rows = {}
        _collect_character_patch_rows(
            session,
            [CharacterPatch(
                template_key="3k_mod_template_historical_gogukcheon_hero_fire",
                template_overrides={},
                detail_overrides={"historical": {"retinue": "hby_retinue"}},
                art_overrides={"portrait": "hby_patch_go_nammu/", "card": "hby_patch_go_nammu"},
            )],
            source_dbs,
            rows_by_table,
            loc_rows,
        )

        templates = rows_by_table["db/character_generation_templates_tables/!!ironic_addon_korea_leader_fix"]
        self.assertEqual(
            {row["key"] for row in templates},
            {
                "3k_mod_template_historical_gogukcheon_hero_fire",
                "ironic_template_historical_gogukcheon_hero_fire",
            },
        )
        self.assertTrue(all(row["art_set_override"] == "3k_mod_art_set_historical_go_nammu_general" for row in templates))
        details = rows_by_table["db/character_generation_template_game_mode_details_tables/!!ironic_addon_korea_leader_fix"]
        self.assertEqual(
            {row["character_generation_template"] for row in details},
            {
                "3k_mod_template_historical_gogukcheon_hero_fire",
                "ironic_template_historical_gogukcheon_hero_fire",
            },
        )
        modes_by_template = defaultdict(set)
        for detail in details:
            modes_by_template[detail["character_generation_template"]].add(detail["game_mode"])
        self.assertEqual(
            modes_by_template,
            {
                "3k_mod_template_historical_gogukcheon_hero_fire": {"historical", "romance"},
                "ironic_template_historical_gogukcheon_hero_fire": {"historical", "romance"},
            },
        )
        self.assertTrue(all(row["retinue"] == "hby_retinue" for row in details))
        art = rows_by_table["db/campaign_character_arts_tables/!!ironic_addon_korea"][0]
        self.assertEqual(art["art_set_id"], "3k_mod_art_set_historical_go_nammu_general")
        self.assertEqual(art["portrait"], "hby_patch_go_nammu/")
        self.assertEqual(art["card"], "hby_patch_go_nammu")
        self.assertNotIn("db/campaign_character_arts_tables/_mtu_characters", rows_by_table)

    def test_korea_addon_character_patch_updates_all_related_art_sets(self) -> None:
        payload = {
            "tables": {
                "db/character_generation_templates_tables/!!ironic_addon_korea_leader_fix": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [
                        {
                            "key": "3k_mod_template_historical_chogo_hero_earth",
                            "art_set_override": "addon_chogo_art",
                            "forename": "1",
                        },
                        {
                            "key": "ironic_template_historical_chogo_hero_earth",
                            "art_set_override": "base_chogo_art",
                            "forename": "1",
                        },
                    ],
                },
                "db/character_generation_template_game_mode_details_tables/!!ironic_addon_korea_leader_fix": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [
                        {"character_generation_template": "3k_mod_template_historical_chogo_hero_earth", "game_mode": "historical"},
                        {"character_generation_template": "ironic_template_historical_chogo_hero_earth", "game_mode": "historical"},
                    ],
                },
                "db/campaign_character_art_sets_tables/!!ironic_addon_korea": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [{"art_set_id": "addon_chogo_art"}],
                },
                "db/campaign_character_art_sets_tables/ironic_culture_korea": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [{"art_set_id": "base_chogo_art"}],
                },
                "db/campaign_character_arts_tables/!!ironic_addon_korea": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [{
                        "art_set_id": "addon_chogo_art",
                        "age": "adult",
                        "has_come_of_age": True,
                        "portrait": "addon_old/",
                        "card": "addon_old",
                    }],
                },
                "db/campaign_character_arts_tables/ironic_culture_korea": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [{
                        "art_set_id": "base_chogo_art",
                        "age": "adult",
                        "has_come_of_age": True,
                        "portrait": "base_old/",
                        "card": "base_old",
                    }],
                },
                "db/names_tables/data__": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [{"id": "1"}],
                },
            },
            "loc": {},
            "assets": {},
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "materials.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            session = MaterialPackSession.open(path)

        rows_by_table = {}
        _collect_character_patch_rows(
            session,
            [CharacterPatch(
                template_key="3k_mod_template_historical_chogo_hero_earth",
                template_overrides={},
                detail_overrides={},
                art_overrides={"portrait": "hby_chogo/", "card": "hby_chogo"},
            )],
            {},
            rows_by_table,
            {},
        )

        addon_art = rows_by_table["db/campaign_character_arts_tables/!!ironic_addon_korea"][0]
        base_art = rows_by_table["db/campaign_character_arts_tables/ironic_culture_korea"][0]
        self.assertEqual(addon_art["portrait"], "hby_chogo/")
        self.assertEqual(addon_art["card"], "hby_chogo")
        self.assertEqual(base_art["portrait"], "hby_chogo/")
        self.assertEqual(base_art["card"], "hby_chogo")

    def test_material_stat_patch_uses_source_table_path(self) -> None:
        payload = {
            "tables": {
                "db/ceos_to_equipment_variants_tables/_mtu_characters_ceo_armours": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [],
                },
                "db/ceos_to_equipment_variants_tables/data__": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [{"ceos_key": "armour_ceo", "armour": "armour_row"}],
                },
                "db/unit_armour_types_tables/_mtu_characters_skills_abilities": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [],
                },
                "db/unit_armour_types_tables/data__": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [{"key": "armour_row", "armour_value": 40}],
                },
            },
            "loc": {},
            "assets": {},
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "materials.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            session = MaterialPackSession.open(path)

        rows_by_table = {}
        source_dbs = {}
        changed = _collect_stat_patch_rows(
            session,
            Recipe(
                mod_name="test",
                equipment_stat_patches=[StatPatch("armour_ceo", "armour", "armour_value", 77)],
                land_unit_clones=[],
                skill_set_clones=[],
                attribute_set_clones=[],
                age_range_clones=[],
                character_clones=[],
                character_patches=[],
                raw={},
            ),
            source_dbs,
            rows_by_table,
        )

        self.assertEqual(changed, 1)
        row = rows_by_table["db/unit_armour_types_tables/data__"][0]
        self.assertEqual(row["key"], "armour_row")
        self.assertEqual(row["armour_value"], 77)

    def test_material_stat_patch_can_target_unit_armour_key_directly(self) -> None:
        payload = {
            "tables": {
                "db/ceos_to_equipment_variants_tables/data__": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [{"ceos_key": "wrong_armour_ceo", "armour": "wrong_armour_row"}],
                },
                "db/unit_armour_types_tables/data__": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [
                        {"key": "actual_selected_armour", "armour_value": 40},
                        {"key": "wrong_armour_row", "armour_value": 10},
                    ],
                },
            },
            "loc": {},
            "assets": {},
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "materials.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            session = MaterialPackSession.open(path)

        rows_by_table = {}
        changed = _collect_stat_patch_rows(
            session,
            Recipe(
                mod_name="test",
                equipment_stat_patches=[StatPatch("actual_selected_armour", "armour", "armour_value", 80)],
                land_unit_clones=[],
                skill_set_clones=[],
                attribute_set_clones=[],
                age_range_clones=[],
                character_clones=[],
                character_patches=[],
                raw={},
            ),
            {},
            rows_by_table,
        )

        self.assertEqual(changed, 1)
        row = rows_by_table["db/unit_armour_types_tables/data__"][0]
        self.assertEqual(row["key"], "actual_selected_armour")
        self.assertEqual(row["armour_value"], 80)

    def test_material_stat_patch_reads_addon_equipment_variant_tables(self) -> None:
        payload = {
            "tables": {
                "db/ceos_to_equipment_variants_tables/!!ironic_addon_korea": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [{"ceos_key": "addon_armour_ceo", "armour": "addon_armour_row"}],
                },
                "db/unit_armour_types_tables/!!ironic_addon_korea": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [{"key": "addon_armour_row", "armour_value": 40}],
                },
            },
            "loc": {},
            "assets": {},
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "materials.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            session = MaterialPackSession.open(path)

        rows_by_table = {}
        changed = _collect_stat_patch_rows(
            session,
            Recipe(
                mod_name="test",
                equipment_stat_patches=[StatPatch("addon_armour_ceo", "armour", "armour_value", 88)],
                land_unit_clones=[],
                skill_set_clones=[],
                attribute_set_clones=[],
                age_range_clones=[],
                character_clones=[],
                character_patches=[],
                raw={},
            ),
            {},
            rows_by_table,
        )

        self.assertEqual(changed, 1)
        row = rows_by_table["db/unit_armour_types_tables/!!ironic_addon_korea"][0]
        self.assertEqual(row["key"], "addon_armour_row")
        self.assertEqual(row["armour_value"], 88)

    def test_material_stat_patch_skips_missing_equipment_mapping(self) -> None:
        payload = {
            "tables": {
                "db/ceos_to_equipment_variants_tables/data__": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [],
                },
                "db/unit_armour_types_tables/data__": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [{"key": "armour_row", "armour_value": 40}],
                },
            },
            "loc": {},
            "assets": {},
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "materials.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            session = MaterialPackSession.open(path)

        rows_by_table = {}
        changed = _collect_stat_patch_rows(
            session,
            Recipe(
                mod_name="test",
                equipment_stat_patches=[StatPatch("missing_armour_ceo", "armour", "armour_value", 77)],
                land_unit_clones=[],
                skill_set_clones=[],
                attribute_set_clones=[],
                age_range_clones=[],
                character_clones=[],
                character_patches=[],
                raw={},
            ),
            {},
            rows_by_table,
        )

        self.assertEqual(changed, 0)
        self.assertEqual(rows_by_table, {})

    def test_material_armour_audio_type_patch_uses_source_table_path(self) -> None:
        payload = {
            "tables": {
                "db/ceos_to_equipment_variants_tables/_mtu_characters_ceo_armours": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [],
                },
                "db/ceos_to_equipment_variants_tables/data__": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [{"ceos_key": "armour_ceo", "armour": "armour_row"}],
                },
                "db/unit_armour_types_tables/_mtu_characters_skills_abilities": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [],
                },
                "db/unit_armour_types_tables/data__": {
                    "db": {"table": {"definition": {"fields": []}, "table_data": []}},
                    "rows": [{"key": "armour_row", "armour_value": 40, "audio_type": "Leather"}],
                },
            },
            "loc": {},
            "assets": {},
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "materials.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            session = MaterialPackSession.open(path)

        rows_by_table = {}
        source_dbs = {}
        changed = _collect_stat_patch_rows(
            session,
            Recipe(
                mod_name="test",
                equipment_stat_patches=[StatPatch("armour_ceo", "armour", "audio_type", "Cloth")],
                land_unit_clones=[],
                skill_set_clones=[],
                attribute_set_clones=[],
                age_range_clones=[],
                character_clones=[],
                character_patches=[],
                raw={},
            ),
            source_dbs,
            rows_by_table,
        )

        self.assertEqual(changed, 1)
        row = rows_by_table["db/unit_armour_types_tables/data__"][0]
        self.assertEqual(row["key"], "armour_row")
        self.assertEqual(row["audio_type"], "Cloth")


if __name__ == "__main__":
    unittest.main()
