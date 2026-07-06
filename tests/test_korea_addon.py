from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from tk_pack_builder import korea_addon


class KoreaAddonMetadataTest(unittest.TestCase):
    def test_kill_character_templates_are_roster_hidden(self) -> None:
        hidden: set[str] = set()

        korea_addon._collect_kill_calls(
            hidden,
            'kill_character("3k_mod_template_historical_go_baekgo_hero_wood")',
        )

        self.assertIn("3k_mod_template_historical_go_baekgo_hero_wood", hidden)

    def test_kill_character_scan_ignores_comments_and_other_scripts(self) -> None:
        hidden: set[str] = set()

        korea_addon._collect_kill_calls(
            hidden,
            '--kill_character("3k_mod_template_historical_gogukcheon_hero_fire")',
            Path("general_korean_born_main.lua"),
        )
        korea_addon._collect_kill_calls(
            hidden,
            'kill_character("3k_mod_template_historical_gogukcheon_hero_fire")',
            Path("ironic_addon_korea_event_global_common.lua"),
        )

        self.assertEqual(hidden, set())

    def test_known_killed_korea_template_is_hidden_when_scripts_are_available(self) -> None:
        metadata = korea_addon.korea_character_metadata("3k_mod_template_historical_go_baekgo_hero_wood")

        self.assertIsNotNone(metadata)
        self.assertTrue(metadata["rosterHidden"])
        self.assertEqual(metadata["koreaHiddenReason"], "script_spawn_then_kill")

    def test_known_playable_korea_leader_is_not_hidden_when_scripts_are_available(self) -> None:
        metadata = korea_addon.korea_character_metadata("3k_mod_template_historical_gogukcheon_hero_fire")

        self.assertIsNotNone(metadata)
        self.assertEqual(metadata["koreaFaction"], "goguryeo")
        self.assertEqual(metadata["koreaFactionKey"], "ironic_faction_goguryeo")
        self.assertNotIn("rosterHidden", metadata)

    def test_builtin_fallback_covers_ui_faction_filters(self) -> None:
        samples = {
            "3k_mod_template_historical_go_gyesu_hero_wood": "goguryeo",
            "3k_mod_template_historical_buyeo_gusu_hero_fire": "baekje",
            "3k_mod_template_historical_kim_gudo_hero_earth": "silla",
            "3k_mod_template_historical_munseong_hero_water": "tamna",
        }

        for template_key, faction in samples.items():
            with self.subTest(template_key=template_key):
                metadata = korea_addon.korea_character_metadata(template_key)

                self.assertIsNotNone(metadata)
                self.assertEqual(metadata["koreaFaction"], faction)
                self.assertTrue(metadata["koreaFactionKey"].startswith("ironic_faction_"))

    def test_builtin_fallback_is_used_when_extract_scripts_are_missing(self) -> None:
        korea_addon.korea_character_index.cache_clear()
        try:
            with patch.object(korea_addon.Path, "is_dir", return_value=False):
                metadata = korea_addon.korea_character_metadata("3k_mod_template_historical_go_gyesu_hero_wood")

            self.assertIsNotNone(metadata)
            self.assertEqual(metadata["koreaFaction"], "goguryeo")
            self.assertEqual(metadata["koreaSourceScript"], "built_in_korea_fallback")
        finally:
            korea_addon.korea_character_index.cache_clear()

    def test_display_name_hint_is_limited_to_korea_metadata(self) -> None:
        self.assertEqual(
            korea_addon.korea_display_name_hint("3k_main_template_historical_qiulijiu_hero_fire"),
            "",
        )
        self.assertTrue(
            korea_addon.korea_display_name_hint("3k_mod_template_historical_go_gyesu_hero_wood")
        )


if __name__ == "__main__":
    unittest.main()
