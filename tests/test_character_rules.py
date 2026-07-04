from __future__ import annotations

import unittest

from tk_pack_builder.character_rules import (
    generic_initial_ceo_key_for_template_gender,
    gender_compatible_initial_ceo_key,
    spawn_safe_initial_ceo_key,
    voiceover_actor_for_template_gender,
)


class CharacterRulesTest(unittest.TestCase):
    def test_historical_initial_ceo_is_preserved_for_cross_gender_template(self) -> None:
        self.assertEqual(
            gender_compatible_initial_ceo_key(
                "3k_main_ceo_initial_data_character_historical_dong_zhuo",
                False,
                "3k_general_fire",
            ),
            "3k_main_ceo_initial_data_character_historical_dong_zhuo",
        )

    def test_lady_initial_ceo_is_preserved_for_cross_gender_template(self) -> None:
        self.assertEqual(
            gender_compatible_initial_ceo_key(
                "3k_main_ceo_initial_data_character_historical_lady_bian",
                True,
                "3k_general_earth",
            ),
            "3k_main_ceo_initial_data_character_historical_lady_bian",
        )

    def test_generic_initial_ceo_remaps_to_template_gender(self) -> None:
        self.assertEqual(
            gender_compatible_initial_ceo_key(
                "3k_main_ceo_initial_data_character_generic_m_fire_general",
                False,
                "3k_general_fire",
            ),
            "3k_main_ceo_initial_data_character_generic_f_fire_general",
        )

    def test_voiceover_actor_uses_template_gender_and_element(self) -> None:
        self.assertEqual(
            voiceover_actor_for_template_gender(False, "3k_general_water"),
            "vo_actor_group_generic_female_water_general",
        )

    def test_generic_initial_ceo_uses_template_gender_and_element(self) -> None:
        self.assertEqual(
            generic_initial_ceo_key_for_template_gender(False, "3k_general_wood"),
            "3k_main_ceo_initial_data_character_generic_f_wood_general",
        )

    def test_spawn_safe_initial_ceo_preserves_historical_unique_key(self) -> None:
        self.assertEqual(
            spawn_safe_initial_ceo_key(
                "3k_mtu_ceo_initial_data_character_historical_lady_guan_yinping",
                False,
                "3k_general_wood",
            ),
            "3k_mtu_ceo_initial_data_character_historical_lady_guan_yinping",
        )

    def test_spawn_safe_initial_ceo_keeps_generic_key(self) -> None:
        self.assertEqual(
            spawn_safe_initial_ceo_key(
                "3k_main_ceo_initial_data_character_generic_m_fire_general",
                False,
                "3k_general_fire",
            ),
            "3k_main_ceo_initial_data_character_generic_f_fire_general",
        )


if __name__ == "__main__":
    unittest.main()
