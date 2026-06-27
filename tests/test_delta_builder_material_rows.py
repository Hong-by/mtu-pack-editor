from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tk_pack_builder.delta_builder import (
    _campaign_start_spawn_script,
    _collect_character_clone_rows,
    _collect_character_patch_rows,
    _collect_land_unit_clone_rows,
    _collect_stat_patch_rows,
    _copy_skill_dependency,
    _read_rows,
)
from tk_pack_builder.internal_materials import MaterialPackSession
from tk_pack_builder.recipe import CharacterClone, CharacterPatch, LandUnitClone, Recipe, StatPatch, recipe_from_dict


class DeltaBuilderMaterialRowsTest(unittest.TestCase):
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

    def test_campaign_start_spawn_emits_lua_spawner(self) -> None:
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
        self.assertIn("function hby_mtu_pack_editor_player_spawn", script or "")
        self.assertIn("hby_mtu_player_spawn_listener_registered", script or "")

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
                    overrides={"charge_bonus": 99, "morale": 88},
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
                        {"character_generation_template": "source_template", "game_mode": "historical", "retinue": "source_retinue"},
                        {"character_generation_template": "source_template", "game_mode": "romance", "retinue": "source_retinue"},
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
