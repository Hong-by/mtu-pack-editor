from __future__ import annotations

import unittest
import xml.etree.ElementTree as ET

from scripts.build_dedicated_armour_bob_pool import (
    GENERIC_ARMOUR_ICON,
    POC_KEYS,
    _keep_neutral_production_row,
    _slot_keys,
    _slot_manifest,
    _verify_neutral_delta,
)


class BuildDedicatedArmourBobPoolTest(unittest.TestCase):
    def test_slot_keys_are_stable_and_unique(self) -> None:
        slots = [_slot_manifest(index) for index in range(1, 33)]
        self.assertEqual(slots[0]["slotId"], "slot-001")
        self.assertEqual(slots[-1]["slotId"], "slot-032")
        self.assertEqual(slots[0]["sourceCeoKey"], "*")
        self.assertEqual(len({slot["armourCeoKey"] for slot in slots}), 32)
        self.assertEqual(len({slot["initialCeoKey"] for slot in slots}), 32)
        self.assertEqual(
            _slot_keys(1)["armourCeoKey"],
            "hby_mtu_ancillary_armour_dedicated_001",
        )

    def test_neutral_pool_keeps_only_dedicated_armour_initial_equipment(self) -> None:
        armour = ET.fromstring(
            "<row><equipped_ceo>"
            + POC_KEYS["armourCeoKey"]
            + "</equipped_ceo></row>"
        )
        elephant = ET.fromstring(
            "<row><equipped_ceo>3k_dlc06_ancillary_mount_elephant_unique"
            "</equipped_ceo></row>"
        )
        self.assertTrue(
            _keep_neutral_production_row(
                "ceo_initial_data_equipments.xml",
                armour,
            )
        )
        self.assertFalse(
            _keep_neutral_production_row(
                "ceo_initial_data_equipments.xml",
                elephant,
            )
        )

    def test_neutral_pool_drops_mulu_stats_traits_and_permissions(self) -> None:
        cunning = ET.fromstring(
            "<row><effect>3k_main_effect_character_attribute_cunning_mod"
            "</effect></row>"
        )
        mulu_trait_stage = ET.fromstring(
            "<row><initial_data_stage>"
            "3k_dlc06_initial_data_stage_character_traits_historical_nanman_king_mulu"
            "</initial_data_stage></row>"
        )
        permission = ET.fromstring(
            "<row><scripted_permissions>"
            "3k_dlc06_ceo_permissions_ancillary_armour_nanman_king_mulu"
            "</scripted_permissions></row>"
        )
        self.assertFalse(
            _keep_neutral_production_row(
                "ceo_effect_list_to_effects.xml",
                cunning,
            )
        )
        self.assertFalse(
            _keep_neutral_production_row(
                "ceo_initial_data_to_stages.xml",
                mulu_trait_stage,
            )
        )
        self.assertFalse(
            _keep_neutral_production_row(
                "ceo_initial_data_scripted_permissions.xml",
                permission,
            )
        )

    def test_generic_armour_icon_does_not_reference_source_character(self) -> None:
        self.assertNotIn("mulu", GENERIC_ARMOUR_ICON.lower())

    def test_neutral_delta_rejects_source_character_strings(self) -> None:
        class FakeCcd:
            def __init__(self, strings: list[str]) -> None:
                self._strings = strings

            def all_strings(self):
                return iter(self._strings)

        with self.assertRaisesRegex(RuntimeError, "leaked source-character data"):
            _verify_neutral_delta(
                FakeCcd(["base"]),
                FakeCcd(["base", "3k_dlc06_ancillary_mount_elephant_unique"]),
            )


if __name__ == "__main__":
    unittest.main()
