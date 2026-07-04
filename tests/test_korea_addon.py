from __future__ import annotations

import unittest
from pathlib import Path

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
        if metadata is None:
            self.skipTest("Korea add-on scripts are not extracted in this workspace.")

        self.assertTrue(metadata["rosterHidden"])
        self.assertEqual(metadata["koreaHiddenReason"], "script_spawn_then_kill")

    def test_known_playable_korea_leader_is_not_hidden_when_scripts_are_available(self) -> None:
        metadata = korea_addon.korea_character_metadata("3k_mod_template_historical_gogukcheon_hero_fire")
        if metadata is None:
            self.skipTest("Korea add-on scripts are not extracted in this workspace.")

        self.assertNotIn("rosterHidden", metadata)


if __name__ == "__main__":
    unittest.main()
