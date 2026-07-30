from __future__ import annotations

import unittest

from scripts.build_internal_materials_v015 import MERGED_KOREAN_LOC_PATH, finalize_loc_materials
from scripts.build_reference_core_pack import select_loc_files


class MaterialLocMergeTest(unittest.TestCase):
    def test_finalize_loc_materials_keeps_all_keys_and_prefers_korean_sources(self) -> None:
        materials = {
            "loc": {
                "text/db/base.loc": {
                    "sourcePath": "E:/game/data/local_en.pack",
                    "locPath": "text/db/base.loc",
                    "rows": {
                        "ceo_nodes_title_test": "English title",
                        "unprefixed_runtime_key": "English fallback",
                    },
                },
                "text/localisation__.loc": {
                    "sourcePath": "E:/game/data/local_kr.pack",
                    "locPath": "text/localisation__.loc",
                    "rows": {
                        "ceo_nodes_title_test": "Korean title",
                        "unprefixed_runtime_key": "Korean fallback",
                    },
                },
                "text/db/mod.loc": {
                    "sourcePath": "E:/Steam/workshop/3242244024/!!190_expanded_kr.pack",
                    "locPath": "text/db/mod.loc",
                    "rows": {
                        "ceo_nodes_title_test": "Mod Korean title",
                        "mod_only_key": "Mod only",
                    },
                },
            }
        }

        finalize_loc_materials(materials)

        self.assertEqual(list(materials["loc"]), [MERGED_KOREAN_LOC_PATH])
        rows = materials["loc"][MERGED_KOREAN_LOC_PATH]["rows"]
        self.assertEqual(rows["ceo_nodes_title_test"], "Mod Korean title")
        self.assertEqual(rows["unprefixed_runtime_key"], "Korean fallback")
        self.assertEqual(rows["mod_only_key"], "Mod only")

    def test_reference_core_select_loc_files_keeps_direct_row_references(self) -> None:
        materials = {
            "loc": {
                MERGED_KOREAN_LOC_PATH: {
                    "sourcePath": "merged",
                    "locPath": MERGED_KOREAN_LOC_PATH,
                    "rows": {
                        "plain_key_used_by_ui": "Needed",
                        "plain_key_unused": "Unused",
                    },
                }
            }
        }
        tables = {
            "db/example_tables/test": {
                "rows": [{"key": "plain_key_used_by_ui"}],
            }
        }

        selected = select_loc_files(materials, tables)

        self.assertEqual(list(selected), [MERGED_KOREAN_LOC_PATH])
        self.assertEqual(selected[MERGED_KOREAN_LOC_PATH]["plain_key_used_by_ui"], "Needed")
        self.assertNotIn("plain_key_unused", selected[MERGED_KOREAN_LOC_PATH])

    def test_reference_core_select_loc_files_follows_translation_references(self) -> None:
        materials = {
            "loc": {
                MERGED_KOREAN_LOC_PATH: {
                    "sourcePath": "merged",
                    "locPath": MERGED_KOREAN_LOC_PATH,
                    "rows": {
                        "plain_key_used_by_ui": "{{tr:nested_key}}",
                        "nested_key": "Nested text",
                    },
                }
            }
        }
        tables = {
            "db/example_tables/test": {
                "rows": [{"key": "plain_key_used_by_ui"}],
            }
        }

        selected = select_loc_files(materials, tables)[MERGED_KOREAN_LOC_PATH]

        self.assertEqual(selected["plain_key_used_by_ui"], "{{tr:nested_key}}")
        self.assertEqual(selected["nested_key"], "Nested text")

    def test_reference_core_select_loc_files_keeps_ability_mechanic_labels(self) -> None:
        materials = {
            "loc": {
                MERGED_KOREAN_LOC_PATH: {
                    "sourcePath": "merged",
                    "locPath": MERGED_KOREAN_LOC_PATH,
                    "rows": {
                        "unit_stat_localisations_onscreen_name_stat_resistance_all": "피해 저항",
                        "unit_attributes_imued_effect_text_fatigue_immune": "피로 면역",
                        "unit_ability_types_onscreen_name_test_ability": "발동 시 강화",
                        "effects_description_test_fatigue_resistance": "피로 누적 속도",
                    },
                }
            }
        }

        selected = select_loc_files(materials, {})[MERGED_KOREAN_LOC_PATH]

        self.assertEqual(
            selected["unit_stat_localisations_onscreen_name_stat_resistance_all"],
            "피해 저항",
        )
        self.assertEqual(
            selected["unit_attributes_imued_effect_text_fatigue_immune"],
            "피로 면역",
        )
        self.assertEqual(
            selected["unit_ability_types_onscreen_name_test_ability"],
            "발동 시 강화",
        )
        self.assertEqual(
            selected["effects_description_test_fatigue_resistance"],
            "피로 누적 속도",
        )

    def test_reference_core_select_loc_files_keeps_title_candidates_from_initial_ceo(self) -> None:
        materials = {
            "loc": {
                MERGED_KOREAN_LOC_PATH: {
                    "sourcePath": "merged",
                    "locPath": MERGED_KOREAN_LOC_PATH,
                    "rows": {
                        "ceo_nodes_title_3k_main_ceo_node_career_historical_lu_bu_01": "Lu Bu title",
                        "ceo_nodes_description_3k_main_ceo_node_career_historical_lu_bu_01": "Lu Bu description",
                    },
                }
            }
        }
        tables = {
            "db/character_generation_template_game_mode_details_tables/test": {
                "rows": [
                    {
                        "character_generation_template": "3k_main_template_historical_lu_bu_hero_fire",
                        "initial_ceos": "3k_main_ceo_initial_data_character_historical_lu_bu",
                    }
                ],
            }
        }

        selected = select_loc_files(materials, tables)[MERGED_KOREAN_LOC_PATH]

        self.assertEqual(selected["ceo_nodes_title_3k_main_ceo_node_career_historical_lu_bu_01"], "Lu Bu title")
        self.assertEqual(
            selected["ceo_nodes_description_3k_main_ceo_node_career_historical_lu_bu_01"],
            "Lu Bu description",
        )


if __name__ == "__main__":
    unittest.main()
