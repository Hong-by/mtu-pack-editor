from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tk_pack_builder import web
from tk_pack_builder.validation import ValidationMessage


class FakeSession:
    pack_path = Path("writer.pack")
    pack_key = "writer.pack"

    def close(self) -> None:
        return None


class FakeAnalysis:
    def to_dict(self) -> dict[str, str]:
        return {"packName": "writer.pack"}


class FakeReferenceSession:
    def __init__(self, tables: dict[str, list[dict[str, str]]]) -> None:
        self._tables = tables

    def list_tables(self, source: str = "pack") -> list[str]:
        return sorted(self._tables)

    def read_table(self, table_path: str, source: str = "pack") -> list[dict[str, str]]:
        if table_path not in self._tables:
            raise ValueError(table_path)
        return self._tables[table_path]


class FakePackSession:
    pack_path = Path("writer.pack")
    pack_key = "writer.pack"

    def __init__(self, tables: dict[str, list[dict[str, object]]]) -> None:
        self._tables = tables

    def list_tables(self, source: str = "pack") -> list[str]:
        return sorted(self._tables)

    def read_table(self, table_path: str, source: str = "pack") -> list[dict[str, object]]:
        if table_path not in self._tables:
            raise ValueError(table_path)
        return self._tables[table_path]

    def list_files(self) -> list[str]:
        return []

    def list_loc_files(self) -> list[str]:
        return []

    def read_loc(self, loc_path: str) -> dict[str, str]:
        return {}


class WebMaterialBuildTest(unittest.TestCase):
    def test_combat_stats_do_not_match_lady_sun_to_gongsun_armour(self) -> None:
        tables = {
            "ceo_initial_datas": [
                {"key": "3k_main_ceo_initial_data_character_historical_lady_sun"},
                {"key": "3k_main_ceo_initial_data_character_historical_gongsun_zan"},
            ],
            "equipment_variants_weapons": [],
            "equipment_variants_armours": [
                {
                    "ceos_key": "3k_main_ancillary_armour_gongsun_zans_armour_unique",
                    "armour": "3k_main_hero_gongsun_zan_unique",
                },
                {
                    "ceos_key": "3k_main_ancillary_armour_lady_suns_armour_unique",
                    "armour": "3k_main_hero_lady_sun_unique",
                },
            ],
            "melee_weapons": [],
            "missile_weapons": [],
            "projectiles": [],
            "unit_armour_types": [
                {"key": "3k_main_hero_gongsun_zan_unique", "armour_value": 65, "audio_type": "Segmented_Light"},
                {"key": "3k_main_hero_lady_sun_unique", "armour_value": 80, "audio_type": "Segmented_Medium"},
            ],
            "character_generation_template_game_mode_details": [],
        }

        stats = web._combat_stats_by_initial_ceo(tables)

        self.assertEqual(
            stats["3k_main_ceo_initial_data_character_historical_lady_sun"]["armourStatKey"],
            "3k_main_hero_lady_sun_unique",
        )
        self.assertEqual(
            stats["3k_main_ceo_initial_data_character_historical_gongsun_zan"]["armourStatKey"],
            "3k_main_hero_gongsun_zan_unique",
        )

    def test_combat_stats_match_named_weapon_from_variant_model_key(self) -> None:
        tables = {
            "ceo_initial_datas": [
                {"key": "3k_mtu_ceo_initial_data_character_historical_lady_ma_yunlu"},
            ],
            "equipment_variants_weapons": [
                {
                    "ceos_key": "3k_mtu_ancillary_weapon_mothers_bow",
                    "primary_missile_weapon": "3k_mtu_hero_bow_lady_ma_yunlu_unique",
                },
            ],
            "equipment_variants_armours": [
                {
                    "ceos_key": "3k_mtu_ancillary_armour_lady_ma_yunlus_armour_unique",
                    "armour": "3k_mtu_hero_lady_ma_yunlu_unique",
                },
            ],
            "melee_weapons": [],
            "missile_weapons": [
                {
                    "key": "3k_mtu_hero_bow_lady_ma_yunlu_unique",
                    "default_projectile": "3k_mtu_arrow_lady_ma_yunlu",
                },
            ],
            "projectiles": [
                {"key": "3k_mtu_arrow_lady_ma_yunlu", "damage": 42, "ap_damage": 11, "effective_range": 250},
            ],
            "unit_armour_types": [
                {"key": "3k_mtu_hero_lady_ma_yunlu_unique", "armour_value": 45, "audio_type": "Segmented_Medium"},
            ],
            "character_generation_template_game_mode_details": [],
        }

        stats = web._combat_stats_by_initial_ceo(tables)

        self.assertEqual(
            stats["3k_mtu_ceo_initial_data_character_historical_lady_ma_yunlu"]["weaponCeo"],
            "3k_mtu_ancillary_weapon_mothers_bow",
        )
        self.assertEqual(
            stats["3k_mtu_ceo_initial_data_character_historical_lady_ma_yunlu"]["missileWeaponStatKey"],
            "3k_mtu_hero_bow_lady_ma_yunlu_unique",
        )
        self.assertEqual(
            stats["3k_mtu_ceo_initial_data_character_historical_lady_ma_yunlu"]["armourCeo"],
            "3k_mtu_ancillary_armour_lady_ma_yunlus_armour_unique",
        )
        self.assertEqual(
            stats["3k_mtu_ceo_initial_data_character_historical_lady_ma_yunlu"]["armourCeo"],
            "3k_mtu_ancillary_armour_lady_ma_yunlus_armour_unique",
        )

    def test_snapshot_runtime_equipment_keys_preserve_source_ceo_keys(self) -> None:
        character_data = {
            "pack": {
                "characters": [
                    {
                        "key": "3k_mtu_template_historical_lady_ma_yunlu_hero_metal",
                        "combatStats": {
                            "armourCeo": "3k_mtu_ancillary_armour_lady_ma_yunlus_armour_unique",
                        },
                    },
                ],
            },
        }

        web._normalize_character_data_runtime_equipment_keys(character_data)

        self.assertEqual(
            character_data["pack"]["characters"][0]["combatStats"]["armourCeo"],
            "3k_mtu_ancillary_armour_lady_ma_yunlus_armour_unique",
        )

    def test_title_catalog_merges_duplicate_title_keys(self) -> None:
        title_key = "3k_main_ceo_node_career_historical_test_hero_01"
        characters = [
            {
                "key": "3k_main_template_historical_test_hero_wood",
                "displayName": "테스트 장수",
                "titleInfo": {
                    "ceoNodeKey": title_key,
                    "label": "01",
                },
                "templateRow": {"_sourceTablePath": "db/character_generation_templates_tables/data__"},
            },
            {
                "key": "3k_mtu_template_historical_test_hero_wood",
                "displayName": "테스트 장수 MTU",
                "titleInfo": {
                    "ceoNodeKey": title_key,
                    "label": "정리된 칭호",
                    "description": "정리된 효과",
                },
                "templateRow": {"_sourceTablePath": "db/character_generation_templates_tables/_mtu_characters"},
            },
        ]

        with patch.object(web, "_load_title_effect_catalog", return_value=({}, [])):
            catalog = web._build_title_catalog(characters)

        self.assertEqual(1, len(catalog))
        self.assertEqual(title_key, catalog[0]["key"])
        self.assertEqual("정리된 칭호", catalog[0]["label"])
        self.assertEqual("정리된 효과", catalog[0]["description"])

    def test_common_generic_titles_are_canonicalized_by_element_and_role(self) -> None:
        characters = [
            {
                "key": "3k_main_template_generic_metal_agent_normal_m_hero",
                "displayName": "generic agent normal m",
                "titleInfo": {
                    "ceoNodeKey": "3k_main_ceo_node_career_historical_3k_main_template_generic_metal_agent_normal_m_hero_01",
                    "initialCeoKey": "3k_main_ceo_initial_data_character_generic_m_metal_agent",
                    "label": "금 첩보원",
                },
                "templateRow": {"_sourceTablePath": "db/character_generation_templates_tables/data__"},
            },
            {
                "key": "3k_mtu_template_generic_metal_agent_normal_f_hero",
                "displayName": "generic agent normal f",
                "titleInfo": {
                    "ceoNodeKey": "3k_mtu_ceo_node_career_historical_3k_korea_template_generic_metal_agent_normal_f_hero_01",
                    "initialCeoKey": "3k_main_ceo_initial_data_character_generic_f_metal_agent",
                    "label": "금 첩보원",
                },
                "templateRow": {"_sourceTablePath": "db/character_generation_templates_tables/_mtu_characters"},
            },
        ]

        with patch.object(web, "_load_title_effect_catalog", return_value=({}, [])):
            catalog = web._build_title_catalog(characters)

        self.assertEqual(1, len(catalog))
        self.assertEqual("common_title:metal:agent", catalog[0]["canonicalTitleGroup"])
        self.assertEqual("사무원", catalog[0]["label"])
        self.assertEqual("기본 칭호", catalog[0]["ownerName"])
        self.assertIn("전문성 +15", catalog[0]["effectSummary"])
        self.assertEqual("common", catalog[0]["titleSourceKind"])

    def test_common_generic_title_mapping_does_not_override_unique_titles_with_generic_initials(self) -> None:
        title_key = "3k_main_ceo_node_career_historical_guan_yu_01"
        characters = [
            {
                "key": "3k_main_template_historical_guan_yu_hero_wood",
                "displayName": "관우",
                "titleInfo": {
                    "ceoNodeKey": title_key,
                    "initialCeoKey": "3k_main_ceo_initial_data_character_generic_m_wood_general",
                    "label": "무신",
                },
                "templateRow": {"_sourceTablePath": "db/character_generation_templates_tables/data__"},
            },
        ]

        with patch.object(web, "_load_title_effect_catalog", return_value=({}, [])):
            catalog = web._build_title_catalog(characters)

        self.assertEqual(1, len(catalog))
        self.assertEqual(title_key, catalog[0]["key"])
        self.assertEqual("무신", catalog[0]["label"])
        self.assertFalse(catalog[0].get("canonicalTitleGroup"))

    def test_title_info_rejects_mixed_name_title_loc_and_uses_frontend_title(self) -> None:
        loc_text = {
            "ceo_nodes_title_3k_main_ceo_node_career_historical_lu_zheng_01": "여 zheng 여 zheng 01",
            "frontend_faction_leader_unique_characters_localised_description_3k_mtu_template_historical_lady_lu_zheng_hero_water_190": (
                "[[b]]육정[[/b]]\\n태원의 정찰병\\n\\n장군 유형: {{tr:3k_general_type_water}}"
            ),
        }

        info = web._title_info_for_character(
            {"key": "3k_mtu_template_historical_lady_lu_zheng_hero_water"},
            [
                {
                    "gameMode": "historical",
                    "initialCeos": "3k_mtu_ceo_initial_data_character_historical_lady_lu_zheng",
                }
            ],
            loc_text,
        )

        self.assertEqual("태원의 정찰병", info["label"])

    def test_title_catalog_skips_generated_template_pool_labels(self) -> None:
        characters = [
            {
                "key": "3k_xianbei_template_generic_castellan_f_01",
                "displayName": "generic castellan f 01",
                "titleInfo": {
                    "ceoNodeKey": "3k_mtu_ceo_node_career_historical_3k_xianbei_template_generic_castellan_f_01_01",
                    "label": "xianbei 기본 castellan 여성 01 xianbei 기본 castellan 여성 01 01",
                },
                "templateRow": {"_sourceTablePath": "db/character_generation_templates_tables/generic_nomads"},
                "details": [],
            },
        ]

        with patch.object(web, "_load_title_effect_catalog", return_value=({}, [])):
            catalog = web._build_title_catalog(characters)

        self.assertEqual([], catalog)

    def test_title_info_prefers_korean_loc_over_earlier_generic_loc(self) -> None:
        loc_text = {
            "ceo_nodes_title_3k_mtu_ceo_node_career_historical_generic_m_metal_general_01": "generic m metal general",
            "ceo_nodes_title_3k_main_ceo_node_career_historical_generic_m_metal_general_01": "금 장군",
        }

        info = web._title_info_for_character(
            {"key": "3k_dlc04_template_historical_generic_m_metal_general"},
            [
                {
                    "gameMode": "historical",
                    "initialCeos": "3k_main_ceo_initial_data_character_generic_m_metal_general",
                }
            ],
            loc_text,
        )

        self.assertEqual("금 장군", info["label"])
        self.assertEqual("3k_main_ceo_node_career_historical_generic_m_metal_general_01", info["ceoNodeKey"])

    def test_generic_title_fallback_is_translated(self) -> None:
        loc_text = {
            "ceo_nodes_title_3k_mtu_ceo_node_career_historical_generic_m_metal_general_01": "generic m metal general",
        }

        info = web._title_info_for_character(
            {"key": "3k_dlc04_template_historical_generic_m_metal_general"},
            [
                {
                    "gameMode": "historical",
                    "initialCeos": "3k_main_ceo_initial_data_character_generic_m_metal_general",
                }
            ],
            loc_text,
        )

        self.assertEqual("남성 금 장군", info["label"])

    def test_background_title_effects_are_keyed_and_cataloged(self) -> None:
        web._load_title_effect_catalog.cache_clear()
        effects_by_title, entries = web._load_title_effect_catalog()

        commander_scholar = web._title_effect_for_key_or_label(
            effects_by_title,
            "학자",
            "bg_3k_main_character_background_commander_scholar",
        )
        strategist_academic = web._title_effect_for_key_or_label(
            effects_by_title,
            "학자",
            "bg_3k_main_character_background_strategist_academic",
        )
        self.assertIn("권위 +15", commander_scholar["effectSummary"])
        self.assertIn("지략 +15", strategist_academic["effectSummary"])

        catalog = web._build_title_catalog([])
        by_key = {item["key"]: item for item in catalog}
        self.assertIn("bg_3k_main_character_background_commander_officer", by_key)
        self.assertIn("bg_3k_main_character_background_cao_cao", by_key)
        self.assertEqual("군관", by_key["bg_3k_main_character_background_commander_officer"]["label"])
        self.assertEqual(
            "bg_3k_main_character_background_commander_officer",
            by_key["bg_3k_main_character_background_commander_officer"]["titleCeoKey"],
        )
        self.assertTrue(by_key["bg_3k_main_character_background_commander_officer"]["displayOnlyTitle"])
        self.assertEqual("background", by_key["bg_3k_main_character_background_commander_officer"]["titleSourceKind"])
        self.assertTrue(any(item.get("key") == "bg_mtu_character_background_xun_yu" for item in entries))

    def test_mtu_background_title_priority_wins_duplicate_labels(self) -> None:
        web._load_title_effect_catalog.cache_clear()
        effects_by_title, _entries = web._load_title_effect_catalog()

        label_lookup = effects_by_title[web._title_effect_lookup_key("백마장군")]
        self.assertEqual("방덕", label_lookup["owner"])
        self.assertEqual("bg_3k_main_character_background_pang_de", label_lookup["key"])

        label_only = web._title_effect_for_key_or_label(effects_by_title, "백마장군")
        self.assertEqual({}, label_only)

        pang_de = web._title_effect_for_key_or_label(
            effects_by_title,
            "백마장군",
            "bg_3k_main_character_background_pang_de",
        )
        self.assertEqual("방덕", pang_de["owner"])

    def test_background_title_aliases_are_lookup_keys(self) -> None:
        web._load_title_effect_catalog.cache_clear()
        effects_by_title, _entries = web._load_title_effect_catalog()

        primary = effects_by_title[web._title_effect_lookup_key("혈기넘치는 군관")]
        alias = effects_by_title[web._title_effect_lookup_key("애꾸눈의 망명자")]

        self.assertEqual("하후돈", primary["owner"])
        self.assertEqual(primary["key"], alias["key"])
        self.assertEqual("혈기넘치는 군관", alias["title"])

    def test_background_title_elements_follow_stat_bonuses(self) -> None:
        web._load_title_effect_catalog.cache_clear()
        _, entries = web._load_title_effect_catalog()
        by_key = {entry["key"]: entry for entry in entries if entry.get("key")}

        self.assertEqual(
            ["earth", "fire"],
            by_key["bg_3k_main_character_background_commander_officer"]["elements"],
        )
        self.assertEqual(
            ["metal", "earth"],
            by_key["bg_3k_main_character_background_sentinel_clerk"]["elements"],
        )
        self.assertEqual(
            ["wood", "metal"],
            by_key["bg_3k_main_character_background_champion_farmer"]["elements"],
        )
        self.assertEqual(
            ["fire", "wood"],
            by_key["bg_3k_main_character_background_vanguard_brawler"]["elements"],
        )
        self.assertEqual(
            ["water", "metal"],
            by_key["bg_3k_main_character_background_strategist_academic"]["elements"],
        )
        self.assertEqual(
            ["metal", "water"],
            by_key["bg_3k_main_character_background_recruited_yellow_dragon"]["elements"],
        )

    def test_skill_effect_catalog_is_keyed_and_added_to_skill_index(self) -> None:
        web._load_skill_effect_catalog.cache_clear()
        by_key, entries = web._load_skill_effect_catalog()

        manipulation = by_key["3k_main_skill_special_active_manipulation"]
        self.assertEqual("난세의 간웅", manipulation["name"])
        self.assertEqual("조조", manipulation["owner"])
        self.assertEqual("earth", manipulation["element"])
        self.assertTrue(manipulation["exclusive"])

        lu_lingqi = by_key["3k_mtu_skill_special_active_lu_lingqi_fury"]
        self.assertEqual("여희의 분노", lu_lingqi["name"])
        self.assertEqual("fire", lu_lingqi["element"])
        self.assertTrue(any(item["key"] == "3k_mtu_skill_special_active_xun_yu_vision" for item in entries))

        summary = web._summarize_skill_trees(
            {
                "character_skill_node_sets": [],
                "character_skill_nodes": [],
                "character_skill_node_links": [],
                "character_skill_level_to_effects_junctions": [],
                "effects": [],
            },
            {},
            [],
        )
        self.assertIn("3k_main_skill_special_active_manipulation", summary["skillIndex"])
        self.assertIn("3k_mtu_skill_special_active_lu_lingqi_fury", summary["skillIndex"])
        self.assertEqual(
            "난세의 간웅",
            summary["skillIndex"]["3k_main_skill_special_active_manipulation"]["name"],
        )
        self.assertEqual(
            "fire",
            summary["skillIndex"]["3k_mtu_skill_special_active_lu_lingqi_fury"]["element"],
        )

    def test_skill_effect_summary_strips_game_ui_markup(self) -> None:
        summary = web._effect_summary([
            {
                "effectKey": "test_effect_instinct",
                "name": "[[b]][[b]]본능 [[/b]]%+n[[/b]]",
                "value": 4,
            },
            {
                "effectKey": "test_effect_morale",
                "name": "부대 사기 [[b]]%+n[[/b]]",
                "value": 2,
            },
        ])

        self.assertEqual(summary, "본능 +4 · 부대 사기 +2")
        self.assertNotIn("[[", summary)
        self.assertNotIn("%+n", summary)

    def test_skill_tree_effect_summary_strips_loc_markup(self) -> None:
        summary = web._summarize_skill_trees(
            {
                "character_skill_node_sets": [{"key": "test_skillset"}],
                "character_skill_nodes": [
                    {
                        "key": "test_node",
                        "character_skill_node_set_key": "test_skillset",
                        "character_skill_key": "test_skill",
                        "indent": 1,
                        "tier": 1,
                    }
                ],
                "character_skill_node_links": [],
                "character_skill_level_to_effects_junctions": [
                    {
                        "character_skill_key": "test_skill",
                        "effect_key": "test_effect_instinct",
                        "effect_scope": "character_to_character_own",
                        "level": 1,
                        "value": 4,
                    }
                ],
                "effects": [{"key": "test_effect_instinct"}],
            },
            {"effects_description_test_effect_instinct": "[[b]][[b]]본능 [[/b]]%+n[[/b]]"},
            [
                {
                    "key": "test_character",
                    "label": "테스트",
                    "details": [{"gameMode": "romance", "skillSet": "test_skillset"}],
                }
            ],
        )

        node = summary["romance"][0]["nodes"][0]
        self.assertEqual(node["effectSummary"], "본능 +4")
        self.assertEqual(summary["skillIndex"]["test_skill"]["effectSummary"], "본능 +4")

    def test_catalogs_use_database_base_and_mtu_override(self) -> None:
        tables = {
            "character_generation_template_game_mode_details": [
                {
                    "character_generation_template": "3k_mtu_template_historical_test_hero_wood",
                    "game_mode": "historical",
                    "initial_ceos": "3k_mtu_ceo_initial_data_character_historical_test",
                    "attribute_set": "shared_attribute_set",
                    "_sourceTablePath": "db/character_generation_template_game_mode_details_tables/_mtu_characters",
                }
            ],
            "campaign_character_art_sets": [
                {
                    "art_set_id": "shared_art_set",
                    "is_male": True,
                    "_sourceTablePath": "db/campaign_character_art_sets_tables/data__",
                },
                {
                    "art_set_id": "shared_art_set",
                    "is_male": False,
                    "_sourceTablePath": "db/campaign_character_art_sets_tables/_mtu_characters",
                },
            ],
            "campaign_character_arts": [
                {
                    "art_set_id": "shared_art_set",
                    "age": 16,
                    "has_come_of_age": True,
                    "portrait": "shared_portrait/",
                    "card": "shared_card",
                    "uniform": "shared_uniform",
                    "_sourceTablePath": "db/campaign_character_arts_tables/data__",
                }
            ],
            "character_generation_templates": [
                {
                    "key": "3k_mtu_template_historical_test_hero_wood",
                    "art_set_override": "shared_art_set",
                    "_sourceTablePath": "db/character_generation_templates_tables/_mtu_characters",
                }
            ],
            "character_generation_spawn_age_ranges": [],
            "ceo_initial_datas": [],
            "character_attribute_sets": [
                {
                    "set_name": "shared_attribute_set",
                    "_sourceTablePath": "db/character_attribute_sets_tables/data__",
                },
                {
                    "set_name": "shared_attribute_set",
                    "_sourceTablePath": "db/character_attribute_sets_tables/_mtu_characters",
                },
            ],
            "character_attributes": [
                {
                    "set_name": "shared_attribute_set",
                    "attribute_type": "authority",
                    "value": 40,
                    "_sourceTablePath": "db/character_attributes_tables/data__",
                },
                {
                    "set_name": "shared_attribute_set",
                    "attribute_type": "authority",
                    "value": 70,
                    "_sourceTablePath": "db/character_attributes_tables/_mtu_characters",
                },
            ],
            "land_units": [],
            "character_skill_nodes": [],
            "character_skill_node_sets": [],
            "character_skill_node_set_items": [],
            "character_skill_node_links": [],
            "character_skill_level_to_effects_junctions": [],
        }

        summary = web.summarize_character_tables(tables, {}, [])

        model = next(item for item in summary["modelSets"] if item["key"] == "shared_art_set")
        attribute = next(item for item in summary["attributeSetCatalog"] if item["key"] == "shared_attribute_set")
        title = next(item for item in summary["titleCatalog"] if item["ownerKey"] == "3k_mtu_template_historical_test_hero_wood")
        self.assertEqual(model["sourceTag"], "MTU")
        self.assertFalse(model["isMale"])
        self.assertEqual(attribute["sourceTag"], "MTU")
        self.assertEqual(attribute["stats"]["authority"], 70)
        self.assertEqual(title["sourceTag"], "MTU")

    def test_read_character_data_includes_skill_tree_snapshot_data(self) -> None:
        tables = {
            "character_generation_templates": [
                {
                    "key": "3k_mtu_template_historical_test_hero_wood",
                    "art_set_override": "shared_art_set",
                    "is_male": False,
                }
            ],
            "character_generation_template_game_mode_details": [
                {
                    "character_generation_template": "3k_mtu_template_historical_test_hero_wood",
                    "game_mode": "romance",
                    "skill_set_override": "mtu_skillset_test",
                    "initial_ceos": "3k_mtu_ceo_initial_data_character_historical_test",
                }
            ],
            "campaign_character_art_sets": [{"art_set_id": "shared_art_set", "is_male": False}],
            "campaign_character_arts": [],
            "character_generation_spawn_age_ranges": [],
            "ceo_initial_datas": [],
            "character_skill_node_sets": [{"key": "mtu_skillset_test", "onscreen_name": "Test skill set"}],
            "character_skill_nodes": [
                {
                    "key": "mtu_skill_node_test",
                    "character_skill_node_set_key": "mtu_skillset_test",
                    "character_skill_key": "3k_mtu_skill_wood_test",
                    "x": 1,
                    "y": 2,
                    "onscreen_name": "Test skill",
                }
            ],
            "character_skill_node_links": [],
            "character_skill_level_to_effects_junctions": [
                {
                    "character_skill_key": "3k_mtu_skill_wood_test",
                    "effect_key": "3k_main_effect_character_stat_mod_authority",
                    "effect_scope": "character_to_character_own",
                    "level": 1,
                    "value": 6,
                }
            ],
            "effects": [{"key": "3k_main_effect_character_stat_mod_authority"}],
        }

        with patch.object(web, "_merge_internal_materials", return_value=None):
            data = web.read_character_data(FakePackSession(tables), adapter_name="mock")

        skill_trees = data["pack"]["skillTrees"]
        self.assertEqual(skill_trees["nodeCount"], 1)
        tree = next(item for item in skill_trees["romance"] if item["key"] == "mtu_skillset_test")
        self.assertEqual(tree["nodes"][0]["skillKey"], "3k_mtu_skill_wood_test")
        self.assertIn("3k_mtu_skill_wood_test", skill_trees["skillIndex"])

    def test_summary_skips_art_sets_without_art_rows(self) -> None:
        tables = {
            "character_generation_templates": [],
            "character_generation_template_game_mode_details": [],
            "campaign_character_art_sets": [
                {"art_set_id": "orphan_art_set", "is_male": True}
            ],
            "campaign_character_arts": [],
            "character_generation_spawn_age_ranges": [],
            "ceo_initial_datas": [],
            "character_skill_node_sets": [],
            "character_skill_nodes": [],
            "character_skill_node_links": [],
            "character_skill_level_to_effects_junctions": [],
        }

        summary = web.summarize_character_tables(tables, {}, [])

        self.assertNotIn("orphan_art_set", {item["key"] for item in summary["artSets"]})
        self.assertNotIn("orphan_art_set", {item["key"] for item in summary["modelSets"]})

    def test_romance_skill_tree_prefers_romance_nodes_at_same_position(self) -> None:
        tables = {
            "character_skill_node_sets": [{"key": "3k_main_skillset_historical_lu_bu"}],
            "character_skill_nodes": [
                {
                    "key": "3k_main_skillset_historical_lu_bu_2A_historical",
                    "character_skill_node_set_key": "3k_main_skillset_historical_lu_bu",
                    "character_skill_key": "3k_main_skill_bodyguard_fire_alt_1",
                    "x": 0.1,
                    "y": 1,
                },
                {
                    "key": "3k_main_skillset_historical_lu_bu_2A_romance",
                    "character_skill_node_set_key": "3k_main_skillset_historical_lu_bu",
                    "character_skill_key": "3k_main_skill_special_ability_fire_the_dragons_gaze",
                    "x": 0.1,
                    "y": 1,
                },
            ],
            "character_skill_node_links": [],
            "character_skill_level_to_effects_junctions": [],
            "effects": [],
        }
        loc_text = {
            "character_skills_localised_name_3k_main_skill_bodyguard_fire_alt_1": "선봉장",
            "character_skills_localised_name_3k_main_skill_special_ability_fire_the_dragons_gaze": "용의 눈빛",
        }
        characters = [
            {
                "key": "3k_main_template_historical_lu_bu_hero_fire",
                "label": "여포",
                "details": [
                    {
                        "gameMode": "romance",
                        "skillSet": "3k_main_skillset_historical_lu_bu",
                    }
                ],
            }
        ]

        skill_trees = web._summarize_skill_trees(tables, loc_text, characters)

        tree = skill_trees["romance"][0]
        self.assertEqual(skill_trees["nodeCount"], 1)
        self.assertEqual(tree["nodes"][0]["skillKey"], "3k_main_skill_special_ability_fire_the_dragons_gaze")
        self.assertEqual(tree["nodes"][0]["name"], "용의 눈빛")

    def test_title_info_uses_template_token_when_initial_ceo_is_generic(self) -> None:
        tables = {
            "character_generation_templates": [
                {
                    "key": "3k_main_template_historical_guan_yu_hero_wood",
                    "art_set_override": "guan_yu_art",
                    "is_male": True,
                }
            ],
            "character_generation_template_game_mode_details": [
                {
                    "character_generation_template": "3k_main_template_historical_guan_yu_hero_wood",
                    "game_mode": "historical",
                    "initial_ceos": "3k_main_ceo_initial_data_character_generic_m_wood_general",
                }
            ],
            "campaign_character_art_sets": [{"art_set_id": "guan_yu_art", "is_male": True}],
            "campaign_character_arts": [],
            "character_generation_spawn_age_ranges": [],
            "ceo_initial_datas": [],
            "character_skill_node_sets": [],
            "character_skill_nodes": [],
            "character_skill_node_links": [],
            "character_skill_level_to_effects_junctions": [],
        }
        loc_text = {
            "ceo_nodes_title_3k_main_ceo_node_career_historical_guan_yu_01": "무신",
            "ceo_nodes_title_3k_main_ceo_node_career_historical_generic_m_wood_general_01": "민병대 노장",
        }

        summary = web.summarize_character_tables(tables, loc_text, [])

        character = next(item for item in summary["characters"] if item["key"] == "3k_main_template_historical_guan_yu_hero_wood")
        self.assertEqual(character["titleInfo"]["ceoNodeKey"], "3k_main_ceo_node_career_historical_guan_yu_01")
        self.assertEqual(character["titleInfo"]["label"], "무신")

    def test_unit_stats_follow_retinue_slot_chain_across_modes(self) -> None:
        tables = {
            "character_generation_templates": [
                {
                    "key": "3k_mtu_template_historical_test_hero_fire",
                    "art_set_override": "shared_art_set",
                }
            ],
            "character_generation_template_game_mode_details": [
                {
                    "character_generation_template": "3k_mtu_template_historical_test_hero_fire",
                    "game_mode": "historical",
                    "retinue": "historical_retinue_without_slot",
                },
                {
                    "character_generation_template": "3k_mtu_template_historical_test_hero_fire",
                    "game_mode": "romance",
                    "retinue": "romance_retinue",
                },
            ],
            "campaign_character_art_sets": [{"art_set_id": "shared_art_set", "is_male": True}],
            "campaign_character_arts": [],
            "character_generation_spawn_age_ranges": [],
            "ceo_initial_datas": [],
            "land_units": [
                {
                    "key": "romance_land_unit",
                    "melee_attack": 42,
                    "melee_defence": 31,
                    "charge_bonus": 77,
                    "dismounted_melee_attack": 24,
                    "dismounted_charge_bonus": 17,
                    "morale": 66,
                    "primary_ammo": 8,
                    "category": "infantry",
                    "class": "melee",
                }
            ],
            "retinue_slot_initial_units": [
                {
                    "retinue": "romance_retinue",
                    "slot_index": 0,
                    "initial_unit_record": "romance_main_unit",
                }
            ],
            "main_units": [
                {
                    "unit": "romance_main_unit",
                    "land_unit": "romance_land_unit",
                }
            ],
            "character_skill_node_sets": [],
            "character_skill_nodes": [],
            "character_skill_node_links": [],
            "character_skill_level_to_effects_junctions": [],
        }

        summary = web.summarize_character_tables(tables, {}, [])

        character = next(item for item in summary["characters"] if item["key"] == "3k_mtu_template_historical_test_hero_fire")
        stats = character["combatStats"]
        self.assertEqual(stats["landUnitKey"], "romance_land_unit")
        self.assertEqual(stats["sourceRetinueKey"], "romance_retinue")
        self.assertEqual(stats["unitMeleeAttack"], 42)
        self.assertEqual(stats["unitMeleeDefence"], 31)
        self.assertEqual(stats["unitChargeBonus"], 77)
        self.assertEqual(stats["unitDismountedMeleeAttack"], 24)
        self.assertEqual(stats["unitDismountedChargeBonus"], 17)
        self.assertEqual(summary["mainUnits"][0]["unit"], "romance_main_unit")
        self.assertEqual(summary["mainUnits"][0]["landUnit"], "romance_land_unit")

    def test_unit_stats_fall_back_from_generic_retinue_to_generic_land_unit(self) -> None:
        tables = {
            "character_generation_templates": [
                {
                    "key": "3k_mtu_template_historical_lady_zhang_xingcai_hero_fire",
                    "art_set_override": "shared_art_set",
                }
            ],
            "character_generation_template_game_mode_details": [
                {
                    "character_generation_template": "3k_mtu_template_historical_lady_zhang_xingcai_hero_fire",
                    "game_mode": "historical",
                    "retinue": "3k_main_general_generic_fire",
                },
                {
                    "character_generation_template": "3k_mtu_template_historical_lady_zhang_xingcai_hero_fire",
                    "game_mode": "romance",
                    "retinue": "3k_main_hero_generic_fire",
                },
            ],
            "campaign_character_art_sets": [{"art_set_id": "shared_art_set", "is_male": False}],
            "campaign_character_arts": [],
            "character_generation_spawn_age_ranges": [],
            "ceo_initial_datas": [],
            "land_units": [
                {
                    "key": "3k_main_general_fire_generic",
                    "charge_bonus": 25,
                    "morale": 42,
                    "primary_ammo": 0,
                },
                {
                    "key": "3k_main_hero_fire_generic",
                    "charge_bonus": 50,
                    "morale": 60,
                    "primary_ammo": 0,
                },
            ],
            "retinue_slot_initial_units": [],
            "main_units": [],
            "character_skill_node_sets": [],
            "character_skill_nodes": [],
            "character_skill_node_links": [],
            "character_skill_level_to_effects_junctions": [],
        }

        summary = web.summarize_character_tables(tables, {}, [])

        character = summary["characters"][0]
        stats = character["combatStats"]
        self.assertEqual(stats["landUnitKey"], "3k_main_general_fire_generic")
        self.assertEqual(stats["sourceRetinueKey"], "3k_main_general_generic_fire")
        self.assertEqual(stats["unitChargeBonus"], 25)

    def test_internal_material_merge_does_not_clear_resolved_combat_stats(self) -> None:
        character_data = {
            "pack": {
                "characters": [
                    {
                        "key": "3k_mtu_template_historical_lady_zhang_xingcai_hero_fire",
                        "details": [{"gameMode": "romance", "retinue": "3k_main_hero_generic_fire"}],
                        "combatStats": {
                            "landUnitKey": "3k_main_hero_fire_generic",
                            "sourceRetinueKey": "3k_main_hero_generic_fire",
                            "unitChargeBonus": 50,
                        },
                    }
                ]
            }
        }
        internal_summary = {
            "characters": [
                {
                    "key": "3k_mtu_template_historical_lady_zhang_xingcai_hero_fire",
                    "details": [],
                    "combatStats": {
                        "landUnitKey": None,
                        "sourceRetinueKey": "",
                        "baseDefense": 40,
                    },
                    "displayName": "장성채",
                }
            ]
        }

        with patch.object(web, "_load_internal_material_summary", return_value=internal_summary):
            web._merge_internal_material_character_summary(character_data)

        character = character_data["pack"]["characters"][0]
        self.assertEqual(character["displayName"], "장성채")
        self.assertEqual(character["combatStats"]["landUnitKey"], "3k_main_hero_fire_generic")
        self.assertEqual(character["combatStats"]["sourceRetinueKey"], "3k_main_hero_generic_fire")
        self.assertEqual(character["combatStats"]["unitChargeBonus"], 50)
        self.assertEqual(character["combatStats"]["baseDefense"], 40)
        self.assertEqual(character["details"], [{"gameMode": "romance", "retinue": "3k_main_hero_generic_fire"}])

    def test_core_reference_rows_are_merged_before_character_summary(self) -> None:
        tables = {
            "character_generation_templates": [
                {
                    "key": "3k_mtu_template_historical_lady_zhang_xingcai_hero_fire",
                    "art_set_override": "shared_art_set",
                }
            ],
            "character_generation_template_game_mode_details": [
                {
                    "character_generation_template": "3k_mtu_template_historical_lady_zhang_xingcai_hero_fire",
                    "game_mode": "romance",
                    "retinue": "3k_main_hero_generic_fire",
                }
            ],
            "campaign_character_art_sets": [{"art_set_id": "shared_art_set", "is_male": False}],
            "campaign_character_arts": [],
            "character_generation_spawn_age_ranges": [],
            "ceo_initial_datas": [],
            "land_units": [],
            "retinue_slot_initial_units": [],
            "main_units": [],
            "character_skill_node_sets": [],
            "character_skill_nodes": [],
            "character_skill_node_links": [],
            "character_skill_level_to_effects_junctions": [],
        }

        def merge_reference_rows(target_tables, *_args):
            target_tables["land_units"].append({
                "key": "3k_main_hero_fire_generic",
                "charge_bonus": 50,
                "morale": 60,
                "primary_ammo": 0,
            })
            return [{"path": "mtu_reference_core.pack", "ok": True}]

        with (
            patch.object(web, "_merge_reference_packs", side_effect=merge_reference_rows) as merge_mock,
            patch.object(web, "_merge_internal_materials", side_effect=AssertionError("core should replace internal material merge")),
            patch.object(web, "_merge_local_extracted_assets", return_value=None),
        ):
            character_data = web.read_character_data(
                FakePackSession(tables),
                reference_paths=[Path("mtu_reference_core.pack")],
            )

        self.assertEqual(merge_mock.call_args.args[4], [Path("mtu_reference_core.pack")])
        character = character_data["pack"]["characters"][0]
        self.assertEqual(character["combatStats"]["landUnitKey"], "3k_main_hero_fire_generic")
        self.assertEqual(character["combatStats"]["unitChargeBonus"], 50)

    def test_internal_skill_trees_are_merged_when_pack_has_trees(self) -> None:
        target = {
            "skillTrees": {
                "romance": [
                    {"key": "pack_skillset", "nodes": [{"key": "pack_node"}]},
                ],
                "nodeCount": 1,
                "skillIndex": {"pack_skill": {"name": "Pack Skill"}},
            },
        }
        source = {
            "skillTrees": {
                "romance": [
                    {"key": "pack_skillset", "nodes": [{"key": "ignored_duplicate"}]},
                    {"key": "internal_skillset", "nodes": [{"key": "internal_node"}]},
                ],
                "nodeCount": 2,
                "skillIndex": {
                    "pack_skill": {"name": "Duplicate Skill"},
                    "internal_skill": {"name": "Internal Skill"},
                },
            },
        }

        web._merge_summary_supporting_rows(target, source)

        skill_trees = target["skillTrees"]
        self.assertEqual(
            {tree["key"] for tree in skill_trees["romance"]},
            {"pack_skillset", "internal_skillset"},
        )
        self.assertEqual(skill_trees["nodeCount"], 2)
        self.assertEqual(skill_trees["skillIndex"]["pack_skill"]["name"], "Pack Skill")
        self.assertEqual(skill_trees["skillIndex"]["internal_skill"]["name"], "Internal Skill")

    def test_skill_index_infers_source_from_key_prefix(self) -> None:
        dlc = web._skill_index_entry("3k_dlc05_skill_special_active_dance_of_steel", {}, [])
        mtu = web._skill_index_entry("3k_mtu_skill_special_active_test", {}, [])
        vanilla = web._skill_index_entry("3k_main_skill_special_active_test", {}, [])

        self.assertEqual(dlc["source"], "DLC")
        self.assertEqual(mtu["source"], "MTU")
        self.assertEqual(vanilla["source"], "바닐라")

    def test_ceo_set_catalogs_resolve_loc_titles_to_node_keys(self) -> None:
        loc_text = {
            "ceo_nodes_title_3k_main_ceo_node_trait_personality_brave_01": "용감함",
            "ceo_nodes_title_3k_main_ancillary_double_edged_sword_exceptional": "전쟁용 검",
        }

        trait_sets = web._build_ceo_set_catalog(web.TRAIT_SET_PRESETS, loc_text, "trait")
        equipment_sets = web._build_ceo_set_catalog(web.EQUIPMENT_SET_PRESETS, loc_text, "equipment")

        warrior = next(item for item in trait_sets if item["key"] == "warrior")
        brave = next(item for item in warrior["items"] if item["label"] == "용감함")
        self.assertEqual(brave["key"], "3k_main_ceo_trait_personality_brave")
        self.assertEqual(brave["source"], "sheet")
        self.assertIn("3k_main_ceo_trait_personality_brave", warrior["ceoKeys"])
        self.assertTrue(all(isinstance(key, str) for key in warrior["ceoKeys"]))
        sentinel = next(item for item in equipment_sets if item["key"] == "sentinel")
        sword = next(item for item in sentinel["items"] if item["label"] == "전쟁용 검")
        self.assertEqual(sword["key"], "3k_main_ancillary_weapon_double_edged_sword_exceptional")
        self.assertEqual(sword["source"], "sheet")
        self.assertIn("3k_main_ancillary_weapon_double_edged_sword_exceptional", sentinel["ceoKeys"])
        self.assertTrue(all(isinstance(key, str) for key in sentinel["ceoKeys"]))

    def test_reference_reader_merges_all_tables_for_same_alias(self) -> None:
        session = FakeReferenceSession(
            {
                "db/character_generation_templates_tables/data__": [
                    {"key": "3k_main_template_historical_lu_bu_hero_fire"}
                ],
                "db/character_generation_templates_tables/_mtu_characters": [
                    {"key": "3k_mtu_template_historical_lu_su_hero_water"}
                ],
                "db/character_generation_templates_tables/!!ironic_addon_korea": [
                    {"key": "3k_mod_template_historical_go_gyesu_hero_wood"}
                ],
                "db/character_generation_template_game_mode_details_tables/data__": [
                    {"character_generation_template": "3k_main_template_historical_lu_bu_hero_fire", "game_mode": "historical"}
                ],
                "db/character_generation_template_game_mode_details_tables/!!ironic_addon_korea": [
                    {"character_generation_template": "3k_mod_template_historical_go_gyesu_hero_wood", "game_mode": "historical"}
                ],
            }
        )

        tables = web._read_reference_tables(session)

        template_keys = {row["key"] for row in tables["character_generation_templates"]}
        detail_keys = {
            row["character_generation_template"]
            for row in tables["character_generation_template_game_mode_details"]
        }
        self.assertIn("3k_main_template_historical_lu_bu_hero_fire", template_keys)
        self.assertIn("3k_mtu_template_historical_lu_su_hero_water", template_keys)
        self.assertIn("3k_mod_template_historical_go_gyesu_hero_wood", template_keys)
        self.assertIn("3k_mod_template_historical_go_gyesu_hero_wood", detail_keys)
        korea_row = next(row for row in tables["character_generation_templates"] if row["key"].startswith("3k_mod_"))
        self.assertEqual(web._catalog_source_tag(korea_row), "KR")

    def test_reference_row_merge_uses_source_priority(self) -> None:
        target = [
            {
                "key": "shared_template",
                "value": "database",
                "_referenceSourcePath": "mtu_reference_core.pack",
                "_sourceTablePath": "db/character_generation_templates_tables/data__",
                "_sourceRank": 10,
            }
        ]

        web._append_missing_rows(
            target,
            [
                {
                    "key": "shared_template",
                    "value": "mtu",
                    "_sourceTablePath": "db/character_generation_templates_tables/_mtu_characters",
                    "_sourceRank": 90,
                }
            ],
            "key",
            "mtu_reference_core.pack",
        )

        self.assertEqual(len(target), 1)
        self.assertEqual(target[0]["value"], "mtu")

        web._append_missing_rows(
            target,
            [
                {
                    "key": "shared_template",
                    "value": "database-again",
                    "_sourceTablePath": "db/character_generation_templates_tables/data__",
                    "_sourceRank": 10,
                }
            ],
            "key",
            "mtu_reference_core.pack",
        )

        self.assertEqual(target[0]["value"], "mtu")

    def test_core_reference_still_adds_local_hby_assets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            asset = root / "hby_generated_character_sets" / "ui" / "characters" / "hby_test" / "stills" / "unitcards" / "hby_test.png"
            asset.parent.mkdir(parents=True)
            asset.write_bytes(b"png")
            asset_files: list[str] = []
            asset_sources: dict[str, str] = {}

            with patch.object(web, "EXTRACTED_ASSET_ROOT", root):
                report = web._merge_local_extracted_assets(asset_files, asset_sources)

        self.assertIsNotNone(report)
        self.assertIn("ui/characters/hby_test/stills/unitcards/hby_test.png", asset_files)
        self.assertEqual(report["addedAssets"], 1)

    def test_internal_asset_manifest_skips_unavailable_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            extracted_root = root / "assets"
            source_id = "source_a"
            available_path = "ui/characters/available/stills/unitcards/available.png"
            missing_path = "ui/characters/missing/stills/unitcards/missing.png"
            extracted = extracted_root / source_id / available_path
            extracted.parent.mkdir(parents=True)
            extracted.write_bytes(b"png")
            manifest_path = root / "asset_manifest.json"
            manifest_path.write_text(json.dumps({
                "assets": {
                    available_path: {
                        "sourceId": source_id,
                        "sourcePath": "",
                        "extractedPath": str(extracted),
                    },
                    missing_path: {
                        "sourceId": "missing_source",
                        "sourcePath": "",
                        "extractedPath": str(root / "missing.png"),
                    },
                }
            }), encoding="utf-8")
            asset_files: list[str] = []
            asset_sources: dict[str, str] = {}

            with (
                patch.object(web, "INTERNAL_ASSET_MANIFEST", manifest_path),
                patch.object(web, "EXTRACTED_ASSET_ROOT", extracted_root),
            ):
                added = web._merge_internal_asset_manifest(asset_files, asset_sources, set())

        self.assertEqual(added, 1)
        self.assertIn(available_path, asset_files)
        self.assertNotIn(missing_path, asset_files)

    def test_core_reference_still_includes_default_game_packs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            core = root / "mtu_reference_core.pack"
            game_dir = root / "data"
            game_dir.mkdir()
            local_kr = game_dir / "local_kr.pack"
            core.write_bytes(b"core")
            local_kr.write_bytes(b"local")

            with (
                patch.object(web, "DEFAULT_GAME_DATA_DIRS", [game_dir]),
                patch.object(web, "DEFAULT_GAME_LOCAL_PACKS", ("local_kr.pack",)),
            ):
                paths = web._reference_pack_paths({"referencePackPaths": [str(core)]})

        self.assertIn(core.resolve(), paths)
        self.assertIn(local_kr.resolve(), paths)

    def test_auxiliary_catalog_does_not_append_korea_without_db_rows(self) -> None:
        character_data = {"pack": {"characters": []}}
        catalog = {
            "characters": [
                {
                    "key": "3k_mod_template_historical_go_gyesu_hero_wood",
                    "displayName": "고계수",
                    "virtualImageOnly": False,
                    "imageOnly": False,
                }
            ]
        }

        with (
            patch.object(web, "_load_internal_character_catalog_pack", return_value=catalog),
            patch.object(web, "korea_character_metadata", return_value={"isKoreaAddon": True}),
        ):
            web._merge_auxiliary_catalog_characters(character_data)

        self.assertEqual(character_data["pack"]["characters"], [])

    def test_dropdown_labels_fall_back_to_korean_terms(self) -> None:
        self.assertEqual(
            web._localized_label("3k_main_attribute_set_general_fire_records", context="attribute"),
            "화 기본 능력치",
        )
        self.assertEqual(web._friendly_art_set_label("3k_main_hero_special_water_lady_cai_yan"), "3k_main_hero_special_water_lady_cai_yan")
        self.assertEqual(web._friendly_model_set_label("3k_main_hero_special_water_lady_cai_yan", ""), "3k_main_hero_special_water_lady_cai_yan")

    def test_skill_and_effect_labels_do_not_expose_raw_keys(self) -> None:
        self.assertEqual(
            web._friendly_effect_key("3k_main_effect_character_stat_mod_expertise"),
            "전문성",
        )
        summary = web._effect_summary([
            {
                "effectKey": "3k_main_effect_character_stat_mod_authority",
                "name": "3k_main_effect_character_stat_mod_authority",
                "value": 8,
            }
        ])
        self.assertEqual(summary, "권위 +8")

    def test_auxiliary_catalog_skips_aw_image_only_characters(self) -> None:
        character_data = {"pack": {"characters": []}}
        catalog = {
            "characters": [
                {
                    "key": "image_only_aw_test",
                    "displayName": "AW test",
                    "virtualImageOnly": True,
                    "referenceSourcePath": "AW_mh_hero_special_water_diao_chan.pack",
                }
            ]
        }

        with patch.object(web, "_load_internal_character_catalog_pack", return_value=catalog):
            web._merge_auxiliary_catalog_characters(character_data)

        self.assertEqual(character_data["pack"]["characters"], [])

    def test_open_pack_with_core_reference_applies_korea_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pack_path = Path(tmp) / "my_hero.pack"
            pack_path.write_bytes(b"pack")
            character_data = {
                "pack": {
                    "characters": [
                        {
                            "key": "3k_mod_template_historical_go_gyesu_hero_wood",
                            "displayName": "old",
                        }
                    ]
                }
            }

            with (
                patch.object(web, "_reference_pack_paths", return_value=[Path("mtu_reference_core.pack")]),
                patch.object(web, "_open_session", return_value=FakeSession()),
                patch.object(web, "analyze_pack", return_value=FakeAnalysis()),
                patch.object(web, "read_character_data", return_value=character_data),
                patch.object(web.PACK_CACHE, "put_open_payload", return_value=None),
                patch.object(web, "_write_reference_snapshot", return_value=None),
                patch.object(web, "korea_character_metadata", return_value={"isKoreaAddon": True, "koreaDisplayNameHint": "고계수"}),
                patch.object(web, "korea_display_name_hint", return_value="잘못된힌트"),
            ):
                result = web.open_pack_payload({
                    "inputPath": str(pack_path),
                    "adapter": "rpfm",
                    "forceRefresh": True,
                })

            character = result["characters"]["pack"]["characters"][0]
            self.assertTrue(result["ok"])
            self.assertTrue(character["isKoreaAddon"])
            self.assertEqual(character["displayName"], "고계수")
            self.assertEqual(character["label"], "고계수")

    def test_korea_name_hint_is_not_applied_without_metadata(self) -> None:
        character_data = {
            "pack": {
                "characters": [
                    {
                        "key": "3k_main_template_historical_qiulijiu_hero_fire",
                        "displayName": "구리거",
                        "label": "구리거",
                        "isKoreaAddon": True,
                        "koreaFaction": "",
                        "koreaDisplayNameHint": "고계수",
                    }
                ]
            }
        }

        with (
            patch.object(web, "_merge_internal_material_character_summary", return_value=None),
            patch.object(web, "_merge_auxiliary_catalog_characters", return_value=None),
            patch.object(web, "korea_character_metadata", return_value=None),
            patch.object(web, "korea_display_name_hint", return_value="고계수"),
        ):
            web._enrich_korea_addon_character_data(character_data)

        character = character_data["pack"]["characters"][0]
        self.assertEqual(character["displayName"], "구리거")
        self.assertEqual(character["label"], "구리거")
        self.assertNotIn("isKoreaAddon", character)
        self.assertNotIn("koreaDisplayNameHint", character)

    def test_stale_korea_material_name_falls_back_to_template_token(self) -> None:
        character = web._sanitize_stale_korea_character({
            "key": "3k_main_template_historical_qiulijiu_hero_fire",
            "displayName": "고계수",
            "label": "고계수",
            "isKoreaAddon": True,
            "koreaDisplayNameHint": "고계수",
            "templateRow": {"key": "3k_main_template_historical_qiulijiu_hero_fire"},
            "titleInfo": {"label": "qiulijiu"},
        })

        self.assertEqual(character["displayName"], "qiulijiu")
        self.assertEqual(character["label"], "qiulijiu")
        self.assertNotIn("isKoreaAddon", character)

    def test_stale_korea_material_name_uses_known_character_name(self) -> None:
        character = web._sanitize_stale_korea_character({
            "key": "3k_mtu_template_historical_lady_zou_yuan_hero_water",
            "displayName": "고계수",
            "label": "고계수",
            "isKoreaAddon": True,
            "koreaDisplayNameHint": "고계수",
            "templateRow": {"key": "3k_mtu_template_historical_lady_zou_yuan_hero_water"},
        })

        self.assertEqual(character["displayName"], "추원")
        self.assertEqual(character["label"], "추원")
        self.assertNotIn("isKoreaAddon", character)

    def test_image_only_bad_hint_name_uses_art_set_label(self) -> None:
        summary = {
            "characters": [
                {
                    "key": "image_only_hby_generated_character_sets_hby_hero_special_go_yeon_hwa",
                    "displayName": "잘못된힌트",
                    "label": "잘못된힌트",
                    "forename": "잘못된힌트",
                    "artSet": "image_only_hby_generated_character_sets_hby_hero_special_go_yeon_hwa",
                    "portrait": "hby_hero_special_go_yeon_hwa",
                    "virtualImageOnly": True,
                }
            ],
            "artSets": [
                {
                    "key": "image_only_hby_generated_character_sets_hby_hero_special_go_yeon_hwa",
                    "label": "고연화",
                }
            ],
        }

        web._repair_image_only_character_labels(summary)

        character = summary["characters"][0]
        self.assertEqual(character["displayName"], "고연화")
        self.assertEqual(character["label"], "고연화")
        self.assertEqual(character["forename"], "고연화")

    def test_build_payload_uses_internal_materials_when_requested(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            materials = tmp_path / "materials.json"
            materials.write_text(json.dumps({"tables": {}, "loc": {}, "assets": {}}), encoding="utf-8")
            output = tmp_path / "out.pack"
            output.write_bytes(b"pack")
            with (
                patch.object(web, "_open_session", return_value=FakeSession()) as open_session,
                patch.object(web.delta_builder_module, "build_delta_pack_from_materials", return_value=[{"level": "success", "code": "ok", "message": "built"}]) as build,
            ):
                previous_core = web.delta_builder_module.CORE_ASSET_SOURCE_ID
                result = web.build_payload({
                    "adapter": "rpfm",
                    "inputPath": "writer.pack",
                    "outputPath": str(output),
                    "delta": True,
                    "useInternalMaterials": True,
                    "materialPath": str(materials),
                    "coreAssetSourceId": "core-test",
                    "recipe": {"modName": "test"},
                })

        self.assertTrue(result["ok"])
        self.assertEqual(result["messages"], [{
            "level": "success",
            "code": "pack_written",
            "message": "팩 생성 완료",
            "detail": f"경로: {output}",
        }])
        self.assertEqual(web.delta_builder_module.CORE_ASSET_SOURCE_ID, previous_core)
        open_session.assert_called_once()
        build.assert_called_once()

    def test_internal_materials_requires_patch_pack(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            materials = Path(tmp) / "materials.json"
            materials.write_text(json.dumps({"tables": {}, "loc": {}, "assets": {}}), encoding="utf-8")
            with patch.object(web, "_open_session", return_value=FakeSession()):
                with self.assertRaisesRegex(ValueError, "only available for patch pack"):
                    web.build_payload({
                        "adapter": "rpfm",
                        "inputPath": "writer.pack",
                        "outputPath": str(Path(tmp) / "out.pack"),
                        "delta": False,
                        "useInternalMaterials": True,
                        "materialPath": str(materials),
                        "recipe": {"modName": "test"},
                    })

    def test_validate_payload_uses_internal_materials_when_requested(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            materials = Path(tmp) / "materials.json"
            materials.write_text(json.dumps({"tables": {}, "loc": {}, "assets": {}}), encoding="utf-8")
            expected_messages = [ValidationMessage("success", "ok", "validated")]

            with (
                patch.object(web, "_open_session") as open_session,
                patch.object(web, "validate", return_value=expected_messages) as validate_mock,
            ):
                result = web.validate_payload({
                    "adapter": "rpfm",
                    "inputPath": "writer.pack",
                    "outputPath": str(Path(tmp) / "out.pack"),
                    "delta": True,
                    "useInternalMaterials": True,
                    "materialPath": str(materials),
                    "recipe": {"modName": "test"},
                })

        self.assertTrue(result["ok"])
        self.assertEqual(result["messages"], [{"level": "success", "code": "ok", "message": "validated"}])
        open_session.assert_not_called()
        self.assertEqual(validate_mock.call_args.args[0].metadata()["adapter"], "internal-materials")

    def test_reference_snapshot_is_bound_to_input_pack_fingerprint(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            snapshot = tmp_path / "reference_snapshot.json"
            pack = tmp_path / "my_hero.pack"
            pack.write_bytes(b"first")

            with patch.object(web, "REFERENCE_SNAPSHOT", snapshot):
                web._write_reference_snapshot(
                    {"packName": "test"},
                    {"pack": {"characters": []}},
                    "asset-token",
                    "reference-token",
                    {"version": "a"},
                    pack_path=pack,
                    include_vanilla=False,
                )

                self.assertIsNotNone(
                    web._load_reference_snapshot(
                        "asset-token",
                        "reference-token",
                        {"version": "a"},
                        pack_path=pack,
                        include_vanilla=False,
                    )
                )

                self.assertIsNone(
                    web._load_reference_snapshot(
                        "asset-token",
                        "reference-token",
                        {"version": "different"},
                        pack_path=pack,
                        include_vanilla=False,
                    )
                )

                self.assertIsNone(
                    web._load_reference_snapshot(
                        "asset-token",
                        "reference-token",
                        {"version": "a"},
                        pack_path=pack,
                        include_vanilla=True,
                    )
                )

                pack.write_bytes(b"second-version")

                self.assertIsNone(
                    web._load_reference_snapshot(
                        "asset-token",
                        "reference-token",
                        {"version": "a"},
                        pack_path=pack,
                        include_vanilla=False,
                    )
                )


if __name__ == "__main__":
    unittest.main()
